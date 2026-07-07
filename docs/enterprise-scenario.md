# Enterprise test scenario

This platform ships with four seeded **use-case starter packs** you can use to
exercise it under realistic enterprise conditions. Each pack is a complete
governed workflow: an environment (prompt/tool/policy profiles + a domain
schema), a workflow template whose ICM stage contracts carry the right
human-review and eval gates, a domain rubric, and an eval suite.

Seed (or re-seed — it is idempotent) with:

```sh
# inside the api container, or a dev shell with DB access
ICM_SEED_ADMIN_EMAIL=you@example.com python -m app.platform.seed.usecases
```

## The four packs

| Slug | What it governs | Gates | Stresses |
| --- | --- | --- | --- |
| `financial-analyst-report` | Investment/credit memo drafting | compliance review + accuracy/citation eval | citation integrity, disclosure |
| `legal-contract-review` | Clause drafting + redline | lawyer review + risk/completeness eval | human override, risk caps |
| `support-policy-response` | High-volume policy replies | sampling review + tone/accuracy eval | throughput, drift detection |
| `clinical-protocol-drafting` | Study protocol drafting | medical review + safety eval + reversibility check | resilience layer (halt & reconstruct) |

## End-to-end walkthrough (financial analyst report)

This is the canonical acceptance test: it drives one run through every gate and,
in doing so, populates the governance-quality metrics (Harness 1). Do it in the
console, or via the API (`$T` is a bearer token from `POST /auth/login`).

1. **Start a run** from the template's published version
   (`POST /workflow/runs`, `workflow_template_version_id`). The run begins at
   stage `scope`.
2. **Scope** — submit a `scope_brief` artifact, then complete the stage.
3. **Draft memo** — submit `draft_memo` + `figure_log` artifacts, complete.
4. **Compliance review** (gate) — the run **pauses for review**. A `reviewer`
   opens the task in **Reviews** and records approve / edit / reject. This is
   where **override rate** and **review outcomes** come from.
5. **Quality eval** (gate) — the run **pauses for eval**. An `evaluator` starts
   an eval run against the *Memo quality gate* suite + *Memo accuracy &
   citations* rubric and submits scores from `min_reviewers` reviewers. A split
   verdict produces a **disagreement / needs-adjudication** signal; the weighted
   total vs. the pass threshold decides the gate.
6. **Finalize** — with both gates satisfied, complete the run.
7. **Promote** (optional) — request an environment promotion; the evidence
   evaluator gathers eval pass rates + open disagreements + drift and either
   blocks (missing evidence, fail-closed) or moves to approval-pending. This
   feeds **promotion evidence completeness**.
8. **Resilience** (optional) — capture a coverage snapshot; a rubric-thresholded
   human-capacity run scores whether people can still verify/override/reconstruct
   the work, and drift signals surface on the dashboard.

Run the same shape for the other three packs to cover legal override, support
sampling + drift, and clinical reversibility.

## What "good" looks like

After the walkthrough, `python -m bench.governance_metrics` should show a
non-zero decided count, a sensible override rate, an eval pass rate, and — if you
promoted — an evidence-completeness figure. See [benchmarking.md](benchmarking.md)
for how to measure and interpret the results.
