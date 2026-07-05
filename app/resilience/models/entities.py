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


class SubjectType(enum.StrEnum):
    person = "person"
    team = "team"
    environment = "environment"


class CapacityDimension(enum.StrEnum):
    """Spec 15.2 core concepts measured per subject."""

    verification = "verification"
    override = "override"
    reconstruction = "reconstruction"


class CapabilityStatus(enum.StrEnum):
    unassessed = "unassessed"
    qualified = "qualified"
    not_qualified = "not_qualified"


class HumanCapacityRunStatus(enum.StrEnum):
    awaiting_scores = "awaiting_scores"
    completed = "completed"
    failed = "failed"


class AiMode(enum.StrEnum):
    off = "off"
    reduced = "reduced"
    delayed = "delayed"


class DrillStatus(enum.StrEnum):
    running = "running"
    completed = "completed"
    failed = "failed"


class CoverageStatus(enum.StrEnum):
    adequate = "adequate"
    shortfall = "shortfall"


class ResilienceDecisionOutcome(enum.StrEnum):
    passed = "pass"
    breach = "breach"


class CriticalCapability(UuidPkMixin, TimestampedMixin, TenantScopedMixin, Base):
    __tablename__ = "critical_capabilities"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    domain: Mapped[str] = mapped_column(String(100), nullable=False)
    criticality_level: Mapped[str] = mapped_column(String(20), default="high", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    minimum_required_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    profiles: Mapped[list["CapabilityProfile"]] = relationship(back_populates="capability")


class CapabilityProfile(UuidPkMixin, TimestampedMixin, Base):
    __tablename__ = "capability_profiles"
    __table_args__ = (UniqueConstraint("critical_capability_id", "subject_type", "subject_ref_id"),)

    critical_capability_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("critical_capabilities.id"), index=True, nullable=False
    )
    subject_type: Mapped[SubjectType] = mapped_column(
        Enum(SubjectType, native_enum=False, length=20), nullable=False
    )
    subject_ref_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    current_status: Mapped[CapabilityStatus] = mapped_column(
        Enum(CapabilityStatus, native_enum=False, length=20),
        default=CapabilityStatus.unassessed,
        nullable=False,
    )
    last_assessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    capability: Mapped[CriticalCapability] = relationship(back_populates="profiles")


class CapabilityRubric(UuidPkMixin, TimestampedMixin, TenantScopedMixin, Base):
    __tablename__ = "capability_rubrics"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # {dimension: minimum score in [0, 1]} — must cover a suite's required dimensions.
    thresholds_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class HumanCapacityEvalSuite(UuidPkMixin, TimestampedMixin, TenantScopedMixin, Base):
    __tablename__ = "human_capacity_eval_suites"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    critical_capability_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("critical_capabilities.id"), nullable=False
    )
    capability_rubric_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("capability_rubrics.id"), nullable=False
    )
    config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    cases: Mapped[list["HumanCapacityEvalCase"]] = relationship(
        back_populates="suite", order_by="HumanCapacityEvalCase.order_index"
    )
    rubric: Mapped[CapabilityRubric] = relationship()
    capability: Mapped[CriticalCapability] = relationship()


class HumanCapacityEvalCase(UuidPkMixin, TimestampedMixin, Base):
    __tablename__ = "human_capacity_eval_cases"

    human_capacity_eval_suite_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("human_capacity_eval_suites.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    dimension: Mapped[CapacityDimension] = mapped_column(
        Enum(CapacityDimension, native_enum=False, length=20), nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    suite: Mapped[HumanCapacityEvalSuite] = relationship(back_populates="cases")


class HumanCapacityRun(UuidPkMixin, TimestampedMixin, TenantScopedMixin, Base):
    __tablename__ = "human_capacity_runs"

    human_capacity_eval_suite_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("human_capacity_eval_suites.id"), index=True, nullable=False
    )
    subject_type: Mapped[SubjectType] = mapped_column(
        Enum(SubjectType, native_enum=False, length=20), nullable=False
    )
    subject_ref_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    workflow_template_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    environment_template_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    status: Mapped[HumanCapacityRunStatus] = mapped_column(
        Enum(HumanCapacityRunStatus, native_enum=False, length=30),
        default=HumanCapacityRunStatus.awaiting_scores,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    qualified: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    suite: Mapped[HumanCapacityEvalSuite] = relationship()
    scores: Mapped[list["CapacityDimensionScore"]] = relationship(back_populates="run")


class CapacityDimensionScore(UuidPkMixin, TimestampedMixin, Base):
    """Spec 15.3 VerificationScore / OverrideScore / ReconstructionScore, folded
    into one table keyed by dimension (identical shape, unique per run+dimension)."""

    __tablename__ = "capacity_dimension_scores"
    __table_args__ = (UniqueConstraint("human_capacity_run_id", "dimension"),)

    human_capacity_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("human_capacity_runs.id"), index=True, nullable=False
    )
    dimension: Mapped[CapacityDimension] = mapped_column(
        Enum(CapacityDimension, native_enum=False, length=20), nullable=False
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    assessed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    run: Mapped[HumanCapacityRun] = relationship(back_populates="scores")


class ReviewerCompetencyRecord(UuidPkMixin, TimestampedMixin, TenantScopedMixin, Base):
    __tablename__ = "reviewer_competency_records"

    reviewer_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    critical_capability_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("critical_capabilities.id"), nullable=False
    )
    human_capacity_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("human_capacity_runs.id"), nullable=False
    )
    status: Mapped[CapabilityStatus] = mapped_column(
        Enum(CapabilityStatus, native_enum=False, length=20), nullable=False
    )


class FallbackDrill(UuidPkMixin, TimestampedMixin, TenantScopedMixin, Base):
    __tablename__ = "fallback_drills"

    environment_template_version_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    workflow_template_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    drill_type: Mapped[str] = mapped_column(String(100), nullable=False)
    ai_mode: Mapped[AiMode] = mapped_column(
        Enum(AiMode, native_enum=False, length=20), nullable=False
    )
    status: Mapped[DrillStatus] = mapped_column(
        Enum(DrillStatus, native_enum=False, length=20),
        default=DrillStatus.running,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class FallbackReadinessAssessment(UuidPkMixin, TimestampedMixin, TenantScopedMixin, Base):
    __tablename__ = "fallback_readiness_assessments"

    fallback_drill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fallback_drills.id"), index=True, nullable=False
    )
    readiness_score: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReversibilityAssessment(UuidPkMixin, TimestampedMixin, TenantScopedMixin, Base):
    __tablename__ = "reversibility_assessments"

    scope_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    assessment_score: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StrategicCoverageSnapshot(UuidPkMixin, TimestampedMixin, TenantScopedMixin, Base):
    __tablename__ = "strategic_coverage_snapshots"

    critical_capability_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("critical_capabilities.id"), index=True, nullable=False
    )
    qualified_subject_count: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_required_count: Mapped[int] = mapped_column(Integer, nullable=False)
    coverage_status: Mapped[CoverageStatus] = mapped_column(
        Enum(CoverageStatus, native_enum=False, length=20), nullable=False
    )
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ResilienceThreshold(UuidPkMixin, TimestampedMixin, TenantScopedMixin, Base):
    __tablename__ = "resilience_thresholds"

    scope_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    min_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    policy_action: Mapped[str] = mapped_column(String(50), default="block", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ResilienceDecision(UuidPkMixin, TimestampedMixin, TenantScopedMixin, Base):
    __tablename__ = "resilience_decisions"

    resilience_threshold_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("resilience_thresholds.id"), nullable=True
    )
    scope_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    decision: Mapped[ResilienceDecisionOutcome] = mapped_column(
        Enum(ResilienceDecisionOutcome, native_enum=False, length=10), nullable=False
    )
    observed_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
