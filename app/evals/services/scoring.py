import uuid

from sqlalchemy.orm import Session

from app.evals.models.entities import (
    DisagreementRecord,
    EvalDecision,
    EvalDecisionType,
    EvalRun,
    EvalRunStatus,
    ReviewerScore,
)
from app.evals.repositories.evals import EvalsRepository
from app.evals.rubrics.service import validate_and_score
from app.governance.services.audit import AuditService
from app.platform.auth.models import User
from app.platform.errors import InvalidStateError
from app.platform.events.bus import get_event_bus
from app.platform.storage.service import StorageService
from app.platform.time.clock import utc_now
from app.workflow.models.entities import ActorType


class EvalScoringService:
    def __init__(self, session: Session, storage: StorageService) -> None:
        self._session = session
        self._storage = storage
        self._repo = EvalsRepository(session)
        self._audit = AuditService(session)

    def submit_score(
        self,
        run: EvalRun,
        reviewer: User,
        *,
        score_json: dict,
        rationale: str,
        is_calibration: bool = False,
    ) -> ReviewerScore:
        if run.status is not EvalRunStatus.awaiting_human_score:
            raise InvalidStateError(f"eval run is not awaiting scores (status {run.status})")
        if self._repo.has_score_from(run.id, reviewer.id):
            raise InvalidStateError("reviewer has already scored this eval run")

        rubric_version = self._repo.get_rubric_version(run.tenant_id, run.rubric_version_id)
        weighted_total, passed = validate_and_score(rubric_version, score_json)

        score = ReviewerScore(
            eval_run_id=run.id,
            rubric_version_id=rubric_version.id,
            reviewer_id=reviewer.id,
            score_json={**score_json, "_weighted_total": weighted_total},
            pass_fail=passed,
            rationale=rationale,
            is_calibration=is_calibration,
            submitted_at=utc_now(),
        )
        self._session.add(score)
        self._session.flush()

        min_reviewers = run.suite.config_json.get("min_reviewers", 1)
        scores = self._repo.scores_for_run(run.id)
        if len(scores) >= min_reviewers:
            self._complete_run(run, scores)
        return score

    def _complete_run(self, run: EvalRun, scores: list[ReviewerScore]) -> EvalDecision:
        passes = [s for s in scores if s.pass_fail]
        fails = [s for s in scores if not s.pass_fail]

        if len(passes) > len(fails):
            decision_type = EvalDecisionType.passed
        elif len(fails) > len(passes):
            decision_type = EvalDecisionType.failed
        else:
            decision_type = EvalDecisionType.needs_adjudication

        # Spec 18.1: any pass/fail split is recorded, even when a majority exists.
        if passes and fails:
            self._session.add(
                DisagreementRecord(
                    eval_run_id=run.id,
                    reviewer_score_ids_json=[str(s.id) for s in scores],
                )
            )

        totals = [s.score_json.get("_weighted_total", 0) for s in scores]
        decision = EvalDecision(
            eval_run_id=run.id,
            decision_type=decision_type,
            decided_by_type=ActorType.system,
            metrics_json={
                "mean_weighted_total": sum(totals) / len(totals),
                "pass_votes": len(passes),
                "fail_votes": len(fails),
                "reviewer_count": len(scores),
            },
            rationale=f"{len(passes)} pass / {len(fails)} fail across {len(scores)} reviewer(s)",
        )
        self._session.add(decision)
        run.status = EvalRunStatus.completed
        run.completed_at = utc_now()
        self._session.flush()

        self._audit.record(
            tenant_id=run.tenant_id,
            project_id=run.project_id,
            event_type="evals.result.recorded",
            actor_type=ActorType.system,
            workflow_run_id=run.workflow_run_id,
            stage_run_id=run.stage_run_id,
            eval_run_id=run.id,
            payload={"decision_type": decision.decision_type, **decision.metrics_json},
        )
        get_event_bus().publish(
            "evals.result.recorded",
            {
                "eval_run_id": str(run.id),
                "decision_type": str(decision.decision_type),
                "stage_run_id": str(run.stage_run_id) if run.stage_run_id else None,
            },
        )

        self._notify_eval_gate(run, decision)
        return decision

    def _notify_eval_gate(self, run: EvalRun, decision: EvalDecision) -> None:
        """If this run targets a stage paused at the eval gate, drive the workflow."""
        if run.stage_run_id is None:
            return

        # Local import: workflow and evals call into each other across the eval gate.
        from app.workflow.models.entities import StageRunStatus
        from app.workflow.repositories.workflow import WorkflowRepository
        from app.workflow.services.runs import StageExecutionCoordinator

        stage_run = WorkflowRepository(self._session).get_stage_run(run.tenant_id, run.stage_run_id)
        if stage_run.status is not StageRunStatus.awaiting_eval:
            return
        coordinator = StageExecutionCoordinator(self._session, self._storage)
        if decision.decision_type is EvalDecisionType.passed:
            coordinator.resume_eval_passed_stage(stage_run)
        elif decision.decision_type is EvalDecisionType.failed:
            coordinator.fail_stage(stage_run, f"failed eval run {run.id}")
        # needs_adjudication: the stage stays paused until a later run decides.


def get_disagreements_for_run(session: Session, eval_run_id: uuid.UUID) -> list[DisagreementRecord]:
    from sqlalchemy import select

    return list(
        session.scalars(
            select(DisagreementRecord).where(DisagreementRecord.eval_run_id == eval_run_id)
        )
    )
