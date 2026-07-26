# Trust Is a Build Artifact

### What we learned building Signet, a platform where AI agents have to earn their way into production

*Research column · Signet project · July 2026*

---

Most AI governance today is a document. Somewhere in the organization there is a policy PDF that says models will be monitored, humans will stay in the loop, and evidence will be retained. Meanwhile, the actual system ships whatever the last deploy shipped, the "human in the loop" is a person clicking Approve at 4:55 pm, and the evidence — if anyone asks — is a Slack thread.

We spent the last two months building the opposite: a platform where governance is not a document but a **build artifact** — something the system produces, checks, and refuses to proceed without. The platform is called **Signet**. It runs governed AI workflows for consequential work (financial analysis memos, legal contract review, clinical protocol drafting), and it is live in production on a single modest server. This column is about the five design principles that survived contact with reality, and the numbers that came out the other side.

## 1. Fail closed: missing evidence is a "no"

The core mechanic in Signet is the **release gate**. Before a workflow environment version can be promoted for real use, an evidence evaluator gathers everything known about it: evaluation runs and their outcomes, unresolved reviewer disagreements, drift signals, human-capacity thresholds. If any required evidence is missing, the promotion is not "pending" or "flagged for follow-up." It is **blocked**, with the reasons written down.

This sounds obvious until you watch it work on real data. In our first live promotion attempt, the gate blocked an environment version because its history contained one failed evaluation run and two runs still awaiting scores — artifacts of earlier demos we had half-forgotten. The system had not. That is the point: fail-closed gates convert institutional memory from a thing people have to a thing the database has.

The alternative — fail-open, where missing evidence passes silently — is how most review processes actually behave. Nobody decides to skip the check; the check just never fires. Structural governance means the default answer is no.

## 2. Degrade to human, never kill the run

Signet's workflows mix human stages and automated stages. When an agent executes a stage, plenty can go wrong: the model provider is down, the output doesn't parse, the monthly budget cap is hit. Our failure philosophy is one sentence: **any agent failure leaves the stage open for a human, with the error written on it.** The run is never killed, and the failure is never papered over.

This came from a real bill of scars. Our first automated stage execution failed because the open-source model labelled its output block with a filename instead of the required role name and dropped its closing tag. Under a fail-fast design, that run dies and the operator re-runs and prays. Under degrade-to-human, the stage stayed open, the error summary said exactly what happened, and a person could either fix the parsing (we did — the parser now accepts filename aliases and unterminated final blocks) or simply do the stage themselves.

Automation that hands work *back* gracefully is more deployable than automation that insists on finishing. Teams will turn on an agent they know they can catch.

## 3. The judge is a model too

The most seductive shortcut in AI operations is the LLM judge: have a second model score the first model's work, and suddenly quality assurance scales for free. Signet uses LLM judges — but under two hard constraints that we think should be table stakes anywhere.

**First, the judge is advisory.** Judge scores are recorded alongside human scores, flagged as agent-authored, and never count toward the reviewer quorum that decides a gate. Humans decide; the judge's job is to disagree loudly enough to be useful. Every judge–human disagreement is logged, and when rolling agreement drops below a threshold, sampling automatically widens to 100% — more scrutiny, not less, exactly when trust is weakest.

**Second, the judge has to pass its own exam.** A judge configuration (provider, model, rubric version) is treated like any other model release: it is validated against a **golden set** of examples with known human verdicts, split into train/dev/test with the test split frozen forever. We measure the judge's true positive rate (does it fail work humans failed?) and true negative rate (does it pass work humans passed?), with confidence intervals. A calibration gate can require minimum TPR/TNR on the frozen test split before the judge is allowed to score production work at all — fail closed, again.

The live system produced our favorite result here. Our first golden set contained a stub artifact that a scripted human had waved through. The judge — correctly — kept failing it. That gave the judge a measured true negative rate of **zero**, which made it statistically *uninformative* (its answers carry no signal about the truth). Signet's response was not to average over the embarrassment but to **refuse to compute** the corrected production fail-rate estimate that depends on judge quality (a Rogan–Gladen correction, borrowed from diagnostic-test epidemiology: true rate = (observed rate + TNR − 1) / (TPR + TNR − 1)). An uninformative judge produces a divide-by-roughly-zero, and the system says so instead of printing a number. Honest refusal is a feature. Most dashboards would have shown a percentage.

The deeper lesson: the failure was in the *golden set*, not the judge. The judge was right to fail the stub. Calibration infrastructure doesn't just validate judges — it audits your own ground truth.

## 4. Evidence must be self-verifying

When someone asks "prove this run was governed," the answer cannot be a database query only the vendor can run. Signet exports an **evidence pack** per workflow run: one JSON document containing the full lineage — stage contracts (with content hashes), every artifact (hashed, with the human or agent identity that produced it), review decisions, evaluation scores with judge provenance, disagreements, drift signals, model usage and spend, the audit trail, and the judge-calibration metrics that say how much the automated oversight itself can be trusted.

Two properties matter more than the content. **The pack is hash-chained**: each entry's hash incorporates the previous one, and a root hash seals the whole document, so any tampering — reordering, deletion, edits — breaks verification. And **verification is pure**: a short function re-walks the chain from the served JSON alone, no database, no vendor. The pack also maps its sections onto the EU AI Act's technical-documentation and record-keeping articles and the Federal Reserve's SR 11-7 model risk guidance — not as a compliance claim, but as a translation layer so an auditor can find what they need.

Exporting a pack is itself a consequential action, so it lands in the audit trail — recorded *after* the pack is built, so the export event never sits inside its own hash chain. Governance systems must be able to govern themselves without infinite regress.

## 5. Measure the humans too

The quiet failure mode of successful automation is that the humans atrophy. If the agent drafts every memo for two years, the reviewer who could once reconstruct the analysis from scratch becomes a reviewer who can only check formatting. The oversight is still on the org chart; it is no longer in the people.

Signet treats this as a first-class, measurable risk. **Human-capacity resilience runs** score people on three dimensions against real work: can they *verify* an output (catch its flaws), *override* it (produce a defensible alternative), and *reconstruct* it (do the task without the AI at all)? **Fallback drills** rehearse operating with AI off, reduced, or delayed, and produce readiness assessments. Coverage snapshots track whether enough qualified humans exist per critical capability. And — closing the loop — these thresholds feed the same fail-closed release gates as everything else: an environment version can be blocked from promotion because the *humans* aren't ready, not just the model.

We know of no other system that couples "is the model good enough?" and "are the people still capable of catching it?" in one gate. We think both questions are the same question.

## The number that matters

If you keep one metric from a governed AI system, keep the **override rate**: of the outputs humans reviewed, what fraction did they change or reject? In our end-to-end enterprise scenario, the override rate was 0.5 — one memo approved as-is, one edited before approval.

An override rate of zero is not good news; it means review has become theater (or your reviewers can no longer tell — see principle 5). A very high rate means the automation isn't earning its keep. The number is only meaningful because every override is a recorded decision on a gated stage — which is to say, the metric is a *byproduct of structure*. You cannot bolt it on afterwards.

## What makes this work: boring, legible structure

Under all of this sits a deliberately simple methodology (ICM — Interpretable Context Methodology): every agent stage receives its context as five explicit, inspectable layers — identity, routing, stage contract, reference material, and the previous stage's handoff artifacts — recorded in a manifest with content references. Every stage has a written contract for what it must produce. Nothing about this is clever. That is the point: you cannot audit what you cannot enumerate, and five named layers with hashes beats an unbounded prompt every time.

## What we don't know yet

Honesty section. Our golden sets are still small and partly synthetic — the pilot's job is to harvest real human review decisions into them. Judge robustness against provider rate-limits needs retry logic before the judge's silence is always a *decision* rather than an outage. The console still hides some of the machinery (calibration dashboards are API-only today). And the deepest open question is longitudinal: does measuring human capacity actually preserve it, or just document its decline? One design-partner quarter, one override-rate curve, and one set of capacity trendlines will tell us more than another month of building.

But the thesis has survived everything we've thrown at it so far: **trust in AI systems is not a property you assert — it's an artifact you build, hash, and gate on.**

---

*Signet is a FastAPI + React platform implementing governed agent workflows with evidence-gated releases. The methodology, evidence formats, and calibration mathematics described here are documented in the project's `docs/` directory: `icm-paper.md`, `evidence-pack.md`, `enterprise-scenario.md`, and `master-backend-platform-spec.md`.*
