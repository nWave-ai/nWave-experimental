"""pytest-bdd binding -- fix-floor-auto-close-cross-wave slice-02 (dual-aware DEVOPS).

The platform-architect OWNS BOTH design AND devops. The cross-wave floor
auto-close (slice-01) gates on the SINGLE-valued ``WAVE_OWNERS.get(subagent_type)
== active_wave`` and ``WAVE_OWNERS`` maps ``nw-platform-architect -> "design"``
only, so a DEVOPS-wave terminal return does NOT close the floor at HEAD (the
dual-ownership gap). slice-02 wires the dual-aware predicate (reuse the SHIPPED
``wave_dispatch_guard_policy._PLATFORM_ARCHITECT_WAVES = frozenset({"design",
"devops"})`` + ``_PLATFORM_ARCHITECT``, mirroring ``_marker_is_on_spine``) into the
close. The scorecard predicate keys on ``_PLATFORM_ARCHITECT_WAVES`` appearing in
``subagent_stop_service.py`` once DELIVER lands the wiring.

The SUT is driven ONLY through the composition-root driving port (Mandate-16):
the REAL ``SubagentStopService.validate()`` composed via
``service_factory.create_subagent_stop_service()`` (Layer-3 composition, which
ALREADY wires the ``WaveActiveWriter`` + the per-wave design/devops review
readers), over a REAL ``WaveActiveFilesystemStore`` floor seeded on disk and read
back through the production reader. The slice-01 composition
(``FloorAutoCloseComposition``) is EXTENDED, not forked.

ACTIVE-RED / live-green split (atdd_pure -- NOT @skip):
  * AC-5 (devops-close) is ACTIVE-RED: at HEAD ``WAVE_OWNERS.get(
    "nw-platform-architect") == "design" != "devops"`` so the close declines and
    the devops floor reads back STILL_ARMED -- the ``floor is cleared`` Then fires
    a semantic AssertionError (the close path IS reached; the gate-OUT ALLOWs).
  * AC-6 (design-close-preserved) is live-green: a design floor + the
    platform-architect return ALREADY closes at HEAD (``WAVE_OWNERS.get == "design"
    == "design"``) -- pins the slice-01 superset the dual-aware predicate must not
    narrow.
  * AC-7 (non-owner-devops-no-close) is live-green: a non-dual-owner return must
    leave a devops floor armed; nothing closes today for a non-owner, so it
    ALREADY holds -- pins that the dual-aware set must not OVER-close.

S1 (step-text uniqueness): the slice-02 verbs are UNIQUE to this feature ("dual
owner", "dual-owning platform-architect returns terminally", "dual-owned wave
floor is cleared / stays armed", "non-dual-owner") -- distinct from the slice-01
floor-auto-close verbs. No cross-module step shadow.
"""

from __future__ import annotations

from pytest_bdd import given, scenarios, then, when

from .steps.composition import FloorAutoCloseComposition, floor  # noqa: F401
from .steps.domain_types import WaveFloorWave


scenarios("slice-02-floor-auto-close-devops-wave.feature")


# --- Given ------------------------------------------------------------------


@given("an active devops wave floor with the platform-architect as the dual owner")
def given_devops_floor_dual_owner(floor: FloorAutoCloseComposition, tmp_path) -> None:
    floor.use_project_root(tmp_path)
    floor.given_platform_architect_floor(WaveFloorWave.DEVOPS)


@given("an active design wave floor with the platform-architect as the dual owner")
def given_design_floor_dual_owner(floor: FloorAutoCloseComposition, tmp_path) -> None:
    floor.use_project_root(tmp_path)
    floor.given_platform_architect_floor(WaveFloorWave.DESIGN)


@given("an active devops wave floor with a non-dual-owner return")
def given_devops_floor_non_dual_owner(
    floor: FloorAutoCloseComposition, tmp_path
) -> None:
    floor.use_project_root(tmp_path)
    floor.given_non_owner_under_devops_floor()


# --- When -------------------------------------------------------------------


@when("the dual-owning platform-architect returns terminally from its wave")
def when_dual_owner_returns(floor: FloorAutoCloseComposition) -> None:
    floor.when_owner_returns_through_gate_out()


@when("the non-dual-owner returns terminally from the devops wave")
def when_non_dual_owner_returns(floor: FloorAutoCloseComposition) -> None:
    floor.when_non_owner_returns_through_gate_out()


# --- Then -------------------------------------------------------------------


@then("the dual-owner return is allowed")
def then_dual_owner_return_allowed(floor: FloorAutoCloseComposition) -> None:
    floor.then_return_is_allowed()


@then("the dual-owned wave floor is cleared")
def then_dual_owned_floor_cleared(floor: FloorAutoCloseComposition) -> None:
    floor.then_floor_is_cleared()


@then("the dual-owned wave floor stays armed")
def then_dual_owned_floor_stays_armed(floor: FloorAutoCloseComposition) -> None:
    floor.then_floor_stays_armed()
