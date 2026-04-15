"""Promotion request state machine.

Phase 2 deployment governance. Orchestrates gate evaluation, manual approval,
execution via Argo CD, and rollback for application promotions between tiers.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import (
    Application,
    ApplicationDeployment,
    ApplicationDeploymentEvent,
)
from app.models.environment import Environment
from app.models.promotion import PromotionGateResult, PromotionRequest
from app.models.team import Team
from app.schemas.promotion import PromotionRequestCreate
from app.services import application_service, audit_service
from app.services.k8s_service import k8s_service

logger = logging.getLogger(__name__)


SOURCE_TIER_MAP = {
    "production": "staging",
    "staging": "dev",
}

ADMIN_ROLES = {"admin", "platform-admin"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _load_request(
    db: AsyncSession, request_id: uuid.UUID | str
) -> PromotionRequest | None:
    result = await db.execute(
        select(PromotionRequest)
        .where(PromotionRequest.id == request_id)
        .options(
            selectinload(PromotionRequest.application).selectinload(Application.team),
            selectinload(PromotionRequest.application)
            .selectinload(Application.deployments)
            .selectinload(ApplicationDeployment.environment),
            selectinload(PromotionRequest.from_deployment).selectinload(
                ApplicationDeployment.environment
            ),
            selectinload(PromotionRequest.to_environment),
            selectinload(PromotionRequest.gate_results),
        )
    )
    return result.scalar_one_or_none()


async def _require_request(
    db: AsyncSession, request_id: uuid.UUID | str
) -> PromotionRequest:
    request = await _load_request(db, request_id)
    if request is None:
        raise ValueError(f"Promotion request '{request_id}' not found")
    return request


async def _get_team_by_slug(db: AsyncSession, team_slug: str) -> Team:
    result = await db.execute(
        select(Team)
        .where(Team.slug == team_slug)
        .options(selectinload(Team.members))
    )
    team = result.scalar_one_or_none()
    if team is None:
        raise ValueError(f"Team '{team_slug}' not found")
    return team


def _validate_team_membership(team: Team, user_email: str) -> None:
    emails = {m.email for m in team.members}
    if team.owner_email:
        emails.add(team.owner_email)
    if user_email not in emails:
        raise ValueError(
            f"User '{user_email}' is not a member of team '{team.slug}'"
        )


def _find_deployment_for_tier(
    app: Application, tier: str
) -> ApplicationDeployment | None:
    for d in app.deployments:
        if d.environment and d.environment.tier == tier:
            return d
    return None


def _manual_approval_gate_result(
    request: PromotionRequest,
) -> PromotionGateResult | None:
    for gr in request.gate_results:
        if gr.gate_type == "manual_approval":
            return gr
    return None


def _is_admin(user_roles: list[str]) -> bool:
    return any(r in ADMIN_ROLES for r in user_roles)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def create_request(
    db: AsyncSession,
    team_slug: str,
    app_name: str,
    data: PromotionRequestCreate,
    user_email: str,
) -> PromotionRequest:
    team = await _get_team_by_slug(db, team_slug)
    _validate_team_membership(team, user_email)

    app = await application_service._get_application(db, team_slug, app_name)

    target_tier = data.target_tier
    source_tier = SOURCE_TIER_MAP.get(target_tier)
    if source_tier is None:
        raise ValueError("cannot promote to dev")

    # Resolve target environment (should already exist).
    env_result = await db.execute(
        select(Environment).where(
            Environment.team_id == app.team_id,
            Environment.tier == target_tier,
        )
    )
    target_env = env_result.scalar_one_or_none()
    if target_env is None:
        raise ValueError(
            f"Environment '{target_tier}' does not exist for team '{team_slug}'"
        )

    source_deployment = _find_deployment_for_tier(app, source_tier)

    strategy = data.strategy or app.default_strategy or "rolling"
    if strategy in ("bluegreen", "canary") and target_tier != "production":
        raise ValueError(
            "Blue-green and canary strategies are only allowed on production"
        )

    image_tag = data.image_tag
    if image_tag is None:
        if source_deployment is None or source_deployment.image_tag is None:
            raise ValueError(
                f"image_tag not provided and no source deployment found in '{source_tier}'"
            )
        image_tag = source_deployment.image_tag

    request = PromotionRequest(
        application_id=app.id,
        from_deployment_id=source_deployment.id if source_deployment else None,
        to_environment_id=target_env.id,
        source_tier=source_tier,
        target_tier=target_tier,
        requested_by=user_email,
        status="pending_gates",
        image_tag=image_tag,
        chart_version=data.chart_version,
        git_sha=data.git_sha,
        value_overrides=data.value_overrides,
        strategy=strategy,
        canary_steps={"steps": data.canary_steps} if data.canary_steps else None,
        notes=data.notes,
    )
    db.add(request)
    await db.flush()

    # Reload with relationships.
    request = await _require_request(db, request.id)

    await audit_service.log_action(
        db,
        user_email=user_email,
        action="request_promotion",
        resource_type="promotion_request",
        resource_id=str(request.id),
        team_slug=team_slug,
        request_body={
            "application": app_name,
            "target_tier": target_tier,
            "image_tag": image_tag,
            "strategy": strategy,
        },
    )

    return await _evaluate_and_advance(db, request)


async def _evaluate_and_advance(
    db: AsyncSession, request: PromotionRequest
) -> PromotionRequest:
    """Evaluate gates and advance status. Auto-executes when no approval needed."""
    # Lazy import to avoid circular dep at module load time while parallel work
    # builds gate_service.
    from app.services.gate_service import (
        evaluate_gates,
        has_blocking_failure,
        needs_manual_approval,
    )

    results = await evaluate_gates(db, request)

    # gate_service is expected to persist results; reload request to pick them up.
    request = await _require_request(db, request.id)

    if has_blocking_failure(results):
        failed = [
            getattr(r, "gate_type", "unknown")
            for r in results
            if not getattr(r, "passed", False)
            and getattr(r, "gate_type", None) != "manual_approval"
        ]
        request.status = "rejected"
        request.rejected_reason = f"gate(s) failed: {', '.join(failed) or 'unknown'}"
        await db.flush()
        return request

    if needs_manual_approval(results):
        request.status = "pending_approval"
        await db.flush()
        return request

    request.status = "approved"
    await db.flush()
    return await execute_request(db, request)


async def approve_request(
    db: AsyncSession,
    request_id: uuid.UUID | str,
    user_email: str,
    user_roles: list[str],
) -> PromotionRequest:
    request = await _require_request(db, request_id)
    if request.status != "pending_approval":
        raise ValueError(
            f"Cannot approve request in status '{request.status}'"
        )

    manual_gate = _manual_approval_gate_result(request)
    required_role = "admin"
    if manual_gate and manual_gate.details:
        required_role = manual_gate.details.get("required_role", "admin")

    if required_role not in user_roles and not _is_admin(user_roles):
        raise ValueError(
            f"User lacks required role '{required_role}' to approve promotion"
        )

    request.approver_email = user_email
    request.approved_at = datetime.now(timezone.utc)
    request.status = "approved"
    await db.flush()

    await audit_service.log_action(
        db,
        user_email=user_email,
        action="approve_promotion",
        resource_type="promotion_request",
        resource_id=str(request.id),
    )

    return await execute_request(db, request)


async def reject_request(
    db: AsyncSession,
    request_id: uuid.UUID | str,
    user_email: str,
    reason: str,
) -> PromotionRequest:
    request = await _require_request(db, request_id)
    if request.status not in ("pending_gates", "pending_approval"):
        raise ValueError(
            f"Cannot reject request in status '{request.status}'"
        )

    request.status = "rejected"
    request.rejected_reason = reason
    await db.flush()

    await audit_service.log_action(
        db,
        user_email=user_email,
        action="reject_promotion",
        resource_type="promotion_request",
        resource_id=str(request.id),
        request_body={"reason": reason},
    )
    return request


async def force_execute(
    db: AsyncSession,
    request_id: uuid.UUID | str,
    user_email: str,
    reason: str,
    user_roles: list[str],
) -> PromotionRequest:
    if not _is_admin(user_roles):
        raise ValueError("Force execute requires admin or platform-admin role")

    request = await _require_request(db, request_id)
    if request.status not in ("pending_gates", "pending_approval", "rejected"):
        raise ValueError(
            f"Cannot force execute request in status '{request.status}'"
        )

    request.force_reason = reason
    request.forced_by = user_email
    request.status = "approved"
    await db.flush()

    await audit_service.log_action(
        db,
        user_email=user_email,
        action="force_promotion",
        resource_type="promotion_request",
        resource_id=str(request.id),
        request_body={"reason": reason},
    )
    return await execute_request(db, request)


async def cancel_request(
    db: AsyncSession,
    request_id: uuid.UUID | str,
    user_email: str,
) -> PromotionRequest:
    request = await _require_request(db, request_id)
    if request.status not in ("pending_gates", "pending_approval", "approved"):
        raise ValueError(
            f"Cannot cancel request in status '{request.status}'"
        )
    request.status = "cancelled"
    await db.flush()

    await audit_service.log_action(
        db,
        user_email=user_email,
        action="cancel_promotion",
        resource_type="promotion_request",
        resource_id=str(request.id),
    )
    return request


async def execute_request(
    db: AsyncSession,
    request_id_or_obj: uuid.UUID | str | PromotionRequest,
) -> PromotionRequest:
    if isinstance(request_id_or_obj, PromotionRequest):
        request = request_id_or_obj
        # Ensure relationships are loaded.
        if request.application is None or request.to_environment is None:
            request = await _require_request(db, request.id)
    else:
        request = await _require_request(db, request_id_or_obj)

    app = request.application
    target_env = request.to_environment
    target_tier = request.target_tier

    cluster = k8s_service.cluster_for_tier(target_tier)

    # Capture current Argo CD revision as rollback point.
    existing_deployment = _find_deployment_for_tier(app, target_tier)
    argocd_app_name: str | None = (
        existing_deployment.argocd_app_name if existing_deployment else None
    )
    rollback_revision: str | None = None
    if argocd_app_name:
        try:
            current = k8s_service.get_argo_application(
                cluster, "argocd", argocd_app_name
            )
            if current is not None:
                status = current.get("status", {}) or {}
                op_state = status.get("operationState", {}) or {}
                sync_result = op_state.get("syncResult", {}) or {}
                rollback_revision = sync_result.get("revision") or (
                    status.get("sync", {}) or {}
                ).get("revision")
        except Exception as e:
            logger.warning(
                "Could not capture rollback revision for %s: %s",
                argocd_app_name,
                e,
            )
    if rollback_revision:
        request.rollback_revision = rollback_revision

    # Build the updated Argo CD Application body.
    body = application_service._build_argocd_app_body(
        app=app,
        environment=target_env,
        cluster=cluster,
        image_tag=request.image_tag,
        chart_version=request.chart_version,
        value_overrides=request.value_overrides,
    )
    new_argocd_app_name = body["metadata"]["name"]

    strategy = request.strategy or "rolling"
    if strategy in ("bluegreen", "canary") and target_tier == "production":
        try:
            from app.services.rollout_service import (  # type: ignore
                RolloutsNotAvailable,
                build_rollout_manifest,
            )

            # TODO(Phase 2b): integrate rollout manifest into Argo app body or
            # apply it as a sidecar resource once rollout_service stabilizes.
            build_rollout_manifest(app, target_env, request)
        except ImportError:
            # TODO(Phase 2b): rollout_service not yet available.
            logger.warning(
                "rollout_service not available; falling back to rolling strategy"
            )
            strategy = "rolling"
        except Exception as e:
            # RolloutsNotAvailable or other — degrade to rolling.
            logger.warning(
                "Rollout manifest build failed (%s); falling back to rolling",
                e,
            )
            strategy = "rolling"

    k8s_service.create_argo_application(cluster, "argocd", body)

    now = datetime.now(timezone.utc)
    actor = request.approver_email or request.requested_by
    previous_image_tag: str | None = None

    if existing_deployment is None:
        deployment = ApplicationDeployment(
            application_id=app.id,
            environment_id=target_env.id,
            argocd_app_name=new_argocd_app_name,
            image_tag=request.image_tag,
            chart_version=request.chart_version,
            git_sha=request.git_sha,
            strategy=strategy,
            deployed_at=now,
            deployed_by=actor,
        )
        db.add(deployment)
        await db.flush()
    else:
        previous_image_tag = existing_deployment.image_tag
        existing_deployment.argocd_app_name = new_argocd_app_name
        existing_deployment.image_tag = request.image_tag
        existing_deployment.chart_version = request.chart_version
        existing_deployment.git_sha = request.git_sha
        existing_deployment.strategy = strategy
        existing_deployment.deployed_at = now
        existing_deployment.deployed_by = actor
        deployment = existing_deployment

    source_deployment = request.from_deployment
    from_version = (
        source_deployment.image_tag if source_deployment else previous_image_tag
    )

    event = ApplicationDeploymentEvent(
        deployment_id=deployment.id,
        event_type="sync_started",
        from_version=from_version,
        to_version=request.image_tag,
        actor=actor,
        details={"promotion_request_id": str(request.id)},
        occurred_at=now,
    )
    db.add(event)

    request.status = "executing"
    request.executed_at = now
    await db.flush()

    return request


async def rollback_request(
    db: AsyncSession,
    request_id: uuid.UUID | str,
    user_email: str,
    reason: str,
) -> PromotionRequest:
    request = await _require_request(db, request_id)
    if request.status not in ("executing", "completed", "failed"):
        raise ValueError(
            f"Cannot rollback request in status '{request.status}'"
        )

    await _perform_rollback(request, reason, actor=user_email)

    request.status = "rolled_back"
    await db.flush()

    await audit_service.log_action(
        db,
        user_email=user_email,
        action="rollback_promotion",
        resource_type="promotion_request",
        resource_id=str(request.id),
        request_body={"reason": reason},
    )
    return request


async def auto_rollback(
    db: AsyncSession,
    request_id: uuid.UUID | str,
    reason: str = "degraded_health_timeout",
) -> PromotionRequest:
    request = await _require_request(db, request_id)
    if request.status not in ("executing", "completed", "failed"):
        raise ValueError(
            f"Cannot auto-rollback request in status '{request.status}'"
        )

    await _perform_rollback(request, reason, actor="system")

    request.status = "rolled_back"
    await db.flush()

    await audit_service.log_action(
        db,
        user_email="system",
        action="rollback_promotion",
        resource_type="promotion_request",
        resource_id=str(request.id),
        request_body={"reason": reason, "auto": True},
    )
    return request


async def _perform_rollback(
    request: PromotionRequest, reason: str, actor: str
) -> None:
    """Attempt to roll back the Argo CD Application to rollback_revision.

    k8s_service does not yet expose a first-class sync/rollback helper; log the
    intent when unavailable so the sync loop / operators can follow up.
    """
    if not request.rollback_revision:
        logger.warning(
            "Rollback requested for %s but no rollback_revision captured; "
            "reason=%s actor=%s",
            request.id,
            reason,
            actor,
        )
        return

    # TODO(Phase 2b): k8s_service needs a rollback/sync-to-revision helper.
    # For now we log the intent; sync loop (task #50) will reconcile.
    logger.warning(
        "Rollback intent for promotion %s to revision %s (reason=%s, actor=%s) "
        "-- k8s_service rollback helper not yet implemented",
        request.id,
        request.rollback_revision,
        reason,
        actor,
    )


async def list_requests(
    db: AsyncSession,
    team_slug: str | None = None,
    app_name: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[PromotionRequest], int]:
    query = select(PromotionRequest).options(
        selectinload(PromotionRequest.application).selectinload(Application.team),
        selectinload(PromotionRequest.gate_results),
        selectinload(PromotionRequest.from_deployment),
        selectinload(PromotionRequest.to_environment),
    )
    count_query = select(func.count()).select_from(PromotionRequest)

    if team_slug is not None or app_name is not None:
        query = query.join(Application, Application.id == PromotionRequest.application_id)
        count_query = count_query.join(
            Application, Application.id == PromotionRequest.application_id
        )
        if team_slug is not None:
            query = query.join(Team, Team.id == Application.team_id).where(
                Team.slug == team_slug
            )
            count_query = count_query.join(
                Team, Team.id == Application.team_id
            ).where(Team.slug == team_slug)
        if app_name is not None:
            query = query.where(Application.name == app_name)
            count_query = count_query.where(Application.name == app_name)

    if status is not None:
        query = query.where(PromotionRequest.status == status)
        count_query = count_query.where(PromotionRequest.status == status)

    query = query.order_by(PromotionRequest.requested_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    items = list(result.scalars().all())

    total_result = await db.execute(count_query)
    total = int(total_result.scalar() or 0)

    return items, total


async def get_request(
    db: AsyncSession, request_id: uuid.UUID | str
) -> PromotionRequest | None:
    return await _load_request(db, request_id)
