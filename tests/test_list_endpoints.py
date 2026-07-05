"""List endpoints added for the operations console (phase 13)."""

from app.platform.auth.models import Role
from tests.conftest import login_headers
from tests.test_evals import make_eval_run, make_rubric_version, make_suite
from tests.test_workflow import create_version, submit


def start_run(client, operator_headers):
    version = create_version(client, operator_headers)
    run = client.post(
        "/workflow/runs",
        json={"workflow_template_version_id": version["id"]},
        headers=operator_headers,
    ).json()
    return version, run


def test_list_templates_and_runs(client, operator_headers) -> None:
    _version, run = start_run(client, operator_headers)

    templates = client.get("/workflow/templates", headers=operator_headers).json()
    assert [t["slug"] for t in templates] == ["research-report"]

    runs = client.get("/workflow/runs", headers=operator_headers).json()
    assert [r["id"] for r in runs] == [run["id"]]


def test_list_stage_artifacts(client, operator_headers) -> None:
    _version, run = start_run(client, operator_headers)
    stage_id = run["current_stage_run_id"]
    submit(client, operator_headers, stage_id, "scope_brief", "v1")
    submit(client, operator_headers, stage_id, "scope_brief", "v2")

    artifacts = client.get(
        f"/workflow/stage-runs/{stage_id}/artifacts", headers=operator_headers
    ).json()
    assert [(a["artifact_role"], a["version_number"]) for a in artifacts] == [
        ("scope_brief", 1),
        ("scope_brief", 2),
    ]


def test_list_eval_runs_with_status_filter(client, operator_headers, evaluator_headers) -> None:
    _version, run = start_run(client, operator_headers)
    suite = make_suite(client, evaluator_headers).json()
    rubric = make_rubric_version(client, evaluator_headers).json()
    eval_run = make_eval_run(
        client, evaluator_headers, suite, rubric, run["current_stage_run_id"]
    ).json()

    awaiting = client.get(
        "/evals/runs",
        params={"status": "awaiting_human_score"},
        headers=evaluator_headers,
    ).json()
    assert [r["id"] for r in awaiting] == [eval_run["id"]]
    completed = client.get(
        "/evals/runs", params={"status": "completed"}, headers=evaluator_headers
    ).json()
    assert completed == []

    version_out = client.get(
        f"/evals/rubric-versions/{eval_run['rubric_version_id']}",
        headers=evaluator_headers,
    ).json()
    assert version_out["criteria_json"][0]["key"] == "accuracy"


def test_list_promotions(client, db, tenant_id) -> None:
    from tests.test_environment import make_env_template, make_env_version

    manager = login_headers(
        client, db, Role.environment_manager, "envmgr@example.com", tenant_id=tenant_id
    )
    template = make_env_template(client, manager)
    version = make_env_version(client, manager, template["id"]).json()
    promotion = client.post(
        "/environment/promotions",
        json={"environment_template_version_id": version["id"]},
        headers=manager,
    ).json()

    listed = client.get("/environment/promotions", headers=manager).json()
    assert [p["id"] for p in listed] == [promotion["id"]]


def test_lists_are_tenant_scoped(client, db, operator_headers) -> None:
    start_run(client, operator_headers)
    other = login_headers(client, db, Role.operator, "other-lister@example.com")
    assert client.get("/workflow/runs", headers=other).json() == []
    assert client.get("/workflow/templates", headers=other).json() == []
