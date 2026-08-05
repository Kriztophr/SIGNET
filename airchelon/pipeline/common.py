"""Shared plumbing for the Airchelon agent pipeline.

Model IDs are pinned, never floating (CLAUDE.md rule 5). A silent model
change destroys reproducibility of an audited piece, so every stage names
its model here and nowhere else.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

# Pinned per docs/airchelon-agent-layer-spec.md §2. Never use a floating alias.
RESEARCH_MODEL = "claude-sonnet-5"
DRAFT_MODEL = "claude-opus-5"
DISCLOSURE_MODEL = "claude-haiku-4-5-20251001"
REPURPOSE_MODEL = "claude-haiku-4-5-20251001"

AIRCHELON_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = AIRCHELON_ROOT / "prompts"
SCHEMAS_DIR = AIRCHELON_ROOT / "schemas"
DOCS_DIR = AIRCHELON_ROOT / "docs"
RESEARCH_DIR = AIRCHELON_ROOT / "content" / "research"
DRAFTS_DIR = AIRCHELON_ROOT / "content" / "drafts"
PUBLISHED_DIR = AIRCHELON_ROOT / "content" / "published"
ESSAYS_DIR = AIRCHELON_ROOT / "content" / "essays"
AUDIT_DIR = AIRCHELON_ROOT / "content" / "audit"


class AuditIntegrityError(RuntimeError):
    """Raised when a run cannot be tied to a clean, committed prompt."""


def prompt_commit(prompt_path: Path, repo_root: Path | None = None) -> str:
    """Return the commit hash of the prompt file as it stands right now.

    Refuses to run against an uncommitted or locally modified prompt: the
    recorded hash would then misrepresent the prompt actually used, which is
    exactly the audit failure the hash exists to prevent.
    """
    root = repo_root or AIRCHELON_ROOT
    rel = prompt_path.resolve().relative_to(_git_toplevel(root))

    dirty = _git(root, "status", "--porcelain", "--", str(rel))
    if dirty.strip():
        raise AuditIntegrityError(
            f"{rel} has uncommitted changes; commit the prompt before running the agent "
            "so the recorded prompt_commit matches what actually ran."
        )
    commit = _git(root, "log", "-1", "--format=%H", "--", str(rel)).strip()
    if not commit:
        raise AuditIntegrityError(f"{rel} is not tracked by git; commit it first.")
    return commit


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def _git_toplevel(cwd: Path) -> Path:
    return Path(_git(cwd, "rev-parse", "--show-toplevel").strip())


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def record_run(
    piece_id: str,
    stage: str,
    model_id: str,
    prompt_commit_hash: str,
    inputs: dict[str, str],
    outputs: dict[str, str],
) -> Path:
    """Append a run record to the piece's audit file (content/audit/<id>.jsonl).

    This supplements — never replaces — the review tool's named human audit
    log. It captures what docs/airchelon-agent-layer-spec.md §4 requires:
    pinned model ID, prompt commit, and the inputs as they stood at run time.
    """
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "at": utc_now(),
        "piece_id": piece_id,
        "stage": stage,
        "model_id": model_id,
        "prompt_commit": prompt_commit_hash,
        "inputs": inputs,
        "outputs": outputs,
    }
    path = AUDIT_DIR / f"{piece_id}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")
    return path


def extract_section(markdown: str, heading: str) -> str:
    """Return a markdown section from `heading` up to the next same-or-higher heading."""
    lines = markdown.splitlines()
    level = None
    start = None
    for i, line in enumerate(lines):
        if line.startswith("#") and line.lstrip("#").strip().lower() == heading.lower():
            level = len(line) - len(line.lstrip("#"))
            start = i
            break
    if start is None:
        raise ValueError(f"Heading {heading!r} not found")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        stripped = lines[j]
        if stripped.startswith("#"):
            this_level = len(stripped) - len(stripped.lstrip("#"))
            if this_level <= level:
                end = j
                break
    return "\n".join(lines[start:end]).strip()


def final_text(message) -> str:
    """Concatenate the text blocks of a Messages API response."""
    return "".join(block.text for block in message.content if block.type == "text")


def run_streamed(client, request: dict):
    """Run one Messages API call with streaming, resuming through pause_turn.

    Server tools (web search/fetch) can pause a long turn; resuming means
    re-sending with the assistant turn appended. Returns the final message.
    """
    messages = list(request["messages"])
    while True:
        with client.messages.stream(**{**request, "messages": messages}) as stream:
            message = stream.get_final_message()
        if message.stop_reason != "pause_turn":
            return message
        messages = messages + [{"role": "assistant", "content": message.content}]


def require_completed(message, stage: str) -> None:
    """Fail loudly on refusals or truncation instead of writing a bad artifact."""
    if message.stop_reason == "refusal":
        raise RuntimeError(
            f"{stage}: the model declined this request (stop_reason=refusal). "
            "Nothing was written. Raise with the founder rather than retrying blindly."
        )
    if message.stop_reason == "max_tokens":
        raise RuntimeError(
            f"{stage}: output was truncated at max_tokens. Nothing was written; "
            "re-run with a higher limit."
        )
