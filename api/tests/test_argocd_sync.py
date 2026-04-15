"""Tests for the Argo CD sync loop in isolation."""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models.application import (
    Application,
    ApplicationDeployment,
    ApplicationDeploymentEvent,
)
from app.models.environment import Environment
from app.models.team import Team
from app.services.argocd_sync import _sync_deployments

pytestmark = pytest.mark.asyncio


async def _seed(db_session, tier: str = "dev", image_tag: str = "v1.0.0"):
    """Seed a team, environment, application, and deployment."""
    team = Team(
        slug=f"sync-team-{uuid.uuid4().hex[:6]}",
        display_name="Sync Team",
        owner_email="owner@company.com",
    )
    db_session.add(team)
    await db_session.flush()

    env = Environment(
        team_id=team.id,
        tier=tier,
        namespace_name=f"{team.slug}-{tier}",
        phase="Active",
        policies={},
        resource_quota={},
    )
    db_session.add(env)
    await db_session.flush()

    app = Application(
        team_id=team.id,
        name="checkout-api",
        display_name="Checkout API",
        owner_email="owner@company.com",
        default_strategy="rolling",
    )
    db_session.add(app)
    await db_session.flush()

    argocd_name = f"{team.slug}-checkout-api-{tier}"
    deployment = ApplicationDeployment(
        application_id=app.id,
        environment_id=env.id,
        argocd_app_name=argocd_name,
        image_tag=image_tag,
        strategy="rolling",
        deployed_at=datetime.now(timezone.utc),
        deployed_by="owner@company.com",
        health_status="Progressing",
        sync_status="OutOfSync",
    )
    db_session.add(deployment)
    await db_session.commit()
    return team, env, app, deployment, argocd_name


def _argo_app(name: str, health: str = "Healthy", sync: str = "Synced",
              images=None) -> dict:
    return {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {"name": name},
        "status": {
            "health": {"status": health},
            "sync": {"status": sync},
            "summary": {"images": images or []},
            "operationState": {},
        },
    }


# ---------------------------------------------------------------------------


async def test_sync_with_no_deployments(db_session, mock_k8s):
    await _sync_deployments(db_session)
    # Should not call out to k8s_service when nothing to sync
    assert mock_k8s.list_argo_applications.call_count == 0


async def test_sync_updates_health_status(db_session, mock_k8s):
    _, _, _, deployment, argo_name = await _seed(db_session)
    mock_k8s.list_argo_applications.return_value = [_argo_app(argo_name)]

    await _sync_deployments(db_session)
    await db_session.commit()

    await db_session.refresh(deployment)
    assert deployment.health_status == "Healthy"
    assert deployment.sync_status == "Synced"
    assert deployment.last_synced_at is not None


async def test_sync_emits_status_changed_event(db_session, mock_k8s):
    _, _, _, deployment, argo_name = await _seed(db_session)
    mock_k8s.list_argo_applications.return_value = [_argo_app(argo_name)]

    await _sync_deployments(db_session)
    await db_session.commit()

    result = await db_session.execute(
        select(ApplicationDeploymentEvent).where(
            ApplicationDeploymentEvent.deployment_id == deployment.id,
            ApplicationDeploymentEvent.event_type == "status_changed",
        )
    )
    events = list(result.scalars().all())
    assert len(events) == 1
    assert events[0].to_version == "Healthy"


async def test_sync_marks_missing_when_no_argocd_match(db_session, mock_k8s):
    _, _, _, deployment, _ = await _seed(db_session)
    mock_k8s.list_argo_applications.return_value = []  # no matching app

    await _sync_deployments(db_session)
    await db_session.commit()

    await db_session.refresh(deployment)
    assert deployment.health_status == "Missing"
    assert deployment.sync_status == "Unknown"


async def test_sync_handles_per_deployment_errors(db_session, mock_k8s):
    _, _, _, d1, n1 = await _seed(db_session)
    # Second seeding: different team to avoid unique-namespace collisions
    _, _, _, d2, n2 = await _seed(db_session, tier="staging")

    # First argo entry is garbage (missing status -> raises on access), second OK
    class Bad:
        def get(self, *args, **kwargs):
            raise RuntimeError("boom")

    bad = {"metadata": {"name": n1}, "status": Bad()}
    good = _argo_app(n2, health="Healthy")
    mock_k8s.list_argo_applications.return_value = [bad, good]

    await _sync_deployments(db_session)
    await db_session.commit()

    await db_session.refresh(d2)
    assert d2.health_status == "Healthy"
    # d1 failed to update -> still the seeded value
    await db_session.refresh(d1)
    assert d1.health_status == "Progressing"


async def test_sync_extracts_image_tag_from_summary(db_session, mock_k8s):
    _, _, _, deployment, argo_name = await _seed(db_session, image_tag="v1.0.0")
    mock_k8s.list_argo_applications.return_value = [
        _argo_app(argo_name, images=["registry/acme/checkout:v1.2.3"])
    ]

    await _sync_deployments(db_session)
    await db_session.commit()

    await db_session.refresh(deployment)
    assert deployment.image_tag == "v1.2.3"
