import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.governance.models.entities import (
    ApprovalGate,
    ReviewDecision,
    ReviewDecisionType,
    ReviewTask,
    ReviewTaskStatus,
)
from app.governance.services.audit import AuditService
from app.platform.auth.models import Role, User
from app.platform.errors import ForbiddenError, InvalidStateError, NotFoundError
from app.platform.events.bus import get_event_bus
from app.platform.observability.correlation import get_correlation_id
from app.platform.storage.service import StorageService
from app.platform.time.clock import utc_now
from app.workflow.models.entities import ActorType, StageDefinition, StageRun, WorkflowRun
from app.workflow.repositories.workflow import WorkflowRepository

_DECIDABLE = (ReviewTaskStatus.open, ReviewTaskStatus.in_progress)


class ReviewTaskService:
    def __init__(self, session: Session, storage: StorageService) -> None:
        self._session = session
        self._storage = storage
        self._audit = AuditService(session)
        self._workflow_repo = WorkflowRepository(session)

    # -- creation ---------------------------------------------------------

    def request_review(
        self, run: WorkflowRun, stage_run: StageRun, stage: StageDefinition
    ) -> ReviewTask:
        """Called by the workflow coordinator when a stage pauses for review."""
        gate = self._find_or_create_gate(stage)
        primary_role = stage.contract.parsed_contract_json["outputs"][0]["role"]
        latest = self._workflow_repo.latest_artifacts_by_role(stage_run.id)
        primary_artifact = latest.get(primary_role)

        task = ReviewTask(
            tenant_id=run.tenant_id,
            project_id=run.project_id,
            workflow_run_id=run.id,
            stage_run_id=stage_run.id,
            artifact_id=primary_artifact.id if primary_artifact else None,
            approval_gate_id=gate.id,
            status=ReviewTaskStatus.open,
            eligible_role=gate.required_role,
            due_at=(utc_now() + timedelta(minutes=gate.sla_minutes) if gate.sla_minutes else None),
            correlation_id=get_correlation_id(),
        )
        self._session.add(task)
        self._session.flush()
        stage_run.review_gate_id = gate.id

        self._audit.record(
            tenant_id=run.tenant_id,
            project_id=run.project_id,
            event_type="governance.review.requested",
            actor_type=ActorType.system,
            workflow_run_id=run.id,
            stage_run_id=stage_run.id,
            review_task_id=task.id,
            payload={"stage_key": stage.stage_key, "eligible_role": task.eligible_role},
        )
        get_event_bus().publish(
            "governance.review.requested",
            {
                "review_task_id": str(task.id),
                "workflow_run_id": str(run.id),
                "stage_run_id": str(stage_run.id),
                "stage_key": stage.stage_key,
            },
        )
        return task

    def _find_or_create_gate(self, stage: StageDefinition) -> ApprovalGate:
        gate = self._session.scalar(
            select(ApprovalGate).where(ApprovalGate.stage_definition_id == stage.id)
        )
        if gate is None:
            gate = ApprovalGate(stage_definition_id=stage.id, required_role=Role.reviewer.value)
            self._session.add(gate)
            self._session.flush()
        return gate

    # -- lookup -----------------------------------------------------------

    def get_task(self, tenant_id: uuid.UUID, task_id: uuid.UUID) -> ReviewTask:
        task = self._session.scalar(
            select(ReviewTask).where(ReviewTask.id == task_id, ReviewTask.tenant_id == tenant_id)
        )
        if task is None:
            raise NotFoundError(f"review task {task_id} not found")
        return task

    def list_tasks(
        self, tenant_id: uuid.UUID, status: ReviewTaskStatus | None = None
    ) -> list[ReviewTask]:
        stmt = select(ReviewTask).where(ReviewTask.tenant_id == tenant_id)
        if status is not None:
            stmt = stmt.where(ReviewTask.status == status)
        return list(self._session.scalars(stmt.order_by(ReviewTask.created_at)))

    # -- decisions --------------------------------------------------------

    def approve(self, task: ReviewTask, reviewer: User, rationale: str) -> ReviewTask:
        self._check_decidable(task, reviewer)
        self._record_decision(task, reviewer, ReviewDecisionType.approve, rationale)
        task.status = ReviewTaskStatus.approved
        self._resume_stage(task)
        self._finish(task, reviewer, "approved", rationale)
        return task

    def edit(
        self,
        task: ReviewTask,
        reviewer: User,
        rationale: str,
        *,
        artifact_role: str,
        content: str,
        content_type: str = "text/markdown",
    ) -> ReviewTask:
        """Approve with reviewer edits: the edited artifact becomes the version
        that hands off to the next stage."""
        self._check_decidable(task, reviewer)
        stage_run = self._workflow_repo.get_stage_run(task.tenant_id, task.stage_run_id)
        previous = self._workflow_repo.latest_artifacts_by_role(stage_run.id).get(artifact_role)
        if previous is None:
            raise InvalidStateError(f"stage has no artifact with role {artifact_role!r} to edit")

        from app.workflow.models.entities import StageRunStatus
        from app.workflow.services.artifacts import ArtifactService

        edited = ArtifactService(self._session, self._storage).submit(
            stage_run,
            artifact_role=artifact_role,
            content=content,
            content_type=content_type,
            created_by_type=ActorType.human,
            created_by_id=reviewer.id,
            is_human_edited=True,
            source_artifact_id=previous.id,
            allowed_states=(StageRunStatus.awaiting_review,),
        )
        self._record_decision(
            task, reviewer, ReviewDecisionType.edit, rationale, edited_artifact_id=edited.id
        )
        task.status = ReviewTaskStatus.edited
        self._resume_stage(task)
        self._finish(task, reviewer, "edited", rationale, {"edited_artifact_id": str(edited.id)})
        return task

    def reject(self, task: ReviewTask, reviewer: User, rationale: str) -> ReviewTask:
        self._check_decidable(task, reviewer)
        self._record_decision(task, reviewer, ReviewDecisionType.reject, rationale)
        task.status = ReviewTaskStatus.rejected

        from app.workflow.services.runs import StageExecutionCoordinator

        stage_run = self._workflow_repo.get_stage_run(task.tenant_id, task.stage_run_id)
        StageExecutionCoordinator(self._session, self._storage).fail_stage(
            stage_run, f"rejected by review: {rationale}"
        )
        self._finish(task, reviewer, "rejected", rationale)
        return task

    def escalate(self, task: ReviewTask, reviewer: User, rationale: str) -> ReviewTask:
        """Marks the task escalated and opens a fresh task for admins; the stage
        stays paused until the escalated task is decided."""
        self._check_decidable(task, reviewer)
        self._record_decision(task, reviewer, ReviewDecisionType.escalate, rationale)
        task.status = ReviewTaskStatus.escalated

        escalated = ReviewTask(
            tenant_id=task.tenant_id,
            project_id=task.project_id,
            workflow_run_id=task.workflow_run_id,
            stage_run_id=task.stage_run_id,
            artifact_id=task.artifact_id,
            approval_gate_id=task.approval_gate_id,
            status=ReviewTaskStatus.open,
            eligible_role=Role.admin.value,
            correlation_id=get_correlation_id(),
        )
        self._session.add(escalated)
        self._session.flush()
        self._finish(
            task, reviewer, "escalated", rationale, {"escalated_task_id": str(escalated.id)}
        )
        return escalated

    # -- internals --------------------------------------------------------

    def _check_decidable(self, task: ReviewTask, reviewer: User) -> None:
        if task.status not in _DECIDABLE:
            raise InvalidStateError(f"review task is already {task.status}")
        if reviewer.role is not Role.admin and reviewer.role.value != task.eligible_role:
            raise ForbiddenError(f"review task requires role {task.eligible_role!r}")

    def _record_decision(
        self,
        task: ReviewTask,
        reviewer: User,
        decision_type: ReviewDecisionType,
        rationale: str,
        edited_artifact_id: uuid.UUID | None = None,
    ) -> None:
        self._session.add(
            ReviewDecision(
                review_task_id=task.id,
                decision_type=decision_type,
                rationale=rationale,
                edited_artifact_id=edited_artifact_id,
                decided_by=reviewer.id,
                decided_at=utc_now(),
            )
        )
        self._session.flush()

    def _resume_stage(self, task: ReviewTask) -> None:
        from app.workflow.services.runs import StageExecutionCoordinator

        stage_run = self._workflow_repo.get_stage_run(task.tenant_id, task.stage_run_id)
        StageExecutionCoordinator(self._session, self._storage).resume_approved_stage(stage_run)

    def _finish(
        self,
        task: ReviewTask,
        reviewer: User,
        outcome: str,
        rationale: str,
        extra: dict | None = None,
    ) -> None:
        self._audit.record(
            tenant_id=task.tenant_id,
            project_id=task.project_id,
            event_type=f"governance.review.{outcome}",
            actor_type=ActorType.human,
            actor_id=reviewer.id,
            workflow_run_id=task.workflow_run_id,
            stage_run_id=task.stage_run_id,
            review_task_id=task.id,
            payload={"rationale": rationale, **(extra or {})},
        )
        get_event_bus().publish(
            f"governance.review.{outcome}",
            {
                "review_task_id": str(task.id),
                "workflow_run_id": str(task.workflow_run_id),
                "stage_run_id": str(task.stage_run_id),
                "decided_by": str(reviewer.id),
            },
        )
        self._session.flush()
