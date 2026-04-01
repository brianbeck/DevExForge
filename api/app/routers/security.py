"""Security and compliance endpoints."""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import CurrentUser, get_current_user
from app.services import environment_service
from app.services.k8s_service import k8s_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/teams/{slug}/environments/{tier}",
    tags=["security"],
)


async def _get_env_namespace(db: AsyncSession, slug: str, tier: str) -> tuple[str, str]:
    """Get the namespace and cluster for an environment. Raises HTTPException if not found."""
    try:
        env = await environment_service.get_environment(db, slug, tier)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    cluster = k8s_service.cluster_for_tier(tier)
    return env.namespace_name, cluster


@router.get("/violations")
async def get_violations(
    slug: str,
    tier: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get Gatekeeper policy violations for an environment."""
    namespace, cluster = await _get_env_namespace(db, slug, tier)
    try:
        violations = k8s_service.list_gatekeeper_violations(cluster, namespace)
    except Exception:
        logger.warning("Failed to fetch violations for %s", namespace, exc_info=True)
        violations = []
    return {"violations": violations, "total": len(violations)}


@router.get("/vulnerabilities")
async def get_vulnerabilities(
    slug: str,
    tier: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get Trivy vulnerability reports for an environment."""
    namespace, cluster = await _get_env_namespace(db, slug, tier)
    try:
        reports = k8s_service.list_vulnerability_reports(cluster, namespace)
    except Exception:
        logger.warning("Failed to fetch vulnerability reports for %s", namespace, exc_info=True)
        reports = []
    return {"vulnerabilities": reports, "total": len(reports)}


@router.get("/security-events")
async def get_security_events(
    slug: str,
    tier: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
) -> dict:
    """Get Falco security events for an environment."""
    namespace, cluster = await _get_env_namespace(db, slug, tier)
    try:
        events = k8s_service.list_falco_events(cluster, namespace, limit=limit)
    except Exception:
        logger.warning("Failed to fetch Falco events for %s", namespace, exc_info=True)
        events = []
    return {"events": events, "total": len(events)}


@router.get("/compliance-summary")
async def get_compliance_summary(
    slug: str,
    tier: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get a compliance summary for an environment."""
    namespace, cluster = await _get_env_namespace(db, slug, tier)

    violations = []
    vulnerabilities = []
    events = []

    try:
        violations = k8s_service.list_gatekeeper_violations(cluster, namespace)
    except Exception:
        logger.warning("Failed to fetch violations for %s", namespace, exc_info=True)

    try:
        vulnerabilities = k8s_service.list_vulnerability_reports(cluster, namespace)
    except Exception:
        logger.warning("Failed to fetch vulns for %s", namespace, exc_info=True)

    try:
        events = k8s_service.list_falco_events(cluster, namespace, limit=10)
    except Exception:
        logger.warning("Failed to fetch Falco events for %s", namespace, exc_info=True)

    total_critical = sum(v.get("critical", 0) for v in vulnerabilities)
    total_high = sum(v.get("high", 0) for v in vulnerabilities)

    # Compliance score: 100 minus penalties
    score = 100
    score -= len(violations) * 10       # -10 per policy violation
    score -= total_critical * 20         # -20 per critical CVE
    score -= total_high * 5              # -5 per high CVE
    score -= len(events) * 2             # -2 per Falco event
    score = max(0, score)

    status = "compliant" if score >= 80 else "warning" if score >= 50 else "critical"

    return {
        "score": score,
        "status": status,
        "policyViolations": len(violations),
        "criticalCVEs": total_critical,
        "highCVEs": total_high,
        "securityEvents": len(events),
        "imageCount": len(vulnerabilities),
    }
