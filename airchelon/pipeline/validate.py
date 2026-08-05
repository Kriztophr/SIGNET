"""Validation of research source files against schemas/source-file.schema.json.

The schema file is the contract — the research agent's output is validated
against the actual committed schema, not a reimplementation of it.
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from .common import SCHEMAS_DIR

SCHEMA_PATH = SCHEMAS_DIR / "source-file.schema.json"


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validation_errors(source_file: dict) -> list[str]:
    """Return human-readable schema violations, empty when valid."""
    validator = Draft202012Validator(load_schema())
    errors = sorted(validator.iter_errors(source_file), key=lambda e: list(e.absolute_path))
    out = []
    for err in errors:
        where = "/".join(str(p) for p in err.absolute_path) or "(root)"
        out.append(f"{where}: {err.message}")
    return out


def validate_file(path: Path) -> dict:
    """Load and validate a source file; raise ValueError with all violations."""
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validation_errors(data)
    if errors:
        listing = "\n  - ".join(errors)
        raise ValueError(f"{path} does not satisfy the source-file schema:\n  - {listing}")
    return data
