"""Judge calibration (spec §13.2/§13.3; roadmap stage 4b, plan of 2026-07-12).

A trustworthy judge is not a given: judge configs are models and get validated
like models. Golden examples carry a human gold label and an immutable
train/dev/test split assigned at creation; examples sharing a group_key (e.g.
one workflow run's artifacts) always share a split, so correlated work never
straddles train and test. A CalibrationRun executes the current judge prompt
over a dev or test split and records TPR/TNR with Wilson intervals — the
positive class is a DEFECT (gold pass_fail is False), so TPR reads "the judge
catches what humans failed".

Freeze discipline: a test_set_version becomes frozen the moment any
non-failed CalibrationRun references it; later additions must open the next
version. Dev is for iteration; test is never tuned against.

The calibration gate (JudgeConfig.calibration_gate) makes this CI for judges:
a suite can require a passing test-split run for the live judge model before
the judge is allowed to score production work — fail closed, judge stays
silent, humans unaffected.

Monitoring: with TPR/TNR known, the observed judge fail rate on production
runs is corrected for judge error with the Rogan-Gladen estimator
(p_true = (p_obs + TNR - 1) / (TPR + TNR - 1)). When TPR + TNR ≈ 1 the judge
is uninformative and the corrected estimate is withheld rather than reported.
"""

from __future__ import annotations

import hashlib
import math
import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.evals.models.entities import (
    CalibrationExample,
    CalibrationRun,
    CalibrationRunStatus,
    CalibrationSplit,
    DisagreementRecord,
    EvalDecision,
    EvalDecisionType,
    EvalRun,
    ReviewerScore,
)
from app.evals.repositories.evals import EvalsRepository
from app.evals.rubrics.service import validate_and_score
from app.evals.services.judge import build_judge_system, eval_target_content, parse_judge_response
from app.governance.services.audit import AuditService
from app.platform.errors import DomainValidationError, InvalidStateError, NotFoundError
from app.platform.events.bus import get_event_bus
from app.platform.ids.generator import new_uuid
from app.platform.llm.adapter import get_llm_adapter
from app.platform.llm.budget import BudgetExceededError, LLMUsageLedger
from app.platform.settings.config import get_settings
from app.platform.storage.service import StorageService
from app.platform.time.clock import utc_now
from app.workflow.models.entities import ActorType

logger = structlog.get_logger(__name__)

# Deterministic default split by group hash: half the gold data trains/steers
# prompts, the rest measures — dev for iteration, test frozen for the gate.
SPLIT_BUCKETS = ((CalibrationSplit.train, 50), (CalibrationSplit.dev, 75))
# Below this informedness (TPR + TNR - 1) the judge is statistically
# uninformative and the Rogan-Gladen correction is unstable — withhold it.
MIN_INFORMEDNESS = 0.1


def assign_split(group_key: str) -> CalibrationSplit:
    bucket = int(hashlib.sha256(group_key.encode("utf-8")).hexdigest(), 16) % 100
    for split, upper in SPLIT_BUCKETS:
        if bucket < upper:
            return split
    return CalibrationSplit.test


def wilson_interval(successes: int, n: int, z: float = 1.96) -> list[float] | None:
    """95% Wilson score interval; honest about small n, never leaves [0, 1]."""
    if n == 0:
        return None
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return [round(max(0.0, center - margin), 4), round(min(1.0, center + margin), 4)]


def compute_agreement_metrics(examples: list[dict]) -> dict:
    """TPR/TNR over scored examples. Positive class = defect (gold fail)."""
    scored = [e for e in examples if e.get("judge_pass_fail") is not None]
    defects = [e for e in scored if e["gold_pass_fail"] is False]
    passes = [e for e in scored if e["gold_pass_fail"] is True]
    tp = sum(1 for e in defects if e["judge_pass_fail"] is False)
    tn = sum(1 for e in passes if e["judge_pass_fail"] is True)

    tpr = tp / len(defects) if defects else None
    tnr = tn / len(passes) if passes else None
    informedness = round(tpr + tnr - 1, 4) if tpr is not None and tnr is not None else None
    return {
        "n_scored": len(scored),
        "n_errors": len(examples) - len(scored),
        "n_defects": len(defects),
        "n_passes": len(passes),
        "tpr": round(tpr, 4) if tpr is not None else None,
        "tpr_ci95": wilson_interval(tp, len(defects)),
        "tnr": round(tnr, 4) if tnr is not None else None,
        "tnr_ci95": wilson_interval(tn, len(passes)),
        "accuracy": round((tp + tn) / len(scored), 4) if scored else None,
        "informedness": informedness,
        "uninformative": informedness is not None and informedness < MIN_INFORMEDNESS,
        "positive_class": "defect (gold pass_fail = false)",
    }


def rogan_gladen_corrected(p_obs: float, tpr: float, tnr: float) -> float | None:
    """Corrected true fail rate from the judge's observed fail rate; None when
    the judge is uninformative (TPR + TNR ≈ 1 makes the estimator unstable)."""
    informedness = tpr + tnr - 1
    if informedness < MIN_INFORMEDNESS:
        return None
    return round(min(1.0, max(0.0, (p_obs + tnr - 1) / informedness)), 4)


def latest_test_calibration(
    session: Session,
    tenant_id: uuid.UUID,
    *,
    rubric_version_id: uuid.UUID,
    judge_model: str,
) -> CalibrationRun | None:
    return session.scalar(
        select(CalibrationRun)
        .where(
            CalibrationRun.tenant_id == tenant_id,
            CalibrationRun.rubric_version_id == rubric_version_id,
            CalibrationRun.judge_model == judge_model,
            CalibrationRun.split == CalibrationSplit.test,
            CalibrationRun.status == CalibrationRunStatus.completed,
        )
        .order_by(CalibrationRun.completed_at.desc())
        .limit(1)
    )


def calibration_gate_check(
    session: Session,
    tenant_id: uuid.UUID,
    *,
    rubric_version_id: uuid.UUID,
    judge_model: str,
    min_tpr: float,
    min_tnr: float,
) -> tuple[bool, str]:
    """CI gate for judge configs, fail closed: no completed test-split run for
    this (rubric version, judge model), or metrics below thresholds ⇒ blocked."""
    run = latest_test_calibration(
        session, tenant_id, rubric_version_id=rubric_version_id, judge_model=judge_model
    )
    if run is None:
        return False, (
            f"no completed test-split calibration run for judge model {judge_model!r} "
            "on this rubric version"
        )
    tpr = run.metrics_json.get("tpr")
    tnr = run.metrics_json.get("tnr")
    if tpr is None or tnr is None:
        return False, "calibration run lacks TPR/TNR (a split class had no examples)"
    if tpr < min_tpr or tnr < min_tnr:
        return False, (
            f"calibration below thresholds: TPR {tpr} (min {min_tpr}), TNR {tnr} (min {min_tnr})"
        )
    return True, "calibrated"


class CalibrationExampleService:
    def __init__(self, session: Session, storage: StorageService) -> None:
        self._session = session
        self._storage = storage
        self._repo = EvalsRepository(session)

    def create_example(
        self,
        tenant_id: uuid.UUID,
        created_by: uuid.UUID,
        *,
        rubric_version_id: uuid.UUID,
        content: str,
        gold_score_json: dict,
        gold_pass_fail: bool,
        gold_rationale: str = "",
        group_key: str,
        split: CalibrationSplit | None = None,
        test_set_version: int | None = None,
        provenance: str = "authored",
        source_eval_run_id: uuid.UUID | None = None,
        source_artifact_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
    ) -> CalibrationExample:
        rubric_version = self._repo.get_rubric_version(tenant_id, rubric_version_id)
        # Gold scores must be shaped like real reviewer scores for this rubric.
        validate_and_score(rubric_version, gold_score_json)

        split = self._resolve_split(tenant_id, group_key, split)
        version = (
            self._resolve_test_set_version(tenant_id, rubric_version.id, test_set_version)
            if split is CalibrationSplit.test
            else None
        )

        example_id = new_uuid()
        content_ref = self._storage.put_text(f"calibration/{tenant_id}/{example_id}.md", content)
        example = CalibrationExample(
            id=example_id,
            tenant_id=tenant_id,
            project_id=project_id,
            rubric_version_id=rubric_version.id,
            content_ref=content_ref,
            content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            gold_score_json=gold_score_json,
            gold_pass_fail=gold_pass_fail,
            gold_rationale=gold_rationale,
            split=split,
            group_key=group_key,
            test_set_version=version,
            provenance=provenance,
            source_eval_run_id=source_eval_run_id,
            source_artifact_id=source_artifact_id,
            created_by=created_by,
        )
        self._session.add(example)
        self._session.flush()

        AuditService(self._session).record(
            tenant_id=tenant_id,
            project_id=project_id,
            event_type="evals.calibration.example_created",
            actor_type=ActorType.human,
            actor_id=created_by,
            eval_run_id=source_eval_run_id,
            payload={
                "calibration_example_id": str(example.id),
                "split": str(split),
                "test_set_version": version,
                "provenance": provenance,
                "gold_pass_fail": gold_pass_fail,
            },
        )
        return example

    def harvest_from_eval_run(
        self,
        tenant_id: uuid.UUID,
        created_by: uuid.UUID,
        *,
        eval_run_id: uuid.UUID,
        split: CalibrationSplit | None = None,
        group_key: str | None = None,
        test_set_version: int | None = None,
    ) -> CalibrationExample:
        """Promote a human-decided eval run to a golden example: the content
        the judge would have seen, labeled with the human decision."""
        run = self._repo.get_run(tenant_id, eval_run_id)
        # Query directly: the run instance may carry stale relationship state
        # if it was loaded before the decision landed in this session.
        decision = self._session.scalar(
            select(EvalDecision).where(EvalDecision.eval_run_id == run.id)
        )
        if decision is None or decision.decision_type not in (
            EvalDecisionType.passed,
            EvalDecisionType.failed,
        ):
            raise InvalidStateError(
                f"eval run {eval_run_id} has no pass/fail human decision to use as a gold label"
            )
        already = self._session.scalar(
            select(CalibrationExample).where(
                CalibrationExample.tenant_id == tenant_id,
                CalibrationExample.source_eval_run_id == run.id,
            )
        )
        if already is not None:
            raise InvalidStateError(f"eval run {eval_run_id} is already harvested")

        human_scores = [
            s for s in self._repo.scores_for_run(run.id) if s.scored_by_type is ActorType.human
        ]
        if not human_scores:
            raise InvalidStateError(f"eval run {eval_run_id} has no human scores")
        gold_scores = self._mean_scores(human_scores)
        had_disagreement = (
            self._session.scalar(
                select(func.count())
                .select_from(DisagreementRecord)
                .where(DisagreementRecord.eval_run_id == run.id)
            )
            > 0
        )

        return self.create_example(
            tenant_id,
            created_by,
            rubric_version_id=run.rubric_version_id,
            content=eval_target_content(self._session, self._storage, run),
            gold_score_json=gold_scores,
            gold_pass_fail=decision.decision_type is EvalDecisionType.passed,
            gold_rationale=decision.rationale,
            # Same workflow run ⇒ same split: correlated artifacts must not leak.
            group_key=group_key or str(run.workflow_run_id or run.target_ref_id),
            split=split,
            test_set_version=test_set_version,
            provenance="harvested_disagreement" if had_disagreement else "harvested_eval_run",
            source_eval_run_id=run.id,
            source_artifact_id=run.artifact_id,
            project_id=run.project_id,
        )

    def harvest_suggestions(self, tenant_id: uuid.UUID, limit: int = 50) -> list[dict]:
        """Decided-but-unharvested eval runs worth turning into golden
        examples — disagreements and judge misses first (the flywheel)."""
        harvested = select(CalibrationExample.source_eval_run_id).where(
            CalibrationExample.tenant_id == tenant_id,
            CalibrationExample.source_eval_run_id.is_not(None),
        )
        runs = list(
            self._session.scalars(
                select(EvalRun)
                .where(EvalRun.tenant_id == tenant_id, EvalRun.id.not_in(harvested))
                .order_by(EvalRun.completed_at.desc())
                .limit(500)
            )
        )
        suggestions = []
        for run in runs:
            decision = self._session.scalar(
                select(EvalDecision).where(EvalDecision.eval_run_id == run.id)
            )
            if decision is None or decision.decision_type not in (
                EvalDecisionType.passed,
                EvalDecisionType.failed,
            ):
                continue
            reasons = []
            if decision.metrics_json.get("judge_agrees") is False:
                reasons.append("judge disagreed with the human decision")
            if self._session.scalar(
                select(func.count())
                .select_from(DisagreementRecord)
                .where(DisagreementRecord.eval_run_id == run.id)
            ):
                reasons.append("reviewers disagreed")
            if reasons:
                suggestions.append(
                    {
                        "eval_run_id": str(run.id),
                        "decision": str(decision.decision_type),
                        "reasons": reasons,
                    }
                )
            if len(suggestions) >= limit:
                break
        return suggestions

    # ------------------------------------------------------------------ #
    def _resolve_split(
        self, tenant_id: uuid.UUID, group_key: str, requested: CalibrationSplit | None
    ) -> CalibrationSplit:
        existing = self._session.scalar(
            select(CalibrationExample.split)
            .where(
                CalibrationExample.tenant_id == tenant_id,
                CalibrationExample.group_key == group_key,
            )
            .limit(1)
        )
        if existing is not None:
            if requested is not None and requested is not existing:
                raise DomainValidationError(
                    f"group {group_key!r} is already in the {existing} split; examples from "
                    "one group must share a split (leakage guard)"
                )
            return existing
        return requested if requested is not None else assign_split(group_key)

    def _resolve_test_set_version(
        self, tenant_id: uuid.UUID, rubric_version_id: uuid.UUID, requested: int | None
    ) -> int:
        current = (
            self._session.scalar(
                select(func.max(CalibrationExample.test_set_version)).where(
                    CalibrationExample.tenant_id == tenant_id,
                    CalibrationExample.rubric_version_id == rubric_version_id,
                    CalibrationExample.split == CalibrationSplit.test,
                )
            )
            or 0
        )
        version = requested if requested is not None else max(current, 1)
        if version < 1 or version > current + 1:
            raise DomainValidationError(
                f"test_set_version must be between 1 and {current + 1} (next open version)"
            )
        if self._is_test_set_frozen(tenant_id, rubric_version_id, version):
            raise DomainValidationError(
                f"test set v{version} is frozen (a calibration run has used it); "
                f"add the example to v{max(current, version) + 1} instead"
            )
        return version

    def _is_test_set_frozen(
        self, tenant_id: uuid.UUID, rubric_version_id: uuid.UUID, version: int
    ) -> bool:
        return (
            self._session.scalar(
                select(func.count())
                .select_from(CalibrationRun)
                .where(
                    CalibrationRun.tenant_id == tenant_id,
                    CalibrationRun.rubric_version_id == rubric_version_id,
                    CalibrationRun.split == CalibrationSplit.test,
                    CalibrationRun.test_set_version == version,
                    CalibrationRun.status != CalibrationRunStatus.failed,
                )
            )
            > 0
        )

    @staticmethod
    def _mean_scores(scores: list[ReviewerScore]) -> dict:
        keys: dict[str, list[float]] = {}
        for score in scores:
            for key, value in score.score_json.items():
                if not key.startswith("_") and isinstance(value, (int, float)):
                    keys.setdefault(key, []).append(float(value))
        return {key: sum(values) / len(values) for key, values in keys.items()}


class CalibrationRunService:
    def __init__(self, session: Session, storage: StorageService) -> None:
        self._session = session
        self._storage = storage
        self._repo = EvalsRepository(session)

    def create_run(
        self,
        tenant_id: uuid.UUID,
        triggered_by: uuid.UUID,
        *,
        rubric_version_id: uuid.UUID,
        split: CalibrationSplit,
        test_set_version: int | None = None,
        project_id: uuid.UUID | None = None,
    ) -> CalibrationRun:
        if split not in (CalibrationSplit.dev, CalibrationSplit.test):
            raise DomainValidationError(
                "calibration runs evaluate the dev or test split; train is prompt material only"
            )
        rubric_version = self._repo.get_rubric_version(tenant_id, rubric_version_id)
        version = None
        if split is CalibrationSplit.test:
            version = test_set_version or self._latest_test_set_version(
                tenant_id, rubric_version.id
            )
        if not self._split_examples(tenant_id, rubric_version.id, split, version):
            raise DomainValidationError(
                f"no {split} examples exist for this rubric version"
                + (f" (test set v{version})" if version else "")
            )

        settings = get_settings()
        run = CalibrationRun(
            tenant_id=tenant_id,
            project_id=project_id,
            rubric_version_id=rubric_version.id,
            split=split,
            test_set_version=version,
            judge_provider=settings.llm_judge_provider,
            judge_model=settings.llm_judge_model,
            judge_config_json={
                "provider": settings.llm_judge_provider,
                "model": settings.llm_judge_model,
                "max_output_tokens": settings.llm_max_output_tokens,
            },
            triggered_by=triggered_by,
        )
        self._session.add(run)
        self._session.flush()

        from app.tasks.calibration_tasks import dispatch_calibration_run

        dispatch_calibration_run(run.id)
        return run

    def execute(self, calibration_run_id: uuid.UUID) -> CalibrationRun:
        """Score every example in the run's split with the live judge config.
        Per-example provider/parse errors are recorded and skipped; a budget
        cap or unexpected error fails the run — it never propagates out."""
        run = self._session.scalar(
            select(CalibrationRun).where(CalibrationRun.id == calibration_run_id)
        )
        if run is None:
            raise LookupError(f"calibration run {calibration_run_id} not found")
        if run.status is not CalibrationRunStatus.pending:
            logger.info(
                "calibration_run_skipped",
                calibration_run_id=str(run.id),
                reason=f"run is {run.status}",
            )
            return run

        run.status = CalibrationRunStatus.running
        run.started_at = utc_now()
        self._session.flush()

        examples = self._examples(run)
        rubric_version = self._repo.get_rubric_version(run.tenant_id, run.rubric_version_id)
        system = build_judge_system(rubric_version)
        settings = get_settings()
        ledger = LLMUsageLedger(self._session)

        results: list[dict] = []
        error_summary: str | None = None
        for example in examples:
            entry: dict = {
                "example_id": str(example.id),
                "gold_pass_fail": example.gold_pass_fail,
                "judge_pass_fail": None,
            }
            try:
                ledger.ensure_within_budget()
                result = get_llm_adapter("judge").complete(
                    model=settings.llm_judge_model,
                    system=system,
                    user_content=self._storage.get_text(example.content_ref),
                    max_tokens=settings.llm_max_output_tokens,
                )
                ledger.record(run.tenant_id, result, purpose="calibration")
                scores, _rationale = parse_judge_response(result.text)
                weighted_total, judge_pass = validate_and_score(rubric_version, scores)
                entry.update(
                    judge_pass_fail=judge_pass,
                    weighted_total=weighted_total,
                    scores=scores,
                )
            except BudgetExceededError as exc:
                error_summary = f"budget cap reached after {len(results)} examples: {exc}"
                results.append(entry)
                break
            except Exception as exc:  # noqa: BLE001 — one bad example must not kill the run
                entry["error"] = f"{type(exc).__name__}: {exc}"
            results.append(entry)

        run.example_count = len(examples)
        run.results_json = {"examples": results}
        if error_summary is not None:
            run.status = CalibrationRunStatus.failed
            run.results_json["error"] = error_summary
        else:
            run.metrics_json = compute_agreement_metrics(results)
            run.status = CalibrationRunStatus.completed
        run.completed_at = utc_now()
        self._session.flush()

        AuditService(self._session).record(
            tenant_id=run.tenant_id,
            project_id=run.project_id,
            event_type="evals.calibration.run_completed",
            actor_type=ActorType.system,
            payload={
                "calibration_run_id": str(run.id),
                "status": str(run.status),
                "split": str(run.split),
                "test_set_version": run.test_set_version,
                "judge_model": run.judge_model,
                "metrics": run.metrics_json,
            },
        )
        get_event_bus().publish(
            "evals.calibration.run_completed",
            {
                "calibration_run_id": str(run.id),
                "status": str(run.status),
                "metrics": run.metrics_json,
            },
        )
        logger.info(
            "calibration_run_finished",
            calibration_run_id=str(run.id),
            status=str(run.status),
            metrics=run.metrics_json,
        )
        return run

    def get_run(self, tenant_id: uuid.UUID, run_id: uuid.UUID) -> CalibrationRun:
        run = self._session.scalar(
            select(CalibrationRun).where(
                CalibrationRun.id == run_id, CalibrationRun.tenant_id == tenant_id
            )
        )
        if run is None:
            raise NotFoundError(f"calibration run {run_id} not found")
        return run

    # ------------------------------------------------------------------ #
    def _latest_test_set_version(self, tenant_id: uuid.UUID, rubric_version_id: uuid.UUID) -> int:
        version = self._session.scalar(
            select(func.max(CalibrationExample.test_set_version)).where(
                CalibrationExample.tenant_id == tenant_id,
                CalibrationExample.rubric_version_id == rubric_version_id,
                CalibrationExample.split == CalibrationSplit.test,
            )
        )
        if version is None:
            raise DomainValidationError("no test examples exist for this rubric version")
        return version

    def _examples(self, run: CalibrationRun) -> list[CalibrationExample]:
        return self._split_examples(
            run.tenant_id, run.rubric_version_id, run.split, run.test_set_version
        )

    def _split_examples(
        self,
        tenant_id: uuid.UUID,
        rubric_version_id: uuid.UUID,
        split: CalibrationSplit,
        test_set_version: int | None,
    ) -> list[CalibrationExample]:
        stmt = select(CalibrationExample).where(
            CalibrationExample.tenant_id == tenant_id,
            CalibrationExample.rubric_version_id == rubric_version_id,
            CalibrationExample.split == split,
        )
        if split is CalibrationSplit.test and test_set_version is not None:
            # Test sets are cumulative: v2 = v1 plus additions, never removals.
            stmt = stmt.where(CalibrationExample.test_set_version <= test_set_version)
        return list(self._session.scalars(stmt.order_by(CalibrationExample.created_at)))


def suite_judge_monitoring(session: Session, tenant_id: uuid.UUID, suite_id: uuid.UUID) -> dict:
    """Online monitoring for one suite: observed judge fail rate on production
    eval runs, corrected for judge error when a test-split calibration exists
    for the current judge model (Rogan-Gladen)."""
    judge_rows = session.execute(
        select(ReviewerScore.pass_fail)
        .join(EvalRun, ReviewerScore.eval_run_id == EvalRun.id)
        .where(
            EvalRun.tenant_id == tenant_id,
            EvalRun.eval_suite_id == suite_id,
            ReviewerScore.scored_by_type == ActorType.agent,
        )
    ).all()
    n_obs = len(judge_rows)
    observed = {
        "n_judge_scored": n_obs,
        "observed_fail_rate": None,
        "observed_fail_ci95": None,
    }
    fails = sum(1 for (passed,) in judge_rows if not passed)
    if n_obs:
        observed["observed_fail_rate"] = round(fails / n_obs, 4)
        observed["observed_fail_ci95"] = wilson_interval(fails, n_obs)

    # The rubric version the suite currently judges under: its latest run's.
    rubric_version_id = session.scalar(
        select(EvalRun.rubric_version_id)
        .where(EvalRun.tenant_id == tenant_id, EvalRun.eval_suite_id == suite_id)
        .order_by(EvalRun.created_at.desc())
        .limit(1)
    )
    calibration = None
    corrected = None
    if rubric_version_id is not None:
        run = latest_test_calibration(
            session,
            tenant_id,
            rubric_version_id=rubric_version_id,
            judge_model=get_settings().llm_judge_model,
        )
        if run is not None:
            calibration = {
                "calibration_run_id": str(run.id),
                "judge_model": run.judge_model,
                "test_set_version": run.test_set_version,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                **run.metrics_json,
            }
            tpr, tnr = run.metrics_json.get("tpr"), run.metrics_json.get("tnr")
            if tpr is not None and tnr is not None and observed["observed_fail_rate"] is not None:
                point = rogan_gladen_corrected(observed["observed_fail_rate"], tpr, tnr)
                lo, hi = observed["observed_fail_ci95"]
                corrected = {
                    "corrected_fail_rate": point,
                    # Approximate: propagates only the observed-rate interval
                    # through the correction at point TPR/TNR.
                    "corrected_fail_ci95_approx": (
                        None
                        if point is None
                        else [
                            rogan_gladen_corrected(lo, tpr, tnr),
                            rogan_gladen_corrected(hi, tpr, tnr),
                        ]
                    ),
                    "uninformative_judge": point is None,
                }
    return {
        "eval_suite_id": str(suite_id),
        "judge_model": get_settings().llm_judge_model,
        "observed": observed,
        "calibration": calibration,
        "corrected": corrected,
    }
