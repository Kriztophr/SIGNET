# /// script
# requires-python = ">=3.12"
# dependencies = ["anthropic>=0.116.0", "jsonschema>=4.23"]
# ///
"""Run the Airchelon disclosure-flagging agent.

Inspects a draft against the source file and reports flags — it never edits the
draft, and it may propose tier ESCALATION only (docs/airchelon-agent-layer-spec.md
section 2.3). Run it on every draft before human review.

Usage:
    uv run airchelon/pipeline/run_disclosure.py --piece-id 02-slug --tier 2

Reads content/drafts/<piece-id>.md and content/research/<piece-id>.json, writes
the flag list to content/drafts/<piece-id>.flags.txt. The human reviewer decides
what to do with each flag and records a reason for any flag they override.
"""

import argparse
from pathlib import Path

import common


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--piece-id", required=True)
    parser.add_argument(
        "--tier", type=int, choices=(1, 2, 3), required=True, help="Currently assigned risk tier"
    )
    parser.add_argument("--draft", type=Path, help="Draft path (default content/drafts/<id>.md)")
    parser.add_argument(
        "--source", type=Path, help="Source file (default content/research/<id>.json)"
    )
    parser.add_argument("--out", type=Path, help="Output (default content/drafts/<id>.flags.txt)")
    args = parser.parse_args()

    draft_path = args.draft or (common.DRAFTS_DIR / f"{args.piece_id}.md")
    source_path = args.source or (common.RESEARCH_DIR / f"{args.piece_id}.json")
    if not draft_path.exists():
        common.die(f"{draft_path} not found — run run_draft.py first")
    if not source_path.exists():
        common.die(f"{source_path} not found — the source-integrity check needs it")

    commit = common.prompt_commit(common.PROMPTS_DIR / "disclosure-agent.md")
    system = (common.PROMPTS_DIR / "disclosure-agent.md").read_text()
    user = (
        f"Piece ID: {args.piece_id}\n"
        f"Currently assigned risk tier: {args.tier}\n\n"
        "## Source file\n\n"
        f"{source_path.read_text()}\n\n"
        "## Draft\n\n"
        f"{draft_path.read_text()}\n\n"
        "Run all four checks and report in the exact output format from your "
        "instructions. Remember: you may propose escalation only, never a lower tier."
    )

    c = common.client()
    print(f"disclosure agent: checking draft ({common.DISCLOSURE_MODEL})…")
    msg = c.messages.create(
        model=common.DISCLOSURE_MODEL,
        max_tokens=4000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    common.check_refusal(msg)
    flags = common.final_text(msg).strip()

    generated_at = common.now_iso()
    out = args.out or (common.DRAFTS_DIR / f"{args.piece_id}.flags.txt")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        f"Airchelon disclosure agent — piece {args.piece_id}\n"
        f"model {common.DISCLOSURE_MODEL} | prompt {commit[:12]} | {generated_at}\n"
        f"assigned tier at run time: {args.tier}\n" + "-" * 60 + "\n" + flags + "\n"
    )
    print(f"wrote {out}\n")
    print(flags)

    common.emit_provenance(
        "disclosure",
        {
            "model_id": common.DISCLOSURE_MODEL,
            "prompt_commit": commit,
            "flags_file": str(out.relative_to(common.AIRCHELON_ROOT)),
            "generated_at": generated_at,
        },
    )


if __name__ == "__main__":
    main()
