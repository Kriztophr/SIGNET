from tests.test_evals import (
    FAILING,
    PASSING,
    make_eval_run,
    make_rubric_version,
    make_suite,
    score,
)
from tests.test_workflow import DRAFT_CONTRACT, SCOPE_CONTRACT, submit


def eval_gated_version(client, headers, *, review_required_first=False) -> dict:
    template = client.post(
        "/workflow/templates",
        json={"name": "Gated report", "slug": "gated-report"},
        headers=headers,
    ).json()
    version = client.post(
        f"/workflow/templates/{template['id']}/versions",
        json={
            "stages": [
                {
                    "stage_key": "scope",
                    "display_name": "Scope",
                    "order_index": 0,
                    "review_required": review_required_first,
                    "eval_required": True,
                    "contract_markdown": SCOPE_CONTRACT,
                },
                {
                    "stage_key": "draft",
                    "display_name": "Draft",
                    "order_index": 1,
                    "contract_markdown": DRAFT_CONTRACT,
                },
            ]
        },
        headers=headers,
    )
    assert version.status_code == 201, version.text
    return version.json()


def start_gated_run(client, operator_headers, **kwargs) -> tuple[dict, str]:
    version = eval_gated_version(client, operator_headers, **kwargs)
    run = client.post(
        "/workflow/runs",
        json={"workflow_template_version_id": version["id"]},
        headers=operator_headers,
    ).json()
    stage1_id = run["current_stage_run_id"]
    submit(client, operator_headers, stage1_id, "scope_brief", "the brief")
    submit(client, operator_headers, stage1_id, "handoff", "the handoff")
    return run, stage1_id


def eval_the_stage(client, evaluator_headers, stage_run_id, *, min_reviewers=1) -> dict:
    suite = make_suite(client, evaluator_headers, min_reviewers=min_reviewers).json()
    version = make_rubric_version(client, evaluator_headers).json()
    return make_eval_run(client, evaluator_headers, suite, version, stage_run_id).json()


def test_eval_required_stage_pauses(client, operator_headers) -> None:
    run, stage1_id = start_gated_run(client, operator_headers)
    paused = client.post(
        f"/workflow/stage-runs/{stage1_id}/complete", headers=operator_headers
    ).json()
    assert paused["status"] == "paused_for_eval"
    stage = client.get(f"/workflow/stage-runs/{stage1_id}", headers=operator_headers).json()
    assert stage["status"] == "awaiting_eval"


def test_eval_pass_resumes_and_hands_off(client, operator_headers, evaluator_headers) -> None:
    run, stage1_id = start_gated_run(client, operator_headers)
    client.post(f"/workflow/stage-runs/{stage1_id}/complete", headers=operator_headers)

    eval_run = eval_the_stage(client, evaluator_headers, stage1_id)
    score(client, evaluator_headers, eval_run["id"], PASSING)

    resumed = client.get(f"/workflow/runs/{run['id']}", headers=operator_headers).json()
    assert resumed["status"] == "running"
    stage2_id = resumed["current_stage_run_id"]
    assert stage2_id != stage1_id
    stage1 = client.get(f"/workflow/stage-runs/{stage1_id}", headers=operator_headers).json()
    assert stage1["status"] == "completed"

    manifest = client.get(
        f"/workflow/stage-runs/{stage2_id}/context-manifest", headers=operator_headers
    ).json()
    roles = {item["artifact_role"] for item in manifest["layer4_inputs_json"]}
    assert roles == {"scope_brief", "handoff"}


def test_eval_fail_fails_run(client, operator_headers, evaluator_headers) -> None:
    run, stage1_id = start_gated_run(client, operator_headers)
    client.post(f"/workflow/stage-runs/{stage1_id}/complete", headers=operator_headers)

    eval_run = eval_the_stage(client, evaluator_headers, stage1_id)
    score(client, evaluator_headers, eval_run["id"], FAILING)

    failed = client.get(f"/workflow/runs/{run['id']}", headers=operator_headers).json()
    assert failed["status"] == "failed"
    stage1 = client.get(f"/workflow/stage-runs/{stage1_id}", headers=operator_headers).json()
    assert stage1["status"] == "failed"
    assert "eval" in stage1["error_summary"]


def test_adjudication_split_keeps_paused_second_run_unblocks(
    client, db, operator_headers, evaluator_headers, reviewer_headers
) -> None:
    """A split reviewer vote leaves the stage paused for adjudication; a
    second, agreeing eval run then unblocks it."""
    run, stage1_id = start_gated_run(client, operator_headers)
    client.post(f"/workflow/stage-runs/{stage1_id}/complete", headers=operator_headers)

    split_run = eval_the_stage(client, evaluator_headers, stage1_id, min_reviewers=2)
    score(client, evaluator_headers, split_run["id"], PASSING)
    score(client, reviewer_headers, split_run["id"], FAILING)

    still_paused = client.get(f"/workflow/runs/{run['id']}", headers=operator_headers).json()
    assert still_paused["status"] == "paused_for_eval"

    second = eval_the_stage(client, evaluator_headers, stage1_id)
    score(client, evaluator_headers, second["id"], PASSING)
    resumed = client.get(f"/workflow/runs/{run['id']}", headers=operator_headers).json()
    assert resumed["status"] == "running"


def test_pre_existing_pass_skips_pause(client, operator_headers, evaluator_headers) -> None:
    """Deadlock guard: an eval completed before the stage reaches the gate counts."""
    _run, stage1_id = start_gated_run(client, operator_headers)
    eval_run = eval_the_stage(client, evaluator_headers, stage1_id)
    score(client, evaluator_headers, eval_run["id"], PASSING)  # stage still running

    completed = client.post(
        f"/workflow/stage-runs/{stage1_id}/complete", headers=operator_headers
    ).json()
    assert completed["status"] == "running"  # advanced straight through
    stage1 = client.get(f"/workflow/stage-runs/{stage1_id}", headers=operator_headers).json()
    assert stage1["status"] == "completed"


def test_manual_fail_from_awaiting_eval(client, operator_headers) -> None:
    """An operator can manually fail a stage waiting at the eval gate, which
    fails the whole run."""
    run, stage1_id = start_gated_run(client, operator_headers)
    client.post(f"/workflow/stage-runs/{stage1_id}/complete", headers=operator_headers)
    failed = client.post(
        f"/workflow/stage-runs/{stage1_id}/fail",
        json={"error_summary": "operator abort"},
        headers=operator_headers,
    )
    assert failed.status_code == 200
    assert failed.json()["status"] == "failed"


def test_review_then_eval_hands_off_edited_artifact(
    client, operator_headers, evaluator_headers, reviewer_headers
) -> None:
    run, stage1_id = start_gated_run(client, operator_headers, review_required_first=True)
    paused = client.post(
        f"/workflow/stage-runs/{stage1_id}/complete", headers=operator_headers
    ).json()
    assert paused["status"] == "paused_for_review"  # review takes precedence

    task = client.get(
        "/governance/review-tasks", params={"status": "open"}, headers=operator_headers
    ).json()[0]
    client.post(
        f"/governance/review-tasks/{task['id']}/edit",
        json={
            "rationale": "tightened",
            "artifact_role": "scope_brief",
            "content": "edited brief",
        },
        headers=reviewer_headers,
    )

    # After review resolution the eval gate engages.
    gated = client.get(f"/workflow/runs/{run['id']}", headers=operator_headers).json()
    assert gated["status"] == "paused_for_eval"

    eval_run = eval_the_stage(client, evaluator_headers, stage1_id)
    score(client, evaluator_headers, eval_run["id"], PASSING)

    resumed = client.get(f"/workflow/runs/{run['id']}", headers=operator_headers).json()
    assert resumed["status"] == "running"
    manifest = client.get(
        f"/workflow/stage-runs/{resumed['current_stage_run_id']}/context-manifest",
        headers=operator_headers,
    ).json()
    handed = {i["artifact_role"]: i for i in manifest["layer4_inputs_json"]}
    assert handed["scope_brief"]["version_number"] == 2  # the reviewer-edited version
