# Airchelon — Project Context for Claude Code

Read automatically by Claude Code. Full detail on every decision lives in `/docs` — read the relevant doc before making changes in that area. Don't rely on this summary alone for anything you're about to build.

*Successor to the original handoff CLAUDE.md, updated 3 August 2026.*

## What Airchelon is

A publication + software company in the shape of Every.to's subscription-bundle model, built for regulated-industry professionals (healthcare, finance, aviation, insurance) with an explicit remit to write about AI models, AI governance, and the creator economy as freely as Every does — not boxed into a single vertical. Positioning, mission, tone of voice, taglines: `docs/airchelon-brand-strategy.md`.

Name: **Airchelon** (Air + Echelon). Identity direction in `docs/airchelon-logo-brief.md`. Organizing question: "What do you see from up here?"

## Repo layout

```
docs/        Strategy and specification. Authoritative.
prompts/     One file per agent. Versioned — the commit hash is an audit artifact.
schemas/     Output contracts. source-file.schema.json governs the research agent.
content/     essays/, research/ (source files), drafts/, published/ (human-moved only), audit/ (run records).
pipeline/    The wired agent layer. Four scripts calling the Messages API directly.
tools/review/  The editorial review tool.
```

## Running the pipeline

From the repo root, with `ANTHROPIC_API_KEY` set (deps: `uv sync`):

```sh
uv run python -m airchelon.pipeline.research P-001 --brief "What the piece must establish"
uv run python -m airchelon.pipeline.draft P-001            # add --revision-note for passes 2+
uv run python -m airchelon.pipeline.disclosure P-001
# … human review gate in tools/review/, then a human moves the piece to content/published/ …
uv run python -m airchelon.pipeline.repurpose airchelon/content/published/<piece>.md
```

Each run refuses to start against an uncommitted prompt file, and appends a
record (pinned model ID, prompt commit, input/output hashes) to
`content/audit/<piece-id>.jsonl`.

## Decisions locked in

- **Platform:** Ghost via Ghost(Pro). **Theme:** Signal by Enova Studio ($129 one-time, Ghost 6.0+, Tailwind v4). *Unconfirmed:* whether its RSS is natively Apple/Spotify-submittable — verify against Signal's docs before assuming. Fallback: Transistor/Buzzsprout/Captivate.
- **Editorial model:** founder + AI agents (research / draft / disclosure-flag / repurpose), not a contributor roster. Human writers added later on triggers in the editorial ops doc. Deliberate, not a placeholder.
- **Palette:** finalized light + dark, amber accent `#B8631A` / `#E08A34`. Full hex values in the logo brief, Section 6.
- **Build order:** media → community/live → enterprise consulting/training → cohort courses → software instruments. Consulting deliberately ahead of software. Reasoning in `docs/airchelon-business-model.md`.
- **Editorial governance:** mandatory human review gate on every piece, risk-tiered Tier 1 → Tier 3. Pipeline in `docs/airchelon-editorial-operating-system.md`.
- **Agent layer:** no orchestration framework. Four prompts run in fixed order, git-versioned, calling the Messages API directly. Model choice and cost budget in `docs/airchelon-agent-layer-spec.md`.

## Rules that are not negotiable

If a task would require breaking one of these, stop and raise it with the founder rather than working around it.

1. **The pipeline halts at draft.** There is no code path from the drafting agent to publication. Not a disabled flag — no path.
2. **Tiers escalate only.** Nothing in this repo may lower a piece's risk tier. The review tool enforces it; agents must not propose it.
3. **The drafting agent gets no tools.** No web access. It writes only from the source file. This is what makes "every claim traces to a source" mechanically checkable.
4. **The repurposing agent reads published pieces only.** Never drafts.
5. **Model IDs are pinned, never floating.** `claude-opus-5`, `claude-sonnet-5`, `claude-haiku-4-5-20251001`. A silent model change destroys reproducibility of an audited piece.
6. **Every audit entry names a person.** No system-generated approvals.

## Current state

**Built:** editorial review tool, agent layer spec, four agent prompts, source file schema, essay 1 drafted, and — as of 5 August 2026 — the agent layer wired to the Messages API (`pipeline/`): research (Sonnet 5 + web tools, schema-validated output), drafting (Opus 5, no tools, prompt-cached prefix), disclosure flagging (pinned Haiku), repurposing (pinned Haiku via Batch API, refuses anything outside `content/published/`). The review tool now captures per-stage model IDs and the prompt commit as named audit entries, and blocks Tier 3 publish on an incomplete provenance record. Governance tests live in `tests/test_airchelon_pipeline.py`.

**Not built / still true:** the review tool is single-user local storage, not shared. No piece has been run end to end through the pipeline against the live API yet.

**Blocking, in priority order:**

1. **Founder capacity decision** — full-time vs. alongside the existing Business Change Analyst role. Governs every timeline. Not a Claude Code task; flag it if unaddressed.
2. **Formal trademark clearance** before any further brand spend. Risk is higher than the original handoff assumed — see the status block at the top of `docs/airchelon-master-build-checklist.md`. Do not commission logo artwork until this resolves.
3. **Entity formation, domain, handles.** All confirmed available, none claimed. Cheapest and most time-sensitive item on the list.
4. **One SME contractor per priority vertical.** Tier 3 is currently unpublishable — the review tool requires a compliance signer distinct from the editorial reviewer and no such person exists. This now sits above software in priority.
5. **Ghost(Pro) setup, Stripe, Signal install and restyle** to the amber palette.
6. **AI-disclosure policy page live before essay 1 publishes.** Essay 1 argues disclosure must be systematic; publishing it without the policy live undercuts it on day one.

## Suggested next tasks in Claude Code

1. ~~Wire the research agent~~ — done, `pipeline/research.py`.
2. ~~Wire the drafting agent with no tools~~ — done, `pipeline/draft.py`.
3. Run essay 1 through the review tool end to end — ideation to published, every checklist item, provenance tag generated. A piece with a complete audit trail is the artifact you show a consulting prospect. (Needs a live `ANTHROPIC_API_KEY` and a human at the review gate.)
4. ~~Add model ID and prompt commit hash capture to the review tool's audit entries~~ — done, Provenance section in `tools/review/airchelon-review.jsx`; Tier 3 publish is blocked without it.
5. Restyle the Signal theme to the palette. (Needs the purchased theme files — not in this repo.)

## Docs index

| File | Covers |
|---|---|
| `docs/airchelon-master-build-checklist.md` | Full status tracker. **Read the status block at the top first.** Keep updated. |
| `docs/airchelon-brand-strategy.md` | Positioning, mission, tone, pillars, taglines, format range |
| `docs/airchelon-logo-brief.md` | Visual identity, symbol concepts, colour palette, typography direction |
| `docs/airchelon-business-model.md` | Pricing by phase, build-order reasoning, targets |
| `docs/airchelon-editorial-operating-system.md` | Risk-tiered pipeline, roles, hiring triggers |
| `docs/airchelon-agent-layer-spec.md` | Agent architecture, model choice, cost budget, audit requirements |
