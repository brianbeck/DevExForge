from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


Strategy = Literal["rolling", "bluegreen", "canary"]
Tier = Literal["dev", "staging", "production"]


class ApplicationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    display_name: str = Field(..., alias="displayName", min_length=1, max_length=256)
    description: str | None = None
    repo_url: str | None = Field(None, alias="repoUrl")
    chart_path: str | None = Field(None, alias="chartPath")
    chart_repo_url: str | None = Field(None, alias="chartRepoUrl")
    image_repo: str | None = Field(None, alias="imageRepo")
    owner_email: str = Field(..., alias="ownerEmail")
    default_strategy: Strategy = Field("rolling", alias="defaultStrategy")
    metadata: dict | None = None

    model_config = ConfigDict(populate_by_name=True)


class ApplicationUpdate(BaseModel):
    display_name: str | None = Field(None, alias="displayName", max_length=256)
    description: str | None = None
    repo_url: str | None = Field(None, alias="repoUrl")
    chart_path: str | None = Field(None, alias="chartPath")
    chart_repo_url: str | None = Field(None, alias="chartRepoUrl")
    image_repo: str | None = Field(None, alias="imageRepo")
    owner_email: str | None = Field(None, alias="ownerEmail")
    default_strategy: Strategy | None = Field(None, alias="defaultStrategy")
    metadata: dict | None = None

    model_config = ConfigDict(populate_by_name=True)


class ApplicationResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    display_name: str = Field(..., alias="displayName")
    description: str | None = None
    repo_url: str | None = Field(None, alias="repoUrl")
    chart_path: str | None = Field(None, alias="chartPath")
    chart_repo_url: str | None = Field(None, alias="chartRepoUrl")
    image_repo: str | None = Field(None, alias="imageRepo")
    owner_email: str = Field(..., alias="ownerEmail")
    default_strategy: str = Field(..., alias="defaultStrategy")
    canary_steps: dict | None = Field(None, alias="canarySteps")
    metadata: dict | None = None
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, by_alias=True)


class ApplicationDeploymentResponse(BaseModel):
    id: UUID
    environment_tier: str = Field(..., alias="environmentTier")
    environment_id: UUID = Field(..., alias="environmentId")
    namespace_name: str = Field(..., alias="namespaceName")
    argocd_app_name: str = Field(..., alias="argocdAppName")
    image_tag: str | None = Field(None, alias="imageTag")
    chart_version: str | None = Field(None, alias="chartVersion")
    git_sha: str | None = Field(None, alias="gitSha")
    health_status: str | None = Field(None, alias="healthStatus")
    sync_status: str | None = Field(None, alias="syncStatus")
    strategy: str
    deployed_at: datetime = Field(..., alias="deployedAt")
    deployed_by: str = Field(..., alias="deployedBy")
    last_synced_at: datetime | None = Field(None, alias="lastSyncedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, by_alias=True)


class ApplicationDetailResponse(ApplicationResponse):
    deployments: list[ApplicationDeploymentResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, by_alias=True)


class ApplicationInventoryCell(BaseModel):
    image_tag: str | None = Field(None, alias="imageTag")
    deployed_at: datetime | None = Field(None, alias="deployedAt")
    deployed_by: str | None = Field(None, alias="deployedBy")
    health_status: str | None = Field(None, alias="healthStatus")
    sync_status: str | None = Field(None, alias="syncStatus")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, by_alias=True)


class ApplicationInventoryRow(BaseModel):
    id: UUID
    name: str
    display_name: str = Field(..., alias="displayName")
    owner_email: str = Field(..., alias="ownerEmail")
    team_slug: str = Field(..., alias="teamSlug")
    deployments: dict[str, ApplicationInventoryCell | None]

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, by_alias=True)


class ApplicationInventoryResponse(BaseModel):
    rows: list[ApplicationInventoryRow]
    total: int


class DeploymentEventResponse(BaseModel):
    id: int
    deployment_id: UUID = Field(..., alias="deploymentId")
    event_type: str = Field(..., alias="eventType")
    from_version: str | None = Field(None, alias="fromVersion")
    to_version: str | None = Field(None, alias="toVersion")
    actor: str
    details: dict | None = None
    occurred_at: datetime = Field(..., alias="occurredAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, by_alias=True)


class DeploymentHistoryResponse(BaseModel):
    events: list[DeploymentEventResponse]
    total: int


class ApplicationDeployRequest(BaseModel):
    tier: Tier
    image_tag: str | None = Field(None, alias="imageTag")
    chart_version: str | None = Field(None, alias="chartVersion")
    git_sha: str | None = Field(None, alias="gitSha")
    value_overrides: dict | None = Field(None, alias="valueOverrides")
    strategy: Strategy | None = None

    model_config = ConfigDict(populate_by_name=True)


class ApplicationDeployResponse(BaseModel):
    deployment_id: UUID = Field(..., alias="deploymentId")
    argocd_app_name: str = Field(..., alias="argocdAppName")
    namespace_name: str = Field(..., alias="namespaceName")
    image_tag: str | None = Field(None, alias="imageTag")
    strategy: str
    message: str

    model_config = ConfigDict(populate_by_name=True, by_alias=True)
