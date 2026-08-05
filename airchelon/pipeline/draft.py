"""Drafting agent — claude-opus-5, no tools. Deliberately.

Without web access the drafting agent cannot introduce a fact that isn't in
the source file, which is what makes "every claim traces to a source"
mechanically checkable. The request this module builds carries NO tools key —
not an empty list, no key at all — and the pipeline halts here: there is no
code path from this module to publication.

Usage:
    uv run python -m airchelon.pipeline.draft P-001
    uv run python -m airchelon.pipeline.draft P-001 --revision-note "Reviewer asked to ..."
"""

from __future__ import annotations

import argparse
import json
import sys

import anthropic

from .common import (
    DOCS_DIR,
    DRAFT_MODEL,
    DRAFTS_DIR,
    ESSAYS_DIR,
    PROMPTS_DIR,
    PUBLISHED_DIR,
    RESEARCH_DIR,
    extract_section,
    final_text,
    prompt_commit,
    record_run,
    require_completed,
    run_streamed,
    sha256_of,
    utc_now,
)
from .validate import validate_file

PROMPT_PATH = PROMPTS_DIR / "drafting-agent.md"
BRAND_STRATEGY_PATH = DOCS_DIR / "airchelon-brand-strategy.md"
MAX_EXEMPLARS = 3


def voice_guide() -> str:
    doc = BRAND_STRATEGY_PATH.read_text(encoding="utf-8")
    return "\n\n".join(
        extract_section(doc, heading) for heading in ("Tone of voice", "Voice sample")
    )


def exemplars() -> list[tuple[str, str]]:
    """Published pieces first; fall back to drafted essays pre-launch."""
    pool = sorted(PUBLISHED_DIR.glob("*.md")) or sorted(ESSAYS_DIR.glob("*.md"))
    return [(p.name, p.read_text(encoding="utf-8")) for p in pool[:MAX_EXEMPLARS]]


def build_request(source_file: dict, revision_note: str | None = None) -> dict:
    """The full Messages API request for a drafting run. Pure, for testability.

    The stable prefix (agent prompt, voice guide, exemplars, source file) is
    cached; revision passes re-send it at ~10% of base input cost — the
    highest-value cost lever in the agent layer spec.
    """
    exemplar_blocks = "\n\n".join(
        f'<exemplar name="{name}">\n{text}\n</exemplar>' for name, text in exemplars()
    )
    system = [
        {"type": "text", "text": PROMPT_PATH.read_text(encoding="utf-8")},
        {
            "type": "text",
            "text": (
                "## Tone of voice (from the brand strategy doc)\n\n"
                f"{voice_guide()}\n\n"
                "## Voice exemplars\n\n"
                f"{exemplar_blocks}"
            ),
            "cache_control": {"type": "ephemeral"},
        },
    ]
    user_parts = [
        "The commissioning brief:\n\n"
        f"<brief>\n{source_file['brief']}\n</brief>\n\n"
        "The verified source file. Every factual sentence in your draft must cite one "
        "of these records by ID; anything you cannot attribute goes in the NEEDS SOURCE "
        "block at the foot of the draft.\n\n"
        f"<source_file>\n{json.dumps(source_file, indent=2)}\n</source_file>",
    ]
    if revision_note:
        user_parts.append(f"Revision requested by the reviewer:\n\n{revision_note}")
    return {
        "model": DRAFT_MODEL,
        "max_tokens": 32000,
        "system": system,
        "messages": [{"role": "user", "content": "\n\n".join(user_parts)}],
    }


def run(piece_id: str, revision_note: str | None = None) -> None:
    source_path = RESEARCH_DIR / f"{piece_id}.json"
    if not source_path.exists():
        raise SystemExit(
            f"No source file at {source_path}. Run the research agent first — "
            "the drafting agent writes only from a validated source file."
        )
    source_file = validate_file(source_path)

    commit = prompt_commit(PROMPT_PATH)
    client = anthropic.Anthropic()

    request = build_request(source_file, revision_note)
    assert "tools" not in request  # load-bearing: the drafting agent gets no tools
    message = run_streamed(client, request)
    require_completed(message, "draft")

    body = final_text(message).strip()
    front_matter = "\n".join(
        [
            "---",
            f"piece_id: {piece_id}",
            "stage: draft  # NOT publishable; the pipeline halts here for human review",
            f"model_id: {DRAFT_MODEL}",
            f"prompt_commit: {commit}",
            f"source_file_sha256: {sha256_of(source_path)}",
            f"generated_at: {utc_now()}",
            "---",
        ]
    )
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    out = DRAFTS_DIR / f"{piece_id}.md"
    out.write_text(front_matter + "\n\n" + body + "\n", encoding="utf-8")
    record_run(
        piece_id,
        stage="draft" if not revision_note else "draft-revision",
        model_id=DRAFT_MODEL,
        prompt_commit_hash=commit,
        inputs={"source_file_sha256": sha256_of(source_path)},
        outputs={"draft_sha256": sha256_of(out)},
    )
    cached = message.usage.cache_read_input_tokens or 0
    print(f"Wrote {out} (cache read: {cached} tokens)")
    print("Next: run the disclosure agent, then take the piece to human review.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the Airchelon drafting agent")
    parser.add_argument("piece_id", help="Piece ID with a validated source file")
    parser.add_argument("--revision-note", help="Reviewer note for a revision pass")
    args = parser.parse_args(argv)
    run(args.piece_id, args.revision_note)


if __name__ == "__main__":
    sys.exit(main())
