# Stage 3 Contract — Synthesize

## Objective
Produce a **section-level outline** and a **claims-to-evidence map** that fully covers the scope brief using only the logged evidence.

## Inputs
1. Global identity + stage identity
2. `../../02_stage_1_scope/05_artifacts/scope_brief.md`
3. `../../03_stage_2_research/05_artifacts/evidence_log.md`
4. `../../03_stage_2_research/05_artifacts/source_bibliography.md`
5. `../../03_stage_2_research/05_artifacts/handoff.md`

## Load skill modules
- `../../_shared/skills/argument_structuring.md`
- `../../_shared/skills/claims_mapping.md`

## Procedure
1. Group evidence rows by theme. Discard themes that do not serve a scope-brief research question.
2. Draft an outline: title → hook → 3–6 sections → conclusion → call to action. Each section lists the claims it will make (not the prose).
3. For each claim, populate `claims_map.md` linking claim → RQ → supporting evidence row IDs → confidence.
4. Flag any section that relies exclusively on `LOW` confidence rows.

## Output schema — `outline.md`
```
# {Working title}

## Hook (~75 words)
- Purpose:
- Emotional register:

## Section 1 — {title}
Claims:
- C1.1 …
- C1.2 …

## Section 2 — …
…

## Conclusion / call to action
- Ask:
```

## Output schema — `claims_map.md`
```
| Claim ID | Claim text | RQ | Supporting evidence rows | Confidence | Notes |
|----------|------------|----|--------------------------|-----------|-------|
```

## Definition of done
- Every research question in the scope brief maps to at least one section.
- Every claim in the outline appears in `claims_map.md`.
- No claim has zero supporting evidence rows.
- Word-count budget per section adds to ±10 % of the target length in `scope_brief.md`.

## Failure modes to watch
- Introducing new claims not supported by the evidence log (write them in `handoff.md` as gaps, do not sneak them in).
- Reordering claims so the confidence signal is lost.
- Over-weighting a single source across multiple sections.
