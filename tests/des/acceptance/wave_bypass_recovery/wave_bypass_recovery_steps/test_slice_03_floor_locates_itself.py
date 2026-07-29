"""pytest-bdd binding for fix-wave-bypass-recovery-truthful slice-03 scenarios.

Driving surface (Mandate-13 driving-port-only, Layer 3 composition): the REAL
spine service via the production composition root, same seam as slice-01; the
observable is ``HookDecision.reason`` on a WAVE_MARKER_BYPASS block. Step
bodies delegate to the SAME composition root as slice-01
(``composition_slice_01_truthful_recovery.py`` -- one Given/When precondition,
reused by both slices per Mandate-12 SSOT); no business logic in step bodies.

Active-RED scaffold (atdd_pure -- NOT @skip): RED until DELIVER extends
``_describe_wave_floor`` to state the floor's absolute path, the resolved
project root, and (for INFERRED) the concrete deduction signal. Every
assertion fails with a semantic AssertionError, never a collection / import /
setup error.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_01_truthful_recovery import TruthfulRecoveryComposition


scenarios("../slice-wave-bypass-recovery-03-floor-locates-itself.feature")


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


@when("a partial-context in-wave dispatch is vetoed for the bypass")
def when_partial_context_dispatch_vetoed(
    recovery: TruthfulRecoveryComposition,
) -> None:
    recovery.when_markerless_dispatch_vetoed()


# --- Then ------------------------------------------------------------------


@then("the reason names the floor file's absolute path")
def then_reason_names_floor_absolute_path(
    recovery: TruthfulRecoveryComposition,
) -> None:
    recovery.then_reason_names_floor_absolute_path()


@then("the reason names the resolved project root")
def then_reason_names_resolved_project_root(
    recovery: TruthfulRecoveryComposition,
) -> None:
    recovery.then_reason_names_resolved_project_root()


@then("the reason names the concrete signal the inferred floor was deduced from")
def then_reason_names_the_inferred_signal(
    recovery: TruthfulRecoveryComposition,
) -> None:
    recovery.then_reason_names_the_inferred_signal()
