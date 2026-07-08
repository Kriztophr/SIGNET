import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.platform.db.base import Base, TenantScopedMixin, TimestampedMixin, UuidPkMixin
from app.workflow.models.entities import ActorType


class EvalTargetType(enum.StrEnum):
    artifact = "artifact"
    stage_run = "stage_run"
    workflow_run = "workflow_run"
    environment_version = "environment_version"


class EvalSuiteType(enum.StrEnum):
    rubric_scored = "rubric_scored"


class EvalRunStatus(enum.StrEnum):
    pending = "pending"
    running = "running"
    awaiting_human_score = "awaiting_human_score"
    completed = "completed"
    failed = "failed"


class EvalDecisionType(enum.StrEnum):
    passed = "pass"
    failed = "fail"
    needs_adjudication = "needs_adjudication"


class RegressionPackRunStatus(enum.StrEnum):
    completed = "completed"
    failed = "failed"


class EvalSuite(UuidPkMixin, TimestampedMixin, TenantScopedMixin, Base):
    __tablename__ = "eval_suites"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    target_type: Mapped[EvalTargetType] = mapped_column(
        Enum(EvalTargetType, native_enum=False, length=30), nullable=False
    )
    suite_type: Mapped[EvalSuiteType] = mapped_column(
        Enum(EvalSuiteType, native_enum=False, length=30),
        default=EvalSuiteType.rubric_scored,
        nullable=False,
    )
    config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    cases: Mapped[list["EvalCase"]] = relationship(
        back_populates="suite", order_by="EvalCase.order_index"
    )


class EvalCase(UuidPkMixin, TimestampedMixin, Base):
    __tablename__ = "eval_cases"

    eval_suite_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("eval_suites.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    prompt_or_instruction: Mapped[str] = mapped_column(Text, nullable=False)
    expected_shape_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    suite: Mapped[EvalSuite] = relationship(back_populates="cases")


class Rubric(UuidPkMixin, TimestampedMixin, TenantScopedMixin, Base):
    __tablename__ = "rubrics"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    versions: Mapped[list["RubricVersion"]] = relationship(
        back_populates="rubric", order_by="RubricVersion.version_number"
    )


class RubricVersion(UuidPkMixin, TimestampedMixin, Base):
    __tablename__ = "rubric_versions"
    __table_args__ = (UniqueConstraint("rubric_id", "version_number"),)

    rubric_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rubrics.id"), index=True, nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    criteria_json: Mapped[list] = mapped_column(JSON, nullable=False)
    score_scale_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    pass_threshold_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rubric: Mapped[Rubric] = relationship(back_populates="versions")


class EvalRun(UuidPkMixin, TimestampedMixin, TenantScopedMixin, Base):
    __tablename__ = "eval_runs"

    eval_suite_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("eval_suites.id"), index=True, nullable=False
    )
    rubric_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rubric_versions.id"), nullable=False
    )
    target_ref_type: Mapped[EvalTargetType] = mapped_column(
        Enum(EvalTargetType, native_enum=False, length=30), nullable=False
    )
    target_ref_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    # Traceability per spec 16.1: derived from the target at run creation.
    workflow_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True, nullable=True)
    stage_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True, nullable=True)
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    environment_template_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    status: Mapped[EvalRunStatus] = mapped_column(
        Enum(EvalRunStatus, native_enum=False, length=30),
        default=EvalRunStatus.pending,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    suite: Mapped[EvalSuite] = relationship()
    rubric_version: Mapped[RubricVersion] = relationship()
    scores: Mapped[list["ReviewerScore"]] = relationship(back_populates="run")
    decision: Mapped["EvalDecision | None"] = relationship(back_populates="run")


class ReviewerScore(UuidPkMixin, TimestampedMixin, Base):
    __tablename__ = "reviewer_scores"
    __table_args__ = (UniqueConstraint("eval_run_id", "reviewer_id"),)

    eval_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("eval_runs.id"), index=True, nullable=False
    )
    rubric_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rubric_versions.id"), nullable=False
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    # Spec §28.8: LLM-judge scores are agent-authored and advisory — they never
    # count toward min_reviewers or vote in the decision.
    scored_by_type: Mapped[ActorType] = mapped_column(
        Enum(ActorType, native_enum=False, length=20),
        default=ActorType.human,
        server_default="human",
        nullable=False,
    )
    score_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    pass_fail: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    is_calibration: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    run: Mapped[EvalRun] = relationship(back_populates="scores")


class EvalDecision(UuidPkMixin, TimestampedMixin, Base):
    __tablename__ = "eval_decisions"

    eval_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("eval_runs.id"), unique=True, nullable=False
    )
    decision_type: Mapped[EvalDecisionType] = mapped_column(
        Enum(EvalDecisionType, native_enum=False, length=30), nullable=False
    )
    decided_by_type: Mapped[ActorType] = mapped_column(
        Enum(ActorType, native_enum=False, length=20),
        default=ActorType.system,
        nullable=False,
    )
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)

    run: Mapped[EvalRun] = relationship(back_populates="decision")


class Baseline(UuidPkMixin, TimestampedMixin, TenantScopedMixin, Base):
    __tablename__ = "baselines"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    baseline_data_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class RegressionPack(UuidPkMixin, TimestampedMixin, TenantScopedMixin, Base):
    __tablename__ = "regression_packs"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    eval_suite_refs_json: Mapped[list] = mapped_column(JSON, nullable=False)
    scope_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_ref: Mapped[str] = mapped_column(String(200), nullable=False)


class RegressionPackRun(UuidPkMixin, TimestampedMixin, Base):
    __tablename__ = "regression_pack_runs"

    regression_pack_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("regression_packs.id"), index=True, nullable=False
    )
    status: Mapped[RegressionPackRunStatus] = mapped_column(
        Enum(RegressionPackRunStatus, native_enum=False, length=20), nullable=False
    )
    results_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    pass_rate: Mapped[float] = mapped_column(Float, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class DriftSignal(UuidPkMixin, TimestampedMixin, TenantScopedMixin, Base):
    __tablename__ = "drift_signals"

    scope_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    signal_strength: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DisagreementRecord(UuidPkMixin, TimestampedMixin, Base):
    __tablename__ = "disagreement_records"

    eval_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("eval_runs.id"), index=True, nullable=False
    )
    reviewer_score_ids_json: Mapped[list] = mapped_column(JSON, nullable=False)
    disagreement_type: Mapped[str] = mapped_column(
        String(50), default="pass_fail_split", nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
