"""Tests for application management CRUD + inventory endpoints."""
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.application import Application, ApplicationDeployment
from app.models.environment import Environment
from app.models.team import Team

pytestmark = pytest.mark.asyncio

TEAMS_URL = "/api/v1/teams"


async def _create_team(client: AsyncClient, name: str = "App Team") -> str:
    resp = await client.post(TEAMS_URL, json={"displayName": name})
    assert resp.status_code == 201
    return resp.json()["slug"]


async def _create_env(client: AsyncClient, slug: str, tier: str) -> dict:
    resp = await client.post(
        f"{TEAMS_URL}/{slug}/environments", json={"tier": tier}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _app_payload(name: str = "checkout-api", **overrides) -> dict:
    body = {
        "name": name,
        "displayName": name.replace("-", " ").title(),
        "description": "Handles checkout",
        "repoUrl": "https://github.com/acme/checkout",
        "chartPath": "deploy/chart",
        "ownerEmail": "owner@company.com",
        "defaultStrategy": "rolling",
    }
    body.update(overrides)
    return body


def _apps_url(slug: str) -> str:
    return f"{TEAMS_URL}/{slug}/applications"


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------


async def test_register_application_success(client: AsyncClient, mock_k8s):
    slug = await _create_team(client)
    resp = await client.post(_apps_url(slug), json=_app_payload())
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "checkout-api"
    assert data["displayName"] == "Checkout Api"
    assert data["deployments"] == []


async def test_register_application_duplicate_name_fails(
    client: AsyncClient, mock_k8s
):
    slug = await _create_team(client)
    resp1 = await client.post(_apps_url(slug), json=_app_payload())
    assert resp1.status_code == 201
    resp2 = await client.post(_apps_url(slug), json=_app_payload())
    assert resp2.status_code == 409


async def test_register_requires_team_membership(
    db_session, developer_client: AsyncClient, mock_k8s
):
    # Create the team directly in the DB with an unrelated owner, so the
    # developer user is neither the owner nor a member.
    team = Team(
        slug="private-team",
        display_name="Private Team",
        owner_email="someone-else@company.com",
    )
    db_session.add(team)
    await db_session.commit()

    resp = await developer_client.post(
        _apps_url("private-team"), json=_app_payload()
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# List / get
# ---------------------------------------------------------------------------


async def test_list_team_applications_empty(client: AsyncClient, mock_k8s):
    slug = await _create_team(client)
    resp = await client.get(_apps_url(slug))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_team_applications_with_data(client: AsyncClient, mock_k8s):
    slug = await _create_team(client)
    await client.post(_apps_url(slug), json=_app_payload("svc-a"))
    await client.post(_apps_url(slug), json=_app_payload("svc-b"))
    resp = await client.get(_apps_url(slug))
    assert resp.status_code == 200
    names = {a["name"] for a in resp.json()}
    assert names == {"svc-a", "svc-b"}


async def test_get_application_success(client: AsyncClient, mock_k8s):
    slug = await _create_team(client)
    await client.post(
        _apps_url(slug),
        json=_app_payload("checkout-api", description="Checkout service"),
    )
    resp = await client.get(f"{_apps_url(slug)}/checkout-api")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "checkout-api"
    assert data["description"] == "Checkout service"
    assert data["ownerEmail"] == "owner@company.com"
    assert data["repoUrl"] == "https://github.com/acme/checkout"


async def test_get_application_not_found(client: AsyncClient, mock_k8s):
    slug = await _create_team(client)
    resp = await client.get(f"{_apps_url(slug)}/does-not-exist")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Update / delete
# ---------------------------------------------------------------------------


async def test_update_application_description(client: AsyncClient, mock_k8s):
    slug = await _create_team(client)
    await client.post(_apps_url(slug), json=_app_payload())
    resp = await client.patch(
        f"{_apps_url(slug)}/checkout-api",
        json={"description": "Updated blurb"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["description"] == "Updated blurb"


async def test_delete_application_cascade(client: AsyncClient, mock_k8s):
    slug = await _create_team(client)
    await client.post(_apps_url(slug), json=_app_payload())
    resp = await client.delete(f"{_apps_url(slug)}/checkout-api")
    assert resp.status_code == 204
    # No deployments, so no Argo CD delete calls
    assert mock_k8s.delete_argo_application.call_count == 0
    # And the app is gone
    get_resp = await client.get(f"{_apps_url(slug)}/checkout-api")
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------


async def test_team_inventory_empty(client: AsyncClient, mock_k8s):
    slug = await _create_team(client)
    await client.post(_apps_url(slug), json=_app_payload())
    resp = await client.get(f"{_apps_url(slug)}/inventory")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    row = data["rows"][0]
    assert row["name"] == "checkout-api"
    assert row["deployments"]["dev"] is None
    assert row["deployments"]["staging"] is None
    assert row["deployments"]["production"] is None


async def test_team_inventory_with_deployments(
    client: AsyncClient, db_session, mock_k8s
):
    slug = await _create_team(client)
    await _create_env(client, slug, "dev")
    await client.post(_apps_url(slug), json=_app_payload())

    # Insert deployment directly in DB
    team = (
        await db_session.execute(select(Team).where(Team.slug == slug))
    ).scalar_one()
    app_row = (
        await db_session.execute(
            select(Application).where(Application.team_id == team.id)
        )
    ).scalar_one()
    env_row = (
        await db_session.execute(
            select(Environment).where(
                Environment.team_id == team.id, Environment.tier == "dev"
            )
        )
    ).scalar_one()

    deployment = ApplicationDeployment(
        application_id=app_row.id,
        environment_id=env_row.id,
        argocd_app_name=f"{slug}-checkout-api-dev",
        image_tag="v1.0.0",
        strategy="rolling",
        deployed_at=datetime.now(timezone.utc),
        deployed_by="owner@company.com",
        health_status="Healthy",
        sync_status="Synced",
    )
    db_session.add(deployment)
    await db_session.commit()

    resp = await client.get(f"{_apps_url(slug)}/inventory")
    assert resp.status_code == 200
    row = resp.json()["rows"][0]
    assert row["deployments"]["dev"] is not None
    assert row["deployments"]["dev"]["imageTag"] == "v1.0.0"
    assert row["deployments"]["dev"]["healthStatus"] == "Healthy"
    assert row["deployments"]["staging"] is None


# ---------------------------------------------------------------------------
# Global inventory (admin only)
# ---------------------------------------------------------------------------


async def test_global_inventory_admin_ok(client: AsyncClient, mock_k8s):
    slug = await _create_team(client)
    await client.post(_apps_url(slug), json=_app_payload())
    resp = await client.get("/api/v1/applications/inventory")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1


async def test_global_inventory_developer_forbidden(
    developer_client: AsyncClient, mock_k8s
):
    resp = await developer_client.get("/api/v1/applications/inventory")
    assert resp.status_code == 403
