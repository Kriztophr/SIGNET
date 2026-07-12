"""Harness 3 — agent-output-vs-baseline via the eval rubrics.

Benchmarks candidate outputs (e.g. different models / prompt strategies) against
each other using the platform's **real** scoring function
(``app.evals.rubrics.service.validate_and_score``) as the judge, for every seeded
use-case rubric. It reports a per-rubric leaderboard and a **discrimination**
check: does the rubric's pass threshold cleanly separate acceptable outputs from
unacceptable ones, and with how much headroom?

The score vectors below are illustrative baselines — the point of the harness is
the framework: replace ``CANDIDATES`` with the per-criterion scores a human or
LLM judge assigns to real model outputs to get a live model-vs-model benchmark.

    python -m bench.rubric_benchmark [--json]
"""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace

from app.evals.rubrics.service import validate_and_score
from app.platform.seed.usecases import SCORE_SCALE, USE_CASES

# Candidate archetypes as a fraction of the score scale, applied to every
# criterion, with the flagship (highest-weight) criterion nudged to expose
# whether the rubric's weighting actually discriminates.
CANDIDATES: dict[str, float] = {
    "gold_reference": 1.0,  # a near-perfect output
    "strong_model": 0.8,  # solid, should pass
    "borderline_model": 0.62,  # right around the line
    "weak_baseline": 0.32,  # should fail, especially on weighted criteria
}


def _score_vector(criteria: list[dict], fraction: float) -> dict[str, float]:
    scale_max = SCORE_SCALE["max"]
    heaviest = max(criteria, key=lambda c: c.get("weight", 1))["key"]
    vector: dict[str, float] = {}
    for c in criteria:
        value = round(scale_max * fraction)
        # Penalise the flagship criterion harder for weak candidates.
        if c["key"] == heaviest and fraction < 0.5:
            value = max(SCORE_SCALE["min"], value - 1)
        vector[c["key"]] = float(value)
    return vector


def benchmark_rubric(name: str, criteria: list[dict], threshold: float) -> dict:
    version = SimpleNamespace(
        criteria_json=criteria,
        score_scale_json=SCORE_SCALE,
        pass_threshold_json={"min_total": threshold},
    )
    max_total = sum(c.get("weight", 1) for c in criteria) * SCORE_SCALE["max"]
    board = []
    for label, fraction in CANDIDATES.items():
        total, passed = validate_and_score(version, _score_vector(criteria, fraction))
        board.append({"system": label, "total": total, "max": max_total, "pass": passed})
    board.sort(key=lambda r: r["total"], reverse=True)

    passing = [r["total"] for r in board if r["pass"]]
    failing = [r["total"] for r in board if not r["pass"]]
    # Clean separation = lowest pass strictly above highest fail; headroom is the gap.
    separated = bool(passing and failing and min(passing) > max(failing))
    headroom = round(min(passing) - max(failing), 2) if passing and failing else None
    return {
        "rubric": name,
        "threshold": threshold,
        "max_total": max_total,
        "leaderboard": board,
        "clean_separation": separated,
        "threshold_headroom": headroom,
    }


def render(results: list[dict]) -> str:
    out = ["ICM rubric / output benchmark", "=" * 42]
    for r in results:
        out.append(f"\n{r['rubric']}  (pass >= {r['threshold']} of {r['max_total']})")
        for row in r["leaderboard"]:
            mark = "PASS" if row["pass"] else "fail"
            out.append(f"  {row['system']:<18} {row['total']:>5.1f}/{row['max']:<4}  [{mark}]")
        out.append(
            f"  -> clean_separation={r['clean_separation']} "
            f"threshold_headroom={r['threshold_headroom']}"
        )
    discriminating = sum(1 for r in results if r["clean_separation"])
    out.append(f"\n{discriminating}/{len(results)} rubrics cleanly separate pass from fail")
    return "\n".join(out)


def main() -> int:
    results = [
        benchmark_rubric(uc.rubric_name, uc.rubric_criteria, uc.rubric_pass_min_total)
        for uc in USE_CASES
    ]
    if "--json" in sys.argv:
        print(json.dumps(results, indent=2))
    else:
        print(render(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
