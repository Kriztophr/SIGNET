import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.resilience.models.entities import (
    AiMode,
    CapacityDimension,
    CoverageStatus,
    DrillStatus,
    HumanCapacityRunStatus,
    ResilienceDecisionOutcome,
    SubjectType,
)


class CapabilityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    domain: str = Field(min_length=1, max_length=100)
    criticality_level: str = Field(default="high", pattern="^(low|medium|high|critical)$")
    description: str = ""
    minimum_required_count: int = Field(default=1, ge=1)
    project_id: uuid.UUID | None = None


class CapabilityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    domain: str
    criticality_level: str
    description: str
    minimum_required_count: int
    created_at: datetime


class CapacityCaseIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    instruction: str = Field(min_length=1)
    dimension: CapacityDimension
    order_index: int | None = None


class SuiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    critical_capability_id: uuid.UUID
    rubric_name: str = Field(min_length=1, max_length=200)
    rubric_thresholds: dict
    required_dimensions: list[CapacityDimension] | None = None
    cases: list[CapacityCaseIn] = Field(default_factory=list)
    project_id: uuid.UUID | None = None


class SuiteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    critical_capability_id: uuid.UUID
    capability_rubric_id: uuid.UUID
    config_json: dict
    created_at: datetime


class CapacityRunCreate(BaseModel):
    human_capacity_eval_suite_id: uuid.UUID
    subject_type: SubjectType
    subject_ref_id: uuid.UUID
    workflow_template_version_id: uuid.UUID | None = None
    environment_template_version_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None


class CapacityRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    human_capacity_eval_suite_id: uuid.UUID
    subject_type: SubjectType
    subject_ref_id: uuid.UUID
    status: HumanCapacityRunStatus
    qualified: bool | None
    started_at: datetime | None
    completed_at: datetime | None
    correlation_id: str | None


class CapacityScoreCreate(BaseModel):
    human_capacity_run_id: uuid.UUID
    dimension: CapacityDimension
    score: float = Field(ge=0, le=1)
    evidence: dict = Field(default_factory=dict)


class CapacityScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    human_capacity_run_id: uuid.UUID
    dimension: CapacityDimension
    score: float
    evidence_json: dict
    assessed_by: uuid.UUID | None
    created_at: datetime


class DrillCreate(BaseModel):
    environment_template_version_id: uuid.UUID
    drill_type: str = Field(min_length=1, max_length=100)
    ai_mode: AiMode
    workflow_template_version_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None


class DrillCompleteRequest(BaseModel):
    readiness_score: float = Field(ge=0, le=1)
    summary: dict = Field(default_factory=dict)
    evidence: dict = Field(default_factory=dict)


class DrillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    environment_template_version_id: uuid.UUID
    workflow_template_version_id: uuid.UUID | None
    drill_type: str
    ai_mode: AiMode
    status: DrillStatus
    started_at: datetime | None
    completed_at: datetime | None
    summary_json: dict


class ReadinessAssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    fallback_drill_id: uuid.UUID
    readiness_score: float
    evidence_json: dict
    assessed_at: datetime


class ReversibilityCreate(BaseModel):
    scope_type: str = Field(min_length=1, max_length=50)
    scope_ref: str = Field(min_length=1, max_length=200)
    assessment_score: float = Field(ge=0, le=1)
    evidence: dict = Field(default_factory=dict)
    project_id: uuid.UUID | None = None


class ReversibilityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    scope_type: str
    scope_ref: str
    assessment_score: float
    evidence_json: dict
    assessed_at: datetime


class CoverageSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    critical_capability_id: uuid.UUID
    qualified_subject_count: int
    minimum_required_count: int
    coverage_status: CoverageStatus
    captured_at: datetime


class ThresholdCreate(BaseModel):
    scope_type: str = Field(min_length=1, max_length=50)
    scope_ref: str = Field(min_length=1, max_length=200)
    metric_name: str = Field(min_length=1, max_length=100)
    min_threshold: float
    policy_action: str = "block"
    project_id: uuid.UUID | None = None


class ThresholdOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    scope_type: str
    scope_ref: str
    metric_name: str
    min_threshold: float
    policy_action: str
    is_active: bool
    created_at: datetime


class ResilienceDecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    resilience_threshold_id: uuid.UUID | None
    scope_type: str
    scope_ref: str
    metric_name: str
    decision: ResilienceDecisionOutcome
    observed_value: float | None
    evidence_json: dict
    decided_at: datetime
