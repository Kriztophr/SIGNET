import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.evals.models.entities import (
    CalibrationRunStatus,
    CalibrationSplit,
    EvalDecisionType,
    EvalRunStatus,
    EvalSuiteType,
    EvalTargetType,
    RegressionPackRunStatus,
)


class EvalCaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    prompt_or_instruction: str = Field(min_length=1)
    expected_shape: dict | None = None
    weight: float = Field(default=1.0, gt=0)
    order_index: int | None = None


class SuiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    target_type: EvalTargetType
    config: dict = Field(default_factory=dict)
    cases: list[EvalCaseCreate] = Field(default_factory=list)
    project_id: uuid.UUID | None = None


class EvalCaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    prompt_or_instruction: str
    weight: float
    order_index: int


class SuiteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    project_id: uuid.UUID | None
    name: str
    target_type: EvalTargetType
    suite_type: EvalSuiteType
    config_json: dict
    cases: list[EvalCaseOut]
    created_at: datetime


class RubricCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    project_id: uuid.UUID | None = None


class RubricVersionCreate(BaseModel):
    criteria: list[dict] = Field(min_length=1)
    score_scale: dict
    pass_threshold: dict


class RubricVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rubric_id: uuid.UUID
    version_number: int
    criteria_json: list
    score_scale_json: dict
    pass_threshold_json: dict
    published_at: datetime | None


class RubricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str
    versions: list[RubricVersionOut]


class EvalRunCreate(BaseModel):
    eval_suite_id: uuid.UUID
    rubric_version_id: uuid.UUID
    target_ref_type: EvalTargetType
    target_ref_id: uuid.UUID
    project_id: uuid.UUID | None = None


class EvalRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    eval_suite_id: uuid.UUID
    rubric_version_id: uuid.UUID
    target_ref_type: EvalTargetType
    target_ref_id: uuid.UUID
    workflow_run_id: uuid.UUID | None
    stage_run_id: uuid.UUID | None
    artifact_id: uuid.UUID | None
    environment_template_version_id: uuid.UUID | None
    status: EvalRunStatus
    started_at: datetime | None
    completed_at: datetime | None
    correlation_id: str | None


class ReviewerScoreCreate(BaseModel):
    eval_run_id: uuid.UUID
    score_json: dict
    rationale: str = Field(min_length=1)
    is_calibration: bool = False


class ReviewerScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    eval_run_id: uuid.UUID
    rubric_version_id: uuid.UUID
    reviewer_id: uuid.UUID
    scored_by_type: str
    score_json: dict
    pass_fail: bool
    rationale: str
    is_calibration: bool
    submitted_at: datetime


class EvalDecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    eval_run_id: uuid.UUID
    decision_type: EvalDecisionType
    decided_by_type: str
    metrics_json: dict
    rationale: str


class EvalResultOut(BaseModel):
    run: EvalRunOut
    decision: EvalDecisionOut | None
    scores: list[ReviewerScoreOut]


class BaselineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    scope_type: str = Field(min_length=1, max_length=50)
    scope_ref: str = Field(min_length=1, max_length=200)
    baseline_data: dict
    project_id: uuid.UUID | None = None


class BaselineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    scope_type: str
    scope_ref: str
    baseline_data_json: dict
    created_at: datetime


class RegressionPackCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    eval_suite_ids: list[uuid.UUID] = Field(min_length=1)
    scope_type: str = Field(min_length=1, max_length=50)
    scope_ref: str = Field(min_length=1, max_length=200)
    project_id: uuid.UUID | None = None


class RegressionPackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str
    eval_suite_refs_json: list
    scope_type: str
    scope_ref: str
    created_at: datetime


class RegressionPackRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    regression_pack_id: uuid.UUID
    status: RegressionPackRunStatus
    results_json: dict
    pass_rate: float
    started_at: datetime | None
    completed_at: datetime | None


class CalibrationExampleCreate(BaseModel):
    rubric_version_id: uuid.UUID
    content: str = Field(min_length=1)
    gold_score_json: dict
    gold_pass_fail: bool
    gold_rationale: str = ""
    group_key: str = Field(min_length=1, max_length=200)
    split: CalibrationSplit | None = None
    test_set_version: int | None = Field(default=None, ge=1)
    project_id: uuid.UUID | None = None


class CalibrationHarvestRequest(BaseModel):
    eval_run_id: uuid.UUID
    split: CalibrationSplit | None = None
    group_key: str | None = Field(default=None, min_length=1, max_length=200)
    test_set_version: int | None = Field(default=None, ge=1)


class CalibrationExampleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    project_id: uuid.UUID | None
    rubric_version_id: uuid.UUID
    content_sha256: str
    gold_score_json: dict
    gold_pass_fail: bool
    gold_rationale: str
    split: CalibrationSplit
    group_key: str
    test_set_version: int | None
    provenance: str
    source_eval_run_id: uuid.UUID | None
    source_artifact_id: uuid.UUID | None
    created_at: datetime


class CalibrationRunCreate(BaseModel):
    rubric_version_id: uuid.UUID
    split: CalibrationSplit
    test_set_version: int | None = Field(default=None, ge=1)
    project_id: uuid.UUID | None = None


class CalibrationRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    rubric_version_id: uuid.UUID
    split: CalibrationSplit
    test_set_version: int | None
    judge_provider: str
    judge_model: str
    judge_config_json: dict
    status: CalibrationRunStatus
    results_json: dict
    metrics_json: dict
    example_count: int
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class CalibrationSuggestionOut(BaseModel):
    eval_run_id: uuid.UUID
    decision: str
    reasons: list[str]


class JudgeMonitoringOut(BaseModel):
    eval_suite_id: uuid.UUID
    judge_model: str
    observed: dict
    calibration: dict | None
    corrected: dict | None


class DriftSignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    scope_type: str
    scope_ref: str
    signal_type: str
    signal_strength: float
    evidence_json: dict
    detected_at: datetime
