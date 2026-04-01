from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AuditLogResponse(BaseModel):
    id: int
    timestamp: datetime
    user_email: str = Field(..., alias="userEmail")
    action: str
    resource_type: str = Field(..., alias="resourceType")
    resource_id: str | None = Field(None, alias="resourceId")
    team_slug: str | None = Field(None, alias="teamSlug")
    request_body: dict | None = Field(None, alias="requestBody")
    response_status: int | None = Field(None, alias="responseStatus")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, by_alias=True)


class AuditLogList(BaseModel):
    entries: list[AuditLogResponse]
    total: int
    limit: int
    offset: int
