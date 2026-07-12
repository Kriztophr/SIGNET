"""Run-scoped evidence pack export (roadmap stage 4; spec §17.3 / §22).

One workflow run's complete governance record as a single, self-verifying
document: run/stage/artifact lineage, review decisions with actors, eval runs
with reviewer scores (judge provenance included), disagreements, drift
signals, LLM spend, the audit trail, and the judge-calibration state — plus a
machine-readable mapping of each section onto EU AI Act Annex IV items and
SR 11-7 controls (docs/evidence-pack.md is the narrative companion).

Tamper evidence is an SHA-256 entry chain: entries are emitted in a fixed
section order, each entry's hash covers the previous hash plus the canonical
JSON of the entry body, and the chain is seeded from the pack header. Editing,
reordering, inserting, or dropping any entry breaks every hash after it;
`verify_evidence_pack` re-walks the chain from the served JSON alone.

Dependency note: governance reads sibling modules' records here (evals,
workflow, platform.llm) because evidence assembly is an audit concern; nothing
imports this module back, so no cycle forms.
"""

import enum
import hashlib
import json
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evals.models.entities import DisagreementRecord, DriftSignal, EvalRun, ReviewerScore
from app.evals.services.judge import JUDGE_REVIEWER_ID, judge_config, recent_agreement
from app.governance.models.entities import AuditEvent, ReviewTask
from app.platform.auth.models import User
from app.platform.llm.models import LLMUsage
from app.platform.storage.service import StorageService
from app.platform.time.clock import utc_now
from app.workflow.models.entities import Artifact, ContextManifest, StageRun, WorkflowRun
from app.workflow.repositories.workflow import WorkflowRepository

PACK_FORMAT = "icm-evidence-pack/v1"
HASH_ALGORITHM = "sha256-entry-chain"

SECTION_ORDER = [
    "run",
    "stages",
    "artifacts",
    "reviews",
    "evals",
    "disagreements",
    "drift_signals",
    "llm_usage",
    "audit_events",
    "judge_calibration",
    "control_mapping",
]

# Coarse, article-level citations only: the pack supplies supporting evidence
# for these obligations; it is not a conformity claim (see the disclaimer).
CONTROL_MAPPING = {
    "run": {
        "eu_ai_act": ["Annex IV(1) general description", "Art 12 record-keeping"],
        "sr_11_7": ["Model inventory and documentation"],
    },
    "stages": {
        "eu_ai_act": ["Annex IV(2) development process and design specification"],
        "sr_11_7": ["Model development documentation"],
    },
    "artifacts": {
        "eu_ai_act": ["Annex IV(2) system elements", "Art 12 record-keeping"],
        "sr_11_7": ["Documentation of model inputs and outputs"],
    },
    "reviews": {
        "eu_ai_act": ["Art 14 human oversight"],
        "sr_11_7": ["Effective challenge by qualified staff"],
    },
    "evals": {
        "eu_ai_act": ["Annex IV(4) performance metrics and validation"],
        "sr_11_7": ["Model validation"],
    },
    "disagreements": {
        "eu_ai_act": ["Art 14 human oversight"],
        "sr_11_7": ["Effective challenge; validation independence"],
    },
    "drift_signals": {
        "eu_ai_act": ["Art 72 post-market monitoring", "Annex IV(9)"],
        "sr_11_7": ["Ongoing monitoring and outcomes analysis"],
    },
    "llm_usage": {
        "eu_ai_act": ["Art 12 record-keeping"],
        "sr_11_7": ["Model use controls and documentation"],
    },
    "audit_events": {
        "eu_ai_act": ["Art 12 record-keeping", "Art 19 automatically generated logs"],
        "sr_11_7": ["Governance, policies, and audit"],
    },
    "judge_calibration": {
        "eu_ai_act": ["Art 14 human oversight", "Art 72 post-market monitoring"],
        "sr_11_7": ["Validation of vendor and automated review tools"],
    },
}

CONTROL_MAPPING_DISCLAIMER = (
    "This mapping identifies where pack sections provide supporting evidence "
    "for the cited obligations. It is not a legal conformity assessment or a "
    "declaration of conformity."
)


# --------------------------------------------------------------------------- #
# Canonical serialization and the hash chain
# --------------------------------------------------------------------------- #
def _jsonable(value):
    """Reduce to JSON primitives so the hashed form and the served JSON agree."""
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, enum.Enum):
        return value.value
    return value


def canonical_json(data) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chain_hash(prev_hash: str, entry_body: dict) -> str:
    return _sha256(prev_hash + canonical_json(entry_body))


def verify_evidence_pack(pack: dict) -> bool:
    """Re-walk the hash chain of a served pack. Pure function — callers
    outside the platform can verify with nothing but this algorithm."""
    try:
        header = {k: v for k, v in pack.items() if k not in ("entries", "integrity")}
        prev = _sha256(canonical_json(header))
        for position, entry in enumerate(pack["entries"]):
            if entry["index"] != position:
                return False
            body = {"index": entry["index"], "section": entry["section"], "data": entry["data"]}
            expected = _chain_hash(prev, body)
            if entry["sha256"] != expected:
                return False
            prev = expected
        integrity = pack["integrity"]
        return (
            integrity["root_hash"] == prev
            and integrity["entry_count"] == len(pack["entries"])
            and integrity["algorithm"] == HASH_ALGORITHM
        )
    except (KeyError, TypeError):
        return False


# --------------------------------------------------------------------------- #
# Builder
# --------------------------------------------------------------------------- #
class EvidencePackBuilder:
    def __init__(self, session: Session, storage: StorageService) -> None:
        self._session = session
        self._storage = storage
        self._actor_cache: dict[uuid.UUID, dict | None] = {}

    def build(self, tenant_id: uuid.UUID, run_id: uuid.UUID, generated_by: User) -> dict:
        run = WorkflowRepository(self._session).get_run(tenant_id, run_id)

        stage_runs = self._stage_runs(run)
        eval_runs = self._eval_runs(run)
        sections: dict[str, list[dict]] = {
            "run": [self._run_data(run)],
            "stages": [self._stage_data(sr) for sr in stage_runs],
            "artifacts": self._artifact_data(run, stage_runs),
            "reviews": self._review_data(run),
            "evals": [self._eval_data(er) for er in eval_runs],
            "disagreements": self._disagreement_data(eval_runs),
            "drift_signals": self._drift_data(run, eval_runs),
            "llm_usage": self._llm_usage_data(run, eval_runs),
            "audit_events": self._audit_data(run),
            "judge_calibration": self._calibration_data(eval_runs),
            "control_mapping": [
                {
                    "mapping": CONTROL_MAPPING,
                    "disclaimer": CONTROL_MAPPING_DISCLAIMER,
                    "reference": "docs/evidence-pack.md",
                }
            ],
        }

        header = _jsonable(
            {
                "format": PACK_FORMAT,
                "workflow_run_id": run.id,
                "tenant_id": run.tenant_id,
                "project_id": run.project_id,
                "correlation_id": run.correlation_id,
                "generated_at": utc_now(),
                "generated_by": {
                    "user_id": generated_by.id,
                    "email": generated_by.email,
                    "role": generated_by.role,
                },
                "section_counts": {name: len(sections[name]) for name in SECTION_ORDER},
            }
        )

        entries: list[dict] = []
        prev = _sha256(canonical_json(header))
        for section in SECTION_ORDER:
            for data in sections[section]:
                body = {"index": len(entries), "section": section, "data": _jsonable(data)}
                prev = _chain_hash(prev, body)
                entries.append({**body, "sha256": prev})

        return {
            **header,
            "entries": entries,
            "integrity": {
                "algorithm": HASH_ALGORITHM,
                "entry_count": len(entries),
                "root_hash": prev,
                "verification": (
                    "entry.sha256 = sha256(prev_hash_hex + canonical_json({index, section, "
                    "data})) with sorted keys and separators (',', ':'); the chain is seeded "
                    "with sha256(canonical_json(header)) where the header is the pack minus "
                    "'entries' and 'integrity'."
                ),
            },
        }

    # ------------------------------------------------------------------ #
    def _actor(self, user_id: uuid.UUID | None) -> dict | None:
        """Resolve an actor id to a durable identity record for the auditor."""
        if user_id is None:
            return None
        if user_id not in self._actor_cache:
            user = self._session.get(User, user_id)
            self._actor_cache[user_id] = (
                {
                    "user_id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": user.role,
                }
                if user is not None
                else {"user_id": user_id, "email": None, "full_name": None, "role": None}
            )
        return self._actor_cache[user_id]

    def _stage_runs(self, run: WorkflowRun) -> list[StageRun]:
        return WorkflowRepository(self._session).stage_runs_for_run(run.id)

    def _eval_runs(self, run: WorkflowRun) -> list[EvalRun]:
        return sorted(
            self._session.scalars(select(EvalRun).where(EvalRun.workflow_run_id == run.id)),
            key=lambda er: (er.created_at, str(er.id)),
        )

    def _run_data(self, run: WorkflowRun) -> dict:
        version = run.version
        return {
            "workflow_run_id": run.id,
            "status": run.status,
            "correlation_id": run.correlation_id,
            "triggered_by": self._actor(run.triggered_by),
            "created_at": run.created_at,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "template": {
                "id": version.template.id,
                "name": version.template.name,
                "slug": version.template.slug,
            },
            "template_version": {
                "id": version.id,
                "version_number": version.version_number,
                "environment_template_version_id": version.environment_template_version_id,
            },
        }

    def _stage_data(self, stage_run: StageRun) -> dict:
        definition = stage_run.stage_definition
        manifest = self._session.scalar(
            select(ContextManifest).where(ContextManifest.stage_run_id == stage_run.id)
        )
        return {
            "stage_run_id": stage_run.id,
            "stage_key": definition.stage_key,
            "display_name": definition.display_name,
            "order_index": definition.order_index,
            "execution_mode": definition.execution_mode,
            "review_required": definition.review_required,
            "eval_required": definition.eval_required,
            "status": stage_run.status,
            "attempt_number": stage_run.attempt_number,
            "started_at": stage_run.started_at,
            "completed_at": stage_run.completed_at,
            "error_summary": stage_run.error_summary,
            "contract_sha256": (
                _sha256(definition.contract.source_markdown)
                if definition.contract is not None
                else None
            ),
            "context_manifest": (
                {
                    "layer0_ref": manifest.layer0_ref,
                    "layer1_ref": manifest.layer1_ref,
                    "layer2_ref": manifest.layer2_ref,
                    "layer3_inputs": manifest.layer3_inputs_json,
                    "layer4_inputs": manifest.layer4_inputs_json,
                    "token_estimate": manifest.token_estimate,
                }
                if manifest is not None
                else None
            ),
        }

    def _artifact_data(self, run: WorkflowRun, stage_runs: list[StageRun]) -> list[dict]:
        stage_keys = {sr.id: sr.stage_definition.stage_key for sr in stage_runs}
        artifacts = sorted(
            self._session.scalars(select(Artifact).where(Artifact.workflow_run_id == run.id)),
            key=lambda a: (a.created_at, str(a.id)),
        )
        results = []
        for artifact in artifacts:
            try:
                content_sha256 = _sha256(self._storage.get_text(artifact.storage_uri))
            except Exception:  # noqa: BLE001 — a missing blob is itself evidence
                content_sha256 = None
            results.append(
                {
                    "artifact_id": artifact.id,
                    "stage_run_id": artifact.stage_run_id,
                    "stage_key": stage_keys.get(artifact.stage_run_id),
                    "artifact_role": artifact.artifact_role,
                    "version_number": artifact.version_number,
                    "content_type": artifact.content_type,
                    "created_by_type": artifact.created_by_type,
                    "created_by": self._actor(artifact.created_by_id),
                    "is_human_edited": artifact.is_human_edited,
                    "source_artifact_id": artifact.source_artifact_id,
                    "created_at": artifact.created_at,
                    "content_sha256": content_sha256,
                    "content_available": content_sha256 is not None,
                }
            )
        return results

    def _review_data(self, run: WorkflowRun) -> list[dict]:
        tasks = sorted(
            self._session.scalars(select(ReviewTask).where(ReviewTask.workflow_run_id == run.id)),
            key=lambda t: (t.created_at, str(t.id)),
        )
        return [
            {
                "review_task_id": task.id,
                "stage_run_id": task.stage_run_id,
                "status": task.status,
                "eligible_role": task.eligible_role,
                "assigned_to": self._actor(task.assigned_to),
                "created_at": task.created_at,
                "decisions": [
                    {
                        "decision_type": decision.decision_type,
                        "rationale": decision.rationale,
                        "decided_by": self._actor(decision.decided_by),
                        "decided_at": decision.decided_at,
                        "edited_artifact_id": decision.edited_artifact_id,
                    }
                    for decision in sorted(task.decisions, key=lambda d: d.decided_at)
                ],
            }
            for task in tasks
        ]

    def _eval_data(self, eval_run: EvalRun) -> dict:
        rubric_version = eval_run.rubric_version
        scores = sorted(eval_run.scores, key=lambda s: (s.submitted_at, str(s.id)))
        decision = eval_run.decision
        return {
            "eval_run_id": eval_run.id,
            "suite": {"id": eval_run.suite.id, "name": eval_run.suite.name},
            "rubric": {
                "rubric_id": rubric_version.rubric.id,
                "name": rubric_version.rubric.name,
                "version_id": rubric_version.id,
                "version_number": rubric_version.version_number,
            },
            "target_ref_type": eval_run.target_ref_type,
            "target_ref_id": eval_run.target_ref_id,
            "stage_run_id": eval_run.stage_run_id,
            "artifact_id": eval_run.artifact_id,
            "status": eval_run.status,
            "started_at": eval_run.started_at,
            "completed_at": eval_run.completed_at,
            "triggered_by": self._actor(eval_run.triggered_by),
            "scores": [self._score_data(score) for score in scores],
            "decision": (
                {
                    "decision_type": decision.decision_type,
                    "decided_by_type": decision.decided_by_type,
                    "metrics": decision.metrics_json,
                    "rationale": decision.rationale,
                }
                if decision is not None
                else None
            ),
        }

    def _score_data(self, score: ReviewerScore) -> dict:
        is_judge = score.reviewer_id == JUDGE_REVIEWER_ID
        return {
            "reviewer_score_id": score.id,
            "scored_by_type": score.scored_by_type,
            "llm_judge": is_judge,
            "judge_model": score.score_json.get("_judge_model") if is_judge else None,
            "reviewer": (
                {"reviewer_id": JUDGE_REVIEWER_ID, "identity": "platform-llm-judge"}
                if is_judge
                else self._actor(score.reviewer_id)
            ),
            "score_json": score.score_json,
            "pass_fail": score.pass_fail,
            "rationale": score.rationale,
            "submitted_at": score.submitted_at,
        }

    def _disagreement_data(self, eval_runs: list[EvalRun]) -> list[dict]:
        if not eval_runs:
            return []
        records = sorted(
            self._session.scalars(
                select(DisagreementRecord).where(
                    DisagreementRecord.eval_run_id.in_([er.id for er in eval_runs])
                )
            ),
            key=lambda r: (r.created_at, str(r.id)),
        )
        return [
            {
                "disagreement_record_id": record.id,
                "eval_run_id": record.eval_run_id,
                "disagreement_type": record.disagreement_type,
                "status": record.status,
                "reviewer_score_ids": record.reviewer_score_ids_json,
                "created_at": record.created_at,
            }
            for record in records
        ]

    def _drift_data(self, run: WorkflowRun, eval_runs: list[EvalRun]) -> list[dict]:
        suite_refs = {str(er.eval_suite_id) for er in eval_runs}
        if not suite_refs:
            return []
        signals = sorted(
            self._session.scalars(
                select(DriftSignal).where(
                    DriftSignal.tenant_id == run.tenant_id,
                    DriftSignal.scope_ref.in_(suite_refs),
                )
            ),
            key=lambda s: (s.detected_at, str(s.id)),
        )
        return [
            {
                "drift_signal_id": signal.id,
                "scope_type": signal.scope_type,
                "scope_ref": signal.scope_ref,
                "signal_type": signal.signal_type,
                "signal_strength": signal.signal_strength,
                "evidence": signal.evidence_json,
                "detected_at": signal.detected_at,
            }
            for signal in signals
        ]

    def _llm_usage_data(self, run: WorkflowRun, eval_runs: list[EvalRun]) -> list[dict]:
        eval_ids = [er.id for er in eval_runs]
        criteria = LLMUsage.workflow_run_id == run.id
        if eval_ids:
            criteria = criteria | LLMUsage.eval_run_id.in_(eval_ids)
        rows = sorted(
            self._session.scalars(select(LLMUsage).where(criteria)),
            key=lambda r: (r.created_at, str(r.id)),
        )
        return [
            {
                "llm_usage_id": row.id,
                "model": row.model,
                "purpose": row.purpose,
                "input_tokens": row.input_tokens,
                "output_tokens": row.output_tokens,
                "cost_usd": row.cost_usd,
                "stage_run_id": row.stage_run_id,
                "eval_run_id": row.eval_run_id,
                "created_at": row.created_at,
            }
            for row in rows
        ]

    def _audit_data(self, run: WorkflowRun) -> list[dict]:
        events = sorted(
            self._session.scalars(
                select(AuditEvent).where(
                    AuditEvent.tenant_id == run.tenant_id,
                    AuditEvent.workflow_run_id == run.id,
                )
            ),
            key=lambda e: (e.occurred_at, str(e.id)),
        )
        return [
            {
                "audit_event_id": event.id,
                "event_type": event.event_type,
                "occurred_at": event.occurred_at,
                "actor_type": event.actor_type,
                "actor": self._actor(event.actor_id),
                "stage_run_id": event.stage_run_id,
                "review_task_id": event.review_task_id,
                "eval_run_id": event.eval_run_id,
                "environment_promotion_id": event.environment_promotion_id,
                "payload": event.payload_json,
                "correlation_id": event.correlation_id,
            }
            for event in events
        ]

    def _calibration_data(self, eval_runs: list[EvalRun]) -> list[dict]:
        """Judge-calibration state per suite touched by this run. Until the
        calibration module lands (roadmap stage 4b: frozen golden test split,
        TPR/TNR with Wilson intervals, Rogan-Gladen corrected fail rate), the
        validation evidence is the rolling human-agreement loop."""
        suites: dict[uuid.UUID, EvalRun] = {}
        for eval_run in eval_runs:
            suites.setdefault(eval_run.eval_suite_id, eval_run)
        results = []
        for suite_id, eval_run in sorted(suites.items(), key=lambda kv: str(kv[0])):
            cfg = judge_config(eval_run.suite)
            agreement, sample_size = recent_agreement(self._session, suite_id, window=cfg.window)
            results.append(
                {
                    "eval_suite_id": suite_id,
                    "suite_name": eval_run.suite.name,
                    "judge_enabled": cfg.enabled,
                    "sampling_rate": cfg.sampling_rate,
                    "agreement_threshold": cfg.agreement_threshold,
                    "window": cfg.window,
                    "rolling_agreement": agreement,
                    "agreement_sample_size": sample_size,
                    "sampling_widened": (
                        agreement is not None and agreement < cfg.agreement_threshold
                    ),
                    "methodology": {
                        "status": "rolling_agreement",
                        "validated_split_metrics": None,
                        "note": (
                            "Judge scores are advisory and never decide gates; every "
                            "judge verdict is compared against the human decision, and "
                            "sustained disagreement auto-widens sampling to 100% and "
                            "raises a drift signal. Formal TPR/TNR calibration against "
                            "a frozen golden test split is scheduled as the next "
                            "roadmap stage and will appear here when available."
                        ),
                    },
                }
            )
        return results
