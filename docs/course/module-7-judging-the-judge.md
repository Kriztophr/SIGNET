# Module 7 — Judging the judge

**Core question:** when can you trust an LLM to score another LLM?

**Time:** ~2 hours (the statistics deserve it) · **Roles used:** evaluator · **Needs:** a judge model configured (`ICM_LLM_JUDGE_*`; a free OpenRouter model works)

## Objectives

1. Configure an advisory LLM judge on an eval suite and explain each safeguard around it.
2. Build a golden set, run a calibration, and read TPR/TNR with confidence intervals.
3. Explain the Rogan–Gladen correction and — more importantly — when the system refuses to apply it.

## Concepts

### Advisory means advisory

The judge scores *sampled* eval runs against the same rubric humans use, and its score is recorded as an agent-authored advisory opinion. It never counts toward the reviewer quorum and never decides a gate. Its value is disagreement: at human decision time the platform records whether the judge agreed, and when rolling agreement drops below the suite's threshold, sampling **auto-widens to 100%** and each further disagreement raises a drift signal. Low trust triggers more scrutiny — automatically, in the safe direction.

### The judge is a model release

A judge configuration (provider + model + rubric version) must be validated like anything else you'd deploy. Signet's calibration module treats this properly:

- **Golden set:** CalibrationExamples — artifacts with known human verdicts (harvested from real decided eval runs, or hand-authored "known failure modes"). Each example gets an **immutable split**: train (prompt material), dev (iteration), or **test — frozen the moment any calibration run has used it**. Additions after freezing open test-set v2; v1 is never edited. Examples from the same workflow run share a split (group leakage guard).
- **Metrics, defect-positive:** the *positive class is a defect*. **TPR** = of work humans failed, what fraction does the judge fail? (Misses here = defects sailing through.) **TNR** = of work humans passed, what fraction does the judge pass? (Misses here = noise, alert fatigue.) Both come with **Wilson confidence intervals**, which stay honest at the small sample sizes golden sets actually have.
- **Fail-closed gate:** a suite can require minimum test-split TPR/TNR before the judge may score production work at all. No calibration run, or a failing one → the judge stays silent. Humans are unaffected — the judge is a layer on top of human quorum, never a substitute.

### Correcting production estimates — and refusing to

If you know judge quality, you can correct its raw production fail rate into an estimate of the *true* fail rate (Rogan–Gladen, from diagnostic epidemiology):

> true rate ≈ (observed rate + TNR − 1) / (TPR + TNR − 1)

The denominator, TPR + TNR − 1, is the judge's **informedness** — how much better than a coin it is. When informedness is near zero the correction explodes, so Signet **withholds the corrected estimate and flags the judge as uninformative** rather than printing garbage with decimal places.

### The production episode you will now reproduce

This platform's first live calibration run scored TPR = 1.0 and **TNR = 0.0** → informedness 0 → uninformative, correction withheld. The postmortem finding: the golden "pass" example was a stub artifact a scripted human had waved through — **the judge was right and the gold label was wrong**. Calibration audits your ground truth as much as your judge. Watch for the same thing in your own golden set.

## Lab

1. **Enable the judge.** On your module 5 suite, set `config_json.llm_judge = {enabled: true, sampling_rate: 1.0, agreement_threshold: 0.8, window: 20}` (sampling 1.0 so the lab is deterministic). Run an eval; verify the judge's advisory score appears, marked agent-authored, and that `reviewer_count` excludes it.
2. **Build a golden set (≥6 examples).** Harvest your decided eval runs (`POST /evals/calibration/examples/harvest`; check `/evals/calibration/suggestions` for disagreement-flagged candidates) and hand-author at least two *known failure modes* — artifacts that look plausible but violate the rubric. Assign splits; put at least four in test.
3. **Calibrate.** `POST /evals/calibration/runs` for your judge config over the test split. Read the results: TPR, TNR, Wilson intervals, informedness, per-example verdicts.
4. **Interrogate every miss.** For each example the judge got "wrong," decide: is the judge wrong, or is the gold label wrong? (Expect at least one gold-label casualty — see the episode above.) Fix labels only via new examples/versions; frozen test sets don't get edited.
5. **Arm the gate.** Set `llm_judge.calibration_gate = {enabled: true, min_tpr: 0.7, min_tnr: 0.7}`. If your judge fails the bar, confirm it goes silent on new evals while human scoring proceeds untouched.
6. **Deliverable:** your calibration run's metrics with a 3–4 sentence verdict: is this judge deployable, what would you change first (judge, rubric, or golden set), and what does its informedness let you say about production fail rates?

## Knowledge check

1. Your judge shows TPR 0.95, TNR 0.40. In operational terms, what is it doing to your team, and is it more dangerous or merely annoying?
2. Why is the test split frozen *forever*, with additions going to v2 — what does editing a used test set do to every historical calibration claim?
3. State the condition under which Signet withholds the Rogan–Gladen estimate, and defend the withholding to an executive who "just wants the number."

## Reading

- `docs/evidence-pack.md` — the judge_calibration section auditors will read.
- `docs/master-backend-platform-spec.md` §13.2/§13.3 and §28.8 — calibration seams and semantics.
