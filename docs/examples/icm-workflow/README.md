# Interpretable Context Methodology (ICM) — 5-step workflow template

A directory-first template that makes agent context **legible, auditable, and human-gated**. A single agent executes each of the five stages against an explicit contract, produces file artifacts, and halts for human review between stages.

Example project baked into this template: **Technical Research Brief → Published Article** (Scope → Research → Synthesize → Draft → Publish). Swap the example content in `04_references/` and adjust word counts to reuse for any 5-step creative or technical project.

---

## The five-layer context hierarchy

Every stage folder has the same five subdirectories. This is the ICM invariant.

| Layer | Folder | What lives here | Who writes it |
|-------|--------|-----------------|---------------|
| 1. Identity | `01_identity/` | Who the agent is *for this stage* — role, register, non-negotiables | Template author |
| 2. Routing | `02_routing/` | Inputs the stage expects, outputs it must produce, how to advance | Template author |
| 3. Stage contract | `03_contract/` | The prompt the agent executes: objective, procedure, schemas, definition of done | Template author |
| 4. Reference material | `04_references/` | Human-curated read-only inputs (initial request, curated PDFs, venue specs) | Human reviewer |
| 5. Working artifacts | `05_artifacts/` | Everything the agent produces + human `SIGNOFF.md` | Agent + human |

Two global layers sit above the stages:
- `00_identity/agent_identity.md` — the operator's global identity, loaded first at every stage.
- `01_routing/router.md` — the stage map and the state machine.

And one shared layer sits beside them:
- `_shared/skills/` — reusable skill modules the contracts pull in on demand.
- `_shared/references/` — style guide and the single-line `state.md` (active stage pointer).
- `_shared/templates/` — the `handoff.md` and `SIGNOFF.md` templates.

---

## Directory hierarchy

```
icm-workflow/
├── README.md                      ← you are here
├── 00_identity/
│   └── agent_identity.md          ← global identity, loaded at every stage
├── 01_routing/
│   └── router.md                  ← stage map + state machine
├── 02_stage_1_scope/
│   ├── 01_identity/stage_identity.md
│   ├── 02_routing/stage_router.md
│   ├── 03_contract/prompt.md      ← Stage 1 contract
│   ├── 04_references/initial_request.md
│   └── 05_artifacts/              ← agent writes here; human drops SIGNOFF.md here
├── 03_stage_2_research/
│   ├── 01_identity/stage_identity.md
│   ├── 02_routing/stage_router.md
│   ├── 03_contract/prompt.md
│   ├── 04_references/
│   └── 05_artifacts/
├── 04_stage_3_synthesize/
│   ├── 01_identity/stage_identity.md
│   ├── 02_routing/stage_router.md
│   ├── 03_contract/prompt.md
│   ├── 04_references/
│   └── 05_artifacts/
├── 05_stage_4_draft/
│   ├── 01_identity/stage_identity.md
│   ├── 02_routing/stage_router.md
│   ├── 03_contract/prompt.md
│   ├── 04_references/
│   └── 05_artifacts/
├── 06_stage_5_publish/
│   ├── 01_identity/stage_identity.md
│   ├── 02_routing/stage_router.md
│   ├── 03_contract/prompt.md
│   ├── 04_references/publication_target.md
│   └── 05_artifacts/
└── _shared/
    ├── references/
    │   ├── style_guide.md
    │   └── state.md               ← active_stage pointer (single source of truth)
    ├── skills/
    │   ├── scoping.md
    │   ├── source_evaluation.md
    │   ├── evidence_logging.md
    │   ├── argument_structuring.md
    │   ├── claims_mapping.md
    │   ├── drafting.md
    │   ├── self_review.md
    │   ├── publishing.md
    │   └── preflight.md
    └── templates/
        ├── handoff.md
        └── SIGNOFF.template.md
```

---

## The five stages

| # | Stage | Produces | Exits on |
|---|-------|----------|----------|
| 1 | Scope | `scope_brief.md`, `handoff.md` | Human `SIGNOFF.md` |
| 2 | Research | `evidence_log.md`, `source_bibliography.md`, `handoff.md` | Human `SIGNOFF.md` |
| 3 | Synthesize | `outline.md`, `claims_map.md`, `handoff.md` | Human `SIGNOFF.md` |
| 4 | Draft | `draft_v1.md`, `self_review.md`, `handoff.md` | Human `SIGNOFF.md` |
| 5 | Publish | `final.md`, `preflight_checklist.md`, `publish_log.md`, `PUBLISHED.md` | Human `SIGNOFF.md` containing `APPROVE_PUBLISH` |

---

## How a human reviewer works with this template

The pattern is the same at every stage: **read → decide → sign off**.

### 1. Prime the project
- Edit `02_stage_1_scope/04_references/initial_request.md` with your brief.
- Confirm `_shared/references/state.md` shows `active_stage: 1`.

### 2. Run a stage
Hand the agent this prompt:

> Read `00_identity/agent_identity.md`, then `01_routing/router.md`, then `_shared/references/state.md`. Load the active stage folder and execute the contract in its `03_contract/prompt.md`. Halt when the definition of done is met.

The agent will write to that stage's `05_artifacts/` and stop.

### 3. Review the artifacts
Between stages, focus your attention on:

| Stage | What to inspect first | Common issues to look for |
|-------|-----------------------|---------------------------|
| Scope | Success criteria, out-of-scope list, RQ count | Vague criteria, hidden scope creep, too many RQs |
| Research | Confidence distribution in `evidence_log.md`, `THIN` and `CONFLICT` flags in `handoff.md` | Single-source claims, tertiary sources treated as primary, missing paywalled data |
| Synthesize | `claims_map.md` — does every claim have evidence? Word budget per section | Un-sourced claims, over-weighted single sources, section imbalance |
| Draft | `self_review.md` verdict, citation coverage, tone in hook/conclusion | Padding, citation drift, marketing register |
| Publish | `dry_run.md`, `preflight_checklist.md` | Any `FAIL` row, missing alt text, unresolved links |

### 4. Sign off (or send back)
Copy `_shared/templates/SIGNOFF.template.md` into the current stage's `05_artifacts/` as `SIGNOFF.md` and fill it in.

- `APPROVE` → update `state.md` to the next stage number, hand the agent the same run prompt.
- `REVISE` → list the required changes; run the agent again on the same stage.
- `HALT` → stop the workflow and record why.

For Stage 5 only: an `APPROVE` decision must also include the literal token `APPROVE_PUBLISH` on its own line in `SIGNOFF.md`. Without that token, the agent will not call the publishing endpoint.

### 5. After Stage 5
`PUBLISHED.md` is your receipt. It contains the live URL, the publish timestamp, and the SHA-256 of `final.md`. Archive the whole `icm-workflow/` directory alongside the receipt — the entire audit trail (identity, routing, contracts, references, evidence, claims, drafts, publish log) travels with it.

---

## Why the structure looks this way

- **Numbered folders enforce reading order.** An agent that sorts alphabetically encounters identity before routing before contract before references before artifacts. No prompt engineering needed to explain what to read first.
- **Contracts are files, not chat.** You can diff them, version them, and hand the same repo to a different agent tomorrow.
- **Artifacts are files, not chat.** You can grep them, hash them, and cite them in a compliance review months later.
- **State is one line.** `active_stage: N` in `state.md`. If you ever wonder "where are we?", one file answers it.
- **Skills are separable.** Each stage's contract pulls in only the skill modules it needs. Skills can be reused across projects without touching stage contracts.
- **Publish is quarantined.** The only stage that touches the outside world requires a distinguished approval token. Everything upstream is safe to re-run.

## Reusing this template for a different 5-step project

1. Replace the example content in `02_stage_1_scope/04_references/initial_request.md` and `06_stage_5_publish/04_references/publication_target.md`.
2. Rename the stages in `01_routing/router.md` if your project has different stage semantics (e.g. Scope → Model → Train → Evaluate → Deploy). Keep the five-layer subdirectory structure inside each stage.
3. Add or remove skill modules under `_shared/skills/` and update the contracts to load them.
4. Keep the state file, the handoff template, and the SIGNOFF gate — they are the load-bearing pieces of the methodology.
