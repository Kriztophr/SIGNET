import uuid

import pytest

from app.platform.auth.models import Role
from tests.conftest import login_headers
from tests.test_workflow import create_version, submit


@pytest.fixture
def tenant_id(client, operator_headers) -> uuid.UUID:
    me = client.get("/users/me", headers=operator_headers).json()
    return uuid.UUID(me["tenant_id"])


@pytest.fixture
def reviewer_headers(client, db, tenant_id) -> dict:
    return login_headers(client, db, Role.reviewer, "reviewer@example.com", tenant_id=tenant_id)


@pytest.fixture
def admin_headers(client, db, tenant_id) -> dict:
    return login_headers(client, db, Role.admin, "admin@example.com", tenant_id=tenant_id)


def start_reviewed_run(client, operator_headers) -> tuple[dict, str, dict]:
    """Run a review-gated first stage up to its pause; returns (run, stage1_id, task)."""
    version = create_version(client, operator_headers, review_required_first=True)
    run = client.post(
        "/workflow/runs",
        json={"workflow_template_version_id": version["id"]},
        headers=operator_headers,
    ).json()
    stage1_id = run["current_stage_run_id"]
    submit(client, operator_headers, stage1_id, "scope_brief", "the brief")
    submit(client, operator_headers, stage1_id, "handoff", "the handoff")
    paused = client.post(
        f"/workflow/stage-runs/{stage1_id}/complete", headers=operator_headers
    ).json()
    assert paused["status"] == "paused_for_review"

    tasks = client.get(
        "/governance/review-tasks", params={"status": "open"}, headers=operator_headers
    ).json()
    assert len(tasks) == 1
    return run, stage1_id, tasks[0]


def test_review_task_created_on_pause(client, operator_headers) -> None:
    run, stage1_id, task = start_reviewed_run(client, operator_headers)
    assert task["workflow_run_id"] == run["id"]
    assert task["stage_run_id"] == stage1_id
    assert task["eligible_role"] == "reviewer"
    assert task["status"] == "open"
    # The primary contracted output anchors the review.
    artifact = client.get(
        f"/workflow/artifacts/{task['artifact_id']}", headers=operator_headers
    ).json()
    assert artifact["artifact_role"] == "scope_brief"


def test_approve_resumes_run(client, operator_headers, reviewer_headers) -> None:
    run, stage1_id, task = start_reviewed_run(client, operator_headers)
    decided = client.post(
        f"/governance/review-tasks/{task['id']}/approve",
        json={"rationale": "meets the definition of done"},
        headers=reviewer_headers,
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "approved"

    resumed = client.get(f"/workflow/runs/{run['id']}", headers=operator_headers).json()
    assert resumed["status"] == "running"
    assert resumed["current_stage_run_id"] != stage1_id
    stage1 = client.get(f"/workflow/stage-runs/{stage1_id}", headers=operator_headers).json()
    assert stage1["status"] == "completed"


def test_edit_hands_off_edited_artifact(client, operator_headers, reviewer_headers) -> None:
    run, stage1_id, task = start_reviewed_run(client, operator_headers)
    decided = client.post(
        f"/governance/review-tasks/{task['id']}/edit",
        json={
            "rationale": "tightened the success criteria",
            "artifact_role": "scope_brief",
            "content": "the brief, edited by reviewer",
        },
        headers=reviewer_headers,
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "edited"

    resumed = client.get(f"/workflow/runs/{run['id']}", headers=operator_headers).json()
    assert resumed["status"] == "running"
    stage2_id = resumed["current_stage_run_id"]
    manifest = client.get(
        f"/workflow/stage-runs/{stage2_id}/context-manifest", headers=operator_headers
    ).json()
    handed = {i["artifact_role"]: i for i in manifest["layer4_inputs_json"]}
    assert handed["scope_brief"]["version_number"] == 2

    edited = client.get(
        f"/workflow/artifacts/{handed['scope_brief']['artifact_id']}",
        headers=operator_headers,
    ).json()
    assert edited["is_human_edited"] is True
    assert edited["source_artifact_id"] is not None
    content = client.get(f"/workflow/artifacts/{edited['id']}/content", headers=operator_headers)
    assert content.text == "the brief, edited by reviewer"


def test_reject_fails_run(client, operator_headers, reviewer_headers) -> None:
    run, stage1_id, task = start_reviewed_run(client, operator_headers)
    decided = client.post(
        f"/governance/review-tasks/{task['id']}/reject",
        json={"rationale": "scope creep"},
        headers=reviewer_headers,
    )
    assert decided.json()["status"] == "rejected"
    failed = client.get(f"/workflow/runs/{run['id']}", headers=operator_headers).json()
    assert failed["status"] == "failed"
    stage1 = client.get(f"/workflow/stage-runs/{stage1_id}", headers=operator_headers).json()
    assert stage1["status"] == "failed"
    assert "rejected by review" in stage1["error_summary"]


def test_escalate_opens_admin_task(
    client, operator_headers, reviewer_headers, admin_headers
) -> None:
    run, _stage1_id, task = start_reviewed_run(client, operator_headers)
    escalated = client.post(
        f"/governance/review-tasks/{task['id']}/escalate",
        json={"rationale": "material ambiguity"},
        headers=reviewer_headers,
    ).json()
    assert escalated["eligible_role"] == "admin"
    assert escalated["id"] != task["id"]

    original = client.get(f"/governance/review-tasks/{task['id']}", headers=operator_headers).json()
    assert original["status"] == "escalated"

    # A reviewer cannot decide the escalated task; an admin can, resuming the run.
    denied = client.post(
        f"/governance/review-tasks/{escalated['id']}/approve",
        json={"rationale": "trying anyway"},
        headers=reviewer_headers,
    )
    assert denied.status_code == 403

    approved = client.post(
        f"/governance/review-tasks/{escalated['id']}/approve",
        json={"rationale": "resolved at admin level"},
        headers=admin_headers,
    )
    assert approved.status_code == 200
    resumed = client.get(f"/workflow/runs/{run['id']}", headers=operator_headers).json()
    assert resumed["status"] == "running"


def test_decided_task_cannot_be_decided_again(client, operator_headers, reviewer_headers) -> None:
    _run, _stage1_id, task = start_reviewed_run(client, operator_headers)
    client.post(
        f"/governance/review-tasks/{task['id']}/approve",
        json={"rationale": "fine"},
        headers=reviewer_headers,
    )
    again = client.post(
        f"/governance/review-tasks/{task['id']}/reject",
        json={"rationale": "changed my mind"},
        headers=reviewer_headers,
    )
    assert again.status_code == 409


def test_operator_cannot_decide_reviews(client, operator_headers) -> None:
    _run, _stage1_id, task = start_reviewed_run(client, operator_headers)
    denied = client.post(
        f"/governance/review-tasks/{task['id']}/approve",
        json={"rationale": "self-approval"},
        headers=operator_headers,
    )
    assert denied.status_code == 403


def test_policy_rule_forces_review(client, operator_headers, admin_headers) -> None:
    rule = client.post(
        "/governance/policies",
        json={
            "name": "review everything",
            "scope_type": "tenant",
            "rule_type": "require_review",
            "severity": "high",
        },
        headers=admin_headers,
    )
    assert rule.status_code == 201, rule.text

    # The scope stage is NOT review_required, but the tenant-wide policy is active.
    version = create_version(client, operator_headers)
    run = client.post(
        "/workflow/runs",
        json={"workflow_template_version_id": version["id"]},
        headers=operator_headers,
    ).json()
    stage1_id = run["current_stage_run_id"]
    submit(client, operator_headers, stage1_id, "scope_brief")
    submit(client, operator_headers, stage1_id, "handoff")
    paused = client.post(
        f"/workflow/stage-runs/{stage1_id}/complete", headers=operator_headers
    ).json()
    assert paused["status"] == "paused_for_review"

    events = client.get(
        "/governance/audit-events",
        params={"event_type": "governance.policy.evaluated"},
        headers=admin_headers,
    ).json()
    assert len(events) == 1
    assert events[0]["payload_json"]["decision"] == "require_review"


def test_audit_trail_of_review_lifecycle(
    client, operator_headers, reviewer_headers, admin_headers
) -> None:
    run, _stage1_id, task = start_reviewed_run(client, operator_headers)
    client.post(
        f"/governance/review-tasks/{task['id']}/approve",
        json={"rationale": "good"},
        headers=reviewer_headers,
    )
    events = client.get(
        "/governance/audit-events",
        params={"workflow_run_id": run["id"]},
        headers=admin_headers,
    ).json()
    types = {event["event_type"] for event in events}
    assert "governance.review.requested" in types
    assert "governance.review.approved" in types
    approved = next(e for e in events if e["event_type"] == "governance.review.approved")
    assert approved["actor_type"] == "human"
    assert approved["payload_json"]["rationale"] == "good"


def test_audit_stream_requires_auditor_or_admin(client, operator_headers) -> None:
    assert client.get("/governance/audit-events", headers=operator_headers).status_code == 403
