# /// script
# requires-python = ">=3.12"
# dependencies = ["anthropic>=0.116.0", "jsonschema>=4.23"]
# ///
"""Run the Airchelon drafting agent.

Writes a draft from the source file and nothing else — the agent gets NO tools,
deliberately (docs/airchelon-agent-layer-spec.md section 2.2): without web access
it cannot introduce a fact that isn't already in the source file, which is what
makes "every claim traces to a source" mechanically checkable.

Usage:
    uv run airchelon/pipeline/run_draft.py --piece-id 02-slug --brief "..."
    uv run airchelon/pipeline/run_draft.py --piece-id 02-slug --brief-file brief.md \
        --exemplar content/essays/01-the-first-thing-we-governed.md
    # revision pass (reuses the cached voice guide + source file):
    uv run airchelon/pipeline/run_draft.py --piece-id 02-slug --brief "..." \
        --revise --notes "Reviewer notes: tighten section 2, cut the third metaphor."

Output goes to content/drafts/<piece-id>.md — never to content/essays/, which is
for pieces that have cleared the review gate. There is no code path from this
script to publication.
"""

import argparse
import re
from pathlib import Path

import common


def voice_guide() -> str:
    """The tone-of-voice section of the brand strategy doc (incl. the voice sample)."""
    text = (common.DOCS_DIR / "airchelon-brand-strategy.md").read_text()
    match = re.search(r"^### Tone of voice$(.*?)(?=^## )", text, re.MULTILINE | re.DOTALL)
    if not match:
        common.die("could not find '### Tone of voice' in docs/airchelon-brand-strategy.md")
    return "### Tone of voice" + match.group(1)


def build_system(source_json: str, exemplars: list[Path]) -> list[dict]:
    prompt = (common.PROMPTS_DIR / "drafting-agent.md").read_text()
    blocks = [
        {"type": "text", "text": prompt},
        {"type": "text", "text": "## Brand voice guide\n\n" + voice_guide()},
    ]
    if exemplars:
        joined = "\n\n---\n\n".join(f"### Exemplar: {p.name}\n\n{p.read_text()}" for p in exemplars)
        blocks.append(
            {"type": "text", "text": "## Voice exemplars (published pieces)\n\n" + joined}
        )
    blocks.append(
        {
            "type": "text",
            "text": "## Source file (the only permitted factual basis for the draft)\n\n"
            + source_json,
            # Cost lever 1 in the spec: the voice guide, exemplars, and source file
            # are re-sent on every revision pass — cache the whole static prefix.
            "cache_control": {"type": "ephemeral"},
        }
    )
    return blocks


def check_citations(draft: str, source_json: str) -> list[str]:
    import json

    sources = {s["id"]: s for s in json.loads(source_json)["sources"]}
    body = draft.split("NEEDS SOURCE")[0]
    warnings = []
    cited = set(re.findall(r"\[(S-\d{3})\]", body))
    for sid in sorted(cited):
        if sid not in sources:
            warnings.append(f"body cites {sid}, which does not exist in the source file")
        elif sources[sid]["confidence"] == "unsourced":
            warnings.append(f"body cites {sid}, which is marked unsourced — rule violation")
    if not cited:
        warnings.append("draft body contains no [S-xxx] citations at all")
    return warnings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--piece-id", required=True)
    parser.add_argument("--brief", help="Piece brief text")
    parser.add_argument("--brief-file", type=Path)
    parser.add_argument(
        "--source", type=Path, help="Source file (default content/research/<id>.json)"
    )
    parser.add_argument(
        "--exemplar",
        type=Path,
        action="append",
        default=[],
        help="Published piece to use as a voice exemplar (repeatable, 2-3 recommended)",
    )
    parser.add_argument("--revise", action="store_true", help="Revision pass on the existing draft")
    parser.add_argument("--notes", help="Reviewer notes for a revision pass")
    parser.add_argument("--out", type=Path, help="Output path (default content/drafts/<id>.md)")
    args = parser.parse_args()

    brief = args.brief or (args.brief_file.read_text().strip() if args.brief_file else None)
    if not brief:
        common.die("provide --brief or --brief-file")

    source_path = args.source or (common.RESEARCH_DIR / f"{args.piece_id}.json")
    if not source_path.exists():
        common.die(f"{source_path} not found — run run_research.py first")
    source_json = source_path.read_text()

    import json

    errors = common.validate_source_file(json.loads(source_json))
    if errors:
        for e in errors:
            print(f"invalid: {e}")
        common.die("source file fails schema validation; fix it before drafting")

    out = args.out or (common.DRAFTS_DIR / f"{args.piece_id}.md")

    user_parts = [f"Piece ID: {args.piece_id}", f"Piece brief:\n{brief}"]
    if args.revise:
        if not out.exists():
            common.die(f"--revise given but {out} does not exist")
        user_parts.append("This is a revision pass. The current draft:\n\n" + out.read_text())
        if args.notes:
            user_parts.append("Reviewer notes to address:\n" + args.notes)
        user_parts.append(
            "Revise the draft accordingly. Return the complete revised draft in Markdown, "
            "keeping inline [S-xxx] citations and the NEEDS SOURCE block."
        )
    else:
        user_parts.append(
            "Write the draft now. Return Markdown only: the draft with inline [S-xxx] "
            "citations, then the NEEDS SOURCE block (write 'NEEDS SOURCE: none' if empty)."
        )
    if not args.exemplar:
        user_parts.append("No published voice exemplars exist yet — rely on the voice guide alone.")

    commit = common.prompt_commit(common.PROMPTS_DIR / "drafting-agent.md")
    c = common.client()
    print(f"drafting agent: {'revision' if args.revise else 'first'} pass ({common.DRAFT_MODEL})…")
    with c.messages.stream(
        model=common.DRAFT_MODEL,
        max_tokens=32000,
        system=build_system(source_json, args.exemplar),
        # No `tools` parameter. Ever. See the module docstring.
        messages=[{"role": "user", "content": "\n\n".join(user_parts)}],
    ) as stream:
        msg = stream.get_final_message()
    common.check_refusal(msg)

    usage = msg.usage
    if usage.cache_read_input_tokens:
        print(f"drafting agent: cache hit ({usage.cache_read_input_tokens} tokens read)")

    draft = common.final_text(msg).strip() + "\n"
    header = (
        f"<!-- airchelon draft — piece {args.piece_id} | model {common.DRAFT_MODEL} | "
        f"prompt {commit[:12]} | source sha256 {common.sha256_file(source_path)[:16]} | "
        f"{common.now_iso()} -->\n\n"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(header + draft)
    print(f"wrote {out}")

    for w in check_citations(draft, source_json):
        print(f"  warning: {w}")

    common.emit_provenance(
        "draft",
        {
            "model_id": common.DRAFT_MODEL,
            "prompt_commit": commit,
            "draft_file": str(out.relative_to(common.AIRCHELON_ROOT)),
            "source_file_sha256": common.sha256_file(source_path),
            "generated_at": common.now_iso(),
        },
    )


if __name__ == "__main__":
    main()
