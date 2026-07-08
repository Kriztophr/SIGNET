"""Harness 1 — governance-quality & process metrics.

Answers "is the governance actually working?" by pulling the audit-relevant
records from the API and computing:

* review outcomes & **override rate** (edited+rejected / decided)
* **eval pass rate** and adjudication/disagreement rate
* **drift** signal volume and mean strength
* **promotion evidence completeness** (blocked = missing evidence, fail-closed)

Zeros are expected on a fresh platform — the metrics light up as work flows
through (e.g. after running the scenario in docs/benchmarking.md). Emits a text
report and, with --json, a machine-readable snapshot.

    ICM_BENCH_BASE_URL=https://your-host ICM_BENCH_EMAIL=... ICM_BENCH_PASSWORD=... \
        python -m bench.governance_metrics [--json]
"""

from __future__ import annotations

import json
import sys
from collections import Counter

from bench.client import ApiClient


def _rows(client: ApiClient, path: str) -> list[dict]:
    resp = client.get(path)
    if resp.status != 200:
        return []
    data = resp.json()
    return data if isinstance(data, list) else []


def collect(client: ApiClient) -> dict:
    # Reviews — try unfiltered, fall back to the known statuses.
    reviews = _rows(client, "/governance/review-tasks")
    if not reviews:
        for status in ("open", "approved", "edited", "rejected", "escalated"):
            reviews += _rows(client, f"/governance/review-tasks?status={status}")
    review_status = Counter(r.get("status", "unknown") for r in reviews)
    decided = sum(review_status[s] for s in ("approved", "edited", "rejected", "escalated"))
    overrides = review_status["edited"] + review_status["rejected"]

    # Evals — pull recent runs and their decisions.
    eval_runs = _rows(client, "/evals/runs?limit=500")
    eval_status = Counter(r.get("status", "unknown") for r in eval_runs)
    passes = fails = adjudications = disagreements = 0
    judge_scored = judge_agreed = 0
    for run in eval_runs:
        result = client.get(f"/evals/runs/{run['id']}/result")
        if result.status != 200:
            continue
        payload = result.json() or {}
        decision = payload.get("decision") or {}
        dtype = decision.get("decision_type")
        if dtype in ("pass", "approved", "adequate"):
            passes += 1
        elif dtype in ("fail", "rejected", "shortfall"):
            fails += 1
        if dtype == "needs_adjudication":
            adjudications += 1
        scores = payload.get("scores") or []
        # Human-vs-human split only; the advisory judge doesn't vote.
        verdicts = {s.get("pass_fail") for s in scores if s.get("scored_by_type") != "agent"}
        if len(verdicts) > 1:
            disagreements += 1
        # Judge-vs-human agreement (recorded on the decision at completion).
        metrics = decision.get("metrics_json") or {}
        if "judge_agrees" in metrics:
            judge_scored += 1
            judge_agreed += bool(metrics["judge_agrees"])

    drift = _rows(client, "/evals/drift-signals")
    drift_strength = [d.get("signal_strength", 0.0) for d in drift]

    promotions = _rows(client, "/environment/promotions")
    promo_status = Counter(p.get("status", "unknown") for p in promotions)

    def rate(num: int, den: int) -> float | None:
        return round(num / den, 3) if den else None

    decided_evals = passes + fails
    return {
        "reviews": {
            "total": len(reviews),
            "by_status": dict(review_status),
            "decided": decided,
            "override_rate": rate(overrides, decided),
        },
        "evals": {
            "total": len(eval_runs),
            "by_status": dict(eval_status),
            "decided": decided_evals,
            "pass_rate": rate(passes, decided_evals),
            "adjudication_rate": rate(adjudications, len(eval_runs)),
            "reviewer_disagreement_rate": rate(disagreements, len(eval_runs)),
            "judge_scored": judge_scored,
            "judge_agreement_rate": rate(judge_agreed, judge_scored),
        },
        "drift": {
            "signals": len(drift),
            "mean_strength": round(sum(drift_strength) / len(drift_strength), 3) if drift_strength else None,
        },
        "promotions": {
            "total": len(promotions),
            "by_status": dict(promo_status),
            "blocked_missing_evidence": promo_status["blocked"],
            "evidence_complete_rate": rate(
                len(promotions) - promo_status["blocked"], len(promotions)
            ),
        },
    }


def render(snapshot: dict) -> str:
    r, e, d, p = snapshot["reviews"], snapshot["evals"], snapshot["drift"], snapshot["promotions"]
    lines = [
        "ICM governance-quality metrics",
        "=" * 42,
        f"Reviews          total={r['total']:<4} decided={r['decided']:<4} "
        f"override_rate={r['override_rate']}",
        f"                 by_status={r['by_status']}",
        f"Evals            total={e['total']:<4} decided={e['decided']:<4} "
        f"pass_rate={e['pass_rate']}",
        f"                 adjudication_rate={e['adjudication_rate']} "
        f"disagreement_rate={e['reviewer_disagreement_rate']}",
        f"                 judge_scored={e['judge_scored']} "
        f"judge_agreement_rate={e['judge_agreement_rate']}",
        f"Drift            signals={d['signals']:<4} mean_strength={d['mean_strength']}",
        f"Promotions       total={p['total']:<4} blocked={p['blocked_missing_evidence']:<4} "
        f"evidence_complete_rate={p['evidence_complete_rate']}",
    ]
    return "\n".join(lines)


def main() -> int:
    client = ApiClient().login()
    snapshot = collect(client)
    if "--json" in sys.argv:
        print(json.dumps(snapshot, indent=2))
    else:
        print(render(snapshot))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
