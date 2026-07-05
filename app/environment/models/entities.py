import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
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


class EnvironmentTemplateStatus(enum.StrEnum):
    draft = "draft"
    active = "active"
    archived = "archived"


class PromotionStatus(enum.StrEnum):
    """Spec 17.1 promotion states."""

    draft = "draft"
    under_evaluation = "under_evaluation"
    approval_pending = "approval_pending"
    approved = "approved"
    deprecated = "deprecated"
    blocked = "blocked"


class EnvironmentTemplate(UuidPkMixin, TimestampedMixin, TenantScopedMixin, Base):
    __tablename__ = "environment_templates"
    __table_args__ = (UniqueConstraint("tenant_id", "slug"),)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[EnvironmentTemplateStatus] = mapped_column(
        Enum(EnvironmentTemplateStatus, native_enum=False, length=20),
        default=EnvironmentTemplateStatus.draft,
        nullable=False,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    versions: Mapped[list["EnvironmentTemplateVersion"]] = relationship(
        back_populates="template", order_by="EnvironmentTemplateVersion.version_number"
    )


class EnvironmentTemplateVersion(UuidPkMixin, TimestampedMixin, Base):
    __tablename__ = "environment_template_versions"
    __table_args__ = (UniqueConstraint("environment_template_id", "version_number"),)

    environment_template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("environment_templates.id"), index=True, nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    workspace_blueprint_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    template: Mapped[EnvironmentTemplate] = relationship(back_populates="versions")
    reference_bundles: Mapped[list["ReferenceBundle"]] = relationship(back_populates="version")
    prompt_profiles: Mapped[list["PromptProfile"]] = relationship(back_populates="version")
    tool_profiles: Mapped[list["ToolProfile"]] = relationship(back_populates="version")
    policy_profiles: Mapped[list["PolicyProfile"]] = relationship(back_populates="version")


class ReferenceBundle(UuidPkMixin, TimestampedMixin, Base):
    __tablename__ = "reference_bundles"

    environment_template_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("environment_template_versions.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    bundle_type: Mapped[str] = mapped_column(String(50), nullable=False)
    storage_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    manifest_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    version: Mapped[EnvironmentTemplateVersion] = relationship(back_populates="reference_bundles")


class PromptProfile(UuidPkMixin, TimestampedMixin, Base):
    __tablename__ = "prompt_profiles"

    environment_template_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("environment_template_versions.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    instructions_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    style_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)

    version: Mapped[EnvironmentTemplateVersion] = relationship(back_populates="prompt_profiles")


class ToolProfile(UuidPkMixin, TimestampedMixin, Base):
    __tablename__ = "tool_profiles"

    environment_template_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("environment_template_versions.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    allowed_tools_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    adapter_settings_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    version: Mapped[EnvironmentTemplateVersion] = relationship(back_populates="tool_profiles")


class PolicyProfile(UuidPkMixin, TimestampedMixin, Base):
    __tablename__ = "policy_profiles"

    environment_template_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("environment_template_versions.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    default_gate_settings_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    default_policy_refs_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    version: Mapped[EnvironmentTemplateVersion] = relationship(back_populates="policy_profiles")


class DomainSchema(UuidPkMixin, TimestampedMixin, Base):
    __tablename__ = "domain_schemas"

    environment_template_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("environment_template_versions.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    schema_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class WorkspaceBlueprint(UuidPkMixin, TimestampedMixin, Base):
    __tablename__ = "workspace_blueprints"

    environment_template_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("environment_template_versions.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    blueprint_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class SetupQuestionnaire(UuidPkMixin, TimestampedMixin, TenantScopedMixin, Base):
    __tablename__ = "setup_questionnaires"

    environment_template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("environment_templates.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    questions_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    answers_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class EnvironmentPromotion(UuidPkMixin, TimestampedMixin, TenantScopedMixin, Base):
    __tablename__ = "environment_promotions"

    environment_template_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("environment_template_versions.id"), index=True, nullable=False
    )
    status: Mapped[PromotionStatus] = mapped_column(
        Enum(PromotionStatus, native_enum=False, length=30),
        default=PromotionStatus.draft,
        nullable=False,
    )
    requested_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requirements_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
