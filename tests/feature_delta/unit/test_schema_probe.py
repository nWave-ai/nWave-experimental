"""
Unit tests for JsonSchemaFileLoader — driving through the public API.

Port-to-port: probe() and load_schema() ARE the driving port.
Asserts on return value and exception raising.

Test Budget: 2 behaviors x 2 = 4 max. Using 2.
  B1: probe() raises SystemExit(70) on corrupted JSON
  B2: load_schema() returns parsed schema dict for a valid schema file
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest


if TYPE_CHECKING:
    from pathlib import Path
from nwave_ai.feature_delta.adapters.schema import JsonSchemaFileLoader


def test_probe_raises_system_exit_70_on_corrupted_json(tmp_path: Path) -> None:
    """B1: corrupted JSON causes probe() to exit with code 70."""
    broken = tmp_path / "schema.json"
    broken.write_text("{not valid json", encoding="utf-8")
    loader = JsonSchemaFileLoader(schema_path=broken)
    with pytest.raises(SystemExit) as exc_info:
        loader.probe()
    assert exc_info.value.code == 70


def test_load_schema_returns_parsed_dict_for_valid_file(tmp_path: Path) -> None:
    """B2: valid draft-07 schema file is returned as a parsed dict."""
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "https://nwave.ai/schemas/feature-delta-schema.json",
        "title": "feature-delta",
        "type": "object",
        "definitions": {},
    }
    schema_file = tmp_path / "schema.json"
    schema_file.write_text(json.dumps(schema), encoding="utf-8")
    loader = JsonSchemaFileLoader(schema_path=schema_file)
    result = loader.load_schema()
    assert result["$schema"] == "http://json-schema.org/draft-07/schema#"
    assert result["title"] == "feature-delta"
