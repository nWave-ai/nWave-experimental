"""pytest-bdd binding for the fix-actionable-veto-recovery slice-01 scenarios.

Driving surface (Mandate-13 driving-port-only, Layer 3 composition): the REAL
spine services via the production composition root; the observable extended here
is ``HookDecision.recovery_suggestions``. Step bodies delegate to the composition
root (composition_actionable_veto_recovery.py); no business logic in step bodies
(Mandate-12). The ``<site>`` parameter is parsed once into the typed ``VetoSite``
enum, so ONE scenario shape ranges over the 6 enumerated bare-veto sites.

Active-RED scaffold (atdd_pure -- NOT @skip): each parametrized case is RED until
DELIVER adds a recovery_suggestions arg to that site's block (the list is empty at
HEAD). Every case fails with a semantic AssertionError, never a collection /
import / setup error.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_actionable_veto_recovery import ActionableRecoveryComposition
from .domain_types_actionable_veto_recovery import VetoSite


scenarios("../slice-actionable-veto-recovery-01-walking-skeleton.feature")


@pytest.fixture
def recovery() -> ActionableRecoveryComposition:
    return ActionableRecoveryComposition()


# --- Given -----------------------------------------------------------------


@given(parsers.parse("the spine is armed for the {site} veto"))
def given_spine_armed_for_site(
    recovery: ActionableRecoveryComposition, site: str, tmp_path: Path
) -> None:
    recovery.given_bare_veto_site(tmp_path, VetoSite[site])


# --- When ------------------------------------------------------------------


@when("the vetoed dispatch is checked for recovery")
def when_dispatch_checked_for_recovery(
    recovery: ActionableRecoveryComposition,
) -> None:
    recovery.when_dispatch_checked_for_recovery()


# --- Then ------------------------------------------------------------------


@then(parsers.parse("the {site} veto still blocks the dispatch"))
def then_veto_still_blocks(recovery: ActionableRecoveryComposition, site: str) -> None:
    recovery.then_veto_still_blocks()


@then("the block carries a non-empty recovery list")
def then_block_carries_non_empty_recovery(
    recovery: ActionableRecoveryComposition,
) -> None:
    recovery.then_block_carries_non_empty_recovery()


@then(parsers.parse("the recovery names the fix specific to the {site} veto"))
def then_recovery_names_specific_fix(
    recovery: ActionableRecoveryComposition, site: str
) -> None:
    recovery.then_recovery_names_specific_fix()
