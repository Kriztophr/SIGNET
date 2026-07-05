"""Promotion evidence gathering (spec 17.2 / 17.3).

An environment version may only be approved on evidence. This module reads the
evals and governance records tied to the version and produces a structured
evidence package plus a fail-closed list of blocking reasons. The environment
module depends on evals/governance here — never the reverse.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evals.models.entities import (
    DisagreementRecord,
    DriftSignal,
    EvalDecision,
    EvalDecisionType,
    EvalRun,
    EvalRunStatus,
    RegressionPack,
    RegressionPackRun,
)

# Fail-closed defaults: absent an explicit requirement, the strict rule applies.
DEFAULT_MIN_REGRESSION_PASS_RATE = 1.0


class PromotionEvidenceEvaluator:
    def __init__(self, session: Session) -> None:
        self._session = session

    def evaluate(
        self, tenant_id: uuid.UUID, version_id: uuid.UUID, requirements: dict
    ) -> tuple[dict, list[str]]:
        """Returns (evidence_json, blocking_reasons). Empty reasons ⇒ promotable."""
        blocking: list[str] = []
        min_pass_rate = requirements.get(
            "min_regression_pass_rate", DEFAULT_MIN_REGRESSION_PASS_RATE
        )
        pack_ids = [uuid.UUID(p) for p in requirements.get("regression_pack_ids", [])]

        regression_evidence = self._regression_evidence(
            tenant_id, pack_ids, min_pass_rate, blocking
        )
        eval_evidence = self._eval_evidence(
            tenant_id, version_id, requirements.get("require_eval_evidence", True), blocking
        )
        disagreement_count = self._open_disagreements(version_id)
        if requirements.get("require_no_open_disagreements", True) and disagreement_count:
            blocking.append(f"{disagreement_count} unresolved review disagreement(s)")
        drift_count = self._active_drift(tenant_id, pack_ids, requirements, blocking)

        evidence = {
            "regression_packs": regression_evidence,
            "eval_runs": eval_evidence,
            "open_disagreements": disagreement_count,
            "active_drift_signals": drift_count,
            # Resilience thresholds land in phase 9; recorded as a seam until then.
            "resilience": "not_evaluated",
            "blocking_reasons": list(blocking),
        }
        return evidence, blocking

    def _regression_evidence(
        self,
        tenant_id: uuid.UUID,
        pack_ids: list[uuid.UUID],
        min_pass_rate: float,
        blocking: list[str],
    ) -> list[dict]:
        results = []
        for pack_id in pack_ids:
            pack = self._session.scalar(
                select(RegressionPack).where(
                    RegressionPack.id == pack_id, RegressionPack.tenant_id == tenant_id
                )
            )
            if pack is None:
                blocking.append(f"regression pack {pack_id} not found")
                results.append({"pack_id": str(pack_id), "found": False, "passed": False})
                continue
            latest = self._session.scalar(
                select(RegressionPackRun)
                .where(RegressionPackRun.regression_pack_id == pack.id)
                .order_by(RegressionPackRun.completed_at.desc())
                .limit(1)
            )
            if latest is None:
                blocking.append(f"regression pack {pack.name!r} has no completed run")
                results.append({"pack_id": str(pack_id), "run": None, "passed": False})
                continue
            passed = latest.pass_rate >= min_pass_rate
            if not passed:
                blocking.append(
                    f"regression pack {pack.name!r} pass rate {latest.pass_rate} "
                    f"below required {min_pass_rate}"
                )
            results.append(
                {
                    "pack_id": str(pack_id),
                    "regression_pack_run_id": str(latest.id),
                    "pass_rate": latest.pass_rate,
                    "passed": passed,
                }
            )
        return results

    def _eval_evidence(
        self,
        tenant_id: uuid.UUID,
        version_id: uuid.UUID,
        require_evidence: bool,
        blocking: list[str],
    ) -> dict:
        runs = list(
            self._session.scalars(
                select(EvalRun).where(
                    EvalRun.tenant_id == tenant_id,
                    EvalRun.environment_template_version_id == version_id,
                )
            )
        )
        summary = {"total": len(runs), "passed": 0, "failed": 0, "incomplete": 0, "adjudication": 0}
        for run in runs:
            if run.status is not EvalRunStatus.completed:
                summary["incomplete"] += 1
                continue
            decision = self._session.scalar(
                select(EvalDecision).where(EvalDecision.eval_run_id == run.id)
            )
            if decision is None or decision.decision_type is EvalDecisionType.needs_adjudication:
                summary["adjudication"] += 1
            elif decision.decision_type is EvalDecisionType.passed:
                summary["passed"] += 1
            else:
                summary["failed"] += 1

        if require_evidence and summary["total"] == 0:
            blocking.append("no eval runs linked to this environment version")
        if summary["failed"]:
            blocking.append(f"{summary['failed']} failed eval run(s) on this version")
        if summary["incomplete"]:
            blocking.append(f"{summary['incomplete']} eval run(s) still awaiting scores")
        if summary["adjudication"]:
            blocking.append(f"{summary['adjudication']} eval run(s) needing adjudication")
        return summary

    def _open_disagreements(self, version_id: uuid.UUID) -> int:
        return len(
            self._session.scalars(
                select(DisagreementRecord.id)
                .join(EvalRun, DisagreementRecord.eval_run_id == EvalRun.id)
                .where(
                    EvalRun.environment_template_version_id == version_id,
                    DisagreementRecord.status == "open",
                )
            ).all()
        )

    def _active_drift(
        self,
        tenant_id: uuid.UUID,
        pack_ids: list[uuid.UUID],
        requirements: dict,
        blocking: list[str],
    ) -> int:
        # Drift on any scope covered by the gated regression packs blocks promotion.
        scopes: set[tuple[str, str]] = set()
        for pack_id in pack_ids:
            pack = self._session.get(RegressionPack, pack_id)
            if pack is not None:
                scopes.add((pack.scope_type, pack.scope_ref))
        explicit = requirements.get("drift_scope")
        if explicit:
            scopes.add((explicit["scope_type"], explicit["scope_ref"]))

        count = 0
        for scope_type, scope_ref in scopes:
            count += len(
                self._session.scalars(
                    select(DriftSignal.id).where(
                        DriftSignal.tenant_id == tenant_id,
                        DriftSignal.scope_type == scope_type,
                        DriftSignal.scope_ref == scope_ref,
                    )
                ).all()
            )
        if count:
            blocking.append(f"{count} active drift signal(s) on gated scopes")
        return count
