"""Airchelon agent pipeline.

Four prompts, run in a fixed order, calling the Messages API directly.
No orchestration framework — see docs/airchelon-agent-layer-spec.md.

The one hard architectural rule: the pipeline halts at draft. There is no
code path from the drafting agent to publication.
"""
