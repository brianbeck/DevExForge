import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import CurrentUser, get_current_user
from app.models.promotion import PromotionRequest
from app.schemas.promotion import (
    FromDeploymentSummary,
    GateResultResponse,
    PromotionApproveRequest,
    PromotionForceRequest,
    PromotionRejectRequest,
    PromotionRequestCreate,
    PromotionRequestDetailResponse,
    PromotionRequestListResponse,
    PromotionRequestResponse,
    PromotionRollbackRequest,
)
from app.services import promotion_service, team_service

logger = logging.getLogger(__name__)


team_router = APIRouter(
    prefix="/api/v1/teams/{slug}/applications/{name}", tags=["promotions"]
)
router = APIRouter(prefix="/api/v1/promotion-requests", tags=["promotions"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _value_error_status(message: str) -> int:
    msg = message.lower()
    if "not found" in msg or "does not exist" in msg:
        return 404
    return 409


async def _check_team_permission(
    slug: str,
    user: CurrentUser,
    db: AsyncSession,
    require_admin: bool = False,
    member_only: bool = False,
) -> None:
    """Check team permission.

    - member_only: any team member (admin, developer, viewer) or owner passes.
    - require_admin: only team admin or platform admin.
    - default: admin or developer.
    """
    if "admin" in user.roles:
        return
    team = await team_service.get_team(db, slug)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    if team.owner_email == user.email:
        return
    for m in (team.members or []):
        if m.email == user.email:
            if member_only:
                return
            if require_admin:
                if m.role == "admin":
                    return
            else:
                if m.role in ("admin", "developer"):
                    return
            break
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission for this team",
    )


def _from_deployment_summary(request: PromotionRequest) -> FromDeploymentSummary | None:
    d = request.from_deployment
    if d is None:
        return None
    tier = d.environment.tier if d.environment else (request.source_tier or "")
    return FromDeploymentSummary(
        id=d.id,
        tier=tier,
        imageTag=d.image_tag,
        chartVersion=d.chart_version,
        gitSha=d.git_sha,
        healthStatus=d.health_status,
        syncStatus=d.sync_status,
        deployedAt=d.deployed_at,
    )


def _base_fields(request: PromotionRequest) -> dict:
    canary_steps = None
    if request.canary_steps and isinstance(request.canary_steps, dict):
        canary_steps = request.canary_steps.get("steps")
    app = request.application
    team = app.team if app is not None else None
    return dict(
        id=request.id,
        applicationId=request.application_id,
        applicationName=app.name if app is not None else None,
        teamSlug=team.slug if team is not None else None,
        fromTier=request.source_tier,
        targetTier=request.target_tier,
        fromDeploymentId=request.from_deployment_id,
        imageTag=request.image_tag,
        chartVersion=request.chart_version,
        gitSha=request.git_sha,
        valueOverrides=request.value_overrides,
        strategy=request.strategy,
        canarySteps=canary_steps,
        status=request.status,
        notes=request.notes,
        requestedBy=request.requested_by,
        requestedAt=request.requested_at,
        approverEmail=request.approver_email,
        approvedAt=request.approved_at,
        rejectionReason=request.rejected_reason,
        forceReason=request.force_reason,
        forcedBy=request.forced_by,
        executedAt=request.executed_at,
        completedAt=request.completed_at,
        rollbackRevision=request.rollback_revision,
        createdAt=request.requested_at,
        updatedAt=request.requested_at,
    )


def _to_response(request: PromotionRequest) -> PromotionRequestResponse:
    return PromotionRequestResponse(**_base_fields(request))


def _to_detail_response(request: PromotionRequest) -> PromotionRequestDetailResponse:
    gate_results = [
        GateResultResponse(
            id=gr.id,
            gateType=gr.gate_type,
            passed=gr.passed,
            message=gr.message,
            details=gr.details,
            evaluatedAt=gr.evaluated_at,
        )
        for gr in (request.gate_results or [])
    ]
    return PromotionRequestDetailResponse(
        **_base_fields(request),
        gateResults=gate_results,
        fromDeployment=_from_deployment_summary(request),
    )


def _to_list_response(
    requests: list[PromotionRequest], total: int, filters: dict
) -> PromotionRequestListResponse:
    return PromotionRequestListResponse(
        items=[_to_response(r) for r in requests],
        total=total,
        filters=filters,
    )


async def _require_request_or_404(
    db: AsyncSession, request_id: UUID
) -> PromotionRequest:
    request = await promotion_service.get_request(db, request_id)
    if request is None:
        raise HTTPException(
            status_code=404, detail=f"Promotion request '{request_id}' not found"
        )
    return request


async def _check_request_team_permission(
    db: AsyncSession,
    request: PromotionRequest,
    user: CurrentUser,
    require_admin: bool = False,
    member_only: bool = False,
) -> None:
    team = request.application.team if request.application else None
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found for request")
    await _check_team_permission(
        team.slug, user, db, require_admin=require_admin, member_only=member_only
    )


# ---------------------------------------------------------------------------
# Team-scoped endpoints
# ---------------------------------------------------------------------------


@team_router.post(
    "/promotion-requests", status_code=status.HTTP_201_CREATED
)
async def create_promotion_request(
    slug: str,
    name: str,
    data: PromotionRequestCreate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PromotionRequestResponse:
    await _check_team_permission(slug, user, db)
    try:
        request = await promotion_service.create_request(
            db, slug, name, data, user.email
        )
    except ValueError as e:
        raise HTTPException(status_code=_value_error_status(str(e)), detail=str(e))
    except IntegrityError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return _to_response(request)


@team_router.get("/promotion-requests")
async def list_team_promotion_requests(
    slug: str,
    name: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: int = 50,
    offset: int = 0,
) -> PromotionRequestListResponse:
    await _check_team_permission(slug, user, db, member_only=True)
    try:
        items, total = await promotion_service.list_requests(
            db,
            team_slug=slug,
            app_name=name,
            status=status_filter,
            limit=limit,
            offset=offset,
        )
    except ValueError as e:
        raise HTTPException(status_code=_value_error_status(str(e)), detail=str(e))
    return _to_list_response(
        items,
        total,
        {"teamSlug": slug, "appName": name, "status": status_filter},
    )


# ---------------------------------------------------------------------------
# Global / admin endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_all_promotion_requests(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    team_slug: Annotated[str | None, Query(alias="teamSlug")] = None,
    app_name: Annotated[str | None, Query(alias="appName")] = None,
    limit: int = 50,
    offset: int = 0,
) -> PromotionRequestListResponse:
    if "admin" not in user.roles and "platform-admin" not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    items, total = await promotion_service.list_requests(
        db,
        team_slug=team_slug,
        app_name=app_name,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return _to_list_response(
        items,
        total,
        {"teamSlug": team_slug, "appName": app_name, "status": status_filter},
    )


@router.get("/{request_id}")
async def get_promotion_request(
    request_id: UUID,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PromotionRequestDetailResponse:
    request = await _require_request_or_404(db, request_id)
    await _check_request_team_permission(db, request, user, member_only=True)
    return _to_detail_response(request)


@router.post("/{request_id}/approve")
async def approve_promotion_request(
    request_id: UUID,
    data: PromotionApproveRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PromotionRequestResponse:
    request = await _require_request_or_404(db, request_id)
    # Team membership check; role requirement enforced by service against gate config.
    await _check_request_team_permission(db, request, user, member_only=True)
    try:
        request = await promotion_service.approve_request(
            db, request_id, user.email, user.roles
        )
    except ValueError as e:
        raise HTTPException(status_code=_value_error_status(str(e)), detail=str(e))
    return _to_response(request)


@router.post("/{request_id}/reject")
async def reject_promotion_request(
    request_id: UUID,
    data: PromotionRejectRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PromotionRequestResponse:
    request = await _require_request_or_404(db, request_id)
    await _check_request_team_permission(db, request, user, member_only=True)
    try:
        request = await promotion_service.reject_request(
            db, request_id, user.email, data.reason
        )
    except ValueError as e:
        raise HTTPException(status_code=_value_error_status(str(e)), detail=str(e))
    return _to_response(request)


@router.post("/{request_id}/force")
async def force_promotion_request(
    request_id: UUID,
    data: PromotionForceRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PromotionRequestResponse:
    if "admin" not in user.roles and "platform-admin" not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin role required",
        )
    await _require_request_or_404(db, request_id)
    try:
        request = await promotion_service.force_execute(
            db, request_id, user.email, data.reason, user.roles
        )
    except ValueError as e:
        raise HTTPException(status_code=_value_error_status(str(e)), detail=str(e))
    return _to_response(request)


@router.post("/{request_id}/rollback")
async def rollback_promotion_request(
    request_id: UUID,
    data: PromotionRollbackRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PromotionRequestResponse:
    request = await _require_request_or_404(db, request_id)
    await _check_request_team_permission(db, request, user, require_admin=True)
    try:
        request = await promotion_service.rollback_request(
            db, request_id, user.email, data.reason
        )
    except ValueError as e:
        raise HTTPException(status_code=_value_error_status(str(e)), detail=str(e))
    return _to_response(request)


@router.post("/{request_id}/cancel")
async def cancel_promotion_request(
    request_id: UUID,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PromotionRequestResponse:
    request = await _require_request_or_404(db, request_id)
    # Requester or team admin (platform admin passes via _check_team_permission).
    if request.requested_by != user.email:
        await _check_request_team_permission(db, request, user, require_admin=True)
    try:
        request = await promotion_service.cancel_request(db, request_id, user.email)
    except ValueError as e:
        raise HTTPException(status_code=_value_error_status(str(e)), detail=str(e))
    return _to_response(request)
