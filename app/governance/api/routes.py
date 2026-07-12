import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.governance.audit.evidence_pack import EvidencePackBuilder
from app.governance.models.entities import ReviewTaskStatus
from app.governance.schemas.governance import (
    AuditEventOut,
    DecisionRequest,
    EditDecisionRequest,
    PolicyRuleCreate,
    PolicyRuleOut,
    ReviewTaskOut,
)
from app.governance.services.audit import AuditService
from app.governance.services.policies import PolicyService
from app.governance.services.reviews import ReviewTaskService
from app.platform.auth.dependencies import get_current_user, require_roles
from app.platform.auth.models import Role, User
from app.platform.db.session import get_db
from app.platform.storage.service import StorageService, get_storage
from app.workflow.models.entities import ActorType

router = APIRouter(prefix="/governance", tags=["governance"])

_reviewer = require_roles(Role.reviewer)
_admin = require_roles()  # admin only: require_roles always allows admin
_auditor = require_roles(Role.auditor)


@router.post("/policies", response_model=PolicyRuleOut, status_code=201)
def create_policy(
    body: PolicyRuleCreate,
    user: User = Depends(_admin),
    db: Session = Depends(get_db),
) -> PolicyRuleOut:
    rule = PolicyService(db).create_rule(
        user.tenant_id,
        user.id,
        name=body.name,
        scope_type=body.scope_type,
        scope_ref=body.scope_ref,
        rule_type=body.rule_type,
        rule_expression=body.rule_expression,
        severity=body.severity,
        project_id=body.project_id,
    )
    db.commit()
    return rule


@router.get("/policies/{rule_id}", response_model=PolicyRuleOut)
def get_policy(
    rule_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PolicyRuleOut:
    return PolicyService(db).get_rule(user.tenant_id, rule_id)


@router.get("/review-tasks", response_model=list[ReviewTaskOut])
def list_review_tasks(
    status: ReviewTaskStatus | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
) -> list[ReviewTaskOut]:
    return ReviewTaskService(db, storage).list_tasks(user.tenant_id, status)


@router.get("/review-tasks/{task_id}", response_model=ReviewTaskOut)
def get_review_task(
    task_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
) -> ReviewTaskOut:
    return ReviewTaskService(db, storage).get_task(user.tenant_id, task_id)


@router.post("/review-tasks/{task_id}/approve", response_model=ReviewTaskOut)
def approve_review_task(
    task_id: uuid.UUID,
    body: DecisionRequest,
    user: User = Depends(_reviewer),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
) -> ReviewTaskOut:
    service = ReviewTaskService(db, storage)
    task = service.approve(service.get_task(user.tenant_id, task_id), user, body.rationale)
    db.commit()
    return task


@router.post("/review-tasks/{task_id}/edit", response_model=ReviewTaskOut)
def edit_review_task(
    task_id: uuid.UUID,
    body: EditDecisionRequest,
    user: User = Depends(_reviewer),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
) -> ReviewTaskOut:
    service = ReviewTaskService(db, storage)
    task = service.edit(
        service.get_task(user.tenant_id, task_id),
        user,
        body.rationale,
        artifact_role=body.artifact_role,
        content=body.content,
        content_type=body.content_type,
    )
    db.commit()
    return task


@router.post("/review-tasks/{task_id}/reject", response_model=ReviewTaskOut)
def reject_review_task(
    task_id: uuid.UUID,
    body: DecisionRequest,
    user: User = Depends(_reviewer),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
) -> ReviewTaskOut:
    service = ReviewTaskService(db, storage)
    task = service.reject(service.get_task(user.tenant_id, task_id), user, body.rationale)
    db.commit()
    return task


@router.post("/review-tasks/{task_id}/escalate", response_model=ReviewTaskOut)
def escalate_review_task(
    task_id: uuid.UUID,
    body: DecisionRequest,
    user: User = Depends(_reviewer),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
) -> ReviewTaskOut:
    service = ReviewTaskService(db, storage)
    escalated = service.escalate(service.get_task(user.tenant_id, task_id), user, body.rationale)
    db.commit()
    return escalated


@router.get("/evidence-packs/runs/{run_id}")
def export_run_evidence_pack(
    run_id: uuid.UUID,
    user: User = Depends(_auditor),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
) -> dict:
    """Run-scoped evidence pack (spec §17.3/§22): the full governance record
    of one workflow run behind an SHA-256 hash chain. The export itself is a
    consequential action, so it lands in the audit trail — after the pack is
    built, keeping the export event out of its own hash chain."""
    pack = EvidencePackBuilder(db, storage).build(user.tenant_id, run_id, generated_by=user)
    AuditService(db).record(
        tenant_id=user.tenant_id,
        event_type="governance.evidence_pack.exported",
        actor_type=ActorType.human,
        actor_id=user.id,
        workflow_run_id=run_id,
        payload={
            "root_hash": pack["integrity"]["root_hash"],
            "entry_count": pack["integrity"]["entry_count"],
            "format": pack["format"],
        },
    )
    db.commit()
    return pack


@router.get("/audit-events", response_model=list[AuditEventOut])
def list_audit_events(
    event_type: str | None = None,
    workflow_run_id: uuid.UUID | None = None,
    limit: int = 100,
    user: User = Depends(_auditor),
    db: Session = Depends(get_db),
) -> list[AuditEventOut]:
    return AuditService(db).query(
        user.tenant_id,
        event_type=event_type,
        workflow_run_id=workflow_run_id,
        limit=limit,
    )
