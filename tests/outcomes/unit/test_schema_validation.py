"""Unit test: JSON Schema validates registry entries.

Drives the production loader (`registry_service.load_schema`, which reads the
packaged `nwave_ai/outcomes/schema.json` via importlib.resources) and asserts:
- a valid canonical entry passes
- entries missing required fields fail
- entries with invalid kind/id pattern fail

The schema is deliberately NOT re-resolved by a path formula of this test's own:
one loader, one resource. A second copy of the path arithmetic here is exactly
how the schema location silently drifted out from under the CLI (#63) while this
file stayed green.
"""

from __future__ import annotations

import pytest
from jsonschema import Draft7Validator, ValidationError
from nwave_ai.outcomes.application.registry_service import load_schema


def _load_schema() -> dict:
    return load_schema()


def _valid_entry() -> dict:
    return {
        "id": "OUT-1",
        "kind": "specification",
        "summary": "valid",
        "feature": "outcomes-registry",
        "inputs": [{"shape": "FeatureDeltaModel"}],
        "output": {"shape": "tuple[Violation, ...]"},
        "keywords": ["non-empty"],
        "artifact": "nwave_ai/outcomes/cli.py",
        "related": [],
        "superseded_by": None,
    }


def test_valid_entry_passes_schema() -> None:
    Draft7Validator(_load_schema()).validate(_valid_entry())


@pytest.mark.parametrize(
    "mutation,expected_path_fragment",
    [
        ({"id": "out-1"}, "id"),  # lowercase fails pattern
        ({"kind": "bogus"}, "kind"),  # not in enum
        ({"inputs": []}, "inputs"),  # below minItems
        ({"output": {}}, "shape"),  # missing required nested
        ({"keywords": ["a", "b", "c", "d", "e", "f", "g"]}, "keywords"),  # too many
    ],
    ids=[
        "bad-id-pattern",
        "bad-kind-enum",
        "empty-inputs",
        "missing-output-shape",
        "too-many-keywords",
    ],
)
def test_invalid_entries_fail_schema(
    mutation: dict, expected_path_fragment: str
) -> None:
    entry = _valid_entry() | mutation
    with pytest.raises(ValidationError) as exc:
        Draft7Validator(_load_schema()).validate(entry)
    assert expected_path_fragment in str(exc.value), (
        f"expected '{expected_path_fragment}' in error: {exc.value}"
    )


def test_missing_required_field_fails_schema() -> None:
    entry = _valid_entry()
    del entry["id"]
    with pytest.raises(ValidationError):
        Draft7Validator(_load_schema()).validate(entry)
