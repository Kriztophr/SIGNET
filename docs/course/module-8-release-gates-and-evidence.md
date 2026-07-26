# Module 8 — Release gates and evidence packs

**Core question:** what does "prove this was governed" look like as a file?

**Time:** ~90 minutes · **Roles used:** environment manager, auditor

## Objectives

1. Drive a release gate down both paths: blocked (fail-closed) and approved (evidence-complete).
2. Export a run's evidence pack and verify its hash chain independently.
3. Map pack sections to the regulatory questions they answer (EU AI Act, SR 11-7).

## Concepts

### The release gate

Promoting an environment version is requesting permission to use a configuration for real work. The evidence evaluator gathers, per version: eval-run outcomes, regression pack pass rates, open disagreements, active drift signals, and human-capacity resilience thresholds (module 9). **Any gap or failure → status `blocked`, with every reason listed.** Clean evidence → `approval_pending`, and the human approval **re-checks the evidence at decision time** — evidence can rot between request and click, and the gate knows it.

Two field notes from this platform's production history: a version was blocked because of one failed and two unscored eval runs left over from old demos (the gate remembers what people forget); and default requirements are strict on purpose — relaxations like `require_eval_evidence: false` are themselves recorded in the requirements JSON, so leniency is visible forever.

### The evidence pack

`GET /governance/evidence-packs/runs/{run_id}` (auditor role) returns one self-contained JSON document per workflow run: run lineage, stage contracts (hashed) with ICM context manifests, artifacts (content-hashed, actor-attributed — human or agent), review decisions with rationales, eval scores with judge provenance and agreement, disagreements, drift signals, model usage and spend, audit events, judge-calibration metrics (module 7's TPR/TNR — proof the automated oversight was itself validated), and a control mapping.

Its integrity design is the teachable core:

- **Hash chain:** entries are canonically serialized; each entry's SHA-256 incorporates the previous hash; a root hash seals the pack. Any edit, deletion, or reordering breaks the chain.
- **Pure verification:** `verify_evidence_pack(pack)` re-walks the chain from the served JSON alone — no database, no vendor trust. Auditors verify; they don't take your word.
- **No self-reference:** the export itself is audited, but the export event is recorded *after* the pack is built — a pack never contains its own export, avoiding infinite regress.
- **Least disclosure:** storage URIs are excluded; content is identified by hash, not by fetchable location.

### The regulatory translation

The pack's control_mapping section indexes its contents against EU AI Act Annex IV (technical documentation), Article 12 (record-keeping), 14 (human oversight), 19/72 (logs, post-market monitoring) and SR 11-7's validation/monitoring expectations — a translation layer with an explicit non-conformity-claim disclaimer, so an auditor can navigate, and nobody mistakes a JSON file for a certification.

## Lab

1. **Get blocked on purpose.** As environment manager, request promotion (`POST /environment/promotions`) for the environment version your course tenant has been abusing — it has failed evals, splits, maybe drift. Read every blocking reason and trace each to the module where you created it. This is your course transcript, written by the gate.
2. **Get approved honestly.** Promote a version with clean evidence (run a fresh eval to a clean pass first), or relax a requirement explicitly and note how the relaxation itself appears in the record. Approve it (Release Gates → Approve release) and observe the re-check.
3. **Export the pack.** As auditor, export your capstone-track run's evidence pack from the run inspector (Export Compliance Pack) or the API. Skim every section; find your own name.
4. **Verify and tamper.** In a Python shell: run `verify_evidence_pack(pack)` from `app.governance.audit.evidence_pack` → `True`. Now change one character of one artifact hash and re-verify → `False`. You have just done the auditor's job end to end.
5. **Deliverable:** both promotions' evidence JSON (blocked + approved), plus your tamper demonstration (before/after verification results).

## Knowledge check

1. Why must approval *re-check* evidence rather than trusting the evidence gathered at request time?
2. The pack excludes storage URIs but includes content hashes. What attack/abuse does that trade away, and what does it preserve?
3. An auditor asks: "Your logs say the run was reviewed — why should I believe the log?" Answer using the hash chain and the pure verifier.

## Reading

- `docs/evidence-pack.md` — full section-by-section narrative including the control mapping and a verification snippet.
- `docs/master-backend-platform-spec.md` §17 and §22 — gate and export requirements.
