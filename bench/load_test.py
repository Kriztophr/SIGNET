"""Harness 2 — system performance / load.

Drives a mix of read endpoints concurrently for a fixed duration and reports
throughput, error rate, and latency percentiles (overall and per endpoint).
Read-only: it never mutates state, so it is safe to point at production.

    ICM_BENCH_BASE_URL=https://your-host ICM_BENCH_EMAIL=... ICM_BENCH_PASSWORD=... \
    ICM_BENCH_CONCURRENCY=16 ICM_BENCH_DURATION=15 \
        python -m bench.load_test [--json]

Interpretation: run it from the VPS (base_url=http://localhost:8000) for the
server's own latency, or from a client to include the network + edge path.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from bench.client import ApiClient, percentile

# (path, relative weight) — read-only endpoints across the five layers.
ENDPOINTS: list[tuple[str, int]] = [
    ("/health", 3),
    ("/workflow/templates", 2),
    ("/workflow/runs?limit=25", 2),
    ("/evals/runs?limit=25", 2),
    ("/evals/rubrics", 1),
    ("/governance/review-tasks?status=open", 2),
    ("/environment/promotions", 1),
    ("/resilience/coverage-snapshots", 1),
]


def _weighted_paths() -> list[str]:
    paths: list[str] = []
    for path, weight in ENDPOINTS:
        paths.extend([path] * weight)
    return paths


def run_load(client: ApiClient, concurrency: int, duration_s: float) -> dict:
    paths = _weighted_paths()
    deadline = time.perf_counter() + duration_s
    latencies: list[float] = []
    per_endpoint: dict[str, list[float]] = defaultdict(list)
    errors = 0
    counter = {"i": 0}

    def worker() -> None:
        nonlocal errors
        while time.perf_counter() < deadline:
            idx = counter["i"] % len(paths)
            counter["i"] += 1
            path = paths[idx]
            resp = client.get(path, timeout=30.0)
            latencies.append(resp.elapsed_ms)
            per_endpoint[path.split("?")[0]].append(resp.elapsed_ms)
            if resp.status >= 400:
                errors += 1

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for _ in range(concurrency):
            pool.submit(worker)
    wall = time.perf_counter() - start

    total = len(latencies)
    return {
        "concurrency": concurrency,
        "duration_s": round(wall, 2),
        "requests": total,
        "throughput_rps": round(total / wall, 1) if wall else 0,
        "error_rate": round(errors / total, 4) if total else None,
        "latency_ms": {
            "p50": round(percentile(latencies, 50), 1),
            "p95": round(percentile(latencies, 95), 1),
            "p99": round(percentile(latencies, 99), 1),
            "max": round(max(latencies), 1) if latencies else 0,
        },
        "per_endpoint_p95_ms": {
            path: round(percentile(vals, 95), 1) for path, vals in sorted(per_endpoint.items())
        },
    }


def render(r: dict) -> str:
    lat = r["latency_ms"]
    lines = [
        "ICM load test",
        "=" * 42,
        f"concurrency={r['concurrency']}  duration={r['duration_s']}s  requests={r['requests']}",
        f"throughput={r['throughput_rps']} req/s   error_rate={r['error_rate']}",
        f"latency ms  p50={lat['p50']}  p95={lat['p95']}  p99={lat['p99']}  max={lat['max']}",
        "per-endpoint p95 (ms):",
    ]
    lines += [f"  {p:<42} {ms}" for p, ms in r["per_endpoint_p95_ms"].items()]
    return "\n".join(lines)


def main() -> int:
    concurrency = int(os.environ.get("ICM_BENCH_CONCURRENCY", "16"))
    duration = float(os.environ.get("ICM_BENCH_DURATION", "15"))
    client = ApiClient().login()
    result = run_load(client, concurrency, duration)
    if "--json" in sys.argv:
        print(json.dumps(result, indent=2))
    else:
        print(render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
