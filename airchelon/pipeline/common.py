"""Shared plumbing for the Airchelon agent pipeline.

Governance rules enforced here, per docs/airchelon-agent-layer-spec.md:

- Model IDs are pinned constants, never floating aliases. A silent model change
  destroys the reproducibility of an audited piece.
- Every run captures the git commit hash of the prompt file it used, and emits a
  provenance block the review tool can import into a piece's audit trail.
- There is no code path from any of these scripts to publication. Scripts read
  and write local files under content/ only.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import anthropic
import jsonschema

# Pinned model IDs — spec section 2. Never replace with a floating alias.
RESEARCH_MODEL = "claude-sonnet-5"
DRAFT_MODEL = "claude-opus-5"
DISCLOSURE_MODEL = "claude-haiku-4-5-20251001"

AIRCHELON_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = AIRCHELON_ROOT / "prompts"
SCHEMAS_DIR = AIRCHELON_ROOT / "schemas"
DOCS_DIR = AIRCHELON_ROOT / "docs"
RESEARCH_DIR = AIRCHELON_ROOT / "content" / "research"
DRAFTS_DIR = AIRCHELON_ROOT / "content" / "drafts"
ESSAYS_DIR = AIRCHELON_ROOT / "content" / "essays"


def load_env() -> None:
    """Load ANTHROPIC_API_KEY (and friends) from airchelon/.env if not already set."""
    env_file = AIRCHELON_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        os.environ.setdefault(key, value)


def client() -> anthropic.Anthropic:
    load_env()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        die(
            "ANTHROPIC_API_KEY is not set. Export it, or put it in airchelon/.env "
            "(gitignored). Set a spend limit in the Console before first use — "
            "see docs/airchelon-agent-layer-spec.md section 3."
        )
    return anthropic.Anthropic()


def die(message: str) -> "None":
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def prompt_commit(prompt_file: Path) -> str:
    """Git commit hash of a prompt file at run time — an audit artifact.

    Refuses to run against a dirty prompt file: an uncommitted prompt edit would
    make the recorded hash a lie.
    """
    rel = prompt_file.relative_to(AIRCHELON_ROOT)

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=AIRCHELON_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    try:
        dirty = git("status", "--porcelain", "--", str(rel))
        if dirty:
            die(
                f"{rel} has uncommitted changes. Commit the prompt before running the "
                "agent — the recorded prompt_commit must describe the prompt that "
                "actually ran."
            )
        commit = git("log", "-n", "1", "--format=%H", "--", str(rel))
        if not commit:
            die(f"{rel} has no git history. Commit it first.")
        return commit
    except subprocess.CalledProcessError as exc:
        die(f"git failed while capturing the prompt commit: {exc.stderr or exc}")
        raise  # unreachable; keeps type-checkers happy


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_schema() -> dict:
    return json.loads((SCHEMAS_DIR / "source-file.schema.json").read_text())


def validate_source_file(data: dict) -> list[str]:
    """Validate a research source file against the schema. Returns error strings."""
    validator = jsonschema.Draft202012Validator(load_schema())
    errors = []
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
        where = "/".join(str(p) for p in err.absolute_path) or "(root)"
        errors.append(f"{where}: {err.message}")
    # Schema can't express the pairing rule in both directions cheaply; check it here.
    ids = {s.get("id") for s in data.get("sources", [])}
    for s in data.get("sources", []):
        pair = s.get("contested_pair")
        if s.get("confidence") == "contested" and pair not in ids:
            errors.append(
                f"sources/{s.get('id')}: contested_pair {pair!r} does not name another record"
            )
    return errors


def extract_json(text: str) -> dict:
    """Pull a JSON object out of model output, tolerating code fences and preambles."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("model output contains no JSON object")
        text = text[start : end + 1]
    return json.loads(text)


def final_text(message: anthropic.types.Message) -> str:
    return "".join(block.text for block in message.content if block.type == "text")


def emit_provenance(stage: str, record: dict) -> None:
    """Print the provenance block the review tool's Provenance section imports."""
    block = {"airchelon_provenance": {stage: record}}
    print("\n--- provenance block (paste into the review tool) ---")
    print(json.dumps(block, indent=2))
    print("--- end provenance block ---")


def check_refusal(message: anthropic.types.Message) -> None:
    if message.stop_reason == "refusal":
        details = getattr(message, "stop_details", None)
        die(f"the model declined this request (refusal{f': {details}' if details else ''}).")
    if message.stop_reason == "max_tokens":
        die("output was truncated at max_tokens — re-run with a smaller brief or raise the cap.")
