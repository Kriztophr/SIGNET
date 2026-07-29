# Signet

**Signet** is a governed agent workflow, evals, environment, and human capacity resilience
platform — every AI-assisted run leaves a sealed, verifiable record of who approved what,
how it scored, and what it cost. A production-oriented **modular monolith** built with
FastAPI, PostgreSQL, Redis, and Celery, designed for single-VPS deployment first, with
clean extension points for a private GPU compute node later.

Signet's workflow substrate is delivered with the **Interpretable Context Methodology
(ICM)**: staged execution through explicit stage contracts, layered context loading, and
human-readable, versioned intermediate artifacts — not opaque orchestration logic. ICM is
the methodology, Signet is the product; governance, evals, environment versioning, and
human-capacity measurement build on that substrate.

## Authoritative documents

- [docs/master-backend-platform-spec.md](docs/master-backend-platform-spec.md) — the master
  backend platform spec. Authoritative for scope, entities, services, APIs, and state models.
- [docs/icm-paper.md](docs/icm-paper.md) — the ICM reference: five-layer context model
  (identity, routing, stage contract, references, working artifacts), handoffs, signoff gates.
- [docs/examples/icm-workflow/](docs/examples/icm-workflow/) — a worked ICM workspace on disk;
  the shape the Workflow module's workspace materialization reproduces per run.

Where the two conflict, the master backend platform spec wins.

## Learn Signet

- [docs/research-column.md](docs/research-column.md) — *Trust Is a Build Artifact*: the
  design principles behind the platform and the production results that tested them, as a
  readable column.

## Layer model and build status

| Layer | Module | Responsibility | Status |
|---|---|---|---|
| Shared core | `app/platform` | Auth, RBAC, DB, storage, events, observability | ✅ built |
| Workflow | `app/workflow` | Staged execution, context assembly, artifact handoff | ✅ built |
| Governance | `app/governance` | Policy checks, approvals, review, audit, escalation | ✅ built |
| Evals | `app/evals` | Scoring, baselines, regression packs, calibration, drift | ✅ built (calibration deferred) |
| Environment | `app/environment` | Reusable templates, profiles, references, promotion | ✅ built |
| Human Capacity Resilience | `app/resilience` | Human capability measurement, fallback readiness, reversibility | ✅ built |
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
6. **Evaluate**: stages marked `eval_required` pause again after review
   (`awaiting_eval`) until an eval run against the stage produces a passing decision.
   Eval runs score targets (artifacts, stage runs, workflow runs) against **versioned
   rubrics** (`POST /evals/runs`, `POST /evals/reviewer-scores`); multi-reviewer suites
   decide by majority, record any split as a `DisagreementRecord`, and tie votes wait
   for a fresh eval run. Regression packs aggregate the latest decisions per suite —
   missing evidence counts as failure — and a pass rate below the matching baseline
   raises a `DriftSignal` (`GET /evals/drift-signals`).
7. **Package and promote**: business-specific operating context is captured as versioned
   **environment templates** with prompt / tool / policy profiles, reference bundles, and
   workspace blueprints (`POST /environment/templates`, `.../versions`). Promoting a
   version to `approved` (`POST /environment/promotions`) is **evidence-gated** (spec §17):
   the platform gathers the eval runs linked to that environment version, the named
   regression packs' latest pass rates, open review disagreements, and active drift
   signals, then either lands the promotion in `approval_pending` or fails it closed to
   `blocked` with the reasons recorded. Approval re-checks evidence so nothing that
   regressed since the request can slip through — including **resilience thresholds**
   (§17.2) scoped to the version or tenant-wide.
8. **Keep humans capable**: the resilience module measures whether people can still
   verify, override, and reconstruct critical work without AI. Critical capabilities
   (`POST /resilience/capabilities`) are assessed via human-capacity runs scored per
   dimension against capability rubrics; qualification updates capability profiles and
   competency records. **Fallback drills** (`POST /resilience/fallback-drills`, AI off /
   reduced / delayed) produce readiness assessments; **reversibility assessments**
   record whether human-led operation can be restored; **coverage snapshots** flag
   capabilities with too few qualified humans. **Resilience thresholds**
   (`POST /resilience/thresholds`: reversibility_score, fallback_readiness,
   coverage_ratio) are evaluated fail-closed at promotion time — no evidence is a
   breach, not a skip — and every evaluation lands as a durable `ResilienceDecision`.

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

## Operations console (frontend)

A React + Vite + TypeScript SPA in [frontend/](frontend/) covering the human-in-the-loop
surfaces: the **review queue** (approve / edit / reject / escalate with rationale),
**eval scoring** against rubric criteria, the **run inspector** (stages, ICM context
manifests, versioned artifacts, operator actions), the **promotion dashboard** (evidence
and one-click approval), and the **resilience console** (coverage + drift). It talks to
the same API with the same JWTs and role rules; in production Caddy serves it and proxies
API paths on the same origin, so there is no CORS surface.

```sh
cd frontend
npm install
npm run dev        # console on :5173, proxying API calls to uvicorn on :8000
npm run build      # typecheck + production build (CI-enforced)
```

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

## Security

Security is enforced in the platform, not around it: fail-closed production boot
checks, JWT with issuer verification and DB-loaded privileges, login throttling,
a 12-character password floor, tenant-scoped repositories everywhere, host
allowlisting, security headers at both the app and the edge, and a test sweep
asserting every route requires authentication. The full model and its documented
limitations live in [docs/security.md](docs/security.md).

## Deployment

Single Hostinger VPS via Docker Compose: Caddy (edge, the only host-exposed service) →
FastAPI api → Postgres, Redis, Celery worker, with persistent volumes for the database and
artifact storage. See [docs/deployment.md](docs/deployment.md) for the full runbook:
provisioning, hardening, first deploy, migrations, admin bootstrap, updates, and backups.
CI (GitHub Actions) runs lint and the full test suite on every push.
Kubernetes is a deliberate non-goal.

To run the platform on a workstation — Compose, or a SQLite path that needs no
Docker — see [docs/local-development.md](docs/local-development.md).
