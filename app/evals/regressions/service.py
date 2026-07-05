import uuid

from sqlalchemy.orm import Session

from app.evals.models.entities import (
    Baseline,
    DriftSignal,
    EvalDecisionType,
    RegressionPack,
    RegressionPackRun,
    RegressionPackRunStatus,
)
from app.evals.repositories.evals import EvalsRepository
from app.governance.services.audit import AuditService
from app.platform.errors import DomainValidationError
from app.platform.events.bus import get_event_bus
from app.platform.time.clock import utc_now
from app.workflow.models.entities import ActorType


class BaselineService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_baseline(
        self,
        tenant_id: uuid.UUID,
        *,
        name: str,
        scope_type: str,
        scope_ref: str,
        baseline_data: dict,
        project_id: uuid.UUID | None = None,
    ) -> Baseline:
        baseline = Baseline(
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            scope_type=scope_type,
            scope_ref=scope_ref,
            baseline_data_json=baseline_data,
        )
        self._session.add(baseline)
        self._session.flush()
        return baseline


class RegressionPackService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = EvalsRepository(session)
        self._audit = AuditService(session)

    def create_pack(
        self,
        tenant_id: uuid.UUID,
        *,
        name: str,
        description: str,
        eval_suite_ids: list[uuid.UUID],
        scope_type: str,
        scope_ref: str,
        project_id: uuid.UUID | None = None,
    ) -> RegressionPack:
        if not eval_suite_ids:
            raise DomainValidationError("a regression pack needs at least one eval suite")
        for suite_id in eval_suite_ids:
            self._repo.get_suite(tenant_id, suite_id)  # 404 on unknown/foreign suites
        pack = RegressionPack(
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            description=description,
            eval_suite_refs_json=[str(s) for s in eval_suite_ids],
            scope_type=scope_type,
            scope_ref=scope_ref,
        )
        self._session.add(pack)
        self._session.flush()
        return pack

    def run_pack(
        self, tenant_id: uuid.UUID, pack_id: uuid.UUID, triggered_by: uuid.UUID
    ) -> RegressionPackRun:
        """Aggregates each referenced suite's latest completed decision.

        Fail closed: a suite with no completed decision counts as failing and is
        recorded as missing_evidence — never silently skipped.
        """
        pack = self._repo.get_regression_pack(tenant_id, pack_id)
        started = utc_now()
        suite_results: list[dict] = []
        pass_count = 0
        for raw_suite_id in pack.eval_suite_refs_json:
            suite_id = uuid.UUID(raw_suite_id)
            decision = self._repo.latest_decision_for_suite(suite_id)
            if decision is None:
                suite_results.append({"eval_suite_id": raw_suite_id, "outcome": "missing_evidence"})
                continue
            passed = decision.decision_type is EvalDecisionType.passed
            pass_count += 1 if passed else 0
            suite_results.append(
                {
                    "eval_suite_id": raw_suite_id,
                    "eval_run_id": str(decision.eval_run_id),
                    "decision_type": str(decision.decision_type),
                    "outcome": "pass" if passed else "fail",
                }
            )

        pass_rate = pass_count / len(suite_results)
        pack_run = RegressionPackRun(
            regression_pack_id=pack.id,
            status=RegressionPackRunStatus.completed,
            results_json={"suites": suite_results},
            pass_rate=pass_rate,
            started_at=started,
            completed_at=utc_now(),
            triggered_by=triggered_by,
        )
        self._session.add(pack_run)
        self._session.flush()

        self._detect_drift(pack, pack_run)
        return pack_run

    def _detect_drift(self, pack: RegressionPack, pack_run: RegressionPackRun) -> None:
        baseline = self._repo.baseline_for_scope(pack.tenant_id, pack.scope_type, pack.scope_ref)
        if baseline is None:
            return
        expected = baseline.baseline_data_json.get("pass_rate")
        if not isinstance(expected, int | float) or pack_run.pass_rate >= expected:
            return

        signal = DriftSignal(
            tenant_id=pack.tenant_id,
            project_id=pack.project_id,
            scope_type=pack.scope_type,
            scope_ref=pack.scope_ref,
            signal_type="regression_pass_rate_drop",
            signal_strength=expected - pack_run.pass_rate,
            evidence_json={
                "regression_pack_id": str(pack.id),
                "regression_pack_run_id": str(pack_run.id),
                "baseline_id": str(baseline.id),
                "baseline_pass_rate": expected,
                "observed_pass_rate": pack_run.pass_rate,
            },
            detected_at=utc_now(),
        )
        self._session.add(signal)
        self._session.flush()

        self._audit.record(
            tenant_id=pack.tenant_id,
            project_id=pack.project_id,
            event_type="evals.drift.detected",
            actor_type=ActorType.system,
            payload=signal.evidence_json,
        )
        get_event_bus().publish(
            "evals.drift.detected",
            {
                "drift_signal_id": str(signal.id),
                "scope_type": pack.scope_type,
                "scope_ref": pack.scope_ref,
                "signal_strength": signal.signal_strength,
            },
        )
