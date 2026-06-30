"""pytest-bdd binding -- fix-floor-auto-close-cross-wave slice-01.

The wave-active floor auto-closes on the wave OWNER's attested terminal gate-OUT
PASS (Option A, Ale 2026-06-23). The SUT is driven ONLY through the
composition-root driving port (Mandate-16, Driving-Port-Only):

  * the REAL ``SubagentStopService.validate()`` composed via
    ``service_factory.create_subagent_stop_service()`` (Layer-3 composition), over
    a REAL ``WaveActiveFilesystemStore`` floor seeded on disk and read back through
    the production reader.
  * the REAL shipped ``PreToolUseService`` for the AC-2 in-wave sub-dispatch path.

Step bodies delegate to the composition root (Mandate-15; <=2 statements, the
final statement a composition call, no control flow). The Examples ``owner``
column is coerced to the typed ``WaveOwner`` enum at the step boundary.

ACTIVE-RED / live-green split (atdd_pure -- NOT @skip):
  * AC-1 (cross-wave-close) is ACTIVE-RED: at HEAD nothing closes the floor on the
    owner's terminal PASS (the service consumes a read-only reader; the context
    carries no subagent_type), so the floor reads back STILL_ARMED and the
    ``floor is cleared`` Then fires a semantic AssertionError.
  * AC-2 (in-wave-persist) + AC-3 (non-terminal-no-close) + AC-4 (veto-unchanged)
    are live-green regression guards: they assert behaviors the current code
    ALREADY exhibits, pinning the invariants the close must not break.

S1 (step-text uniqueness): the auto-close verbs are UNIQUE to this feature
("active wave floor owned by", "the wave owner returns through the attested
gate-OUT", "the wave-active floor is cleared / stays armed", "review-verdict
veto") -- distinct vocabulary from the slice-01 wave-dispatch-exemption verbs. No
cross-module step shadow.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, scenarios, then, when

from .steps.composition import FloorAutoCloseComposition, floor  # noqa: F401
from .steps.domain_types import WaveOwner


scenarios("slice-01-floor-auto-close-cross-wave.feature")


_OWNER_BY_LABEL = {
    "nw-product-owner": WaveOwner.PRODUCT_OWNER,
    "nw-solution-architect": WaveOwner.SOLUTION_ARCHITECT,
    "nw-platform-architect": WaveOwner.PLATFORM_ARCHITECT,
    "nw-acceptance-designer": WaveOwner.ACCEPTANCE_DESIGNER,
}


# --- Given ------------------------------------------------------------------


@given(parsers.parse('an active wave floor owned by "{owner}"'))
def given_active_floor_owned_by(
    floor: FloorAutoCloseComposition, tmp_path, owner: str
) -> None:
    floor.use_project_root(tmp_path)
    floor.given_active_floor_owned_by(_OWNER_BY_LABEL[owner])


@given(
    parsers.parse('an active wave floor for a "{owner}" wave with a non-owner return')
)
def given_active_floor_non_owner(
    floor: FloorAutoCloseComposition, tmp_path, owner: str
) -> None:
    floor.use_project_root(tmp_path)
    floor.given_active_floor_for_non_owner_return(_OWNER_BY_LABEL[owner])


# --- When -------------------------------------------------------------------


@when("the wave owner returns through the attested gate-OUT")
def when_owner_returns(floor: FloorAutoCloseComposition) -> None:
    floor.when_owner_returns_through_gate_out()


@when("the non-owner returns through the attested gate-OUT")
def when_non_owner_returns(floor: FloorAutoCloseComposition) -> None:
    floor.when_non_owner_returns_through_gate_out()


@when("the in-wave sub-dispatch is evaluated")
def when_in_wave(floor: FloorAutoCloseComposition) -> None:
    floor.when_in_wave_sub_dispatch_is_evaluated()


@when("the wave owner returns with a review-verdict veto")
def when_owner_returns_veto(floor: FloorAutoCloseComposition) -> None:
    floor.when_owner_returns_with_review_veto()


# --- Then -------------------------------------------------------------------


@then("the return is allowed")
def then_return_allowed(floor: FloorAutoCloseComposition) -> None:
    floor.then_return_is_allowed()


@then("the return is blocked")
def then_return_blocked(floor: FloorAutoCloseComposition) -> None:
    floor.then_return_is_blocked()


@then("the wave-active floor is cleared")
def then_floor_cleared(floor: FloorAutoCloseComposition) -> None:
    floor.then_floor_is_cleared()


@then("the wave-active floor stays armed")
def then_floor_stays_armed(floor: FloorAutoCloseComposition) -> None:
    floor.then_floor_stays_armed()
