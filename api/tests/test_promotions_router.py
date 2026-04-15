"""HTTP-level tests for the promotion-requests routers."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.application import Application, ApplicationDeployment
from app.models.environment import Environment
from app.models.promotion import PromotionGate, PromotionRequest
from app.models.team import Team, TeamMember

pytestmark = pytest.mark.asyncio

TEAMS_URL = "/api/v1/teams"


async def _seed_team_and_app(
    db_session,
    *,
    owner_email: str = "admin@company.com",
    with_manual_gate: bool = False,
    member_emails: list[str] | None = None,
) -> tuple[Team, Application, ApplicationDeployment, Environment]:
    team = Team(
        slug=f"prt-{uuid.uuid4().hex[:6]}",
        display_name="PRT",
        owner_email=owner_email,
    )
    db_session.add(team)
    await db_session.flush()

    for email in member_emails or []:
        db_session.add(
            TeamMember(team_id=team.id, email=email, role="developer")
        )

    staging_env = Environment(
        team_id=team.id,
        tier="staging",
        namespace_name=f"{team.slug}-staging",
        phase="Active",
    )
    prod_env = Environment(
        team_id=team.id,
        tier="production",
        namespace_name=f"{team.slug}-production",
        phase="Active",
    )
    db_session.add_all([staging_env, prod_env])
    await db_session.flush()

    app = Application(
        team_id=team.id,
        name="svc",
        display_name="svc",
        owner_email=owner_email,
        repo_url="https://github.com/acme/svc",
        chart_path="deploy/chart",
        default_strategy="rolling",
    )
    db_session.add(app)
    await db_session.flush()

    src = ApplicationDeployment(
        application_id=app.id,
        environment_id=staging_env.id,
        argocd_app_name=f"{team.slug}-svc-staging",
        image_tag="v1.0.0",
        strategy="rolling",
        deployed_at=datetime.now(timezone.utc) - timedelta(hours=72),
        deployed_by=owner_email,
        health_status="Healthy",
        sync_status="Synced",
    )
    db_session.add(src)

    if with_manual_gate:
        db_session.add(
            PromotionGate(
                scope="platform",
                team_id=None,
                application_id=None,
                tier="production",
                gate_type="manual_approval",
                config={"required_role": "admin", "count": 1},
                # advisory so _evaluate_and_advance doesn't treat it as a
                # hard failure before needs_manual_approval() is checked.
                enforcement="advisory",
                created_by="system",
            )
        )

    await db_session.commit()
    return team, app, src, prod_env


def _team_pr_url(slug: str, app_name: str) -> str:
    return f"{TEAMS_URL}/{slug}/applications/{app_name}/promotion-requests"


# ---------------------------------------------------------------------------


async def test_create_promotion_request_returns_201(
    client: AsyncClient, db_session, mock_k8s
):
    team, app, *_ = await _seed_team_and_app(db_session)
    resp = await client.post(
        _team_pr_url(team.slug, app.name),
        json={"targetTier": "production", "imageTag": "v2.0.0"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "executing"
    assert body["imageTag"] == "v2.0.0"
    assert body["targetTier"] == "production"


async def test_list_team_promotion_requests_only_that_app(
    client: AsyncClient, db_session, mock_k8s
):
    team, app, *_ = await _seed_team_and_app(db_session)
    await client.post(
        _team_pr_url(team.slug, app.name),
        json={"targetTier": "production", "imageTag": "v2.0.0"},
    )
    resp = await client.get(_team_pr_url(team.slug, app.name))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["targetTier"] == "production"


async def test_global_list_requires_admin(
    developer_client: AsyncClient, db_session, mock_k8s
):
    resp = await developer_client.get("/api/v1/promotion-requests")
    assert resp.status_code == 403


async def test_global_list_admin_ok(
    client: AsyncClient, db_session, mock_k8s
):
    team, app, *_ = await _seed_team_and_app(db_session)
    await client.post(
        _team_pr_url(team.slug, app.name),
        json={"targetTier": "production", "imageTag": "v2.0.0"},
    )
    resp = await client.get("/api/v1/promotion-requests")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


async def test_approve_promotion_request_ok(
    client: AsyncClient, db_session, mock_k8s
):
    team, app, src, prod_env = await _seed_team_and_app(db_session)
    # Hand-craft a pending_approval request.
    request = PromotionRequest(
        application_id=app.id,
        from_deployment_id=src.id,
        to_environment_id=prod_env.id,
        source_tier="staging",
        target_tier="production",
        requested_by="admin@company.com",
        status="pending_approval",
        image_tag="v2.0.0",
        strategy="rolling",
    )
    db_session.add(request)
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/promotion-requests/{request.id}/approve",
        json={},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "executing"
    assert resp.json()["approverEmail"] == "admin@company.com"


async def test_reject_promotion_request_requires_reason(
    client: AsyncClient, db_session, mock_k8s
):
    team, app, src, prod_env = await _seed_team_and_app(db_session)
    request = PromotionRequest(
        application_id=app.id,
        from_deployment_id=src.id,
        to_environment_id=prod_env.id,
        source_tier="staging",
        target_tier="production",
        requested_by="admin@company.com",
        status="pending_approval",
        image_tag="v2.0.0",
        strategy="rolling",
    )
    db_session.add(request)
    await db_session.commit()

    # No body at all: pydantic 422.
    resp = await client.post(
        f"/api/v1/promotion-requests/{request.id}/reject", json={}
    )
    assert resp.status_code == 422


async def test_force_promotion_request_requires_admin(
    developer_client: AsyncClient, db_session, mock_k8s
):
    # Build state as a background seed.
    team, app, src, prod_env = await _seed_team_and_app(
        db_session,
        owner_email="someone-else@company.com",
        member_emails=["developer1@company.com"],
    )
    request = PromotionRequest(
        application_id=app.id,
        from_deployment_id=src.id,
        to_environment_id=prod_env.id,
        source_tier="staging",
        target_tier="production",
        requested_by="developer1@company.com",
        status="rejected",
        image_tag="v2.0.0",
        strategy="rolling",
    )
    db_session.add(request)
    await db_session.commit()

    resp = await developer_client.post(
        f"/api/v1/promotion-requests/{request.id}/force",
        json={"reason": "emergency"},
    )
    assert resp.status_code == 403


async def test_get_promotion_request_detail_returns_gate_results(
    client: AsyncClient, db_session, mock_k8s
):
    team, app, *_ = await _seed_team_and_app(db_session)
    # Create via API so gate_results rows are populated.
    resp = await client.post(
        _team_pr_url(team.slug, app.name),
        json={"targetTier": "production", "imageTag": "v2.0.0"},
    )
    assert resp.status_code == 201
    request_id = resp.json()["id"]

    detail = await client.get(f"/api/v1/promotion-requests/{request_id}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert "gateResults" in body
    assert body["fromDeployment"] is not None
    assert body["fromDeployment"]["tier"] == "staging"
