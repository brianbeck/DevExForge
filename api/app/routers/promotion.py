"""Application promotion between environments."""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import CurrentUser, get_current_user
from app.schemas.environment import PromoteRequest, PromoteResponse
from app.services import audit_service, environment_service, team_service
from app.services.k8s_service import k8s_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/teams/{slug}/environments/{tier}/applications",
    tags=["promotion"],
)


TIER_ORDER = {"dev": 0, "staging": 1, "production": 2}


async def _validate_promotion(
    db: AsyncSession, slug: str, tier: str, target_tier: str, user: CurrentUser
) -> tuple:
    """Validate permissions, environments exist, and promotion direction is forward.

    Returns (source_env, target_env).
    """
    # Verify user has admin role on the team
    if "admin" not in user.roles:
        team = await team_service.get_team(db, slug)
        if team is None:
            raise HTTPException(status_code=404, detail="Team not found")
        is_team_admin = team.owner_email == user.email or any(
            m.email == user.email and m.role == "admin"
            for m in (team.members or [])
        )
        if not is_team_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only team admins can promote applications",
            )

    # Verify source environment exists
    source_env = await _get_environment_or_404(db, slug, tier, "Source")

    # Verify target environment exists
    target_env = await _get_environment_or_404(db, slug, target_tier, "Target")

    # Validate promotion direction (can only promote forward)
    if TIER_ORDER.get(target_tier, 0) <= TIER_ORDER.get(tier, 0):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot promote from '{tier}' to '{target_tier}'. "
                   f"Promotion must go forward (dev -> staging -> production).",
        )

    return source_env, target_env


async def _get_environment_or_404(
    db: AsyncSession, slug: str, tier: str, label: str
):
    """Fetch an environment, raising 404 if not found."""
    try:
        env = await environment_service.get_environment(db, slug, tier)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if env is None:
        detail = f"{label} environment '{tier}' not found"
        if label == "Target":
            detail += ". Create it first."
        raise HTTPException(status_code=404, detail=detail)
    return env


def _build_promotion_app(
    source_app: dict, slug: str, tier: str, target_tier: str,
    app_name: str, target_namespace: str, value_overrides: dict | None,
) -> dict:
    """Build the Argo CD Application CR for the promotion target."""
    source_spec = source_app.get("spec", {})
    argocd_ns = "argocd"

    target_app_body = {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {
            "name": app_name,
            "namespace": argocd_ns,
            "labels": {
                "devexforge.brianbeck.net/team": slug,
                "devexforge.brianbeck.net/tier": target_tier,
                "devexforge.brianbeck.net/promoted-from": tier,
            },
        },
        "spec": {
            "project": target_namespace,
            "source": dict(source_spec.get("source", {})),
            "destination": {
                "server": "https://kubernetes.default.svc",
                "namespace": target_namespace,
            },
            "syncPolicy": {
                "automated": {
                    "prune": True,
                    "selfHeal": True,
                },
            },
        },
    }

    if value_overrides:
        _apply_helm_overrides(target_app_body, value_overrides)

    return target_app_body


def _apply_helm_overrides(app_body: dict, overrides: dict) -> None:
    """Merge value overrides into the Helm parameters of an Application CR."""
    source_helm = app_body["spec"]["source"].get("helm", {})
    existing_params = {
        p["name"]: p for p in source_helm.get("parameters", [])
    }
    for key, value in overrides.items():
        existing_params[key] = {"name": key, "value": str(value)}
    source_helm["parameters"] = list(existing_params.values())
    app_body["spec"]["source"]["helm"] = source_helm


@router.post("/{app_name}/promote")
async def promote_application(
    slug: str,
    tier: str,
    app_name: str,
    data: PromoteRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PromoteResponse:
    """Promote an application from source tier to target tier.

    Reads the Argo CD Application from the source cluster/namespace,
    creates or updates it in the target cluster/namespace with the same
    source (repo, chart, revision) but targeting the new namespace.
    """
    _source_env, target_env = await _validate_promotion(db, slug, tier, data.target_tier, user)

    # Read the source Argo CD Application
    source_cluster = k8s_service.cluster_for_tier(tier)
    argocd_ns = "argocd"
    source_app = k8s_service.get_argo_application(source_cluster, argocd_ns, app_name)
    if source_app is None:
        raise HTTPException(
            status_code=404,
            detail=f"Application '{app_name}' not found in {tier} environment",
        )

    # Build and apply the target Application CR
    target_cluster = k8s_service.cluster_for_tier(data.target_tier)
    target_namespace = target_env.namespace_name
    target_app_body = _build_promotion_app(
        source_app, slug, tier, data.target_tier,
        app_name, target_namespace, data.value_overrides,
    )

    try:
        k8s_service.create_argo_application(target_cluster, argocd_ns, target_app_body)
    except Exception as e:
        logger.error("Failed to create Application in %s: %s", target_cluster, e)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to create application in {target_cluster}: {e}",
        )

    await audit_service.log_action(
        db,
        user_email=user.email,
        action="promote",
        resource_type="application",
        resource_id=app_name,
        team_slug=slug,
        request_body={
            "sourceTier": tier,
            "targetTier": data.target_tier,
            "applicationName": app_name,
            "valueOverrides": data.value_overrides,
        },
        response_status=200,
    )

    return PromoteResponse(
        message=f"Successfully promoted '{app_name}' from {tier} to {data.target_tier}",
        sourceTier=tier,
        targetTier=data.target_tier,
        applicationName=app_name,
        targetCluster=target_cluster,
        targetNamespace=target_namespace,
    )
