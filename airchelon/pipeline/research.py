"""Research agent — claude-sonnet-5 with web search and web fetch.

Output is a JSON source file validated against schemas/source-file.schema.json
and written to content/research/<piece-id>.json. The script — not the model —
stamps piece_id, brief, generated_at, and the agent provenance block, so the
audit fields are authoritative rather than self-reported.

Usage:
    uv run python -m airchelon.pipeline.research P-001 --brief "What the piece must establish"
    uv run python -m airchelon.pipeline.research P-001 --brief-file briefs/p-001.md
"""

from __future__ import annotations

import argparse
import json
import sys

import anthropic

from .common import (
    PROMPTS_DIR,
    RESEARCH_DIR,
    RESEARCH_MODEL,
    final_text,
    prompt_commit,
    record_run,
    require_completed,
    run_streamed,
    sha256_of,
    utc_now,
)
from .validate import SCHEMA_PATH, validation_errors

PROMPT_PATH = PROMPTS_DIR / "research-agent.md"


def build_request(brief: str) -> dict:
    """The full Messages API request for a research run. Pure, for testability."""
    schema_text = SCHEMA_PATH.read_text(encoding="utf-8")
    system = PROMPT_PATH.read_text(encoding="utf-8")
    user = (
        "Commissioning brief for the piece you are researching:\n\n"
        f"<brief>\n{brief}\n</brief>\n\n"
        "Assemble the source file now. Your entire reply must be a single JSON object "
        'with one key, "sources", whose value is the array of source records — '
        "no prose, no markdown fences. Each record must satisfy this contract:\n\n"
        f"<schema>\n{schema_text}\n</schema>\n\n"
        "The wrapper fields (piece_id, brief, generated_at, agent) are stamped by the "
        "pipeline, not by you. Number records S-001 upward."
    )
    return {
        "model": RESEARCH_MODEL,
        "max_tokens": 16000,
        "system": system,
        "tools": [
            {"type": "web_search_20260209", "name": "web_search", "max_uses": 20},
            {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 30},
        ],
        "messages": [{"role": "user", "content": user}],
    }


def parse_sources(text: str) -> list[dict]:
    """Extract the sources array from the model's JSON-only reply."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("Research agent reply contained no JSON object") from None
        data = json.loads(cleaned[start : end + 1])
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("sources"), list):
        return data["sources"]
    raise ValueError("Research agent reply was JSON but carried no sources array")


def run(piece_id: str, brief: str) -> None:
    commit = prompt_commit(PROMPT_PATH)
    client = anthropic.Anthropic()

    request = build_request(brief)
    message = run_streamed(client, request)
    require_completed(message, "research")

    source_file = {
        "piece_id": piece_id,
        "brief": brief,
        "generated_at": utc_now(),
        "agent": {"model_id": RESEARCH_MODEL, "prompt_commit": commit},
        "sources": parse_sources(final_text(message)),
    }

    errors = validation_errors(source_file)
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    if errors:
        reject = RESEARCH_DIR / f"{piece_id}.invalid.json"
        reject.write_text(json.dumps(source_file, indent=2) + "\n", encoding="utf-8")
        listing = "\n  - ".join(errors)
        raise SystemExit(
            f"Research output failed schema validation (written to {reject} for "
            f"inspection, NOT usable by the drafting agent):\n  - {listing}"
        )

    out = RESEARCH_DIR / f"{piece_id}.json"
    out.write_text(json.dumps(source_file, indent=2) + "\n", encoding="utf-8")
    record_run(
        piece_id,
        stage="research",
        model_id=RESEARCH_MODEL,
        prompt_commit_hash=commit,
        inputs={"brief_sha256": _sha_text(brief)},
        outputs={"source_file": str(out.relative_to(out.parents[3])), "sha256": sha256_of(out)},
    )
    unsourced = sum(1 for s in source_file["sources"] if s["confidence"] == "unsourced")
    print(f"Wrote {out} ({len(source_file['sources'])} records, {unsourced} unsourced)")


def _sha_text(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the Airchelon research agent")
    parser.add_argument("piece_id", help="Piece ID, matching the review tool")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--brief", help="Commissioning brief text")
    group.add_argument("--brief-file", help="Path to a file containing the brief")
    args = parser.parse_args(argv)

    brief = args.brief
    if args.brief_file:
        from pathlib import Path

        brief = Path(args.brief_file).read_text(encoding="utf-8").strip()
    run(args.piece_id, brief)


if __name__ == "__main__":
    sys.exit(main())
