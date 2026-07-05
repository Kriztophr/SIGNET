# Stage 4 Contract — Draft

## Objective
Produce `draft_v1.md`: a publication-ready first draft that satisfies the signed outline and cites every factual claim.

## Inputs
1. Global identity + stage identity
2. Signed outline and claims map from Stage 3
3. Bibliography and evidence log from Stage 2
4. `_shared/references/style_guide.md`

## Load skill modules
- `../../_shared/skills/drafting.md`
- `../../_shared/skills/self_review.md`

## Procedure
1. Draft each section in the order given by `outline.md`. Do not reorder.
2. For every factual sentence, append an inline citation drawn from `source_bibliography.md`. Anchor text should be the publisher or a descriptive phrase — never the word "source".
3. After the full draft is written, produce `self_review.md` covering: claims coverage, citation coverage, word count, tone check, hedged sentences.
4. If self-review finds any unresolvable issue, write it in `handoff.md` and mark the draft `DRAFT-BLOCKED`.

## Output schema — `draft_v1.md`
- Title line: `# {final title}`
- Byline / dateline optional
- Hook, sections, conclusion mapped 1:1 to outline
- Sources appendix omitted — inline citations only
- No `[UNVERIFIED]` markers left in the body text unless the outline explicitly authorized one

## Output schema — `self_review.md`
```
## Word count
Target: {N}. Actual: {M}. Delta: {%}.

## Claims coverage
| Claim ID | Present in draft? | Section | Notes |
|----------|-------------------|---------|-------|

## Citation coverage
| Section | # factual sentences | # citations | Missing? |
|---------|---------------------|-------------|----------|

## Tone / style flags
-
```

## Definition of done
- Every claim from `claims_map.md` appears in the draft or is explicitly logged as dropped in `handoff.md`.
- Citation coverage: 100 % of factual sentences.
- Word count within ±10 % of target.
- `self_review.md` has no unaddressed red flags.

## Failure modes to watch
- Padding: introducing new claims to hit word count.
- Citation drift: attaching a source to a sentence it does not actually support.
- Tone drift into marketing register when the target audience is technical.
