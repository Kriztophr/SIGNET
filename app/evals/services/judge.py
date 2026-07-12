"""LLM-judge scoring of eval runs (spec §28.8; charter 2026-07-08).

The judge is a calibrated instrument, never an authority: it records an
advisory agent-authored ReviewerScore against the same rubric humans use, but
it does not count toward min_reviewers and casts no vote in the decision.
Humans remain the deciders; the judge's value is coverage and an agreement
signal.

Calibration loop: each suite opts in via config_json["llm_judge"] and sets a
sampling rate. When the human decision lands, the judge's verdict is compared
against it (scoring.py records the agreement in the decision metrics). If
rolling agreement over the last `window` decided runs drops below
`agreement_threshold`, sampling auto-widens to 100% and each further
disagreement emits a judge_human_disagreement DriftSignal — a drifting judge
gets MORE human oversight, fail-open toward humans.

Failure philosophy: the judge is advisory, so any failure (no key, budget cap,
provider error, malformed output) is a logged no-op. The eval run is never
touched; human scoring proceeds exactly as if there were no judge.
"""

from __future__ import annotations

import json
import random
import re
import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evals.models.entities import (
    DriftSignal,
    EvalDecision,
    EvalDecisionType,
    EvalRun,
    EvalRunStatus,
    EvalSuite,
    ReviewerScore,
)
from app.evals.repositories.evals import EvalsRepository
from app.evals.rubrics.service import validate_and_score
from app.governance.services.audit import AuditService
from app.platform.events.bus import get_event_bus
from app.platform.llm.adapter import get_llm_adapter
from app.platform.llm.budget import LLMUsageLedger
from app.platform.settings.config import get_settings
from app.platform.storage.service import StorageService
from app.platform.time.clock import utc_now
from app.workflow.models.entities import ActorType

logger = structlog.get_logger(__name__)

# One stable reviewer identity for the judge: the (eval_run_id, reviewer_id)
# unique constraint then guarantees at most one judge score per run.
JUDGE_REVIEWER_ID = uuid.uuid5(uuid.NAMESPACE_URL, "icm://platform/llm-judge")

DEFAULT_SAMPLING_RATE = 0.25
DEFAULT_AGREEMENT_THRESHOLD = 0.8
DEFAULT_AGREEMENT_WINDOW = 20

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)

_SYSTEM_TEMPLATE = """\
You are an LLM judge inside a governed evals platform. Score the submitted
work against the rubric below exactly as a careful human reviewer would. Your
score is advisory: humans decide, and your agreement with them is tracked.

## Rubric criteria (score each key)
{criteria}

## Score scale
Every criterion score must be a number between {scale_min} and {scale_max}.

## Output format (mandatory)
Reply with a single JSON object and nothing else — no markdown fences, no
commentary:
{{"scores": {{{score_keys}}}, "rationale": "<2-4 sentences justifying the scores>"}}"""


DEFAULT_GATE_MIN_TPR = 0.7
DEFAULT_GATE_MIN_TNR = 0.7


@dataclass
class JudgeConfig:
    enabled: bool = False
    sampling_rate: float = DEFAULT_SAMPLING_RATE
    agreement_threshold: float = DEFAULT_AGREEMENT_THRESHOLD
    window: int = DEFAULT_AGREEMENT_WINDOW
    # Calibration gate (stage 4b): when enabled, the judge only scores if the
    # current judge config has a completed test-split calibration run meeting
    # these thresholds for the run's rubric version. Fail closed — an
    # uncalibrated judge stays silent; humans are unaffected.
    gate_enabled: bool = False
    gate_min_tpr: float = DEFAULT_GATE_MIN_TPR
    gate_min_tnr: float = DEFAULT_GATE_MIN_TNR


def judge_config(suite: EvalSuite) -> JudgeConfig:
    raw = suite.config_json.get("llm_judge") or {}
    if not isinstance(raw, dict):
        return JudgeConfig()
    gate = raw.get("calibration_gate") or {}
    if not isinstance(gate, dict):
        gate = {}
    return JudgeConfig(
        enabled=bool(raw.get("enabled", False)),
        sampling_rate=float(raw.get("sampling_rate", DEFAULT_SAMPLING_RATE)),
        agreement_threshold=float(raw.get("agreement_threshold", DEFAULT_AGREEMENT_THRESHOLD)),
        window=int(raw.get("window", DEFAULT_AGREEMENT_WINDOW)),
        gate_enabled=bool(gate.get("enabled", False)),
        gate_min_tpr=float(gate.get("min_tpr", DEFAULT_GATE_MIN_TPR)),
        gate_min_tnr=float(gate.get("min_tnr", DEFAULT_GATE_MIN_TNR)),
    )


def build_judge_system(rubric_version) -> str:
    """The judging prompt for a rubric version — shared by production judging
    and calibration runs, so calibration measures the prompt that actually runs."""
    criteria_lines = "\n".join(
        f"- {c['key']} (weight {c.get('weight', 1)}): {c.get('description', '')}"
        for c in rubric_version.criteria_json
    )
    score_keys = ", ".join(f'"{c["key"]}": <number>' for c in rubric_version.criteria_json)
    return _SYSTEM_TEMPLATE.format(
        criteria=criteria_lines,
        scale_min=rubric_version.score_scale_json["min"],
        scale_max=rubric_version.score_scale_json["max"],
        score_keys=score_keys,
    )


def parse_judge_response(text: str) -> tuple[dict, str]:
    match = _JSON_BLOCK.search(text)
    if match is None:
        raise ValueError("judge response contained no JSON object")
    payload = json.loads(match.group(0))
    scores = payload.get("scores")
    if not isinstance(scores, dict) or not scores:
        raise ValueError("judge response missing a 'scores' object")
    rationale = payload.get("rationale") or "(judge provided no rationale)"
    return scores, str(rationale)


def eval_target_content(session: Session, storage: StorageService, run: EvalRun) -> str:
    """The work under judgment: the target artifact, or every latest artifact
    of the target stage run. Shared by judging and calibration harvesting so
    golden examples snapshot exactly what the judge would have seen."""
    from app.workflow.repositories.workflow import WorkflowRepository

    def read(ref: str) -> str:
        try:
            return storage.get_text(ref)
        except Exception:  # noqa: BLE001 — a missing blob degrades, not crashes
            return "(unavailable)"

    workflow_repo = WorkflowRepository(session)
    if run.artifact_id is not None:
        artifact = workflow_repo.get_artifact(run.tenant_id, run.artifact_id)
        content = read(artifact.storage_uri)
        return f"# Artifact under evaluation — {artifact.artifact_role}\n{content}"
    if run.stage_run_id is not None:
        latest = workflow_repo.latest_artifacts_by_role(run.stage_run_id)
        if not latest:
            return "# Stage under evaluation\n(no artifacts submitted for this stage)"
        sections = [
            f"# Artifact — {role} (v{artifact.version_number})\n" + read(artifact.storage_uri)
            for role, artifact in sorted(latest.items())
        ]
        return "\n\n".join(sections)
    raise ValueError(f"judge cannot read target type {run.target_ref_type}")


def recent_agreement(
    session: Session, suite_id: uuid.UUID, *, window: int
) -> tuple[float | None, int]:
    """Judge-vs-human agreement over the last `window` decided runs of this
    suite that have a judge score. None when there is no history yet."""
    rows = session.execute(
        select(ReviewerScore.pass_fail, EvalDecision.decision_type)
        .join(EvalRun, ReviewerScore.eval_run_id == EvalRun.id)
        .join(EvalDecision, EvalDecision.eval_run_id == EvalRun.id)
        .where(
            EvalRun.eval_suite_id == suite_id,
            ReviewerScore.scored_by_type == ActorType.agent,
            EvalDecision.decision_type.in_([EvalDecisionType.passed, EvalDecisionType.failed]),
        )
        .order_by(EvalRun.completed_at.desc())
        .limit(window)
    ).all()
    if not rows:
        return None, 0
    agreed = sum(
        1
        for judge_pass, decision_type in rows
        if judge_pass == (decision_type is EvalDecisionType.passed)
    )
    return agreed / len(rows), len(rows)


class JudgeEvalService:
    def __init__(self, session: Session, storage: StorageService) -> None:
        self._session = session
        self._storage = storage
        self._repo = EvalsRepository(session)

    def score_run(self, eval_run_id: uuid.UUID) -> ReviewerScore | None:
        run = self._session.scalar(select(EvalRun).where(EvalRun.id == eval_run_id))
        if run is None:
            raise LookupError(f"eval run {eval_run_id} not found")

        log = logger.bind(eval_run_id=str(eval_run_id), eval_suite_id=str(run.eval_suite_id))
        cfg = judge_config(run.suite)
        if not cfg.enabled:
            return None
        if run.status is not EvalRunStatus.awaiting_human_score:
            log.info("judge_skipped", reason=f"run is {run.status}")
            return None
        if self._repo.has_score_from(run.id, JUDGE_REVIEWER_ID):
            log.info("judge_skipped", reason="already judge-scored")
            return None

        if cfg.gate_enabled:
            # Local import: calibration consumes this module's prompt builders.
            from app.evals.calibration.service import calibration_gate_check

            passed_gate, gate_reason = calibration_gate_check(
                self._session,
                run.tenant_id,
                rubric_version_id=run.rubric_version_id,
                judge_model=get_settings().llm_judge_model,
                min_tpr=cfg.gate_min_tpr,
                min_tnr=cfg.gate_min_tnr,
            )
            if not passed_gate:
                log.warning("judge_skipped", reason=f"calibration gate: {gate_reason}")
                return None

        agreement, _ = recent_agreement(self._session, run.eval_suite_id, window=cfg.window)
        widened = agreement is not None and agreement < cfg.agreement_threshold
        effective_rate = 1.0 if widened else cfg.sampling_rate
        if random.random() >= effective_rate:
            log.info("judge_skipped", reason="not sampled", sampling_rate=effective_rate)
            return None

        try:
            ledger = LLMUsageLedger(self._session)
            ledger.ensure_within_budget()
            rubric_version = run.rubric_version
            settings = get_settings()
            result = get_llm_adapter("judge").complete(
                model=settings.llm_judge_model,
                system=self._build_system(rubric_version),
                user_content=self._target_content(run),
                max_tokens=settings.llm_max_output_tokens,
            )
            ledger.record(
                run.tenant_id,
                result,
                purpose="judge",
                workflow_run_id=run.workflow_run_id,
                stage_run_id=run.stage_run_id,
                eval_run_id=run.id,
            )
            scores, rationale = self._parse_response(result.text)
            weighted_total, passed = validate_and_score(rubric_version, scores)
        except Exception as exc:  # noqa: BLE001 — advisory: never block human scoring
            log.warning("judge_scoring_failed", error=f"{type(exc).__name__}: {exc}")
            return None

        score = ReviewerScore(
            eval_run_id=run.id,
            rubric_version_id=rubric_version.id,
            reviewer_id=JUDGE_REVIEWER_ID,
            scored_by_type=ActorType.agent,
            score_json={
                **scores,
                "_weighted_total": weighted_total,
                "_judge_model": result.model,
            },
            pass_fail=passed,
            rationale=rationale,
            submitted_at=utc_now(),
        )
        self._session.add(score)
        self._session.flush()

        AuditService(self._session).record(
            tenant_id=run.tenant_id,
            project_id=run.project_id,
            event_type="evals.judge.scored",
            actor_type=ActorType.agent,
            workflow_run_id=run.workflow_run_id,
            stage_run_id=run.stage_run_id,
            eval_run_id=run.id,
            payload={
                "pass_fail": passed,
                "weighted_total": weighted_total,
                "model": result.model,
                "sampling_widened": widened,
            },
        )
        get_event_bus().publish(
            "evals.judge.scored",
            {"eval_run_id": str(run.id), "pass_fail": passed, "sampling_widened": widened},
        )
        log.info("judge_scored", pass_fail=passed, sampling_widened=widened)
        return score

    # ------------------------------------------------------------------ #
    def _build_system(self, rubric_version) -> str:
        return build_judge_system(rubric_version)

    def _target_content(self, run: EvalRun) -> str:
        return eval_target_content(self._session, self._storage, run)

    @staticmethod
    def _parse_response(text: str) -> tuple[dict, str]:
        return parse_judge_response(text)


def record_judge_agreement(
    session: Session, run: EvalRun, decision: EvalDecision, judge_score: ReviewerScore
) -> None:
    """Called by the scoring service once the human decision exists. On a
    disagreement that drags rolling agreement below the suite's threshold,
    emit a DriftSignal — the auto-widened sampling is already implied by
    recent_agreement() on the next judge call."""
    if decision.decision_type not in (EvalDecisionType.passed, EvalDecisionType.failed):
        return
    agrees = judge_score.pass_fail == (decision.decision_type is EvalDecisionType.passed)
    if agrees:
        return

    cfg = judge_config(run.suite)
    agreement, sample_size = recent_agreement(session, run.eval_suite_id, window=cfg.window)
    if agreement is None or agreement >= cfg.agreement_threshold:
        return

    session.add(
        DriftSignal(
            tenant_id=run.tenant_id,
            project_id=run.project_id,
            scope_type="eval_suite",
            scope_ref=str(run.eval_suite_id),
            signal_type="judge_human_disagreement",
            signal_strength=round(1 - agreement, 3),
            evidence_json={
                "eval_run_id": str(run.id),
                "judge_pass_fail": judge_score.pass_fail,
                "human_decision": str(decision.decision_type),
                "rolling_agreement": round(agreement, 3),
                "window": cfg.window,
                "sample_size": sample_size,
                "agreement_threshold": cfg.agreement_threshold,
                "effect": "judge sampling widened to 100% until agreement recovers",
            },
            detected_at=utc_now(),
        )
    )
    session.flush()
    get_event_bus().publish(
        "evals.drift.detected",
        {
            "scope_type": "eval_suite",
            "scope_ref": str(run.eval_suite_id),
            "signal_type": "judge_human_disagreement",
            "signal_strength": round(1 - agreement, 3),
        },
    )
    logger.warning(
        "judge_human_disagreement_drift",
        eval_suite_id=str(run.eval_suite_id),
        rolling_agreement=agreement,
    )
