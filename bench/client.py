"""Minimal stdlib HTTP client for the benchmarks (no third-party deps).

Configuration via environment:

    ICM_BENCH_BASE_URL   default http://localhost:8000  (use the public URL to
                         include the edge/Traefik path, or localhost on the VPS)
    ICM_BENCH_EMAIL      admin/operator email
    ICM_BENCH_PASSWORD   its password
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class Response:
    status: int
    body: bytes
    elapsed_ms: float

    def json(self):
        return json.loads(self.body.decode("utf-8")) if self.body else None


class ApiClient:
    def __init__(self, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url or os.environ.get("ICM_BENCH_BASE_URL", "http://localhost:8000")).rstrip("/")
        self.token = token

    def request(self, method: str, path: str, body: dict | None = None, timeout: float = 30.0) -> Response:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = resp.read()
                status = resp.status
        except urllib.error.HTTPError as err:
            payload = err.read()
            status = err.code
        elapsed_ms = (time.perf_counter() - start) * 1000
        return Response(status=status, body=payload, elapsed_ms=elapsed_ms)

    def get(self, path: str, **kw) -> Response:
        return self.request("GET", path, **kw)

    def post(self, path: str, body: dict | None = None, **kw) -> Response:
        return self.request("POST", path, body=body, **kw)

    def login(self, email: str | None = None, password: str | None = None) -> "ApiClient":
        email = email or os.environ.get("ICM_BENCH_EMAIL")
        password = password or os.environ.get("ICM_BENCH_PASSWORD")
        if not email or not password:
            raise SystemExit("set ICM_BENCH_EMAIL and ICM_BENCH_PASSWORD (or pass them in)")
        resp = self.post("/auth/login", {"email": email, "password": password})
        if resp.status != 200:
            raise SystemExit(f"login failed: HTTP {resp.status} {resp.body[:200]!r}")
        self.token = resp.json()["access_token"]
        return self


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * (pct / 100)
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)
