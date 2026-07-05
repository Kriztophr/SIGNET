import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.governance.models.entities import (
    PolicyDecision,
    PolicyRule,
    PolicyRuleType,
    PolicyScopeType,
)
from app.governance.services.audit import AuditService
from app.platform.errors import NotFoundError
from app.platform.events.bus import get_event_bus
from app.workflow.models.entities import ActorType, StageDefinition, StageRun, WorkflowRun


class PolicyService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_rule(
        self,
        tenant_id: uuid.UUID,
        created_by: uuid.UUID,
        *,
        name: str,
        scope_type: PolicyScopeType,
        scope_ref: str | None,
        rule_type: PolicyRuleType,
        rule_expression: dict,
        severity: str,
        project_id: uuid.UUID | None = None,
    ) -> PolicyRule:
        rule = PolicyRule(
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            scope_type=scope_type,
            scope_ref=scope_ref,
            rule_type=rule_type,
            rule_expression_json=rule_expression,
            severity=severity,
            created_by=created_by,
        )
        self._session.add(rule)
        self._session.flush()
        return rule

    def get_rule(self, tenant_id: uuid.UUID, rule_id: uuid.UUID) -> PolicyRule:
        rule = self._session.scalar(
            select(PolicyRule).where(PolicyRule.id == rule_id, PolicyRule.tenant_id == tenant_id)
        )
        if rule is None:
            raise NotFoundError(f"policy rule {rule_id} not found")
        return rule


class PolicyEngine:
    """Evaluates active policy rules at workflow control points.

    Every evaluation that changes an outcome is recorded as a PolicyDecision and
    an audit event, so control decisions stay reconstructable.
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._audit = AuditService(session)

    def stage_requires_review(
        self, run: WorkflowRun, stage_run: StageRun, stage: StageDefinition
    ) -> bool:
        rules = self._session.scalars(
            select(PolicyRule).where(
                PolicyRule.tenant_id == run.tenant_id,
                PolicyRule.rule_type == PolicyRuleType.require_review,
                PolicyRule.is_active.is_(True),
            )
        )
        matched = [rule for rule in rules if self._matches(rule, run, stage)]
        for rule in matched:
            self._session.add(
                PolicyDecision(
                    policy_rule_id=rule.id,
                    workflow_run_id=run.id,
                    stage_run_id=stage_run.id,
                    decision_type="require_review",
                    decision_reason=f"policy {rule.name!r} matched stage {stage.stage_key!r}",
                    decision_metadata_json={"severity": rule.severity},
                )
            )
            self._audit.record(
                tenant_id=run.tenant_id,
                project_id=run.project_id,
                event_type="governance.policy.evaluated",
                actor_type=ActorType.system,
                workflow_run_id=run.id,
                stage_run_id=stage_run.id,
                payload={"policy_rule_id": str(rule.id), "decision": "require_review"},
            )
            get_event_bus().publish(
                "governance.policy.evaluated",
                {
                    "policy_rule_id": str(rule.id),
                    "workflow_run_id": str(run.id),
                    "stage_run_id": str(stage_run.id),
                    "decision": "require_review",
                },
            )
        self._session.flush()
        return bool(matched)

    @staticmethod
    def _matches(rule: PolicyRule, run: WorkflowRun, stage: StageDefinition) -> bool:
        if rule.scope_type is PolicyScopeType.tenant:
            return True
        if rule.scope_type is PolicyScopeType.workflow_template:
            return rule.scope_ref == str(stage.version.workflow_template_id)
        if rule.scope_type is PolicyScopeType.stage_key:
            return rule.scope_ref == stage.stage_key
        return False
