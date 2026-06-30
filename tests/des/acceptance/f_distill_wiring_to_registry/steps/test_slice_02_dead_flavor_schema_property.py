"""pytest-bdd binding for slice-02 (the dead flavor-schema gate-stack property).

Driving surface (Mandate-13 driving-port-only):
  * CS-1 -> Layer 3 composition: a read of the shipped flavor SCHEMA
    ``nWave/flavors/_schema.yaml`` as DATA, witnessing the dead
    ``properties.wave_gate_stacks`` $defs is GONE (DDD-9). The artifact IS the
    contract -- the same pure-stdlib YAML read slice-01 CT-3 uses on the flavor
    INSTANCE, here applied to the SCHEMA.

Step bodies delegate to ``DistillWiringComposition`` (Mandate-12: each body is a
single composition call; no control flow, no inline business logic). The slice-02
deliverable REUSES the slice-01 composition root, extended with one method pair.

active-RED scaffold (atdd_pure per-slice JIT -- NOT @skip): RED at HEAD for the
RIGHT reason (verified live this session):
  * CS-1: ``_schema.yaml`` STILL declares ``properties.wave_gate_stacks``
    (line 146-174 at HEAD) -> the assert-absent fires a NAMED semantic
    AssertionError, never a collection/import error.

GREEN once DELIVER removes the ``wave_gate_stacks`` property block from
``nWave/flavors/_schema.yaml`` -- completing the MOVE so the registry is the SOLE
gate-stack source and no dead flavor schema property survives.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition import DistillWiringComposition


scenarios("../slice-02-dead-flavor-gate-stack-schema-property-is-removed.feature")


# --- fixture (a fresh wiring composition per scenario) ----------------------


@pytest.fixture
def wiring() -> DistillWiringComposition:
    """A fresh DISTILL-wiring composition per scenario (the driving-port surface)."""
    return DistillWiringComposition()


# --- Given -- name the driving surface under witness ------------------------


@given("the shipped flavor schema")
def given_shipped_flavor_schema(wiring: DistillWiringComposition) -> None:
    # No state to arm -- the schema IS the shipped artifact the When reads as DATA.
    pass


# --- When -- read the shipped flavor schema ---------------------------------


@when("the flavor schema is inspected for the dead gate-stack property")
def when_schema_inspected(wiring: DistillWiringComposition) -> None:
    wiring.when_the_flavor_schema_is_inspected_for_the_dead_property()


# --- Then -- observable reader ----------------------------------------------


@then("the dead flavor gate-stack property is absent")
def then_dead_property_absent(wiring: DistillWiringComposition) -> None:
    wiring.then_the_dead_schema_property_is_absent()
