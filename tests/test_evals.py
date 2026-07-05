import uuid

import pytest
from sqlalchemy import select

from app.evals.models.entities import DisagreementRecord
from tests.test_workflow import create_version

CRITERIA = [
    {"key": "accuracy", "description": "factually correct", "weight": 2},
    {"key": "clarity", "description": "clearly written", "weight": 1},
]
SCALE = {"min": 0, "max": 5}
THRESHOLD = {"min_total": 10}  # max attainable = 2*5 + 1*5 = 15

PASSING = {"accuracy": 4, "clarity": 3}  # 8 + 3 = 11 >= 10
FAILING = {"accuracy": 2, "clarity": 2}  # 4 + 2 = 6 < 10


def make_rubric_version(client, headers, criteria=CRITERIA, scale=SCALE, threshold=THRESHOLD):
    rubric = client.post("/evals/rubrics", json={"name": "Quality rubric"}, headers=headers).json()
    return client.post(
        f"/evals/rubrics/{rubric['id']}/versions",
        json={"criteria": criteria, "score_scale": scale, "pass_threshold": threshold},
        headers=headers,
    )


def make_suite(client, headers, target_type="stage_run", min_reviewers=1):
    return client.post(
        "/evals/suites",
        json={
            "name": "Stage output quality",
            "target_type": target_type,
            "config": {"min_reviewers": min_reviewers},
            "cases": [{"name": "read the artifact", "prompt_or_instruction": "Score the output."}],
        },
        headers=headers,
    )


def make_workflow_stage(client, operator_headers) -> tuple[dict, str]:
    """Start a plain two-stage run; returns (run, first stage_run_id)."""
    version = create_version(client, operator_headers)
    run = client.post(
        "/workflow/runs",
        json={"workflow_template_version_id": version["id"]},
        headers=operator_headers,
    ).json()
    return run, run["current_stage_run_id"]


def make_eval_run(
    client, evaluator_headers, suite, rubric_version, target_id, target_type="stage_run"
):
    return client.post(
        "/evals/runs",
        json={
            "eval_suite_id": suite["id"],
            "rubric_version_id": rubric_version["id"],
            "target_ref_type": target_type,
            "target_ref_id": target_id,
        },
        headers=evaluator_headers,
    )


def score(client, headers, eval_run_id, score_json, rationale="scored"):
    return client.post(
        "/evals/reviewer-scores",
        json={"eval_run_id": eval_run_id, "score_json": score_json, "rationale": rationale},
        headers=headers,
    )


# -- rubric and suite validation -------------------------------------------


def test_rubric_validation_rejects_bad_configs(client, evaluator_headers) -> None:
    dup = make_rubric_version(
        client, evaluator_headers, criteria=[{"key": "a", "weight": 1}, {"key": "a", "weight": 1}]
    )
    assert dup.status_code == 422

    bad_weight = make_rubric_version(
        client, evaluator_headers, criteria=[{"key": "a", "weight": 0}]
    )
    assert bad_weight.status_code == 422

    bad_scale = make_rubric_version(client, evaluator_headers, scale={"min": 5, "max": 5})
    assert bad_scale.status_code == 422

    unattainable = make_rubric_version(client, evaluator_headers, threshold={"min_total": 99})
    assert unattainable.status_code == 422
    assert "attainable" in unattainable.json()["detail"]


def test_suite_min_reviewers_validated(client, evaluator_headers) -> None:
    response = make_suite(client, evaluator_headers, min_reviewers=0)
    assert response.status_code == 422


# -- run creation and target resolution ------------------------------------


def test_run_derives_workflow_linkage(client, operator_headers, evaluator_headers) -> None:
    wf_run, stage_run_id = make_workflow_stage(client, operator_headers)
    suite = make_suite(client, evaluator_headers).json()
    version = make_rubric_version(client, evaluator_headers).json()

    run = make_eval_run(client, evaluator_headers, suite, version, stage_run_id)
    assert run.status_code == 201, run.text
    body = run.json()
    assert body["status"] == "awaiting_human_score"
    assert body["stage_run_id"] == stage_run_id
    assert body["workflow_run_id"] == wf_run["id"]


def test_run_target_type_must_match_suite(client, operator_headers, evaluator_headers) -> None:
    _wf_run, stage_run_id = make_workflow_stage(client, operator_headers)
    suite = make_suite(client, evaluator_headers, target_type="artifact").json()
    version = make_rubric_version(client, evaluator_headers).json()
    response = make_eval_run(
        client, evaluator_headers, suite, version, stage_run_id, target_type="stage_run"
    )
    assert response.status_code == 422


def test_run_unknown_target_404(client, evaluator_headers) -> None:
    suite = make_suite(client, evaluator_headers).json()
    version = make_rubric_version(client, evaluator_headers).json()
    response = make_eval_run(client, evaluator_headers, suite, version, str(uuid.uuid4()))
    assert response.status_code == 404


# -- scoring ----------------------------------------------------------------


@pytest.fixture
def awaiting_run(client, operator_headers, evaluator_headers) -> dict:
    _wf_run, stage_run_id = make_workflow_stage(client, operator_headers)
    suite = make_suite(client, evaluator_headers).json()
    version = make_rubric_version(client, evaluator_headers).json()
    return make_eval_run(client, evaluator_headers, suite, version, stage_run_id).json()


def test_score_validation(client, evaluator_headers, awaiting_run) -> None:
    wrong_keys = score(client, evaluator_headers, awaiting_run["id"], {"accuracy": 3})
    assert wrong_keys.status_code == 422
    assert "clarity" in wrong_keys.json()["detail"]

    out_of_range = score(
        client, evaluator_headers, awaiting_run["id"], {"accuracy": 9, "clarity": 3}
    )
    assert out_of_range.status_code == 422


def test_single_reviewer_pass_completes_run(
    client, evaluator_headers, admin_headers, awaiting_run
) -> None:
    response = score(client, evaluator_headers, awaiting_run["id"], PASSING)
    assert response.status_code == 201, response.text
    assert response.json()["pass_fail"] is True

    result = client.get(
        f"/evals/runs/{awaiting_run['id']}/result", headers=evaluator_headers
    ).json()
    assert result["run"]["status"] == "completed"
    assert result["decision"]["decision_type"] == "pass"
    assert result["decision"]["metrics_json"]["pass_votes"] == 1
    assert len(result["scores"]) == 1

    events = client.get(
        "/governance/audit-events",
        params={"event_type": "evals.result.recorded"},
        headers=admin_headers,
    ).json()
    assert len(events) == 1


def test_single_reviewer_fail(client, evaluator_headers, awaiting_run) -> None:
    score(client, evaluator_headers, awaiting_run["id"], FAILING)
    result = client.get(
        f"/evals/runs/{awaiting_run['id']}/result", headers=evaluator_headers
    ).json()
    assert result["decision"]["decision_type"] == "fail"


def test_duplicate_reviewer_rejected(client, operator_headers, evaluator_headers) -> None:
    _wf, stage_run_id = make_workflow_stage(client, operator_headers)
    suite = make_suite(client, evaluator_headers, min_reviewers=2).json()
    version = make_rubric_version(client, evaluator_headers).json()
    run = make_eval_run(client, evaluator_headers, suite, version, stage_run_id).json()

    assert score(client, evaluator_headers, run["id"], PASSING).status_code == 201
    assert score(client, evaluator_headers, run["id"], PASSING).status_code == 409


def test_score_after_completion_rejected(
    client, evaluator_headers, reviewer_headers, awaiting_run
) -> None:
    score(client, evaluator_headers, awaiting_run["id"], PASSING)
    late = score(client, reviewer_headers, awaiting_run["id"], PASSING)
    assert late.status_code == 409


def test_split_vote_needs_adjudication(
    client, db, operator_headers, evaluator_headers, reviewer_headers
) -> None:
    _wf, stage_run_id = make_workflow_stage(client, operator_headers)
    suite = make_suite(client, evaluator_headers, min_reviewers=2).json()
    version = make_rubric_version(client, evaluator_headers).json()
    run = make_eval_run(client, evaluator_headers, suite, version, stage_run_id).json()

    score(client, evaluator_headers, run["id"], PASSING)
    score(client, reviewer_headers, run["id"], FAILING)

    result = client.get(f"/evals/runs/{run['id']}/result", headers=evaluator_headers).json()
    assert result["decision"]["decision_type"] == "needs_adjudication"
    records = db.scalars(
        select(DisagreementRecord).where(DisagreementRecord.eval_run_id == uuid.UUID(run["id"]))
    ).all()
    assert len(records) == 1
    assert len(records[0].reviewer_score_ids_json) == 2


def test_majority_still_records_disagreement(
    client, db, operator_headers, evaluator_headers, reviewer_headers, admin_headers
) -> None:
    _wf, stage_run_id = make_workflow_stage(client, operator_headers)
    suite = make_suite(client, evaluator_headers, min_reviewers=3).json()
    version = make_rubric_version(client, evaluator_headers).json()
    run = make_eval_run(client, evaluator_headers, suite, version, stage_run_id).json()

    score(client, evaluator_headers, run["id"], PASSING)
    score(client, reviewer_headers, run["id"], PASSING)
    score(client, admin_headers, run["id"], FAILING)

    result = client.get(f"/evals/runs/{run['id']}/result", headers=evaluator_headers).json()
    # Spec 18.1: majority decides, but the split is durably recorded.
    assert result["decision"]["decision_type"] == "pass"
    records = db.scalars(
        select(DisagreementRecord).where(DisagreementRecord.eval_run_id == uuid.UUID(run["id"]))
    ).all()
    assert len(records) == 1


# -- RBAC -------------------------------------------------------------------


def test_operator_cannot_score(client, operator_headers, awaiting_run) -> None:
    assert score(client, operator_headers, awaiting_run["id"], PASSING).status_code == 403


def test_reviewer_can_score(client, reviewer_headers, awaiting_run) -> None:
    assert score(client, reviewer_headers, awaiting_run["id"], PASSING).status_code == 201


def test_operator_cannot_create_suite(client, operator_headers) -> None:
    assert make_suite(client, operator_headers).status_code == 403


# -- regression packs, baselines, drift --------------------------------------


def make_pack(client, headers, suite_ids, scope_ref="proj-a"):
    return client.post(
        "/evals/regression-packs",
        json={
            "name": "release gate",
            "eval_suite_ids": suite_ids,
            "scope_type": "project",
            "scope_ref": scope_ref,
        },
        headers=headers,
    )


def test_pack_rejects_unknown_suite(client, evaluator_headers) -> None:
    assert make_pack(client, evaluator_headers, [str(uuid.uuid4())]).status_code == 404


def test_missing_evidence_counts_as_fail_and_triggers_drift(
    client, operator_headers, evaluator_headers
) -> None:
    suite = make_suite(client, evaluator_headers).json()  # no completed decision
    pack = make_pack(client, evaluator_headers, [suite["id"]]).json()
    client.post(
        "/evals/baselines",
        json={
            "name": "release baseline",
            "scope_type": "project",
            "scope_ref": "proj-a",
            "baseline_data": {"pass_rate": 1.0},
        },
        headers=evaluator_headers,
    )

    pack_run = client.post(
        f"/evals/regression-packs/{pack['id']}/run", headers=evaluator_headers
    ).json()
    assert pack_run["pass_rate"] == 0.0
    assert pack_run["results_json"]["suites"][0]["outcome"] == "missing_evidence"

    signals = client.get("/evals/drift-signals", headers=evaluator_headers).json()
    assert len(signals) == 1
    assert signals[0]["signal_type"] == "regression_pass_rate_drop"
    assert signals[0]["signal_strength"] == 1.0


def test_passing_pack_produces_no_drift(client, operator_headers, evaluator_headers) -> None:
    _wf, stage_run_id = make_workflow_stage(client, operator_headers)
    suite = make_suite(client, evaluator_headers).json()
    version = make_rubric_version(client, evaluator_headers).json()
    run = make_eval_run(client, evaluator_headers, suite, version, stage_run_id).json()
    score(client, evaluator_headers, run["id"], PASSING)

    pack = make_pack(client, evaluator_headers, [suite["id"]]).json()
    client.post(
        "/evals/baselines",
        json={
            "name": "release baseline",
            "scope_type": "project",
            "scope_ref": "proj-a",
            "baseline_data": {"pass_rate": 1.0},
        },
        headers=evaluator_headers,
    )
    pack_run = client.post(
        f"/evals/regression-packs/{pack['id']}/run", headers=evaluator_headers
    ).json()
    assert pack_run["pass_rate"] == 1.0
    assert client.get("/evals/drift-signals", headers=evaluator_headers).json() == []


def test_pack_without_baseline_never_signals(client, operator_headers, evaluator_headers) -> None:
    suite = make_suite(client, evaluator_headers).json()
    pack = make_pack(client, evaluator_headers, [suite["id"]], scope_ref="no-baseline").json()
    pack_run = client.post(
        f"/evals/regression-packs/{pack['id']}/run", headers=evaluator_headers
    ).json()
    assert pack_run["pass_rate"] == 0.0
    assert client.get("/evals/drift-signals", headers=evaluator_headers).json() == []
