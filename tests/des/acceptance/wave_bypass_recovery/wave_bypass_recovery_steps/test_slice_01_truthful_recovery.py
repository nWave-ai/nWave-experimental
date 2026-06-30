"""pytest-bdd binding for fix-wave-bypass-recovery-truthful slice-01 scenarios.

Driving surface (Mandate-13 driving-port-only, Layer 3 composition): the REAL
spine service via the production composition root; the observable is
``HookDecision.recovery_suggestions`` on a WAVE_MARKER_BYPASS block. Step bodies
delegate to the composition root
(``composition_slice_01_truthful_recovery.py``); no business logic in step bodies
(Mandate-12 criterion 3 -- each body is a single composition call).

Active-RED scaffold (atdd_pure -- NOT @skip): RED until DELIVER replaces the
untruthful DES-WAVE-only recovery item with the A2 stale-floor clear hint naming
``des wave-clear``. Every assertion fails with a semantic AssertionError, never a
collection / import / setup error.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_01_truthful_recovery import TruthfulRecoveryComposition


scenarios("../slice-wave-bypass-recovery-01-truthful-recovery.feature")


@pytest.fixture
def recovery() -> TruthfulRecoveryComposition:
    return TruthfulRecoveryComposition()


# --- Given -----------------------------------------------------------------


@given("a stale inferred wave floor the dispatch is not entering")
def given_stale_inferred_floor(
    recovery: TruthfulRecoveryComposition, tmp_path: Path
) -> None:
    recovery.given_stale_inferred_floor(tmp_path)


# --- When ------------------------------------------------------------------


# CLASS-1 RE-EXPRESS (ADR-001 Amendment 2): trigger re-expressed markerless ->
# partial-context; the composition seeds a DES-* subset (no DES-VALIDATION) that
# still fires WAVE_MARKER_BYPASS, preserving the JOB-019 truthful-recovery oracle.
@when("a partial-context in-wave dispatch is vetoed for the bypass")
def when_partial_context_dispatch_vetoed(
    recovery: TruthfulRecoveryComposition,
) -> None:
    recovery.when_markerless_dispatch_vetoed()


# --- Then ------------------------------------------------------------------


@then("the wave-bypass veto still blocks the dispatch")
def then_wave_marker_bypass_still_blocks(
    recovery: TruthfulRecoveryComposition,
) -> None:
    recovery.then_wave_marker_bypass_still_blocks()


@then("the block reason still names the wave-bypass error")
def then_block_reason_names_wave_marker_bypass(
    recovery: TruthfulRecoveryComposition,
) -> None:
    recovery.then_block_reason_names_wave_marker_bypass()


@then("the first recovery item carries the wave's real markers")
def then_first_recovery_item_carries_real_markers(
    recovery: TruthfulRecoveryComposition,
) -> None:
    recovery.then_first_recovery_item_carries_real_markers()


@then("the second recovery item names the sanctioned wave-clear command")
def then_second_recovery_item_names_sanctioned_clear(
    recovery: TruthfulRecoveryComposition,
) -> None:
    recovery.then_second_recovery_item_names_sanctioned_clear()


@then("no recovery item proposes the phantom wave-entry action")
def then_no_recovery_item_proposes_phantom_wave_entry(
    recovery: TruthfulRecoveryComposition,
) -> None:
    recovery.then_no_recovery_item_proposes_phantom_wave_entry()
