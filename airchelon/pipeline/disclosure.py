"""Disclosure-flagging agent — claude-haiku-4-5-20251001.

Runs on the draft before human review. Output is a flag list, never an edit —
this module does not touch the draft file, and the prompt permits tier
escalation proposals only. The flag list is part of the piece's audit trail:
an overridden flag with a recorded reason is a defensible judgement.

Usage:
    uv run python -m airchelon.pipeline.disclosure P-001
"""

from __future__ import annotations

import argparse
import json
import sys

import anthropic

from .common import (
    DISCLOSURE_MODEL,
    DRAFTS_DIR,
    PROMPTS_DIR,
    RESEARCH_DIR,
    final_text,
    prompt_commit,
    record_run,
    require_completed,
    run_streamed,
    sha256_of,
    utc_now,
)
from .validate import validate_file

PROMPT_PATH = PROMPTS_DIR / "disclosure-agent.md"


def build_request(draft_text: str, source_file: dict) -> dict:
    """The full Messages API request for a disclosure run. Pure, for testability."""
    user = (
        "The draft to inspect:\n\n"
        f"<draft>\n{draft_text}\n</draft>\n\n"
        "The source file its citations must resolve against:\n\n"
        f"<source_file>\n{json.dumps(source_file, indent=2)}\n</source_file>\n\n"
        "Run all four checks and reply in the exact output format from your instructions."
    )
    return {
        "model": DISCLOSURE_MODEL,
        "max_tokens": 4000,
        "system": PROMPT_PATH.read_text(encoding="utf-8"),
        "messages": [{"role": "user", "content": user}],
    }


def run(piece_id: str) -> None:
    draft_path = DRAFTS_DIR / f"{piece_id}.md"
    source_path = RESEARCH_DIR / f"{piece_id}.json"
    if not draft_path.exists():
        raise SystemExit(f"No draft at {draft_path}. Run the drafting agent first.")
    source_file = validate_file(source_path)

    commit = prompt_commit(PROMPT_PATH)
    client = anthropic.Anthropic()

    request = build_request(draft_path.read_text(encoding="utf-8"), source_file)
    message = run_streamed(client, request)
    require_completed(message, "disclosure")

    flags = final_text(message).strip()
    header = "\n".join(
        [
            f"# Disclosure flags — {piece_id}",
            f"# model_id: {DISCLOSURE_MODEL}",
            f"# prompt_commit: {commit}",
            f"# draft_sha256: {sha256_of(draft_path)}",
            f"# generated_at: {utc_now()}",
            "# The human reviewer records a reason for any flag they override.",
        ]
    )
    out = DRAFTS_DIR / f"{piece_id}.flags.txt"
    out.write_text(header + "\n\n" + flags + "\n", encoding="utf-8")
    record_run(
        piece_id,
        stage="disclosure",
        model_id=DISCLOSURE_MODEL,
        prompt_commit_hash=commit,
        inputs={"draft_sha256": sha256_of(draft_path)},
        outputs={"flags_sha256": sha256_of(out)},
    )
    print(f"Wrote {out}")
    print("The piece is ready for the human review gate in the review tool.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the Airchelon disclosure-flagging agent")
    parser.add_argument("piece_id", help="Piece ID with a draft in content/drafts/")
    args = parser.parse_args(argv)
    run(args.piece_id)


if __name__ == "__main__":
    sys.exit(main())
