# Airchelon Editorial Operating System

*Defines two things: (1) the mandatory human-review system that sits between any AI-drafted content and publication, and (2) how that same system extends once Airchelon hires human writers. One system, two entry points — not two separate processes.*

---

## 1. Core principle

Nothing publishes without a named human sign-off. That's true on day one with just you and a team of agents, and it stays true after Airchelon hires its first writer — the review gate doesn't go away when humans start writing, it just moves earlier in the pipeline for them (they skip the AI research/draft stages).

This also isn't just an editorial safeguard — it's a **risk-tiered, human-in-the-loop structure borrowed directly from the AI governance frameworks Airchelon writes about** (the EU AI Act's risk-based approach, NIST AI RMF's human-oversight principle). Running the newsroom this way isn't overhead — it's a live demonstration of the exact governance practice Airchelon sells expertise in, and it's worth naming that connection explicitly in consulting pitches later.

---

## 2. Risk tiers (determines how much review a piece needs)

| Tier | What qualifies | Review required |
|---|---|---|
| **1 — Perspective** | Opinion, commentary, general industry takes, no specific claims about named entities or regulatory positions | Founder voice/quality check only |
| **2 — Analysis** | References specific data, named companies, factual claims that could be wrong | Founder review + source verification (every claim traced to a cited source) |
| **3 — Regulated guidance** | Anything a healthcare, finance, aviation, or other regulated-industry reader could act on as compliance/regulatory guidance | Founder/managing-editor review **plus** compliance or subject-matter-expert sign-off, and explicit AI-involvement disclosure |

Tier 3 is the one that matters most — it's where an LLM hallucination stops being an embarrassment and becomes actionable bad advice given to someone in a regulated role.

---

## 3. The pipeline

```
1. Ideation        → topic proposed (founder or agent-suggested), founder approves calendar
2. Research         → research agent compiles sources; output MUST be a source list, not prose
3. Draft            → drafting agent writes from the sourced research, inline citations required
4. Human review     → MANDATORY GATE — see checklist below
5. Revision loop     → agent revises per reviewer notes; reviewer re-checks only the changed sections
6. Compliance sign-off → Tier 3 only — SME or qualified compliance reviewer, separate from the editorial reviewer
7. Final approval   → founder sign-off, every tier, no exceptions
8. Publish + log    → audit entry recorded: who drafted, who reviewed, tier, what changed
```

Human-written drafts (once there are human writers) enter at **step 4** — same gate, same checklist, same sign-off requirement. The system doesn't distinguish "AI drafts" from "human drafts" at the review stage; it treats all drafts the same from that point forward.

---

## 4. The review checklist (step 4, every piece, every tier)

- [ ] Every factual claim traces to a source in the research file — no unsourced claims survive to publish
- [ ] Correct risk tier assigned (reviewer can escalate a tier, not downgrade one)
- [ ] Brand voice check against the tone-of-voice section of the brand strategy
- [ ] AI-involvement disclosure applied if the piece reads as personal opinion/testimonial (per [FTC staff guidance, March 2025](https://humanadsai.com/blog/ftc-ai-generated-content-disclosure)) or if [EU AI Act Article 50](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50) transparency obligations apply
- [ ] Tier 3 only: named compliance/SME reviewer has signed off separately from the editorial reviewer — no single person clears both

---

## 5. Roles

| Role | Who (today) | Who (once Airchelon hires) |
|---|---|---|
| Editor-in-Chief | You — final sign-off, always | Same — retains Tier 3 sign-off even after hiring |
| Editorial reviewer (Tier 1–2) | You | Managing editor (first non-founder hire), once volume exceeds your review bandwidth |
| Compliance/SME reviewer (Tier 3) | You, if qualified for that vertical, else pause publish until a contractor SME is sourced | Contracted or staff SME per regulated vertical (healthcare, finance, aviation, etc.) |
| Research agent | AI | Unchanged — still supports human writers' research too |
| Drafting agent | AI | Unchanged — becomes optional writing assistant for hired writers, not a requirement |
| Disclosure-flagging agent | AI — flags anything needing AI-involvement disclosure before it reaches human review | Unchanged |

---

## 6. The "operating system" itself — what to actually build

You're right that a checklist alone won't hold up once volume increases — this needs a real system of record, not memory. Two honest options, in order of effort:

**MVP (build this first, no engineering required):** A Kanban-style board — Notion, Airtable, or even a GitHub-Projects board — with one card per piece, columns matching the pipeline stages above, a risk-tier tag, and a comment thread doubling as the audit trail. Given your GitHub comfort, a GitHub-PR-style flow works well here: agent draft = initial commit, your review notes = PR comments, sign-off = merge. This gets the discipline in place on day one at zero build cost.

**Real instrument (Phase 4 candidate):** Once Airchelon's software line exists, this review system is itself a natural first "instrument" — literally an application of the "insight → instrument" thesis to Airchelon's own operations. A purpose-built tool could add a public-facing provenance tag on published pieces ("Researched by Airchelon's agents, drafted by [agent], reviewed and approved by [you]") — turning the transparency requirement into a visible trust signal rather than a compliance afterthought, and giving future consulting clients something concrete to point to.

Start with the MVP board now; don't wait to build the real instrument before publishing anything.

---

## 7. When Airchelon hires human writers

**What doesn't change:** the pipeline, the risk tiers, the mandatory human sign-off, the audit log. A hired writer's draft still goes through step 4 onward exactly like an agent draft would.

**What's added:**
- **Onboarding:** brand voice/tone-of-voice training (from the brand strategy doc), a written disclosure policy covering the writer's own AI tool use (consistency matters — if Airchelon discloses its own AI use, a hired writer's undisclosed AI-assisted drafting would be a direct contradiction), and training on the review board itself.
- **Hiring trigger — capacity:** hire when content cadence consistently exceeds what you and the review gate can process without becoming the bottleneck.
- **Hiring trigger — credibility:** hire specifically for verticals where Airchelon needs a named expert byline you don't personally have (e.g., an aviation-regulatory specialist, an insurance-compliance specialist) — hire for expertise gaps, not just throughput.
- **New role at scale:** once there are multiple contributors, appoint a **managing editor** (human) to run Tier 1–2 review day-to-day, freeing you to focus on Tier 3 compliance sign-off and overall direction — same structure as the table in Section 5.
- **Compensation transition:** new hires start on the flat per-piece rate described in the business model doc; individual writers move to the Every-style revenue-share/churn-attribution model once there's enough subscriber data on their specific bylines to measure it — this is a per-writer transition, not a company-wide switch.

---

## 8. Immediate next step

Set up the MVP review board (Section 6) before publishing anything — even the very first essay should go through steps 4, 7, and 8 above, so the audit trail exists from piece #1, not retrofitted later once there's something to defend.
