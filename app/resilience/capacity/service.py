import uuid

from sqlalchemy.orm import Session

from app.governance.services.audit import AuditService
from app.platform.auth.models import User
from app.platform.errors import DomainValidationError, InvalidStateError
from app.platform.events.bus import get_event_bus
from app.platform.observability.correlation import get_correlation_id
from app.platform.time.clock import utc_now
from app.resilience.models.entities import (
    CapabilityRubric,
    CapabilityStatus,
    CapacityDimension,
    CapacityDimensionScore,
    CriticalCapability,
    HumanCapacityEvalCase,
    HumanCapacityEvalSuite,
    HumanCapacityRun,
    HumanCapacityRunStatus,
    ReviewerCompetencyRecord,
    SubjectType,
)
from app.resilience.repositories.resilience import ResilienceRepository
from app.workflow.models.entities import ActorType

ALL_DIMENSIONS = [d.value for d in CapacityDimension]


class CapacityEvaluationService:
    """Measures whether a subject can still verify, override, and reconstruct
    critical work (spec 15.2), and keeps capability profiles current."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = ResilienceRepository(session)
        self._audit = AuditService(session)

    def create_capability(
        self,
        tenant_id: uuid.UUID,
        *,
        name: str,
        domain: str,
        criticality_level: str,
        description: str = "",
        minimum_required_count: int = 1,
        project_id: uuid.UUID | None = None,
    ) -> CriticalCapability:
        if minimum_required_count < 1:
            raise DomainValidationError("minimum_required_count must be >= 1")
        capability = CriticalCapability(
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            domain=domain,
            criticality_level=criticality_level,
            description=description,
            minimum_required_count=minimum_required_count,
        )
        self._session.add(capability)
        self._session.flush()
        return capability

    def create_suite(
        self,
        tenant_id: uuid.UUID,
        created_by: uuid.UUID,
        *,
        name: str,
        critical_capability_id: uuid.UUID,
        rubric_name: str,
        rubric_thresholds: dict,
        required_dimensions: list[str] | None = None,
        cases: list[dict] | None = None,
        project_id: uuid.UUID | None = None,
    ) -> HumanCapacityEvalSuite:
        capability = self._repo.get_capability(tenant_id, critical_capability_id)
        required = required_dimensions or ALL_DIMENSIONS
        self._validate_rubric(rubric_thresholds, required)

        rubric = CapabilityRubric(
            tenant_id=tenant_id,
            project_id=project_id,
            name=rubric_name,
            thresholds_json=rubric_thresholds,
        )
        self._session.add(rubric)
        self._session.flush()

        suite = HumanCapacityEvalSuite(
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            critical_capability_id=capability.id,
            capability_rubric_id=rubric.id,
            config_json={"required_dimensions": required},
            created_by=created_by,
        )
        self._session.add(suite)
        self._session.flush()

        for index, case in enumerate(cases or []):
            order_index = case.get("order_index")
            self._session.add(
                HumanCapacityEvalCase(
                    human_capacity_eval_suite_id=suite.id,
                    name=case["name"],
                    instruction=case["instruction"],
                    dimension=CapacityDimension(case["dimension"]),
                    order_index=order_index if order_index is not None else index,
                )
            )
        self._session.flush()
        return suite

    @staticmethod
    def _validate_rubric(thresholds: dict, required_dimensions: list[str]) -> None:
        unknown = set(required_dimensions) - set(ALL_DIMENSIONS)
        if unknown:
            raise DomainValidationError(f"unknown capacity dimensions: {sorted(unknown)}")
        missing = [d for d in required_dimensions if d not in thresholds]
        if missing:
            raise DomainValidationError(
                f"rubric thresholds missing required dimensions: {', '.join(missing)}"
            )
        for dimension, value in thresholds.items():
            if dimension not in ALL_DIMENSIONS:
                raise DomainValidationError(f"unknown dimension {dimension!r} in thresholds")
            if not isinstance(value, int | float) or not (0 <= value <= 1):
                raise DomainValidationError(
                    f"threshold for {dimension!r} must be a number in [0, 1]"
                )

    def create_run(
        self,
        tenant_id: uuid.UUID,
        triggered_by: uuid.UUID,
        *,
        suite_id: uuid.UUID,
        subject_type: SubjectType,
        subject_ref_id: uuid.UUID,
        workflow_template_version_id: uuid.UUID | None = None,
        environment_template_version_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
    ) -> HumanCapacityRun:
        suite = self._repo.get_suite(tenant_id, suite_id)
        run = HumanCapacityRun(
            tenant_id=tenant_id,
            project_id=project_id,
            human_capacity_eval_suite_id=suite.id,
            subject_type=subject_type,
            subject_ref_id=subject_ref_id,
            workflow_template_version_id=workflow_template_version_id,
            environment_template_version_id=environment_template_version_id,
            started_at=utc_now(),
            triggered_by=triggered_by,
            correlation_id=get_correlation_id(),
        )
        self._session.add(run)
        self._session.flush()
        return run

    def submit_score(
        self,
        run: HumanCapacityRun,
        assessor: User,
        *,
        dimension: CapacityDimension,
        score: float,
        evidence: dict,
    ) -> CapacityDimensionScore:
        if run.status is not HumanCapacityRunStatus.awaiting_scores:
            raise InvalidStateError(f"run is not awaiting scores (status {run.status})")
        if not (0 <= score <= 1):
            raise DomainValidationError("score must be within [0, 1]")
        if any(existing.dimension is dimension for existing in run.scores):
            raise InvalidStateError(f"dimension {dimension} is already scored for this run")

        record = CapacityDimensionScore(
            human_capacity_run_id=run.id,
            dimension=dimension,
            score=score,
            evidence_json=evidence,
            assessed_by=assessor.id,
        )
        self._session.add(record)
        self._session.flush()
        self._session.refresh(run, ["scores"])

        required = run.suite.config_json.get("required_dimensions", ALL_DIMENSIONS)
        scored = {s.dimension.value: s.score for s in run.scores}
        if set(required) <= set(scored):
            self._complete_run(run, required, scored)
        return record

    def _complete_run(
        self, run: HumanCapacityRun, required: list[str], scored: dict[str, float]
    ) -> None:
        thresholds = run.suite.rubric.thresholds_json
        qualified = all(scored[dim] >= thresholds[dim] for dim in required)

        run.status = HumanCapacityRunStatus.completed
        run.completed_at = utc_now()
        run.qualified = qualified

        capability = self._repo.get_capability(run.tenant_id, run.suite.critical_capability_id)
        profile = self._repo.get_or_create_profile(capability, run.subject_type, run.subject_ref_id)
        profile.current_status = (
            CapabilityStatus.qualified if qualified else CapabilityStatus.not_qualified
        )
        profile.last_assessed_at = utc_now()

        if run.subject_type is SubjectType.person:
            self._session.add(
                ReviewerCompetencyRecord(
                    tenant_id=run.tenant_id,
                    project_id=run.project_id,
                    reviewer_id=run.subject_ref_id,
                    critical_capability_id=capability.id,
                    human_capacity_run_id=run.id,
                    status=profile.current_status,
                )
            )
        self._session.flush()

        self._audit.record(
            tenant_id=run.tenant_id,
            project_id=run.project_id,
            event_type="resilience.capacity.assessed",
            actor_type=ActorType.system,
            payload={
                "human_capacity_run_id": str(run.id),
                "critical_capability_id": str(capability.id),
                "subject_type": str(run.subject_type),
                "subject_ref_id": str(run.subject_ref_id),
                "qualified": qualified,
                "scores": scored,
            },
        )
        get_event_bus().publish(
            "resilience.capacity.assessed",
            {
                "human_capacity_run_id": str(run.id),
                "critical_capability_id": str(capability.id),
                "qualified": qualified,
            },
        )
