import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import CurrentUser, get_current_user
from app.routers.applications import _check_team_permission, _value_error_status
from app.schemas.promotion import RolloutActionResponse, RolloutStatusResponse
from app.services import application_service, audit_service
from app.services.k8s_service import k8s_service
from app.services.rollout_service import (
    RolloutsNotAvailable,
    abort_rollout,
    check_rollouts_available,
    get_rollout_status,
    pause_rollout,
    promote_rollout,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/teams/{slug}/applications", tags=["rollouts"]
)

ROLLOUTS_UNAVAILABLE_MSG = "Argo Rollouts not installed on target cluster"


async def _resolve_target(
    slug: str,
    name: str,
    tier: str,
    db: AsyncSession,
) -> tuple[str, str, str]:
    """Resolve (cluster, namespace, rollout_name) for the given app/tier."""
    try:
        app = await application_service.get_application(db, slug, name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        cluster = k8s_service.cluster_for_tier(tier)
    except ValueError as e:
        raise HTTPException(
            status_code=_value_error_status(str(e)), detail=str(e)
        )

    namespace = f"{slug}-{tier}"
    return cluster, namespace, app.name


async def _ensure_rollouts_available(cluster: str) -> None:
    try:
        available = await check_rollouts_available(cluster)
    except RolloutsNotAvailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ROLLOUTS_UNAVAILABLE_MSG,
        )
    if not available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ROLLOUTS_UNAVAILABLE_MSG,
        )


@router.get("/{name}/rollout")
async def rollout_status(
    slug: str,
    name: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    tier: str = "production",
) -> RolloutStatusResponse:
    await _check_team_permission(slug, user, db)
    cluster, namespace, rollout_name = await _resolve_target(slug, name, tier, db)
    await _ensure_rollouts_available(cluster)

    try:
        data = await get_rollout_status(cluster, namespace, rollout_name)
    except RolloutsNotAvailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ROLLOUTS_UNAVAILABLE_MSG,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=_value_error_status(str(e)), detail=str(e)
        )

    app = await application_service.get_application(db, slug, name)
    strategy = app.default_strategy or "bluegreen"
    total_steps: int | None = None
    if strategy == "canary":
        total_steps = len(app.canary_steps or [])

    phase = data.get("phase") or "Unknown"
    if phase not in ("Progressing", "Paused", "Healthy", "Degraded"):
        # Normalize unknown/NotFound phases to Degraded so response schema validates.
        phase = "Degraded"

    return RolloutStatusResponse(
        appName=rollout_name,
        namespace=namespace,
        strategy=strategy,
        phase=phase,  # type: ignore[arg-type]
        currentStepIndex=data.get("currentStepIndex"),
        totalSteps=total_steps,
        stableRevision=data.get("stableRevision") or "",
        canaryRevision=data.get("canaryRevision"),
        activeService=data.get("activeService"),
        previewService=data.get("previewService"),
        message=data.get("message") or "",
    )


async def _run_action(
    slug: str,
    name: str,
    tier: str,
    action: str,
    user: CurrentUser,
    db: AsyncSession,
) -> RolloutActionResponse:
    await _check_team_permission(slug, user, db, require_admin=True)
    cluster, namespace, rollout_name = await _resolve_target(slug, name, tier, db)
    await _ensure_rollouts_available(cluster)

    actions = {
        "promote": (promote_rollout, "rollout promoted"),
        "pause": (pause_rollout, "rollout paused"),
        "abort": (abort_rollout, "rollout aborted"),
    }
    fn, message = actions[action]

    try:
        await fn(cluster, namespace, rollout_name)
    except RolloutsNotAvailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ROLLOUTS_UNAVAILABLE_MSG,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=_value_error_status(str(e)), detail=str(e)
        )

    await audit_service.log_action(
        db,
        user_email=user.email,
        action=f"rollout_{action}",
        resource_type="application",
        resource_id=rollout_name,
        team_slug=slug,
        request_body={"tier": tier},
        response_status=200,
    )

    return RolloutActionResponse(success=True, message=message)


@router.post("/{name}/rollout/promote")
async def rollout_promote(
    slug: str,
    name: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    tier: str = "production",
) -> RolloutActionResponse:
    return await _run_action(slug, name, tier, "promote", user, db)


@router.post("/{name}/rollout/pause")
async def rollout_pause(
    slug: str,
    name: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    tier: str = "production",
) -> RolloutActionResponse:
    return await _run_action(slug, name, tier, "pause", user, db)


@router.post("/{name}/rollout/abort")
async def rollout_abort(
    slug: str,
    name: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    tier: str = "production",
) -> RolloutActionResponse:
    return await _run_action(slug, name, tier, "abort", user, db)
