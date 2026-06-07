"""Step definitions: slice-01 -- the U1 carpaccio PreToolUse intercept.

slice-01 of F-DES-ATDD-PURE-HOOK-GATES (U1 -- ADR-030 D1).

Three ATs, max parametrize density (feedback_ats_max_pbt_parametrize_density_
2026_05_19):
  * walking-skeleton (@wiring_e2e) -- 1 example-based scenario: drive the real
    `handle_pre_tool_use` hook via the Claude Code JSON stdin protocol and
    assert a structured block reaches stdout. Genuine end-to-end, not
    fixture-folded.
  * recognition Scenario Outline -- 1 parametrized AT collapsing the M3
    positive-recognition + carpaccio-decision universe (classic / valid+clear /
    valid+reject / phase-missing / slice-missing) into one decision table.
  * order-check + handler-exception scenarios -- the M8 carpaccio-order check
    and the M1 fail-closed handler-exception path.

Layer 3 (subprocess/FS acceptance, real ledger file on tmp_path) -- example-only
sad paths, no PBT machinery (Mandate 9/11). Step bodies delegate to
`CarpaccioInterceptComposition`; no inline logic (Mandate-12 criterion 3).

RED contract: the production module
`des.adapters.drivers.hooks.carpaccio_intercept` does not exist on master and
`pre_tool_use_handler.handle_pre_tool_use` has no atdd_pure branch -- every
scenario fails RED for MISSING_FUNCTIONALITY. slice-01 GREEN ships the real U1
intercept.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .slice01_composition import CarpaccioInterceptComposition, InterceptOutcome
from .slice01_domain_types import (
    CARPACCIO_OUTCOME_BY_PHRASE,
    DISPATCH_SHAPE_BY_PHRASE,
    VERDICT_BY_PHRASE,
    SliceId,
)


scenarios("../carpaccio-intercept.feature")


@pytest.fixture
def composition(tmp_path: Path) -> CarpaccioInterceptComposition:
    """Production-wired U1 intercept composition rooted at a tmp project dir."""
    return CarpaccioInterceptComposition(tmp_path)


@pytest.fixture
def outcome_box() -> dict[str, InterceptOutcome]:
    """Carrier for the U1 intercept outcome."""
    return {}


def _outcome(outcome_box: dict[str, InterceptOutcome]) -> InterceptOutcome:
    return outcome_box["outcome"]


# --- Given -------------------------------------------------------------------


@given("an atdd_pure feature with an integrity-checked AT-completion ledger")
def given_feature_with_ledger(composition: CarpaccioInterceptComposition) -> None:
    # No setup beyond the composition root -- the ledger is created lazily on
    # the first append; this Given names the precondition the chained scenarios
    # share (Pillar 2).
    pass


@given(parsers.parse("slice-01 carries a verified slice commit in the ledger"))
def given_predecessor_verified(composition: CarpaccioInterceptComposition) -> None:
    composition.predecessor_is_verified(SliceId("slice-01"))


@given(parsers.parse("a crafter dispatch into {slice_id} carrying {dispatch}"))
def given_dispatch(
    composition: CarpaccioInterceptComposition, slice_id: str, dispatch: str
) -> None:
    composition.enter_slice(SliceId(slice_id))
    composition.use_dispatch(DISPATCH_SHAPE_BY_PHRASE[dispatch])


@given(parsers.parse("the carpaccio gate {carpaccio} the entering slice"))
def given_carpaccio_outcome(
    composition: CarpaccioInterceptComposition, carpaccio: str
) -> None:
    composition.carpaccio_will(CARPACCIO_OUTCOME_BY_PHRASE[carpaccio])


@given("the U1 intercept body raises an internal exception")
def given_handler_raises(composition: CarpaccioInterceptComposition) -> None:
    composition.handler_will_raise()


# --- When --------------------------------------------------------------------


@when("the U1 carpaccio intercept evaluates the dispatch")
def when_evaluate(
    composition: CarpaccioInterceptComposition,
    outcome_box: dict[str, InterceptOutcome],
) -> None:
    outcome_box["outcome"] = composition.evaluate()


@when("the real PreToolUse hook processes the dispatch")
def when_drive_real_hook(
    composition: CarpaccioInterceptComposition,
    outcome_box: dict[str, InterceptOutcome],
) -> None:
    outcome_box["outcome"] = composition.drive_real_pre_tool_use_hook()


# --- Then --------------------------------------------------------------------


@then(parsers.parse("the dispatch is {verdict}"))
def then_verdict(outcome_box: dict[str, InterceptOutcome], verdict: str) -> None:
    assert _outcome(outcome_box).verdict == VERDICT_BY_PHRASE[verdict]


@then(parsers.parse("the block names the {event} event"))
def then_block_event(outcome_box: dict[str, InterceptOutcome], event: str) -> None:
    assert _outcome(outcome_box).event == event


@then(parsers.parse("the carpaccio gate invocation {invocation}"))
def then_carpaccio_invocation(
    outcome_box: dict[str, InterceptOutcome], invocation: str
) -> None:
    expected_invoked = invocation == "happens"
    assert _outcome(outcome_box).carpaccio_invoked is expected_invoked
