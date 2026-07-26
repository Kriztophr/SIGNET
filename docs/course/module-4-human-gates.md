# Module 4 — Human gates: the approval queue

**Core question:** what are the four honest answers a reviewer can give?

**Time:** ~60 minutes · **Roles used:** reviewer (plus your module 3 operator run)

## Objectives

1. Use all four review decisions — approve, edit, reject, escalate — and know when each is the honest one.
2. Explain why *edit* is the most informative decision a governance system can record.
3. Trace a review decision into the audit trail.

## Concepts

### Four decisions, not two

Most approval systems offer approve/reject, which quietly forces dishonesty: work that is 90% right gets approved (with a sigh) or rejected (with a fight). Signet's review tasks offer four:

- **Approve** — the work meets its stage contract as-is.
- **Edit** — the work needed correction; the reviewer fixes an artifact *and the correction is recorded as theirs*. The run proceeds with the corrected artifact.
- **Reject** — the work fails its contract; the stage fails.
- **Escalate** — this reviewer should not be the one deciding (conflict, uncertainty, stakes); the task moves up with a written rationale.

### Why edit matters most

Approvals tell you little (see: oversight theater). Rejections are rare and loud. **Edits are the signal:** each one is a concrete, attributable delta between what the AI produced and what a qualified human required. The platform's headline metric — the **override rate** (edited + rejected as a fraction of reviewed) — is powered by reviewers being honest, and honesty requires the edit option to exist. In the reference enterprise scenario the override rate was 0.5: one memo approved, one edited. Both facts are in the record with names attached.

One sharp platform rule you will hit in the lab: **an edit must target an artifact role on the paused stage** — you cannot "fix" an upstream stage's artifact from a later gate. Corrections happen where accountability sits.

### Eligibility and time

Each task carries a required reviewer role and a due time. Role-gating is enforced (an evaluator cannot decide a reviewer's task), and open/decided status is queryable — so "who could decide, who did decide, and how long it sat" are all facts, not reconstructions.

## Lab

Use the run you left paused in module 3. Log in as a **reviewer** (not the operator who did the work — feel why that separation exists).

1. **Work the queue.** Approval Queue → open your task. Read the stage contract and the submitted deliverables side by side. Decide honestly.
2. **Do one edit-override.** If the work is genuinely fine, have a partner (or your operator login) submit a subtly flawed artifact on a second run: a wrong number, an unsupported claim. Then, as reviewer, choose **Edit**, correct the artifact, and write a rationale that names the flaw. API: `POST /governance/review-tasks/{id}/edit`.
3. **Escalate once.** On any open task, escalate with a rationale like "outcome affects my own team's target." Observe where the task goes.
4. **Audit yourself.** As auditor (or admin), `GET /governance/audit-events` and find your decisions. Note each event carries the actor, the run, and the rationale.
5. **Deliverable:** the edited artifact's before/after, your rationale, and the audit events for both your edit and your escalation.

## Knowledge check

1. Your team's override rate has been exactly 0.00 for six weeks. Give two hypotheses — one about the AI, one about the humans — and say which module 9 will test.
2. Why does Signet require the edit to land on the *paused* stage's artifacts rather than allowing upstream fixes?
3. When is *escalate* more honest than *reject*?

## Reading

- `docs/enterprise-scenario.md` — the walkthrough includes a real edit-override, including the mistake of targeting the wrong stage's artifact.
- `docs/benchmarking.md` — how override_rate and disagreement metrics are computed.
