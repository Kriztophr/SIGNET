"""Stage contract parsing.

Contracts are authored as constrained markdown and parsed into structured JSON at
template-version creation time, so a malformed contract is rejected before any run
can reference it (fail closed). Expected shape::

    # Contract: <optional title>

    ## Identity
    Free prose: who the stage executor is and what this stage alone does.

    ## Inputs
    - signed scope_brief.md

    ## Procedure
    1. First step.
    2. Second step.

    ## Outputs
    - draft: draft_v1.md — publishable prose mapped 1:1 to the outline
    - self_review: self_review.md

    ## Definition of done
    - every claim appears in the draft or is logged as dropped

    ## Failure modes
    - padding with adjectives

``Identity`` and at least one ``Outputs`` entry are mandatory. Each output line is
``<artifact_role>: <filename>`` with an optional ``— description``; the artifact
role is what stage completion validates submitted artifacts against.
"""

import re

from app.platform.errors import DomainValidationError

CONTRACT_SCHEMA_VERSION = "1.0"

_SECTION_ALIASES = {
    "identity": "identity",
    "inputs": "inputs",
    "procedure": "procedure",
    "outputs": "outputs",
    "definition of done": "definition_of_done",
    "failure modes": "failure_modes",
}

_LIST_ITEM = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(?P<text>.+)$")
_OUTPUT_ITEM = re.compile(
    r"^(?P<role>[a-z0-9_.-]+)\s*:\s*(?P<filename>\S+)(?:\s*[—–-]\s*(?P<description>.+))?$"
)


class ContractParseError(DomainValidationError):
    pass


def _list_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        match = _LIST_ITEM.match(line)
        if match:
            items.append(match.group("text").strip())
    return items


def parse_contract(source_markdown: str) -> dict:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in source_markdown.splitlines():
        if line.startswith("## "):
            current = _SECTION_ALIASES.get(line[3:].strip().lower())
            continue
        if line.startswith("# "):
            continue
        if current is not None:
            sections.setdefault(current, []).append(line)

    identity = "\n".join(sections.get("identity", [])).strip()
    if not identity:
        raise ContractParseError("contract is missing a non-empty '## Identity' section")

    outputs = []
    for item in _list_items(sections.get("outputs", [])):
        match = _OUTPUT_ITEM.match(item)
        if match is None:
            raise ContractParseError(
                f"malformed output entry {item!r}; expected '<role>: <filename> — <description>'"
            )
        outputs.append(
            {
                "role": match.group("role"),
                "filename": match.group("filename"),
                "description": (match.group("description") or "").strip(),
            }
        )
    if not outputs:
        raise ContractParseError("contract must declare at least one entry under '## Outputs'")
    roles = [output["role"] for output in outputs]
    if len(roles) != len(set(roles)):
        raise ContractParseError("contract output roles must be unique")

    return {
        "identity": identity,
        "inputs": _list_items(sections.get("inputs", [])),
        "procedure": _list_items(sections.get("procedure", [])),
        "outputs": outputs,
        "definition_of_done": _list_items(sections.get("definition_of_done", [])),
        "failure_modes": _list_items(sections.get("failure_modes", [])),
    }
