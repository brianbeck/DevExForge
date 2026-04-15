"""HTTP-level tests for admin + team gate routers."""
import uuid

import pytest
from httpx import AsyncClient

from app.models.application import Application
from app.models.promotion import PromotionGate
from app.models.team import Team, TeamMember

pytestmark = pytest.mark.asyncio

ADMIN_URL = "/api/v1/admin/promotion-gates"
TEAMS_URL = "/api/v1/teams"


async def _seed_team_and_app(
    db_session, *, owner_email: str = "admin@company.com"
) -> tuple[Team, Application]:
    team = Team(
        slug=f"gr-{uuid.uuid4().hex[:6]}",
        display_name="GR",
        owner_email=owner_email,
    )
    db_session.add(team)
    await db_session.flush()
    # Add owner also as admin member so team endpoints pass admin checks.
    db_session.add(
        TeamMember(team_id=team.id, email=owner_email, role="admin")
    )
    app = Application(
        team_id=team.id,
        name="svc",
        display_name="svc",
        owner_email=owner_email,
        default_strategy="rolling",
    )
    db_session.add(app)
    await db_session.commit()
    return team, app


async def test_admin_list_gates_includes_seeded_platform(
    client: AsyncClient, db_session, seeded_platform_gates
):
    resp = await client.get(ADMIN_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 8
    platform_types = {
        g["gateType"] for g in body["items"] if g["scope"] == "platform"
    }
    assert {
        "deployed_in_prior_env",
        "health_passing",
        "min_time_in_prior_env",
        "manual_approval",
    }.issubset(platform_types)


async def test_admin_create_platform_gate(client: AsyncClient):
    resp = await client.post(
        ADMIN_URL,
        json={
            "scope": "platform",
            "tier": "production",
            "gateType": "max_high_cves",
            "config": {"max": 10},
            "enforcement": "advisory",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["scope"] == "platform"
    assert body["gateType"] == "max_high_cves"
    assert body["enforcement"] == "advisory"


async def test_team_create_gate_forces_team_scope(
    client: AsyncClient, db_session
):
    team, app = await _seed_team_and_app(db_session)
    resp = await client.post(
        f"{TEAMS_URL}/{team.slug}/applications/{app.name}/gates",
        json={
            "scope": "team",
            "tier": "production",
            "gateType": "max_high_cves",
            "config": {"max": 3},
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["scope"] == "team"
    assert body["teamId"] == str(team.id)


async def test_team_cannot_delete_platform_gate(
    client: AsyncClient, db_session, seeded_platform_gates
):
    team, app = await _seed_team_and_app(db_session)
    # Pick any platform gate id
    platform_gate = seeded_platform_gates[0]
    resp = await client.delete(
        f"{TEAMS_URL}/{team.slug}/applications/{app.name}/gates/{platform_gate.id}"
    )
    assert resp.status_code == 403


async def test_team_list_returns_platform_and_team(
    client: AsyncClient, db_session, seeded_platform_gates
):
    team, app = await _seed_team_and_app(db_session)
    # Add a team-scoped gate
    db_session.add(
        PromotionGate(
            scope="team",
            team_id=team.id,
            application_id=None,
            tier="production",
            gate_type="max_high_cves",
            config={"max": 5},
            enforcement="advisory",
            created_by=team.owner_email,
        )
    )
    await db_session.commit()

    resp = await client.get(
        f"{TEAMS_URL}/{team.slug}/applications/{app.name}/gates"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    scopes = {g["scope"] for g in body["items"]}
    assert "platform" in scopes
    assert "team" in scopes
