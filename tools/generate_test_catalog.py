"""Generate docs/test-catalog.md — the test suite in plain language.

Reads every tests/test_*.py, takes each test's docstring (first paragraph)
when it has one and otherwise turns the test name into a sentence, and writes
a reviewer-facing catalog grouped by area. Run after adding or changing
tests:

    uv run python tools/generate_test_catalog.py
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TESTS = REPO / "tests"
OUTPUT = REPO / "docs" / "test-catalog.md"

# Reviewer-facing area names per test module.
AREA_TITLES = {
    "test_auth": "Authentication and roles",
    "test_celery_app": "Background worker configuration",
    "test_celery_registration": "Background worker task registration",
    "test_contract_parser": "Stage contract parsing (fail closed)",
    "test_platform_core": "Platform core (identity, time, events)",
    "test_security": "Security (authentication sweep, headers, throttling)",
    "test_workflow": "Workflow (ICM stages, contracts, artifacts)",
    "test_governance": "Governance (review gates, audit trail)",
    "test_evals": "Evals (rubrics, human scoring, decisions, regression packs)",
    "test_eval_gate": "Workflow eval gate",
    "test_judge_evals": "LLM judge (advisory scoring, agreement, drift)",
    "test_calibration": "Judge calibration (golden sets, TPR/TNR, gate)",
    "test_evidence_pack": "Evidence packs (export, hash chain)",
    "test_agent_execution": "Agent execution (automated stages, kill switch)",
    "test_llm_adapters": "LLM providers (Anthropic, OpenAI-compatible)",
    "test_environment": "Environment (templates, evidence-gated promotion)",
    "test_resilience": "Human capacity resilience (drills, thresholds)",
    "test_list_endpoints": "Console list endpoints",
    "test_health": "Health and API docs exposure",
    "test_migrations": "Database migrations",
    "test_storage": "Object storage",
}


def humanize(test_name: str) -> str:
    words = test_name.removeprefix("test_").replace("_", " ").strip()
    return words[:1].upper() + words[1:] + "."


def first_paragraph(docstring: str | None) -> str | None:
    if not docstring:
        return None
    paragraph = docstring.strip().split("\n\n")[0]
    return " ".join(line.strip() for line in paragraph.splitlines())


def collect(path: Path) -> tuple[str | None, list[tuple[str, str]]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    module_doc = first_paragraph(ast.get_docstring(tree))
    entries: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test_"
        ):
            description = first_paragraph(ast.get_docstring(node)) or humanize(node.name)
            entries.append((node.name, description))
    return module_doc, entries


def main() -> None:
    sections: list[str] = []
    total = 0
    for path in sorted(TESTS.glob("test_*.py")):
        module_doc, entries = collect(path)
        if not entries:
            continue
        total += len(entries)
        title = AREA_TITLES.get(path.stem, path.stem.removeprefix("test_").replace("_", " "))
        lines = [f"## {title}", ""]
        lines.append(f"*{len(entries)} checks — `tests/{path.name}`*")
        if module_doc:
            lines += ["", f"> {module_doc}"]
        lines.append("")
        lines += [f"- {description}" for _name, description in entries]
        lines.append("")
        sections.append("\n".join(lines))

    OUTPUT.write_text(
        "\n".join(
            [
                "# Test catalog — what the suite proves, in plain language",
                "",
                "Each line below is one automated check, described for a human reviewer.",
                "A release is only shipped when every one of them passes. Regenerate after",
                "changing tests: `uv run python tools/generate_test_catalog.py`.",
                "",
                f"**{total} checks across {len(sections)} areas.**",
                "",
                *sections,
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"wrote {OUTPUT.relative_to(REPO)} ({total} checks)")


if __name__ == "__main__":
    main()
