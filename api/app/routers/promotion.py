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


@router.post("/{app_name}/promote", response_model=PromoteResponse)
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
    # 1. Verify user has admin role on the team
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

    # 2. Verify source environment exists
    try:
        source_env = await environment_service.get_environment(db, slug, tier)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if source_env is None:
        raise HTTPException(status_code=404, detail=f"Source environment '{tier}' not found")

    # 3. Verify target environment exists
    try:
        target_env = await environment_service.get_environment(db, slug, data.target_tier)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if target_env is None:
        raise HTTPException(
            status_code=404,
            detail=f"Target environment '{data.target_tier}' not found. Create it first.",
        )

    # 4. Validate promotion direction (can only promote forward)
    tier_order = {"dev": 0, "staging": 1, "production": 2}
    if tier_order.get(data.target_tier, 0) <= tier_order.get(tier, 0):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot promote from '{tier}' to '{data.target_tier}'. "
                   f"Promotion must go forward (dev -> staging -> production).",
        )

    # 5. Read the source Argo CD Application
    source_cluster = k8s_service.cluster_for_tier(tier)
    argocd_ns = "argocd"
    source_app = k8s_service.get_argo_application(source_cluster, argocd_ns, app_name)
    if source_app is None:
        raise HTTPException(
            status_code=404,
            detail=f"Application '{app_name}' not found in {tier} environment",
        )

    # 6. Build the target Application CR
    source_spec = source_app.get("spec", {})
    target_cluster = k8s_service.cluster_for_tier(data.target_tier)
    target_namespace = target_env.namespace_name
    target_app_name = app_name  # same name in target

    target_app_body = {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {
            "name": target_app_name,
            "namespace": argocd_ns,
            "labels": {
                "devexforge.brianbeck.net/team": slug,
                "devexforge.brianbeck.net/tier": data.target_tier,
                "devexforge.brianbeck.net/promoted-from": tier,
            },
        },
        "spec": {
            "project": target_namespace,  # AppProject name matches namespace
            "source": dict(source_spec.get("source", {})),  # same chart/repo/revision
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

    # Apply value overrides if provided
    if data.value_overrides:
        source_helm = target_app_body["spec"]["source"].get("helm", {})
        existing_params = {
            p["name"]: p for p in source_helm.get("parameters", [])
        }
        for key, value in data.value_overrides.items():
            existing_params[key] = {"name": key, "value": str(value)}
        source_helm["parameters"] = list(existing_params.values())
        target_app_body["spec"]["source"]["helm"] = source_helm

    # 7. Create/update the Application in the target cluster
    try:
        k8s_service.create_argo_application(target_cluster, argocd_ns, target_app_body)
    except Exception as e:
        logger.error("Failed to create Application in %s: %s", target_cluster, e)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to create application in {target_cluster}: {e}",
        )

    # 8. Audit log
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
