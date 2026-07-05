import uuid

from sqlalchemy.orm import Session

from app.platform.errors import DomainValidationError, InvalidStateError
from app.platform.events.bus import get_event_bus
from app.platform.storage.service import StorageService
from app.platform.time.clock import utc_now
from app.workflow.models.entities import (
    StageDefinition,
    StageRun,
    StageRunStatus,
    WorkflowRun,
    WorkflowRunStatus,
)
from app.workflow.repositories.workflow import WorkflowRepository
from app.workflow.services.workspace import (
    ContextAssemblyService,
    WorkspaceMaterializationService,
)


class StageExecutionCoordinator:
    """Owns the run/stage state machines and the ICM handoff rule."""

    def __init__(self, session: Session, storage: StorageService) -> None:
        self._session = session
        self._storage = storage
        self._repo = WorkflowRepository(session)
        self._workspace = WorkspaceMaterializationService(storage)
        self._context = ContextAssemblyService(storage)

    def start_stage(
        self, run: WorkflowRun, stage: StageDefinition, layer4_inputs: list[dict]
    ) -> StageRun:
        stage_run = StageRun(
            workflow_run_id=run.id,
            stage_definition_id=stage.id,
            status=StageRunStatus.running,
            attempt_number=1,
            started_at=utc_now(),
        )
        self._session.add(stage_run)
        self._session.flush()

        layer2_key = self._workspace.materialize_stage(run, stage, stage.contract.source_markdown)
        manifest = self._context.build_manifest(
            stage_run, run, layer2_key, layer3_inputs=[], layer4_inputs=layer4_inputs
        )
        self._session.add(manifest)
        run.current_stage_run_id = stage_run.id
        self._session.flush()

        get_event_bus().publish(
            "workflow.stage.started",
            {
                "workflow_run_id": str(run.id),
                "stage_run_id": str(stage_run.id),
                "stage_key": stage.stage_key,
            },
        )
        return stage_run

    def complete_stage(self, stage_run: StageRun) -> WorkflowRun:
        if stage_run.status is not StageRunStatus.running:
            raise InvalidStateError(
                f"only a running stage can be completed (stage run is {stage_run.status})"
            )
        run = stage_run.run
        stage = stage_run.stage_definition
        self._validate_contract_outputs(stage_run, stage)

        # Local imports: workflow and governance call into each other across the
        # review gate, so the dependency is resolved at call time.
        from app.governance.services.policies import PolicyEngine
        from app.governance.services.reviews import ReviewTaskService

        needs_review = stage.review_required or PolicyEngine(self._session).stage_requires_review(
            run, stage_run, stage
        )
        if needs_review:
            stage_run.status = StageRunStatus.awaiting_review
            run.status = WorkflowRunStatus.paused_for_review
            self._session.flush()
            ReviewTaskService(self._session, self._storage).request_review(run, stage_run, stage)
            return run

        return self._finalize_stage(stage_run)

    def resume_approved_stage(self, stage_run: StageRun) -> WorkflowRun:
        """Called by governance once a review resolves in favour of the stage."""
        if stage_run.status is not StageRunStatus.awaiting_review:
            raise InvalidStateError(
                f"only a stage awaiting review can resume (stage run is {stage_run.status})"
            )
        stage_run.status = StageRunStatus.approved
        stage_run.run.status = WorkflowRunStatus.running
        self._session.flush()
        return self._finalize_stage(stage_run)

    def _finalize_stage(self, stage_run: StageRun) -> WorkflowRun:
        run = stage_run.run
        stage = stage_run.stage_definition
        stage_run.status = StageRunStatus.completed
        stage_run.completed_at = utc_now()
        get_event_bus().publish(
            "workflow.stage.completed",
            {
                "workflow_run_id": str(run.id),
                "stage_run_id": str(stage_run.id),
                "stage_key": stage.stage_key,
            },
        )

        next_stage = self._next_stage(run, stage)
        if next_stage is None:
            run.status = WorkflowRunStatus.completed
            run.completed_at = utc_now()
            run.current_stage_run_id = None
            self._session.flush()
            return run

        # ICM handoff rule: the completed stage's latest artifact per role becomes
        # the next stage's layer-4 working input.
        handoff = [
            {
                "artifact_id": str(artifact.id),
                "artifact_role": artifact.artifact_role,
                "ref": artifact.storage_uri,
                "version_number": artifact.version_number,
                "from_stage_key": stage.stage_key,
                "size_bytes": len(self._storage.get_text(artifact.storage_uri)),
            }
            for artifact in self._repo.latest_artifacts_by_role(stage_run.id).values()
        ]
        self.start_stage(run, next_stage, handoff)
        self._session.flush()
        return run

    def fail_stage(self, stage_run: StageRun, error_summary: str) -> WorkflowRun:
        if stage_run.status not in (StageRunStatus.running, StageRunStatus.awaiting_review):
            raise InvalidStateError(f"cannot fail a stage in state {stage_run.status}")
        run = stage_run.run
        stage_run.status = StageRunStatus.failed
        stage_run.error_summary = error_summary
        stage_run.completed_at = utc_now()
        run.status = WorkflowRunStatus.failed
        run.completed_at = utc_now()
        self._session.flush()
        get_event_bus().publish(
            "workflow.stage.failed",
            {
                "workflow_run_id": str(run.id),
                "stage_run_id": str(stage_run.id),
                "stage_key": stage_run.stage_definition.stage_key,
                "error_summary": error_summary,
            },
        )
        return run

    def _validate_contract_outputs(self, stage_run: StageRun, stage: StageDefinition) -> None:
        required = {output["role"] for output in stage.contract.parsed_contract_json["outputs"]}
        submitted = set(self._repo.latest_artifacts_by_role(stage_run.id))
        missing = sorted(required - submitted)
        if missing:
            raise DomainValidationError(
                f"contract outputs missing before completion: {', '.join(missing)}"
            )

    def _next_stage(self, run: WorkflowRun, stage: StageDefinition) -> StageDefinition | None:
        stages = self._repo.get_version(run.tenant_id, run.workflow_template_version_id).stages
        following = [s for s in stages if s.order_index == stage.order_index + 1]
        return following[0] if following else None


class WorkflowRunService:
    def __init__(self, session: Session, storage: StorageService) -> None:
        self._session = session
        self._storage = storage
        self._repo = WorkflowRepository(session)
        self._workspace = WorkspaceMaterializationService(storage)
        self._coordinator = StageExecutionCoordinator(session, storage)

    def create_and_start(
        self,
        tenant_id: uuid.UUID,
        triggered_by: uuid.UUID,
        version_id: uuid.UUID,
        project_id: uuid.UUID | None,
        correlation_id: str | None,
    ) -> WorkflowRun:
        version = self._repo.get_version(tenant_id, version_id)
        if not version.stages:
            raise DomainValidationError("template version has no stages")

        run = WorkflowRun(
            tenant_id=tenant_id,
            project_id=project_id,
            workflow_template_version_id=version.id,
            environment_template_version_id=version.environment_template_version_id,
            status=WorkflowRunStatus.running,
            triggered_by=triggered_by,
            started_at=utc_now(),
            correlation_id=correlation_id,
        )
        self._session.add(run)
        self._session.flush()

        self._workspace.materialize_run(run, version)
        get_event_bus().publish(
            "workflow.run.created",
            {
                "workflow_run_id": str(run.id),
                "workflow_template_version_id": str(version.id),
                "tenant_id": str(tenant_id),
            },
        )
        self._coordinator.start_stage(run, version.stages[0], layer4_inputs=[])
        return run
