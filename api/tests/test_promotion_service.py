"""Tests for the promotion_service state machine."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.application import Application, ApplicationDeployment
from app.models.environment import Environment
from app.models.promotion import PromotionGate, PromotionRequest
from app.models.team import Team
from app.schemas.promotion import PromotionRequestCreate
from app.services import promotion_service

pytestmark = pytest.mark.asyncio


async def _seed_world(
    db_session,
    *,
    source_health: str = "Healthy",
    source_deployed_at: datetime | None = None,
    with_manual_gate: bool = False,
    with_impossible_gate: bool = False,
) -> tuple[Team, Application, ApplicationDeployment, Environment]:
    team = Team(
        slug=f"prom-team-{uuid.uuid4().hex[:6]}",
        display_name="Prom Team",
        owner_email="owner@company.com",
    )
    db_session.add(team)
    await db_session.flush()

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
        owner_email="owner@company.com",
        repo_url="https://github.com/acme/svc",
        chart_path="deploy/chart",
        default_strategy="rolling",
    )
    db_session.add(app)
    await db_session.flush()

    deployed_at = source_deployed_at or (
        datetime.now(timezone.utc) - timedelta(hours=72)
    )
    source_deployment = ApplicationDeployment(
        application_id=app.id,
        environment_id=staging_env.id,
        argocd_app_name=f"{team.slug}-svc-staging",
        image_tag="v1.0.0",
        strategy="rolling",
        deployed_at=deployed_at,
        deployed_by="owner@company.com",
        health_status=source_health,
        sync_status="Synced",
    )
    db_session.add(source_deployment)
    await db_session.flush()

    # Only add gates relevant for the test. We deliberately avoid seeding
    # the full platform gate set because many require k8s/vuln calls.
    if with_manual_gate:
        db_session.add(
            PromotionGate(
                scope="platform",
                team_id=None,
                application_id=None,
                tier="production",
                gate_type="manual_approval",
                config={"required_role": "admin", "count": 1},
                enforcement="advisory",
                created_by="system",
            )
        )
    if with_impossible_gate:
        db_session.add(
            PromotionGate(
                scope="platform",
                team_id=None,
                application_id=None,
                tier="production",
                gate_type="min_time_in_prior_env",
                config={"hours": 999},
                enforcement="blocking",
                created_by="system",
            )
        )
    await db_session.flush()

    return team, app, source_deployment, prod_env


def _make_payload(**overrides) -> PromotionRequestCreate:
    body = {"target_tier": "production", "image_tag": "v1.0.0"}
    body.update(overrides)
    return PromotionRequestCreate(**body)


# ---------------------------------------------------------------------------
# create_request
# ---------------------------------------------------------------------------


async def test_create_request_executes_when_no_gates(db_session, mock_k8s):
    team, app, _src, _prod = await _seed_world(db_session)
    req = await promotion_service.create_request(
        db_session, team.slug, app.name, _make_payload(), team.owner_email
    )
    assert req.status == "executing"
    assert mock_k8s.create_argo_application.call_count == 1


async def test_create_request_manual_approval_pends(db_session, mock_k8s):
    team, app, _src, _prod = await _seed_world(
        db_session, with_manual_gate=True
    )
    req = await promotion_service.create_request(
        db_session, team.slug, app.name, _make_payload(), team.owner_email
    )
    assert req.status == "pending_approval"
    assert mock_k8s.create_argo_application.call_count == 0


async def test_create_request_blocking_gate_rejects(db_session, mock_k8s):
    team, app, _src, _prod = await _seed_world(
        db_session, with_impossible_gate=True
    )
    req = await promotion_service.create_request(
        db_session, team.slug, app.name, _make_payload(), team.owner_email
    )
    assert req.status == "rejected"
    assert "min_time_in_prior_env" in (req.rejected_reason or "")


# ---------------------------------------------------------------------------
# approve / reject / force / cancel
# ---------------------------------------------------------------------------


async def test_approve_without_required_role_raises(db_session, mock_k8s):
    team, app, _src, _prod = await _seed_world(
        db_session, with_manual_gate=True
    )
    req = await promotion_service.create_request(
        db_session, team.slug, app.name, _make_payload(), team.owner_email
    )
    assert req.status == "pending_approval"
    with pytest.raises(ValueError, match="lacks required role"):
        await promotion_service.approve_request(
            db_session, req.id, "dev@company.com", ["developer"]
        )


async def test_approve_with_admin_role_executes(db_session, mock_k8s):
    team, app, _src, _prod = await _seed_world(
        db_session, with_manual_gate=True
    )
    req = await promotion_service.create_request(
        db_session, team.slug, app.name, _make_payload(), team.owner_email
    )
    req = await promotion_service.approve_request(
        db_session, req.id, "admin@company.com", ["admin"]
    )
    assert req.status == "executing"
    assert req.approver_email == "admin@company.com"
    assert mock_k8s.create_argo_application.call_count == 1


async def test_reject_request_with_reason(db_session, mock_k8s):
    team, app, _src, _prod = await _seed_world(
        db_session, with_manual_gate=True
    )
    req = await promotion_service.create_request(
        db_session, team.slug, app.name, _make_payload(), team.owner_email
    )
    req = await promotion_service.reject_request(
        db_session, req.id, "admin@company.com", "not this week"
    )
    assert req.status == "rejected"
    assert req.rejected_reason == "not this week"


async def test_force_execute_requires_admin(db_session, mock_k8s):
    team, app, _src, _prod = await _seed_world(
        db_session, with_impossible_gate=True
    )
    req = await promotion_service.create_request(
        db_session, team.slug, app.name, _make_payload(), team.owner_email
    )
    assert req.status == "rejected"
    with pytest.raises(ValueError, match="admin"):
        await promotion_service.force_execute(
            db_session, req.id, "dev@company.com", "hotfix", ["developer"]
        )


async def test_force_execute_captures_reason(db_session, mock_k8s):
    team, app, _src, _prod = await _seed_world(
        db_session, with_impossible_gate=True
    )
    req = await promotion_service.create_request(
        db_session, team.slug, app.name, _make_payload(), team.owner_email
    )
    req = await promotion_service.force_execute(
        db_session, req.id, "admin@company.com", "hotfix rollout", ["admin"]
    )
    assert req.status == "executing"
    assert req.force_reason == "hotfix rollout"
    assert req.forced_by == "admin@company.com"


async def test_cancel_request(db_session, mock_k8s):
    team, app, _src, _prod = await _seed_world(
        db_session, with_manual_gate=True
    )
    req = await promotion_service.create_request(
        db_session, team.slug, app.name, _make_payload(), team.owner_email
    )
    req = await promotion_service.cancel_request(
        db_session, req.id, team.owner_email
    )
    assert req.status == "cancelled"


async def test_rollback_sets_rolled_back(db_session, mock_k8s):
    team, app, _src, _prod = await _seed_world(db_session)
    req = await promotion_service.create_request(
        db_session, team.slug, app.name, _make_payload(), team.owner_email
    )
    assert req.status == "executing"
    req = await promotion_service.rollback_request(
        db_session, req.id, "admin@company.com", "degraded after deploy"
    )
    assert req.status == "rolled_back"
