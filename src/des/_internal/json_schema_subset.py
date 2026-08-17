"""Stdlib-only interpreter for the JSON Schema subset DES actually uses.

The installed nWave shim is ``#!/usr/bin/env python3`` and the caller
project's venv is intentionally first on ``PATH`` -- see ``des._compat``'s
bundle-stdlib-only contract. ``jsonschema`` is a real, correctly-declared
project dependency (other non-DES consumers keep using
``Draft202012Validator`` directly, e.g. ``tests/build/
test_thin_delivery_contract_schema.py``), but it is a PyPI package the
installed DES bundle cannot assume is present on that PATH. ``des.cli.
dispatch`` is, per graphify's binding-resolved call graph, the ONE shipped
DES module that imports ``jsonschema`` -- so it is the one caller that
needs a stdlib-only substitute, not a reason to remove the real dependency
project-wide.

This module interprets exactly the validation-keyword subset used by
``nWave/schemas/thin-delivery-contract.schema.json`` today: ``$ref``
(local ``#/$defs/...`` only), ``$defs``, ``type``, ``required``,
``properties``, ``additionalProperties``, ``const``, ``enum``,
``minimum``, ``minLength``, ``pattern``, ``minItems``, ``uniqueItems``,
``items``, ``minProperties``, ``propertyNames``, ``oneOf``. The
annotation keywords ``$schema``, ``$id``, ``title``, ``description`` are
recognised and ignored. The schema file itself remains the sole authority
for the contract shape -- this module hardcodes no DeliveryContract field
names or constraints, only the JSON Schema vocabulary needed to interpret
whatever the schema file declares.

Fail-closed, deliberately narrow: any schema keyword outside this subset,
or any ``$ref`` that is not a local ``#/$defs/<name>`` pointer, raises
immediately rather than silently skipping the constraint it would have
enforced. A schema-authoring mistake that adds a richer keyword (say,
``patternProperties`` or ``anyOf``) must be caught here, not silently
under-validated at runtime.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Mapping


class JsonSchemaSubsetError(Exception):
    """One actionable validation or unsupported-schema-shape failure.

    ``message`` is the human-readable WHAT; ``path`` is the JSON-pointer-
    style tuple of property names / array indices leading to the failing
    instance node (empty tuple for a whole-document failure), mirroring
    ``jsonschema.exceptions.ValidationError.message`` /
    ``.absolute_path`` closely enough for callers that only read those two
    fields -- without depending on ``jsonschema`` itself. ``validator``
    names the JSON Schema keyword that fired, or ``"$schema-subset"`` for
    an unsupported-schema-shape refusal (never a keyword violation).
    """

    def __init__(
        self,
        message: str,
        path: tuple[str | int, ...] = (),
        validator: str = "$schema-subset",
    ) -> None:
        self.message = message
        self.path = path
        self.validator = validator
        super().__init__(message)


_KNOWN_ANNOTATIONS = frozenset({"$schema", "$id", "title", "description"})
_KNOWN_KEYWORDS = (
    frozenset(
        {
            "$ref",
            "$defs",
            "type",
            "required",
            "properties",
            "additionalProperties",
            "const",
            "enum",
            "minimum",
            "minLength",
            "pattern",
            "minItems",
            "uniqueItems",
            "items",
            "minProperties",
            "propertyNames",
            "oneOf",
        }
    )
    | _KNOWN_ANNOTATIONS
)

_TYPE_CHECKS: Mapping[str, object] = {
    "object": lambda value: isinstance(value, dict),
    "array": lambda value: isinstance(value, list),
    "string": lambda value: isinstance(value, str),
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "number": lambda value: (
        isinstance(value, (int, float)) and not isinstance(value, bool)
    ),
    "boolean": lambda value: isinstance(value, bool),
    "null": lambda value: value is None,
}


def validate(schema: dict, instance: object) -> None:
    """Validate ``instance`` against ``schema``'s supported subset.

    Raises ``JsonSchemaSubsetError`` on the first violation, or on the
    first unsupported schema keyword / non-local ``$ref`` encountered
    anywhere in the schema (checked once, up front, before any instance
    comparison) -- fail-closed rather than silently under-enforcing.
    """
    _check_supported(schema, schema)
    _validate_node(schema, instance, (), schema)


def _check_supported(node: dict, root: dict) -> None:
    """Recursively refuse an unknown keyword or a non-local ``$ref``."""
    for key, value in node.items():
        if key == "$ref":
            _resolve_ref(value, root)
            continue
        if key not in _KNOWN_KEYWORDS:
            raise JsonSchemaSubsetError(f"unsupported schema keyword: {key!r}")
        if key == "$defs":
            if not isinstance(value, dict):
                raise JsonSchemaSubsetError("$defs must be an object")
            for subschema in value.values():
                _require_schema_object(subschema)
                _check_supported(subschema, root)
        elif key == "properties":
            if not isinstance(value, dict):
                raise JsonSchemaSubsetError("properties must be an object")
            for subschema in value.values():
                _require_schema_object(subschema)
                _check_supported(subschema, root)
        elif key == "additionalProperties":
            if isinstance(value, dict):
                _check_supported(value, root)
            elif not isinstance(value, bool):
                raise JsonSchemaSubsetError(
                    "additionalProperties must be a boolean or an object schema"
                )
        elif key in ("items", "propertyNames"):
            _require_schema_object(value)
            _check_supported(value, root)
        elif key == "oneOf":
            if not isinstance(value, list) or not value:
                raise JsonSchemaSubsetError("oneOf must be a non-empty array")
            for subschema in value:
                _require_schema_object(subschema)
                _check_supported(subschema, root)


def _require_schema_object(node: object) -> None:
    if not isinstance(node, dict):
        raise JsonSchemaSubsetError(
            f"unsupported schema node (not an object): {node!r}"
        )


def _resolve_ref(ref: object, root: dict) -> dict:
    if not isinstance(ref, str) or not ref.startswith("#/$defs/"):
        raise JsonSchemaSubsetError(
            f"unsupported $ref (must be a local #/$defs/<name> reference): {ref!r}"
        )
    name = ref.removeprefix("#/$defs/")
    if "/" in name:
        raise JsonSchemaSubsetError(f"unsupported nested $ref target: {ref!r}")
    defs = root.get("$defs", {})
    if not isinstance(defs, dict) or name not in defs:
        raise JsonSchemaSubsetError(f"$ref target not found in $defs: {ref!r}")
    target = defs[name]
    _require_schema_object(target)
    return target


def _canon(value: object) -> object:
    """A hashable, type-distinguishing canonical form for equality/dedup.

    JSON booleans are not integers: ``True`` and ``1`` must compare
    unequal for ``const``/``enum``/``uniqueItems``, even though Python's
    ``bool`` is an ``int`` subclass. Dicts and lists are not hashable in
    Python; converting them to nested, order-independent (for objects)
    tuples of canonical child values makes every instance value usable as
    a set/dict key downstream without ever calling ``hash()`` on the raw
    JSON value itself.
    """
    if isinstance(value, bool):
        return ("boolean", value)
    if isinstance(value, int):
        return ("number", float(value))
    if isinstance(value, float):
        return ("number", value)
    if isinstance(value, str):
        return ("string", value)
    if value is None:
        return ("null",)
    if isinstance(value, list):
        return ("array", tuple(_canon(item) for item in value))
    if isinstance(value, dict):
        return ("object", tuple(sorted((k, _canon(v)) for k, v in value.items())))
    raise JsonSchemaSubsetError(f"unsupported JSON instance value: {value!r}")


def _json_equal(left: object, right: object) -> bool:
    return _canon(left) == _canon(right)


def _validate_type(
    type_name: object, instance: object, path: tuple[str | int, ...]
) -> None:
    if not isinstance(type_name, str) or type_name not in _TYPE_CHECKS:
        raise JsonSchemaSubsetError(
            f"unsupported type keyword value: {type_name!r}", path
        )
    if not _TYPE_CHECKS[type_name](instance):
        raise JsonSchemaSubsetError(
            f"{instance!r} is not of type {type_name!r}", path, "type"
        )


def _matches(
    schema: dict, instance: object, path: tuple[str | int, ...], root: dict
) -> bool:
    try:
        _validate_node(schema, instance, path, root)
    except JsonSchemaSubsetError:
        return False
    return True


def _validate_node(
    schema: dict, instance: object, path: tuple[str | int, ...], root: dict
) -> None:
    if "$ref" in schema:
        target = _resolve_ref(schema["$ref"], root)
        _validate_node(target, instance, path, root)
        remainder = {
            key: value
            for key, value in schema.items()
            if key != "$ref" and key not in _KNOWN_ANNOTATIONS
        }
        if remainder:
            _validate_node(remainder, instance, path, root)
        return

    if "oneOf" in schema:
        branches = schema["oneOf"]
        matches = sum(
            1 for branch in branches if _matches(branch, instance, path, root)
        )
        if matches != 1:
            raise JsonSchemaSubsetError(
                f"expected exactly one oneOf branch to match, {matches} matched",
                path,
                "oneOf",
            )
        return

    if "type" in schema:
        _validate_type(schema["type"], instance, path)

    if "const" in schema and not _json_equal(instance, schema["const"]):
        raise JsonSchemaSubsetError(
            f"{instance!r} does not equal const {schema['const']!r}", path, "const"
        )

    if "enum" in schema and not any(
        _json_equal(instance, member) for member in schema["enum"]
    ):
        raise JsonSchemaSubsetError(
            f"{instance!r} is not one of {schema['enum']!r}", path, "enum"
        )

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            raise JsonSchemaSubsetError(
                f"{instance!r} is shorter than minLength {schema['minLength']}",
                path,
                "minLength",
            )
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            raise JsonSchemaSubsetError(
                f"{instance!r} does not match pattern {schema['pattern']!r}",
                path,
                "pattern",
            )

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            raise JsonSchemaSubsetError(
                f"{instance!r} is less than minimum {schema['minimum']}",
                path,
                "minimum",
            )

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            raise JsonSchemaSubsetError(
                f"array has fewer than minItems {schema['minItems']} elements",
                path,
                "minItems",
            )
        if schema.get("uniqueItems"):
            seen: set[object] = set()
            for item in instance:
                marker = _canon(item)
                if marker in seen:
                    raise JsonSchemaSubsetError(
                        "array items are not unique", path, "uniqueItems"
                    )
                seen.add(marker)
        if "items" in schema:
            items_schema = schema["items"]
            for index, item in enumerate(instance):
                _validate_node(items_schema, item, (*path, index), root)

    if isinstance(instance, dict):
        if "minProperties" in schema and len(instance) < schema["minProperties"]:
            raise JsonSchemaSubsetError(
                f"object has fewer than minProperties {schema['minProperties']} "
                "properties",
                path,
                "minProperties",
            )
        if "required" in schema:
            missing = [name for name in schema["required"] if name not in instance]
            if missing:
                raise JsonSchemaSubsetError(
                    f"missing required properties: {missing}", path, "required"
                )
        properties = schema.get("properties", {})
        for key, subschema in properties.items():
            if key in instance:
                _validate_node(subschema, instance[key], (*path, key), root)
        if "additionalProperties" in schema:
            additional = schema["additionalProperties"]
            for key, value in instance.items():
                if key in properties:
                    continue
                if additional is False:
                    raise JsonSchemaSubsetError(
                        f"additional property {key!r} is not allowed",
                        path,
                        "additionalProperties",
                    )
                if isinstance(additional, dict):
                    _validate_node(additional, value, (*path, key), root)
        if "propertyNames" in schema:
            names_schema = schema["propertyNames"]
            for key in instance:
                _validate_node(names_schema, key, path, root)


__all__ = ["JsonSchemaSubsetError", "validate"]
