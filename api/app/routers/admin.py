import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import CurrentUser, require_role
from app.models.admin import PolicyProfile, QuotaPreset
from app.models.team import Team
from app.schemas.admin import (
    AdminTeamSummary,
    PolicyProfileCreate,
    PolicyProfileResponse,
    QuotaPresetCreate,
    QuotaPresetResponse,
)
from app.services import audit_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# --- Quota Presets ---


@router.get("/quota-presets")
async def list_quota_presets(
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[QuotaPresetResponse]:
    result = await db.execute(select(QuotaPreset).order_by(QuotaPreset.name))
    presets = result.scalars().all()
    return [QuotaPresetResponse.model_validate(p) for p in presets]


@router.post(
    "/quota-presets",
    status_code=status.HTTP_201_CREATED,
)
async def create_quota_preset(
    data: QuotaPresetCreate,
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> QuotaPresetResponse:
    existing = await db.execute(
        select(QuotaPreset).where(QuotaPreset.name == data.name)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail=f"Quota preset '{data.name}' already exists")

    preset = QuotaPreset(
        name=data.name,
        cpu_request=data.cpu_request,
        cpu_limit=data.cpu_limit,
        memory_request=data.memory_request,
        memory_limit=data.memory_limit,
        pods=data.pods,
        services=data.services,
        pvcs=data.pvcs,
    )
    db.add(preset)
    await db.flush()

    await audit_service.log_action(
        db,
        user_email=user.email,
        action="create",
        resource_type="quota_preset",
        resource_id=str(preset.id),
        request_body=data.model_dump(by_alias=True),
        response_status=201,
    )

    return QuotaPresetResponse.model_validate(preset)


@router.delete("/quota-presets/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quota_preset(
    preset_id: UUID,
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    result = await db.execute(
        select(QuotaPreset).where(QuotaPreset.id == preset_id)
    )
    preset = result.scalar_one_or_none()
    if preset is None:
        raise HTTPException(status_code=404, detail="Quota preset not found")

    preset_id_str = str(preset.id)
    await db.delete(preset)
    await db.flush()

    await audit_service.log_action(
        db,
        user_email=user.email,
        action="delete",
        resource_type="quota_preset",
        resource_id=preset_id_str,
        response_status=204,
    )


# --- Policy Profiles ---


@router.get("/policy-profiles")
async def list_policy_profiles(
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[PolicyProfileResponse]:
    result = await db.execute(select(PolicyProfile).order_by(PolicyProfile.name))
    profiles = result.scalars().all()
    return [PolicyProfileResponse.model_validate(p) for p in profiles]


@router.post(
    "/policy-profiles",
    status_code=status.HTTP_201_CREATED,
)
async def create_policy_profile(
    data: PolicyProfileCreate,
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PolicyProfileResponse:
    existing = await db.execute(
        select(PolicyProfile).where(PolicyProfile.name == data.name)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail=f"Policy profile '{data.name}' already exists")

    profile = PolicyProfile(
        name=data.name,
        max_critical_cves=data.max_critical_cves,
        max_high_cves=data.max_high_cves,
        require_non_root=data.require_non_root,
        require_read_only_root=data.require_read_only_root,
        require_resource_limits=data.require_resource_limits,
    )
    db.add(profile)
    await db.flush()

    await audit_service.log_action(
        db,
        user_email=user.email,
        action="create",
        resource_type="policy_profile",
        resource_id=str(profile.id),
        request_body=data.model_dump(by_alias=True),
        response_status=201,
    )

    return PolicyProfileResponse.model_validate(profile)


@router.delete("/policy-profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy_profile(
    profile_id: UUID,
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    result = await db.execute(
        select(PolicyProfile).where(PolicyProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Policy profile not found")

    profile_id_str = str(profile.id)
    await db.delete(profile)
    await db.flush()

    await audit_service.log_action(
        db,
        user_email=user.email,
        action="delete",
        resource_type="policy_profile",
        resource_id=profile_id_str,
        response_status=204,
    )


# --- Admin Team Overview ---


@router.get("/teams")
async def list_all_teams(
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AdminTeamSummary]:
    result = await db.execute(
        select(Team)
        .options(selectinload(Team.members), selectinload(Team.environments))
        .order_by(Team.slug)
    )
    teams = result.scalars().all()
    return [
        AdminTeamSummary(
            id=t.id,
            slug=t.slug,
            displayName=t.display_name,
            ownerEmail=t.owner_email,
            memberCount=len(t.members) if t.members else 0,
            environmentCount=len(t.environments) if t.environments else 0,
            createdAt=t.created_at,
        )
        for t in teams
    ]
