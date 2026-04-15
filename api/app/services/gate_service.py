"""Promotion gate evaluation service.

Phase 2 of deployment governance: platform-mandatory gates and team-defined
gates are evaluated against a PromotionRequest before a promotion is allowed
to proceed. Mirrors the tier-floor pattern in policy_service: platform gates
are stricter and always win de-duplication against team gates of the same type.

Each gate type is a pluggable async function registered in GATE_REGISTRY that
evaluates a gate config against a shared GateContext and returns a GateResult.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application, ApplicationDeployment
from app.models.environment import Environment
from app.models.promotion import (
    PromotionGate,
    PromotionGateResult,
    PromotionRequest,
)
from app.services.k8s_service import k8s_service

logger = logging.getLogger(__name__)


# Prior tier for a given target tier. dev has no prior.
_PRIOR_TIER: dict[str, str | None] = {
    "dev": None,
    "staging": "dev",
    "production": "staging",
}


@dataclass
class GateResult:
    passed: bool
    gate_type: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    enforcement: str = "blocking"  # "blocking" | "advisory"

    @property
    def is_blocking_failure(self) -> bool:
        return (not self.passed) and self.enforcement == "blocking"


@dataclass
class GateContext:
    db: AsyncSession
    promotion_request: PromotionRequest
    application: Application
    source_deployment: ApplicationDeployment | None
    target_tier: str


# -----------------------------------------------------------------------------
# Gate implementations
# -----------------------------------------------------------------------------


async def gate_deployed_in_prior_env(
    config: dict, ctx: GateContext
) -> GateResult:
    prior = _PRIOR_TIER.get(ctx.target_tier)
    if prior is None:
        return GateResult(
            passed=True,
            gate_type="deployed_in_prior_env",
            message=f"Target tier '{ctx.target_tier}' has no prior tier (N/A)",
            details={"target_tier": ctx.target_tier},
        )
    if ctx.source_deployment is None:
        return GateResult(
            passed=False,
            gate_type="deployed_in_prior_env",
            message=f"No deployment found in prior tier '{prior}'",
            details={"prior_tier": prior},
        )
    health = ctx.source_deployment.health_status
    if health != "Healthy":
        return GateResult(
            passed=False,
            gate_type="deployed_in_prior_env",
            message=f"Prior tier '{prior}' deployment health is '{health}', expected 'Healthy'",
            details={"prior_tier": prior, "health_status": health},
        )
    return GateResult(
        passed=True,
        gate_type="deployed_in_prior_env",
        message=f"Application is healthy in prior tier '{prior}'",
        details={"prior_tier": prior, "health_status": health},
    )


async def gate_min_time_in_prior_env(
    config: dict, ctx: GateContext
) -> GateResult:
    hours = int(config.get("hours", 0))
    if ctx.source_deployment is None:
        return GateResult(
            passed=False,
            gate_type="min_time_in_prior_env",
            message="No source deployment to measure soak time against",
            details={"required_hours": hours},
        )
    deployed_at = ctx.source_deployment.deployed_at
    if deployed_at.tzinfo is None:
        deployed_at = deployed_at.replace(tzinfo=timezone.utc)
    elapsed = datetime.now(timezone.utc) - deployed_at
    required = timedelta(hours=hours)
    passed = elapsed >= required
    return GateResult(
        passed=passed,
        gate_type="min_time_in_prior_env",
        message=(
            f"Soaked {elapsed.total_seconds() / 3600:.1f}h in prior tier "
            f"(required: {hours}h)"
        ),
        details={
            "required_hours": hours,
            "elapsed_hours": round(elapsed.total_seconds() / 3600, 2),
            "deployed_at": deployed_at.isoformat(),
        },
    )


async def gate_health_passing(config: dict, ctx: GateContext) -> GateResult:
    if ctx.source_deployment is None:
        return GateResult(
            passed=False,
            gate_type="health_passing",
            message="No source deployment available to check health",
            details={},
        )
    health = ctx.source_deployment.health_status
    passed = health == "Healthy"
    return GateResult(
        passed=passed,
        gate_type="health_passing",
        message=f"Source deployment health: {health}",
        details={"health_status": health},
    )


def _vuln_counts_for_source(ctx: GateContext) -> tuple[int, int, str | None]:
    """Return (critical_count, high_count, namespace) for the source env, or (0,0,None).

    Inlined minimal vulnerability lookup so the service layer doesn't depend on
    routers. Uses k8s_service.list_vulnerability_reports which already aggregates
    critical/high counts per report.
    """
    if ctx.source_deployment is None:
        return 0, 0, None
    env = ctx.source_deployment.environment
    namespace = env.namespace_name
    try:
        cluster = k8s_service.cluster_for_tier(env.tier)
    except ValueError:
        return 0, 0, namespace
    try:
        reports = k8s_service.list_vulnerability_reports(cluster, namespace)
    except Exception as e:
        logger.warning(
            "Gate vuln lookup failed for %s: %s", namespace, e, exc_info=True
        )
        raise
    crit = sum(r.get("critical", 0) for r in reports)
    high = sum(r.get("high", 0) for r in reports)
    return crit, high, namespace


async def gate_no_critical_cves(config: dict, ctx: GateContext) -> GateResult:
    if ctx.source_deployment is None:
        return GateResult(
            passed=False,
            gate_type="no_critical_cves",
            message="No source deployment to scan for vulnerabilities",
            details={},
        )
    try:
        crit, high, namespace = _vuln_counts_for_source(ctx)
    except Exception as e:
        return GateResult(
            passed=False,
            gate_type="no_critical_cves",
            message=f"Failed to fetch vulnerability reports: {e}",
            details={},
        )
    passed = crit == 0
    return GateResult(
        passed=passed,
        gate_type="no_critical_cves",
        message=f"Found {crit} critical CVE(s) in namespace '{namespace}'",
        details={"critical": crit, "high": high, "namespace": namespace},
    )


async def gate_max_high_cves(config: dict, ctx: GateContext) -> GateResult:
    max_allowed = int(config.get("max", 0))
    if ctx.source_deployment is None:
        return GateResult(
            passed=False,
            gate_type="max_high_cves",
            message="No source deployment to scan for vulnerabilities",
            details={"max": max_allowed},
        )
    try:
        crit, high, namespace = _vuln_counts_for_source(ctx)
    except Exception as e:
        return GateResult(
            passed=False,
            gate_type="max_high_cves",
            message=f"Failed to fetch vulnerability reports: {e}",
            details={"max": max_allowed},
        )
    passed = high <= max_allowed
    return GateResult(
        passed=passed,
        gate_type="max_high_cves",
        message=f"Found {high} high CVE(s); limit is {max_allowed}",
        details={"high": high, "critical": crit, "max": max_allowed, "namespace": namespace},
    )


def _compute_compliance_score(ctx: GateContext) -> tuple[int, dict]:
    """Inlined version of observability compliance-summary scoring."""
    if ctx.source_deployment is None:
        return 0, {}
    env = ctx.source_deployment.environment
    namespace = env.namespace_name
    cluster = k8s_service.cluster_for_tier(env.tier)

    violations = []
    vulnerabilities = []
    events = []
    try:
        violations = k8s_service.list_gatekeeper_violations(cluster, namespace)
    except Exception:
        logger.warning("compliance gate: violations fetch failed", exc_info=True)
    try:
        vulnerabilities = k8s_service.list_vulnerability_reports(cluster, namespace)
    except Exception:
        logger.warning("compliance gate: vuln fetch failed", exc_info=True)
    try:
        events = k8s_service.list_falco_events(cluster, namespace, limit=10)
    except Exception:
        logger.warning("compliance gate: falco fetch failed", exc_info=True)

    total_critical = sum(v.get("critical", 0) for v in vulnerabilities)
    total_high = sum(v.get("high", 0) for v in vulnerabilities)

    score = 100
    score -= len(violations) * 10
    score -= total_critical * 20
    score -= total_high * 5
    score -= len(events) * 2
    score = max(0, score)

    return score, {
        "namespace": namespace,
        "policyViolations": len(violations),
        "criticalCVEs": total_critical,
        "highCVEs": total_high,
        "securityEvents": len(events),
    }


async def gate_compliance_score_min(
    config: dict, ctx: GateContext
) -> GateResult:
    min_score = int(config.get("min", 0))
    if ctx.source_deployment is None:
        return GateResult(
            passed=False,
            gate_type="compliance_score_min",
            message="No source deployment to compute compliance score",
            details={"min": min_score},
        )
    try:
        score, details = _compute_compliance_score(ctx)
    except Exception as e:
        return GateResult(
            passed=False,
            gate_type="compliance_score_min",
            message=f"Failed to compute compliance score: {e}",
            details={"min": min_score},
        )
    passed = score >= min_score
    return GateResult(
        passed=passed,
        gate_type="compliance_score_min",
        message=f"Compliance score {score} (required: {min_score})",
        details={**details, "score": score, "min": min_score},
    )


async def gate_manual_approval(config: dict, ctx: GateContext) -> GateResult:
    # Manual approval is never "passed" at evaluation time. The approval flow
    # in promotion_service flips the overall promotion state; the gate result
    # just signals the approval is pending and who can clear it.
    required_role = config.get("required_role", "team-admin")
    count = int(config.get("count", 1))
    return GateResult(
        passed=False,
        gate_type="manual_approval",
        message=(
            f"Manual approval required: {count} x '{required_role}' "
            "(cleared by approval flow, not evaluation)"
        ),
        details={"required_role": required_role, "count": count},
    )


def _parse_github_owner_repo(repo_url: str) -> tuple[str, str] | None:
    """Extract (owner, repo) from a GitHub repo URL. Returns None on failure."""
    if not repo_url:
        return None
    # Support git@github.com:owner/repo(.git) and https://github.com/owner/repo(.git)
    url = repo_url.strip()
    if url.startswith("git@"):
        try:
            _, path = url.split(":", 1)
        except ValueError:
            return None
    else:
        parsed = urlparse(url)
        if "github.com" not in (parsed.netloc or ""):
            return None
        path = parsed.path.lstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parts = path.split("/")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        return None
    return parts[0], parts[1]


async def gate_github_tag_exists(
    config: dict, ctx: GateContext
) -> GateResult:
    # Note: unauthenticated; a GITHUB_TOKEN env var could be added later for
    # private repos and higher rate limits.
    repo_url = config.get("repo") or ctx.application.repo_url
    tag = ctx.promotion_request.image_tag or ctx.promotion_request.git_sha
    if not tag:
        return GateResult(
            passed=False,
            gate_type="github_tag_exists",
            message="No image_tag or git_sha on promotion request to look up",
            details={},
        )
    parsed = _parse_github_owner_repo(repo_url or "")
    if parsed is None:
        return GateResult(
            passed=False,
            gate_type="github_tag_exists",
            message=f"Could not parse GitHub owner/repo from '{repo_url}'",
            details={"repo_url": repo_url, "tag": tag},
            enforcement="advisory",
        )
    owner, repo = parsed
    url = f"https://api.github.com/repos/{owner}/{repo}/git/refs/tags/{tag}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers={"Accept": "application/vnd.github+json"})
    except httpx.HTTPError as e:
        return GateResult(
            passed=False,
            gate_type="github_tag_exists",
            message=f"GitHub API unreachable ({e}); treated as advisory",
            details={"owner": owner, "repo": repo, "tag": tag},
            enforcement="advisory",
        )
    if resp.status_code == 200:
        return GateResult(
            passed=True,
            gate_type="github_tag_exists",
            message=f"Tag '{tag}' exists at {owner}/{repo}",
            details={"owner": owner, "repo": repo, "tag": tag},
        )
    if resp.status_code == 404:
        return GateResult(
            passed=False,
            gate_type="github_tag_exists",
            message=f"Tag '{tag}' not found at {owner}/{repo}",
            details={"owner": owner, "repo": repo, "tag": tag},
        )
    return GateResult(
        passed=False,
        gate_type="github_tag_exists",
        message=f"GitHub API returned {resp.status_code}; treated as advisory",
        details={
            "owner": owner,
            "repo": repo,
            "tag": tag,
            "status": resp.status_code,
        },
        enforcement="advisory",
    )


# -----------------------------------------------------------------------------
# Registry
# -----------------------------------------------------------------------------

GATE_REGISTRY: dict[str, Callable[[dict, GateContext], Awaitable[GateResult]]] = {
    "deployed_in_prior_env": gate_deployed_in_prior_env,
    "min_time_in_prior_env": gate_min_time_in_prior_env,
    "health_passing": gate_health_passing,
    "no_critical_cves": gate_no_critical_cves,
    "max_high_cves": gate_max_high_cves,
    "compliance_score_min": gate_compliance_score_min,
    "manual_approval": gate_manual_approval,
    "github_tag_exists": gate_github_tag_exists,
}


# -----------------------------------------------------------------------------
# Gate loading and evaluation
# -----------------------------------------------------------------------------


async def list_applicable_gates(
    db: AsyncSession,
    application: Application,
    target_tier: str,
) -> list[PromotionGate]:
    """Load platform + team gates applying to this (application, tier).

    De-duplication: if a team gate has the same gate_type as a platform gate,
    the platform one wins (stricter by platform policy).
    """
    stmt = select(PromotionGate).where(
        PromotionGate.tier == target_tier,
        or_(
            PromotionGate.scope == "platform",
            (PromotionGate.scope == "team")
            & (PromotionGate.team_id == application.team_id)
            & (
                (PromotionGate.application_id.is_(None))
                | (PromotionGate.application_id == application.id)
            ),
        ),
    )
    result = await db.execute(stmt)
    gates = list(result.scalars().all())

    # Platform gates win on gate_type collisions.
    platform_types = {g.gate_type for g in gates if g.scope == "platform"}
    deduped: list[PromotionGate] = []
    for g in gates:
        if g.scope == "team" and g.gate_type in platform_types:
            continue
        deduped.append(g)
    return deduped


async def _load_source_deployment(
    db: AsyncSession,
    application: Application,
    source_tier: str | None,
) -> ApplicationDeployment | None:
    if source_tier is None:
        return None
    stmt = (
        select(ApplicationDeployment)
        .join(Environment, Environment.id == ApplicationDeployment.environment_id)
        .where(
            ApplicationDeployment.application_id == application.id,
            Environment.tier == source_tier,
        )
        .options(selectinload(ApplicationDeployment.environment))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def evaluate_gates(
    db: AsyncSession,
    promotion_request: PromotionRequest,
) -> list[GateResult]:
    """Evaluate all applicable gates for a promotion request.

    Builds a GateContext, runs each gate through the registry (catching
    exceptions as failed results), and persists a PromotionGateResult row
    per evaluation.
    """
    # Load application
    app_stmt = (
        select(Application)
        .where(Application.id == promotion_request.application_id)
        .options(selectinload(Application.team))
    )
    app = (await db.execute(app_stmt)).scalar_one()

    # Source tier: prefer explicit request value, else infer from target
    source_tier = promotion_request.source_tier or _PRIOR_TIER.get(
        promotion_request.target_tier
    )
    source_deployment = await _load_source_deployment(db, app, source_tier)

    ctx = GateContext(
        db=db,
        promotion_request=promotion_request,
        application=app,
        source_deployment=source_deployment,
        target_tier=promotion_request.target_tier,
    )

    gates = await list_applicable_gates(db, app, promotion_request.target_tier)

    results: list[GateResult] = []
    for gate in gates:
        fn = GATE_REGISTRY.get(gate.gate_type)
        config = gate.config or {}
        if fn is None:
            result = GateResult(
                passed=False,
                gate_type=gate.gate_type,
                message=f"Unknown gate type '{gate.gate_type}' (not in registry)",
                details={},
                enforcement=gate.enforcement,
            )
        else:
            try:
                result = await fn(config, ctx)
            except Exception as e:
                logger.exception("Gate '%s' raised", gate.gate_type)
                result = GateResult(
                    passed=False,
                    gate_type=gate.gate_type,
                    message=f"gate raised: {e}",
                    details={},
                    enforcement=gate.enforcement,
                )
            # Gate row's configured enforcement overrides the function default,
            # except: manual_approval and advisory failures from network errors
            # should preserve advisory semantics when the gate row itself is
            # blocking (platform can't relax network flakiness into blocking).
            # For simplicity: the DB row's enforcement wins unless the gate
            # function explicitly downgraded to advisory.
            if result.enforcement != "advisory":
                result.enforcement = gate.enforcement

        results.append(result)

        db.add(
            PromotionGateResult(
                promotion_request_id=promotion_request.id,
                gate_id=gate.id,
                gate_type=result.gate_type,
                passed=result.passed,
                message=result.message,
                details=result.details or None,
            )
        )

    await db.flush()
    return results


# -----------------------------------------------------------------------------
# Convenience helpers
# -----------------------------------------------------------------------------


def has_blocking_failure(results: list[GateResult]) -> bool:
    # manual_approval is always passed=False by design — it signals "awaiting
    # approval", not "gate failed". The approval flow clears it, so it never
    # counts as a blocking failure here.
    return any(
        r.is_blocking_failure for r in results if r.gate_type != "manual_approval"
    )


def needs_manual_approval(results: list[GateResult]) -> bool:
    return any(
        r.gate_type == "manual_approval" and not r.passed for r in results
    )
