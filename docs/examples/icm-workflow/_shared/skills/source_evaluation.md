# Skill — Source evaluation

## When to load
Stage 2, before adding any row to the evidence log.

## Source tiers
- **Primary.** Regulator publications, standards bodies (ISO, IEEE), peer-reviewed papers, court judgments, first-party corporate filings, official datasets.
- **Secondary.** Reputable trade press citing primary sources, textbooks, analyst reports with methodology disclosed.
- **Tertiary.** Blog posts, opinion pieces, LLM-generated summaries. Use only to point toward primary sources; never as the sole support for a claim.

## Evaluation checklist per source
1. Who authored it? What is their standing?
2. When was it published? Is it still current given the regulatory or technical landscape?
3. Does it cite its own sources?
4. Is there a conflict of interest?
5. Can the passage be verified against a primary source?

## Confidence rubric
- `HIGH` — Primary source, direct quotation, no interpretive drift.
- `MEDIUM` — Primary source paraphrased, or secondary source citing a named primary.
- `LOW` — Secondary or tertiary source without a traceable primary; a single blog post; an LLM summary.

Never mark a claim `HIGH` on the strength of a single source. Two independent primaries required.

## Conflict handling
When two credible sources disagree, log both rows, tag them `CONFLICT`, and describe the disagreement in the `Notes` column. Do not pick a winner unilaterally.
