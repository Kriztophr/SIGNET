# Governing Agentic AI — a hands-on course built on Signet

A practical course on making AI agents safe to use for consequential work — taught on a real, running platform rather than slides. Students finish having built, gated, broken, judged, and audited a governed AI workflow end to end.

## Who this is for

- **Engineers** adding AI agents to products who need more than "add a human in the loop" as a plan.
- **Risk, compliance, and audit professionals** who need to know what good AI evidence looks like from the inside.
- **Team leads and founders** deciding how much autonomy to give AI systems, and how to know when to change the answer.

**Prerequisites:** comfort with a web console and copy-pasting API calls (curl or any HTTP client). Modules 6–8 benefit from basic Python reading ability. No machine-learning background required — the course teaches the few statistics it uses (true/false positive rates, confidence intervals) from scratch.

## What you need

A running Signet instance you are allowed to experiment on:

- **Local:** clone the repo, `docker compose up` (see `docs/deployment.md`), bootstrap an admin.
- **Staging:** any non-production deployment. Seed the six role demo accounts with
  `ICM_SEED_DEMO_USERS=1 ICM_DEMO_USERS_PASSWORD=<your password> python -m app.platform.seed.demo_users`
  so every student can log in as operator, reviewer, evaluator, auditor, environment manager, and resilience manager.
- **Never run labs against a production tenant.** Several labs deliberately create failed runs, blocked releases, and drift signals.

The four built-in scenario packs (`python -m app.platform.seed.usecases`) give every lab realistic material: financial analyst report, legal contract review, support policy response, and clinical protocol drafting.

## The through-line

One idea carries the whole course: **trust is a build artifact.** Every module adds one structural mechanism that produces evidence instead of assurances, and the capstone assembles them into a single auditable delivery.

## Module map

| # | Module | Core question | Lab deliverable |
|---|--------|---------------|-----------------|
| 1 | [Why AI governance fails](module-1-why-governance-fails.md) | Why do policies and "humans in the loop" not work by themselves? | Governance failure analysis of a real incident |
| 2 | [Legible context: the ICM methodology](module-2-icm-methodology.md) | What does an agent actually know when it acts, and can you prove it? | Annotated context manifest |
| 3 | [Blueprints, runs, and stage contracts](module-3-blueprints-and-runs.md) | How do you turn "do good work" into checkable stages? | A running gated workflow you built |
| 4 | [Human gates: the approval queue](module-4-human-gates.md) | What are the four honest answers a reviewer can give? | An edit-override with recorded rationale |
| 5 | [Quality checks: rubrics and evals](module-5-rubrics-and-evals.md) | How do you score work so two strangers agree — and what happens when they don't? | A rubric, a split decision, a disagreement record |
| 6 | [Agents on the inside](module-6-agent-execution.md) | How do you let a model do the work without losing the ability to stop it? | An automated stage + a forced graceful failure |
| 7 | [Judging the judge](module-7-judging-the-judge.md) | When can you trust an LLM to score another LLM? | A calibration run and its verdict on your judge |
| 8 | [Release gates and evidence packs](module-8-release-gates-and-evidence.md) | What does "prove this was governed" look like as a file? | A blocked gate, an approved gate, a verified evidence pack |
| 9 | [Keeping humans capable](module-9-human-capacity-resilience.md) | Is your oversight still real after two years of automation? | A capacity resilience assessment wired into a gate |
| 10 | [Capstone: one governed delivery](module-10-capstone.md) | Can you do all of it, on a domain you choose? | End-to-end run + evidence pack + governance memo |

Each module is 60–90 minutes of guided work: a short concept section in plain language, a hands-on lab on your Signet instance, knowledge checks, and pointers into the platform's own documentation for depth.

## Assessment

- **Labs (60%).** Each module's lab produces a concrete artifact in your Signet tenant (a workflow, a decision, a calibration run, an evidence pack). Labs are graded on whether the artifact exists and whether the student can explain *why the system responded the way it did* — especially when it said no.
- **Capstone (40%).** Module 10, graded with the rubric included in that module. The centerpiece is a 1–2 page governance memo written for a non-technical executive, defended orally if taught live.

There is no exam. The platform's refusal messages are the exam.

## Teaching notes

- The course deliberately makes students hit **fail-closed behavior** before showing them the happy path. A blocked release you have to diagnose teaches more than an approved one.
- Every lab that can be done from the console says so; every lab also gives the API call, because auditors and engineers meet the same system at different doors.
- Where the platform produced a genuinely instructive result in production (the uninformative-judge episode in module 7, the blocked promotion in module 8), the labs reproduce it on purpose.
- Companion reading: the research column at [`docs/research-column.md`](../research-column.md) is the course's ideology in 2,000 words; assign it before module 1.
