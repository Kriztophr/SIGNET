import uuid

from sqlalchemy.orm import Session

from app.environment.models.entities import EnvironmentPromotion, PromotionStatus
from app.environment.promotion.evidence import PromotionEvidenceEvaluator
from app.environment.repositories.environment import EnvironmentRepository
from app.governance.services.audit import AuditService
from app.platform.auth.models import User
from app.platform.errors import ForbiddenError, InvalidStateError
from app.platform.events.bus import get_event_bus
from app.platform.time.clock import utc_now
from app.workflow.models.entities import ActorType


class EnvironmentPromotionService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = EnvironmentRepository(session)
        self._evaluator = PromotionEvidenceEvaluator(session)
        self._audit = AuditService(session)

    def request_promotion(
        self,
        tenant_id: uuid.UUID,
        requested_by: uuid.UUID,
        *,
        version_id: uuid.UUID,
        requirements: dict,
        project_id: uuid.UUID | None = None,
    ) -> EnvironmentPromotion:
        """Creates the promotion and immediately evaluates evidence, landing it in
        approval_pending (promotable) or blocked (fail closed)."""
        version = self._repo.get_version(tenant_id, version_id)
        promotion = EnvironmentPromotion(
            tenant_id=tenant_id,
            project_id=project_id,
            environment_template_version_id=version.id,
            status=PromotionStatus.under_evaluation,
            requested_by=requested_by,
            requested_at=utc_now(),
            requirements_json=requirements,
        )
        self._session.add(promotion)
        self._session.flush()

        evidence, blocking = self._evaluator.evaluate(tenant_id, version.id, requirements)
        promotion.evidence_json = evidence
        if blocking:
            promotion.status = PromotionStatus.blocked
            promotion.decision_reason = "; ".join(blocking)
        else:
            promotion.status = PromotionStatus.approval_pending
            promotion.decision_reason = "all promotion requirements satisfied"
        self._session.flush()

        self._audit.record(
            tenant_id=tenant_id,
            project_id=project_id,
            event_type="environment.promotion.requested",
            actor_type=ActorType.human,
            actor_id=requested_by,
            environment_promotion_id=promotion.id,
            payload={"status": promotion.status, "blocking_reasons": blocking},
        )
        get_event_bus().publish(
            "environment.promotion.requested",
            {
                "environment_promotion_id": str(promotion.id),
                "environment_template_version_id": str(version.id),
                "status": str(promotion.status),
            },
        )
        return promotion

    def approve(
        self, tenant_id: uuid.UUID, promotion_id: uuid.UUID, approver: User
    ) -> EnvironmentPromotion:
        promotion = self._repo.get_promotion(tenant_id, promotion_id)
        if promotion.status is not PromotionStatus.approval_pending:
            raise InvalidStateError(
                f"only a promotion awaiting approval can be approved "
                f"(promotion is {promotion.status})"
            )
        # Re-check evidence at approval time: nothing may have regressed since request.
        evidence, blocking = self._evaluator.evaluate(
            tenant_id, promotion.environment_template_version_id, promotion.requirements_json
        )
        promotion.evidence_json = evidence
        if blocking:
            promotion.status = PromotionStatus.blocked
            promotion.decision_reason = "; ".join(blocking)
            self._session.flush()
            raise ForbiddenError(
                "promotion evidence regressed since request: " + "; ".join(blocking)
            )

        promotion.status = PromotionStatus.approved
        promotion.approved_by = approver.id
        promotion.approved_at = utc_now()
        promotion.decision_reason = "approved on complete evidence"
        self._session.flush()

        self._audit.record(
            tenant_id=tenant_id,
            project_id=promotion.project_id,
            event_type="environment.promotion.approved",
            actor_type=ActorType.human,
            actor_id=approver.id,
            environment_promotion_id=promotion.id,
            payload={
                "environment_template_version_id": str(promotion.environment_template_version_id)
            },
        )
        get_event_bus().publish(
            "environment.promotion.approved",
            {
                "environment_promotion_id": str(promotion.id),
                "environment_template_version_id": str(promotion.environment_template_version_id),
                "approved_by": str(approver.id),
            },
        )
        return promotion
