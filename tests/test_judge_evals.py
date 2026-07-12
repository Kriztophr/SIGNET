"""LLM-judge scoring of eval runs (spec §28.8).

The judge is advisory: it records an agent ReviewerScore against the human
rubric, never counts toward min_reviewers, and never decides a gate. Sustained
judge-vs-human disagreement emits a DriftSignal and auto-widens sampling.
"""

import json
import uuid

import pytest
from sqlalchemy import select

from app.evals.models.entities import DriftSignal, ReviewerScore
from app.evals.services.judge import JUDGE_REVIEWER_ID, JudgeEvalService
from app.platform.llm.adapter import LLMResult, set_llm_adapter
from app.platform.llm.models import LLMUsage
from app.platform.time.clock import utc_now
from app.tasks.judge_tasks import set_judge_dispatcher
from app.workflow.models.entities import ActorType
from tests.test_evals import (
    FAILING,
    PASSING,
    make_eval_run,
    make_rubric_version,
    make_workflow_stage,
    score,
)

JUDGE_PASSING = json.dumps({"scores": PASSING, "rationale": "accurate and clear"})
JUDGE_FAILING = json.dumps({"scores": FAILING, "rationale": "weak on both criteria"})


class FakeAdapter:
    def __init__(self, text=JUDGE_PASSING, error: Exception | None = None) -> None:
        self.text = text
        self.error = error
        self.calls: list[dict] = []

    def complete(self, *, model, system, user_content, max_tokens) -> LLMResult:
        self.calls.append({"model": model, "system": system, "user_content": user_content})
        if self.error is not None:
            raise self.error
        return LLMResult(text=self.text, model=model, input_tokens=900, output_tokens=150)


@pytest.fixture(autouse=True)
def _reset_seams(db, storage):
    """Synchronous dispatch through the real judge service; reset after."""
    set_judge_dispatcher(lambda eval_run_id: JudgeEvalService(db, storage).score_run(eval_run_id))
    yield
    set_judge_dispatcher(None)
    set_llm_adapter(None)


def make_judge_suite(client, headers, *, min_reviewers=1, sampling_rate=1.0, **judge_overrides):
    return client.post(
        "/evals/suites",
        json={
            "name": "Judge-assisted quality",
            "target_type": "stage_run",
            "config": {
                "min_reviewers": min_reviewers,
                "llm_judge": {
                    "enabled": True,
                    "sampling_rate": sampling_rate,
                    "agreement_threshold": 0.8,
                    "window": 5,
                    **judge_overrides,
                },
            },
            "cases": [{"name": "judge the output", "prompt_or_instruction": "Score the output."}],
        },
        headers=headers,
    ).json()


def judge_scores(db, eval_run_id: str) -> list[ReviewerScore]:
    return list(
        db.scalars(
            select(ReviewerScore).where(
                ReviewerScore.eval_run_id == uuid.UUID(eval_run_id),
                ReviewerScore.scored_by_type == ActorType.agent,
            )
        )
    )


def test_judge_scores_on_run_creation_but_never_decides(
    client, db, operator_headers, evaluator_headers
) -> None:
    fake = FakeAdapter()
    set_llm_adapter(fake)
    _wf, stage_run_id = make_workflow_stage(client, operator_headers)
    suite = make_judge_suite(client, evaluator_headers)
    version = make_rubric_version(client, evaluator_headers).json()

    run = make_eval_run(client, evaluator_headers, suite, version, stage_run_id).json()

    # Judge scored against the rubric, but the run still awaits a human.
    assert run["status"] == "awaiting_human_score"
    fetched = client.get(f"/evals/runs/{run['id']}", headers=evaluator_headers).json()
    assert fetched["status"] == "awaiting_human_score"

    scores = judge_scores(db, run["id"])
    assert len(scores) == 1
    assert scores[0].reviewer_id == JUDGE_REVIEWER_ID
    assert scores[0].pass_fail is True
    assert scores[0].score_json["_weighted_total"] == 11

    # The rubric drove the prompt; spend was recorded against the eval run.
    assert "accuracy" in fake.calls[0]["system"]
    usage = db.scalars(select(LLMUsage).where(LLMUsage.purpose == "judge")).all()
    assert len(usage) == 1
    assert usage[0].eval_run_id == uuid.UUID(run["id"])


def test_human_decision_records_judge_agreement(
    client, db, operator_headers, evaluator_headers
) -> None:
    set_llm_adapter(FakeAdapter(JUDGE_PASSING))
    _wf, stage_run_id = make_workflow_stage(client, operator_headers)
    suite = make_judge_suite(client, evaluator_headers)
    version = make_rubric_version(client, evaluator_headers).json()
    run = make_eval_run(client, evaluator_headers, suite, version, stage_run_id).json()

    score(client, evaluator_headers, run["id"], PASSING)

    result = client.get(f"/evals/runs/{run['id']}/result", headers=evaluator_headers).json()
    metrics = result["decision"]["metrics_json"]
    assert result["decision"]["decision_type"] == "pass"
    assert metrics["reviewer_count"] == 1  # the judge did not count
    assert metrics["judge_pass_fail"] is True
    assert metrics["judge_agrees"] is True
    # Agreement means no drift.
    assert db.scalars(select(DriftSignal)).all() == []
    # The API exposes both scores, judge marked as agent.
    by_type = {s["scored_by_type"]: s for s in result["scores"]}
    assert set(by_type) == {"human", "agent"}


def test_judge_never_counts_toward_min_reviewers(
    client, db, operator_headers, evaluator_headers, reviewer_headers
) -> None:
    set_llm_adapter(FakeAdapter())
    _wf, stage_run_id = make_workflow_stage(client, operator_headers)
    suite = make_judge_suite(client, evaluator_headers, min_reviewers=2)
    version = make_rubric_version(client, evaluator_headers).json()
    run = make_eval_run(client, evaluator_headers, suite, version, stage_run_id).json()
    assert len(judge_scores(db, run["id"])) == 1

    # Judge + one human is NOT two reviewers.
    score(client, evaluator_headers, run["id"], PASSING)
    assert (
        client.get(f"/evals/runs/{run['id']}", headers=evaluator_headers).json()["status"]
        == "awaiting_human_score"
    )

    score(client, reviewer_headers, run["id"], PASSING)
    result = client.get(f"/evals/runs/{run['id']}/result", headers=evaluator_headers).json()
    assert result["run"]["status"] == "completed"
    assert result["decision"]["metrics_json"]["reviewer_count"] == 2


def test_disagreement_emits_drift_and_widens_sampling(
    client, db, operator_headers, evaluator_headers
) -> None:
    set_llm_adapter(FakeAdapter(JUDGE_PASSING))
    # sampling_rate 0: the judge only acts once disagreement widens sampling.
    suite = make_judge_suite(client, evaluator_headers, sampling_rate=0.0)
    version = make_rubric_version(client, evaluator_headers).json()

    _wf1, stage_run_1 = make_workflow_stage(client, operator_headers)
    run1 = make_eval_run(client, evaluator_headers, suite, version, stage_run_1).json()
    assert judge_scores(db, run1["id"]) == []  # not sampled

    # Simulate an earlier sampled judge verdict that the human then overrides.
    db.add(
        ReviewerScore(
            eval_run_id=uuid.UUID(run1["id"]),
            rubric_version_id=uuid.UUID(version["id"]),
            reviewer_id=JUDGE_REVIEWER_ID,
            scored_by_type=ActorType.agent,
            score_json={**PASSING, "_weighted_total": 11},
            pass_fail=True,
            rationale="judge said pass",
            submitted_at=utc_now(),
        )
    )
    db.flush()
    score(client, evaluator_headers, run1["id"], FAILING)

    result = client.get(f"/evals/runs/{run1['id']}/result", headers=evaluator_headers).json()
    assert result["decision"]["decision_type"] == "fail"
    assert result["decision"]["metrics_json"]["judge_agrees"] is False

    signals = client.get("/evals/drift-signals", headers=evaluator_headers).json()
    assert len(signals) == 1
    assert signals[0]["signal_type"] == "judge_human_disagreement"
    assert signals[0]["scope_ref"] == suite["id"]
    assert signals[0]["evidence_json"]["rolling_agreement"] == 0.0

    # Rolling agreement (0.0) is below threshold: sampling is widened to 100%,
    # so the next run gets judged despite sampling_rate=0.
    run2 = make_eval_run(client, evaluator_headers, suite, version, stage_run_1).json()
    assert len(judge_scores(db, run2["id"])) == 1


def test_sampling_zero_without_history_skips_judge(
    client, db, operator_headers, evaluator_headers
) -> None:
    fake = FakeAdapter()
    set_llm_adapter(fake)
    _wf, stage_run_id = make_workflow_stage(client, operator_headers)
    suite = make_judge_suite(client, evaluator_headers, sampling_rate=0.0)
    version = make_rubric_version(client, evaluator_headers).json()

    run = make_eval_run(client, evaluator_headers, suite, version, stage_run_id).json()

    assert judge_scores(db, run["id"]) == []
    assert fake.calls == []


def test_suite_without_judge_config_gets_no_judge(
    client, db, operator_headers, evaluator_headers
) -> None:
    fake = FakeAdapter()
    set_llm_adapter(fake)
    _wf, stage_run_id = make_workflow_stage(client, operator_headers)
    suite = client.post(
        "/evals/suites",
        json={
            "name": "Plain human suite",
            "target_type": "stage_run",
            "config": {"min_reviewers": 1},
            "cases": [{"name": "score it", "prompt_or_instruction": "Score."}],
        },
        headers=evaluator_headers,
    ).json()
    version = make_rubric_version(client, evaluator_headers).json()

    run = make_eval_run(client, evaluator_headers, suite, version, stage_run_id).json()

    assert judge_scores(db, run["id"]) == []
    assert fake.calls == []


def test_malformed_judge_output_is_a_noop(client, db, operator_headers, evaluator_headers) -> None:
    set_llm_adapter(FakeAdapter(text="I think this deserves a solid B+."))
    _wf, stage_run_id = make_workflow_stage(client, operator_headers)
    suite = make_judge_suite(client, evaluator_headers)
    version = make_rubric_version(client, evaluator_headers).json()

    run = make_eval_run(client, evaluator_headers, suite, version, stage_run_id).json()

    # Advisory failure: no score, run untouched, humans proceed normally.
    assert judge_scores(db, run["id"]) == []
    assert run["status"] == "awaiting_human_score"
    score(client, evaluator_headers, run["id"], PASSING)
    result = client.get(f"/evals/runs/{run['id']}/result", headers=evaluator_headers).json()
    assert result["decision"]["decision_type"] == "pass"
    assert "judge_agrees" not in result["decision"]["metrics_json"]


def test_budget_cap_blocks_judge_before_model_call(
    client, db, tenant_id, operator_headers, evaluator_headers
) -> None:
    db.add(
        LLMUsage(
            tenant_id=tenant_id,
            model="claude-haiku-4-5",
            purpose="judge",
            input_tokens=1,
            output_tokens=1,
            cost_usd=50.0,
        )
    )
    db.flush()
    fake = FakeAdapter()
    set_llm_adapter(fake)
    _wf, stage_run_id = make_workflow_stage(client, operator_headers)
    suite = make_judge_suite(client, evaluator_headers)
    version = make_rubric_version(client, evaluator_headers).json()

    run = make_eval_run(client, evaluator_headers, suite, version, stage_run_id).json()

    assert judge_scores(db, run["id"]) == []
    assert fake.calls == []  # fail closed on spend: the model was never called
