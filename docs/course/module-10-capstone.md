# Module 10 — Capstone: one governed delivery

**Core question:** can you do all of it, on a domain you choose?

**Time:** 4–6 hours over a week · **Roles used:** all of them (that's the point)

## The brief

Design, run, break, judge, gate, and audit one complete governed AI workflow for a consequential deliverable in a domain you know — then explain it to an executive in plain language. Everything must live in your Signet tenant as real objects; nothing may exist only in your write-up.

## Requirements

Your delivery must contain all of the following, each traceable in the final evidence pack:

1. **A blueprint you designed** (module 3): 3–5 stages with written contracts, at least one review gate and one eval gate, each gate placement justified in your memo.
2. **At least one automated stage** (module 6) executed by a real model — plus **one demonstrated containment**: a degraded-to-human failure you forced, or a kill-switch cancellation (on a sacrificial run).
3. **An honest human review** (module 4) including at least one **edit-override** with a written rationale naming the flaw.
4. **A quality check under your own rubric** (module 5) with two independent reviewers — and one engineered split so your record contains a disagreement.
5. **A judge with a verdict on itself** (module 7): advisory judge enabled, golden set ≥ 6 with at least two hand-authored failure modes, one calibration run over a frozen test split, and the calibration gate armed with thresholds you defend.
6. **Both gate outcomes** (modules 8–9): one promotion blocked for reasons you then remediate (at least one reason must be a resilience threshold from module 9), and one approved on complete evidence.
7. **The evidence pack** (module 8): exported for your flagship run, hash chain verified, plus a tamper demonstration.
8. **The governance memo** (1–2 pages, for a non-technical executive) answering exactly four questions:
   - What does this workflow produce, and what could go wrong if ungoverned?
   - Where do humans decide, and what did they actually change? (Report your real override rate and what it means.)
   - How much can the automated oversight be trusted? (Your judge's TPR/TNR in plain words — including, if applicable, why a number was *withheld*.)
   - What would you show a regulator, and how would they know it isn't fabricated?

## Grading rubric (100 points)

| Criterion | Points | What earns full marks |
|-----------|--------|----------------------|
| Blueprint & gate design | 15 | Decidable contracts; gates at irreversibility/judgment points; each gate justified against oversight-theater risk |
| Gates exercised honestly | 20 | Real pause states; an edit with a rationale that names a real flaw; a recorded disagreement; no rubber stamps |
| Agent containment | 15 | Agent work held at a human gate; one containment demonstrated with evidence; provenance chain intact |
| Judge calibration | 20 | Frozen test split; metrics read correctly with CIs; at least one miss interrogated (judge wrong vs. gold wrong); defensible gate thresholds |
| Release gates & evidence | 20 | Blocked→remediated→approved arc incl. a resilience reason; pack verified; tamper demo; sections mapped to the four memo questions |
| Governance memo | 10 | An executive with no AI background could act on it; numbers honest, incl. any withheld ones |

**Auto-fail conditions** (instructor discretion): fabricated artifacts presented as real work; a golden set that contains no genuine failure mode; a memo claiming certainty the evidence doesn't support.

## Advice from the platform's own history

- **Let it block you.** The strongest capstones are the ones where the first promotion attempt returned three blocking reasons the student didn't expect. That page is the course working.
- **Your golden set is probably wrong somewhere.** The reference deployment's first calibration run "failed" because a gold label was bad, not the judge. Find your version of that.
- **Format drift is Tuesday.** If your automated stage never fails, you haven't run it enough times to write honestly about containment.
- **Write the memo last, from the pack.** If a memo claim isn't in the evidence pack, either do the work or cut the claim.

## Submitting

Submit: tenant + flagship run id, the exported evidence pack JSON, both promotion evidence JSONs, the calibration run id, and the memo (markdown or PDF). If taught live, be ready to defend any gate decision in a 10-minute oral.
