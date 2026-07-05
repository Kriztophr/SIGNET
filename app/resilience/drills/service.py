import uuid

from sqlalchemy.orm import Session

from app.governance.services.audit import AuditService
from app.platform.errors import DomainValidationError, InvalidStateError
from app.platform.events.bus import get_event_bus
from app.platform.time.clock import utc_now
from app.resilience.models.entities import (
    AiMode,
    DrillStatus,
    FallbackDrill,
    FallbackReadinessAssessment,
)
from app.resilience.repositories.resilience import ResilienceRepository
from app.workflow.models.entities import ActorType


class CapabilityDrillService:
    """Fallback drills: can a team keep operating with AI off, reduced, or delayed?"""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = ResilienceRepository(session)
        self._audit = AuditService(session)

    def start_drill(
        self,
        tenant_id: uuid.UUID,
        triggered_by: uuid.UUID,
        *,
        environment_template_version_id: uuid.UUID,
        drill_type: str,
        ai_mode: AiMode,
        workflow_template_version_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
    ) -> FallbackDrill:
        drill = FallbackDrill(
            tenant_id=tenant_id,
            project_id=project_id,
            environment_template_version_id=environment_template_version_id,
            workflow_template_version_id=workflow_template_version_id,
            drill_type=drill_type,
            ai_mode=ai_mode,
            status=DrillStatus.running,
            started_at=utc_now(),
            triggered_by=triggered_by,
        )
        self._session.add(drill)
        self._session.flush()
        return drill

    def complete_drill(
        self,
        drill: FallbackDrill,
        *,
        readiness_score: float,
        summary: dict,
        evidence: dict,
    ) -> FallbackReadinessAssessment:
        if drill.status is not DrillStatus.running:
            raise InvalidStateError(f"only a running drill can be completed ({drill.status})")
        if not (0 <= readiness_score <= 1):
            raise DomainValidationError("readiness_score must be within [0, 1]")

        drill.status = DrillStatus.completed
        drill.completed_at = utc_now()
        drill.summary_json = summary

        assessment = FallbackReadinessAssessment(
            tenant_id=drill.tenant_id,
            project_id=drill.project_id,
            fallback_drill_id=drill.id,
            readiness_score=readiness_score,
            evidence_json=evidence,
            assessed_at=utc_now(),
        )
        self._session.add(assessment)
        self._session.flush()

        self._audit.record(
            tenant_id=drill.tenant_id,
            project_id=drill.project_id,
            event_type="resilience.drill.completed",
            actor_type=ActorType.system,
            payload={
                "fallback_drill_id": str(drill.id),
                "drill_type": drill.drill_type,
                "ai_mode": str(drill.ai_mode),
                "readiness_score": readiness_score,
            },
        )
        get_event_bus().publish(
            "resilience.drill.completed",
            {
                "fallback_drill_id": str(drill.id),
                "readiness_score": readiness_score,
                "environment_template_version_id": str(drill.environment_template_version_id),
            },
        )
        return assessment
