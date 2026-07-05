# Whole-system consistency review (phase 12)

Reviewed 2026-07-05 against the master backend platform spec, after phases 1–10.
Verification for every claim: full test suite (170 tests), lint/format, fresh
migration chain upgrade, and an app boot smoke test.

## Spec conformance — verified

| Area | Status |
|---|---|
| §6 layer model | All five layers + shared core implemented as modules with the spec's dependency direction (resilience/environment read evals/governance/workflow; never the reverse; cycles at gates broken with call-time imports) |
| §8 repo layout | Matches (routes thin, services/repositories/schemas/models separation throughout) |
| §10 ICM substrate | Contracts parsed fail-closed, workspace materialization mirrors the reference layout, context manifests carry explicit layer 0–4 refs, handoff feeds latest-artifact-per-role |
| §11–13 governance/evals | Review gates (approve/edit/reject/escalate), policy-forced review, rubric-scored eval runs, majority decisions, §18.1 disagreement records on any split |
| §16.1 linkage | Eval runs derive workflow/stage/artifact/environment refs at creation; audit events carry eval_run_id and environment_promotion_id |
| §17 promotion | Evidence-gated with re-check at approval; regression, eval, disagreement, drift, and resilience-threshold evidence all block fail-closed |
| §15 resilience | Capacity dimensions, drills, reversibility, coverage, thresholds with durable decisions; missing evidence is a breach |
| §19 events | All 19 currently-applicable events published (see below) |
| §20 roles | All seven roles enforced; admin-always rule consistent; audit stream restricted |
| §22 observability | tenant/project/correlation/actor on every consequential action; correlation ID on every request |
| §23 security | See docs/security.md; every route swept for auth; tenant isolation tested per module |
| §24 state models | Full enums implemented; unused states inventoried below |
| §25 API rules | REST, explicit schemas, correlation IDs, no storage refs in responses (ReferenceBundleOut fixed in this review) |

## Findings fixed during this review

1. **`environment.template.versioned` was never published** (spec §19). Now emitted
   by `EnvironmentTemplateService.create_version`.
2. **`ReferenceBundleOut` exposed `storage_uri`**, inconsistent with `ArtifactOut`
   and §25's "avoid leaking internal storage paths". Removed from the schema.

## Event coverage (spec §19)

Published: all `workflow.*` (5), `governance.*` (6), `evals.run.started`,
`evals.result.recorded`, `evals.drift.detected`, `environment.template.versioned`,
`environment.promotion.requested/approved`, `resilience.*` (3).
Not yet applicable: `evals.calibration.completed` — calibration is deliberately
deferred to the §28.8 refinement step (user decision, phase 7).

## Deliberate deferrals (documented, not drift)

- **Celery async execution (§26, §28.7):** all flows run on the proven synchronous
  path; `ExecutionMode.automated`, the unused `StageRun.pending/ready` and
  `EvalRun.pending/running` states, the empty `ExecutionSnapshot` writer, and the
  spec §8 `workflow_tasks/eval_tasks/resilience_tasks` modules are the seams for it.
  The broker, worker container, and `platform.ping` task are already deployed.
- **Calibration/adjudication (§13/§28.8):** CalibrationSession, CalibrationExample,
  AdjudicationTask, AgreementMetric, ReviewerCompetency overlap scoring, and
  `POST /evals/calibration-sessions`.
- **Governance long tail:** ControlException and EscalationRule entities (escalation
  works via admin-task creation today); ReviewTask `expired` state has no SLA sweeper
  (needs the scheduler that arrives with Celery).
- **Lifecycle endpoints:** no run-cancel (`WorkflowRun.cancelled`) or promotion
  deprecate/block-by-hand endpoints yet; states exist and are reachable by design
  when those endpoints land.
- **Modeling simplifications:** EvalTarget and Scorecard folded into EvalRun columns
  and EvalDecision metrics; Verification/Override/Reconstruction scores folded into
  one dimension-keyed table. Both noted in the phase commits.
- **API versioning (§25):** routes are unversioned; add a `/v1` prefix at the edge
  proxy before exposing the API to external consumers.
- **Scale-out caveats:** login throttle window is per-process; reviewer-score
  completion relies on in-transaction status checks (row locking planned with
  Celery). Both documented in docs/security.md.

## Verification executed

- `uv run pytest -q` — 170 passed
- `uv run ruff check .` and `uv run ruff format --check .` — clean
- Fresh SQLite database: `alembic upgrade head` walks all six migrations cleanly
- Boot smoke test: `create_app()` constructs with all seven routers registered
- `pip-audit` on frozen production requirements — no known vulnerabilities
