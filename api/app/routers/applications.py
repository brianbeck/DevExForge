import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import CurrentUser, get_current_user, require_role
from app.models.application import Application, ApplicationDeployment
from app.schemas.application import (
    ApplicationCreate,
    ApplicationDeployRequest,
    ApplicationDeployResponse,
    ApplicationDeploymentResponse,
    ApplicationDetailResponse,
    ApplicationInventoryCell,
    ApplicationInventoryResponse,
    ApplicationInventoryRow,
    ApplicationUpdate,
    DeploymentEventResponse,
    DeploymentHistoryResponse,
)
from app.services import application_service, audit_service, team_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/teams/{slug}/applications", tags=["applications"]
)
admin_router = APIRouter(prefix="/api/v1/applications", tags=["applications"])


def _deployment_to_response(
    deployment: ApplicationDeployment,
) -> ApplicationDeploymentResponse:
    env = deployment.environment
    return ApplicationDeploymentResponse(
        id=deployment.id,
        environmentTier=env.tier,
        environmentId=env.id,
        namespaceName=env.namespace_name,
        argocdAppName=deployment.argocd_app_name,
        imageTag=deployment.image_tag,
        chartVersion=deployment.chart_version,
        gitSha=deployment.git_sha,
        healthStatus=deployment.health_status,
        syncStatus=deployment.sync_status,
        strategy=deployment.strategy,
        deployedAt=deployment.deployed_at,
        deployedBy=deployment.deployed_by,
        lastSyncedAt=deployment.last_synced_at,
    )


def _app_to_response(app: Application) -> ApplicationDetailResponse:
    return ApplicationDetailResponse(
        id=app.id,
        slug=app.name,
        name=app.name,
        displayName=app.display_name,
        description=app.description,
        repoUrl=app.repo_url,
        chartPath=app.chart_path,
        chartRepoUrl=app.chart_repo_url,
        imageRepo=app.image_repo,
        ownerEmail=app.owner_email,
        defaultStrategy=app.default_strategy,
        canarySteps=app.canary_steps,
        metadata=app.app_metadata,
        createdAt=app.created_at,
        updatedAt=app.updated_at,
        deployments=[_deployment_to_response(d) for d in (app.deployments or [])],
    )


def _inventory_rows_to_response(rows: list[dict]) -> ApplicationInventoryResponse:
    inventory_rows: list[ApplicationInventoryRow] = []
    for row in rows:
        cells: dict[str, ApplicationInventoryCell | None] = {}
        for tier, cell in row["deployments"].items():
            if cell is None:
                cells[tier] = None
            else:
                cells[tier] = ApplicationInventoryCell(
                    imageTag=cell.get("imageTag"),
                    deployedAt=cell.get("deployedAt"),
                    deployedBy=cell.get("deployedBy"),
                    healthStatus=cell.get("healthStatus"),
                    syncStatus=cell.get("syncStatus"),
                )
        inventory_rows.append(
            ApplicationInventoryRow(
                id=row["id"],
                name=row["name"],
                displayName=row["displayName"],
                ownerEmail=row["ownerEmail"],
                teamSlug=row["teamSlug"],
                deployments=cells,
            )
        )
    return ApplicationInventoryResponse(
        rows=inventory_rows, total=len(inventory_rows)
    )


async def _check_team_permission(
    slug: str,
    user: CurrentUser,
    db: AsyncSession,
    require_admin: bool = False,
) -> None:
    if "admin" in user.roles:
        return
    team = await team_service.get_team(db, slug)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    if team.owner_email == user.email:
        return
    for m in (team.members or []):
        if m.email == user.email:
            if require_admin:
                if m.role == "admin":
                    return
            else:
                if m.role in ("admin", "developer"):
                    return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to manage applications for this team",
    )


def _value_error_status(message: str) -> int:
    msg = message.lower()
    if "not found" in msg or "does not exist" in msg:
        return 404
    return 409


# ---------------------------------------------------------------------------
# Team-scoped endpoints
# ---------------------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_application(
    slug: str,
    data: ApplicationCreate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApplicationDetailResponse:
    await _check_team_permission(slug, user, db)

    try:
        app = await application_service.create_application(db, slug, data, user)
    except ValueError as e:
        raise HTTPException(status_code=_value_error_status(str(e)), detail=str(e))
    except IntegrityError as e:
        raise HTTPException(status_code=409, detail=str(e))

    await audit_service.log_action(
        db,
        user_email=user.email,
        action="create_application",
        resource_type="application",
        resource_id=str(app.id),
        team_slug=slug,
        request_body=data.model_dump(by_alias=True),
        response_status=201,
    )

    return _app_to_response(app)


@router.get("")
async def list_applications(
    slug: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ApplicationDetailResponse]:
    await _check_team_permission(slug, user, db)
    try:
        apps = await application_service.list_team_applications(db, slug)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return [_app_to_response(a) for a in apps]


@router.get("/inventory")
async def team_inventory(
    slug: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApplicationInventoryResponse:
    await _check_team_permission(slug, user, db)
    try:
        rows = await application_service.get_inventory(db, team_slug=slug)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _inventory_rows_to_response(rows)


@router.get("/{name}")
async def get_application(
    slug: str,
    name: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApplicationDetailResponse:
    await _check_team_permission(slug, user, db)
    try:
        app = await application_service.get_application(db, slug, name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _app_to_response(app)


@router.patch("/{name}")
async def update_application(
    slug: str,
    name: str,
    data: ApplicationUpdate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApplicationDetailResponse:
    await _check_team_permission(slug, user, db, require_admin=True)

    try:
        app = await application_service.update_application(db, slug, name, data)
    except ValueError as e:
        raise HTTPException(status_code=_value_error_status(str(e)), detail=str(e))
    except IntegrityError as e:
        raise HTTPException(status_code=409, detail=str(e))

    await audit_service.log_action(
        db,
        user_email=user.email,
        action="update_application",
        resource_type="application",
        resource_id=str(app.id),
        team_slug=slug,
        request_body=data.model_dump(by_alias=True, exclude_none=True),
        response_status=200,
    )

    # Reload with deployments eager-loaded
    app = await application_service.get_application(db, slug, app.name)
    return _app_to_response(app)


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    slug: str,
    name: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await _check_team_permission(slug, user, db, require_admin=True)

    try:
        app = await application_service.get_application(db, slug, name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    app_id = str(app.id)
    try:
        await application_service.delete_application(db, slug, name)
    except ValueError as e:
        raise HTTPException(status_code=_value_error_status(str(e)), detail=str(e))
    except IntegrityError as e:
        raise HTTPException(status_code=409, detail=str(e))

    await audit_service.log_action(
        db,
        user_email=user.email,
        action="delete_application",
        resource_type="application",
        resource_id=app_id,
        team_slug=slug,
        response_status=204,
    )


@router.get("/{name}/deployments")
async def list_deployments(
    slug: str,
    name: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ApplicationDeploymentResponse]:
    await _check_team_permission(slug, user, db)
    try:
        app = await application_service.get_application(db, slug, name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return [_deployment_to_response(d) for d in (app.deployments or [])]


@router.get("/{name}/history")
async def get_history(
    slug: str,
    name: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 100,
) -> DeploymentHistoryResponse:
    await _check_team_permission(slug, user, db)
    try:
        events = await application_service.get_deployment_history(
            db, slug, name, limit=limit
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return DeploymentHistoryResponse(
        events=[DeploymentEventResponse.model_validate(e) for e in events],
        total=len(events),
    )


@router.post("/{name}/deploy", status_code=status.HTTP_201_CREATED)
async def deploy_application(
    slug: str,
    name: str,
    data: ApplicationDeployRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApplicationDeployResponse:
    await _check_team_permission(slug, user, db)

    try:
        deployment = await application_service.deploy_application(
            db, slug, name, data, user
        )
    except ValueError as e:
        raise HTTPException(status_code=_value_error_status(str(e)), detail=str(e))
    except IntegrityError as e:
        raise HTTPException(status_code=409, detail=str(e))

    await audit_service.log_action(
        db,
        user_email=user.email,
        action="deploy_application",
        resource_type="application",
        resource_id=str(deployment.application_id),
        team_slug=slug,
        request_body=data.model_dump(by_alias=True, exclude_none=True),
        response_status=201,
    )

    # Reload deployment with environment to access namespace_name
    app = await application_service.get_application(db, slug, name)
    namespace_name = ""
    for d in app.deployments:
        if d.id == deployment.id:
            namespace_name = d.environment.namespace_name
            break

    return ApplicationDeployResponse(
        deploymentId=deployment.id,
        argocdAppName=deployment.argocd_app_name,
        namespaceName=namespace_name,
        imageTag=deployment.image_tag,
        strategy=deployment.strategy,
        message=f"Application '{name}' deploy triggered for tier '{data.tier}'",
    )


@router.post("/{name}/refresh")
async def refresh_deployment(
    slug: str,
    name: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ApplicationDeploymentResponse]:
    await _check_team_permission(slug, user, db)

    try:
        app = await application_service.get_application(db, slug, name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    refreshed: list[ApplicationDeployment] = []
    for deployment in app.deployments or []:
        try:
            updated = await application_service.refresh_deployment_status(
                db, str(deployment.id)
            )
            refreshed.append(updated)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception:
            logger.warning(
                "Failed to refresh deployment '%s' for application '%s/%s'",
                deployment.id,
                slug,
                name,
                exc_info=True,
            )

    await audit_service.log_action(
        db,
        user_email=user.email,
        action="refresh_application",
        resource_type="application",
        resource_id=str(app.id),
        team_slug=slug,
        response_status=200,
    )

    # Reload to ensure environment relationship is still loaded
    app = await application_service.get_application(db, slug, name)
    return [_deployment_to_response(d) for d in (app.deployments or [])]


# ---------------------------------------------------------------------------
# Admin-scoped endpoints
# ---------------------------------------------------------------------------


@admin_router.get("")
async def list_all_applications(
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ApplicationDetailResponse]:
    apps = await application_service.list_all_applications(db)
    return [_app_to_response(a) for a in apps]


@admin_router.get("/inventory")
async def global_inventory(
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApplicationInventoryResponse:
    rows = await application_service.get_inventory(db, team_slug=None)
    return _inventory_rows_to_response(rows)
