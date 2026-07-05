import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.environment.models.entities import (
    EnvironmentPromotion,
    EnvironmentTemplate,
    EnvironmentTemplateVersion,
    ReferenceBundle,
    WorkspaceBlueprint,
)
from app.platform.errors import NotFoundError


class EnvironmentRepository:
    """All queries are tenant-scoped, directly or through the owning parent."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_template(self, tenant_id: uuid.UUID, template_id: uuid.UUID) -> EnvironmentTemplate:
        template = self._session.scalar(
            select(EnvironmentTemplate).where(
                EnvironmentTemplate.id == template_id,
                EnvironmentTemplate.tenant_id == tenant_id,
            )
        )
        if template is None:
            raise NotFoundError(f"environment template {template_id} not found")
        return template

    def get_template_by_slug(self, tenant_id: uuid.UUID, slug: str) -> EnvironmentTemplate | None:
        return self._session.scalar(
            select(EnvironmentTemplate).where(
                EnvironmentTemplate.slug == slug,
                EnvironmentTemplate.tenant_id == tenant_id,
            )
        )

    def next_version_number(self, template_id: uuid.UUID) -> int:
        current = self._session.scalar(
            select(func.max(EnvironmentTemplateVersion.version_number)).where(
                EnvironmentTemplateVersion.environment_template_id == template_id
            )
        )
        return (current or 0) + 1

    def get_version(
        self, tenant_id: uuid.UUID, version_id: uuid.UUID
    ) -> EnvironmentTemplateVersion:
        version = self._session.scalar(
            select(EnvironmentTemplateVersion)
            .join(EnvironmentTemplate)
            .where(
                EnvironmentTemplateVersion.id == version_id,
                EnvironmentTemplate.tenant_id == tenant_id,
            )
            .options(
                selectinload(EnvironmentTemplateVersion.reference_bundles),
                selectinload(EnvironmentTemplateVersion.prompt_profiles),
                selectinload(EnvironmentTemplateVersion.tool_profiles),
                selectinload(EnvironmentTemplateVersion.policy_profiles),
            )
        )
        if version is None:
            raise NotFoundError(f"environment template version {version_id} not found")
        return version

    def get_reference_bundle(self, tenant_id: uuid.UUID, bundle_id: uuid.UUID) -> ReferenceBundle:
        bundle = self._session.scalar(
            select(ReferenceBundle)
            .join(EnvironmentTemplateVersion)
            .join(EnvironmentTemplate)
            .where(
                ReferenceBundle.id == bundle_id,
                EnvironmentTemplate.tenant_id == tenant_id,
            )
        )
        if bundle is None:
            raise NotFoundError(f"reference bundle {bundle_id} not found")
        return bundle

    def get_workspace_blueprint(
        self, tenant_id: uuid.UUID, blueprint_id: uuid.UUID
    ) -> WorkspaceBlueprint:
        blueprint = self._session.scalar(
            select(WorkspaceBlueprint)
            .join(EnvironmentTemplateVersion)
            .join(EnvironmentTemplate)
            .where(
                WorkspaceBlueprint.id == blueprint_id,
                EnvironmentTemplate.tenant_id == tenant_id,
            )
        )
        if blueprint is None:
            raise NotFoundError(f"workspace blueprint {blueprint_id} not found")
        return blueprint

    def list_promotions(self, tenant_id: uuid.UUID, limit: int = 100) -> list[EnvironmentPromotion]:
        return list(
            self._session.scalars(
                select(EnvironmentPromotion)
                .where(EnvironmentPromotion.tenant_id == tenant_id)
                .order_by(EnvironmentPromotion.created_at.desc())
                .limit(min(limit, 500))
            )
        )

    def get_promotion(self, tenant_id: uuid.UUID, promotion_id: uuid.UUID) -> EnvironmentPromotion:
        promotion = self._session.scalar(
            select(EnvironmentPromotion).where(
                EnvironmentPromotion.id == promotion_id,
                EnvironmentPromotion.tenant_id == tenant_id,
            )
        )
        if promotion is None:
            raise NotFoundError(f"environment promotion {promotion_id} not found")
        return promotion
