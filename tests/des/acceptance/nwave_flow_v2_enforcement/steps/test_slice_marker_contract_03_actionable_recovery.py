"""pytest-bdd binding for the slice-03 actionable-recovery scenarios.

Driving port (Mandate-13 driving-port-only, Layer 3 composition): the REAL
PreToolUseService.validate via the production composition root; the observable
extended here is HookDecision.recovery_suggestions. Step bodies delegate to the
composition root (composition_slice_marker_contract_03.py); no business logic in
step bodies (Mandate-12). Every step decorator's literal is unique within this
feature directory (S1) and disjoint from the other slices' literals.

Active-RED scaffold (atdd_pure -- NOT @skip): AT-3a is RED until DELIVER adds a
recovery_suggestions arg to the :159 block (the list is empty at HEAD); AT-3b's
no-leak invariant presupposes the slice-01 ALLOW path. Both fail with a semantic
AssertionError, never a collection / import / setup error.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_marker_contract_03 import RecoveryHintComposition
from .domain_types_slice_marker_contract import WaveUnderTest


scenarios("../slice-marker-contract-03-actionable-recovery.feature")


@pytest.fixture
def recovery() -> RecoveryHintComposition:
    return RecoveryHintComposition()


# --- Given -----------------------------------------------------------------


# CLASS-1 RE-EXPRESS (ADR-001 Amendment 2): trigger re-expressed markerless ->
# partial-context; the composition seeds a DES-* subset (no DES-VALIDATION) that
# still BLOCKs, preserving the recovery-message contract.
@given(
    "the design wave is active and a partial-context non-entering child arrives for recovery"
)
def given_partial_context_child_in_wave(
    recovery: RecoveryHintComposition, tmp_path: Path
) -> None:
    recovery.given_markerless_child_in_wave(tmp_path, WaveUnderTest.DESIGN)


@given("the design wave is active and this dispatch is entering for recovery")
def given_wave_entering(recovery: RecoveryHintComposition, tmp_path: Path) -> None:
    recovery.given_wave_entering(tmp_path, WaveUnderTest.DESIGN)


# --- When ------------------------------------------------------------------


@when("the partial-context in-wave child dispatch is checked for recovery")
def when_partial_context_child_checked_for_recovery(
    recovery: RecoveryHintComposition,
) -> None:
    recovery.when_markerless_child_dispatch_checked()


@when("the recognized entry dispatch is checked for recovery")
def when_entry_checked_for_recovery(recovery: RecoveryHintComposition) -> None:
    recovery.when_des_wave_only_entering_dispatch_checked()


# --- Then ------------------------------------------------------------------


@then("the bypass block names an actionable recovery fix")
def then_bypass_block_names_recovery(recovery: RecoveryHintComposition) -> None:
    recovery.then_bypass_block_names_recovery()


@then("the allowed entry carries no recovery state")
def then_allow_path_carries_no_recovery(
    recovery: RecoveryHintComposition,
) -> None:
    recovery.then_allow_path_carries_no_recovery()
