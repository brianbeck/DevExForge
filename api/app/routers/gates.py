import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import CurrentUser, get_current_user, require_role
from app.models.application import Application
from app.models.promotion import PromotionGate
from app.models.team import Team
from app.routers.applications import _check_team_permission
from app.schemas.promotion import (
    PromotionGateCreate,
    PromotionGateListResponse,
    PromotionGateResponse,
)
from app.services import audit_service

logger = logging.getLogger(__name__)

admin_router = APIRouter(
    prefix="/api/v1/admin/promotion-gates", tags=["gates"]
)
team_router = APIRouter(
    prefix="/api/v1/teams/{slug}/applications/{name}/gates", tags=["gates"]
)


def _to_response(gate: PromotionGate) -> PromotionGateResponse:
    return PromotionGateResponse.model_validate(gate)


async def _get_team_and_app(
    db: AsyncSession, slug: str, name: str
) -> tuple[Team, Application]:
    team_result = await db.execute(select(Team).where(Team.slug == slug))
    team = team_result.scalar_one_or_none()
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    app_result = await db.execute(
        select(Application).where(
            Application.team_id == team.id, Application.name == name
        )
    )
    app = app_result.scalar_one_or_none()
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return team, app


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@admin_router.get("")
async def list_all_gates(
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    scope: str | None = None,
    tier: str | None = None,
) -> PromotionGateListResponse:
    stmt = select(PromotionGate)
    if scope is not None:
        stmt = stmt.where(PromotionGate.scope == scope)
    if tier is not None:
        stmt = stmt.where(PromotionGate.tier == tier)
    stmt = stmt.order_by(PromotionGate.created_at)
    result = await db.execute(stmt)
    gates = result.scalars().all()
    items = [_to_response(g) for g in gates]
    return PromotionGateListResponse(items=items, total=len(items))


@admin_router.post("", status_code=status.HTTP_201_CREATED)
async def create_platform_gate(
    data: PromotionGateCreate,
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PromotionGateResponse:
    if data.scope != "platform":
        raise HTTPException(
            status_code=400,
            detail="Admin gate endpoint only accepts scope='platform'",
        )

    gate = PromotionGate(
        scope="platform",
        team_id=None,
        application_id=None,
        tier=data.tier,
        gate_type=data.gate_type,
        config=data.config or {},
        enforcement=data.enforcement,
        created_by=user.email,
    )
    db.add(gate)
    await db.flush()

    await audit_service.log_action(
        db,
        user_email=user.email,
        action="create_gate",
        resource_type="promotion_gate",
        resource_id=str(gate.id),
        request_body=data.model_dump(by_alias=True),
        response_status=201,
    )

    return _to_response(gate)


@admin_router.delete("/{gate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_any_gate(
    gate_id: UUID,
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    result = await db.execute(
        select(PromotionGate).where(PromotionGate.id == gate_id)
    )
    gate = result.scalar_one_or_none()
    if gate is None:
        raise HTTPException(status_code=404, detail="Promotion gate not found")

    gate_id_str = str(gate.id)
    await db.delete(gate)
    await db.flush()

    await audit_service.log_action(
        db,
        user_email=user.email,
        action="delete_gate",
        resource_type="promotion_gate",
        resource_id=gate_id_str,
        response_status=204,
    )


# ---------------------------------------------------------------------------
# Team-scoped endpoints
# ---------------------------------------------------------------------------


@team_router.get("")
async def list_app_gates(
    slug: str,
    name: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PromotionGateListResponse:
    await _check_team_permission(slug, user, db)
    _team, app = await _get_team_and_app(db, slug, name)

    stmt = select(PromotionGate).where(
        or_(
            PromotionGate.scope == "platform",
            (PromotionGate.scope == "team")
            & (PromotionGate.team_id == app.team_id)
            & (
                (PromotionGate.application_id.is_(None))
                | (PromotionGate.application_id == app.id)
            ),
        )
    ).order_by(PromotionGate.tier, PromotionGate.created_at)

    result = await db.execute(stmt)
    gates = result.scalars().all()
    items = [_to_response(g) for g in gates]
    return PromotionGateListResponse(items=items, total=len(items))


@team_router.post("", status_code=status.HTTP_201_CREATED)
async def create_team_gate(
    slug: str,
    name: str,
    data: PromotionGateCreate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PromotionGateResponse:
    await _check_team_permission(slug, user, db, require_admin=True)
    team, app = await _get_team_and_app(db, slug, name)

    if data.application_id is not None and data.application_id != app.id:
        raise HTTPException(
            status_code=400,
            detail="application_id in body does not match URL application",
        )

    gate = PromotionGate(
        scope="team",
        team_id=team.id,
        application_id=data.application_id,
        tier=data.tier,
        gate_type=data.gate_type,
        config=data.config or {},
        enforcement=data.enforcement,
        created_by=user.email,
    )
    db.add(gate)
    await db.flush()

    await audit_service.log_action(
        db,
        user_email=user.email,
        action="create_gate",
        resource_type="promotion_gate",
        resource_id=str(gate.id),
        team_slug=slug,
        request_body=data.model_dump(by_alias=True),
        response_status=201,
    )

    return _to_response(gate)


@team_router.delete("/{gate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team_gate(
    slug: str,
    name: str,
    gate_id: UUID,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await _check_team_permission(slug, user, db, require_admin=True)
    team, _app = await _get_team_and_app(db, slug, name)

    result = await db.execute(
        select(PromotionGate).where(PromotionGate.id == gate_id)
    )
    gate = result.scalar_one_or_none()
    if gate is None:
        raise HTTPException(status_code=404, detail="Promotion gate not found")

    if gate.scope == "platform":
        raise HTTPException(
            status_code=403,
            detail="Platform gates cannot be deleted via the team endpoint",
        )
    if gate.team_id != team.id:
        raise HTTPException(
            status_code=404, detail="Promotion gate not found for this team"
        )

    gate_id_str = str(gate.id)
    await db.delete(gate)
    await db.flush()

    await audit_service.log_action(
        db,
        user_email=user.email,
        action="delete_gate",
        resource_type="promotion_gate",
        resource_id=gate_id_str,
        team_slug=slug,
        response_status=204,
    )
