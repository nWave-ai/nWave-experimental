"""Step definitions: E7 install neighbour-preservation + fail-safe slice.

Binds the single surviving E7 `.feature` file. One production-wired driving
surface, Layer 3 composition over a sandboxed `~/.claude` (Mandate 13 —
driving-port-only): the real `AttributionPlugin` install/uninstall lifecycle
(`@real-io`).

Attribution commit rewriting is exercised by the sibling real-adapter
acceptance slice; this slice only asserts that install never stomps a
neighbour (the operator's own hooks, the existing DES guard) and never
registers an independent commit-attribution hook of its own, failing safe
when the Claude config is absent or corrupt.

Step bodies delegate to the composition root and never inline business logic
(Mandate-12 criterion 3): each body is a typed lookup plus a composition call.

State-delta (Mandate 8): the coexistence/preservation Then steps assert via
`assert_state_delta` over a port-exposed universe (the `pre-bash` guard and the
operator's own hook), so "what did NOT change" is a fail-closed claim, not an
afterthought.

Step-text is unique within this E7 directory (S1): the phrases here
(`the existing commit guard …`, `the operator's own Bash hook …`) are disjoint
from the E1-E6 sibling slice's phrases, so no pytest-bdd registry collision.
"""

from __future__ import annotations

import pytest
from nwave_ai.state_delta import assert_state_delta, unchanged
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import InstallComposition, SettingsView
from .domain_types import CHOICE_BY_PHRASE, HOME_BY_PHRASE, HomeShape


scenarios("../coexistence-and-failsafe.feature")


# ---------------------------------------------------------------------------
# Fixtures — one production-wired composition root per driving surface
# ---------------------------------------------------------------------------


@pytest.fixture
def install(sandbox_home) -> InstallComposition:
    """Production-wired composition over the real AttributionPlugin lifecycle."""
    return InstallComposition(home=sandbox_home)


# ---------------------------------------------------------------------------
# Given — sandbox shape + preference + neighbours
# ---------------------------------------------------------------------------


@given(parsers.parse("a sandboxed nWave home {home_phrase}"))
def given_home_shape(install: InstallComposition, home_phrase: str) -> None:
    _seed_home(install, HOME_BY_PHRASE[home_phrase])


@given("the operator has added their own Bash hook")
def given_operator_hook(install: InstallComposition) -> None:
    install.seed_operator_hook()


@given(parsers.parse("the operator has chosen to {choice_phrase}"))
def given_preference(install: InstallComposition, choice_phrase: str) -> None:
    install.set_preference(CHOICE_BY_PHRASE[choice_phrase])


# ---------------------------------------------------------------------------
# When — drive the real install lifecycle
# ---------------------------------------------------------------------------


@when("nWave is installed")
def when_installed(install: InstallComposition, box: dict[str, object]) -> None:
    box.setdefault("before", install.settings())
    box["message"] = install.install()
    box["after"] = install.settings()


# ---------------------------------------------------------------------------
# Then — observe settings.json hooks.PreToolUse content
# ---------------------------------------------------------------------------


@then("no commit-attribution hook is registered")
def then_attribution_absent(box: dict[str, object]) -> None:
    assert _after(box).attribution_hook_count() == 0


@then("the existing commit guard is still registered")
def then_guard_coexists(box: dict[str, object]) -> None:
    after = _after(box)
    assert_state_delta(
        before={"guard_registered": _before(box).guard_is_registered()},
        after={"guard_registered": after.guard_is_registered()},
        universe={"guard_registered"},
        expected={"guard_registered": unchanged()},
    )
    assert after.guard_is_registered()


@then("the operator's own Bash hook is still registered")
def then_operator_hook_preserved(box: dict[str, object]) -> None:
    after = _after(box)
    assert_state_delta(
        before={"operator_hook": _before(box).operator_hook_is_registered()},
        after={"operator_hook": after.operator_hook_is_registered()},
        universe={"operator_hook"},
        expected={"operator_hook": unchanged()},
    )
    assert after.operator_hook_is_registered()


@then("the install still succeeds")
def then_install_succeeds(box: dict[str, object]) -> None:
    assert box["message"] is not None


@then("the corrupt settings are left untouched")
def then_corrupt_untouched(box: dict[str, object]) -> None:
    assert _after(box).raw_text == "{ not json"


# ---------------------------------------------------------------------------
# Helpers (kept here so step bodies stay a single expression)
# ---------------------------------------------------------------------------


def _seed_home(install: InstallComposition, shape: HomeShape) -> None:
    if shape is HomeShape.GUARD_PRESENT:
        install.seed_guard()
    elif shape is HomeShape.CORRUPT:
        install.seed_corrupt_settings()
    # HomeShape.NO_CLAUDE — leave ~/.claude absent (no seeding).


def _after(box: dict[str, object]) -> SettingsView:
    return box["after"]  # type: ignore[return-value]


def _before(box: dict[str, object]) -> SettingsView:
    return box["before"]  # type: ignore[return-value]
