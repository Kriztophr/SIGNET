import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.environment.models.entities import EnvironmentTemplateStatus, PromotionStatus


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$", max_length=120)
    description: str = ""
    project_id: uuid.UUID | None = None


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    project_id: uuid.UUID | None
    name: str
    slug: str
    description: str
    status: EnvironmentTemplateStatus
    created_at: datetime


class PromptProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    instructions: dict = Field(default_factory=dict)
    style_ref: str | None = None


class ToolProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    allowed_tools: list = Field(default_factory=list)
    adapter_settings: dict = Field(default_factory=dict)


class PolicyProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    default_gate_settings: dict = Field(default_factory=dict)
    default_policy_refs: list = Field(default_factory=list)


class DomainSchemaIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    schema_definition: dict = Field(alias="schema")

    model_config = ConfigDict(populate_by_name=True)


class VersionCreate(BaseModel):
    prompt_profiles: list[PromptProfileIn] = Field(default_factory=list)
    tool_profiles: list[ToolProfileIn] = Field(default_factory=list)
    policy_profiles: list[PolicyProfileIn] = Field(default_factory=list)
    domain_schemas: list[DomainSchemaIn] = Field(default_factory=list)
    workspace_blueprint_ref: str | None = None


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class VersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    environment_template_id: uuid.UUID
    version_number: int
    workspace_blueprint_ref: str | None
    published_at: datetime | None
    prompt_profiles: list[ProfileOut]
    tool_profiles: list[ProfileOut]
    policy_profiles: list[ProfileOut]


class ReferenceBundleCreate(BaseModel):
    environment_template_version_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    bundle_type: str = Field(min_length=1, max_length=50)
    content: str
    manifest: dict = Field(default_factory=dict)


class ReferenceBundleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    environment_template_version_id: uuid.UUID
    name: str
    bundle_type: str
    storage_uri: str
    manifest_json: dict
    created_at: datetime


class WorkspaceBlueprintCreate(BaseModel):
    environment_template_version_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    blueprint: dict


class WorkspaceBlueprintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    environment_template_version_id: uuid.UUID
    name: str
    blueprint_json: dict
    created_at: datetime


class PromotionCreate(BaseModel):
    environment_template_version_id: uuid.UUID
    requirements: dict = Field(default_factory=dict)
    project_id: uuid.UUID | None = None


class PromotionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    environment_template_version_id: uuid.UUID
    status: PromotionStatus
    requested_by: uuid.UUID | None
    requested_at: datetime | None
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    requirements_json: dict
    evidence_json: dict
    decision_reason: str | None
