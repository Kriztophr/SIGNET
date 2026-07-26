# Module 2 — Legible context: the ICM methodology

**Core question:** what does an agent actually know when it acts — and can you prove it?

**Time:** ~75 minutes · **Roles used:** operator (or any role for the read-only parts)

## Objectives

1. Explain the five ICM context layers and what each one is *for*.
2. Read a stage's context manifest in the run inspector and say exactly what the agent (or human) was given.
3. Explain why content references and hashes make context auditable, and what a stage contract is.

## Concepts

### The problem with prompts

An unstructured prompt is an unbounded, unversioned blob. When output goes wrong you cannot answer the first forensic question — *what did the model know?* — because "the prompt" was assembled ad hoc and never recorded as parts.

### The five layers

The Interpretable Context Methodology (ICM, from `docs/icm-paper.md`) splits every stage's context into five named layers:

| Layer | Name | Plain meaning | Changes… |
|-------|------|--------------|----------|
| 0 | Identity | Who the worker is: persona, operating principles, voice | almost never |
| 1 | Routing | The stage map: what stage this is, what comes next | per workflow design |
| 2 | Stage contract | What THIS stage must produce, and what "done" means | per stage |
| 3 | Reference material | Domain sources the work should draw on | per environment |
| 4 | Working artifacts | The previous stage's handoff — actual upstream deliverables | every run |

Two design consequences matter. **Separation of change rates:** identity is stable while artifacts churn every run, so a diff of any layer is meaningful. **Enumerability:** because the layers are named and finite, the platform can record a **context manifest** per stage — content references for layers 0–2 and the concrete artifact list for layer 4, plus a token estimate. That manifest is the forensic answer: *this is what the worker was given, verifiably.*

### Stage contracts

A stage contract is a short markdown document (parsed fail-closed — a malformed contract refuses to run rather than running vaguely) that declares the stage's required deliverable roles and success criteria. Contracts are what make "review" meaningful: the reviewer checks work *against a written promise*, not against vibes. Contract content is hashed, so the evidence pack later proves which version of the promise applied.

### Handoffs

Layer 4 is filled automatically: the latest artifact per role from the previous stage becomes the next stage's inputs. Handoff is a data rule, not a hope that someone pastes the right text.

## Lab

1. **Read the source methodology.** Skim `docs/icm-paper.md` (the five-layer template) and `docs/examples/icm-workflow/` (the on-disk workspace shape Signet materializes). Map each directory/file you see to one of the five layers.
2. **Inspect a real manifest.** Open a run in the console (seed a scenario pack run if needed), select a stage, and find the "Task Context & Attachments" card. Identify: the layer 0/1/2 content references, the layer 4 handoff list (empty means first stage), and the token estimate.
3. **Prove the handoff rule.** Submit an artifact with role `scope_brief` on stage 1, complete the stage, then open stage 2's manifest and confirm `scope_brief` appears as a handoff input — without anyone copying anything.
4. **Deliverable — annotated manifest (½–1 page).** Screenshot or transcribe one stage's manifest and annotate every line: what layer it is, what question it answers in an audit, and what would break (forensically, not functionally) if that line were missing.

## Knowledge check

1. Your agent produced a memo citing a source that isn't in the reference bundle. Which layer's manifest entry do you check first, and what are the two possible explanations?
2. Why does the platform *refuse to run* a stage with a malformed contract instead of running it "best effort"? Connect this to module 1's fail-open discussion.
3. Layer 0 changes once a quarter; layer 4 changes every run. Why is keeping them separate more auditable than one combined prompt with the same total content?

## Reading

- `docs/icm-paper.md` — full methodology, including the handoff protocol and output discipline sections.
- `docs/examples/icm-workflow/` — the reference workspace layout.
