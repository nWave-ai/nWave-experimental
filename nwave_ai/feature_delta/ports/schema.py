"""SchemaProviderPort — driven port interface for JSON Schema loading."""

from __future__ import annotations

from typing import Any, Protocol


class SchemaProviderPort(Protocol):
    """Driven port: loads and validates the feature-delta JSON Schema."""

    def load_schema(self) -> dict[str, Any]:
        """Return the parsed schema as a dict."""
        ...

    def probe(self) -> None:
        """
        Validate the schema file at startup.

        Raises SystemExit(70) if the file is missing, unparseable, or
        fails Draft7Validator.check_schema().  Writes a structured
        health.startup.refused event to stderr before exiting.
        """
        ...
