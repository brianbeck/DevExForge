from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class QuotaPresetCreate(BaseModel):
    name: str
    cpu_request: str = Field("2", alias="cpuRequest")
    cpu_limit: str = Field("4", alias="cpuLimit")
    memory_request: str = Field("4Gi", alias="memoryRequest")
    memory_limit: str = Field("8Gi", alias="memoryLimit")
    pods: int = 20
    services: int = 10
    pvcs: int = 5
    model_config = ConfigDict(populate_by_name=True)


class QuotaPresetResponse(BaseModel):
    id: UUID
    name: str
    cpu_request: str = Field(..., alias="cpuRequest")
    cpu_limit: str = Field(..., alias="cpuLimit")
    memory_request: str = Field(..., alias="memoryRequest")
    memory_limit: str = Field(..., alias="memoryLimit")
    pods: int
    services: int
    pvcs: int
    created_at: datetime = Field(..., alias="createdAt")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, by_alias=True)


class PolicyProfileCreate(BaseModel):
    name: str
    max_critical_cves: int = Field(0, alias="maxCriticalCVEs")
    max_high_cves: int = Field(5, alias="maxHighCVEs")
    require_non_root: bool = Field(True, alias="requireNonRoot")
    require_read_only_root: bool = Field(False, alias="requireReadOnlyRoot")
    require_resource_limits: bool = Field(True, alias="requireResourceLimits")
    model_config = ConfigDict(populate_by_name=True)


class PolicyProfileResponse(BaseModel):
    id: UUID
    name: str
    max_critical_cves: int = Field(..., alias="maxCriticalCVEs")
    max_high_cves: int = Field(..., alias="maxHighCVEs")
    require_non_root: bool = Field(..., alias="requireNonRoot")
    require_read_only_root: bool = Field(..., alias="requireReadOnlyRoot")
    require_resource_limits: bool = Field(..., alias="requireResourceLimits")
    created_at: datetime = Field(..., alias="createdAt")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, by_alias=True)


class AdminTeamSummary(BaseModel):
    id: UUID
    slug: str
    display_name: str = Field(..., alias="displayName")
    owner_email: str = Field(..., alias="ownerEmail")
    member_count: int = Field(..., alias="memberCount")
    environment_count: int = Field(..., alias="environmentCount")
    created_at: datetime = Field(..., alias="createdAt")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, by_alias=True)
