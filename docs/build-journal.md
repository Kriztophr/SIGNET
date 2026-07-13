# Signet — Build Journal

A chronological record of the conversation that built **Signet**, the governed
agent workflow, evals, environment, and human-capacity-resilience platform —
from an empty folder to a deployed, governed system with an operations console.
(The platform carried the working title "ICM platform" during the build; ICM —
the Interpretable Context Methodology — is the methodology it is delivered
with, not the product name.)

- **Repository:** `https://github.com/Kriztophr/NS` (local: `~/projects/icm-platform`)
- **Live URL:** `https://srv1182863.hstgr.cloud` (Hostinger VPS `46.202.195.9`)
- **Stack:** FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL · Redis · Celery ·
  React + Vite + TypeScript · Docker Compose · Caddy · Coolify/Traefik
- **Authoritative spec:** `docs/master-backend-platform-spec.md` (+ the ICM paper
  in `docs/icm-paper.md`)

---

## Phase-by-phase

### Phases 1–2 — Scaffold & project setup
Created the repo and the spec-conformant modular-monolith tree
(`app/platform`, `app/workflow`, `app/governance`, `app/evals`,
`app/environment`, `app/resilience`, `app/tasks`). FastAPI app factory with
env-driven settings (`ICM_` prefix), `/health`, docs disabled in production,
uv-managed dependencies. Authoritative docs vendored into `docs/`.

### Phase 3 — VPS deployment stack
Dockerfile (python:3.14-slim + uv, non-root user), `docker-compose.yml`
(api, worker, postgres, redis, caddy — only Caddy binds host ports), Caddyfile
with automatic HTTPS and security headers, Celery app wired to settings, and a
deployment runbook. Established the **future GPU-node extension seam** (a worker
joining the Redis broker over a private tunnel).

### Phase 4 — Platform core
SQLAlchemy declarative base with UUIDv7 / timestamp / tenant-scoping mixins;
session management; structlog; correlation-ID middleware; in-process EventBus;
**JWT auth + RBAC** (seven roles, bcrypt, `require_roles`, bootstrap-admin CLI);
Alembic wired to metadata with the first migration. *(Also fixed a Windows git
credential-helper hang that blocked pushes.)*

### Phase 5 — Workflow module (the ICM substrate)
The core deliverable. All nine spec entities; **contracts-are-law** parsing
(fail closed at version creation); ICM workspace materialization mirroring the
reference layout; **context manifests** with explicit layer 0–4 refs; versioned
artifacts; the **handoff rule** (latest artifact per role → next stage's layer 4);
run/stage state machines; `review_required` pauses runs. End-to-end tested.

### Phase 6 — Governance module
Review-gate lifecycle: a paused stage auto-opens a `ReviewTask`; reviewers
**approve / edit / reject / escalate** (edit's revision becomes the handoff
version); a `PolicyEngine` can force review; every control decision is a durable
`AuditEvent` queryable at `/governance/audit-events` (auditor/admin only).

### Phase 7 — Evals module
Versioned rubrics validated fail-closed; human reviewer scoring with weighted
totals; majority decisions with `DisagreementRecord` on any split and
`needs_adjudication` on ties; the **workflow eval gate** (wiring the previously
dead `eval_required` flag, review-then-eval ordering); regression packs
(missing evidence counts as failure); baselines → `DriftSignal`.
*(Calibration/adjudication deferred to the spec's refinement step by decision.)*

### Phase 8 — Environment module
Versioned environment templates with prompt/tool/policy profiles, reference
bundles, workspace blueprints; the **evidence-gated promotion flow** (spec §17):
promotion gathers eval, regression, disagreement, and drift evidence and either
lands `approval_pending` or fails closed to `blocked`, re-checking at approval.

### Phase 9 — Human Capacity Resilience module
Critical capabilities with qualified-human minimums; human-capacity runs scoring
**verification / override / reconstruction** against rubric thresholds; fallback
drills (AI off/reduced/delayed) → readiness assessments; reversibility
assessments; strategic coverage snapshots; **resilience thresholds** evaluated
fail-closed and wired into the promotion gate (replacing the phase-8 seam).
This completed all five spec layers.

### Phase 10 — Security hardening (enterprise gate)
Fail-closed production boot validation (rejects weak secret / debug / wildcard
hosts); TrustedHost + security-headers middleware; per-account login throttling;
12-char password floor; JWT issuer + required claims; 10 MB edge body cap;
GitHub Actions CI; `pip-audit` clean; `docs/security.md`. **71 security tests**,
including a sweep asserting every route requires authentication.

### Phases 11–12 — Docs refresh & consistency review
Deployment/README refresh; `docs/consistency-review.md` verifying spec
conformance — and **fixing two real inconsistencies** (a missing
`environment.template.versioned` event; a `storage_uri` leak in a response).
Deliberate deferrals inventoried so they read as plan, not drift.

### Phase 13 — Operations console (frontend)
React + Vite + TypeScript SPA covering the human-in-the-loop surfaces: review
queue, eval scoring, run inspector (ICM manifests + artifacts), promotion
dashboard, resilience console. Same-origin (Caddy serves the SPA and proxies the
API — no CORS). Added tenant-scoped list endpoints the UI needs.

### Production deployment
Deployed to the Hostinger VPS. The box runs **Coolify** (its Traefik owns
80/443), so the stack deploys with a `docker-compose.coolify.yml` overlay:
Caddy joins the `coolify` network without host ports and Traefik terminates TLS.
Code ships by **git bundle over SSH** (private repo). The deploy caught three
bugs no local test could: duplicate Postgres constraint names, a Caddy
`try_files`-before-`reverse_proxy` ordering bug, and a worker healthcheck shell
issue — all fixed. Verified live: health, console, real Let's Encrypt cert,
docs hidden, real admin login.

### VPS hardening
`ufw` enabled (deny incoming; rate-limited 22, allow 80/443) **plus**
`DOCKER-USER` iptables rules — because Docker-published ports bypass ufw — to
block internet access to Coolify (8000), Traefik admin (8080), and realtime
(6001–6002). Nightly `pg_dump` cron with 14-day retention, verified. The
Docker/ufw gotcha documented in `docs/security.md`.

### Phase 14 — Console v2 (redesign + self-serve)
Rebuilt the console's visual language (warm dark theme, hero header,
lime/lavender accent stat cards, icon sidebar) and — more importantly — made the
full loop **self-serve from the browser**: a workflow **template builder**
(stages with review/eval toggles and contract markdown), one-click **Start run**,
and a **New eval run** flow with inline suite/rubric quick-create. Added the
list endpoints these need. **186 backend tests.**

---

## Open item — production connectivity incident (2026-07-05 → 06)

After hardening, a burst of SSH/SCP reconnects during the v2 deploy tripped
Hostinger's upstream network protection and **filtered the VPS's public IP**:
the box is healthy internally (the Hostinger browser terminal works) but
unreachable from the internet on all ports, for everyone, persisting many hours.
No hPanel firewall is enabled, and it is not the platform's `ufw` (which allows
443 globally).

**Resolution path:** wait for the block to auto-expire, or open a Hostinger
support ticket ("remove the automatic network block on VPS 46.202.195.9"). Then
relax `ufw limit 22/tcp` → plain `allow` (key-only SSH needs no brute-force
throttle) to avoid re-tripping it.

### Decision: migrate to Coolify
The manual git-bundle-over-SSH pipeline is what caused the incident. The plan is
to move to Coolify's push-to-deploy so no SSH from a dev machine is ever needed.
Groundwork already committed (no server access required):

- **Auto-migrate on API startup** (`deploy/api-entrypoint.sh`) — the fragile
  manual `alembic upgrade` step is gone.
- **`docker-compose.coolify-managed.yml`** — a standalone stack to add as a
  Coolify "Docker Compose" resource.
- Coolify runbook in `docs/deployment.md`.

**Next steps (once the IP is unblocked):**
1. In Coolify, add the GitHub repo as a Docker Compose resource
   (`docker-compose.coolify-managed.yml`), set env (`POSTGRES_PASSWORD`,
   `ICM_SECRET_KEY`, `ICM_ALLOWED_HOSTS` incl. `127.0.0.1`), assign the domain to
   the `caddy` service, deploy, and enable auto-deploy on push.
2. Dump the current database, retire the manual `/opt/icm-platform` stack,
   re-bootstrap the admin, verify end-to-end.

> **Note on scope:** the "Dual-Task Safety Evaluation" module (from the
> *Trust, but Verify* paper) was reviewed and **deliberately kept out of scope**
> per user decision — to be built on a separate platform.

---

## Key reference commands

```sh
# Local development
uv sync && uv run pytest -q
uv run uvicorn app.main:app --reload          # API + Swagger at /docs
cd frontend && npm install && npm run dev     # console at :5173

# Reach Coolify (its port is firewalled off the internet)
ssh -L 8000:localhost:8000 root@46.202.195.9  # then http://localhost:8000

# Retrieve the production admin password (Hostinger browser terminal)
cat /root/.icm-admin-pw
```

*Generated during the build conversation as a portable record. For the
authoritative, always-current state see the repository's `README.md`,
`docs/security.md`, `docs/deployment.md`, and `docs/consistency-review.md`.*
