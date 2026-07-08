import uuid

from sqlalchemy.orm import Session

from app.evals.models.entities import EvalRun, EvalRunStatus, EvalTargetType
from app.evals.repositories.evals import EvalsRepository
from app.governance.services.audit import AuditService
from app.platform.errors import DomainValidationError
from app.platform.events.bus import get_event_bus
from app.platform.observability.correlation import get_correlation_id
from app.platform.time.clock import utc_now
from app.workflow.models.entities import ActorType
from app.workflow.repositories.workflow import WorkflowRepository


class EvalRunService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = EvalsRepository(session)
        self._workflow_repo = WorkflowRepository(session)
        self._audit = AuditService(session)

    def create_run(
        self,
        tenant_id: uuid.UUID,
        triggered_by: uuid.UUID,
        *,
        eval_suite_id: uuid.UUID,
        rubric_version_id: uuid.UUID,
        target_ref_type: EvalTargetType,
        target_ref_id: uuid.UUID,
        project_id: uuid.UUID | None = None,
    ) -> EvalRun:
        suite = self._repo.get_suite(tenant_id, eval_suite_id)
        if target_ref_type is not suite.target_type:
            raise DomainValidationError(f"suite targets {suite.target_type}, got {target_ref_type}")
        rubric_version = self._repo.get_rubric_version(tenant_id, rubric_version_id)
        linkage = self._resolve_target(tenant_id, target_ref_type, target_ref_id)

        run = EvalRun(
            tenant_id=tenant_id,
            project_id=project_id,
            eval_suite_id=suite.id,
            rubric_version_id=rubric_version.id,
            target_ref_type=target_ref_type,
            target_ref_id=target_ref_id,
            status=EvalRunStatus.awaiting_human_score,
            started_at=utc_now(),
            triggered_by=triggered_by,
            correlation_id=get_correlation_id(),
            **linkage,
        )
        self._session.add(run)
        self._session.flush()

        self._audit.record(
            tenant_id=tenant_id,
            project_id=project_id,
            event_type="evals.run.started",
            actor_type=ActorType.human,
            actor_id=triggered_by,
            workflow_run_id=run.workflow_run_id,
            stage_run_id=run.stage_run_id,
            eval_run_id=run.id,
            payload={"eval_suite_id": str(suite.id), "target_ref_type": target_ref_type},
        )
        get_event_bus().publish(
            "evals.run.started",
            {
                "eval_run_id": str(run.id),
                "eval_suite_id": str(suite.id),
                "target_ref_type": str(target_ref_type),
                "target_ref_id": str(target_ref_id),
            },
        )

        # Spec §28.8: suites that opt in get an advisory LLM-judge score.
        # Local import: the task module imports evals services back.
        from app.evals.services.judge import judge_config
        from app.tasks.judge_tasks import dispatch_judge_scoring

        if judge_config(suite).enabled:
            dispatch_judge_scoring(run.id)
        return run

    def _resolve_target(
        self, tenant_id: uuid.UUID, target_ref_type: EvalTargetType, target_ref_id: uuid.UUID
    ) -> dict:
        """Spec 16.1: every eval run must be traceable to its workflow context.
        Resolution is tenant-scoped, so a foreign target is a plain 404."""
        if target_ref_type is EvalTargetType.artifact:
            artifact = self._workflow_repo.get_artifact(tenant_id, target_ref_id)
            stage_run = self._workflow_repo.get_stage_run(tenant_id, artifact.stage_run_id)
            return {
                "artifact_id": artifact.id,
                "stage_run_id": artifact.stage_run_id,
                "workflow_run_id": artifact.workflow_run_id,
                "environment_template_version_id": (stage_run.run.environment_template_version_id),
            }
        if target_ref_type is EvalTargetType.stage_run:
            stage_run = self._workflow_repo.get_stage_run(tenant_id, target_ref_id)
            return {
                "stage_run_id": stage_run.id,
                "workflow_run_id": stage_run.workflow_run_id,
                "environment_template_version_id": (stage_run.run.environment_template_version_id),
            }
        if target_ref_type is EvalTargetType.workflow_run:
            run = self._workflow_repo.get_run(tenant_id, target_ref_id)
            return {
                "workflow_run_id": run.id,
                "environment_template_version_id": run.environment_template_version_id,
            }
        # environment_version: the environment module lands in phase 8; keep the ref.
        return {"environment_template_version_id": target_ref_id}
