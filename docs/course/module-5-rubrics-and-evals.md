# Module 5 — Quality checks: rubrics and evals

**Core question:** how do you score work so two strangers agree — and what happens when they don't?

**Time:** ~90 minutes · **Roles used:** evaluator ×2 (two people, or two accounts)

## Objectives

1. Write a rubric whose criteria are scoreable without knowing who wrote them.
2. Run an eval with multiple reviewers and watch a decision fire at quorum.
3. Explain what a disagreement record is for, and why ties mean adjudication rather than averaging.

## Concepts

### Rubrics are versioned contracts for judgment

A Signet rubric is a set of weighted criteria with score ranges and a pass threshold, validated fail-closed (a rubric that doesn't add up refuses to save). Rubrics are **versioned**: an eval permanently references the rubric version it used, so "passed" always has a dated, inspectable meaning. When you later meet judge calibration (module 7), versioning becomes load-bearing: a judge is calibrated *per rubric version*, because changing the measuring stick invalidates the measurements.

The craft is writing criteria that are **decidable**: "every numeric claim traces to a cited source (0–3)" is decidable; "analysis is high quality (0–10)" is a mood. Weights encode what actually matters — a perfect-prose memo with an unsupported recommendation should be *able* to fail.

### Quorum, decisions, and honest ties

An eval run collects scores from reviewers until `min_reviewers` is reached; then a decision fires by majority on pass/fail. Two outcomes deserve attention:

- **Any split** (even one dissenter among passers) writes a **DisagreementRecord**. Disagreement is not noise to average away — it is data about either the rubric (undecidable criterion) or the work (genuinely contested) or the reviewers (calibration gap). Open disagreements later *block release gates* (module 8).
- **Ties** produce `needs_adjudication`, not a coin flip. The system refuses to manufacture a majority that doesn't exist.

### Eval gates in the workflow

A stage can require an eval the same way it requires review: the run pauses `paused_for_eval` until a decision exists. Decisions also record metrics — including, later, whether the LLM judge agreed with the humans.

## Lab

This lab needs two evaluator identities (pair up, or use two seeded demo accounts).

1. **Write the rubric.** For your module 3 workflow's judgment-heavy stage, define 3–5 weighted criteria with a pass threshold. Apply the decidability test: could a stranger score each criterion from the artifact alone? Create it (`POST /evals/rubrics` + a version) with `min_reviewers: 2`.
2. **Trigger the eval.** Run your workflow to the eval gate, or start an eval run against an existing stage (Quality Checks → New quality check, targeting the stage run).
3. **Score independently.** Both evaluators score *without conferring*. Aim for honesty, not agreement.
4. **Engineer a split.** On a second eval run, deliberately score to a 1–1 split (one pass, one fail — you're testing plumbing, not lying about quality; note it in the score rationale). Confirm: decision `needs_adjudication`, and a DisagreementRecord exists.
5. **Read your decision.** `GET /evals/runs/{id}` — find the decision type, per-reviewer weighted totals, and (if a judge is configured) the judge's advisory score marked agent-authored.
6. **Deliverable:** your rubric with a one-line decidability defense per criterion, plus the split decision's disagreement record.

## Knowledge check

1. Why record a disagreement even when the majority is clear (2 pass, 1 fail → passed)?
2. A teammate proposes resolving 1–1 ties by averaging the two weighted scores. What does Signet do instead, and why is averaging a governance smell?
3. Why must the eval store the rubric *version* it used? Give the forensic scenario where this matters.

## Reading

- `docs/master-backend-platform-spec.md` §13 (evals) — decision and disagreement semantics.
- `docs/test-catalog.md`, evals section — the platform's tested promises about quorum, ties, and splits.
