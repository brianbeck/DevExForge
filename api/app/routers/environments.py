import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import CurrentUser, get_current_user
from app.schemas.environment import (
    ArgoCDSpec,
    EnvironmentCreate,
    EnvironmentResponse,
    EnvironmentUpdate,
    LimitRangeSpec,
    NetworkPolicySpec,
    PoliciesSpec,
    ResourceQuotaSpec,
)
from app.services import audit_service, environment_service, team_service
from app.services.k8s_service import k8s_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/teams/{slug}/environments", tags=["environments"])


def _env_to_response(env, team_slug: str) -> EnvironmentResponse:
    return EnvironmentResponse(
        id=env.id,
        teamSlug=team_slug,
        tier=env.tier,
        namespaceName=env.namespace_name,
        phase=env.phase,
        resourceQuota=ResourceQuotaSpec(**env.resource_quota) if env.resource_quota else None,
        limitRange=LimitRangeSpec(**env.limit_range) if env.limit_range else None,
        networkPolicy=NetworkPolicySpec(**env.network_policy) if env.network_policy else None,
        policies=PoliciesSpec(**env.policies) if env.policies else None,
        argoCD=ArgoCDSpec(**env.argocd_config) if env.argocd_config else None,
        createdAt=env.created_at,
        updatedAt=env.updated_at,
    )


async def _check_team_permission(slug: str, user: CurrentUser, db: AsyncSession) -> None:
    if "admin" in user.roles:
        return
    team = await team_service.get_team(db, slug)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    if team.owner_email == user.email:
        return
    for m in (team.members or []):
        if m.email == user.email and m.role in ("admin", "developer"):
            return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to manage environments for this team",
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_environment(
    slug: str,
    data: EnvironmentCreate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EnvironmentResponse:
    await _check_team_permission(slug, user, db)

    try:
        env = await environment_service.create_environment(db, slug, data)
    except (ValueError, IntegrityError) as e:
        raise HTTPException(status_code=409, detail=str(e))

    await audit_service.log_action(
        db,
        user_email=user.email,
        action="create",
        resource_type="environment",
        resource_id=str(env.id),
        team_slug=slug,
        request_body=data.model_dump(by_alias=True),
        response_status=201,
    )

    try:
        k8s_service.apply_environment_crd(slug, env)
    except Exception:
        logger.warning("Failed to sync Environment CRD for '%s-%s'", slug, data.tier, exc_info=True)

    return _env_to_response(env, slug)


@router.get("")
async def list_environments(
    slug: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[EnvironmentResponse]:
    try:
        envs = await environment_service.list_environments(db, slug)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return [_env_to_response(e, slug) for e in envs]


@router.get("/{tier}")
async def get_environment(
    slug: str,
    tier: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EnvironmentResponse:
    try:
        env = await environment_service.get_environment(db, slug, tier)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    return _env_to_response(env, slug)


@router.patch("/{tier}")
async def update_environment(
    slug: str,
    tier: str,
    data: EnvironmentUpdate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EnvironmentResponse:
    await _check_team_permission(slug, user, db)

    try:
        env = await environment_service.update_environment(db, slug, tier, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")

    await audit_service.log_action(
        db,
        user_email=user.email,
        action="update",
        resource_type="environment",
        resource_id=str(env.id),
        team_slug=slug,
        request_body=data.model_dump(by_alias=True, exclude_none=True),
        response_status=200,
    )

    try:
        k8s_service.apply_environment_crd(slug, env)
    except Exception:
        logger.warning("Failed to sync Environment CRD for '%s-%s'", slug, tier, exc_info=True)

    return _env_to_response(env, slug)


@router.delete("/{tier}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_environment(
    slug: str,
    tier: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await _check_team_permission(slug, user, db)

    try:
        env = await environment_service.get_environment(db, slug, tier)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")

    env_id = str(env.id)
    await environment_service.delete_environment(db, slug, tier)

    await audit_service.log_action(
        db,
        user_email=user.email,
        action="delete",
        resource_type="environment",
        resource_id=env_id,
        team_slug=slug,
        response_status=204,
    )

    try:
        k8s_service.delete_environment_crd(slug, tier)
    except Exception:
        logger.warning("Failed to delete Environment CRD for '%s-%s'", slug, tier, exc_info=True)
