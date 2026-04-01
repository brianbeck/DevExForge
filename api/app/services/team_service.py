import re
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.middleware.auth import CurrentUser
from app.models.environment import Environment
from app.models.team import Team, TeamMember
from app.schemas.team import TeamCreate, TeamUpdate


def slugify(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug


async def create_team(db: AsyncSession, user: CurrentUser, data: TeamCreate) -> Team:
    slug = slugify(data.display_name)

    existing = await db.execute(select(Team).where(Team.slug == slug))
    if existing.scalar_one_or_none() is not None:
        suffix = 1
        while True:
            candidate = f"{slug}-{suffix}"
            check = await db.execute(select(Team).where(Team.slug == candidate))
            if check.scalar_one_or_none() is None:
                slug = candidate
                break
            suffix += 1

    team = Team(
        slug=slug,
        display_name=data.display_name,
        description=data.description,
        owner_email=user.email,
        owner_keycloak_id=user.keycloak_id,
        cost_center=data.cost_center,
        tags=data.tags or {},
    )
    db.add(team)
    await db.flush()

    owner_member = TeamMember(
        team_id=team.id,
        email=user.email,
        keycloak_id=user.keycloak_id,
        role="admin",
    )
    db.add(owner_member)
    await db.flush()

    # Re-fetch with relationships eagerly loaded
    result = await db.execute(
        select(Team)
        .where(Team.id == team.id)
        .options(selectinload(Team.members), selectinload(Team.environments))
    )
    return result.scalar_one()


async def list_teams(db: AsyncSession, user: CurrentUser) -> list[Team]:
    if "admin" in user.roles:
        result = await db.execute(
            select(Team).options(selectinload(Team.members), selectinload(Team.environments))
        )
        return list(result.scalars().all())

    member_team_ids = select(TeamMember.team_id).where(TeamMember.email == user.email)
    result = await db.execute(
        select(Team)
        .where(Team.id.in_(member_team_ids))
        .options(selectinload(Team.members), selectinload(Team.environments))
    )
    return list(result.scalars().all())


async def get_team(db: AsyncSession, slug: str) -> Team | None:
    result = await db.execute(
        select(Team)
        .where(Team.slug == slug)
        .options(selectinload(Team.members), selectinload(Team.environments))
    )
    return result.scalar_one_or_none()


async def update_team(db: AsyncSession, slug: str, data: TeamUpdate) -> Team | None:
    team = await get_team(db, slug)
    if team is None:
        return None

    if data.display_name is not None:
        team.display_name = data.display_name
    if data.description is not None:
        team.description = data.description
    if data.cost_center is not None:
        team.cost_center = data.cost_center
    if data.tags is not None:
        team.tags = data.tags

    team.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return team


async def delete_team(db: AsyncSession, slug: str) -> bool:
    team = await get_team(db, slug)
    if team is None:
        return False
    await db.delete(team)
    await db.flush()
    return True
