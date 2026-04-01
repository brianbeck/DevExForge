from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TeamCreate(BaseModel):
    display_name: str = Field(..., alias="displayName", min_length=1, max_length=256)
    description: str | None = None
    cost_center: str | None = Field(None, alias="costCenter")
    tags: dict[str, str] | None = None

    model_config = ConfigDict(populate_by_name=True)


class TeamUpdate(BaseModel):
    display_name: str | None = Field(None, alias="displayName", max_length=256)
    description: str | None = None
    cost_center: str | None = Field(None, alias="costCenter")
    tags: dict[str, str] | None = None

    model_config = ConfigDict(populate_by_name=True)


class TeamResponse(BaseModel):
    id: UUID
    slug: str
    display_name: str = Field(..., alias="displayName")
    description: str | None = None
    cost_center: str | None = Field(None, alias="costCenter")
    tags: dict[str, str] | None = None
    owner_email: str = Field(..., alias="ownerEmail")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")
    member_count: int = Field(0, alias="memberCount")
    environment_count: int = Field(0, alias="environmentCount")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, by_alias=True)


class TeamListResponse(BaseModel):
    teams: list[TeamResponse]
    total: int


class MemberCreate(BaseModel):
    email: str
    role: Literal["admin", "developer", "viewer"]


class MemberUpdate(BaseModel):
    role: Literal["admin", "developer", "viewer"]


class MemberResponse(BaseModel):
    email: str
    keycloak_id: str | None = Field(None, alias="keycloakId")
    role: str
    added_at: datetime = Field(..., alias="addedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, by_alias=True)
