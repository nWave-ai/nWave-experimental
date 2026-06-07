"""Step bindings for D4 Phase 2 slice-02 classic flavor."""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, then, when

from ..conftest import FLAVOR_SCHEMA, FLAVORS_DIR, GATE_CATALOG


CLASSIC_FLAVOR = FLAVORS_DIR / "classic.yaml"


class ClassicComposition:
    def __init__(self) -> None:
        self._flavor: dict | None = None
        self._schema: dict | None = None
        self._catalog: dict | None = None
        self._validation_errors: list[str] = []

    def load_flavor(self) -> None:
        import yaml

        self._flavor = yaml.safe_load(CLASSIC_FLAVOR.read_text())

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
        return self._flavor

    @property
    def referenced_gate_ids(self) -> set[str]:
        ids = set()
        for comp in self.flavor["lifecycle_events"].values():
            for gate in comp:
                ids.add(gate["gate_id"])
        return ids

    @property
    def catalog_gate_ids(self) -> set[str]:
        return {g["gate_id"] for g in self._catalog["gates"]}

    @property
    def validation_errors(self) -> list[str]:
        return self._validation_errors

    def gate_ids_in_event(self, event: str) -> list[str]:
        return [g["gate_id"] for g in self.flavor["lifecycle_events"].get(event, [])]


@pytest.fixture
def classic_comp() -> ClassicComposition:
    return ClassicComposition()


@given(parsers.parse('the flavor file at "{path}"'))
def given_classic_flavor(classic_comp, path: str) -> None:
    classic_comp.load_flavor()


@given(parsers.parse('the flavor schema at "{path}"'))
def given_classic_schema(classic_comp, path: str) -> None:
    classic_comp.load_schema()


@given(parsers.parse('the gate catalog at "{path}"'))
def given_classic_catalog(classic_comp, path: str) -> None:
    classic_comp.load_catalog()


@when("the flavor is validated against the schema")
def when_classic_validate(classic_comp) -> None:
    classic_comp.validate()


@when("the gate references are extracted from lifecycle_events")
def when_classic_extract(classic_comp) -> None:
    pass


@when("classic-specific gate references are extracted")
def when_classic_specific(classic_comp) -> None:
    pass


@then("validation succeeds with zero errors")
def then_classic_valid(classic_comp) -> None:
    assert classic_comp.validation_errors == [], (
        f"Validation errors: {classic_comp.validation_errors}"
    )


@then("every referenced gate_id matches a catalog entry")
def then_classic_refs(classic_comp) -> None:
    missing = classic_comp.referenced_gate_ids - classic_comp.catalog_gate_ids
    assert not missing, f"Classic references gates not in catalog: {missing}"


@then(parsers.parse('the classic flavor uses gate "{gate_id}" in {event}'))
def then_classic_uses_gate(classic_comp, gate_id: str, event: str) -> None:
    ids = classic_comp.gate_ids_in_event(event)
    assert gate_id in ids, f"event={event} composition={ids}"


@then(parsers.parse('the classic flavor does NOT reference gate "{gate_id}"'))
def then_classic_no_gate(classic_comp, gate_id: str) -> None:
    assert gate_id not in classic_comp.referenced_gate_ids, (
        f"classic.yaml references {gate_id}, but classic should NOT use it"
    )
