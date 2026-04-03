from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.environment import Environment
from app.models.team import Team
from app.schemas.environment import EnvironmentCreate, EnvironmentUpdate
from app.services import policy_service
from app.services.k8s_service import k8s_service


async def _get_team_by_slug(db: AsyncSession, team_slug: str) -> Team:
    result = await db.execute(select(Team).where(Team.slug == team_slug))
    team = result.scalar_one_or_none()
    if team is None:
        raise ValueError(f"Team '{team_slug}' not found")
    return team


async def create_environment(
    db: AsyncSession, team_slug: str, data: EnvironmentCreate
) -> Environment:
    team = await _get_team_by_slug(db, team_slug)

    existing = await db.execute(
        select(Environment).where(
            Environment.team_id == team.id,
            Environment.tier == data.tier,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError(
            f"Environment '{data.tier}' already exists for team '{team_slug}'"
        )

    namespace_name = f"{team_slug}-{data.tier}"

    # Validate policies against tier floor
    policies_dict = data.policies.model_dump(by_alias=True) if data.policies else None
    violations = policy_service.validate_policies_against_floor(data.tier, policies_dict)
    if violations:
        raise ValueError(
            f"Policy floor violations: {'; '.join(violations)}"
        )

    # Apply floor defaults to ensure minimum policies
    policies_dict = policy_service.apply_floor_defaults(data.tier, policies_dict)

    cluster = k8s_service.cluster_for_tier(data.tier)

    env = Environment(
        team_id=team.id,
        tier=data.tier,
        namespace_name=namespace_name,
        cluster=cluster,
        phase="Pending",
        resource_quota=data.resource_quota.model_dump(by_alias=True) if data.resource_quota else None,
        limit_range=data.limit_range.model_dump(by_alias=True) if data.limit_range else None,
        network_policy=data.network_policy.model_dump(by_alias=True) if data.network_policy else None,
        policies=policies_dict,
        argocd_config=data.argocd.model_dump(by_alias=True) if data.argocd else None,
    )
    db.add(env)
    await db.flush()
    return env


async def list_environments(
    db: AsyncSession, team_slug: str
) -> list[Environment]:
    team = await _get_team_by_slug(db, team_slug)
    result = await db.execute(
        select(Environment).where(Environment.team_id == team.id)
    )
    return list(result.scalars().all())


async def get_environment(
    db: AsyncSession, team_slug: str, tier: str
) -> Environment | None:
    team = await _get_team_by_slug(db, team_slug)
    result = await db.execute(
        select(Environment).where(
            Environment.team_id == team.id,
            Environment.tier == tier,
        )
    )
    return result.scalar_one_or_none()


async def update_environment(
    db: AsyncSession, team_slug: str, tier: str, data: EnvironmentUpdate
) -> Environment | None:
    env = await get_environment(db, team_slug, tier)
    if env is None:
        return None

    if data.resource_quota is not None:
        env.resource_quota = data.resource_quota.model_dump(by_alias=True)
    if data.limit_range is not None:
        env.limit_range = data.limit_range.model_dump(by_alias=True)
    if data.network_policy is not None:
        env.network_policy = data.network_policy.model_dump(by_alias=True)
    if data.policies is not None:
        policies_dict = data.policies.model_dump(by_alias=True)
        violations = policy_service.validate_policies_against_floor(env.tier, policies_dict)
        if violations:
            raise ValueError(
                f"Policy floor violations: {'; '.join(violations)}"
            )
        env.policies = policy_service.apply_floor_defaults(env.tier, policies_dict)
    if data.argocd is not None:
        env.argocd_config = data.argocd.model_dump(by_alias=True)

    await db.flush()
    return env


async def delete_environment(
    db: AsyncSession, team_slug: str, tier: str
) -> bool:
    env = await get_environment(db, team_slug, tier)
    if env is None:
        return False
    await db.delete(env)
    await db.flush()
    return True
