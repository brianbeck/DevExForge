from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ResourceQuotaSpec(BaseModel):
    cpu_request: str | None = Field("500m", alias="cpuRequest")
    cpu_limit: str | None = Field("2", alias="cpuLimit")
    memory_request: str | None = Field("512Mi", alias="memoryRequest")
    memory_limit: str | None = Field("2Gi", alias="memoryLimit")
    pods: int | None = 20
    services: int | None = 10
    persistent_volume_claims: int | None = Field(5, alias="persistentVolumeClaims")

    model_config = ConfigDict(populate_by_name=True, by_alias=True)


class LimitRangeSpec(BaseModel):
    default_cpu_request: str | None = Field("100m", alias="defaultCpuRequest")
    default_cpu_limit: str | None = Field("500m", alias="defaultCpuLimit")
    default_memory_request: str | None = Field("128Mi", alias="defaultMemoryRequest")
    default_memory_limit: str | None = Field("512Mi", alias="defaultMemoryLimit")

    model_config = ConfigDict(populate_by_name=True, by_alias=True)


class NetworkPolicySpec(BaseModel):
    allow_inter_namespace: bool = Field(False, alias="allowInterNamespace")
    allowed_namespaces: list[str] = Field(default_factory=list, alias="allowedNamespaces")
    egress_allow_internet: bool = Field(True, alias="egressAllowInternet")

    model_config = ConfigDict(populate_by_name=True, by_alias=True)


class ExemptionsSpec(BaseModel):
    exempt_images: list[str] = Field(default_factory=list, alias="exemptImages")
    exempt_namespaces: list[str] = Field(default_factory=list, alias="exemptNamespaces")
    model_config = ConfigDict(populate_by_name=True, by_alias=True)


class PoliciesSpec(BaseModel):
    max_critical_cves: int = Field(0, alias="maxCriticalCVEs")
    max_high_cves: int = Field(5, alias="maxHighCVEs")
    require_non_root: bool = Field(True, alias="requireNonRoot")
    require_read_only_root: bool = Field(False, alias="requireReadOnlyRoot")
    require_resource_limits: bool = Field(True, alias="requireResourceLimits")
    exemptions: ExemptionsSpec | None = None

    model_config = ConfigDict(populate_by_name=True, by_alias=True)


class ArgoCDSpec(BaseModel):
    enabled: bool = True
    source_repos: list[str] = Field(default_factory=list, alias="sourceRepos")
    allowed_cluster_resources: list[dict] = Field(default_factory=list, alias="allowedClusterResources")

    model_config = ConfigDict(populate_by_name=True, by_alias=True)


class EnvironmentCreate(BaseModel):
    tier: Literal["dev", "staging", "production"]
    resource_quota: ResourceQuotaSpec | None = Field(None, alias="resourceQuota")
    limit_range: LimitRangeSpec | None = Field(None, alias="limitRange")
    network_policy: NetworkPolicySpec | None = Field(None, alias="networkPolicy")
    policies: PoliciesSpec | None = None
    argocd: ArgoCDSpec | None = Field(None, alias="argoCD")

    model_config = ConfigDict(populate_by_name=True)


class EnvironmentUpdate(BaseModel):
    resource_quota: ResourceQuotaSpec | None = Field(None, alias="resourceQuota")
    limit_range: LimitRangeSpec | None = Field(None, alias="limitRange")
    network_policy: NetworkPolicySpec | None = Field(None, alias="networkPolicy")
    policies: PoliciesSpec | None = None
    argocd: ArgoCDSpec | None = Field(None, alias="argoCD")

    model_config = ConfigDict(populate_by_name=True)


class PromoteRequest(BaseModel):
    target_tier: Literal["staging", "production"] = Field(..., alias="targetTier")
    value_overrides: dict | None = Field(None, alias="valueOverrides")
    model_config = ConfigDict(populate_by_name=True)


class PromoteResponse(BaseModel):
    message: str
    source_tier: str = Field(..., alias="sourceTier")
    target_tier: str = Field(..., alias="targetTier")
    application_name: str = Field(..., alias="applicationName")
    target_cluster: str = Field(..., alias="targetCluster")
    target_namespace: str = Field(..., alias="targetNamespace")
    model_config = ConfigDict(populate_by_name=True, by_alias=True)


class EnvironmentResponse(BaseModel):
    id: UUID
    team_slug: str = Field(..., alias="teamSlug")
    tier: str
    namespace_name: str = Field(..., alias="namespaceName")
    cluster: str | None = None
    phase: str
    resource_quota: ResourceQuotaSpec | None = Field(None, alias="resourceQuota")
    limit_range: LimitRangeSpec | None = Field(None, alias="limitRange")
    network_policy: NetworkPolicySpec | None = Field(None, alias="networkPolicy")
    policies: PoliciesSpec | None = None
    argocd: ArgoCDSpec | None = Field(None, alias="argoCD")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, by_alias=True)
