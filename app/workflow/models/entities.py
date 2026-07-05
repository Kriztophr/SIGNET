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
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.platform.db.base import Base, TenantScopedMixin, TimestampedMixin, UuidPkMixin


class TemplateStatus(enum.StrEnum):
    draft = "draft"
    active = "active"
    archived = "archived"


class ExecutionMode(enum.StrEnum):
    manual = "manual"
    # Reserved extension point: Celery/LLM-driven execution lands behind this value.
    automated = "automated"


class WorkflowRunStatus(enum.StrEnum):
    pending = "pending"
    running = "running"
    paused_for_review = "paused_for_review"
    paused_for_eval = "paused_for_eval"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class StageRunStatus(enum.StrEnum):
    pending = "pending"
    ready = "ready"
    running = "running"
    awaiting_review = "awaiting_review"
    awaiting_eval = "awaiting_eval"
    approved = "approved"
    failed = "failed"
    completed = "completed"


class ActorType(enum.StrEnum):
    human = "human"
    system = "system"
    agent = "agent"


class WorkflowTemplate(UuidPkMixin, TimestampedMixin, TenantScopedMixin, Base):
    __tablename__ = "workflow_templates"
    __table_args__ = (UniqueConstraint("tenant_id", "slug"),)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[TemplateStatus] = mapped_column(
        Enum(TemplateStatus, native_enum=False, length=20),
        default=TemplateStatus.draft,
        nullable=False,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    versions: Mapped[list["WorkflowTemplateVersion"]] = relationship(
        back_populates="template", order_by="WorkflowTemplateVersion.version_number"
    )


class WorkflowTemplateVersion(UuidPkMixin, TimestampedMixin, Base):
    __tablename__ = "workflow_template_versions"
    __table_args__ = (UniqueConstraint("workflow_template_id", "version_number"),)

    workflow_template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_templates.id"), index=True, nullable=False
    )
    environment_template_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    workspace_blueprint_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    template: Mapped[WorkflowTemplate] = relationship(back_populates="versions")
    stages: Mapped[list["StageDefinition"]] = relationship(
        back_populates="version", order_by="StageDefinition.order_index"
    )


class StageDefinition(UuidPkMixin, TimestampedMixin, Base):
    __tablename__ = "stage_definitions"
    __table_args__ = (
        UniqueConstraint("workflow_template_version_id", "stage_key"),
        UniqueConstraint("workflow_template_version_id", "order_index"),
    )

    workflow_template_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_template_versions.id"), index=True, nullable=False
    )
    stage_key: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    execution_mode: Mapped[ExecutionMode] = mapped_column(
        Enum(ExecutionMode, native_enum=False, length=20),
        default=ExecutionMode.manual,
        nullable=False,
    )
    review_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    eval_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    contract_source_ref: Mapped[str] = mapped_column(String(500), nullable=False)

    version: Mapped[WorkflowTemplateVersion] = relationship(back_populates="stages")
    contract: Mapped["StageContract"] = relationship(back_populates="stage_definition")


class StageContract(UuidPkMixin, TimestampedMixin, Base):
    __tablename__ = "stage_contracts"

    stage_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stage_definitions.id"), unique=True, nullable=False
    )
    source_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_contract_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False)

    stage_definition: Mapped[StageDefinition] = relationship(back_populates="contract")


class WorkflowRun(UuidPkMixin, TimestampedMixin, TenantScopedMixin, Base):
    __tablename__ = "workflow_runs"

    workflow_template_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_template_versions.id"), index=True, nullable=False
    )
    environment_template_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    status: Mapped[WorkflowRunStatus] = mapped_column(
        Enum(WorkflowRunStatus, native_enum=False, length=30),
        default=WorkflowRunStatus.pending,
        nullable=False,
    )
    current_stage_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    version: Mapped[WorkflowTemplateVersion] = relationship()
    stage_runs: Mapped[list["StageRun"]] = relationship(
        back_populates="run", order_by="StageRun.created_at"
    )


class StageRun(UuidPkMixin, TimestampedMixin, Base):
    __tablename__ = "stage_runs"

    workflow_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_runs.id"), index=True, nullable=False
    )
    stage_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stage_definitions.id"), nullable=False
    )
    status: Mapped[StageRunStatus] = mapped_column(
        Enum(StageRunStatus, native_enum=False, length=30),
        default=StageRunStatus.pending,
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_gate_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped[WorkflowRun] = relationship(back_populates="stage_runs")
    stage_definition: Mapped[StageDefinition] = relationship()
    context_manifest: Mapped["ContextManifest | None"] = relationship(back_populates="stage_run")


class Artifact(UuidPkMixin, TimestampedMixin, Base):
    __tablename__ = "artifacts"
    __table_args__ = (UniqueConstraint("stage_run_id", "artifact_role", "version_number"),)

    workflow_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_runs.id"), index=True, nullable=False
    )
    stage_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stage_runs.id"), index=True, nullable=False
    )
    artifact_role: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), default="text/markdown", nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    is_human_edited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_artifact_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_by_type: Mapped[ActorType] = mapped_column(
        Enum(ActorType, native_enum=False, length=20), nullable=False
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class ContextManifest(UuidPkMixin, TimestampedMixin, Base):
    """ICM layer mapping for one stage run (spec 10.2):
    layer 0 = workspace identity, layer 1 = routing, layer 2 = stage contract,
    layer 3 = stable references, layer 4 = working artifacts handed off."""

    __tablename__ = "context_manifests"

    stage_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stage_runs.id"), unique=True, nullable=False
    )
    layer0_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    layer1_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    layer2_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    layer3_inputs_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    layer4_inputs_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    stage_run: Mapped[StageRun] = relationship(back_populates="context_manifest")


class ExecutionSnapshot(UuidPkMixin, TimestampedMixin, Base):
    __tablename__ = "execution_snapshots"

    stage_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stage_runs.id"), index=True, nullable=False
    )
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
