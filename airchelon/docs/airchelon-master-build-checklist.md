# Airchelon — Master Build Checklist

*Full gap map across everything a real business needs, not just brand and editorial. ✅ = done, ⬜ = not started, 🔶 = partially done. Cross-references the four docs already built: Brand Strategy, Logo Brief, Business Model & Pricing, Editorial Operating System.*

---

## Status update — 3 August 2026

Changes since this checklist was last authoritative. The body below has **not** been rewritten line by line; where it conflicts with this block, this block is current.

**Now done:**

- ✅ **Editorial review system** — built as custom software rather than finished in Airtable. Source at `tools/review/airchelon-review.jsx`. Enforces escalation-only tiering, a blocking review gate, Tier 3 separation of duties, and a named immutable audit log. Supersedes the "board or lightweight custom tool" open question.
- ✅ **Agent orchestration architecture, model choice, and cost budget** — specified in `docs/airchelon-agent-layer-spec.md`. Agent prompts drafted in `prompts/`. Source file contract in `schemas/source-file.schema.json`.
- 🔶 **First content** — essay 1 drafted at `content/essays/01-the-first-thing-we-governed.md`. Not yet run through the review pipeline, not published.
- ✅ **Agent pipeline wired to the API** *(later on 3 Aug)* — `pipeline/run_research.py`, `run_draft.py`, and `run_disclosure.py` call the Messages API directly with the pinned models from the spec. The research script validates output against the source-file schema before writing; the drafting script sends no tools and prompt-caches the voice guide + source file for revision passes; every script refuses to run against an uncommitted prompt file and prints a provenance block (model ID, prompt commit, content hashes). Agent drafts land in `content/drafts/` — `content/essays/` is reserved for pieces past the review gate. The repurposing agent is deliberately not wired (spec build order step 5: published pieces only, and nothing is published).
- ✅ **Provenance capture in the review tool** *(later on 3 Aug)* — per-stage model ID + prompt commit fields with paste-import of the scripts' provenance blocks, each import written to the audit log; Tier 3 compliance sign-off is blocked until provenance is complete; disclosure-flag overrides can only be recorded with a stated reason. Closes the "what makes Tier 3 defensible" gap flagged in the agent layer spec, section 4.

**Now known, and worse than assumed:**

- 🔶 **Trademark** — informal search extended, formal clearance still not run. Three findings: (a) *Airchelon Soar Records* is an existing record label imprint using the identical string, distributing since roughly 2021 — live commercial use in media, closer to Airchelon's space than Aechelon is; (b) Aechelon Technology took majority PE investment in August 2024 and acquired a radar simulation division in December 2024, and maintains an active trademark portfolio; (c) "Echelon" is a crowded and litigious field, and *Echelon Front* holds class 41 registration for business leadership and executive development training — directly over the Phase 2 consulting/training pillar. Note also that the UK IPO does not refuse on relative grounds; passing examination is not clearance.
- ⬜ **Tier 3 is currently unpublishable.** The review tool requires a named compliance/SME signer distinct from the editorial reviewer, and no such person exists for any vertical. Sourcing one SME contractor per priority vertical now sits above software in build priority.

**Unchanged and still blocking:** founder capacity decision, entity formation, domain and handle registration, Ghost(Pro) setup.

---

---

## 1. Legal & entity foundation

- 🔶 **Name conflict check** — informal web check done (flagged phonetic near-miss with Aechelon Technology); **formal USPTO + UK IPO trademark search not run**
- 🔶 **Logo symbol conflict check** — informal check done (Chevron Corp, Strava, Echelon Fitness/Payments/Risk+Cyber); no formal design-mark search
- ⬜ **Trademark registration** — can't file until formal search clears
- ⬜ **Business entity formation** — jurisdiction not decided (UK Ltd given your London base vs. a US entity given USD pricing and a global content/software business — possibly both eventually)
- ⬜ **Business bank account + bookkeeping setup** (Xero/QuickBooks)
- ⬜ **VAT/tax registration** (UK) and a view on US sales-tax exposure if selling software/courses to US customers
- ⬜ **Domain registration** — availability confirmed, nothing purchased yet
- ⬜ **Social handle registration** — availability confirmed (X, LinkedIn open; YouTube handle taken/dormant, needs a workaround decision), nothing claimed
- ⬜ **Website legal pages** — Terms of Service, Privacy Policy, Cookie Policy
- ⬜ **AI-disclosure policy page** — the checklist item in the Editorial Operating System needs to live as an actual published policy, not just an internal checklist, given FTC guidance and EU AI Act Article 50
- ⬜ **Contributor/writer agreement template** — revenue-share terms, IP ownership, disclosure obligations (the Business Model doc describes the terms; no actual contract drafted)
- ⬜ **GDPR compliance for subscriber data** — relevant given UK/EU base and any EU subscriber list
- ⬜ **Professional/media liability insurance** — not addressed at all yet, and it matters specifically because Tier 3 (regulated-guidance) content carries real liability exposure, not just reputational risk
- ⬜ **Legal ownership of Tier 3 risk** — who is actually liable if a compliance-guidance piece is wrong (you personally, the entity, or a named SME reviewer) — needs a real answer, not just an editorial checklist

## 2. Brand & visual identity

- ✅ Brand strategy — positioning, mission, tone, messaging pillars, taglines *(Airchelon Brand Strategy)*
- ✅ Logo direction, symbol concepts, color palette *(Airchelon Logo Brief)*
- 🔶 **Typography** — categories chosen ("editorial serif," "precision grotesk"), no specific typefaces selected/licensed
- ⬜ **Actual logo artwork** — brief exists, no designed mark yet
- ⬜ **Consolidated brand guidelines** — logo usage rules, finalized type, imagery/photography style, iconography — currently split across two docs, needs one operational reference once the mark exists
- ⬜ **Website visual design** — no UI/layout designed yet

## 3. Product & platform infrastructure

- ✅ **Publishing platform decision** — Ghost
- ✅ **Hosted vs. self-hosted decision** — Ghost(Pro) managed hosting. Resolves upgrade/security-patching overhead and includes email-sending infrastructure out of the box.
- 🔶 **Payment/subscription processing** — Ghost(Pro) has native Stripe integration for membership tiers, so this is largely solved by the platform choice; still need to connect a Stripe account and configure the actual tiers/pricing from the Business Model doc ($15/mo–$150/yr now, rising to $25/mo–$240/yr once software ships)
- 🔶 **Email infrastructure** — Ghost(Pro) handles newsletter delivery and sending natively; still need domain/DNS and sender-authentication (SPF/DKIM) setup pointed at the purchased domain
- 🔶 **Analytics/subscriber management** — Ghost's built-in member analytics covers the basics; may want to add more later, but nothing extra is required to launch
- ✅ **Theme selection** — Signal, by Enova Studio ($129 one-time, lifetime updates, Ghost 6.0+) — handles video/audio/embed/blog episode types, persistent player, transcripts, chapters, personal listening library, "listen everywhere" links, and a companion tool (Signal Tools) that auto-drafts episodes from a YouTube link, audio file, or RSS source. Still need to confirm it matches the amber/editorial visual identity once the logo is finalized — themes are typically restyleable but worth checking.
- 🔶 **Podcast RSS/distribution** — not fully confirmed whether Signal generates its own Apple/Spotify-submittable feed natively from audio hosted inside Ghost, or whether its "listen everywhere" links assume the show is already hosted externally. Worth checking Signal's actual documentation directly before assuming this is solved; if it does need external hosting, Transistor/Buzzsprout/Captivate remain the fallback
- ⬜ **Editorial review board (MVP)** — recommended in the Editorial Operating System (Notion/Airtable/GitHub Projects); not yet actually set up
- ⬜ **Agent team technical build** — the "team of agents" is conceptually assigned roles (research/draft/repurpose/disclosure-flag) in the Editorial Operating System, but there's no concrete orchestration architecture, model choice, or cost budget yet
- ⬜ **Software instruments (Phase 4)** — still fully conceptual, no build started (expected — this is a later phase, but worth tracking as a real gap, not forgetting it)

## 4. Content & editorial

- ⬜ **Zero content exists** — no essays, no podcast episodes written or recorded yet
- ⬜ **Launch content plan** — what the first essay/episode actually is, and the sequence after it
- ⬜ **Editorial calendar** — no schedule/cadence committed to
- ⬜ **Writing/citation style guide** — the review process requires every claim traceable to a source; the actual formatting/citation convention isn't specified yet
- 🔶 **Editorial risk-tiering and review process** — fully designed *(Airchelon Editorial Operating System)*; SME/compliance reviewer for Tier 3 not yet identified as an actual person

## 5. Business model & finance

- 🔶 **Pricing, phased build order, contributor comp philosophy** — designed *(Airchelon Business Model & Pricing Strategy)*; **still pending your requested update** to reflect solo-founder-plus-agents rather than a multi-writer roster
- ⬜ **Financial model** — no actual spreadsheet with costs (agent/AI infrastructure spend, tooling, contractor SME fees, your own runway/compensation) against the qualitative revenue targets already set
- ⬜ **Bootstrap vs. raise decision** — not addressed; affects timeline and how aggressively to build
- ⬜ **First consulting engagement target list** — the Business Model doc identifies consulting as the priority revenue driver, but there's no actual prospect list, sales process, or outreach plan yet

## 6. Go-to-market & growth

- ⬜ **Launch date/timeline** — nothing scheduled
- ⬜ **Initial audience strategy** — how the first readers actually arrive (personal network, guest appearances on other newsletters/podcasts, etc.)
- ⬜ **Distribution/partnership plan** — no cross-promotion or seeding strategy
- ⬜ **PR/positioning for launch** — no plan for how Airchelon gets its first real exposure

## 7. Team & operations

- ⬜ **Your own capacity plan** — is this full-time, or built alongside your current Business Change Analyst role? This decision affects every timeline above and hasn't been addressed yet
- ⬜ **SME/compliance reviewer sourcing** — Tier 3 review requires a real qualified person per regulated vertical; none identified
- 🔶 **Hiring plan for future writers** — designed *(Airchelon Editorial Operating System, Section 7)*; nothing actioned since there's no team yet, which is expected at this stage

## 8. What's genuinely solid right now

To be clear about what's *not* a gap: the strategic foundation — brand positioning, differentiation from Every, name/symbol risk awareness, pricing logic, and the editorial governance model — is unusually thorough for a pre-launch business. The gaps above are almost entirely **execution and legal-formation items**, not strategic ones. That's a good place to be, but none of it becomes a real business until the Section 1 legal items and Section 3 platform items exist.

---

## Suggested immediate priority order

1. Decide your own capacity plan (Section 7) — this determines every timeline below it
2. Formal trademark search (Section 1) — before spending more on brand execution that a conflict could force you to change
3. Entity formation + domain/handle registration (Section 1) — cheap, fast, removes risk of losing the name
4. Platform decision + MVP review board (Section 3) — the minimum infrastructure to publish anything at all
5. First piece of actual content (Section 4) — everything else is still hypothetical until something ships
