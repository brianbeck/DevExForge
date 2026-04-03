from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import Team, TeamMember
from app.schemas.team import MemberCreate


async def _get_team_by_slug(db: AsyncSession, team_slug: str) -> Team:
    result = await db.execute(select(Team).where(Team.slug == team_slug))
    team = result.scalar_one_or_none()
    if team is None:
        raise ValueError(f"Team '{team_slug}' not found")
    return team


async def add_member(db: AsyncSession, team_slug: str, data: MemberCreate) -> TeamMember:
    team = await _get_team_by_slug(db, team_slug)

    existing = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team.id,
            TeamMember.email == data.email,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError(f"Member '{data.email}' already exists in team '{team_slug}'")

    member = TeamMember(
        team_id=team.id,
        email=data.email,
        role=data.role,
    )
    db.add(member)
    await db.flush()
    return member


async def list_members(db: AsyncSession, team_slug: str) -> list[TeamMember]:
    team = await _get_team_by_slug(db, team_slug)
    result = await db.execute(
        select(TeamMember).where(TeamMember.team_id == team.id)
    )
    return list(result.scalars().all())


async def update_member_role(
    db: AsyncSession, team_slug: str, email: str, role: str
) -> TeamMember:
    team = await _get_team_by_slug(db, team_slug)

    result = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team.id,
            TeamMember.email == email,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise ValueError(f"Member '{email}' not found in team '{team_slug}'")

    member.role = role
    await db.flush()
    return member


async def remove_member(db: AsyncSession, team_slug: str, email: str) -> bool:
    team = await _get_team_by_slug(db, team_slug)

    if team.owner_email == email:
        raise ValueError("Cannot remove team owner. Transfer ownership first.")

    result = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team.id,
            TeamMember.email == email,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise ValueError(f"Member '{email}' not found in team '{team_slug}'")

    await db.delete(member)
    await db.flush()
    return True


async def transfer_ownership(
    db: AsyncSession, team_slug: str, new_owner_email: str
) -> Team:
    team = await _get_team_by_slug(db, team_slug)

    result = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team.id,
            TeamMember.email == new_owner_email,
        )
    )
    new_owner_member = result.scalar_one_or_none()
    if new_owner_member is None:
        raise ValueError(
            f"New owner '{new_owner_email}' must be an existing member of team '{team_slug}'"
        )

    team.owner_email = new_owner_email
    team.owner_keycloak_id = new_owner_member.keycloak_id
    new_owner_member.role = "admin"
    await db.flush()
    return team
