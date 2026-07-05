# icm-platform

ICM-native governed agent workflow, evals, environment, and human capacity resilience platform.
A production-oriented **modular monolith** built with FastAPI, PostgreSQL, Redis, and Celery,
designed for single-VPS deployment first, with clean extension points for a private GPU
compute node later.

The workflow substrate implements the **Interpretable Context Methodology (ICM)**: staged
execution through explicit stage contracts, layered context loading, and human-readable,
versioned intermediate artifacts — not opaque orchestration logic. Governance, evals,
environment versioning, and human-capacity measurement build on that substrate.

## Authoritative documents

- [docs/master-backend-platform-spec.md](docs/master-backend-platform-spec.md) — the master
  backend platform spec. Authoritative for scope, entities, services, APIs, and state models.
- [docs/icm-paper.md](docs/icm-paper.md) — the ICM reference: five-layer context model
  (identity, routing, stage contract, references, working artifacts), handoffs, signoff gates.
- [docs/examples/icm-workflow/](docs/examples/icm-workflow/) — a worked ICM workspace on disk;
  the shape the Workflow module's workspace materialization reproduces per run.

Where the two conflict, the master backend platform spec wins.

## Layer model and build status

| Layer | Module | Responsibility | Status |
|---|---|---|---|
| Shared core | `app/platform` | Auth, RBAC, DB, storage, events, observability | ✅ built |
| Workflow | `app/workflow` | Staged execution, context assembly, artifact handoff | ✅ built |
| Governance | `app/governance` | Policy checks, approvals, review, audit, escalation | ✅ built |
| Evals | `app/evals` | Scoring, baselines, regression packs, calibration, drift | ⏳ planned |
| Environment | `app/environment` | Reusable templates, profiles, references, promotion | ⏳ planned |
| Human Capacity Resilience | `app/resilience` | Human capability measurement, fallback readiness, reversibility | ⏳ planned |
| Async jobs | `app/tasks` | Celery task entry points | ✅ wired (broker + ping) |

## How the workflow substrate works

1. **Author a template**: `POST /workflow/templates`, then `POST /workflow/templates/{id}/versions`
   with ordered stages. Each stage carries a markdown **contract** (`## Identity`, `## Inputs`,
   `## Procedure`, `## Outputs`, `## Definition of done`, `## Failure modes`). Contracts are
   parsed at version creation and rejected if malformed — contracts are law, fail closed.
2. **Start a run**: `POST /workflow/runs`. The run materializes an ICM workspace in object
   storage (layer-0 identity document, layer-1 stage router, per-stage contract copies) and
   starts stage 1. Every stage run gets a **context manifest** recording exactly which layer
   0–4 inputs it sees (`GET /workflow/stage-runs/{id}/context-manifest`).
3. **Execute a stage**: submit versioned artifacts (`POST /workflow/stage-runs/{id}/artifacts`),
   then complete (`POST /workflow/stage-runs/{id}/complete`). Completion is blocked until every
   contracted output role has an artifact.
4. **Handoff**: the completed stage's latest artifact per role becomes the next stage's
   layer-4 inputs, with provenance. Stages marked `review_required` (or matched by an
   active `require_review` policy rule) pause the run and open a governance review task.
5. **Review**: reviewers work the queue (`GET /governance/review-tasks?status=open`) and
   **approve**, **edit** (the edited artifact becomes the handoff version), **reject**
   (fails the run), or **escalate** (opens an admin task). Every control decision is
   recorded as a `ReviewDecision` plus an audit event
   (`GET /governance/audit-events`, auditor/admin only).

## Architecture conventions

- Routes stay thin (`api/`); business logic in `services/`; persistence in `repositories/`;
  Pydantic schemas in `schemas/`; SQLAlchemy 2.0 models in `models/`; Alembic migrations
  in `migrations/`.
- Every tenant-owned table carries `tenant_id`/`project_id`; repository queries are
  tenant-scoped, and a cross-tenant miss is a plain 404.
- UUIDv7 primary keys, UTC timestamps, correlation IDs on every request (`X-Correlation-ID`).
- Domain errors (`app/platform/errors.py`) translate to 404 / 409 / 422 at the API layer;
  consequential ambiguity fails closed.
- Auth: JWT bearer tokens (`POST /auth/login`), roles per spec §20, `require_roles(...)`
  guards on mutations. First admin via `python -m app.platform.auth.bootstrap`.

## Development

Requires [uv](https://docs.astral.sh/uv/); it provisions the pinned Python automatically.

```sh
uv sync                                 # create venv and install dependencies
uv run pytest                           # run the test suite
uv run ruff check . && uv run ruff format --check .   # lint / format
uv run alembic upgrade head             # apply migrations (needs ICM_DATABASE_URL)
uv run uvicorn app.main:app --reload    # run the API locally (docs at /docs)
```

Configuration is environment-variable driven with the `ICM_` prefix (see
`app/platform/settings/config.py`). Local defaults work without a `.env` file; production
values are injected via the deployment environment and never committed.

## Deployment

Single Hostinger VPS via Docker Compose: Caddy (edge, the only host-exposed service) →
FastAPI api → Postgres, Redis, Celery worker, with persistent volumes for the database and
artifact storage. See [docs/deployment.md](docs/deployment.md) for the full runbook:
provisioning, hardening, first deploy, migrations, admin bootstrap, updates, and backups.
Kubernetes is a deliberate non-goal.
