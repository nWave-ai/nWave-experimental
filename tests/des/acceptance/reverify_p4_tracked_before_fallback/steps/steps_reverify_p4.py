"""Shared step vocabulary for the P4 tracked-before fallback ATs.

Mandate-12: every step body is <=2 statements and delegates to a
``ReverifyP4Composition`` service method -- no business logic, no control
flow. The DSL emerges from the ``AtPresenceState`` enum: ONE ``@given``
decorator with an enum-coercing parser covers all four AT-presence states,
instead of one decorator per literal.

Both slice .feature files import these same steps -- shared-vocabulary
contract (Pillar 1 + Mandate 10).

Layer 3 (subprocess / real-git acceptance): example-based, no PBT (Mandate
9/11). The slice-02 outline parametrize-collapses the two refusal states.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, then, when

from .composition import ReverifyOutcome, ReverifyP4Composition
from .domain_types import AtPresenceState, P4Verdict


pytestmark = pytest.mark.acceptance


def _state(token: str) -> AtPresenceState:
    """Coerce a Gherkin presence-state token to the typed enum value."""
    return AtPresenceState(token)


# -- Given -----------------------------------------------------------------


@given(
    parsers.parse("a buried slice whose acceptance test is {presence_state}"),
    target_fixture="presence_state",
)
def given_slice_in_presence_state(
    composition: ReverifyP4Composition, presence_state: str
) -> AtPresenceState:
    """Build a real buried-slice git history in the named AT-presence state.

    One decorator, four states -- the enum is the DSL. The composition
    service owns all git-history construction (Mandate-12 SSOT).
    """
    state = _state(presence_state)
    composition.given_slice_in_presence_state(state)
    return state


# -- When ------------------------------------------------------------------


@when("the operator re-verifies the slice", target_fixture="outcome")
def when_operator_reverifies(
    composition: ReverifyP4Composition,
    capsys: pytest.CaptureFixture[str],
) -> ReverifyOutcome:
    """Drive the production reverify CLI port and capture its outcome."""
    return composition.reverify(capsys)


# -- Then ------------------------------------------------------------------


@then("the slice's acceptance-test presence is accepted")
def then_presence_accepted(outcome: ReverifyOutcome) -> None:
    """P4 accepted: no `SliceReverifyRefused`, reverify proceeded."""
    assert outcome.verdict is P4Verdict.ACCEPT, outcome.error


@then("the slice's acceptance-test presence is refused")
def then_presence_refused(outcome: ReverifyOutcome) -> None:
    """P4 refused: `SliceReverifyRefused` event, exit 1."""
    assert outcome.verdict is P4Verdict.REFUSE
    assert outcome.exit_code == 1


@then("the slice is recorded as verified in the completion ledger")
def then_slice_verified(composition: ReverifyP4Composition) -> None:
    """The recovered slice carries a `SliceCommitVerified` ledger record."""
    assert composition.ledger_has_verified_slice()


@then("the slice is not recorded as verified in the completion ledger")
def then_slice_not_verified(composition: ReverifyP4Composition) -> None:
    """A refused slice appends nothing -- preconditions run before any gate."""
    assert not composition.ledger_has_verified_slice()
