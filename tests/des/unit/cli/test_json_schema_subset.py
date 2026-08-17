"""Differential laws for the stdlib-only JSON Schema subset interpreter."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from des._internal import json_schema_subset as subset
from tests.common.delivery_contract_fixture import load_valid_contract


SCHEMA = json.loads(
    Path("nWave/schemas/thin-delivery-contract.schema.json").read_text(encoding="utf-8")
)
Mutation = Callable[[dict[str, Any]], None]


def _subset_accepts(schema: dict[str, Any], value: object) -> bool:
    try:
        subset.validate(schema, value)
    except subset.JsonSchemaSubsetError:
        return False
    return True


def _identity(_contract: dict[str, Any]) -> None:
    return None


def _delete_delivery_id(contract: dict[str, Any]) -> None:
    del contract["delivery-id"]


def _set(path: tuple[str, ...], value: object) -> Mutation:
    def mutate(contract: dict[str, Any]) -> None:
        target = contract
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return mutate


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(_identity, id="valid"),
        pytest.param(_delete_delivery_id, id="missing-required"),
        pytest.param(_set(("schema-version",), "1.1"), id="const"),
        pytest.param(_set(("paradigm",), "procedural"), id="enum"),
        pytest.param(_set(("outcome",), 123), id="type"),
        pytest.param(_set(("outcome",), ""), id="min-length"),
        pytest.param(_set(("delivery-id",), "INVALID"), id="pattern"),
        pytest.param(_set(("budget", "token-limit"), True), id="bool-is-not-integer"),
        pytest.param(_set(("budget", "token-limit"), 0), id="minimum"),
        pytest.param(_set(("obligations",), []), id="min-items"),
        pytest.param(
            _set(("obligations",), ["CONTESTED_LAW", "CONTESTED_LAW"]),
            id="unique-items",
        ),
        pytest.param(_set(("obligations",), ["CONTESTED_LAW", 123]), id="items-enum"),
    ],
)
def test_subset_agrees_with_draft202012_for_the_shipped_contract(
    mutate: Mutation,
) -> None:
    contract = copy.deepcopy(load_valid_contract())
    mutate(contract)

    assert _subset_accepts(SCHEMA, contract) is Draft202012Validator(SCHEMA).is_valid(
        contract
    )


@pytest.mark.parametrize(
    "schema",
    [
        pytest.param({"type": "string", "maxLength": 1}, id="unknown-keyword"),
        pytest.param({"$ref": "https://example.test/schema"}, id="external-ref"),
        pytest.param({"$ref": "other.json#/$defs/x"}, id="relative-ref"),
        pytest.param({"$ref": "#/$defs/outer/inner"}, id="nested-ref"),
    ],
)
def test_unsupported_schema_shapes_fail_closed(schema: dict[str, Any]) -> None:
    with pytest.raises(subset.JsonSchemaSubsetError) as error:
        subset.validate(schema, {})

    assert error.value.validator == "$schema-subset"


@pytest.mark.parametrize(
    ("schema", "value", "expected"),
    [
        pytest.param({"type": "integer"}, True, False, id="bool-not-integer"),
        pytest.param({"type": "integer"}, 1, True, id="integer"),
        pytest.param(
            {"type": "array", "uniqueItems": True},
            [{"x": [1]}, {"x": [1]}],
            False,
            id="duplicate-unhashable-values",
        ),
        pytest.param(
            {"type": "array", "uniqueItems": True},
            [{"x": [1]}, {"x": [2]}],
            True,
            id="distinct-unhashable-values",
        ),
        pytest.param(
            {"oneOf": [{"const": True}, {"const": 1}]},
            True,
            True,
            id="bool-int-const-distinction",
        ),
        pytest.param(
            {
                "oneOf": [
                    {"type": "object"},
                    {"properties": {"x": {"type": "number"}}},
                ]
            },
            {"x": 5},
            False,
            id="one-of-exactly-one",
        ),
    ],
)
def test_json_equality_and_one_of_laws_match_draft202012(
    schema: dict[str, Any], value: object, expected: bool
) -> None:
    assert _subset_accepts(schema, value) is expected
    assert Draft202012Validator(schema).is_valid(value) is expected
