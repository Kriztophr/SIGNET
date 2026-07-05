import uuid

from sqlalchemy.orm import Session

from app.platform.errors import DomainValidationError
from app.platform.time.clock import utc_now
from app.resilience.models.entities import ReversibilityAssessment


class ReversibilityAssessmentService:
    """Records whether human-led operation can be restored for a scope when
    automation must be reduced or paused (spec 15.2)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def record_assessment(
        self,
        tenant_id: uuid.UUID,
        *,
        scope_type: str,
        scope_ref: str,
        assessment_score: float,
        evidence: dict,
        project_id: uuid.UUID | None = None,
    ) -> ReversibilityAssessment:
        if not (0 <= assessment_score <= 1):
            raise DomainValidationError("assessment_score must be within [0, 1]")
        assessment = ReversibilityAssessment(
            tenant_id=tenant_id,
            project_id=project_id,
            scope_type=scope_type,
            scope_ref=scope_ref,
            assessment_score=assessment_score,
            evidence_json=evidence,
            assessed_at=utc_now(),
        )
        self._session.add(assessment)
        self._session.flush()
        return assessment
