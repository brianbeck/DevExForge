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


def _build_audit_query(
    team_slug: str | None = None,
    user_email: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
) -> list:
    """Build a list of filter conditions for audit log queries."""
    filters = []
    if team_slug:
        filters.append(AuditLog.team_slug == team_slug)
    if user_email:
        filters.append(AuditLog.user_email == user_email)
    if action:
        filters.append(AuditLog.action == action)
    if resource_type:
        filters.append(AuditLog.resource_type == resource_type)
    return filters


async def _execute_audit_query(
    db: AsyncSession,
    filters: list,
    limit: int,
    offset: int,
) -> AuditLogList:
    """Execute an audit log query with the given filters and pagination."""
    stmt = select(AuditLog)
    count_stmt = select(func.count()).select_from(AuditLog)

    for condition in filters:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

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


@router.get("/api/v1/audit")
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
    filters = _build_audit_query(team_slug, user_email, action, resource_type)
    return await _execute_audit_query(db, filters, limit, offset)


async def _check_team_audit_permission(
    db: AsyncSession, slug: str, user: CurrentUser
) -> None:
    """Verify the user has permission to view team audit logs."""
    if "admin" in user.roles:
        return
    team_result = await db.execute(select(Team).where(Team.slug == slug))
    team = team_result.scalar_one_or_none()
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    is_authorized = team.owner_email == user.email or any(
        m.email == user.email and m.role == "admin"
        for m in (team.members or [])
    )
    if not is_authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view audit logs for this team",
        )


@router.get("/api/v1/teams/{slug}/audit")
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
    await _check_team_audit_permission(db, slug, user)
    filters = _build_audit_query(slug, user_email, action, resource_type)
    return await _execute_audit_query(db, filters, limit, offset)
