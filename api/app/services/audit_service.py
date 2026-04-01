from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def log_action(
    db: AsyncSession,
    user_email: str,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    team_slug: str | None = None,
    request_body: dict | None = None,
    response_status: int | None = None,
) -> AuditLog:
    entry = AuditLog(
        user_email=user_email,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        team_slug=team_slug,
        request_body=request_body,
        response_status=response_status,
    )
    db.add(entry)
    await db.flush()
    return entry
