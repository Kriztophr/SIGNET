import uuid

from sqlalchemy.orm import Session

from app.governance.services.audit import AuditService
from app.platform.errors import DomainValidationError
from app.platform.events.bus import get_event_bus
from app.platform.time.clock import utc_now
from app.resilience.models.entities import (
    ResilienceDecision,
    ResilienceDecisionOutcome,
    ResilienceThreshold,
)
from app.resilience.repositories.resilience import ResilienceRepository
from app.resilience.services.coverage import StrategicCoverageService
from app.workflow.models.entities import ActorType

SUPPORTED_METRICS = ("reversibility_score", "fallback_readiness", "coverage_ratio")


class ResiliencePolicyService:
    """Evaluates resilience thresholds for a scope and records durable decisions.

    Consumed by the environment promotion gate (spec 17.2: resilience thresholds
    must be met where applicable). Fail closed: a threshold whose metric has no
    evidence is a breach, not a skip.
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = ResilienceRepository(session)
        self._coverage = StrategicCoverageService(session)
        self._audit = AuditService(session)

    def create_threshold(
        self,
        tenant_id: uuid.UUID,
        *,
        scope_type: str,
        scope_ref: str,
        metric_name: str,
        min_threshold: float,
        policy_action: str = "block",
        project_id: uuid.UUID | None = None,
    ) -> ResilienceThreshold:
        if metric_name not in SUPPORTED_METRICS:
            raise DomainValidationError(
                f"unsupported metric {metric_name!r}; supported: {', '.join(SUPPORTED_METRICS)}"
            )
        threshold = ResilienceThreshold(
            tenant_id=tenant_id,
            project_id=project_id,
            scope_type=scope_type,
            scope_ref=scope_ref,
            metric_name=metric_name,
            min_threshold=min_threshold,
            policy_action=policy_action,
        )
        self._session.add(threshold)
        self._session.flush()
        return threshold

    def evaluate_scope(
        self, tenant_id: uuid.UUID, scope_type: str, scope_ref: str
    ) -> tuple[list[dict], list[str]]:
        """Evaluates every active threshold on the scope; returns (results, breaches)."""
        results: list[dict] = []
        breaches: list[str] = []
        for threshold in self._repo.active_thresholds_for_scope(tenant_id, scope_type, scope_ref):
            observed = self._observe(tenant_id, threshold)
            if observed is None:
                outcome = ResilienceDecisionOutcome.breach
                reason = (
                    f"resilience metric {threshold.metric_name!r} has no evidence "
                    f"for scope {scope_type}:{scope_ref}"
                )
            elif observed < threshold.min_threshold:
                outcome = ResilienceDecisionOutcome.breach
                reason = (
                    f"resilience metric {threshold.metric_name!r} at {observed} "
                    f"below required {threshold.min_threshold}"
                )
            else:
                outcome = ResilienceDecisionOutcome.passed
                reason = ""

            decision = ResilienceDecision(
                tenant_id=tenant_id,
                project_id=threshold.project_id,
                resilience_threshold_id=threshold.id,
                scope_type=scope_type,
                scope_ref=scope_ref,
                metric_name=threshold.metric_name,
                decision=outcome,
                observed_value=observed,
                evidence_json={"reason": reason} if reason else {},
                decided_at=utc_now(),
            )
            self._session.add(decision)
            results.append(
                {
                    "threshold_id": str(threshold.id),
                    "metric_name": threshold.metric_name,
                    "observed": observed,
                    "required": threshold.min_threshold,
                    "decision": str(outcome),
                }
            )
            if outcome is ResilienceDecisionOutcome.breach:
                breaches.append(reason)
                self._audit.record(
                    tenant_id=tenant_id,
                    project_id=threshold.project_id,
                    event_type="resilience.threshold.breached",
                    actor_type=ActorType.system,
                    payload={
                        "resilience_threshold_id": str(threshold.id),
                        "metric_name": threshold.metric_name,
                        "observed_value": observed,
                        "min_threshold": threshold.min_threshold,
                        "scope_type": scope_type,
                        "scope_ref": scope_ref,
                    },
                )
                get_event_bus().publish(
                    "resilience.threshold.breached",
                    {
                        "resilience_threshold_id": str(threshold.id),
                        "metric_name": threshold.metric_name,
                        "scope_type": scope_type,
                        "scope_ref": scope_ref,
                    },
                )
        self._session.flush()
        return results, breaches

    def _observe(self, tenant_id: uuid.UUID, threshold: ResilienceThreshold) -> float | None:
        if threshold.metric_name == "reversibility_score":
            assessment = self._repo.latest_reversibility_for_scope(
                tenant_id, threshold.scope_type, threshold.scope_ref
            )
            return assessment.assessment_score if assessment else None
        if threshold.metric_name == "fallback_readiness":
            env_version_id = None
            if threshold.scope_type == "environment_template_version":
                env_version_id = uuid.UUID(threshold.scope_ref)
            readiness = self._repo.latest_readiness_for_environment(tenant_id, env_version_id)
            return readiness.readiness_score if readiness else None
        if threshold.metric_name == "coverage_ratio":
            return self._coverage.minimum_coverage_ratio(tenant_id)
        return None
