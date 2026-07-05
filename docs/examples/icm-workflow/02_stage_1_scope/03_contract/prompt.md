# Stage 1 Contract — Scope

## Objective
Produce a **scope brief** that a downstream researcher could execute without asking clarifying questions.

## Inputs (read in this order)
1. `../../00_identity/agent_identity.md`
2. `../01_identity/stage_identity.md`
3. `../04_references/initial_request.md`
4. `../../_shared/references/style_guide.md`
5. Any additional files in `../04_references/`

## Load skill modules
- `../../_shared/skills/scoping.md`

## Procedure
1. Restate the request in one sentence. If you cannot, halt with `questions_for_human.md`.
2. Identify the **audience**, **deliverable format**, **success criteria**, and **out-of-scope items**.
3. Decompose into **three to seven research questions**, each answerable with public sources or the reviewer's supplied material.
4. Estimate effort per question (S / M / L) and flag any that require primary interviews or paywalled data.
5. Draft `scope_brief.md` using the schema below.
6. Draft `handoff.md` using `../../_shared/templates/handoff.md`.

## Output schema — `scope_brief.md`
```
# Scope brief — {project title}

## One-sentence framing

## Audience and register

## Deliverable
- Format:
- Length target:
- Publication venue:

## Success criteria (measurable)
1.
2.
3.

## Research questions
| # | Question | Effort | Notes / risks |
|---|----------|--------|---------------|

## Explicit out-of-scope
-

## Assumptions
- [ASSUMPTION] …
```

## Definition of done
- Every field in the schema is populated or explicitly marked `N/A`.
- No open clarifying question remains; if any exist, they are in `questions_for_human.md` and the brief is not produced.
- `handoff.md` exists.

## Failure modes to watch
- Silently expanding scope beyond the initial request.
- Research questions phrased so broadly they cannot be answered in one artifact each.
- Success criteria that are not testable ("make it good").
