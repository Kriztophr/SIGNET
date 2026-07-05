import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.platform.db.base import Base, TenantScopedMixin, TimestampedMixin, UuidPkMixin
from app.workflow.models.entities import ActorType


class ReviewTaskStatus(enum.StrEnum):
    open = "open"
    in_progress = "in_progress"
    approved = "approved"
    edited = "edited"
    rejected = "rejected"
    escalated = "escalated"
    expired = "expired"


class ReviewDecisionType(enum.StrEnum):
    approve = "approve"
    edit = "edit"
    reject = "reject"
    escalate = "escalate"


class PolicyRuleType(enum.StrEnum):
    require_review = "require_review"


class PolicyScopeType(enum.StrEnum):
    tenant = "tenant"
    workflow_template = "workflow_template"
    stage_key = "stage_key"


class PolicyRule(UuidPkMixin, TimestampedMixin, TenantScopedMixin, Base):
    __tablename__ = "policy_rules"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    scope_type: Mapped[PolicyScopeType] = mapped_column(
        Enum(PolicyScopeType, native_enum=False, length=30), nullable=False
    )
    scope_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    rule_type: Mapped[PolicyRuleType] = mapped_column(
        Enum(PolicyRuleType, native_enum=False, length=30), nullable=False
    )
    rule_expression_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class PolicyDecision(UuidPkMixin, TimestampedMixin, Base):
    __tablename__ = "policy_decisions"

    policy_rule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("policy_rules.id"), index=True, nullable=False
    )
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    stage_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    decision_type: Mapped[str] = mapped_column(String(50), nullable=False)
    decision_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    decision_metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ApprovalGate(UuidPkMixin, TimestampedMixin, Base):
    __tablename__ = "approval_gates"

    stage_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stage_definitions.id"), unique=True, nullable=False
    )
    gate_type: Mapped[str] = mapped_column(String(50), default="human_review", nullable=False)
    required_role: Mapped[str] = mapped_column(String(50), default="reviewer", nullable=False)
    sla_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    escalation_rule_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ReviewTask(UuidPkMixin, TimestampedMixin, TenantScopedMixin, Base):
    __tablename__ = "review_tasks"

    workflow_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_runs.id"), index=True, nullable=False
    )
    stage_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stage_runs.id"), index=True, nullable=False
    )
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    approval_gate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("approval_gates.id"), nullable=False
    )
    status: Mapped[ReviewTaskStatus] = mapped_column(
        Enum(ReviewTaskStatus, native_enum=False, length=20),
        default=ReviewTaskStatus.open,
        nullable=False,
        index=True,
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    eligible_role: Mapped[str] = mapped_column(String(50), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    decisions: Mapped[list["ReviewDecision"]] = relationship(back_populates="task")


class ReviewDecision(UuidPkMixin, TimestampedMixin, Base):
    __tablename__ = "review_decisions"

    review_task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("review_tasks.id"), index=True, nullable=False
    )
    decision_type: Mapped[ReviewDecisionType] = mapped_column(
        Enum(ReviewDecisionType, native_enum=False, length=20), nullable=False
    )
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    edited_artifact_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    decided_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    task: Mapped[ReviewTask] = relationship(back_populates="decisions")


class AuditEvent(UuidPkMixin, TenantScopedMixin, Base):
    __tablename__ = "audit_events"

    event_type: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    workflow_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True, nullable=True)
    stage_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    review_task_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    eval_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    environment_promotion_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    actor_type: Mapped[ActorType] = mapped_column(
        Enum(ActorType, native_enum=False, length=20), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
