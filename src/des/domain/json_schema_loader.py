"""Generic JSON schema loader base — shared scaffolding SSOT.

Holds the path-resolution + caching scaffolding once, previously copy-pasted
across ``RoadmapSchemaLoader`` and ``TDDSchemaLoader`` (the roadmap docstring
literally read "Mirrors tdd_schema.py pattern"). The fragile 3-context
path-resolution lives here verbatim; subclasses supply only the bundled
schema FILENAME (via ``SCHEMA_FILENAME``) and the ``_parse_schema`` step
(template method: ``load()`` calls ``self._parse_schema(raw)``).

Consolidation (AD-16 residual, 2026-06): byte-for-byte move of the shared
scaffolding — the candidate-path order and the parents[N]/marker logic are
NOT changed. Per-loader differences are exactly: the schema filename, the
``_parse_schema`` body, and the returned VO type.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Generic, TypeVar


SchemaT = TypeVar("SchemaT")


class JsonSchemaLoader(Generic[SchemaT]):
    """Base loader for a bundled JSON schema with WSL-safe path resolution.

    Subclass contract:
    - set ``SCHEMA_FILENAME`` to the bundled schema file name;
    - override ``_parse_schema(raw)`` to parse the raw dict into the VO.
    """

    SCHEMA_FILENAME: str = ""

    @classmethod
    def _resolve_default_schema_path(cls) -> Path:
        """Resolve schema path for current environment.

        Handles three deployment contexts:
        - Source: src/des/domain/<loader>.py -> project_root/nWave/templates/
        - Installed: ~/.claude/lib/python/des/domain/<loader>.py -> ~/.claude/templates/
        - Plugin: .../scripts/des/domain/<loader>.py -> .../scripts/templates/
        """
        module_file = Path(__file__)
        # Normalize to forward slashes for cross-platform matching
        module_str = str(module_file).replace("\\", "/")
        module_resolved_str = str(module_file.resolve()).replace("\\", "/")

        is_installed = (
            ".claude" in module_str or ".claude" in module_resolved_str
        ) and (
            "lib/python/des" in module_str or "lib/python/des" in module_resolved_str
        )

        if is_installed:
            for search_path in [module_file, module_file.resolve()]:
                for parent in search_path.parents:
                    if parent.name == ".claude":
                        candidate = parent / "templates" / cls.SCHEMA_FILENAME
                        if candidate.exists():
                            return candidate

        # Plugin context: scripts/des/domain/<loader>.py → scripts/templates/
        for search_path in [module_file, module_file.resolve()]:
            for parent in search_path.parents:
                if parent.name == "scripts":
                    candidate = parent / "templates" / cls.SCHEMA_FILENAME
                    if candidate.exists():
                        return candidate

        return (
            module_file.resolve().parent.parent.parent.parent
            / "nWave"
            / "templates"
            / cls.SCHEMA_FILENAME
        )

    def __init__(self, schema_path: Path | None = None):
        self._schema_path = schema_path or self._resolve_default_schema_path()
        self._cached_schema: SchemaT | None = None

    @property
    def schema_path(self) -> Path:
        """Path to the schema JSON file."""
        return self._schema_path

    def load(self) -> SchemaT:
        """Load and parse the schema, returning the cached instance if present."""
        if self._cached_schema is not None:
            return self._cached_schema
        raw_data = self._read_schema_file()
        self._cached_schema = self._parse_schema(raw_data)
        return self._cached_schema

    def _read_schema_file(self) -> dict:
        """Read raw JSON from schema file."""
        with open(self._schema_path, encoding="utf-8") as f:
            return json.load(f)

    def _parse_schema(self, raw: dict) -> SchemaT:
        """Parse raw JSON into the schema VO. Subclass hook."""
        raise NotImplementedError

    def clear_cache(self) -> None:
        """Clear the cached schema, forcing reload on next access."""
        self._cached_schema = None
