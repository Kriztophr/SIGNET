"""Repurposing agent — claude-haiku-4-5-20251001, via the Batch API.

Reads published pieces only, never drafts. The gate is structural: the input
must live under content/published/, the directory a human moves a piece into
only after it clears stage 8 in the review tool. A path anywhere else —
including content/drafts/ — is refused before any API call is made. If the
repurposing agent could read drafts, unreviewed material could reach social
channels ahead of the review gate, and the pipeline would stop meaning
anything.

Usage:
    uv run python -m airchelon.pipeline.repurpose airchelon/content/published/01-....md
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import anthropic

from .common import (
    PROMPTS_DIR,
    PUBLISHED_DIR,
    REPURPOSE_MODEL,
    prompt_commit,
    record_run,
    sha256_of,
    utc_now,
)

PROMPT_PATH = PROMPTS_DIR / "repurposing-agent.md"


class NotPublishedError(RuntimeError):
    """The input is not a published piece; the repurposing agent refuses it."""


def assert_published(path: Path) -> Path:
    """Refuse any input that does not live under content/published/."""
    resolved = path.resolve()
    published_root = PUBLISHED_DIR.resolve()
    if not resolved.is_file():
        raise NotPublishedError(f"{path} is not a file.")
    if published_root not in resolved.parents:
        raise NotPublishedError(
            f"{path} is not under {published_root}. The repurposing agent reads "
            "published pieces only — a piece is published when a named human has "
            "cleared it through stage 8 in the review tool and moved it here. "
            "This is a governance rule, not a convenience check."
        )
    return resolved


def build_batch_request(published_text: str, custom_id: str) -> dict:
    """One Batch API request entry for a published piece. Pure, for testability."""
    user = (
        "The published piece to repurpose:\n\n"
        f"<published_piece>\n{published_text}\n</published_piece>\n\n"
        "Produce the outputs listed in your instructions: one long-form post, three "
        "short posts each built on a different specific detail, and a 2–3 sentence "
        "newsletter blurb. Carry the piece's provenance line on each output. Use "
        "markdown headings to separate the outputs."
    )
    return {
        "custom_id": custom_id,
        "params": {
            "model": REPURPOSE_MODEL,
            "max_tokens": 4000,
            "system": PROMPT_PATH.read_text(encoding="utf-8"),
            "messages": [{"role": "user", "content": user}],
        },
    }


def run(piece_path: Path, poll_seconds: int = 30) -> None:
    resolved = assert_published(piece_path)
    commit = prompt_commit(PROMPT_PATH)
    client = anthropic.Anthropic()

    custom_id = resolved.stem[:64]
    batch = client.messages.batches.create(
        requests=[build_batch_request(resolved.read_text(encoding="utf-8"), custom_id)]
    )
    print(f"Submitted batch {batch.id}; polling every {poll_seconds}s (batch pricing, not urgent)")

    while True:
        batch = client.messages.batches.retrieve(batch.id)
        if batch.processing_status == "ended":
            break
        time.sleep(poll_seconds)

    for result in client.messages.batches.results(batch.id):
        if result.custom_id != custom_id:
            continue
        if result.result.type != "succeeded":
            outcome = result.result.type
            raise SystemExit(f"Batch request {custom_id} ended as {outcome}; not retried.")
        message = result.result.message
        text = "".join(b.text for b in message.content if b.type == "text").strip()

        header = "\n".join(
            [
                f"# Derivatives — {resolved.name}",
                f"# model_id: {REPURPOSE_MODEL}",
                f"# prompt_commit: {commit}",
                f"# published_sha256: {sha256_of(resolved)}",
                f"# batch_id: {batch.id}",
                f"# generated_at: {utc_now()}",
            ]
        )
        out = resolved.with_suffix(".derivatives.md")
        out.write_text(header + "\n\n" + text + "\n", encoding="utf-8")
        record_run(
            resolved.stem,
            stage="repurpose",
            model_id=REPURPOSE_MODEL,
            prompt_commit_hash=commit,
            inputs={"published_sha256": sha256_of(resolved), "batch_id": batch.id},
            outputs={"derivatives_sha256": sha256_of(out)},
        )
        print(f"Wrote {out}")
        return
    raise SystemExit("Batch ended but carried no result for this piece.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the Airchelon repurposing agent")
    parser.add_argument("published_piece", help="Path to a piece under content/published/")
    args = parser.parse_args(argv)
    run(Path(args.published_piece))


if __name__ == "__main__":
    sys.exit(main())
