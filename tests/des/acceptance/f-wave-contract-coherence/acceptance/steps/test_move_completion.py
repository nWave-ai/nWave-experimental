"""pytest-bdd binding for f-wave-contract-coherence slice-06 (MOVE-completion).

Driving surface (Mandate-13 driving-port-only): SHIPPED-artifact reads (the flavor
files, the registry, the registry schema, the product glossary) parsed via the
production stdlib-only subset parser, plus the REAL flavor_dispatcher
registry-resolution seam for AT-17 (Layer 3 composition). Step bodies delegate to the
composition root (composition_move_completion.py); no business logic in step bodies
(Mandate-12). The <locus> / <boundary> parameters parse once into typed enums, so one
scenario shape ranges over the two flavor loci / the two DISCUSS boundaries.

AT-15 PREMISE-UPDATED by f-distill-wiring-to-registry slice-02 (CT-9 / DDD-9): slice-01
of that feature COMPLETED the registry migration AT-15 anticipated -- it REMOVED the
flavor wave_gate_stacks block and MOVE-completed the `distill` co-tenant (self-attest /
verify-test-runner) into nWave/waves/distill.yaml gate-out. So AT-15 is re-pointed to
assert the migrated-to-registry truth: the block is gone (GREEN), the `distill` co-tenant
resolves from the LIVE registry (GREEN), and the dead flavor schema $defs is removed (the
leg-c active-RED -- still present at HEAD, DELIVER removes it per DDD-9). f-wave STAYS
DONE (this is honest maintenance, not a re-opening). AT-17/AT-18 keep their own
active-RED legs (spine re-point / glossary terms). Every case fails with a semantic
AssertionError, never a collection / import / setup error.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_move_completion import MoveCompletionComposition
from .domain_types import WaveBoundary


scenarios("../move-completion.feature")


@pytest.fixture
def move() -> MoveCompletionComposition:
    return MoveCompletionComposition()


# --- Given -----------------------------------------------------------------


@given("the canonical wave-contract registry is the sole gate-stack source")
def given_registry_is_sole_gate_stack_source(
    move: MoveCompletionComposition,
) -> None:
    move.given_registry_is_sole_gate_stack_source()


# --- When ------------------------------------------------------------------


@when(
    "the maintainer inspects the shipped flavor wave_gate_stacks block and its schema"
)
def when_maintainer_inspects_flavor_block_and_schema(
    move: MoveCompletionComposition,
) -> None:
    move.when_maintainer_inspects_flavor_block_and_schema()


@when("the maintainer inspects the shipped classic flavor")
def when_maintainer_inspects_classic_flavor(
    move: MoveCompletionComposition,
) -> None:
    move.when_maintainer_inspects_classic_flavor()


@when(
    parsers.parse(
        "the dispatcher resolves the DISCUSS {boundary} stack with no flavor "
        "block present"
    )
)
def when_dispatcher_resolves_discuss_stack_with_no_flavor_block(
    move: MoveCompletionComposition, boundary: str, tmp_path: Path
) -> None:
    move.when_dispatcher_resolves_discuss_stack_with_no_flavor_block(
        WaveBoundary(boundary), tmp_path
    )


@when("the maintainer inspects the registry schema and the product glossary")
def when_maintainer_inspects_schema_and_glossary(
    move: MoveCompletionComposition,
) -> None:
    move.when_maintainer_inspects_schema_and_glossary()


# --- Then ------------------------------------------------------------------


@then("the flavor block no longer declares a `discuss` gate stack")
def then_flavor_block_no_longer_declares_discuss(
    move: MoveCompletionComposition,
) -> None:
    move.then_flavor_block_no_longer_declares_discuss()


@then(
    "the flavor wave_gate_stacks block is gone and the `distill` co-tenant "
    "resolves from the registry while the dead schema $defs is removed"
)
def then_distill_cotenant_migrated_to_registry(
    move: MoveCompletionComposition,
) -> None:
    move.then_distill_cotenant_migrated_to_registry()


@then(
    "the classic flavor carries no wave_gate_stacks declaration before or "
    "after the MOVE"
)
def then_classic_carries_no_wave_gate_stacks(
    move: MoveCompletionComposition,
) -> None:
    move.then_classic_carries_no_wave_gate_stacks()


@then(
    parsers.parse(
        "the resolved {boundary} gate-id sequence is sourced from the registry "
        "and equals the sequence f-declarative-gate-composition guarantees"
    )
)
def then_registry_sourced_sequence_equals_dgc_guarantee(
    move: MoveCompletionComposition, boundary: str
) -> None:
    move.then_registry_sourced_sequence_equals_dgc_guarantee(WaveBoundary(boundary))


@then(
    "the registry schema reserves an overrides hook and the glossary defines "
    "the wave-contract-registry vocabulary"
)
def then_overrides_hook_and_glossary_terms_present(
    move: MoveCompletionComposition,
) -> None:
    move.then_overrides_hook_and_glossary_terms_present()
