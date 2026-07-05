import uuid

import pytest
from sqlalchemy import select

from app.platform.auth.models import Role
from app.resilience.models.entities import ReviewerCompetencyRecord
from tests.conftest import login_headers

GOOD = 0.9
BAD = 0.3
THRESHOLDS = {"verification": 0.7, "override": 0.7, "reconstruction": 0.7}


@pytest.fixture
def resilience_headers(client, db, tenant_id) -> dict:
    return login_headers(
        client, db, Role.resilience_manager, "resilience@example.com", tenant_id=tenant_id
    )


def make_capability(client, headers, *, minimum_required_count=1) -> dict:
    return client.post(
        "/resilience/capabilities",
        json={
            "name": "Verify financial workflow output",
            "domain": "finance",
            "criticality_level": "critical",
            "minimum_required_count": minimum_required_count,
        },
        headers=headers,
    ).json()


def make_capacity_suite(client, headers, capability_id, thresholds=THRESHOLDS) -> dict:
    return client.post(
        "/resilience/suites",
        json={
            "name": "Quarterly capacity check",
            "critical_capability_id": capability_id,
            "rubric_name": "capacity rubric v1",
            "rubric_thresholds": thresholds,
            "cases": [
                {
                    "name": "spot the planted flaw",
                    "instruction": "Find the error in this AI-produced brief.",
                    "dimension": "verification",
                }
            ],
        },
        headers=headers,
    ).json()


def start_run(client, headers, suite_id, subject_id=None) -> dict:
    return client.post(
        "/resilience/eval-runs",
        json={
            "human_capacity_eval_suite_id": suite_id,
            "subject_type": "person",
            "subject_ref_id": subject_id or str(uuid.uuid4()),
        },
        headers=headers,
    ).json()


def submit_score(client, headers, run_id, dimension, score):
    return client.post(
        "/resilience/eval-runs/scores",
        json={
            "human_capacity_run_id": run_id,
            "dimension": dimension,
            "score": score,
            "evidence": {"notes": "assessed live"},
        },
        headers=headers,
    )


def qualify_subject(client, headers, suite_id, subject_id=None) -> dict:
    run = start_run(client, headers, suite_id, subject_id)
    for dimension in ("verification", "override", "reconstruction"):
        assert submit_score(client, headers, run["id"], dimension, GOOD).status_code == 201
    return run


# -- capacity evaluation ------------------------------------------------------


def test_capacity_run_qualifies_subject(client, resilience_headers, admin_headers, db) -> None:
    capability = make_capability(client, resilience_headers)
    suite = make_capacity_suite(client, resilience_headers, capability["id"])
    subject_id = str(uuid.uuid4())
    run = qualify_subject(client, resilience_headers, suite["id"], subject_id)

    completed = client.get(f"/resilience/eval-runs/{run['id']}", headers=resilience_headers).json()
    assert completed["status"] == "completed"
    assert completed["qualified"] is True

    # Person subjects get a competency record.
    records = db.scalars(
        select(ReviewerCompetencyRecord).where(
            ReviewerCompetencyRecord.reviewer_id == uuid.UUID(subject_id)
        )
    ).all()
    assert len(records) == 1
    assert records[0].status.value == "qualified"

    events = client.get(
        "/governance/audit-events",
        params={"event_type": "resilience.capacity.assessed"},
        headers=admin_headers,
    ).json()
    assert len(events) == 1
    assert events[0]["payload_json"]["qualified"] is True


def test_failing_scores_disqualify(client, resilience_headers) -> None:
    capability = make_capability(client, resilience_headers)
    suite = make_capacity_suite(client, resilience_headers, capability["id"])
    run = start_run(client, resilience_headers, suite["id"])
    submit_score(client, resilience_headers, run["id"], "verification", GOOD)
    submit_score(client, resilience_headers, run["id"], "override", BAD)  # below 0.7
    submit_score(client, resilience_headers, run["id"], "reconstruction", GOOD)

    completed = client.get(f"/resilience/eval-runs/{run['id']}", headers=resilience_headers).json()
    assert completed["status"] == "completed"
    assert completed["qualified"] is False


def test_run_completes_only_after_required_dimensions(client, resilience_headers) -> None:
    capability = make_capability(client, resilience_headers)
    suite = make_capacity_suite(client, resilience_headers, capability["id"])
    run = start_run(client, resilience_headers, suite["id"])
    submit_score(client, resilience_headers, run["id"], "verification", GOOD)

    partial = client.get(f"/resilience/eval-runs/{run['id']}", headers=resilience_headers).json()
    assert partial["status"] == "awaiting_scores"

    duplicate = submit_score(client, resilience_headers, run["id"], "verification", GOOD)
    assert duplicate.status_code == 409


def test_rubric_must_cover_required_dimensions(client, resilience_headers) -> None:
    capability = make_capability(client, resilience_headers)
    response = client.post(
        "/resilience/suites",
        json={
            "name": "Bad suite",
            "critical_capability_id": capability["id"],
            "rubric_name": "incomplete",
            "rubric_thresholds": {"verification": 0.7},  # missing override/reconstruction
        },
        headers=resilience_headers,
    )
    assert response.status_code == 422


# -- fallback drills ----------------------------------------------------------


def test_fallback_drill_flow(client, resilience_headers, admin_headers) -> None:
    env_version_id = str(uuid.uuid4())
    drill = client.post(
        "/resilience/fallback-drills",
        json={
            "environment_template_version_id": env_version_id,
            "drill_type": "ai_outage_simulation",
            "ai_mode": "off",
        },
        headers=resilience_headers,
    )
    assert drill.status_code == 201, drill.text
    assert drill.json()["status"] == "running"

    assessment = client.post(
        f"/resilience/fallback-drills/{drill.json()['id']}/complete",
        json={
            "readiness_score": 0.85,
            "summary": {"tasks_completed": 4, "tasks_total": 5},
            "evidence": {"observer": "ops lead"},
        },
        headers=resilience_headers,
    )
    assert assessment.status_code == 200, assessment.text
    assert assessment.json()["readiness_score"] == 0.85

    completed = client.get(
        f"/resilience/fallback-drills/{drill.json()['id']}", headers=resilience_headers
    ).json()
    assert completed["status"] == "completed"

    again = client.post(
        f"/resilience/fallback-drills/{drill.json()['id']}/complete",
        json={"readiness_score": 0.9},
        headers=resilience_headers,
    )
    assert again.status_code == 409

    events = client.get(
        "/governance/audit-events",
        params={"event_type": "resilience.drill.completed"},
        headers=admin_headers,
    ).json()
    assert len(events) == 1


# -- coverage snapshots -------------------------------------------------------


def test_coverage_snapshot_shortfall_and_recovery(client, resilience_headers) -> None:
    capability = make_capability(client, resilience_headers, minimum_required_count=2)
    suite = make_capacity_suite(client, resilience_headers, capability["id"])
    qualify_subject(client, resilience_headers, suite["id"])  # 1 of 2

    snapshots = client.post("/resilience/coverage-snapshots", headers=resilience_headers).json()
    assert len(snapshots) == 1
    assert snapshots[0]["qualified_subject_count"] == 1
    assert snapshots[0]["coverage_status"] == "shortfall"

    qualify_subject(client, resilience_headers, suite["id"])  # 2 of 2
    snapshots = client.post("/resilience/coverage-snapshots", headers=resilience_headers).json()
    assert snapshots[0]["coverage_status"] == "adequate"

    listed = client.get("/resilience/coverage-snapshots", headers=resilience_headers).json()
    assert len(listed) == 2


# -- thresholds gate environment promotion (spec 17.2) ------------------------


def test_resilience_threshold_gates_promotion(
    client, db, resilience_headers, operator_headers, evaluator_headers, tenant_id
) -> None:
    from tests.test_environment import (
        eval_a_workflow_stage_on_version,
        make_env_template,
        make_env_version,
    )

    manager = login_headers(
        client, db, Role.environment_manager, "envmgr@example.com", tenant_id=tenant_id
    )
    template = make_env_template(client, manager)
    version = make_env_version(client, manager, template["id"]).json()
    eval_a_workflow_stage_on_version(
        client, operator_headers, evaluator_headers, version["id"], passing=True
    )

    # A reversibility threshold scoped to this environment version, with no evidence yet.
    threshold = client.post(
        "/resilience/thresholds",
        json={
            "scope_type": "environment_template_version",
            "scope_ref": version["id"],
            "metric_name": "reversibility_score",
            "min_threshold": 0.8,
        },
        headers=resilience_headers,
    )
    assert threshold.status_code == 201, threshold.text

    blocked = client.post(
        "/environment/promotions",
        json={"environment_template_version_id": version["id"]},
        headers=manager,
    ).json()
    assert blocked["status"] == "blocked"
    assert "no evidence" in blocked["decision_reason"]

    # A failing assessment still blocks.
    client.post(
        "/resilience/reversibility-assessments",
        json={
            "scope_type": "environment_template_version",
            "scope_ref": version["id"],
            "assessment_score": 0.5,
            "evidence": {"drill": "partial"},
        },
        headers=resilience_headers,
    )
    still_blocked = client.post(
        "/environment/promotions",
        json={"environment_template_version_id": version["id"]},
        headers=manager,
    ).json()
    assert still_blocked["status"] == "blocked"
    assert "below required" in still_blocked["decision_reason"]

    # A passing assessment unblocks; promotion approves on complete evidence.
    client.post(
        "/resilience/reversibility-assessments",
        json={
            "scope_type": "environment_template_version",
            "scope_ref": version["id"],
            "assessment_score": 0.95,
            "evidence": {"drill": "full restoration in 40m"},
        },
        headers=resilience_headers,
    )
    promotable = client.post(
        "/environment/promotions",
        json={"environment_template_version_id": version["id"]},
        headers=manager,
    ).json()
    assert promotable["status"] == "approval_pending"
    assert promotable["evidence_json"]["resilience"]["thresholds_evaluated"] >= 1

    approved = client.post(f"/environment/promotions/{promotable['id']}/approve", headers=manager)
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"


def test_unsupported_threshold_metric_rejected(client, resilience_headers) -> None:
    response = client.post(
        "/resilience/thresholds",
        json={
            "scope_type": "tenant",
            "scope_ref": "*",
            "metric_name": "vibes",
            "min_threshold": 0.5,
        },
        headers=resilience_headers,
    )
    assert response.status_code == 422


# -- RBAC and isolation -------------------------------------------------------


def test_operator_cannot_manage_resilience(client, operator_headers) -> None:
    denied = client.post(
        "/resilience/capabilities",
        json={"name": "Nope", "domain": "x"},
        headers=operator_headers,
    )
    assert denied.status_code == 403


def test_tenant_isolation(client, db, resilience_headers) -> None:
    capability = make_capability(client, resilience_headers)
    other = login_headers(client, db, Role.resilience_manager, "other-res@example.com")
    assert (
        client.get(f"/resilience/capabilities/{capability['id']}", headers=other).status_code == 404
    )
