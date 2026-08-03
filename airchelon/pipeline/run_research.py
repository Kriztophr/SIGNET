# /// script
# requires-python = ">=3.12"
# dependencies = ["anthropic>=0.116.0", "jsonschema>=4.23"]
# ///
"""Run the Airchelon research agent.

Assembles a verified source file for a commissioned piece, validates it against
schemas/source-file.schema.json, and writes it to content/research/<piece-id>.json.

Usage:
    uv run airchelon/pipeline/run_research.py --piece-id 02-slug --brief "One-line brief"
    uv run airchelon/pipeline/run_research.py --piece-id 02-slug --brief-file brief.md
    uv run airchelon/pipeline/run_research.py --validate content/research/02-slug.json

Model is pinned (claude-sonnet-5). Tools: web search + web fetch, capped by
--max-searches (default 15, per the cost budget in the agent layer spec).
"""

import argparse
import json
from pathlib import Path

import common

MAX_TURNS = 6  # pause_turn resumptions; a runaway loop is a bug, not a budget item


def build_tools(max_searches: int) -> list[dict]:
    return [
        {"type": "web_search_20260209", "name": "web_search", "max_uses": max_searches},
        {"type": "web_fetch_20260209", "name": "web_fetch"},
    ]


def user_prompt(piece_id: str, brief: str) -> str:
    schema = (common.SCHEMAS_DIR / "source-file.schema.json").read_text()
    return (
        f"Piece ID: {piece_id}\n\n"
        f"Commissioning brief:\n{brief}\n\n"
        "Assemble the source file for this piece. Your entire final answer must be a "
        "single JSON object validating against this schema — no prose before or after "
        "it:\n\n"
        f"{schema}\n\n"
        "Leave the `agent` object out; the pipeline records it. Set `piece_id` and "
        "`brief` to the values above."
    )


def run_agent(piece_id: str, brief: str, max_searches: int) -> dict:
    c = common.client()
    system = (common.PROMPTS_DIR / "research-agent.md").read_text()
    tools = build_tools(max_searches)
    messages: list[dict] = [{"role": "user", "content": user_prompt(piece_id, brief)}]

    msg = None
    for turn in range(1, MAX_TURNS + 1):
        print(f"research agent: turn {turn} ({common.RESEARCH_MODEL})…")
        with c.messages.stream(
            model=common.RESEARCH_MODEL,
            max_tokens=32000,
            system=system,
            tools=tools,
            messages=messages,
        ) as stream:
            msg = stream.get_final_message()
        if msg.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": msg.content})
            continue
        break
    common.check_refusal(msg)

    searches = sum(
        1
        for b in msg.content
        if b.type == "server_tool_use" and b.name in ("web_search", "web_fetch")
    )
    print(f"research agent: done ({searches} tool calls in final turn)")
    data = common.extract_json(common.final_text(msg))

    errors = common.validate_source_file({**data, "agent": {"model_id": "x", "prompt_commit": "x"}})
    if errors:
        print(f"research agent: output failed validation ({len(errors)} errors), repairing…")
        messages.append({"role": "assistant", "content": msg.content})
        messages.append(
            {
                "role": "user",
                "content": (
                    "Your source file failed schema validation. Fix these errors and "
                    "return the complete corrected JSON object, nothing else:\n"
                    + "\n".join(f"- {e}" for e in errors)
                ),
            }
        )
        with c.messages.stream(
            model=common.RESEARCH_MODEL,
            max_tokens=32000,
            system=system,
            tools=tools,
            messages=messages,
        ) as stream:
            msg = stream.get_final_message()
        common.check_refusal(msg)
        data = common.extract_json(common.final_text(msg))
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--piece-id", help="Piece ID matching the review tool, e.g. 02-slug")
    parser.add_argument("--brief", help="Commissioning brief text")
    parser.add_argument("--brief-file", type=Path, help="Path to a file holding the brief")
    parser.add_argument("--max-searches", type=int, default=15)
    parser.add_argument("--out", type=Path, help="Output path (default content/research/<id>.json)")
    parser.add_argument("--validate", type=Path, help="Validate an existing source file and exit")
    args = parser.parse_args()

    if args.validate:
        errors = common.validate_source_file(json.loads(args.validate.read_text()))
        if errors:
            for e in errors:
                print(f"invalid: {e}")
            raise SystemExit(1)
        print(f"{args.validate} is a valid source file.")
        return

    if not args.piece_id:
        common.die("--piece-id is required")
    brief = args.brief or (args.brief_file.read_text().strip() if args.brief_file else None)
    if not brief:
        common.die("provide --brief or --brief-file")

    commit = common.prompt_commit(common.PROMPTS_DIR / "research-agent.md")
    data = run_agent(args.piece_id, brief, args.max_searches)

    data["piece_id"] = args.piece_id
    data.setdefault("brief", brief)
    data["generated_at"] = common.now_iso()
    data["agent"] = {"model_id": common.RESEARCH_MODEL, "prompt_commit": commit}

    errors = common.validate_source_file(data)
    if errors:
        for e in errors:
            print(f"invalid: {e}")
        common.die("source file still fails validation after one repair pass; not writing it")

    out = args.out or (common.RESEARCH_DIR / f"{args.piece_id}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2) + "\n")

    unsourced = [s["id"] for s in data["sources"] if s["confidence"] == "unsourced"]
    contested = [s["id"] for s in data["sources"] if s["confidence"] == "contested"]
    print(f"wrote {out} — {len(data['sources'])} records")
    if unsourced:
        print(f"  unsourced (visible holes for the reviewer): {', '.join(unsourced)}")
    if contested:
        print(f"  contested pairs: {', '.join(contested)}")

    common.emit_provenance(
        "research",
        {
            "model_id": common.RESEARCH_MODEL,
            "prompt_commit": commit,
            "source_file": str(out.relative_to(common.AIRCHELON_ROOT)),
            "source_file_sha256": common.sha256_file(out),
            "generated_at": data["generated_at"],
        },
    )


if __name__ == "__main__":
    main()
