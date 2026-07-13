"""Run-scoped evidence pack export (roadmap stage 4; spec §17.3 / §22).

The pack is the auditor's single document: lineage, human decisions, eval
scores with judge provenance, LLM spend, and the audit trail — behind an
SHA-256 hash chain that must survive the HTTP round trip byte-for-byte.
"""

import hashlib

import pytest

from app.evals.services.judge import JudgeEvalService
from app.governance.audit.evidence_pack import PACK_FORMAT, SECTION_ORDER, verify_evidence_pack
from app.platform.auth.models import Role
from app.platform.llm.adapter import set_llm_adapter
from app.tasks.judge_tasks import set_judge_dispatcher
from tests.conftest import login_headers
from tests.test_evals import PASSING, make_eval_run, make_rubric_version, score
from tests.test_governance import start_reviewed_run
from tests.test_judge_evals import FakeAdapter, make_judge_suite
from tests.test_workflow import create_version


@pytest.fixture(autouse=True)
def _judge_seams(db, storage):
    set_judge_dispatcher(lambda eval_run_id: JudgeEvalService(db, storage).score_run(eval_run_id))
    yield
    set_judge_dispatcher(None)
    set_llm_adapter(None)


@pytest.fixture
def auditor_headers(client, db, tenant_id) -> dict:
    return login_headers(client, db, Role.auditor, "auditor@example.com", tenant_id=tenant_id)


def export_pack(client, headers, run_id):
    return client.get(f"/governance/evidence-packs/runs/{run_id}", headers=headers)


def build_governed_run(client, operator_headers, reviewer_headers, evaluator_headers) -> dict:
    """A run with real evidence on it: a review approval and a judge-assisted,
    human-decided eval on the first stage."""
    set_llm_adapter(FakeAdapter())
    run, stage1_id, task = start_reviewed_run(client, operator_headers)
    approved = client.post(
        f"/governance/review-tasks/{task['id']}/approve",
        json={"rationale": "meets the definition of done"},
        headers=reviewer_headers,
    )
    assert approved.status_code == 200, approved.text

    suite = make_judge_suite(client, evaluator_headers)
    rubric_version = make_rubric_version(client, evaluator_headers).json()
    eval_run = make_eval_run(client, evaluator_headers, suite, rubric_version, stage1_id).json()
    score(client, evaluator_headers, eval_run["id"], PASSING)
    return run


def entries_for(pack: dict, section: str) -> list[dict]:
    return [e["data"] for e in pack["entries"] if e["section"] == section]


def test_evidence_pack_full_governed_run(
    client, operator_headers, reviewer_headers, evaluator_headers, auditor_headers
) -> None:
    """A fully governed run — review approval plus a judge-assisted, human-decided
    eval — exports a pack whose hash chain verifies from the served JSON, with
    lineage, actors, judge provenance, spend, and calibration state all present."""
    run = build_governed_run(client, operator_headers, reviewer_headers, evaluator_headers)

    response = export_pack(client, auditor_headers, run["id"])
    assert response.status_code == 200, response.text
    pack = response.json()

    # The chain must verify from the served JSON alone.
    assert pack["format"] == PACK_FORMAT
    assert verify_evidence_pack(pack)
    assert pack["generated_by"]["email"] == "auditor@example.com"
    assert pack["section_counts"] == {s: len(entries_for(pack, s)) for s in SECTION_ORDER}

    run_data = entries_for(pack, "run")[0]
    assert run_data["template"]["slug"] == "research-report"
    assert run_data["workflow_run_id"] == run["id"]

    stages = entries_for(pack, "stages")
    assert [s["stage_key"] for s in stages] == ["scope", "draft"]
    assert all(s["contract_sha256"] for s in stages)
    assert stages[0]["review_required"] is True
    assert stages[0]["context_manifest"]["layer0_ref"]

    artifacts = entries_for(pack, "artifacts")
    by_role = {a["artifact_role"]: a for a in artifacts}
    assert by_role["scope_brief"]["content_sha256"] == hashlib.sha256(b"the brief").hexdigest()
    assert by_role["scope_brief"]["created_by"]["email"] == "operator@example.com"
    assert all(a["content_available"] for a in artifacts)

    reviews = entries_for(pack, "reviews")
    assert len(reviews) == 1
    decision = reviews[0]["decisions"][0]
    assert decision["decision_type"] == "approve"
    assert decision["decided_by"]["email"] == "reviewer@example.com"

    evals = entries_for(pack, "evals")
    assert len(evals) == 1
    scores_by_judge = {s["llm_judge"]: s for s in evals[0]["scores"]}
    assert scores_by_judge[True]["judge_model"]  # judge provenance
    assert scores_by_judge[True]["scored_by_type"] == "agent"
    assert scores_by_judge[False]["reviewer"]["email"] == "evaluator@example.com"
    assert evals[0]["decision"]["decision_type"] == "pass"
    assert evals[0]["decision"]["metrics"]["judge_agrees"] is True

    usage = entries_for(pack, "llm_usage")
    assert len(usage) == 1
    assert usage[0]["purpose"] == "judge"
    assert usage[0]["eval_run_id"] == evals[0]["eval_run_id"]

    assert entries_for(pack, "audit_events")  # the trail came along

    calibration = entries_for(pack, "judge_calibration")
    assert len(calibration) == 1
    assert calibration[0]["judge_enabled"] is True
    assert calibration[0]["rolling_agreement"] == 1.0
    assert calibration[0]["agreement_sample_size"] == 1
    assert calibration[0]["sampling_widened"] is False
    assert calibration[0]["methodology"]["validated_split_metrics"] is None

    mapping = entries_for(pack, "control_mapping")[0]
    assert "eu_ai_act" in mapping["mapping"]["reviews"]
    assert "sr_11_7" in mapping["mapping"]["evals"]
    assert mapping["disclaimer"]


def test_hash_chain_detects_tampering(
    client, operator_headers, reviewer_headers, evaluator_headers, auditor_headers
) -> None:
    run = build_governed_run(client, operator_headers, reviewer_headers, evaluator_headers)
    pack = export_pack(client, auditor_headers, run["id"]).json()
    assert verify_evidence_pack(pack)

    # Rewriting history breaks the chain.
    tampered = {**pack, "entries": [dict(e) for e in pack["entries"]]}
    review_entry = next(e for e in tampered["entries"] if e["section"] == "reviews")
    review_entry["data"] = {
        **review_entry["data"],
        "decisions": [{**review_entry["data"]["decisions"][0], "decision_type": "reject"}],
    }
    assert not verify_evidence_pack(tampered)

    # So does dropping an entry, even with reindexing.
    truncated = {**pack, "entries": pack["entries"][:-1]}
    assert not verify_evidence_pack(truncated)

    # And a forged root hash.
    forged = {**pack, "integrity": {**pack["integrity"], "root_hash": "0" * 64}}
    assert not verify_evidence_pack(forged)


def test_pack_of_minimal_run_is_valid(client, operator_headers, auditor_headers) -> None:
    """A freshly started run with no reviews or evals still exports a valid,
    verifiable pack with zero counts in those sections."""
    version = create_version(client, operator_headers)
    run = client.post(
        "/workflow/runs",
        json={"workflow_template_version_id": version["id"]},
        headers=operator_headers,
    ).json()

    pack = export_pack(client, auditor_headers, run["id"]).json()

    assert verify_evidence_pack(pack)
    assert pack["section_counts"]["reviews"] == 0
    assert pack["section_counts"]["evals"] == 0
    assert pack["section_counts"]["judge_calibration"] == 0
    assert pack["section_counts"]["control_mapping"] == 1


def test_export_requires_auditor_role(
    client, operator_headers, admin_headers, auditor_headers
) -> None:
    version = create_version(client, operator_headers)
    run = client.post(
        "/workflow/runs",
        json={"workflow_template_version_id": version["id"]},
        headers=operator_headers,
    ).json()

    assert export_pack(client, operator_headers, run["id"]).status_code == 403
    assert export_pack(client, auditor_headers, run["id"]).status_code == 200
    assert export_pack(client, admin_headers, run["id"]).status_code == 200


def test_export_is_tenant_scoped(client, db, operator_headers) -> None:
    version = create_version(client, operator_headers)
    run = client.post(
        "/workflow/runs",
        json={"workflow_template_version_id": version["id"]},
        headers=operator_headers,
    ).json()
    foreign_auditor = login_headers(client, db, Role.auditor, "other-tenant@example.com")

    assert export_pack(client, foreign_auditor, run["id"]).status_code == 404


def test_export_itself_is_audited(client, operator_headers, auditor_headers) -> None:
    version = create_version(client, operator_headers)
    run = client.post(
        "/workflow/runs",
        json={"workflow_template_version_id": version["id"]},
        headers=operator_headers,
    ).json()

    pack = export_pack(client, auditor_headers, run["id"]).json()
    # The export event is recorded after the pack is built, so the pack's own
    # audit section does not contain it (it would change the hash it reports).
    assert all(
        e["data"]["event_type"] != "governance.evidence_pack.exported"
        for e in pack["entries"]
        if e["section"] == "audit_events"
    )

    events = client.get(
        "/governance/audit-events",
        params={"event_type": "governance.evidence_pack.exported"},
        headers=auditor_headers,
    ).json()
    assert len(events) == 1
    assert events[0]["payload_json"]["root_hash"] == pack["integrity"]["root_hash"]
    assert events[0]["workflow_run_id"] == run["id"]
