"""Tests for the application deploy flow."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.application import (
    ApplicationDeployment,
    ApplicationDeploymentEvent,
)

pytestmark = pytest.mark.asyncio

TEAMS_URL = "/api/v1/teams"


async def _setup(client: AsyncClient, tiers=("dev", "staging", "production")):
    resp = await client.post(TEAMS_URL, json={"displayName": "Deploy Team"})
    assert resp.status_code == 201
    slug = resp.json()["slug"]
    for tier in tiers:
        r = await client.post(
            f"{TEAMS_URL}/{slug}/environments", json={"tier": tier}
        )
        assert r.status_code == 201, r.text
    # Create an application
    r = await client.post(
        f"{TEAMS_URL}/{slug}/applications",
        json={
            "name": "checkout-api",
            "displayName": "Checkout API",
            "repoUrl": "https://github.com/acme/checkout",
            "chartPath": "deploy/chart",
            "ownerEmail": "owner@company.com",
            "defaultStrategy": "rolling",
        },
    )
    assert r.status_code == 201, r.text
    return slug


def _deploy_url(slug: str, name: str = "checkout-api") -> str:
    return f"{TEAMS_URL}/{slug}/applications/{name}/deploy"


# ---------------------------------------------------------------------------


async def test_deploy_creates_argocd_application(
    client: AsyncClient, db_session, mock_k8s
):
    slug = await _setup(client)
    resp = await client.post(
        _deploy_url(slug), json={"tier": "dev", "imageTag": "v1.0.0"}
    )
    assert resp.status_code == 201, resp.text
    assert mock_k8s.create_argo_application.call_count == 1

    # Deployment row was created
    result = await db_session.execute(select(ApplicationDeployment))
    deployments = list(result.scalars().all())
    assert len(deployments) == 1
    assert deployments[0].image_tag == "v1.0.0"


async def test_deploy_updates_existing_deployment(
    client: AsyncClient, db_session, mock_k8s
):
    slug = await _setup(client)
    await client.post(
        _deploy_url(slug), json={"tier": "dev", "imageTag": "v1.0.0"}
    )
    resp = await client.post(
        _deploy_url(slug), json={"tier": "dev", "imageTag": "v2.0.0"}
    )
    assert resp.status_code == 201
    result = await db_session.execute(select(ApplicationDeployment))
    deployments = list(result.scalars().all())
    assert len(deployments) == 1  # updated, not duplicated
    assert deployments[0].image_tag == "v2.0.0"


async def test_deploy_appends_event(
    client: AsyncClient, db_session, mock_k8s
):
    slug = await _setup(client)
    await client.post(
        _deploy_url(slug), json={"tier": "dev", "imageTag": "v1.0.0"}
    )
    result = await db_session.execute(select(ApplicationDeploymentEvent))
    events = list(result.scalars().all())
    assert len(events) == 1
    assert events[0].event_type == "sync_started"
    assert events[0].to_version == "v1.0.0"
    assert events[0].from_version is None


async def test_deploy_records_previous_version(
    client: AsyncClient, db_session, mock_k8s
):
    slug = await _setup(client)
    await client.post(
        _deploy_url(slug), json={"tier": "dev", "imageTag": "v1.0.0"}
    )
    await client.post(
        _deploy_url(slug), json={"tier": "dev", "imageTag": "v2.0.0"}
    )
    result = await db_session.execute(
        select(ApplicationDeploymentEvent).order_by(
            ApplicationDeploymentEvent.occurred_at
        )
    )
    events = list(result.scalars().all())
    assert len(events) == 2
    assert events[1].from_version == "v1.0.0"
    assert events[1].to_version == "v2.0.0"


async def test_deploy_bluegreen_rejected_in_non_production(
    client: AsyncClient, mock_k8s
):
    slug = await _setup(client)
    resp = await client.post(
        _deploy_url(slug),
        json={"tier": "dev", "imageTag": "v1.0.0", "strategy": "bluegreen"},
    )
    assert resp.status_code in (400, 409)


async def test_deploy_bluegreen_allowed_in_production(
    client: AsyncClient, mock_k8s
):
    slug = await _setup(client)
    resp = await client.post(
        _deploy_url(slug),
        json={
            "tier": "production",
            "imageTag": "v1.0.0",
            "strategy": "bluegreen",
        },
    )
    assert resp.status_code == 201, resp.text


async def test_deploy_to_missing_environment_returns_404(
    client: AsyncClient, mock_k8s
):
    slug = await _setup(client, tiers=("dev",))  # only dev exists
    resp = await client.post(
        _deploy_url(slug),
        json={"tier": "staging", "imageTag": "v1.0.0"},
    )
    assert resp.status_code == 404


async def test_deploy_refresh_updates_status(
    client: AsyncClient, db_session, mock_k8s
):
    slug = await _setup(client)
    await client.post(
        _deploy_url(slug), json={"tier": "dev", "imageTag": "v1.0.0"}
    )
    mock_k8s.get_argo_application_health.return_value = {
        "health_status": "Healthy",
        "sync_status": "Synced",
        "raw": {"status": {}},
    }
    resp = await client.post(
        f"{TEAMS_URL}/{slug}/applications/checkout-api/refresh"
    )
    assert resp.status_code == 200, resp.text
    assert mock_k8s.get_argo_application_health.called
    data = resp.json()
    assert data[0]["healthStatus"] == "Healthy"
    assert data[0]["syncStatus"] == "Synced"
