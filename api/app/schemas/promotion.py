from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


Tier = Literal["dev", "staging", "production"]
Strategy = Literal["rolling", "bluegreen", "canary"]
GateScope = Literal["platform", "team"]
GateType = Literal[
    "deployed_in_prior_env",
    "min_time_in_prior_env",
    "health_passing",
    "no_critical_cves",
    "max_high_cves",
    "compliance_score_min",
    "manual_approval",
    "github_tag_exists",
]
Enforcement = Literal["blocking", "advisory"]
PromotionStatus = Literal[
    "pending_gates",
    "pending_approval",
    "approved",
    "rejected",
    "executing",
    "completed",
    "failed",
    "rolled_back",
    "cancelled",
]
RolloutPhase = Literal["Progressing", "Paused", "Healthy", "Degraded"]


GateConfig = dict[str, Any]


class PromotionGateCreate(BaseModel):
    scope: GateScope
    team_id: UUID | None = Field(None, alias="teamId")
    application_id: UUID | None = Field(None, alias="applicationId")
    tier: Tier
    gate_type: GateType = Field(..., alias="gateType")
    config: GateConfig = Field(default_factory=dict)
    enforcement: Enforcement = "blocking"

    model_config = ConfigDict(populate_by_name=True)


class PromotionGateResponse(BaseModel):
    id: UUID
    scope: str
    team_id: UUID | None = Field(None, alias="teamId")
    application_id: UUID | None = Field(None, alias="applicationId")
    tier: str
    gate_type: str = Field(..., alias="gateType")
    config: GateConfig | None = None
    enforcement: str
    created_by: str = Field(..., alias="createdBy")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, by_alias=True)


class PromotionGateListResponse(BaseModel):
    items: list[PromotionGateResponse]
    total: int


class PromotionRequestCreate(BaseModel):
    target_tier: Tier = Field(..., alias="targetTier")
    image_tag: str | None = Field(None, alias="imageTag")
    chart_version: str | None = Field(None, alias="chartVersion")
    git_sha: str | None = Field(None, alias="gitSha")
    value_overrides: dict[str, Any] | None = Field(None, alias="valueOverrides")
    strategy: Strategy | None = None
    canary_steps: list[dict[str, Any]] | None = Field(None, alias="canarySteps")
    notes: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class PromotionRequestResponse(BaseModel):
    id: UUID
    application_id: UUID = Field(..., alias="applicationId")
    from_tier: str | None = Field(None, alias="fromTier")
    target_tier: str = Field(..., alias="targetTier")
    from_deployment_id: UUID | None = Field(None, alias="fromDeploymentId")
    image_tag: str | None = Field(None, alias="imageTag")
    chart_version: str | None = Field(None, alias="chartVersion")
    git_sha: str | None = Field(None, alias="gitSha")
    value_overrides: dict[str, Any] | None = Field(None, alias="valueOverrides")
    strategy: str | None = None
    canary_steps: list[dict[str, Any]] | None = Field(None, alias="canarySteps")
    status: PromotionStatus
    notes: str | None = None
    requested_by: str = Field(..., alias="requestedBy")
    requested_at: datetime = Field(..., alias="requestedAt")
    approver_email: str | None = Field(None, alias="approverEmail")
    approved_at: datetime | None = Field(None, alias="approvedAt")
    rejection_reason: str | None = Field(None, alias="rejectionReason")
    force_reason: str | None = Field(None, alias="forceReason")
    forced_by: str | None = Field(None, alias="forcedBy")
    executed_at: datetime | None = Field(None, alias="executedAt")
    completed_at: datetime | None = Field(None, alias="completedAt")
    rollback_revision: str | None = Field(None, alias="rollbackRevision")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, by_alias=True)


class GateResultResponse(BaseModel):
    id: int
    gate_type: str = Field(..., alias="gateType")
    passed: bool
    message: str | None = None
    details: dict[str, Any] | None = None
    evaluated_at: datetime = Field(..., alias="evaluatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, by_alias=True)


class FromDeploymentSummary(BaseModel):
    id: UUID
    tier: str
    image_tag: str | None = Field(None, alias="imageTag")
    chart_version: str | None = Field(None, alias="chartVersion")
    git_sha: str | None = Field(None, alias="gitSha")
    health_status: str | None = Field(None, alias="healthStatus")
    sync_status: str | None = Field(None, alias="syncStatus")
    deployed_at: datetime | None = Field(None, alias="deployedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, by_alias=True)


class PromotionRequestDetailResponse(PromotionRequestResponse):
    gate_results: list[GateResultResponse] = Field(default_factory=list, alias="gateResults")
    from_deployment: FromDeploymentSummary | None = Field(None, alias="fromDeployment")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, by_alias=True)


class PromotionRequestListResponse(BaseModel):
    items: list[PromotionRequestResponse]
    total: int
    filters: dict[str, Any] = Field(default_factory=dict)


class PromotionApproveRequest(BaseModel):
    notes: str | None = None


class PromotionRejectRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class PromotionForceRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class PromotionRollbackRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class RolloutStatusResponse(BaseModel):
    app_name: str = Field(..., alias="appName")
    namespace: str
    strategy: str
    phase: RolloutPhase
    current_step_index: int | None = Field(None, alias="currentStepIndex")
    total_steps: int | None = Field(None, alias="totalSteps")
    stable_revision: str = Field(..., alias="stableRevision")
    canary_revision: str | None = Field(None, alias="canaryRevision")
    active_service: str | None = Field(None, alias="activeService")
    preview_service: str | None = Field(None, alias="previewService")
    message: str

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, by_alias=True)


class RolloutActionResponse(BaseModel):
    success: bool
    message: str

    model_config = ConfigDict(populate_by_name=True, by_alias=True)
