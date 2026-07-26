# Test catalog — what the suite proves, in plain language

Each line below is one automated check, described for a human reviewer.
A release is only shipped when every one of them passes. Regenerate after
changing tests: `uv run python tools/generate_test_catalog.py`.

**161 checks across 22 areas.**

## Agent execution (automated stages, kill switch)

*9 checks — `tests/test_agent_execution.py`*

> Agent execution of automated stages (spec §28.7).

- Automated stage executes and advances.
- Agent work still pauses for review gate.
- Agent failure degrades to manual.
- Missing contract outputs degrade to manual.
- Executor output parsing tolerates real open-model sloppiness: blocks labelled with the filename instead of the role, and a missing closing tag.
- When the model emits both an exact role block and a filename-labelled one, the exact role wins.
- Budget cap blocks agent execution.
- The operator kill switch cancels a running run and fails its open stages; a second cancel is rejected.
- An agent task that arrives after its run was cancelled does nothing — the kill switch wins the race.

## Authentication and roles

*12 checks — `tests/test_auth.py`*

- A password verifies against its own bcrypt hash and nothing else.
- Password over 72 bytes rejected.
- Email is normalized lowercase.
- A valid login returns a token that identifies the user on /users/me.
- Login wrong password rejected.
- Login unknown user rejected.
- Inactive user cannot login.
- The identity endpoint is refused without a token.
- The identity endpoint is refused for a malformed token.
- Require roles allows matching role.
- Require roles always allows admin.
- Require roles rejects other roles.

## Judge calibration (golden sets, TPR/TNR, gate)

*11 checks — `tests/test_calibration.py`*

> Judge calibration (spec §13.2/§13.3; roadmap stage 4b).

- The statistics are right: Wilson intervals stay inside [0, 1], the Rogan-Gladen correction matches its formula, and an uninformative judge (TPR + TNR near 1) yields no estimate instead of a misleading one.
- Split is immutable per group.
- Harvest from decided eval run.
- Calibration run computes tpr tnr.
- Test set freezes once used.
- Calibration runs only accept the dev or test split, and only when examples exist there — train is prompt material, never evaluated.
- Calibration gate blocks uncalibrated judge.
- Monitoring status reports corrected fail rate.
- Evidence pack carries validated split metrics.
- Budget cap fails calibration run closed.
- Only evaluators (and admins) may create calibration examples or runs.

## Background worker configuration

*3 checks — `tests/test_celery_app.py`*

- Celery broker comes from settings.
- Celery uses json serialization.
- Ping task is registered and executes.

## Background worker task registration

*1 checks — `tests/test_celery_registration.py`*

> The prod worker loads only app.tasks.celery_app — every Celery task must be registered by importing that single module, or dispatches die on the worker as "Received unregistered task" (found live on 2026-07-12 with evals.judge_score).

- All platform tasks registered via worker entry module.

## Stage contract parsing (fail closed)

*6 checks — `tests/test_contract_parser.py`*

- Parse full contract.
- Missing identity rejected.
- Missing outputs rejected.
- Malformed output entry rejected.
- Duplicate output roles rejected.
- Unknown sections are ignored.

## demo seed

*4 checks — `tests/test_demo_seed.py`*

> Demo-account seeding is opt-in and self-healing: without the env gate it never creates accounts and deactivates any left over from an earlier seed.

- With ICM_SEED_DEMO_USERS unset, no demo accounts are ever created.
- The gate alone is not enough: seeding without a strong password from the environment fails instead of falling back to anything hardcoded.
- With gate + password set, all six role accounts land in the first tenant.
- A production redeploy with the gate off locks out previously seeded demo accounts — the entrypoint run self-heals an environment seeded by mistake.

## Environment (templates, evidence-gated promotion)

*11 checks — `tests/test_environment.py`*

- Template and version creation.
- Duplicate slug rejected.
- Reference bundles and workspace blueprints attach to an environment version and read back intact (without leaking storage URIs).
- Promotion blocked without evidence.
- Promotion approval flow.
- Promotion blocked by failed eval.
- Promotion blocked by regression pack.
- Cannot approve blocked promotion.
- Promotion audit trail.
- Operator cannot create environment.
- Tenant isolation.

## Workflow eval gate

*7 checks — `tests/test_eval_gate.py`*

- Eval required stage pauses.
- Eval pass resumes and hands off.
- Eval fail fails run.
- A split reviewer vote leaves the stage paused for adjudication; a second, agreeing eval run then unblocks it.
- Deadlock guard: an eval completed before the stage reaches the gate counts.
- An operator can manually fail a stage waiting at the eval gate, which fails the whole run.
- Review then eval hands off edited artifact.

## Evals (rubrics, human scoring, decisions, regression packs)

*19 checks — `tests/test_evals.py`*

- Rubric validation rejects bad configs.
- Suite min reviewers validated.
- Creating an eval run against a stage automatically links it to the workflow run and environment version, so evidence stays traceable.
- Run target type must match suite.
- Run unknown target 404.
- Scores with missing rubric criteria or out-of-range values are rejected.
- Single reviewer pass completes run.
- Single reviewer fail.
- Duplicate reviewer rejected.
- Score after completion rejected.
- Split vote needs adjudication.
- Majority still records disagreement.
- Operator cannot score.
- Reviewer can score.
- Operator cannot create suite.
- A regression pack cannot reference an eval suite that does not exist.
- Missing evidence counts as fail and triggers drift.
- Passing pack produces no drift.
- A regression pack with no recorded baseline never raises drift signals — drift is always measured against an explicit baseline.

## Evidence packs (export, hash chain)

*6 checks — `tests/test_evidence_pack.py`*

> Run-scoped evidence pack export (roadmap stage 4; spec §17.3 / §22).

- A fully governed run — review approval plus a judge-assisted, human-decided eval — exports a pack whose hash chain verifies from the served JSON, with lineage, actors, judge provenance, spend, and calibration state all present.
- Hash chain detects tampering.
- A freshly started run with no reviews or evals still exports a valid, verifiable pack with zero counts in those sections.
- Export requires auditor role.
- Export is tenant scoped.
- Export itself is audited.

## Governance (review gates, audit trail)

*10 checks — `tests/test_governance.py`*

- Review task created on pause.
- Approve resumes run.
- Edit hands off edited artifact.
- Reject fails run.
- Escalate opens admin task.
- Decided task cannot be decided again.
- Operator cannot decide reviews.
- Policy rule forces review.
- Audit trail of review lifecycle.
- Audit stream requires auditor or admin.

## Health and API docs exposure

*2 checks — `tests/test_health.py`*

- The health endpoint reports ok with the product name and version.
- Docs exposed outside production.

## LLM judge (advisory scoring, agreement, drift)

*8 checks — `tests/test_judge_evals.py`*

> LLM-judge scoring of eval runs (spec §28.8).

- Judge scores on run creation but never decides.
- Human decision records judge agreement.
- Judge never counts toward min reviewers.
- Disagreement emits drift and widens sampling.
- Sampling zero without history skips judge.
- Suite without judge config gets no judge.
- Malformed judge output is a noop.
- Budget cap blocks judge before model call.

## Console list endpoints

*7 checks — `tests/test_list_endpoints.py`*

> List endpoints added for the operations console (phase 13).

- List templates and runs.
- List stage artifacts.
- List eval runs with status filter.
- List promotions.
- Lists are tenant scoped.
- List template versions.
- List suites and rubrics.

## LLM providers (Anthropic, OpenAI-compatible)

*7 checks — `tests/test_llm_adapters.py`*

> Provider-agnostic LLM adapters (charter 2026-07-08: open-source models behind the same seam — OpenAI-compatible servers like vLLM/Ollama/OpenRouter).

- Openai compatible request and response shape.
- Openai compatible no auth header without key.
- Openai compatible http error raises.
- Openai compatible requires base url.
- Factory selects provider per role.
- Factory rejects unknown provider.
- Cost uses extra price overrides.

## Database migrations

*1 checks — `tests/test_migrations.py`*

- The full database migration chain walks up and back down cleanly on a fresh database.

## Platform core (identity, time, events)

*6 checks — `tests/test_platform_core.py`*

- New uuid is v7 and time ordered.
- Utc now is timezone aware utc.
- Event bus delivers to subscribers.
- Event bus ignores unrelated event types.
- Correlation id echoed when provided.
- Correlation id generated when absent.

## Human capacity resilience (drills, thresholds)

*10 checks — `tests/test_resilience.py`*

- Passing verification/override/reconstruction scores qualify a human for a critical capability.
- Failing scores disqualify.
- Run completes only after required dimensions.
- Rubric must cover required dimensions.
- Fallback drill flow.
- Coverage snapshot shortfall and recovery.
- Resilience threshold gates promotion.
- Unsupported threshold metric rejected.
- Operator cannot manage resilience.
- Tenant isolation.

## Security (authentication sweep, headers, throttling)

*9 checks — `tests/test_security.py`*

- Sweep: no route except /health and /auth/login may answer without a token.
- Expired token rejected.
- Token with wrong signature rejected.
- Token without issuer rejected.
- Login throttled after repeated failures.
- Successful login resets throttle.
- Password policy enforced.
- Security headers present.
- Production settings fail closed.

## Object storage

*3 checks — `tests/test_storage.py`*

- Stored text reads back identically via its storage URI.
- Get missing raises not found.
- Path traversal rejected.

## Workflow (ICM stages, contracts, artifacts)

*9 checks — `tests/test_workflow.py`*

- Template and version creation.
- Duplicate slug rejected.
- Invalid contract rejects version.
- Gapped order index rejected.
- A two-stage run goes from start to completion: contract-checked artifact submission, stage handoff into the next stage's context, done.
- Review required stage pauses run.
- Fail stage fails run.
- Tenant isolation.
- Mutations require operator role.

