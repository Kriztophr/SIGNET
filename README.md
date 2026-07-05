# icm-platform

ICM-native governed agent workflow, evals, environment, and human capacity resilience platform.
A backend-ready **modular monolith** built with FastAPI, PostgreSQL, Redis, and Celery, designed
for single-VPS deployment first, with clean extension points for a private GPU compute node later.

## Authoritative documents

- [docs/master-backend-platform-spec.md](docs/master-backend-platform-spec.md) — the master backend
  platform spec. Authoritative for all scope, entities, services, APIs, and state models.
- [docs/icm-paper.md](docs/icm-paper.md) — the Interpretable Context Methodology (ICM) reference.
  Authoritative for the workflow substrate: five-layer context model (identity, routing, stage
  contract, references, working artifacts), stage contracts, handoffs, and signoff gates.
- [docs/examples/icm-workflow/](docs/examples/icm-workflow/) — a worked example of an ICM workspace
  on disk; the shape the Workflow module's workspace materialization reproduces.

Where the two conflict, the master backend platform spec wins.

## Layer model

| Layer | Module | Responsibility |
|---|---|---|
| Workflow | `app/workflow` | Staged execution, context assembly, artifact handoff |
| Governance | `app/governance` | Policy checks, approvals, review, audit, escalation |
| Evals | `app/evals` | Scoring, baselines, regression packs, calibration, drift |
| Environment | `app/environment` | Reusable templates, profiles, references, promotion |
| Human Capacity Resilience | `app/resilience` | Human capability measurement, fallback readiness, reversibility |
| Shared core | `app/platform` | Auth, RBAC, DB, storage, events, observability |
| Async jobs | `app/tasks` | Celery task entry points |

Routes stay thin (`api/`), business logic lives in `services/`, persistence in `repositories/`,
request/response models in `schemas/` (Pydantic), persisted models in `models/` (SQLAlchemy 2.0),
migrations via Alembic.

## Development

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+ (uv will provision it).

```sh
uv sync              # create venv and install dependencies
uv run pytest        # run tests
uv run uvicorn app.main:app --reload   # run the API locally
```

Configuration is environment-variable driven with the `ICM_` prefix (see
`app/platform/settings/config.py`). Local defaults work without a `.env` file;
production values are injected via the deployment environment and never committed.

## Deployment

Single Hostinger VPS via Docker Compose (api, postgres, redis, celery worker, reverse proxy).
Deployment files and documentation land in phase 3. Kubernetes is a deliberate non-goal.
