# Module 6 — Agents on the inside

**Core question:** how do you let a model do the work without losing the ability to stop it?

**Time:** ~90 minutes · **Roles used:** operator · **Needs:** an LLM provider configured (any OpenAI-compatible endpoint or Anthropic key — see `docs/deployment.md`; a free OpenRouter model is fine for the lab)

## Objectives

1. Configure an automated stage and watch an agent produce contract-conformant deliverables through the *same* gates humans face.
2. Demonstrate the three containment mechanisms: gates, budget cap, kill switch.
3. Force a failure and explain degrade-to-human behavior from the evidence it leaves.

## Concepts

### Agents get no special doors

A stage marked `automated` is executed by an LLM worker that receives exactly the ICM layers a human would (identity, routing, contract, handoffs — straight from the manifest) and must return artifacts for exactly the contract's required roles, in a delimited envelope the platform parses **fail-closed**: missing roles mean the output is not accepted at all. Accepted artifacts are recorded as agent-authored (`ActorType.agent`) — provenance is permanent. Then the stage completes through the normal coordinator, meaning **review and eval gates apply to agent work identically**. The agent can never advance past a gate, because gate logic never learns who did the work.

### Three containments

- **Budget:** every model call is priced into a usage ledger; a monthly hard cap fails closed *before* the call is made. Unknown models bill at a punitive fallback price — being unpriced is expensive by design, so nobody sneaks in an unbudgeted model.
- **Kill switch:** an operator can cancel a run at any moment; open stages fail with "run cancelled by operator" and late-arriving worker results no-op. Cancellation is a first-class recorded action.
- **Degrade to human:** *any* execution failure — provider down, unparseable output, budget exceeded — leaves the stage `running` with an `error_summary`, ready for manual completion. The run never dies from automation failure; automation failure means a human does that stage.

### A real war story (read before the lab)

The first production automated stage on this platform failed because the open model labelled its output block with a filename (`memo.md`) instead of the required role (`memo`), and dropped its closing delimiter. Degrade-to-human caught it; the parser was then hardened (filename aliases, tolerant final-block closing). Moral: format drift is not an edge case with open models — it is Tuesday. Build for it.

## Lab

1. **Automate one stage.** Create a blueprint version where the drafting stage is `automated`, with a review gate after it. Start a run and watch: the agent submits its artifacts, the run pauses at *your* gate. Review the agent's work as a human (module 4 skills) — approve or edit honestly.
2. **Read the ledger.** `GET` the LLM usage records (or inspect `llm_usage` rows): find your run's tokens and cost. If you configured a free model with an explicit zero price, the cost is $0.000000 — and *that fact is recorded*, which is the point.
3. **Force a graceful failure.** Break the executor on purpose — point `ICM_LLM_EXECUTOR_BASE_URL` at a wrong URL, or use a model name the provider doesn't serve — and run again. Confirm: stage still `running`, `error_summary` states the failure, console offers manual completion. Complete the stage by hand. The run finishes despite the automation dying.
4. **Pull the kill switch.** Start one more run and cancel it mid-flight (Cancel run, operator-only). Find the cancellation in the audit trail and the stage failure reasons.
5. **Deliverable:** three run screenshots/exports — agent-authored artifacts held at a gate; the degraded run's error summary plus your manual completion; the cancelled run — with two sentences each on which containment fired.

## Knowledge check

1. Why is "leave the stage open with the error written on it" safer than *retrying automatically until success*? Name the failure class silent retries hide.
2. The budget check runs *before* the model call rather than after. What does ordering buy, concretely?
3. An agent's artifact was edited by a reviewer before approval. What does the provenance chain show, and why do both attributions matter in module 8's evidence pack?

## Reading

- `docs/deployment.md` — "Agent execution (LLM)" and "Open-source / non-Anthropic models" sections (env vars, pricing config, failure philosophy).
- `docs/test-catalog.md`, agent execution section — the tested containment promises.
