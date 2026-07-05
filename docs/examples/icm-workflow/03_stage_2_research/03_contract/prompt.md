# Stage 2 Contract — Research

## Objective
For each research question in the signed scope brief, gather sufficient evidence to answer it, and log every piece of evidence in a reviewable table.

## Inputs (read in this order)
1. `../../00_identity/agent_identity.md`
2. `../01_identity/stage_identity.md`
3. `../../02_stage_1_scope/05_artifacts/scope_brief.md`
4. `../../02_stage_1_scope/05_artifacts/handoff.md`
5. `../04_references/` (any human-curated inputs)

## Load skill modules
- `../../_shared/skills/source_evaluation.md`
- `../../_shared/skills/evidence_logging.md`

## Procedure
1. For each research question RQ-1…RQ-N, plan a source list (3–6 sources per question). Prefer primary.
2. Retrieve each source. Extract only passages that directly address the question.
3. Log each passage as a row in `evidence_log.md` with the schema below. One passage per row.
4. Assign each source a stable ID `S001`, `S002`, … in `source_bibliography.md`.
5. If any RQ ends the stage with fewer than two independent supporting sources, mark it `THIN` in `handoff.md`.

## Output schema — `evidence_log.md`
```
| Row | RQ | Source ID | Quoted passage or paraphrase | Location (URL, page) | Claim it supports | Confidence | Notes |
|-----|----|-----------|------------------------------|----------------------|-------------------|-----------|-------|
```

Confidence values: `HIGH` (primary source, direct quote), `MEDIUM` (secondary, or paraphrase of primary), `LOW` (single blog / opinion). Never above `MEDIUM` for a single source.

## Output schema — `source_bibliography.md`
```
| ID | Author / Publisher | Title | Year | URL | Type (primary/secondary/tertiary) | Access date |
|----|--------------------|-------|------|-----|-----------------------------------|-------------|
```

## Definition of done
- Every RQ has at least two `MEDIUM+` sources, or is flagged `THIN`.
- Every row in `evidence_log.md` maps to a source in the bibliography.
- No claim without a citation.
- `handoff.md` lists `THIN` and `CONFLICT` items explicitly.

## Failure modes to watch
- Citing the same source twice as if it were two independent confirmations.
- Paraphrasing so aggressively that the original meaning drifts.
- Silently dropping an RQ because sources were hard to find.
