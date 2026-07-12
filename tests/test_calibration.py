"""Judge calibration (spec §13.2/§13.3; roadmap stage 4b).

Golden examples with immutable leakage-safe splits; calibration runs measuring
TPR/TNR (positive class = defect) with Wilson intervals; a frozen test set;
the fail-closed calibration gate on production judging; and the Rogan-Gladen
corrected production fail rate.
"""

import uuid

import pytest
from sqlalchemy import select

from app.evals.calibration.service import (
    CalibrationRunService,
    compute_agreement_metrics,
    rogan_gladen_corrected,
    wilson_interval,
)
from app.evals.services.judge import JudgeEvalService
from app.platform.auth.models import Role
from app.platform.llm.adapter import LLMResult, set_llm_adapter
from app.platform.llm.models import LLMUsage
from app.tasks.calibration_tasks import set_calibration_dispatcher
from app.tasks.judge_tasks import set_judge_dispatcher
from tests.conftest import login_headers
from tests.test_evals import (
    FAILING,
    PASSING,
    make_eval_run,
    make_rubric_version,
    make_suite,
    make_workflow_stage,
    score,
)
from tests.test_judge_evals import JUDGE_FAILING, JUDGE_PASSING, make_judge_suite
from tests.test_workflow import submit


class ContentKeyedAdapter:
    """Judge fails anything containing DEFECT, passes everything else — so
    tests can author examples with known judge verdicts."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def complete(self, *, model, system, user_content, max_tokens) -> LLMResult:
        self.calls.append(user_content)
        text = JUDGE_FAILING if "DEFECT" in user_content else JUDGE_PASSING
        return LLMResult(text=text, model=model, input_tokens=500, output_tokens=100)


@pytest.fixture(autouse=True)
def _seams(db, storage):
    set_judge_dispatcher(lambda eval_run_id: JudgeEvalService(db, storage).score_run(eval_run_id))
    set_calibration_dispatcher(lambda run_id: CalibrationRunService(db, storage).execute(run_id))
    yield
    set_judge_dispatcher(None)
    set_calibration_dispatcher(None)
    set_llm_adapter(None)


def author_example(
    client,
    headers,
    rubric_version,
    *,
    content,
    gold_pass,
    group,
    split=None,
    test_set_version=None,
):
    return client.post(
        "/evals/calibration/examples",
        json={
            "rubric_version_id": rubric_version["id"],
            "content": content,
            "gold_score_json": PASSING if gold_pass else FAILING,
            "gold_pass_fail": gold_pass,
            "gold_rationale": "gold label",
            "group_key": group,
            "split": split,
            "test_set_version": test_set_version,
        },
        headers=headers,
    )


def run_calibration(client, headers, rubric_version, split="test", test_set_version=None):
    return client.post(
        "/evals/calibration/runs",
        json={
            "rubric_version_id": rubric_version["id"],
            "split": split,
            "test_set_version": test_set_version,
        },
        headers=headers,
    )


def test_wilson_and_rogan_gladen_math() -> None:
    lo, hi = wilson_interval(8, 10)
    assert 0.4 < lo < 0.8 < hi <= 1.0
    assert wilson_interval(0, 0) is None
    # Point estimate: (0.3 + 0.9 - 1) / (0.9 + 0.9 - 1) = 0.25
    assert rogan_gladen_corrected(0.3, 0.9, 0.9) == 0.25
    # TPR + TNR ≈ 1: the judge is a coin flip; the estimate is withheld.
    assert rogan_gladen_corrected(0.3, 0.55, 0.5) is None
    # Never leaves [0, 1] even when sampling noise pushes it out.
    assert rogan_gladen_corrected(0.05, 0.9, 0.9) == 0.0

    metrics = compute_agreement_metrics(
        [
            {"gold_pass_fail": False, "judge_pass_fail": False},  # TP
            {"gold_pass_fail": False, "judge_pass_fail": True},  # FN
            {"gold_pass_fail": True, "judge_pass_fail": True},  # TN
            {"gold_pass_fail": True, "judge_pass_fail": None, "error": "boom"},
        ]
    )
    assert metrics["n_scored"] == 3
    assert metrics["n_errors"] == 1
    assert metrics["tpr"] == 0.5
    assert metrics["tnr"] == 1.0
    assert metrics["informedness"] == 0.5
    assert metrics["uninformative"] is False


def test_split_is_immutable_per_group(client, evaluator_headers) -> None:
    version = make_rubric_version(client, evaluator_headers).json()

    first = author_example(
        client, evaluator_headers, version, content="a", gold_pass=True, group="g1", split="test"
    )
    assert first.status_code == 201, first.text
    assert first.json()["split"] == "test"
    assert first.json()["test_set_version"] == 1

    # Same group without an explicit split inherits the group's split.
    second = author_example(
        client, evaluator_headers, version, content="b", gold_pass=False, group="g1"
    )
    assert second.json()["split"] == "test"

    # A conflicting explicit split is a leakage attempt — rejected.
    conflict = author_example(
        client, evaluator_headers, version, content="c", gold_pass=True, group="g1", split="dev"
    )
    assert conflict.status_code == 422
    assert "leakage" in conflict.json()["detail"]

    # A fresh group gets a deterministic hash split when none is given.
    third = author_example(
        client, evaluator_headers, version, content="d", gold_pass=True, group="g2"
    )
    fourth = author_example(
        client, evaluator_headers, version, content="e", gold_pass=True, group="g2"
    )
    assert third.json()["split"] == fourth.json()["split"]


def test_harvest_from_decided_eval_run(client, operator_headers, evaluator_headers) -> None:
    _run, stage_run_id = make_workflow_stage(client, operator_headers)
    submit(client, operator_headers, stage_run_id, "scope_brief", "the brief under eval")
    suite = make_suite(client, evaluator_headers).json()
    version = make_rubric_version(client, evaluator_headers).json()
    eval_run = make_eval_run(client, evaluator_headers, suite, version, stage_run_id).json()

    # Undecided runs have no gold label yet.
    early = client.post(
        "/evals/calibration/examples/harvest",
        json={"eval_run_id": eval_run["id"]},
        headers=evaluator_headers,
    )
    assert early.status_code == 409

    score(client, evaluator_headers, eval_run["id"], FAILING)
    harvested = client.post(
        "/evals/calibration/examples/harvest",
        json={"eval_run_id": eval_run["id"], "split": "test"},
        headers=evaluator_headers,
    )
    assert harvested.status_code == 201, harvested.text
    example = harvested.json()
    assert example["gold_pass_fail"] is False  # the human decision is the label
    assert example["gold_score_json"]["accuracy"] == FAILING["accuracy"]
    assert example["provenance"] == "harvested_eval_run"
    assert example["source_eval_run_id"] == eval_run["id"]
    assert example["content_sha256"]
    # Examples from the same workflow run share the group key (no leakage).
    assert example["group_key"] == _run["id"]

    again = client.post(
        "/evals/calibration/examples/harvest",
        json={"eval_run_id": eval_run["id"]},
        headers=evaluator_headers,
    )
    assert again.status_code == 409


def test_calibration_run_computes_tpr_tnr(client, db, evaluator_headers) -> None:
    set_llm_adapter(ContentKeyedAdapter())
    version = make_rubric_version(client, evaluator_headers).json()
    # 3 gold defects: judge catches 2 (DEFECT marker), misses 1. 2 gold passes:
    # judge passes both. TPR = 2/3, TNR = 1.
    cases = [
        ("DEFECT alpha", False),
        ("DEFECT beta", False),
        ("subtle miss", False),
        ("clean one", True),
        ("clean two", True),
    ]
    for i, (content, gold_pass) in enumerate(cases):
        created = author_example(
            client,
            evaluator_headers,
            version,
            content=content,
            gold_pass=gold_pass,
            group=f"grp-{i}",
            split="test",
        )
        assert created.status_code == 201, created.text

    response = run_calibration(client, evaluator_headers, version)
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["status"] == "completed"
    assert run["example_count"] == 5
    assert run["test_set_version"] == 1

    metrics = run["metrics_json"]
    assert metrics["n_defects"] == 3
    assert metrics["n_passes"] == 2
    assert metrics["tpr"] == round(2 / 3, 4)
    assert metrics["tnr"] == 1.0
    assert metrics["tpr_ci95"][0] < 2 / 3 < metrics["tpr_ci95"][1]
    assert metrics["uninformative"] is False

    usage = db.scalars(select(LLMUsage).where(LLMUsage.purpose == "calibration")).all()
    assert len(usage) == 5


def test_test_set_freezes_once_used(client, evaluator_headers) -> None:
    set_llm_adapter(ContentKeyedAdapter())
    version = make_rubric_version(client, evaluator_headers).json()
    author_example(
        client, evaluator_headers, version, content="x", gold_pass=True, group="a", split="test"
    )
    author_example(
        client,
        evaluator_headers,
        version,
        content="DEFECT y",
        gold_pass=False,
        group="b",
        split="test",
    )
    assert run_calibration(client, evaluator_headers, version).json()["status"] == "completed"

    # v1 is frozen now: additions must open v2.
    frozen = author_example(
        client, evaluator_headers, version, content="z", gold_pass=True, group="c", split="test"
    )
    assert frozen.status_code == 422
    assert "frozen" in frozen.json()["detail"]

    v2 = author_example(
        client,
        evaluator_headers,
        version,
        content="z",
        gold_pass=True,
        group="c",
        split="test",
        test_set_version=2,
    )
    assert v2.status_code == 201, v2.text
    assert v2.json()["test_set_version"] == 2

    # A v2 run covers the cumulative set (v1 + v2 examples).
    run2 = run_calibration(client, evaluator_headers, version, test_set_version=2).json()
    assert run2["example_count"] == 3


def test_run_split_validation(client, evaluator_headers) -> None:
    version = make_rubric_version(client, evaluator_headers).json()
    assert run_calibration(client, evaluator_headers, version, split="train").status_code == 422
    assert run_calibration(client, evaluator_headers, version, split="dev").status_code == 422
    assert run_calibration(client, evaluator_headers, version, split="test").status_code == 422


def test_calibration_gate_blocks_uncalibrated_judge(
    client, db, operator_headers, evaluator_headers
) -> None:
    set_llm_adapter(ContentKeyedAdapter())
    _run, stage_run_id = make_workflow_stage(client, operator_headers)
    suite = make_judge_suite(
        client,
        evaluator_headers,
        sampling_rate=1.0,
        **{"calibration_gate": {"enabled": True, "min_tpr": 0.7, "min_tnr": 0.7}},
    )
    version = make_rubric_version(client, evaluator_headers).json()

    # No test-split calibration exists: the gate keeps the judge silent.
    first = make_eval_run(client, evaluator_headers, suite, version, stage_run_id).json()
    assert first["status"] == "awaiting_human_score"  # humans unaffected
    from tests.test_judge_evals import judge_scores

    assert judge_scores(db, first["id"]) == []

    # Calibrate the judge config above both thresholds (TPR = TNR = 1).
    author_example(
        client,
        evaluator_headers,
        version,
        content="DEFECT gold",
        gold_pass=False,
        group="cal-a",
        split="test",
    )
    author_example(
        client,
        evaluator_headers,
        version,
        content="gold pass",
        gold_pass=True,
        group="cal-b",
        split="test",
    )
    calibration = run_calibration(client, evaluator_headers, version).json()
    assert calibration["metrics_json"]["tpr"] == 1.0
    assert calibration["metrics_json"]["tnr"] == 1.0

    second = make_eval_run(client, evaluator_headers, suite, version, stage_run_id).json()
    assert len(judge_scores(db, second["id"])) == 1


def test_monitoring_status_reports_corrected_fail_rate(
    client, db, operator_headers, evaluator_headers
) -> None:
    set_llm_adapter(ContentKeyedAdapter())
    version = make_rubric_version(client, evaluator_headers).json()
    # Perfect calibration (TPR = TNR = 1) so corrected == observed.
    author_example(
        client,
        evaluator_headers,
        version,
        content="DEFECT gold",
        gold_pass=False,
        group="m-a",
        split="test",
    )
    author_example(
        client,
        evaluator_headers,
        version,
        content="fine",
        gold_pass=True,
        group="m-b",
        split="test",
    )
    assert run_calibration(client, evaluator_headers, version).json()["status"] == "completed"

    run, stage1 = make_workflow_stage(client, operator_headers)
    submit(client, operator_headers, stage1, "scope_brief", "DEFECT-riddled brief")
    submit(client, operator_headers, stage1, "handoff", "handoff")
    # Completing stage 1 starts stage 2, whose run has no artifacts (clean).
    client.post(f"/workflow/stage-runs/{stage1}/complete", headers=operator_headers)
    stages = client.get(f"/workflow/runs/{run['id']}/stages", headers=operator_headers).json()
    assert len(stages) == 2
    suite = make_judge_suite(client, evaluator_headers, sampling_rate=1.0)

    # Judge fails the DEFECT stage, passes the untouched one: p_obs = 0.5.
    make_eval_run(client, evaluator_headers, suite, version, stages[0]["id"])
    make_eval_run(client, evaluator_headers, suite, version, stages[1]["id"])

    status = client.get(
        "/evals/calibration/status",
        params={"suite_id": suite["id"]},
        headers=evaluator_headers,
    ).json()
    assert status["observed"]["n_judge_scored"] == 2
    assert status["observed"]["observed_fail_rate"] == 0.5
    assert status["calibration"]["tpr"] == 1.0
    assert status["corrected"]["corrected_fail_rate"] == 0.5
    assert status["corrected"]["uninformative_judge"] is False


def test_evidence_pack_carries_validated_split_metrics(
    client, db, operator_headers, evaluator_headers
) -> None:
    set_llm_adapter(ContentKeyedAdapter())
    version = make_rubric_version(client, evaluator_headers).json()
    author_example(
        client,
        evaluator_headers,
        version,
        content="DEFECT gold",
        gold_pass=False,
        group="e-a",
        split="test",
    )
    author_example(
        client,
        evaluator_headers,
        version,
        content="fine",
        gold_pass=True,
        group="e-b",
        split="test",
    )
    assert run_calibration(client, evaluator_headers, version).json()["status"] == "completed"

    run, stage_run_id = make_workflow_stage(client, operator_headers)
    suite = make_judge_suite(client, evaluator_headers, sampling_rate=1.0)
    eval_run = make_eval_run(client, evaluator_headers, suite, version, stage_run_id).json()
    score(client, evaluator_headers, eval_run["id"], PASSING)

    me = client.get("/users/me", headers=operator_headers).json()
    auditor = login_headers(
        client, db, Role.auditor, "auditor@example.com", tenant_id=uuid.UUID(me["tenant_id"])
    )
    pack = client.get(f"/governance/evidence-packs/runs/{run['id']}", headers=auditor).json()

    from app.governance.audit.evidence_pack import verify_evidence_pack

    assert verify_evidence_pack(pack)
    calibration = [e["data"] for e in pack["entries"] if e["section"] == "judge_calibration"]
    assert len(calibration) == 1
    methodology = calibration[0]["methodology"]
    assert methodology["status"] == "validated_split"
    assert methodology["validated_split_metrics"]["tpr"] == 1.0
    assert methodology["validated_split_metrics"]["tnr"] == 1.0
    assert calibration[0]["observed_judge_fail_rate"]["n_judge_scored"] == 1


def test_budget_cap_fails_calibration_run_closed(client, db, tenant_id, evaluator_headers) -> None:
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
    adapter = ContentKeyedAdapter()
    set_llm_adapter(adapter)
    version = make_rubric_version(client, evaluator_headers).json()
    author_example(
        client, evaluator_headers, version, content="x", gold_pass=True, group="b-a", split="test"
    )

    run = run_calibration(client, evaluator_headers, version).json()

    assert run["status"] == "failed"
    assert "budget" in run["results_json"]["error"]
    assert adapter.calls == []  # fail closed: the model was never called


def test_calibration_rbac(client, operator_headers, evaluator_headers) -> None:
    version = make_rubric_version(client, evaluator_headers).json()
    denied = author_example(
        client, operator_headers, version, content="x", gold_pass=True, group="r-a"
    )
    assert denied.status_code == 403
    assert run_calibration(client, operator_headers, version).status_code == 403
