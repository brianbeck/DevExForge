"""Tests for individual gate functions and list_applicable_gates merging."""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.application import Application
from app.models.environment import Environment
from app.models.promotion import PromotionGate, PromotionRequest
from app.models.team import Team
from app.services import gate_service
from app.services.gate_service import (
    GateContext,
    gate_deployed_in_prior_env,
    gate_github_tag_exists,
    gate_health_passing,
    gate_manual_approval,
    gate_min_time_in_prior_env,
    list_applicable_gates,
)

pytestmark = pytest.mark.asyncio


def _fake_ctx(
    *,
    source_health: str | None = "Healthy",
    source_deployed_at: datetime | None = None,
    target_tier: str = "production",
    image_tag: str | None = "v1.0.0",
    repo_url: str | None = "https://github.com/acme/checkout",
) -> GateContext:
    app = SimpleNamespace(
        id=uuid.uuid4(),
        name="checkout-api",
        repo_url=repo_url,
        team_id=uuid.uuid4(),
    )
    source_deployment = None
    if source_health is not None:
        source_deployment = SimpleNamespace(
            health_status=source_health,
            deployed_at=source_deployed_at or datetime.now(timezone.utc),
            environment=SimpleNamespace(
                namespace_name="acme-dev", tier="staging"
            ),
            image_tag="v1.0.0",
        )
    request = SimpleNamespace(
        id=uuid.uuid4(),
        image_tag=image_tag,
        git_sha=None,
        target_tier=target_tier,
    )
    return GateContext(
        db=MagicMock(),
        promotion_request=request,
        application=app,
        source_deployment=source_deployment,
        target_tier=target_tier,
    )


# ---------------------------------------------------------------------------
# deployed_in_prior_env
# ---------------------------------------------------------------------------


async def test_deployed_in_prior_env_healthy_passes():
    ctx = _fake_ctx(source_health="Healthy", target_tier="production")
    result = await gate_deployed_in_prior_env({}, ctx)
    assert result.passed is True
    assert result.gate_type == "deployed_in_prior_env"


async def test_deployed_in_prior_env_missing_source_fails():
    ctx = _fake_ctx(source_health=None, target_tier="production")
    result = await gate_deployed_in_prior_env({}, ctx)
    assert result.passed is False
    assert "No deployment" in result.message


async def test_deployed_in_prior_env_degraded_fails():
    ctx = _fake_ctx(source_health="Degraded", target_tier="production")
    result = await gate_deployed_in_prior_env({}, ctx)
    assert result.passed is False
    assert "Degraded" in result.message


async def test_deployed_in_prior_env_dev_is_na_pass():
    ctx = _fake_ctx(source_health=None, target_tier="dev")
    result = await gate_deployed_in_prior_env({}, ctx)
    assert result.passed is True
    assert "N/A" in result.message or "no prior" in result.message.lower()


# ---------------------------------------------------------------------------
# min_time_in_prior_env
# ---------------------------------------------------------------------------


async def test_min_time_in_prior_env_sufficient_soak_passes():
    long_ago = datetime.now(timezone.utc) - timedelta(hours=48)
    ctx = _fake_ctx(source_deployed_at=long_ago)
    result = await gate_min_time_in_prior_env({"hours": 24}, ctx)
    assert result.passed is True


async def test_min_time_in_prior_env_too_recent_fails():
    recent = datetime.now(timezone.utc) - timedelta(hours=1)
    ctx = _fake_ctx(source_deployed_at=recent)
    result = await gate_min_time_in_prior_env({"hours": 24}, ctx)
    assert result.passed is False
    assert result.details["required_hours"] == 24


# ---------------------------------------------------------------------------
# health_passing
# ---------------------------------------------------------------------------


async def test_health_passing_healthy():
    ctx = _fake_ctx(source_health="Healthy")
    result = await gate_health_passing({}, ctx)
    assert result.passed is True


async def test_health_passing_degraded_fails():
    ctx = _fake_ctx(source_health="Degraded")
    result = await gate_health_passing({}, ctx)
    assert result.passed is False
    assert result.details["health_status"] == "Degraded"


# ---------------------------------------------------------------------------
# manual_approval
# ---------------------------------------------------------------------------


async def test_manual_approval_never_passes_at_eval():
    ctx = _fake_ctx()
    result = await gate_manual_approval(
        {"required_role": "team-admin", "count": 2}, ctx
    )
    assert result.passed is False
    assert result.details == {"required_role": "team-admin", "count": 2}


# ---------------------------------------------------------------------------
# github_tag_exists
# ---------------------------------------------------------------------------


class _FakeResp:
    def __init__(self, status: int):
        self.status_code = status


class _FakeAsyncClient:
    def __init__(self, status: int):
        self._status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, headers=None):
        return _FakeResp(self._status)


async def test_github_tag_exists_200_passes():
    ctx = _fake_ctx()
    with patch(
        "app.services.gate_service.httpx.AsyncClient",
        lambda timeout=10.0: _FakeAsyncClient(200),
    ):
        result = await gate_github_tag_exists({}, ctx)
    assert result.passed is True


async def test_github_tag_exists_404_fails():
    ctx = _fake_ctx()
    with patch(
        "app.services.gate_service.httpx.AsyncClient",
        lambda timeout=10.0: _FakeAsyncClient(404),
    ):
        result = await gate_github_tag_exists({}, ctx)
    assert result.passed is False
    assert result.enforcement == "blocking"


async def test_github_tag_exists_500_is_advisory():
    ctx = _fake_ctx()
    with patch(
        "app.services.gate_service.httpx.AsyncClient",
        lambda timeout=10.0: _FakeAsyncClient(500),
    ):
        result = await gate_github_tag_exists({}, ctx)
    assert result.passed is False
    assert result.enforcement == "advisory"


# ---------------------------------------------------------------------------
# list_applicable_gates: platform+team merging
# ---------------------------------------------------------------------------


async def _make_team_app(db_session) -> tuple[Team, Application]:
    team = Team(
        slug=f"gate-team-{uuid.uuid4().hex[:6]}",
        display_name="Gate Team",
        owner_email="owner@company.com",
    )
    db_session.add(team)
    await db_session.flush()
    app = Application(
        team_id=team.id,
        name="svc",
        display_name="svc",
        owner_email="owner@company.com",
        default_strategy="rolling",
    )
    db_session.add(app)
    await db_session.flush()
    return team, app


async def test_list_applicable_gates_merges_platform_and_team(
    db_session, seeded_platform_gates
):
    team, app = await _make_team_app(db_session)
    # Team adds an extra advisory gate of a different type.
    db_session.add(
        PromotionGate(
            scope="team",
            team_id=team.id,
            application_id=None,
            tier="production",
            gate_type="max_high_cves",
            config={"max": 5},
            enforcement="advisory",
            created_by="team@company.com",
        )
    )
    await db_session.flush()

    gates = await list_applicable_gates(db_session, app, "production")
    types = sorted(g.gate_type for g in gates)
    # 6 platform production + 1 team
    assert "max_high_cves" in types
    assert types.count("deployed_in_prior_env") == 1
    # Platform production gates are all present
    assert {"deployed_in_prior_env", "health_passing", "min_time_in_prior_env",
            "no_critical_cves", "compliance_score_min",
            "manual_approval"}.issubset(set(types))


async def test_team_gate_cannot_override_platform_gate_of_same_type(
    db_session, seeded_platform_gates
):
    team, app = await _make_team_app(db_session)
    # Try to relax min_time_in_prior_env from 24h to 1h via a team gate
    db_session.add(
        PromotionGate(
            scope="team",
            team_id=team.id,
            application_id=None,
            tier="production",
            gate_type="min_time_in_prior_env",
            config={"hours": 1},
            enforcement="blocking",
            created_by="team@company.com",
        )
    )
    await db_session.flush()

    gates = await list_applicable_gates(db_session, app, "production")
    min_time_gates = [g for g in gates if g.gate_type == "min_time_in_prior_env"]
    assert len(min_time_gates) == 1
    assert min_time_gates[0].scope == "platform"
    assert (min_time_gates[0].config or {}).get("hours") == 24
