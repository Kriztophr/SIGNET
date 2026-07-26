# Module 1 — Why AI governance fails

**Core question:** why do policies and "humans in the loop" not work by themselves?

**Time:** ~60 minutes · **Roles used:** any (read-only exploration)

## Objectives

By the end of this module you can:

1. Name the three standard failure modes of process-based AI governance.
2. Distinguish *aspirational* governance (documents) from *structural* governance (gates).
3. Navigate the Signet console and identify which screen embodies which structural control.

## Concepts

### The three failure modes

**Oversight theater.** A human approval step exists, but nothing forces the human to engage. Approvals cluster at end of day; rejection rates trend to zero; nobody can say afterwards what the reviewer actually looked at. The step is real on the org chart and fake in the data.

**Fail-open defaults.** The policy says "releases require evaluation evidence," but the deploy pipeline has no idea what an evaluation is. When evidence is missing, nothing notices. Skipped checks look identical to passed checks.

**Unfalsifiable records.** When someone finally asks "show me this was reviewed," the answer is reconstructed from chat logs and memory. There is no artifact whose absence would have stopped anything, so the record proves effort, not control.

### The structural alternative

Structural governance means the system physically cannot proceed without the control executing:

- A run **pauses** at a review gate — there is no code path around the reviewer.
- A release with missing evidence is **blocked**, with reasons, by default.
- Every decision writes an **audit event**, and the whole run can be exported as a **hash-chained evidence pack** whose tampering is detectable by anyone.

The rest of this course is those three sentences, in detail.

## Lab

You need any Signet login (a read-only auditor account is ideal).

1. **Tour the console.** Visit each page: Home, Blueprints, Active Workflows, Approval Queue, Quality Checks, Release Gates, Resilience. For each, write one sentence: *what decision does this page exist to force?*
2. **Find the pause.** Open any run under Active Workflows (seed one from a scenario pack if the tenant is empty). Find a stage whose status is `awaiting_review` or a run that is `paused_for_review`. This is oversight theater's opposite: the run is *provably stopped*.
3. **Find the refusal.** Under Release Gates, find (or later in the course, create) a `blocked` promotion and read its blocking reasons. Note that the reasons are specific and machine-generated — nobody wrote them by hand, so nobody can forget to write them.
4. **Deliverable — governance failure analysis (½ page).** Pick a public AI incident you know (a chatbot giving unauthorized refunds, a model-generated legal brief with invented citations, an automated decision reversed on appeal — any real case). Answer: which of the three failure modes was present? Which single Signet mechanism, had it existed in that system, would have changed the outcome, and *at which moment*?

## Knowledge check

1. Why does a low override rate (reviewers changing almost nothing) *not* prove the AI is good?
2. What is the difference between a check that failed and a check that never ran — and why do fail-open systems make them look identical?
3. "Every governance control must produce an artifact whose absence blocks something." Restate this in your own words using one Signet screen as the example.

## Reading

- [`docs/research-column.md`](../research-column.md) — the course's argument in column form.
- `docs/master-backend-platform-spec.md` §17 (promotion gates) and §20 (roles) — skim for vocabulary.
