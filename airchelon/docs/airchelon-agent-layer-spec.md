# Airchelon — Agent Layer Technical Specification

*Fills the gap flagged in the master build checklist, Section 3: "no concrete orchestration architecture, model choice, or cost budget." Companion to the Editorial Operating System, which defines the pipeline this layer plugs into.*

Prices verified against Anthropic's pricing documentation, 3 August 2026.

---

## 1. The architectural decision: this is a workflow, not a swarm

The four roles in the Editorial Operating System — research, draft, disclosure-flag, repurpose — do not need an agent framework. They need four prompts, run in a fixed order, with a human gate in the middle.

Multi-agent orchestration frameworks (LangGraph, CrewAI, AutoGen) exist to coordinate agents that negotiate, delegate, and hand off dynamically. Airchelon's pipeline does none of that. The sequence is fixed, the handoffs are deterministic, and the most important transition in the whole system is a *stop* — nothing crosses step 4 without a person. Adopting a framework buys orchestration you don't need and adds a dependency you'd have to reason about during an audit.

**Recommended stack:**

- A git repository holding one prompt file per agent, plus the brand voice guide and the source-list schema.
- Scripts calling the Messages API directly, or Claude Code driving the repo.
- The review tool (already built) as the system of record for state and audit.

Git is doing real governance work here, not just version control. When someone asks which prompt produced a piece published eight months ago, `git log` answers it. That's an audit artifact you get for free by structuring it this way.

**The one hard architectural rule:** the pipeline halts at draft. There is no code path from the drafting agent to publication. Not a disabled flag, not a config option — no path. Every autonomous-publishing incident starts as a convenience shortcut that seemed safe at the time.

---

## 2. Agent specifications

### 2.1 Research agent

**Model:** `claude-sonnet-5` — strong tool use, and this stage is dominated by fetched-content input tokens rather than reasoning depth.

**Tools:** web search, web fetch.

**Output contract:** a structured source file (JSON), never prose. One record per claim:

```json
{
  "id": "S-014",
  "claim": "single factual assertion, one sentence",
  "source_url": "https://…",
  "publisher": "",
  "published_date": "",
  "accessed": "ISO timestamp",
  "quote_or_locator": "short excerpt or section reference",
  "confidence": "direct | inferred | contested"
}
```

**Hard rules:**
- If no source is found, the agent records `"confidence": "unsourced"` and moves on. It never fills a gap from parametric knowledge. An unsourced record is a visible hole; a plausible invented one is not.
- Anything marked `contested` must carry at least two source records taking different positions.
- No synthesis, no narrative, no recommendations. Prose here would let unsourced framing leak into the draft.

This contract is what makes the review checklist item *"every factual claim traces to a source in the research file"* mechanically checkable rather than a judgement call.

### 2.2 Drafting agent

**Model:** `claude-opus-5` — voice is the product, and this is the one stage where paying for the top model is justified.

**Tools: none.** This is deliberate and load-bearing. Without web access, the drafting agent cannot introduce a fact that isn't already in the source file. Every factual sentence must carry a source ID. Anything the agent wants to assert but can't attribute goes into a `NEEDS SOURCE` block at the foot of the draft rather than into the body.

**Inputs:** the source file, the piece brief, the brand voice guide, and 2–3 previously published pieces as voice exemplars.

**Output:** draft with inline `[S-014]` citations, plus the `NEEDS SOURCE` block.

### 2.3 Disclosure-flagging agent

**Model:** `claude-haiku-4-5-20251001` — this is classification, not composition.

**Runs:** on the draft, before it reaches human review.

**Checks:**
- Does the piece read as personal opinion, experience, or testimonial in a way that triggers FTC disclosure expectations?
- Do EU AI Act Article 50 transparency obligations apply to this piece?
- Does any body sentence make a factual claim with no source ID attached?
- Does the assigned risk tier look too low given the content — specifically, does the piece contain anything a reader in a regulated role could act on as guidance?

**Output:** a flag list. It never edits the draft, and it can propose tier *escalation* only — mirroring the rule enforced in the review tool. A flag that could lower a tier would create exactly the pressure the escalation-only rule exists to remove.

### 2.4 Repurposing agent

**Model:** `claude-haiku-4-5-20251001`, via the Batch API.

**Runs:** after step 8 only. Its input is the published piece, never a draft. This is a governance rule, not a scheduling preference: if the repurposing agent can read drafts, unreviewed material can reach social channels ahead of the review gate, which defeats the entire pipeline.

---

## 3. Cost budget

Assumptions: 4 essays per month, ~1,500 words each, ~10 sources per piece, 3–4 drafting passes.

| Stage | Model | Approx. per piece |
|---|---|---|
| Research (incl. ~15 web searches at $10/1,000) | Sonnet 5 | ~$0.47 |
| Drafting (3–4 passes) | Opus 5 | ~$1.10 |
| Disclosure flagging | Haiku 4.5 | ~$0.02 |
| Repurposing (batch) | Haiku 4.5 | ~$0.02 |
| **Total per piece** | | **~$1.60** |

**At launch cadence (4 pieces/month): under $10/month.** Budget $25/month to absorb retries, experimentation, and podcast transcript work.

**The finding that matters:** the agent layer is not a meaningful cost. It's cheaper than the Ghost(Pro) subscription and roughly a tenth of the one-time Signal theme licence. Even at daily cadence — 20+ pieces a month — this stays under $100/month.

Which means **cost is not the constraint on Airchelon's content volume. Review bandwidth is.** The human gate is the bottleneck by design, and no amount of API budget moves it. Plan capacity against reviewer hours, not spend.

**Cost levers, in order of usefulness:**

1. **Prompt caching on the drafting stage.** The brand voice guide, source file, and voice exemplars are re-sent on every revision pass. A cache hit costs 10% of base input, so caching pays for itself after a single read on the 5-minute window.
2. **Batch API** for disclosure flagging and repurposing — 50% off both directions, and neither is time-sensitive.
3. **Web fetch over web search** where you already know the URL. Fetch adds no charge beyond the tokens; search is $10 per 1,000.

**Diary note:** Sonnet 5 is on introductory pricing of $2/$10 per MTok through 31 August 2026, rising to $3/$15 on 1 September. That lifts the research stage by roughly 50%, which is about 20p a piece. Not a planning concern, but don't be surprised by the line.

Set a spend limit in the Console regardless. A runaway loop is a bug risk, not a budget risk, and a hard cap catches it faster than a bill does.

---

## 4. What the audit trail must capture

For Tier 3 to be defensible, "an AI drafted it" is not sufficient provenance. Each piece's audit entry should record:

- **Pinned model IDs** for every stage — `claude-opus-5`, `claude-sonnet-5`, `claude-haiku-4-5-20251001`. Pin them explicitly; never float to a "latest" alias. A silent model change alters output character and destroys the reproducibility of an audited piece.
- **The git commit hash of the prompt set** used.
- **The source file** as it stood at draft time, stored alongside the piece.
- **The disclosure agent's flag list**, including any flag the human reviewer overrode, and why.

That last item is the one most systems skip and the one an auditor will ask about first. An overridden flag with a recorded reason is a defensible judgement. An overridden flag with no record is indistinguishable from a missed one.

---

## 5. Build order

1. Source-list schema and the research agent — everything downstream depends on this contract.
2. Drafting agent with the voice guide, tested against the two essays you've already planned.
3. Disclosure-flagging agent.
4. Wire model ID and prompt-commit capture into the review tool's audit entries.
5. Repurposing agent — last, and only once something has actually published.
