"""Conftest for D4 Phase 1 slice-01 catalog files.

Driving port: yaml + jsonschema (real I/O on YAML files) + `des.cli.__main__._REGISTRY`
(production registry as ground truth). Per Mandate-13: ATs drive via
function-level imports of public symbols (yaml.safe_load, _REGISTRY tuple),
NOT via internal field introspection.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
GATES_DIR = REPO_ROOT / "nWave" / "gates"
CATALOG_PATH = GATES_DIR / "_catalog.yaml"
SCHEMA_PATH = GATES_DIR / "_schema.yaml"


class CatalogComposition:
    """Composition root for catalog + schema + registry cross-check.

    Wraps file loads + validation so step bodies stay ≤2 statements per
    Mandate-12. Per Mandate-13: no direct domain/application imports;
    `_REGISTRY` is the adapter-layer CLI registry (allowed).
    """

    def __init__(self) -> None:
        self._catalog: dict[str, Any] | None = None
        self._schema: dict[str, Any] | None = None
        self._registry_names: list[str] | None = None
        self._validation_errors: list[str] = []

    def load_catalog(self) -> None:
        import yaml

        with open(CATALOG_PATH, encoding="utf-8") as f:
            self._catalog = yaml.safe_load(f)

    def load_schema(self) -> None:
        import yaml

        with open(SCHEMA_PATH, encoding="utf-8") as f:
            self._schema = yaml.safe_load(f)

    def load_registry(self) -> None:
        from des.cli.__main__ import _REGISTRY

        self._registry_names = [row.name for row in _REGISTRY]

    def validate(self) -> None:
        import jsonschema

        try:
            jsonschema.validate(instance=self._catalog, schema=self._schema)
        except jsonschema.ValidationError as exc:
            self._validation_errors.append(str(exc))

    @property
    def catalog_gates(self) -> list[dict[str, Any]]:
        assert self._catalog is not None
        return self._catalog["gates"]

    @property
    def catalog_gate_ids(self) -> list[str]:
        return [g["gate_id"] for g in self.catalog_gates]

    @property
    def registry_names(self) -> list[str]:
        assert self._registry_names is not None
        return self._registry_names

    @property
    def validation_errors(self) -> list[str]:
        return self._validation_errors

    def find_gate(self, gate_id: str) -> dict[str, Any]:
        for g in self.catalog_gates:
            if g["gate_id"] == gate_id:
                return g
        raise KeyError(f"Gate not found in catalog: {gate_id}")


@pytest.fixture
def composition() -> CatalogComposition:
    return CatalogComposition()
