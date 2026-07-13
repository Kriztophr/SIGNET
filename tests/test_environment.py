import pytest

from app.platform.auth.models import Role
from tests.conftest import login_headers
from tests.test_evals import (
    PASSING,
    make_eval_run,
    make_rubric_version,
    make_suite,
    score,
)
from tests.test_workflow import DRAFT_CONTRACT, SCOPE_CONTRACT


@pytest.fixture
def manager_headers(client, db, tenant_id) -> dict:
    return login_headers(
        client, db, Role.environment_manager, "envmgr@example.com", tenant_id=tenant_id
    )


def make_env_template(client, headers, slug="acme-env") -> dict:
    return client.post(
        "/environment/templates",
        json={"name": "Acme environment", "slug": slug},
        headers=headers,
    ).json()


def make_env_version(client, headers, template_id) -> dict:
    return client.post(
        f"/environment/templates/{template_id}/versions",
        json={
            "prompt_profiles": [{"name": "default", "instructions": {"tone": "neutral"}}],
            "tool_profiles": [{"name": "safe", "allowed_tools": ["search"]}],
            "policy_profiles": [{"name": "strict", "default_gate_settings": {"review": True}}],
            "domain_schemas": [{"name": "invoice", "schema": {"total": "number"}}],
        },
        headers=headers,
    )


# -- templates, versions, profiles ------------------------------------------


def test_template_and_version_creation(client, manager_headers) -> None:
    template = make_env_template(client, manager_headers)
    assert template["status"] == "draft"
    version = make_env_version(client, manager_headers, template["id"])
    assert version.status_code == 201, version.text
    body = version.json()
    assert body["version_number"] == 1
    assert [p["name"] for p in body["prompt_profiles"]] == ["default"]
    assert [p["name"] for p in body["tool_profiles"]] == ["safe"]
    assert [p["name"] for p in body["policy_profiles"]] == ["strict"]


def test_duplicate_slug_rejected(client, manager_headers) -> None:
    make_env_template(client, manager_headers)
    dup = client.post(
        "/environment/templates",
        json={"name": "Again", "slug": "acme-env"},
        headers=manager_headers,
    )
    assert dup.status_code == 422


def test_reference_bundle_and_blueprint(client, manager_headers) -> None:
    """Reference bundles and workspace blueprints attach to an environment
    version and read back intact (without leaking storage URIs)."""
    template = make_env_template(client, manager_headers)
    version = make_env_version(client, manager_headers, template["id"]).json()

    bundle = client.post(
        "/environment/reference-bundles",
        json={
            "environment_template_version_id": version["id"],
            "name": "glossary",
            "bundle_type": "reference",
            "content": "# Glossary\nterm: definition",
            "manifest": {"files": 1},
        },
        headers=manager_headers,
    )
    assert bundle.status_code == 201, bundle.text
    assert bundle.json()["manifest_json"] == {"files": 1}
    assert "storage_uri" not in bundle.json()  # spec 25: no storage refs in responses

    blueprint = client.post(
        "/environment/workspace-blueprints",
        json={
            "environment_template_version_id": version["id"],
            "name": "icm-layout",
            "blueprint": {"layers": ["identity", "routing"]},
        },
        headers=manager_headers,
    )
    assert blueprint.status_code == 201, blueprint.text
    fetched_version = client.get(
        f"/environment/versions/{version['id']}", headers=manager_headers
    ).json()
    assert fetched_version["workspace_blueprint_ref"] == blueprint.json()["id"]


# -- promotion evidence gate ------------------------------------------------


def workflow_version_on_env(client, operator_headers, env_version_id, slug) -> dict:
    """Create a workflow template + version bound to the given environment version,
    so runs (and the evals targeting them) inherit that environment linkage."""
    template = client.post(
        "/workflow/templates",
        json={"name": "Env-bound flow", "slug": slug},
        headers=operator_headers,
    ).json()
    version = client.post(
        f"/workflow/templates/{template['id']}/versions",
        json={
            "environment_template_version_id": env_version_id,
            "stages": [
                {
                    "stage_key": "scope",
                    "display_name": "Scope",
                    "order_index": 0,
                    "contract_markdown": SCOPE_CONTRACT,
                },
                {
                    "stage_key": "draft",
                    "display_name": "Draft",
                    "order_index": 1,
                    "contract_markdown": DRAFT_CONTRACT,
                },
            ],
        },
        headers=operator_headers,
    )
    assert version.status_code == 201, version.text
    return version.json()


_slug_counter = iter(range(1000))


def eval_a_workflow_stage_on_version(
    client, operator_headers, evaluator_headers, env_version_id, *, passing=True
):
    """Run a workflow stage bound to the env version, then eval it. The eval run
    derives environment_template_version_id from the workflow run's environment."""
    wf_version = workflow_version_on_env(
        client, operator_headers, env_version_id, f"env-flow-{next(_slug_counter)}"
    )
    run = client.post(
        "/workflow/runs",
        json={"workflow_template_version_id": wf_version["id"]},
        headers=operator_headers,
    ).json()
    stage_run_id = run["current_stage_run_id"]
    suite = make_suite(client, evaluator_headers).json()
    rubric = make_rubric_version(client, evaluator_headers).json()
    eval_run = make_eval_run(client, evaluator_headers, suite, rubric, stage_run_id).json()
    assert eval_run["environment_template_version_id"] == env_version_id
    score(
        client,
        evaluator_headers,
        eval_run["id"],
        PASSING if passing else {"accuracy": 1, "clarity": 1},
    )
    return eval_run


def test_promotion_blocked_without_evidence(client, manager_headers) -> None:
    template = make_env_template(client, manager_headers)
    version = make_env_version(client, manager_headers, template["id"]).json()

    promotion = client.post(
        "/environment/promotions",
        json={"environment_template_version_id": version["id"]},
        headers=manager_headers,
    )
    assert promotion.status_code == 201, promotion.text
    body = promotion.json()
    # Fail closed: no eval evidence linked to the version.
    assert body["status"] == "blocked"
    assert "no eval runs" in body["decision_reason"]


def test_promotion_approval_flow(
    client, manager_headers, operator_headers, evaluator_headers
) -> None:
    template = make_env_template(client, manager_headers)
    version = make_env_version(client, manager_headers, template["id"]).json()
    eval_a_workflow_stage_on_version(
        client, operator_headers, evaluator_headers, version["id"], passing=True
    )

    promotion = client.post(
        "/environment/promotions",
        json={"environment_template_version_id": version["id"]},
        headers=manager_headers,
    ).json()
    assert promotion["status"] == "approval_pending"
    assert promotion["evidence_json"]["eval_runs"]["passed"] == 1

    approved = client.post(
        f"/environment/promotions/{promotion['id']}/approve", headers=manager_headers
    )
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["status"] == "approved"
    assert body["approved_by"] is not None
    assert body["approved_at"] is not None


def test_promotion_blocked_by_failed_eval(
    client, manager_headers, operator_headers, evaluator_headers
) -> None:
    template = make_env_template(client, manager_headers)
    version = make_env_version(client, manager_headers, template["id"]).json()
    eval_a_workflow_stage_on_version(
        client, operator_headers, evaluator_headers, version["id"], passing=False
    )

    promotion = client.post(
        "/environment/promotions",
        json={"environment_template_version_id": version["id"]},
        headers=manager_headers,
    ).json()
    assert promotion["status"] == "blocked"
    assert "failed eval run" in promotion["decision_reason"]


def test_promotion_blocked_by_regression_pack(
    client, manager_headers, operator_headers, evaluator_headers
) -> None:
    template = make_env_template(client, manager_headers)
    version = make_env_version(client, manager_headers, template["id"]).json()
    eval_a_workflow_stage_on_version(
        client, operator_headers, evaluator_headers, version["id"], passing=True
    )

    # A regression pack whose only suite has no completed decision => pass_rate 0.
    empty_suite = make_suite(client, evaluator_headers).json()
    pack = client.post(
        "/evals/regression-packs",
        json={
            "name": "release gate",
            "eval_suite_ids": [empty_suite["id"]],
            "scope_type": "environment",
            "scope_ref": version["id"],
        },
        headers=evaluator_headers,
    ).json()
    client.post(f"/evals/regression-packs/{pack['id']}/run", headers=evaluator_headers)

    promotion = client.post(
        "/environment/promotions",
        json={
            "environment_template_version_id": version["id"],
            "requirements": {"regression_pack_ids": [pack["id"]]},
        },
        headers=manager_headers,
    ).json()
    assert promotion["status"] == "blocked"
    assert "pass rate" in promotion["decision_reason"]


def test_cannot_approve_blocked_promotion(client, manager_headers) -> None:
    template = make_env_template(client, manager_headers)
    version = make_env_version(client, manager_headers, template["id"]).json()
    promotion = client.post(
        "/environment/promotions",
        json={"environment_template_version_id": version["id"]},
        headers=manager_headers,
    ).json()
    assert promotion["status"] == "blocked"
    denied = client.post(
        f"/environment/promotions/{promotion['id']}/approve", headers=manager_headers
    )
    assert denied.status_code == 409


def test_promotion_audit_trail(
    client, manager_headers, operator_headers, evaluator_headers, admin_headers
) -> None:
    template = make_env_template(client, manager_headers)
    version = make_env_version(client, manager_headers, template["id"]).json()
    eval_a_workflow_stage_on_version(
        client, operator_headers, evaluator_headers, version["id"], passing=True
    )
    promotion = client.post(
        "/environment/promotions",
        json={"environment_template_version_id": version["id"]},
        headers=manager_headers,
    ).json()
    client.post(f"/environment/promotions/{promotion['id']}/approve", headers=manager_headers)

    events = client.get(
        "/governance/audit-events",
        params={"event_type": "environment.promotion.approved"},
        headers=admin_headers,
    ).json()
    assert len(events) == 1
    assert events[0]["environment_promotion_id"] == promotion["id"]


# -- RBAC and isolation -----------------------------------------------------


def test_operator_cannot_create_environment(client, operator_headers) -> None:
    denied = client.post(
        "/environment/templates",
        json={"name": "Nope", "slug": "nope"},
        headers=operator_headers,
    )
    assert denied.status_code == 403


def test_tenant_isolation(client, db, manager_headers) -> None:
    template = make_env_template(client, manager_headers)
    other = login_headers(client, db, Role.environment_manager, "other-mgr@example.com")
    assert client.get(f"/environment/templates/{template['id']}", headers=other).status_code == 404
