import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.evals.models.entities import (
    Baseline,
    DriftSignal,
    EvalDecision,
    EvalDecisionType,
    EvalRun,
    EvalRunStatus,
    EvalSuite,
    RegressionPack,
    ReviewerScore,
    Rubric,
    RubricVersion,
)
from app.platform.errors import NotFoundError


class EvalsRepository:
    """All lookups are tenant-scoped, directly or through the owning parent."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_suite(self, tenant_id: uuid.UUID, suite_id: uuid.UUID) -> EvalSuite:
        suite = self._session.scalar(
            select(EvalSuite)
            .where(EvalSuite.id == suite_id, EvalSuite.tenant_id == tenant_id)
            .options(selectinload(EvalSuite.cases))
        )
        if suite is None:
            raise NotFoundError(f"eval suite {suite_id} not found")
        return suite

    def get_rubric(self, tenant_id: uuid.UUID, rubric_id: uuid.UUID) -> Rubric:
        rubric = self._session.scalar(
            select(Rubric)
            .where(Rubric.id == rubric_id, Rubric.tenant_id == tenant_id)
            .options(selectinload(Rubric.versions))
        )
        if rubric is None:
            raise NotFoundError(f"rubric {rubric_id} not found")
        return rubric

    def get_rubric_version(self, tenant_id: uuid.UUID, version_id: uuid.UUID) -> RubricVersion:
        version = self._session.scalar(
            select(RubricVersion)
            .join(Rubric)
            .where(RubricVersion.id == version_id, Rubric.tenant_id == tenant_id)
        )
        if version is None:
            raise NotFoundError(f"rubric version {version_id} not found")
        return version

    def next_rubric_version_number(self, rubric_id: uuid.UUID) -> int:
        current = self._session.scalar(
            select(func.max(RubricVersion.version_number)).where(
                RubricVersion.rubric_id == rubric_id
            )
        )
        return (current or 0) + 1

    def get_run(self, tenant_id: uuid.UUID, run_id: uuid.UUID) -> EvalRun:
        run = self._session.scalar(
            select(EvalRun)
            .where(EvalRun.id == run_id, EvalRun.tenant_id == tenant_id)
            .options(selectinload(EvalRun.scores), selectinload(EvalRun.decision))
        )
        if run is None:
            raise NotFoundError(f"eval run {run_id} not found")
        return run

    def scores_for_run(self, eval_run_id: uuid.UUID) -> list[ReviewerScore]:
        return list(
            self._session.scalars(
                select(ReviewerScore)
                .where(ReviewerScore.eval_run_id == eval_run_id)
                .order_by(ReviewerScore.submitted_at)
            )
        )

    def has_score_from(self, eval_run_id: uuid.UUID, reviewer_id: uuid.UUID) -> bool:
        return (
            self._session.scalar(
                select(func.count())
                .select_from(ReviewerScore)
                .where(
                    ReviewerScore.eval_run_id == eval_run_id,
                    ReviewerScore.reviewer_id == reviewer_id,
                )
            )
            > 0
        )

    def latest_completed_decision_for_stage_run(
        self, stage_run_id: uuid.UUID
    ) -> EvalDecision | None:
        return self._session.scalar(
            select(EvalDecision)
            .join(EvalRun, EvalDecision.eval_run_id == EvalRun.id)
            .where(
                EvalRun.stage_run_id == stage_run_id,
                EvalRun.status == EvalRunStatus.completed,
            )
            .order_by(EvalRun.completed_at.desc())
            .limit(1)
        )

    def latest_decision_for_suite(self, suite_id: uuid.UUID) -> EvalDecision | None:
        return self._session.scalar(
            select(EvalDecision)
            .join(EvalRun, EvalDecision.eval_run_id == EvalRun.id)
            .where(
                EvalRun.eval_suite_id == suite_id,
                EvalRun.status == EvalRunStatus.completed,
            )
            .order_by(EvalRun.completed_at.desc())
            .limit(1)
        )

    def get_regression_pack(self, tenant_id: uuid.UUID, pack_id: uuid.UUID) -> RegressionPack:
        pack = self._session.scalar(
            select(RegressionPack).where(
                RegressionPack.id == pack_id, RegressionPack.tenant_id == tenant_id
            )
        )
        if pack is None:
            raise NotFoundError(f"regression pack {pack_id} not found")
        return pack

    def baseline_for_scope(
        self, tenant_id: uuid.UUID, scope_type: str, scope_ref: str
    ) -> Baseline | None:
        return self._session.scalar(
            select(Baseline)
            .where(
                Baseline.tenant_id == tenant_id,
                Baseline.scope_type == scope_type,
                Baseline.scope_ref == scope_ref,
            )
            .order_by(Baseline.created_at.desc())
            .limit(1)
        )

    def drift_signals(self, tenant_id: uuid.UUID, limit: int = 100) -> list[DriftSignal]:
        return list(
            self._session.scalars(
                select(DriftSignal)
                .where(DriftSignal.tenant_id == tenant_id)
                .order_by(DriftSignal.detected_at.desc())
                .limit(min(limit, 500))
            )
        )

    @staticmethod
    def is_pass(decision: EvalDecision | None) -> bool:
        return decision is not None and decision.decision_type is EvalDecisionType.passed
