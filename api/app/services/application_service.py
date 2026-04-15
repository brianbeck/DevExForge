import logging
import re
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.middleware.auth import CurrentUser
from app.models.application import (
    Application,
    ApplicationDeployment,
    ApplicationDeploymentEvent,
)
from app.models.environment import Environment
from app.models.team import Team
from app.schemas.application import (
    ApplicationCreate,
    ApplicationDeployRequest,
    ApplicationUpdate,
)
from app.services.k8s_service import k8s_service

logger = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug


async def _get_team_by_slug(db: AsyncSession, team_slug: str) -> Team:
    """Raises ValueError if team not found. Eager-loads members."""
    result = await db.execute(
        select(Team)
        .where(Team.slug == team_slug)
        .options(selectinload(Team.members))
    )
    team = result.scalar_one_or_none()
    if team is None:
        raise ValueError(f"Team '{team_slug}' not found")
    return team


async def _get_application(
    db: AsyncSession, team_slug: str, name: str
) -> Application:
    """Raises ValueError if application not found. Eager-loads team + deployments."""
    result = await db.execute(
        select(Application)
        .join(Team, Team.id == Application.team_id)
        .where(Team.slug == team_slug, Application.name == name)
        .options(
            selectinload(Application.team),
            selectinload(Application.deployments).selectinload(
                ApplicationDeployment.environment
            ),
        )
    )
    app = result.scalar_one_or_none()
    if app is None:
        raise ValueError(
            f"Application '{name}' not found for team '{team_slug}'"
        )
    return app


async def create_application(
    db: AsyncSession,
    team_slug: str,
    data: ApplicationCreate,
    user: CurrentUser,
) -> Application:
    team = await _get_team_by_slug(db, team_slug)

    name_slug = _slugify(data.name)
    if not name_slug:
        raise ValueError("Application name must contain alphanumeric characters")

    existing = await db.execute(
        select(Application).where(
            Application.team_id == team.id,
            Application.name == name_slug,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError(
            f"Application '{name_slug}' already exists for team '{team_slug}'"
        )

    app = Application(
        team_id=team.id,
        name=name_slug,
        display_name=data.display_name,
        description=data.description,
        repo_url=data.repo_url,
        chart_path=data.chart_path,
        chart_repo_url=data.chart_repo_url,
        image_repo=data.image_repo,
        owner_email=data.owner_email,
        default_strategy=data.default_strategy,
        app_metadata=data.metadata,
    )
    db.add(app)
    await db.flush()

    return await _get_application(db, team_slug, name_slug)


async def list_team_applications(
    db: AsyncSession,
    team_slug: str,
) -> list[Application]:
    team = await _get_team_by_slug(db, team_slug)
    result = await db.execute(
        select(Application)
        .where(Application.team_id == team.id)
        .options(
            selectinload(Application.team),
            selectinload(Application.deployments).selectinload(
                ApplicationDeployment.environment
            ),
        )
    )
    return list(result.scalars().all())


async def list_all_applications(
    db: AsyncSession,
) -> list[Application]:
    result = await db.execute(
        select(Application).options(
            selectinload(Application.team),
            selectinload(Application.deployments).selectinload(
                ApplicationDeployment.environment
            ),
        )
    )
    return list(result.scalars().all())


async def get_application(
    db: AsyncSession,
    team_slug: str,
    name: str,
) -> Application:
    return await _get_application(db, team_slug, name)


async def update_application(
    db: AsyncSession,
    team_slug: str,
    name: str,
    data: ApplicationUpdate,
) -> Application:
    app = await _get_application(db, team_slug, name)

    if data.display_name is not None:
        app.display_name = data.display_name
    if data.description is not None:
        app.description = data.description
    if data.repo_url is not None:
        app.repo_url = data.repo_url
    if data.chart_path is not None:
        app.chart_path = data.chart_path
    if data.chart_repo_url is not None:
        app.chart_repo_url = data.chart_repo_url
    if data.image_repo is not None:
        app.image_repo = data.image_repo
    if data.owner_email is not None:
        app.owner_email = data.owner_email
    if data.default_strategy is not None:
        app.default_strategy = data.default_strategy
    if data.metadata is not None:
        app.app_metadata = data.metadata

    app.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return app


async def delete_application(
    db: AsyncSession,
    team_slug: str,
    name: str,
) -> None:
    app = await _get_application(db, team_slug, name)

    # Gather cluster info BEFORE deleting DB record
    argo_targets: list[tuple[str, str, str]] = []
    for deployment in app.deployments:
        try:
            cluster = k8s_service.cluster_for_tier(deployment.environment.tier)
        except ValueError:
            logger.warning(
                "No cluster mapping for tier '%s'; skipping Argo CD cleanup",
                deployment.environment.tier,
            )
            continue
        argo_targets.append((cluster, "argocd", deployment.argocd_app_name))

    await db.delete(app)
    await db.flush()

    for cluster, namespace, app_name in argo_targets:
        try:
            k8s_service.delete_argo_application(cluster, namespace, app_name)
        except Exception as e:
            logger.error(
                "Failed to delete Argo CD Application '%s' in %s/%s: %s",
                app_name,
                cluster,
                namespace,
                e,
            )


async def get_inventory(
    db: AsyncSession,
    team_slug: str | None = None,
) -> list[dict]:
    query = select(Application).options(
        selectinload(Application.team),
        selectinload(Application.deployments).selectinload(
            ApplicationDeployment.environment
        ),
    )
    if team_slug is not None:
        query = query.join(Team, Team.id == Application.team_id).where(
            Team.slug == team_slug
        )

    result = await db.execute(query)
    apps = list(result.scalars().all())

    rows: list[dict] = []
    for app in apps:
        deployments_by_tier: dict[str, dict | None] = {
            "dev": None,
            "staging": None,
            "production": None,
        }
        for deployment in app.deployments:
            tier = deployment.environment.tier
            deployments_by_tier[tier] = {
                "imageTag": deployment.image_tag,
                "deployedAt": deployment.deployed_at,
                "deployedBy": deployment.deployed_by,
                "healthStatus": deployment.health_status,
                "syncStatus": deployment.sync_status,
            }
        rows.append(
            {
                "id": str(app.id),
                "name": app.name,
                "displayName": app.display_name,
                "ownerEmail": app.owner_email,
                "teamSlug": app.team.slug,
                "deployments": deployments_by_tier,
            }
        )
    return rows


def _build_argocd_app_body(
    app: Application,
    environment: Environment,
    cluster: str,
    image_tag: str | None,
    chart_version: str | None,
    value_overrides: dict | None,
) -> dict:
    team_slug = app.team.slug
    app_name = f"{team_slug}-{app.name}-{environment.tier}"
    project_name = f"{team_slug}-{environment.tier}"

    parameters: list[dict] = []
    if image_tag:
        parameters.append({"name": "image.tag", "value": image_tag})
    if value_overrides:
        for key, value in value_overrides.items():
            parameters.append({"name": key, "value": str(value)})

    source: dict = {
        "repoURL": app.repo_url or "",
        "path": app.chart_path or "",
        "targetRevision": chart_version or "HEAD",
    }
    if parameters:
        source["helm"] = {"parameters": parameters}

    body = {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {
            "name": app_name,
            "namespace": "argocd",
            "labels": {
                "devexforge.brianbeck.net/managed-by": "devexforge",
                "devexforge.brianbeck.net/team": team_slug,
                "devexforge.brianbeck.net/application": app.name,
                "devexforge.brianbeck.net/tier": environment.tier,
            },
        },
        "spec": {
            "project": project_name,
            "source": source,
            "destination": {
                "server": "https://kubernetes.default.svc",
                "namespace": environment.namespace_name,
            },
            "syncPolicy": {
                "automated": {
                    "prune": True,
                    "selfHeal": True,
                },
            },
        },
    }
    return body


async def deploy_application(
    db: AsyncSession,
    team_slug: str,
    name: str,
    data: ApplicationDeployRequest,
    user: CurrentUser,
) -> ApplicationDeployment:
    app = await _get_application(db, team_slug, name)

    # Look up environment
    env_result = await db.execute(
        select(Environment).where(
            Environment.team_id == app.team_id,
            Environment.tier == data.tier,
        )
    )
    environment = env_result.scalar_one_or_none()
    if environment is None:
        raise ValueError(
            f"Environment '{data.tier}' does not exist for team '{team_slug}'"
        )

    cluster = k8s_service.cluster_for_tier(data.tier)

    strategy = data.strategy or app.default_strategy
    if strategy in ("bluegreen", "canary") and data.tier != "production":
        raise ValueError(
            "Blue-green and canary are only supported in production"
        )

    body = _build_argocd_app_body(
        app=app,
        environment=environment,
        cluster=cluster,
        image_tag=data.image_tag,
        chart_version=data.chart_version,
        value_overrides=data.value_overrides,
    )
    argocd_app_name = body["metadata"]["name"]

    k8s_service.create_argo_application(cluster, "argocd", body)

    # Upsert deployment
    existing_result = await db.execute(
        select(ApplicationDeployment).where(
            ApplicationDeployment.application_id == app.id,
            ApplicationDeployment.environment_id == environment.id,
        )
    )
    deployment = existing_result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    previous_image_tag: str | None = None
    if deployment is None:
        deployment = ApplicationDeployment(
            application_id=app.id,
            environment_id=environment.id,
            argocd_app_name=argocd_app_name,
            image_tag=data.image_tag,
            chart_version=data.chart_version,
            git_sha=data.git_sha,
            strategy=strategy,
            deployed_at=now,
            deployed_by=user.email,
        )
        db.add(deployment)
    else:
        previous_image_tag = deployment.image_tag
        deployment.argocd_app_name = argocd_app_name
        deployment.image_tag = data.image_tag
        deployment.chart_version = data.chart_version
        deployment.git_sha = data.git_sha
        deployment.strategy = strategy
        deployment.deployed_at = now
        deployment.deployed_by = user.email

    await db.flush()

    event = ApplicationDeploymentEvent(
        deployment_id=deployment.id,
        event_type="sync_started",
        from_version=previous_image_tag,
        to_version=data.image_tag,
        actor=user.email,
        occurred_at=now,
    )
    db.add(event)
    await db.flush()

    return deployment


async def refresh_deployment_status(
    db: AsyncSession,
    deployment_id: str,
) -> ApplicationDeployment:
    result = await db.execute(
        select(ApplicationDeployment)
        .where(ApplicationDeployment.id == deployment_id)
        .options(selectinload(ApplicationDeployment.environment))
    )
    deployment = result.scalar_one_or_none()
    if deployment is None:
        raise ValueError(f"Deployment '{deployment_id}' not found")

    cluster = k8s_service.cluster_for_tier(deployment.environment.tier)
    health = k8s_service.get_argo_application_health(
        cluster, "argocd", deployment.argocd_app_name
    )
    if health is None:
        return deployment

    previous_health = deployment.health_status
    new_health = health.get("health_status")
    new_sync = health.get("sync_status")

    deployment.health_status = new_health
    deployment.sync_status = new_sync
    deployment.raw_status = health.get("raw")
    deployment.last_synced_at = datetime.now(timezone.utc)

    if previous_health != new_health:
        event = ApplicationDeploymentEvent(
            deployment_id=deployment.id,
            event_type="status_changed",
            from_version=None,
            to_version=None,
            actor="system",
            details={
                "previous_health": previous_health,
                "new_health": new_health,
                "sync_status": new_sync,
            },
            occurred_at=datetime.now(timezone.utc),
        )
        db.add(event)

    await db.flush()
    return deployment


async def get_deployment_history(
    db: AsyncSession,
    team_slug: str,
    name: str,
    limit: int = 100,
) -> list[ApplicationDeploymentEvent]:
    app = await _get_application(db, team_slug, name)
    result = await db.execute(
        select(ApplicationDeploymentEvent)
        .join(
            ApplicationDeployment,
            ApplicationDeployment.id == ApplicationDeploymentEvent.deployment_id,
        )
        .where(ApplicationDeployment.application_id == app.id)
        .order_by(ApplicationDeploymentEvent.occurred_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
