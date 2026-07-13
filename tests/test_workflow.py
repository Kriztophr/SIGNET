from app.platform.auth.models import Role
from tests.conftest import login_headers

SCOPE_CONTRACT = """# Contract: scope
## Identity
You are a research editor. Convert an ambiguous request into a bounded brief.
## Inputs
- initial_request.md
## Procedure
1. Apply the scoping skill.
## Outputs
- scope_brief: scope_brief.md — bounded, testable brief
- handoff: handoff.md — stage handoff
## Definition of done
- every field populated
## Failure modes
- silent scope expansion
"""

DRAFT_CONTRACT = """# Contract: draft
## Identity
You are a technical writer. Convert the signed brief into prose.
## Outputs
- draft: draft_v1.md — publishable prose
"""


def create_version(client, headers, *, review_required_first=False) -> dict:
    template = client.post(
        "/workflow/templates",
        json={"name": "Research report", "slug": "research-report"},
        headers=headers,
    )
    assert template.status_code == 201, template.text
    version = client.post(
        f"/workflow/templates/{template.json()['id']}/versions",
        json={
            "stages": [
                {
                    "stage_key": "scope",
                    "display_name": "Scope",
                    "order_index": 0,
                    "review_required": review_required_first,
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


def submit(client, headers, stage_run_id, role, content="content"):
    return client.post(
        f"/workflow/stage-runs/{stage_run_id}/artifacts",
        json={"artifact_role": role, "content": content},
        headers=headers,
    )


def test_template_and_version_creation(client, operator_headers) -> None:
    version = create_version(client, operator_headers)
    assert version["version_number"] == 1
    keys = [stage["stage_key"] for stage in version["stages"]]
    assert keys == ["scope", "draft"]
    assert all(stage["contract_source_ref"] for stage in version["stages"])


def test_duplicate_slug_rejected(client, operator_headers) -> None:
    create_version(client, operator_headers)
    response = client.post(
        "/workflow/templates",
        json={"name": "Again", "slug": "research-report"},
        headers=operator_headers,
    )
    assert response.status_code == 422


def test_invalid_contract_rejects_version(client, operator_headers) -> None:
    template = client.post(
        "/workflow/templates",
        json={"name": "Bad", "slug": "bad"},
        headers=operator_headers,
    )
    response = client.post(
        f"/workflow/templates/{template.json()['id']}/versions",
        json={
            "stages": [
                {
                    "stage_key": "s1",
                    "display_name": "S1",
                    "order_index": 0,
                    "contract_markdown": "## Identity\nSomeone.\n",  # no outputs
                }
            ]
        },
        headers=operator_headers,
    )
    assert response.status_code == 422
    assert "Outputs" in response.json()["detail"]


def test_gapped_order_index_rejected(client, operator_headers) -> None:
    template = client.post(
        "/workflow/templates",
        json={"name": "Gap", "slug": "gap"},
        headers=operator_headers,
    )
    response = client.post(
        f"/workflow/templates/{template.json()['id']}/versions",
        json={
            "stages": [
                {
                    "stage_key": "s1",
                    "display_name": "S1",
                    "order_index": 1,  # must start at 0
                    "contract_markdown": SCOPE_CONTRACT,
                }
            ]
        },
        headers=operator_headers,
    )
    assert response.status_code == 422


def test_run_end_to_end(client, operator_headers) -> None:
    """A two-stage run goes from start to completion: contract-checked
    artifact submission, stage handoff into the next stage's context, done."""
    version = create_version(client, operator_headers)

    run = client.post(
        "/workflow/runs",
        json={"workflow_template_version_id": version["id"]},
        headers=operator_headers,
    )
    assert run.status_code == 201, run.text
    run_body = run.json()
    assert run_body["status"] == "running"
    stage1_id = run_body["current_stage_run_id"]
    assert stage1_id is not None

    # ICM context manifest for stage 1: layers 0-2 set, no handoff inputs yet.
    manifest = client.get(
        f"/workflow/stage-runs/{stage1_id}/context-manifest", headers=operator_headers
    ).json()
    assert manifest["layer0_ref"].endswith("00_identity/workspace_identity.md")
    assert manifest["layer1_ref"].endswith("01_routing/router.md")
    assert manifest["layer2_ref"].endswith("02_stage_1_scope/03_contract/contract.md")
    assert manifest["layer4_inputs_json"] == []
    assert manifest["token_estimate"] > 0

    # Contracts are law: completing without the contracted outputs fails closed.
    premature = client.post(f"/workflow/stage-runs/{stage1_id}/complete", headers=operator_headers)
    assert premature.status_code == 422
    assert "handoff" in premature.json()["detail"]
    assert "scope_brief" in premature.json()["detail"]

    assert submit(client, operator_headers, stage1_id, "scope_brief", "brief v1").status_code == 201
    second = submit(client, operator_headers, stage1_id, "scope_brief", "brief v2")
    assert second.json()["version_number"] == 2
    assert submit(client, operator_headers, stage1_id, "handoff").status_code == 201

    completed = client.post(f"/workflow/stage-runs/{stage1_id}/complete", headers=operator_headers)
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "running"
    stage2_id = completed.json()["current_stage_run_id"]
    assert stage2_id != stage1_id

    stages = client.get(f"/workflow/runs/{run_body['id']}/stages", headers=operator_headers).json()
    assert [s["status"] for s in stages] == ["completed", "running"]

    # Handoff rule: stage 2's layer-4 inputs are stage 1's latest artifacts per role.
    manifest2 = client.get(
        f"/workflow/stage-runs/{stage2_id}/context-manifest", headers=operator_headers
    ).json()
    handed_off = {item["artifact_role"]: item for item in manifest2["layer4_inputs_json"]}
    assert set(handed_off) == {"scope_brief", "handoff"}
    assert handed_off["scope_brief"]["version_number"] == 2
    assert handed_off["scope_brief"]["from_stage_key"] == "scope"

    artifact = submit(client, operator_headers, stage2_id, "draft", "final prose")
    finished = client.post(f"/workflow/stage-runs/{stage2_id}/complete", headers=operator_headers)
    assert finished.json()["status"] == "completed"
    assert finished.json()["current_stage_run_id"] is None
    assert finished.json()["completed_at"] is not None

    content = client.get(
        f"/workflow/artifacts/{artifact.json()['id']}/content", headers=operator_headers
    )
    assert content.text == "final prose"
    assert content.headers["content-type"].startswith("text/markdown")


def test_review_required_stage_pauses_run(client, operator_headers) -> None:
    version = create_version(client, operator_headers, review_required_first=True)
    run = client.post(
        "/workflow/runs",
        json={"workflow_template_version_id": version["id"]},
        headers=operator_headers,
    ).json()
    stage1_id = run["current_stage_run_id"]
    submit(client, operator_headers, stage1_id, "scope_brief")
    submit(client, operator_headers, stage1_id, "handoff")

    paused = client.post(f"/workflow/stage-runs/{stage1_id}/complete", headers=operator_headers)
    assert paused.json()["status"] == "paused_for_review"
    stage = client.get(f"/workflow/stage-runs/{stage1_id}", headers=operator_headers).json()
    assert stage["status"] == "awaiting_review"

    # Nothing else is allowed while awaiting review.
    assert submit(client, operator_headers, stage1_id, "scope_brief").status_code == 409
    again = client.post(f"/workflow/stage-runs/{stage1_id}/complete", headers=operator_headers)
    assert again.status_code == 409


def test_fail_stage_fails_run(client, operator_headers) -> None:
    version = create_version(client, operator_headers)
    run = client.post(
        "/workflow/runs",
        json={"workflow_template_version_id": version["id"]},
        headers=operator_headers,
    ).json()
    failed = client.post(
        f"/workflow/stage-runs/{run['current_stage_run_id']}/fail",
        json={"error_summary": "executor crashed"},
        headers=operator_headers,
    )
    assert failed.json()["status"] == "failed"
    stage = client.get(
        f"/workflow/stage-runs/{run['current_stage_run_id']}", headers=operator_headers
    ).json()
    assert stage["status"] == "failed"
    assert stage["error_summary"] == "executor crashed"


def test_tenant_isolation(client, db, operator_headers) -> None:
    version = create_version(client, operator_headers)
    run = client.post(
        "/workflow/runs",
        json={"workflow_template_version_id": version["id"]},
        headers=operator_headers,
    ).json()

    other_tenant = login_headers(client, db, Role.operator, "other@example.com")
    assert client.get(f"/workflow/runs/{run['id']}", headers=other_tenant).status_code == 404
    assert (
        client.get(
            f"/workflow/stage-runs/{run['current_stage_run_id']}", headers=other_tenant
        ).status_code
        == 404
    )


def test_mutations_require_operator_role(client, db) -> None:
    reviewer = login_headers(client, db, Role.reviewer, "reviewer@example.com")
    response = client.post(
        "/workflow/templates",
        json={"name": "Nope", "slug": "nope"},
        headers=reviewer,
    )
    assert response.status_code == 403
