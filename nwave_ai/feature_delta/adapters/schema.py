"""JsonSchemaFileLoader — driven adapter for the SchemaProviderPort."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


_DEFAULT_SCHEMA_PATH = (
    Path(__file__).parent.parent.parent.parent / "schemas" / "feature-delta-schema.json"
)


def _resolve_schema_path(schema_path: Path | None) -> Path:
    """Resolve schema path: explicit > env var > repo default."""
    if schema_path is not None:
        return schema_path
    env = os.environ.get("NWAVE_FEATURE_DELTA_SCHEMA")
    if env:
        return Path(env)
    return _DEFAULT_SCHEMA_PATH


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
            print(
                f"health.startup.refused adapter=JsonSchemaFileLoader "
                f"path={self._path} error={exc}",
                file=sys.stderr,
            )
            sys.exit(70)

        try:
            Draft7Validator.check_schema(schema)
        except Exception as exc:
            print(
                f"health.startup.refused adapter=JsonSchemaFileLoader "
                f"path={self._path} error={exc}",
                file=sys.stderr,
            )
            sys.exit(70)
