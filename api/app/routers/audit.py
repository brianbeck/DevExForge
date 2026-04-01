import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import CurrentUser, get_current_user, require_role
from app.models.audit import AuditLog
from app.models.team import Team
from app.schemas.audit import AuditLogList, AuditLogResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["audit"])


@router.get("/api/v1/audit", response_model=AuditLogList)
async def query_audit_log(
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    team_slug: str | None = None,
    user_email: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> AuditLogList:
    stmt = select(AuditLog)
    count_stmt = select(func.count()).select_from(AuditLog)

    if team_slug:
        stmt = stmt.where(AuditLog.team_slug == team_slug)
        count_stmt = count_stmt.where(AuditLog.team_slug == team_slug)
    if user_email:
        stmt = stmt.where(AuditLog.user_email == user_email)
        count_stmt = count_stmt.where(AuditLog.user_email == user_email)
    if action:
        stmt = stmt.where(AuditLog.action == action)
        count_stmt = count_stmt.where(AuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
        count_stmt = count_stmt.where(AuditLog.resource_type == resource_type)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    stmt = stmt.order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    entries = result.scalars().all()

    return AuditLogList(
        entries=[AuditLogResponse.model_validate(e) for e in entries],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/api/v1/teams/{slug}/audit", response_model=AuditLogList)
async def query_team_audit_log(
    slug: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    user_email: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> AuditLogList:
    # Check permission: platform admin or team admin/owner
    if "admin" not in user.roles:
        team_result = await db.execute(select(Team).where(Team.slug == slug))
        team = team_result.scalar_one_or_none()
        if team is None:
            raise HTTPException(status_code=404, detail="Team not found")
        if team.owner_email != user.email:
            is_team_admin = False
            for m in (team.members or []):
                if m.email == user.email and m.role == "admin":
                    is_team_admin = True
                    break
            if not is_team_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have permission to view audit logs for this team",
                )

    stmt = select(AuditLog).where(AuditLog.team_slug == slug)
    count_stmt = select(func.count()).select_from(AuditLog).where(AuditLog.team_slug == slug)

    if user_email:
        stmt = stmt.where(AuditLog.user_email == user_email)
        count_stmt = count_stmt.where(AuditLog.user_email == user_email)
    if action:
        stmt = stmt.where(AuditLog.action == action)
        count_stmt = count_stmt.where(AuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
        count_stmt = count_stmt.where(AuditLog.resource_type == resource_type)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    stmt = stmt.order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    entries = result.scalars().all()

    return AuditLogList(
        entries=[AuditLogResponse.model_validate(e) for e in entries],
        total=total,
        limit=limit,
        offset=offset,
    )
