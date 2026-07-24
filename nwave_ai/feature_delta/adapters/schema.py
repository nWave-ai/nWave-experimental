"""JsonSchemaFileLoader — driven adapter for the SchemaProviderPort."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from nwave_ai.feature_delta.adapters.refusal import refuse_startup
from nwave_ai.feature_delta.resources import packaged_resource


def _default_schema_path() -> Path:
    """The schema as a PACKAGE RESOURCE — it travels with the install.

    Resolved at call time (not import time) so tests and callers can still see a
    consistent path after monkeypatching, and so importing this module never
    depends on where the package sits.
    """
    return packaged_resource("schema.json")


def _resolve_schema_path(schema_path: Path | None) -> Path:
    """Resolve schema path: explicit > env var > packaged default.

    The explicit argument and the ``NWAVE_FEATURE_DELTA_SCHEMA`` override are
    the suite's only injection seams and stay exactly as they were (D-3). Only
    the DEFAULT moved: it used to walk four ``.parent`` hops OUT of the package
    to a top-level ``schemas/`` directory, which exists in a source checkout and
    in no install.
    """
    if schema_path is not None:
        return schema_path
    env = os.environ.get("NWAVE_FEATURE_DELTA_SCHEMA")
    if env:
        return Path(env)
    return _default_schema_path()


class JsonSchemaFileLoader:
    """
    Load and validate feature-delta-schema.json against the draft-07 metaschema.

    probe() runs at composition-root startup (DD-A7).  On failure it writes a
    structured health.startup.refused event to stderr and calls sys.exit(70).
    """

    def __init__(self, schema_path: Path | None = None) -> None:
        self._path = _resolve_schema_path(schema_path)

    def load_schema(self) -> dict[str, Any]:
        """Return the parsed schema dict.  Raises FileNotFoundError or json.JSONDecodeError on failure."""
        text = self._path.read_text(encoding="utf-8")
        return json.loads(text)  # type: ignore[no-any-return]

    def probe(self) -> None:
        """
        Startup health-check: parse + Draft7Validator.check_schema().

        On any failure: emit health.startup.refused to stderr, exit 70.
        """
        from jsonschema import Draft7Validator

        try:
            text = self._path.read_text(encoding="utf-8")
            schema = json.loads(text)
        except (OSError, json.JSONDecodeError) as exc:
            refuse_startup("JsonSchemaFileLoader", self._path, exc)

        try:
            Draft7Validator.check_schema(schema)
        except Exception as exc:
            refuse_startup("JsonSchemaFileLoader", self._path, exc)
