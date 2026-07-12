# Run-scoped evidence packs

One API call exports the complete governance record of a workflow run as a
single, self-verifying JSON document — the artifact an auditor, model-risk
reviewer, or regulator asks for when they say *"show me everything that
happened on this run, and prove nothing was altered."*

```
GET /governance/evidence-packs/runs/{run_id}
```

Access: `auditor` (and `admin`). Every export is itself recorded as a
`governance.evidence_pack.exported` audit event carrying the pack's root hash,
so the audit trail attests which evidence snapshots were handed out and by
whom.

## What the pack contains

Entries are emitted in a fixed section order (`icm-evidence-pack/v1`):

| Section | Contents |
| --- | --- |
| `run` | Run status and timestamps, correlation id, triggering actor, workflow template + version lineage, linked environment template version. |
| `stages` | Every stage run: contract identity (SHA-256 of the stage contract markdown), execution mode (manual/automated), review/eval gate flags, attempt, outcome, error summary, and the ICM context manifest (layer 0–4 refs) that defined what the stage could see. |
| `artifacts` | Full artifact lineage: role, version, author (human user identity, or agent), human-edit flag, source-artifact link for edits, and the SHA-256 of the stored content (URIs are not exposed; the hash pins the content). |
| `reviews` | Every review task and each decision on it — approve/edit/reject/escalate, rationale, the deciding human's identity, timestamp, and the edited artifact when the decision rewrote the work. |
| `evals` | Every eval run linked to the run: suite, rubric + version, all reviewer scores with **judge provenance** (`llm_judge`, judge model, `scored_by_type`), and the human decision with its metrics (including judge agreement). |
| `disagreements` | Reviewer disagreement records on those eval runs, with status. |
| `drift_signals` | Drift signals on the suites this run was evaluated under (including `judge_human_disagreement` signals). |
| `llm_usage` | Every LLM call billed to this run — model, purpose (executor/judge), token counts, cost. Proves which model produced what, and what it cost. |
| `audit_events` | The full ordered audit trail for the run. |
| `judge_calibration` | Per suite: judge config, rolling human-agreement rate and sample size, whether sampling has auto-widened, and the calibration methodology status (see below). |
| `control_mapping` | The machine-readable version of the mapping tables below, with a disclaimer. |

## Tamper evidence: the hash chain

The pack carries an SHA-256 entry chain (`integrity.algorithm =
"sha256-entry-chain"`):

1. Canonical JSON = `json.dumps(value, sort_keys=True, separators=(",", ":"),
   ensure_ascii=False)` over JSON primitives (UUIDs as strings, datetimes as
   ISO-8601).
2. The chain is seeded with `sha256(canonical_json(header))`, where the header
   is the pack minus `entries` and `integrity` — so the run identity, export
   time, exporting user, and section counts are all covered.
3. Each entry's hash is `sha256(prev_hash_hex + canonical_json({index,
   section, data}))`.
4. `integrity.root_hash` is the last entry's hash.

Editing, reordering, inserting, or dropping any entry breaks every hash after
it. A third party can verify a served pack with ~15 lines of any language's
standard library; in Python:

```python
import hashlib, json

def verify(pack: dict) -> bool:
    cj = lambda v: json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    h = lambda s: hashlib.sha256(s.encode()).hexdigest()
    header = {k: v for k, v in pack.items() if k not in ("entries", "integrity")}
    prev = h(cj(header))
    for i, e in enumerate(pack["entries"]):
        prev = h(prev + cj({"index": e["index"], "section": e["section"], "data": e["data"]}))
        if e["index"] != i or e["sha256"] != prev:
            return False
    return pack["integrity"]["root_hash"] == prev
```

(The platform ships the same function as
`app.governance.audit.evidence_pack.verify_evidence_pack`.)

To make a pack independently attestable, record its `root_hash` somewhere the
platform cannot rewrite — a ticket, an email, a signed release note. The
exported audit event already stores it in the platform's own trail.

## EU AI Act mapping (Regulation (EU) 2024/1689)

The pack supplies **supporting evidence** for the obligations below for the
AI-assisted workflow it documents. It is not a conformity assessment, and
several Annex IV items (standards applied, declaration of conformity) are
provider-level documents outside a run record's scope.

| Obligation | Where the pack helps |
| --- | --- |
| **Art 12 — Record-keeping** | The whole pack: automatically generated, run-scoped records with actor identity, timestamps, correlation ids, and tamper evidence. |
| **Art 14 — Human oversight** | `reviews` (humans approve/edit/reject/escalate every gated stage), `evals` (human decisions; the LLM judge is advisory and never decides), `disagreements`, and the operator kill switch visible in `audit_events`. |
| **Art 19 — Automatically generated logs** | `audit_events`, retained and exportable. |
| **Art 72 — Post-market monitoring** | `drift_signals`, `judge_calibration` (rolling agreement, auto-widened sampling), regression/baseline machinery feeding them. |
| **Annex IV(1) — General description** | `run` (system, template, versions, environment binding). |
| **Annex IV(2) — Development process & design** | `stages` (contract hashes, ICM context manifests — exactly what the model was given), `artifacts` (what it produced, and every human edit). |
| **Annex IV(4) — Performance metrics & validation** | `evals` (rubric versions, weighted scores, decisions), `judge_calibration`. |
| **Annex IV(9) — Post-market plan evidence** | `drift_signals`, `judge_calibration`. |

## SR 11-7 mapping (Federal Reserve / OCC model risk management)

| SR 11-7 element | Where the pack helps |
| --- | --- |
| **Model development & documentation** | `run` + `stages` + `artifacts`: versioned templates, contract hashes, full input/output lineage per stage. |
| **Model validation** | `evals`: rubric-scored human validation with versioned rubrics and durable decisions. |
| **Effective challenge** | `reviews` (edit/reject decisions with rationales are recorded challenge), `disagreements` and their adjudication status. |
| **Ongoing monitoring & outcomes analysis** | `drift_signals`, `judge_calibration` rolling agreement, eval pass rates over time (see `bench/governance_metrics`). |
| **Model use controls** | `llm_usage` (which model, what purpose, hard budget cap), execution-mode flags, kill-switch events in `audit_events`. |
| **Governance & audit** | `audit_events`, RBAC-gated export, exports themselves audited. |

## Judge calibration status

Automated oversight must itself be validated. Today the pack reports the
**rolling-agreement** method: every LLM-judge verdict is compared with the
human decision on the same eval run; agreement below the suite's threshold
auto-widens judge sampling to 100% and emits drift signals. The
`judge_calibration` section carries the live numbers (agreement rate, sample
size, widened flag) per suite.

The next roadmap stage adds formal calibration: golden examples with human
gold labels in frozen train/dev/test splits, per-config TPR/TNR with
confidence intervals, a fail-closed CI gate on judge-config changes, and a
Rogan–Gladen corrected production fail-rate estimate. When that lands,
`judge_calibration.methodology.validated_split_metrics` is populated; until
then it is explicitly `null` — the pack never overstates its own validation.
