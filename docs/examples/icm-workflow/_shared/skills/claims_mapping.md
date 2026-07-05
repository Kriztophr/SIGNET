# Skill — Claims mapping

## When to load
Stage 3, alongside `argument_structuring.md`.

## Purpose
`claims_map.md` is the audit trail from prose to evidence. Every claim in the outline must appear as a row here with its evidence lineage.

## Claim ID scheme
`C{section}.{index}` — e.g. `C2.3` is the third claim in section 2.

## Row fields
- Claim text: the atomic assertion, phrased as a single declarative sentence.
- RQ: which research question this claim helps answer.
- Supporting evidence rows: comma-separated `E-###` IDs from `evidence_log.md`.
- Confidence: the **lowest** confidence across supporting rows. If any is `LOW`, the claim is `LOW`.
- Notes: hedges needed at draft time (e.g. "phrase as `may`, not `will`").

## Rules
- A claim with zero supporting rows must be deleted from the outline, or promoted to a `handoff.md` gap for the human to fill.
- A `CONFLICT`-tagged evidence row means the claim needs an explicit "sources disagree" treatment in the draft.
- Do not merge two claims to bulk up support. Each claim must stand on its own evidence.
