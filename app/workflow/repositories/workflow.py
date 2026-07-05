import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.platform.errors import NotFoundError
from app.workflow.models.entities import (
    Artifact,
    ContextManifest,
    StageRun,
    WorkflowRun,
    WorkflowTemplate,
    WorkflowTemplateVersion,
)


class WorkflowRepository:
    """All queries are tenant-scoped; a miss inside another tenant is a plain miss."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_template(self, tenant_id: uuid.UUID, template_id: uuid.UUID) -> WorkflowTemplate:
        template = self._session.scalar(
            select(WorkflowTemplate).where(
                WorkflowTemplate.id == template_id,
                WorkflowTemplate.tenant_id == tenant_id,
            )
        )
        if template is None:
            raise NotFoundError(f"workflow template {template_id} not found")
        return template

    def list_templates(self, tenant_id: uuid.UUID, limit: int = 100) -> list[WorkflowTemplate]:
        return list(
            self._session.scalars(
                select(WorkflowTemplate)
                .where(WorkflowTemplate.tenant_id == tenant_id)
                .order_by(WorkflowTemplate.created_at.desc())
                .limit(min(limit, 500))
            )
        )

    def list_runs(self, tenant_id: uuid.UUID, limit: int = 100) -> list[WorkflowRun]:
        return list(
            self._session.scalars(
                select(WorkflowRun)
                .where(WorkflowRun.tenant_id == tenant_id)
                .order_by(WorkflowRun.created_at.desc())
                .limit(min(limit, 500))
            )
        )

    def get_template_by_slug(self, tenant_id: uuid.UUID, slug: str) -> WorkflowTemplate | None:
        return self._session.scalar(
            select(WorkflowTemplate).where(
                WorkflowTemplate.slug == slug,
                WorkflowTemplate.tenant_id == tenant_id,
            )
        )

    def list_versions(
        self, tenant_id: uuid.UUID, template_id: uuid.UUID
    ) -> list[WorkflowTemplateVersion]:
        template = self.get_template(tenant_id, template_id)
        return list(
            self._session.scalars(
                select(WorkflowTemplateVersion)
                .where(WorkflowTemplateVersion.workflow_template_id == template.id)
                .options(selectinload(WorkflowTemplateVersion.stages))
                .order_by(WorkflowTemplateVersion.version_number.desc())
            )
        )

    def next_version_number(self, template_id: uuid.UUID) -> int:
        current = self._session.scalar(
            select(func.max(WorkflowTemplateVersion.version_number)).where(
                WorkflowTemplateVersion.workflow_template_id == template_id
            )
        )
        return (current or 0) + 1

    def get_version(self, tenant_id: uuid.UUID, version_id: uuid.UUID) -> WorkflowTemplateVersion:
        version = self._session.scalar(
            select(WorkflowTemplateVersion)
            .join(WorkflowTemplate)
            .where(
                WorkflowTemplateVersion.id == version_id,
                WorkflowTemplate.tenant_id == tenant_id,
            )
            .options(
                selectinload(WorkflowTemplateVersion.stages),
                selectinload(WorkflowTemplateVersion.template),
            )
        )
        if version is None:
            raise NotFoundError(f"workflow template version {version_id} not found")
        return version

    def get_run(self, tenant_id: uuid.UUID, run_id: uuid.UUID) -> WorkflowRun:
        run = self._session.scalar(
            select(WorkflowRun).where(
                WorkflowRun.id == run_id,
                WorkflowRun.tenant_id == tenant_id,
            )
        )
        if run is None:
            raise NotFoundError(f"workflow run {run_id} not found")
        return run

    def get_stage_run(self, tenant_id: uuid.UUID, stage_run_id: uuid.UUID) -> StageRun:
        stage_run = self._session.scalar(
            select(StageRun)
            .join(WorkflowRun)
            .where(
                StageRun.id == stage_run_id,
                WorkflowRun.tenant_id == tenant_id,
            )
            .options(
                selectinload(StageRun.run),
                selectinload(StageRun.stage_definition),
            )
        )
        if stage_run is None:
            raise NotFoundError(f"stage run {stage_run_id} not found")
        return stage_run

    def get_context_manifest(
        self, tenant_id: uuid.UUID, stage_run_id: uuid.UUID
    ) -> ContextManifest:
        stage_run = self.get_stage_run(tenant_id, stage_run_id)
        manifest = self._session.scalar(
            select(ContextManifest).where(ContextManifest.stage_run_id == stage_run.id)
        )
        if manifest is None:
            raise NotFoundError(f"context manifest for stage run {stage_run_id} not found")
        return manifest

    def get_artifact(self, tenant_id: uuid.UUID, artifact_id: uuid.UUID) -> Artifact:
        artifact = self._session.scalar(
            select(Artifact)
            .join(WorkflowRun, Artifact.workflow_run_id == WorkflowRun.id)
            .where(
                Artifact.id == artifact_id,
                WorkflowRun.tenant_id == tenant_id,
            )
        )
        if artifact is None:
            raise NotFoundError(f"artifact {artifact_id} not found")
        return artifact

    def artifacts_for_stage_run(self, stage_run_id: uuid.UUID) -> list[Artifact]:
        return list(
            self._session.scalars(
                select(Artifact)
                .where(Artifact.stage_run_id == stage_run_id)
                .order_by(Artifact.artifact_role, Artifact.version_number)
            )
        )

    def latest_artifacts_by_role(self, stage_run_id: uuid.UUID) -> dict[str, Artifact]:
        latest: dict[str, Artifact] = {}
        for artifact in self.artifacts_for_stage_run(stage_run_id):
            latest[artifact.artifact_role] = artifact  # ordered by version, last wins
        return latest

    def next_artifact_version(self, stage_run_id: uuid.UUID, role: str) -> int:
        current = self._session.scalar(
            select(func.max(Artifact.version_number)).where(
                Artifact.stage_run_id == stage_run_id,
                Artifact.artifact_role == role,
            )
        )
        return (current or 0) + 1

    def stage_runs_for_run(self, run_id: uuid.UUID) -> list[StageRun]:
        return list(
            self._session.scalars(
                select(StageRun)
                .where(StageRun.workflow_run_id == run_id)
                .options(selectinload(StageRun.stage_definition))
                .order_by(StageRun.created_at)
            )
        )
