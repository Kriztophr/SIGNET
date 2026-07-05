import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.workflow.models.entities import (
    ActorType,
    ExecutionMode,
    StageRunStatus,
    TemplateStatus,
    WorkflowRunStatus,
)


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
    status: TemplateStatus
    created_at: datetime


class StageDefinitionCreate(BaseModel):
    stage_key: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$", max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    order_index: int = Field(ge=0)
    execution_mode: ExecutionMode = ExecutionMode.manual
    review_required: bool = False
    eval_required: bool = False
    contract_markdown: str = Field(min_length=1)


class VersionCreate(BaseModel):
    stages: list[StageDefinitionCreate] = Field(min_length=1)
    environment_template_version_id: uuid.UUID | None = None


class StageDefinitionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    stage_key: str
    display_name: str
    order_index: int
    execution_mode: ExecutionMode
    review_required: bool
    eval_required: bool
    contract_source_ref: str


class VersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_template_id: uuid.UUID
    version_number: int
    environment_template_version_id: uuid.UUID | None
    published_at: datetime | None
    stages: list[StageDefinitionOut]


class ContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stage_definition_id: uuid.UUID
    source_markdown: str
    parsed_contract_json: dict
    schema_version: str


class RunCreate(BaseModel):
    workflow_template_version_id: uuid.UUID
    project_id: uuid.UUID | None = None


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    project_id: uuid.UUID | None
    workflow_template_version_id: uuid.UUID
    status: WorkflowRunStatus
    current_stage_run_id: uuid.UUID | None
    triggered_by: uuid.UUID | None
    started_at: datetime | None
    completed_at: datetime | None
    correlation_id: str | None


class StageRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_run_id: uuid.UUID
    stage_definition_id: uuid.UUID
    status: StageRunStatus
    attempt_number: int
    started_at: datetime | None
    completed_at: datetime | None
    error_summary: str | None


class ContextManifestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    stage_run_id: uuid.UUID
    layer0_ref: str
    layer1_ref: str
    layer2_ref: str
    layer3_inputs_json: list
    layer4_inputs_json: list
    token_estimate: int


class ArtifactSubmit(BaseModel):
    artifact_role: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]*$", max_length=100)
    content: str
    content_type: str = "text/markdown"


class ArtifactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_run_id: uuid.UUID
    stage_run_id: uuid.UUID
    artifact_role: str
    content_type: str
    version_number: int
    is_human_edited: bool
    source_artifact_id: uuid.UUID | None
    created_by_type: ActorType
    created_by_id: uuid.UUID | None
    created_at: datetime


class StageFailRequest(BaseModel):
    error_summary: str = Field(min_length=1)
