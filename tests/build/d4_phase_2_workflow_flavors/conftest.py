"""Conftest for D4 Phase 2 slice-01 atdd_pure.yaml flavor config."""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
FLAVORS_DIR = REPO_ROOT / "nWave" / "flavors"
GATES_DIR = REPO_ROOT / "nWave" / "gates"

ATDD_PURE_FLAVOR = FLAVORS_DIR / "atdd_pure.yaml"
FLAVOR_SCHEMA = FLAVORS_DIR / "_schema.yaml"
GATE_CATALOG = GATES_DIR / "_catalog.yaml"


class FlavorComposition:
    def __init__(self) -> None:
        self._flavor: dict | None = None
        self._schema: dict | None = None
        self._catalog: dict | None = None
        self._validation_errors: list[str] = []

    def load_flavor(self) -> None:
        import yaml

        self._flavor = yaml.safe_load(ATDD_PURE_FLAVOR.read_text())

    def load_schema(self) -> None:
        import yaml

        self._schema = yaml.safe_load(FLAVOR_SCHEMA.read_text())

    def load_catalog(self) -> None:
        import yaml

        self._catalog = yaml.safe_load(GATE_CATALOG.read_text())

    def validate(self) -> None:
        import jsonschema

        try:
            jsonschema.validate(instance=self._flavor, schema=self._schema)
        except jsonschema.ValidationError as exc:
            self._validation_errors.append(str(exc.message))

    @property
    def flavor(self) -> dict:
        assert self._flavor is not None
        return self._flavor

    @property
    def referenced_gate_ids(self) -> set[str]:
        ids = set()
        for event_comp in self.flavor["lifecycle_events"].values():
            for gate in event_comp:
                ids.add(gate["gate_id"])
        return ids

    @property
    def catalog_gate_ids(self) -> set[str]:
        assert self._catalog is not None
        return {g["gate_id"] for g in self._catalog["gates"]}

    @property
    def validation_errors(self) -> list[str]:
        return self._validation_errors

    def dispatch_pre_composition(self) -> list[dict]:
        return self.flavor["lifecycle_events"]["dispatch.pre"]


@pytest.fixture
def flavor_comp() -> FlavorComposition:
    return FlavorComposition()
