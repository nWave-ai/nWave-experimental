"""pytest-bdd binding for the INFERRED fallback strand scenarios (slice-07d).

Driving port (Mandate-13 driving-port-only, Layer 4 wiring): the REAL
PreToolUse hook adapter as a subprocess black box (hook-protocol stdin JSON)
over a tmp ``project_root`` -- the composition seat of the net-new fallback
branch (reader NoWaveActive + valid ``declared_wave`` -> ``arm_inferred`` ->
proceed wave-entering in the SAME pass). AT-2 arms first via the REAL
prompt-submission anchor subprocess. Observables: hook exit/reason + the
floor record at the DESIGN-PINNED path.

Step bodies delegate to the composition root (``composition_slice_07d.py``);
no business logic in step bodies (Mandate-12). Every step decorator's literal
is unique within this feature directory (S1) and disjoint from the
slice-04 / 07 / 07b / 07c literals.

Active-RED scaffold (ADR-025 + ADR-028, atdd_pure -- NOT @skip): until
DELIVER ships the ``DES-WAVE`` marker parse (``DesMarkers.declared_wave``),
``WaveActivationService.arm_inferred`` and the adapter fallback branch, the
declaration is an inert comment and an empty floor stays empty -- AT-1 fails
with a semantic ``AssertionError`` (ALLOWED + no floor record where the
same-pass INFERRED gating is expected), never a collection / import / setup
error. AT-2 (I3 no-clobber) and AT-3 (K2 / S1 untouched, outline x2) are
preservation-GREEN at HEAD and pin the contract end-to-end through DELIVER.

SUT STATE MACHINE (C2): see the .feature header + composition docstring --
{NO_WAVE, ARMED(COMMAND), ARMED(INFERRED)} with declare-arms-INFERRED-and-
gates-same-pass / COMMAND-never-clobbered / no-usable-declaration-stays-
untouched transitions.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_07d import InferredFallbackComposition
from .domain_types_slice_07d import WaveDeclarationShape


scenarios("../slice-07d-inferred-fallback-strand.feature")


@pytest.fixture
def fallback() -> InferredFallbackComposition:
    return InferredFallbackComposition()


# --- Given -----------------------------------------------------------------


@given("no wave has been armed in the project")
def given_no_wave_armed(fallback: InferredFallbackComposition, tmp_path: Path) -> None:
    fallback.given_no_wave_armed(tmp_path)


@given("the discuss wave is already armed by the operator's explicit command")
def given_discuss_armed_by_command(
    fallback: InferredFallbackComposition, tmp_path: Path
) -> None:
    fallback.given_discuss_armed_by_command(tmp_path)


@given("the product requirements for entering discuss are missing")
def given_preconditions_missing(fallback: InferredFallbackComposition) -> None:
    fallback.given_preconditions_missing()


@given("the product requirements for entering discuss are satisfied")
def given_preconditions_satisfied(fallback: InferredFallbackComposition) -> None:
    fallback.given_preconditions_satisfied()


# --- When ------------------------------------------------------------------


@when("a dispatch declaring the discuss wave is checked on the empty floor")
def when_declaring_dispatch_on_empty_floor(
    fallback: InferredFallbackComposition,
) -> None:
    fallback.when_declaring_dispatch_checked()


@when("a dispatch declaring the discuss wave is checked on the armed floor")
def when_declaring_dispatch_on_armed_floor(
    fallback: InferredFallbackComposition,
) -> None:
    fallback.when_declaring_dispatch_checked()


@when(parsers.parse("an ad-hoc dispatch with {declaration} is checked"))
def when_adhoc_dispatch_checked(
    fallback: InferredFallbackComposition, declaration: str
) -> None:
    fallback.when_adhoc_dispatch_checked(WaveDeclarationShape(declaration))


# --- Then ------------------------------------------------------------------


@then("the declaring dispatch is allowed with a greenfield advisory in the same pass")
def then_allowed_greenfield_advisory_same_pass(
    fallback: InferredFallbackComposition,
) -> None:
    fallback.then_allowed_greenfield_advisory_same_pass()


@then("the floor records the discuss wave as inferred from the dispatch")
def then_floor_records_inferred_discuss(
    fallback: InferredFallbackComposition,
) -> None:
    fallback.then_floor_records_inferred_discuss()


@then("the inferred entry carries no pending flag")
def then_inferred_entry_not_pending(fallback: InferredFallbackComposition) -> None:
    fallback.then_inferred_entry_not_pending()


@then("the armed dispatch is allowed to proceed")
def then_armed_dispatch_allowed(fallback: InferredFallbackComposition) -> None:
    fallback.then_armed_dispatch_allowed()


@then("the floor keeps the operator's command provenance")
def then_floor_keeps_command_provenance(
    fallback: InferredFallbackComposition,
) -> None:
    fallback.then_floor_keeps_command_provenance()


@then("the dispatch is allowed untouched by any wave gate")
def then_allowed_untouched(fallback: InferredFallbackComposition) -> None:
    fallback.then_allowed_untouched()


@then("no wave record is created by the dispatch")
def then_no_wave_record_created(fallback: InferredFallbackComposition) -> None:
    fallback.then_no_wave_record_created()
