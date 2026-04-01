from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TemplateCreate(BaseModel):
    name: str
    description: str | None = None
    category: str | None = None
    chart_repo: str | None = Field(None, alias="chartRepo")
    chart_name: str | None = Field(None, alias="chartName")
    chart_version: str | None = Field(None, alias="chartVersion")
    default_values: dict | None = Field(None, alias="defaultValues")
    values_schema: dict | None = Field(None, alias="valuesSchema")
    model_config = ConfigDict(populate_by_name=True)


class TemplateResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    category: str | None = None
    chart_repo: str | None = Field(None, alias="chartRepo")
    chart_name: str | None = Field(None, alias="chartName")
    chart_version: str | None = Field(None, alias="chartVersion")
    default_values: dict | None = Field(None, alias="defaultValues")
    values_schema: dict | None = Field(None, alias="valuesSchema")
    created_at: datetime = Field(..., alias="createdAt")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, by_alias=True)


class DeployRequest(BaseModel):
    template_id: UUID = Field(..., alias="templateId")
    app_name: str = Field(..., alias="appName")
    values: dict | None = None
    model_config = ConfigDict(populate_by_name=True)


class DeployResponse(BaseModel):
    message: str
    application_name: str = Field(..., alias="applicationName")
    namespace: str
    template_name: str = Field(..., alias="templateName")
    model_config = ConfigDict(populate_by_name=True, by_alias=True)
