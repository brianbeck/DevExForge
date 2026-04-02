import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import CurrentUser, get_current_user, require_role
from app.models.catalog import CatalogTemplate
from app.models.environment import Environment
from app.models.team import Team
from app.schemas.catalog import DeployRequest, DeployResponse, TemplateCreate, TemplateResponse
from app.services import audit_service
from app.services.k8s_service import k8s_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["catalog"])


@router.get("/api/v1/catalog/templates")
async def list_templates(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    category: str | None = None,
) -> list[TemplateResponse]:
    stmt = select(CatalogTemplate).order_by(CatalogTemplate.name)
    if category:
        stmt = stmt.where(CatalogTemplate.category == category)
    result = await db.execute(stmt)
    templates = result.scalars().all()
    return [TemplateResponse.model_validate(t) for t in templates]


@router.get("/api/v1/catalog/templates/{template_id}")
async def get_template(
    template_id: UUID,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TemplateResponse:
    result = await db.execute(
        select(CatalogTemplate).where(CatalogTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return TemplateResponse.model_validate(template)


@router.post(
    "/api/v1/catalog/templates",
    status_code=status.HTTP_201_CREATED,
)
async def create_template(
    data: TemplateCreate,
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TemplateResponse:
    existing = await db.execute(
        select(CatalogTemplate).where(CatalogTemplate.name == data.name)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail=f"Template '{data.name}' already exists")

    template = CatalogTemplate(
        name=data.name,
        description=data.description,
        category=data.category,
        chart_repo=data.chart_repo,
        chart_name=data.chart_name,
        chart_version=data.chart_version,
        default_values=data.default_values,
        values_schema=data.values_schema,
    )
    db.add(template)
    await db.flush()

    await audit_service.log_action(
        db,
        user_email=user.email,
        action="create",
        resource_type="catalog_template",
        resource_id=str(template.id),
        request_body=data.model_dump(by_alias=True),
        response_status=201,
    )

    return TemplateResponse.model_validate(template)


@router.delete(
    "/api/v1/catalog/templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_template(
    template_id: UUID,
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    result = await db.execute(
        select(CatalogTemplate).where(CatalogTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    template_id_str = str(template.id)
    await db.delete(template)
    await db.flush()

    await audit_service.log_action(
        db,
        user_email=user.email,
        action="delete",
        resource_type="catalog_template",
        resource_id=template_id_str,
        response_status=204,
    )


@router.post(
    "/api/v1/teams/{slug}/environments/{tier}/deploy",
    status_code=status.HTTP_201_CREATED,
)
async def deploy_from_template(
    slug: str,
    tier: str,
    data: DeployRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DeployResponse:
    team, env, template = await _validate_deploy_request(db, slug, tier, data.template_id, user)

    # Merge values: template defaults + user overrides
    merged_values = dict(template.default_values or {})
    if data.values:
        merged_values.update(data.values)

    # Determine cluster and namespace
    cluster = k8s_service.cluster_for_tier(tier)
    namespace = env.namespace_name
    app_name = f"{slug}-{data.app_name}"

    # Build and apply Argo CD Application CR
    argo_app = _build_argo_application(template, env, slug, tier, app_name, merged_values)

    try:
        k8s_service.create_argo_application(cluster, "argocd", argo_app)
    except Exception as e:
        logger.error("Failed to create Argo CD Application '%s': %s", app_name, e, exc_info=True)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to create Argo CD Application: {e}",
        )

    await audit_service.log_action(
        db,
        user_email=user.email,
        action="deploy",
        resource_type="argo_application",
        resource_id=app_name,
        team_slug=slug,
        request_body={
            "templateId": str(data.template_id),
            "appName": data.app_name,
            "tier": tier,
            "values": data.values,
        },
        response_status=201,
    )

    return DeployResponse(
        message=f"Application '{app_name}' deployed successfully",
        applicationName=app_name,
        namespace=namespace,
        templateName=template.name,
    )


async def _validate_deploy_request(
    db: AsyncSession, slug: str, tier: str, template_id: UUID, user: CurrentUser
) -> tuple[Team, Environment, CatalogTemplate]:
    """Validate team membership, environment existence, and template existence."""
    # Verify team exists
    team_result = await db.execute(select(Team).where(Team.slug == slug))
    team = team_result.scalar_one_or_none()
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")

    # Check user is a member or admin
    if "admin" not in user.roles:
        is_member = team.owner_email == user.email or any(
            m.email == user.email for m in (team.members or [])
        )
        if not is_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to deploy to this team",
            )

    # Verify environment exists
    env_result = await db.execute(
        select(Environment).where(
            Environment.team_id == team.id,
            Environment.tier == tier,
        )
    )
    env = env_result.scalar_one_or_none()
    if env is None:
        raise HTTPException(status_code=404, detail=f"Environment '{tier}' not found for team '{slug}'")

    # Get template
    tmpl_result = await db.execute(
        select(CatalogTemplate).where(CatalogTemplate.id == template_id)
    )
    template = tmpl_result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    if not template.chart_repo or not template.chart_name:
        raise HTTPException(
            status_code=400,
            detail="Template is missing chart_repo or chart_name configuration",
        )

    return team, env, template


def _build_argo_application(
    template: CatalogTemplate,
    env: Environment,
    slug: str,
    tier: str,
    app_name: str,
    values: dict,
) -> dict:
    """Build the Argo CD Application custom resource dict."""
    return {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {
            "name": app_name,
            "namespace": "argocd",
            "labels": {
                "devexforge.io/team": slug,
                "devexforge.io/tier": tier,
                "devexforge.io/template": template.name,
            },
        },
        "spec": {
            "project": "default",
            "source": {
                "repoURL": template.chart_repo,
                "chart": template.chart_name,
                "targetRevision": template.chart_version or "*",
                "helm": {
                    "values": _dict_to_yaml(values),
                },
            },
            "destination": {
                "server": "https://kubernetes.default.svc",
                "namespace": env.namespace_name,
            },
            "syncPolicy": {
                "automated": {
                    "prune": True,
                    "selfHeal": True,
                },
                "syncOptions": ["CreateNamespace=false"],
            },
        },
    }


def _scalar_to_yaml(value: object) -> str:
    """Convert a scalar Python value to its YAML string representation."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return str(value)


def _dict_to_yaml(d: dict, indent: int = 0) -> str:
    """Convert a flat/nested dict to YAML-like string for Helm values."""
    lines = []
    prefix = "  " * indent
    for key, value in d.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(_dict_to_yaml(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}:")
            for item in value:
                if isinstance(item, dict):
                    lines.append(f"{prefix}- ")
                    lines.append(_dict_to_yaml(item, indent + 1))
                else:
                    lines.append(f"{prefix}- {item}")
        else:
            lines.append(f"{prefix}{key}: {_scalar_to_yaml(value)}")
    return "\n".join(lines)
