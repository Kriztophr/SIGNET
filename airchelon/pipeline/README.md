# Airchelon agent pipeline

Scripts that call the Messages API directly — no orchestration framework, per
`docs/airchelon-agent-layer-spec.md`. Three agents run in fixed order, and the
pipeline **halts at draft**: nothing here can publish, and the repurposing agent
is deliberately not wired yet (spec build order step 5 — it runs on published
pieces only, and nothing is published).

```
run_research.py    claude-sonnet-5              → content/research/<id>.json
run_draft.py       claude-opus-5 (NO tools)     → content/drafts/<id>.md
run_disclosure.py  claude-haiku-4-5-20251001    → content/drafts/<id>.flags.txt
                   ── human review gate in the review tool; no code path past it ──
```

`content/essays/` is reserved for pieces that have cleared the review gate.
Agent output never lands there.

## Setup

Requires [uv](https://docs.astral.sh/uv/) (each script carries inline
dependency metadata) and an API key:

```sh
cp airchelon/.env.example airchelon/.env   # then fill in ANTHROPIC_API_KEY
```

Set a spend limit in the Anthropic Console before first use. Expected cost is
~$1.60 per piece (spec section 3) — the limit is a runaway-loop catch, not a
budget concern.

## Running a piece through

```sh
# 1. Research — verified source file, schema-validated before it is written
uv run airchelon/pipeline/run_research.py --piece-id 02-slug \
    --brief "What the piece is commissioned to cover"

# 2. Draft — written from the source file and nothing else
uv run airchelon/pipeline/run_draft.py --piece-id 02-slug --brief "..." \
    --exemplar airchelon/content/essays/01-the-first-thing-we-governed.md

# 3. Disclosure flags — run before the draft reaches human review
uv run airchelon/pipeline/run_disclosure.py --piece-id 02-slug --tier 2

# Revision pass after reviewer notes (hits the prompt cache):
uv run airchelon/pipeline/run_draft.py --piece-id 02-slug --brief "..." \
    --revise --notes "Tighten section 2; cut the third altitude metaphor."

# Validate a source file without calling the API:
uv run airchelon/pipeline/run_research.py --validate airchelon/content/research/02-slug.json
```

Each script ends by printing a **provenance block** — pinned model ID, the git
commit hash of the prompt that ran, and content hashes. Paste it into the
Provenance section of the review tool (`tools/review/airchelon-review.jsx`);
Tier 3 cannot clear compliance sign-off without a complete provenance record.

## Rules the scripts enforce

- **Pinned models.** Model IDs are constants in `common.py`, never aliases.
- **Committed prompts only.** A run aborts if the prompt file has uncommitted
  changes — the recorded `prompt_commit` must describe the prompt that ran.
- **The drafting agent gets no tools.** Its request carries no `tools`
  parameter; every fact must already be in the source file.
- **Validation before write.** A research file that fails the schema (after one
  repair round-trip) is not written. A draft citing a nonexistent or unsourced
  record ID prints a warning for the reviewer.
- **Escalation only.** The disclosure agent is instructed, and reminded per
  run, that it may propose raising a tier and never lowering one.
