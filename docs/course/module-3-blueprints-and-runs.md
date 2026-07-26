# Module 3 — Blueprints, runs, and stage contracts

**Core question:** how do you turn "do good work" into checkable stages?

**Time:** ~90 minutes · **Roles used:** operator

## Objectives

1. Design a staged workflow blueprint with explicit gates and defend each gate's placement.
2. Create the blueprint in Signet, start a run, submit contract-required deliverables, and advance it.
3. Read run and stage state machines well enough to diagnose *why* a run is paused.

## Concepts

### Blueprints vs. runs

A **blueprint** (workflow template) is the reusable definition: ordered stages, each with a contract, an execution mode (human or automated), and gate requirements (review and/or eval). A **run** is one execution of a versioned blueprint. Versioning matters: a run is pinned to the blueprint version it started with, so mid-flight edits can't silently change what "compliant" meant.

### Where gates go

A gate is friction; friction must buy risk reduction. Three placement rules of thumb:

- **Gate before irreversibility.** Review belongs immediately before the output leaves your control (publication, filing, sending), not three stages earlier.
- **Gate at judgment concentration.** The stage where most discretion was exercised (synthesis, recommendation) deserves an eval gate — that is where wrongness is born.
- **Don't gate mechanical stages.** Review of a formatting step teaches reviewers that review is ignorable.

### The state machines

Runs: `running → paused_for_review / paused_for_eval → running → completed` (or `cancelled`, or `failed`). Stages: `pending → running → awaiting_review / completed / failed`. Every pause names its cause. When a run is stuck, the state tells you *which control* is holding it — that is a feature, and lab step 4 makes you use it.

## Lab

Log in as an operator.

1. **Design on paper first (15 min).** Pick a real deliverable from your own work (a client memo, a policy answer, a contract summary). Break it into 3–4 stages. For each stage write: name, the artifact roles it must produce, and gates (review? eval? none?) with one sentence of justification per gate.
2. **Build the blueprint.** Console: Blueprints → New blueprint; enter stages, contracts, and gate flags. Or API:
   `POST /workflow/templates` then `POST /workflow/templates/{id}/versions` with your stage definitions.
3. **Run it.** Start a run, open it under Active Workflows. On the first stage, submit an artifact for each contract-required role (Stage Actions → fill role and content → Submit Deliverable), then Complete Stage & Advance.
4. **Hit your own gate.** Advance until the run pauses. Confirm: run status `paused_for_review`, stage `awaiting_review`, and a task now sits in the Approval Queue (you'll decide it in module 4 — leave it).
5. **Try to cheat.** Attempt to complete a gated stage without the required artifact role, or to advance a paused run. Record the exact error. This is the module's real lesson: the happy path is optional to learn, the refusals are not.
6. **Deliverable:** your running, paused workflow + your stage/gate design sheet from step 1.

## Knowledge check

1. A colleague proposes review gates on *every* stage "to be safe." Argue against it using module 1's oversight-theater concept.
2. Why must a run pin the blueprint *version* rather than following the latest edit?
3. Your run shows `paused_for_eval` but you expected `paused_for_review`. What exactly did you misconfigure, and on which object?

## Reading

- `docs/enterprise-scenario.md` — four production-shaped blueprint designs to compare against yours.
- `docs/test-catalog.md`, workflow section — the platform's own promises about state transitions, in plain language.
