# Router — Global

> Layer 2 of the ICM hierarchy. Tells the agent (and the human) which stage is active and how to move between them.

## Stage map

| # | Stage | Directory | Enters when | Exits when |
|---|-------|-----------|-------------|-----------|
| 1 | Scope | `02_stage_1_scope/` | Project kickoff | `scope_brief.md` reviewed and signed off |
| 2 | Research | `03_stage_2_research/` | Signed scope brief exists | `evidence_log.md` reviewed and signed off |
| 3 | Synthesize | `04_stage_3_synthesize/` | Signed evidence log exists | `outline.md` + `claims_map.md` reviewed and signed off |
| 4 | Draft | `05_stage_4_draft/` | Signed outline exists | `draft_v1.md` reviewed and signed off |
| 5 | Publish | `06_stage_5_publish/` | Signed draft exists | `PUBLISHED.md` receipt written |

## Routing rules for the agent
1. On startup, read `00_identity/agent_identity.md`, then this router, then `_shared/references/state.md`.
2. `state.md` holds a single line: `active_stage: <N>`. Load only the corresponding stage folder.
3. To advance, the human writes `SIGNOFF.md` in the current stage's `05_artifacts/`. The agent then updates `state.md` and stops for the next human trigger.
4. Never auto-advance without a `SIGNOFF.md`.

## Handoff contract between stages
Each stage exits by producing a `handoff.md` that lists:
- Artifacts produced (path + one-line description)
- Open questions carried forward
- Assumptions the next stage will inherit
- `[UNVERIFIED]` claims still pending
