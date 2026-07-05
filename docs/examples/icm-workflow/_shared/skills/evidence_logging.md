# Skill — Evidence logging

## When to load
Stage 2, whenever writing to `evidence_log.md`.

## Row hygiene
- One passage per row. Never merge multiple passages even if they come from the same source.
- Quote verbatim when the passage is ≤ 40 words; paraphrase for longer passages, and label the row `PARAPHRASE` in Notes.
- The **Claim it supports** column must be a single declarative sentence — the atomic unit later reused in `claims_map.md`.
- Location: for web sources, include the URL. For PDFs, include page number. For videos, include timestamp.

## Naming conventions
- Row IDs: `E-001`, `E-002`, …, monotonically increasing.
- Source IDs: `S001`, `S002`, …. Assigned in `source_bibliography.md` and referenced from the log.

## Common mistakes to avoid
- **Double-counting.** Two rows from the same source do not count as two independent sources for the same claim.
- **Interpretive drift.** The paraphrase changes the strength or scope of the original ("some" → "most", "may" → "will").
- **Silent gaps.** If a research question has no supporting rows at the end of the stage, it must appear in `handoff.md` as `THIN`.
