# Benchmarking the platform

Three dependency-free harnesses (stdlib only) live under [`bench/`](../bench).
They cover the three questions an enterprise buyer asks: *is the governance
sound, is the system fast enough, and are the outputs actually good?*

```sh
export ICM_BENCH_BASE_URL=https://your-host      # or http://127.0.0.1:8000 on the VPS
export ICM_BENCH_EMAIL=you@example.com
export ICM_BENCH_PASSWORD=...

python -m bench.governance_metrics [--json]   # Harness 1 — governance quality
python -m bench.load_test          [--json]   # Harness 2 — performance / load
python -m bench.rubric_benchmark    [--json]  # Harness 3 — output vs. baseline
```

Run the [enterprise scenario](enterprise-scenario.md) first so Harness 1 has
data to report.

## Harness 1 — governance quality & process metrics

Pulls audit-relevant records from the API and computes:

| Metric | Definition | Why it matters |
| --- | --- | --- |
| override rate | (edited + rejected) / decided reviews | are humans actually changing AI output, or rubber-stamping? |
| eval pass rate | passing / decided eval runs | quality bar the gate enforces |
| disagreement / adjudication rate | split verdicts / eval runs | reviewer reliability & calibration need |
| drift signals + mean strength | count and average of active drift | is the baseline moving under you? |
| promotion evidence completeness | 1 − blocked/total | how often promotions are blocked fail-closed for missing evidence |

Zeros are correct on a fresh platform; the numbers light up as work flows through
the gates. **Read the rates, not just the counts** — a 0% override rate with high
volume means humans aren't really in the loop.

## Harness 2 — performance / load

Drives a weighted mix of read endpoints across all five layers at a fixed
concurrency for a fixed duration; reports throughput, error rate, and latency
percentiles (overall + per endpoint). Read-only, safe against production.

Run it two ways: **on the VPS against `http://127.0.0.1:8000`** for the app's own
latency, and **from a client against the public URL** to include the network +
Traefik/Caddy edge.

### Baseline (single api worker, Hostinger 8 GB VPS, 2026-07-07)

| Where | Concurrency | Throughput | p50 | p95 | p99 | Errors |
| --- | --- | --- | --- | --- | --- | --- |
| in-container `127.0.0.1:8000` | 4 | 270 req/s | 15 ms | 24 ms | 30 ms | 0% |
| in-container `127.0.0.1:8000` | 16 | 198 req/s | 78 ms | 136 ms | 165 ms | 0% |
| public HTTPS (laptop → VPS) | 16 | 18 req/s | 169 ms | 3192 ms | — | 0% |

**Interpretation.** The app is fast server-side (sub-30 ms p99 at C=4). Throughput
does **not** rise from C=4 to C=16 — the single uvicorn worker is the bottleneck,
so the scaling lever is **more workers / api replicas** (and a Redis-backed login
throttle so replicas share state), not more concurrency per worker. The heavy
public-internet tail is network variance + the edge, not the application; it
shrinks with more workers, HTTP keep-alive, and a client closer to the region.

## Harness 3 — agent-output-vs-baseline

Scores candidate outputs (models / prompt strategies) against each other using
the platform's **real** rubric-scoring function
(`app.evals.rubrics.service.validate_and_score`) for every seeded rubric, and
reports a leaderboard plus a **discrimination** check: does the pass threshold
cleanly separate acceptable from unacceptable outputs, and with how much
headroom?

The shipped score vectors are illustrative archetypes (gold / strong /
borderline / weak). To benchmark **real** models, replace `CANDIDATES` with the
per-criterion scores a human or LLM judge assigns to each model's output — the
harness then ranks the models and tells you whether the rubric can tell them
apart.

### Baseline (illustrative archetypes)

All four seeded rubrics cleanly separate pass from fail with 7–9 points of
threshold headroom, e.g. *Memo accuracy & citations* (pass ≥ 28/40): gold 40,
strong 32 → PASS; borderline 24, weak 13 → fail. A rubric that does **not**
separate its archetypes is mis-weighted or has a mis-set threshold — fix it
before trusting it as a gate.

## Robustness notes

- Harnesses 1–2 are read-only and safe against production; Harness 3 is fully
  offline (no API, no DB).
- All three emit `--json` for CI trend-tracking; snapshot the JSON per release to
  watch pass rates, latency, and discrimination move over time.
- For a heavier load profile, raise `ICM_BENCH_CONCURRENCY` / `ICM_BENCH_DURATION`;
  to load-test writes, extend `bench/load_test.py` with run/artifact creation
  against a throwaway tenant (never production).
