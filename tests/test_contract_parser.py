import pytest

from app.workflow.contracts.parser import ContractParseError, parse_contract

FULL_CONTRACT = """# Contract: scope

## Identity
You are a research editor. Your only job is to convert an ambiguous request
into a bounded, testable brief.

## Inputs
- initial_request.md
- style guide (optional)

## Procedure
1. Apply the scoping skill.
2. Draft the scope brief.
3. Draft the handoff.

## Outputs
- scope_brief: scope_brief.md — bounded, testable brief
- handoff: handoff.md

## Definition of done
- every field populated or explicitly N/A

## Failure modes
- silent scope expansion
"""


def test_parse_full_contract() -> None:
    parsed = parse_contract(FULL_CONTRACT)
    assert parsed["identity"].startswith("You are a research editor.")
    assert parsed["inputs"] == ["initial_request.md", "style guide (optional)"]
    assert len(parsed["procedure"]) == 3
    assert parsed["outputs"] == [
        {
            "role": "scope_brief",
            "filename": "scope_brief.md",
            "description": "bounded, testable brief",
        },
        {"role": "handoff", "filename": "handoff.md", "description": ""},
    ]
    assert parsed["definition_of_done"] == ["every field populated or explicitly N/A"]
    assert parsed["failure_modes"] == ["silent scope expansion"]


def test_missing_identity_rejected() -> None:
    with pytest.raises(ContractParseError, match="Identity"):
        parse_contract("## Outputs\n- a: a.md\n")


def test_missing_outputs_rejected() -> None:
    with pytest.raises(ContractParseError, match="Outputs"):
        parse_contract("## Identity\nSomeone.\n")


def test_malformed_output_entry_rejected() -> None:
    with pytest.raises(ContractParseError, match="malformed output"):
        parse_contract("## Identity\nSomeone.\n## Outputs\n- just some prose\n")


def test_duplicate_output_roles_rejected() -> None:
    source = "## Identity\nSomeone.\n## Outputs\n- a: a.md\n- a: b.md\n"
    with pytest.raises(ContractParseError, match="unique"):
        parse_contract(source)


def test_unknown_sections_are_ignored() -> None:
    source = "## Identity\nSomeone.\n## Notes\nirrelevant\n## Outputs\n- a: a.md\n"
    parsed = parse_contract(source)
    assert parsed["outputs"][0]["role"] == "a"
