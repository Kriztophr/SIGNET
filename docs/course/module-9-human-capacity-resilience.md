# Module 9 — Keeping humans capable

**Core question:** is your oversight still real after two years of automation?

**Time:** ~75 minutes · **Roles used:** resilience manager

## Objectives

1. Explain skill-atrophy risk as a governance problem, not an HR problem.
2. Score a human-capacity run on the three dimensions and interpret the results.
3. Wire resilience thresholds into a release gate and watch missing evidence block a promotion.

## Concepts

### The quiet failure mode

Every earlier module leans on a human backstop: reviewers who catch flaws (4), evaluators who out-judge the judge (5, 7), operators who complete stages when agents die (6). All of that assumes the humans *still can*. Automation erodes exactly the skills it replaces, and the erosion is invisible in day-to-day metrics — approvals keep flowing whether or not the approver could still do the work. By the time an incident reveals the hollowness, the capability took years to lose and will take years to rebuild.

So Signet treats human capability as *evidence with thresholds*, the same governance object as eval pass rates.

### Three dimensions, measured against real work

A **human-capacity resilience run** scores a person, per critical capability, on rubric-thresholded exercises using real platform work:

- **Verification** — given an AI output with planted or natural flaws, do they catch what matters?
- **Override** — can they produce a defensible *alternative*, not just a complaint?
- **Reconstruction** — can they do the task from the same inputs with no AI at all?

The order is the atrophy sequence: reconstruction goes first, override second, verification last — and when verification goes, review is theater with extra steps (module 1, closed loop). Passing scores update the person's capability profile and reviewer competency record — reviewer eligibility can *mean* something beyond a role flag.

### Drills, coverage, reversibility

- **Fallback drills** rehearse operating with AI **off / reduced / delayed**, producing readiness assessments — governance fire drills, run before the fire.
- **Coverage snapshots** compare qualified-human headcount per critical capability against a minimum — the bus-factor for oversight, on a dashboard (the console's Resilience page).
- **Reversibility assessments** record how hard each automation is to unwind. "We could go back if needed" becomes a scored claim instead of a comfort phrase.

### Wired into the same gate

Resilience thresholds (reversibility score, fallback readiness, coverage ratio) are evaluated **fail-closed inside the promotion gate** — scoped to the environment version and tenant-wide. Missing evidence *is* a breach. An environment version can be blocked from release because the *people* aren't demonstrably ready — the platform's most distinctive design decision, and the direct answer to this module's core question.

## Lab

As resilience manager:

1. **Define a critical capability** for your capstone domain (e.g. "financial memo review") with a minimum qualified-subject count.
2. **Run a capacity assessment.** Take a completed run's stage artifacts; have a subject (a course partner) do a verification exercise (flawed artifact — did they find the flaws?), an override exercise (produce the alternative), and a reconstruction exercise (same inputs, no AI). Score each dimension against your rubric thresholds and record the capacity run.
3. **Record one fallback drill** (ai_mode `off` is most instructive: a human does an entire automated stage from the manifest inputs) and its readiness assessment, plus a reversibility assessment for your workflow's automation.
4. **Close the loop with the gate.** Attach a resilience threshold (e.g. `coverage_ratio ≥ 1.0`) to your environment version's scope, then request a promotion with the threshold **unmet or unmeasured** — read the blocking reason. Satisfy it, re-request, and watch the block lift. Missing evidence = breach: you have now seen the platform's deepest principle applied to people.
5. **Deliverable:** the capacity run's three dimension scores with one improvement recommendation per dimension, and both promotions' evidence (blocked-on-resilience, then clean).

## Knowledge check

1. Why is *reconstruction* scored separately from *override* — what distinct governance capacity does each protect?
2. Your coverage snapshot says three people are qualified reviewers for a capability; two leave. Which concrete platform mechanisms notice, and where does it bite?
3. Argue for (or against) this module's premise to a skeptical CFO: why is measuring human capability a *release-gating* concern rather than a training-department concern?

## Reading

- `docs/master-backend-platform-spec.md` — resilience layer sections (capacity dimensions, drills, coverage, policy thresholds).
- `docs/research-column.md` — principle 5, "Measure the humans too."
