import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.governance.models.entities import AuditEvent
from app.platform.observability.correlation import get_correlation_id
from app.platform.time.clock import utc_now
from app.workflow.models.entities import ActorType


class AuditService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        *,
        tenant_id: uuid.UUID,
        event_type: str,
        actor_type: ActorType,
        actor_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
        workflow_run_id: uuid.UUID | None = None,
        stage_run_id: uuid.UUID | None = None,
        review_task_id: uuid.UUID | None = None,
        eval_run_id: uuid.UUID | None = None,
        environment_promotion_id: uuid.UUID | None = None,
        payload: dict | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            tenant_id=tenant_id,
            project_id=project_id,
            event_type=event_type,
            workflow_run_id=workflow_run_id,
            stage_run_id=stage_run_id,
            review_task_id=review_task_id,
            eval_run_id=eval_run_id,
            environment_promotion_id=environment_promotion_id,
            actor_type=actor_type,
            actor_id=actor_id,
            payload_json=payload or {},
            occurred_at=utc_now(),
            correlation_id=get_correlation_id(),
        )
        self._session.add(event)
        self._session.flush()
        return event

    def query(
        self,
        tenant_id: uuid.UUID,
        *,
        event_type: str | None = None,
        workflow_run_id: uuid.UUID | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        stmt = select(AuditEvent).where(AuditEvent.tenant_id == tenant_id)
        if event_type:
            stmt = stmt.where(AuditEvent.event_type == event_type)
        if workflow_run_id:
            stmt = stmt.where(AuditEvent.workflow_run_id == workflow_run_id)
        stmt = stmt.order_by(AuditEvent.occurred_at.desc()).limit(min(limit, 500))
        return list(self._session.scalars(stmt))
