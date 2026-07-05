import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.governance.models.entities import (
    PolicyRuleType,
    PolicyScopeType,
    ReviewDecisionType,
    ReviewTaskStatus,
)


class PolicyRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    scope_type: PolicyScopeType
    scope_ref: str | None = None
    rule_type: PolicyRuleType
    rule_expression: dict = Field(default_factory=dict)
    severity: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    project_id: uuid.UUID | None = None


class PolicyRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    project_id: uuid.UUID | None
    name: str
    scope_type: PolicyScopeType
    scope_ref: str | None
    rule_type: PolicyRuleType
    rule_expression_json: dict
    severity: str
    is_active: bool
    created_at: datetime


class ReviewTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    workflow_run_id: uuid.UUID
    stage_run_id: uuid.UUID
    artifact_id: uuid.UUID | None
    approval_gate_id: uuid.UUID
    status: ReviewTaskStatus
    assigned_to: uuid.UUID | None
    eligible_role: str
    due_at: datetime | None
    created_at: datetime
    correlation_id: str | None


class ReviewDecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    review_task_id: uuid.UUID
    decision_type: ReviewDecisionType
    rationale: str
    edited_artifact_id: uuid.UUID | None
    decided_by: uuid.UUID
    decided_at: datetime


class DecisionRequest(BaseModel):
    rationale: str = Field(min_length=1)


class EditDecisionRequest(DecisionRequest):
    artifact_role: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]*$", max_length=100)
    content: str
    content_type: str = "text/markdown"


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    project_id: uuid.UUID | None
    event_type: str
    workflow_run_id: uuid.UUID | None
    stage_run_id: uuid.UUID | None
    review_task_id: uuid.UUID | None
    actor_type: str
    actor_id: uuid.UUID | None
    payload_json: dict
    occurred_at: datetime
    correlation_id: str | None
