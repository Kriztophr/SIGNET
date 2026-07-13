"""Agent execution of automated stages (spec §28.7).

The fake adapter and a synchronous dispatcher stand in for Anthropic + Celery,
so these tests exercise the real executor, gates, ledger, and kill switch.
"""

import pytest
from sqlalchemy import select

from app.platform.llm.adapter import LLMResult, set_llm_adapter
from app.platform.llm.models import LLMUsage
from app.tasks.agent_tasks import set_agent_dispatcher
from app.workflow.services.agent_execution import AgentStageExecutor

AGENT_CONTRACT = """# Contract: draft
## Identity
You are a technical writer. Convert the signed brief into prose.
## Outputs
- draft: draft_v1.md — publishable prose
- self_review: self_review.md — honest gaps list
"""

GOOD_RESPONSE = """<<<ARTIFACT role="draft">>>
# Draft
Prose produced by the agent.
<<<END ARTIFACT>>>
<<<ARTIFACT role="self_review">>>
- no gaps found
<<<END ARTIFACT>>>"""


class FakeAdapter:
    def __init__(self, text=GOOD_RESPONSE, error: Exception | None = None) -> None:
        self.text = text
        self.error = error
        self.calls: list[dict] = []

    def complete(self, *, model, system, user_content, max_tokens) -> LLMResult:
        self.calls.append({"model": model, "system": system, "user_content": user_content})
        if self.error is not None:
            raise self.error
        return LLMResult(text=self.text, model=model, input_tokens=1200, output_tokens=800)


@pytest.fixture(autouse=True)
def _reset_seams(db, storage):
    """Synchronous dispatch through the real executor; reset both seams after."""
    set_agent_dispatcher(
        lambda stage_run_id: AgentStageExecutor(db, storage).execute_stage(stage_run_id)
    )
    yield
    set_agent_dispatcher(None)
    set_llm_adapter(None)


def create_automated_version(client, headers, *, review_required=False, eval_required=False):
    template = client.post(
        "/workflow/templates",
        json={"name": "Agent report", "slug": "agent-report"},
        headers=headers,
    )
    assert template.status_code == 201, template.text
    version = client.post(
        f"/workflow/templates/{template.json()['id']}/versions",
        json={
            "stages": [
                {
                    "stage_key": "draft",
                    "display_name": "Draft",
                    "order_index": 0,
                    "execution_mode": "automated",
                    "review_required": review_required,
                    "eval_required": eval_required,
                    "contract_markdown": AGENT_CONTRACT,
                },
                {
                    "stage_key": "finalize",
                    "display_name": "Finalize",
                    "order_index": 1,
                    "contract_markdown": (
                        "## Identity\nPublisher.\n## Outputs\n- final: final.md — done\n"
                    ),
                },
            ]
        },
        headers=headers,
    )
    assert version.status_code == 201, version.text
    return version.json()


def start_run(client, headers, version):
    run = client.post(
        "/workflow/runs",
        json={"workflow_template_version_id": version["id"]},
        headers=headers,
    )
    assert run.status_code == 201, run.text
    return run.json()


def test_automated_stage_executes_and_advances(client, db, operator_headers) -> None:
    fake = FakeAdapter()
    set_llm_adapter(fake)
    version = create_automated_version(client, operator_headers)

    run = start_run(client, operator_headers, version)

    # The agent completed the draft stage; the run advanced to finalize.
    stages = client.get(f"/workflow/runs/{run['id']}/stages", headers=operator_headers).json()
    assert [s["status"] for s in stages] == ["completed", "running"]

    artifacts = client.get(
        f"/workflow/stage-runs/{stages[0]['id']}/artifacts", headers=operator_headers
    ).json()
    assert {a["artifact_role"] for a in artifacts} == {"draft", "self_review"}
    assert all(a["created_by_type"] == "agent" for a in artifacts)

    # The contract was the system prompt (with the required roles named
    # explicitly); usage was recorded with real cost.
    assert "Contract: draft" in fake.calls[0]["system"]
    assert '"draft", "self_review"' in fake.calls[0]["system"]
    usage = db.execute(select(LLMUsage)).scalars().all()
    assert len(usage) == 1
    assert usage[0].purpose == "executor"
    assert float(usage[0].cost_usd) > 0


def test_agent_work_still_pauses_for_review_gate(client, operator_headers) -> None:
    set_llm_adapter(FakeAdapter())
    version = create_automated_version(client, operator_headers, review_required=True)

    run = start_run(client, operator_headers, version)

    fetched = client.get(f"/workflow/runs/{run['id']}", headers=operator_headers).json()
    assert fetched["status"] == "paused_for_review"


def test_agent_failure_degrades_to_manual(client, operator_headers) -> None:
    set_llm_adapter(FakeAdapter(error=RuntimeError("provider down")))
    version = create_automated_version(client, operator_headers)

    run = start_run(client, operator_headers, version)

    stages = client.get(f"/workflow/runs/{run['id']}/stages", headers=operator_headers).json()
    assert stages[0]["status"] == "running"  # left for a human, run not killed
    assert "agent execution failed" in stages[0]["error_summary"]
    assert "manual completion" in stages[0]["error_summary"]


def test_missing_contract_outputs_degrade_to_manual(client, operator_headers) -> None:
    set_llm_adapter(FakeAdapter(text='<<<ARTIFACT role="draft">>>\nonly one\n<<<END ARTIFACT>>>'))
    version = create_automated_version(client, operator_headers)

    run = start_run(client, operator_headers, version)

    stages = client.get(f"/workflow/runs/{run['id']}/stages", headers=operator_headers).json()
    assert stages[0]["status"] == "running"
    assert "self_review" in stages[0]["error_summary"]


def test_lenient_parse_filename_role_and_missing_end_tag(client, operator_headers) -> None:
    """Executor output parsing tolerates real open-model sloppiness: blocks
    labelled with the filename instead of the role, and a missing closing tag."""
    # Both failure modes observed with gpt-oss-120b on prod (2026-07-12): the
    # block labelled with the contract FILENAME instead of the role, and the
    # final block missing its <<<END ARTIFACT>>> closing tag.
    sloppy = (
        '<<<ARTIFACT role="draft_v1.md">>>\n# Draft\nProse.\n<<<END ARTIFACT>>>\n'
        '<<<ARTIFACT role="self_review">>>\n- no gaps found\n'
    )
    set_llm_adapter(FakeAdapter(text=sloppy))
    version = create_automated_version(client, operator_headers)

    run = start_run(client, operator_headers, version)

    stages = client.get(f"/workflow/runs/{run['id']}/stages", headers=operator_headers).json()
    assert [s["status"] for s in stages] == ["completed", "running"]
    artifacts = client.get(
        f"/workflow/stage-runs/{stages[0]['id']}/artifacts", headers=operator_headers
    ).json()
    assert {a["artifact_role"] for a in artifacts} == {"draft", "self_review"}


def test_exact_role_block_wins_over_filename_alias(client, operator_headers) -> None:
    """When the model emits both an exact role block and a filename-labelled
    one, the exact role wins."""
    # 'draft_v1.md' aliases to 'draft', but an exact 'draft' block must win.
    text = (
        '<<<ARTIFACT role="draft_v1.md">>>\nalias content\n<<<END ARTIFACT>>>\n'
        '<<<ARTIFACT role="draft">>>\nexact content\n<<<END ARTIFACT>>>\n'
        '<<<ARTIFACT role="self_review">>>\n- ok\n<<<END ARTIFACT>>>'
    )
    set_llm_adapter(FakeAdapter(text=text))
    version = create_automated_version(client, operator_headers)

    run = start_run(client, operator_headers, version)

    stages = client.get(f"/workflow/runs/{run['id']}/stages", headers=operator_headers).json()
    artifacts = client.get(
        f"/workflow/stage-runs/{stages[0]['id']}/artifacts", headers=operator_headers
    ).json()
    draft = next(a for a in artifacts if a["artifact_role"] == "draft")
    content = client.get(f"/workflow/artifacts/{draft['id']}/content", headers=operator_headers)
    assert content.text.strip() == "exact content"


def test_budget_cap_blocks_agent_execution(client, db, tenant_id, operator_headers) -> None:
    # Exhaust the monthly budget before the run starts.
    db.add(
        LLMUsage(
            tenant_id=tenant_id,
            model="claude-opus-4-8",
            purpose="executor",
            input_tokens=1,
            output_tokens=1,
            cost_usd=50.0,
        )
    )
    db.flush()
    fake = FakeAdapter()
    set_llm_adapter(fake)
    version = create_automated_version(client, operator_headers)

    run = start_run(client, operator_headers, version)

    stages = client.get(f"/workflow/runs/{run['id']}/stages", headers=operator_headers).json()
    assert stages[0]["status"] == "running"
    assert "budget exhausted" in stages[0]["error_summary"]
    assert fake.calls == []  # fail closed: the model was never called


def test_cancel_run_kill_switch(client, operator_headers) -> None:
    """The operator kill switch cancels a running run and fails its open
    stages; a second cancel is rejected."""
    # Manual template so the run sits at a running stage.
    template = client.post(
        "/workflow/templates",
        json={"name": "Manual", "slug": "manual-cancel"},
        headers=operator_headers,
    ).json()
    version = client.post(
        f"/workflow/templates/{template['id']}/versions",
        json={
            "stages": [
                {
                    "stage_key": "scope",
                    "display_name": "Scope",
                    "order_index": 0,
                    "contract_markdown": (
                        "## Identity\nScoper.\n## Outputs\n- brief: brief.md — the brief\n"
                    ),
                }
            ]
        },
        headers=operator_headers,
    ).json()
    run = start_run(client, operator_headers, version)

    cancelled = client.post(f"/workflow/runs/{run['id']}/cancel", headers=operator_headers)
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["current_stage_run_id"] is None

    stages = client.get(f"/workflow/runs/{run['id']}/stages", headers=operator_headers).json()
    assert stages[0]["status"] == "failed"
    assert "cancelled" in stages[0]["error_summary"]

    again = client.post(f"/workflow/runs/{run['id']}/cancel", headers=operator_headers)
    assert again.status_code == 409


def test_cancelled_run_never_executes_agent(client, db, storage, operator_headers) -> None:
    """An agent task that arrives after its run was cancelled does nothing —
    the kill switch wins the race."""
    # Queue the dispatch (deferred), cancel, then let the "worker" run late.
    queued: list = []
    set_agent_dispatcher(queued.append)
    fake = FakeAdapter()
    set_llm_adapter(fake)

    version = create_automated_version(client, operator_headers)
    run = start_run(client, operator_headers, version)
    assert len(queued) == 1

    assert (
        client.post(f"/workflow/runs/{run['id']}/cancel", headers=operator_headers).status_code
        == 200
    )

    AgentStageExecutor(db, storage).execute_stage(queued[0])  # late worker
    assert fake.calls == []  # kill switch honoured: no model call, no artifacts
