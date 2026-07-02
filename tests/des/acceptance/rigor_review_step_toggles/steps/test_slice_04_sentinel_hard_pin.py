"""slice-04 acceptance: Sentinel is an un-disable-able hard-pinned review step.

Driving port (Mandate-13 / DSN-1): the REAL ``DESConfig.resolve_review_steps()``
read over a REAL ``.nwave/des-config.json`` under ``tmp_path`` (in-process,
real-IO -- the feature's driving surface is the config-adapter method consulted
by the nw-distill review dispatch, NOT a CLI, so no interpreter fork is warranted
per the Architecture-of-Reference in-process Driving default).

Active-RED topology (nw-distill-red-scaffolding P1-P4):
  P1  module-top imports ONLY the stable ``DESConfig`` entry (present at HEAD,
      shipped by slice-01); the pure-domain catalog/resolver is NEVER imported
      here -> collection cannot ImportError -> RED, not BROKEN.
  P2  the driving call goes through ``DESConfig.resolve_review_steps()``
      in-process; that method + ``ResolvedReviewStepSet.active()`` are shipped
      (slices 01/02/03 green), so the call resolves cleanly to a real set.
  P3  the absent behaviour is reached at RUNTIME: ``ResolvedReviewStepSet`` does
      NOT yet expose an ``is_always_on(step_id)`` accessor, so the explicit
      hard-pin observable is missing today.
  P4  the failure is a semantic ``AssertionError`` -- the hard-pin ``Then``
      ``getattr``-guards the absent accessor (``callable(None) is False``) and
      asserts a guidance message, NOT a raw AttributeError. DELIVER adds
      ``ResolvedReviewStepSet.is_always_on(step_id)`` and the hard-pin ``Then``s
      take over. The membership ``Then``s (#1-#3) are GREEN-today regression
      locks (the ``always_on`` short-circuit already makes ``sentinel`` inert to
      every disabling attempt).

RED strategy (explicit, per the slice-04 task): scenarios #1-#3 prove the
un-disable-able CONTRACT and are green-today (vacuous-by-design short-circuit);
scenarios #4-#5 drive a NOT-YET-EXISTING explicit hard-pin observable
(``is_always_on``) so the slice has a GENUINE active-RED that is a semantic
AssertionError on a missing surface, not a vacuous green and not a BROKEN import.

Resolution is a pure read (config in -> active set out, config file unchanged):
@contract-shape:pure-function. No observable state mutates -> Mandate-8 state-
delta does not apply; example-based assertions per Mandate-9 (layer-3 example-only).

EXTEND of the slice-01 binding shape: ``when_resolve`` + the
``{step_id}``-parameterized membership ``Then``s are mirrored inline (kept
per-module, unconsolidated -- see ``steps/conftest.py``). The ``ctx`` fixture
and ``_write_project_config`` helper were consolidated into
``steps/conftest.py`` at feature-end (whole-feature L1-L6 batch refactor).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when

from des.adapters.driven.config.des_config import DESConfig

from .conftest import _write_project_config


scenarios("../slice-04-sentinel-hard-pin.feature")


# ---------------------------------------------------------------------------
# Given: real project rigor configs under tmp_path
# ---------------------------------------------------------------------------


@given("a project rigor config with review enabled and no per-step toggles")
def given_no_toggles(ctx: dict[str, Any], tmp_path: Path) -> None:
    ctx["config_path"] = _write_project_config(tmp_path, {"review_enabled": True})
    ctx["absent_global"] = tmp_path / "home" / ".nwave" / "global-config.json"


@given(
    parsers.parse('a project rigor config that disables the "{step_id}" review step')
)
def given_step_disabled(ctx: dict[str, Any], tmp_path: Path, step_id: str) -> None:
    ctx["config_path"] = _write_project_config(
        tmp_path,
        {"review_enabled": True, "review_steps": {step_id: {"enabled": False}}},
    )
    ctx["absent_global"] = tmp_path / "home" / ".nwave" / "global-config.json"


@given("a project rigor config with review disabled at the profile level")
def given_review_disabled(ctx: dict[str, Any], tmp_path: Path) -> None:
    ctx["config_path"] = _write_project_config(tmp_path, {"review_enabled": False})
    ctx["absent_global"] = tmp_path / "home" / ".nwave" / "global-config.json"


@given(
    parsers.parse(
        'a project rigor config that disables review and the "{step_id}" review step'
    )
)
def given_review_and_step_disabled(
    ctx: dict[str, Any], tmp_path: Path, step_id: str
) -> None:
    ctx["config_path"] = _write_project_config(
        tmp_path,
        {"review_enabled": False, "review_steps": {step_id: {"enabled": False}}},
    )
    ctx["absent_global"] = tmp_path / "home" / ".nwave" / "global-config.json"


# ---------------------------------------------------------------------------
# When: drive the real DESConfig method in-process
# ---------------------------------------------------------------------------


@when("the active review steps are resolved for that project")
def when_resolve(ctx: dict[str, Any]) -> None:
    config = DESConfig(
        config_path=ctx["config_path"],
        global_config_path=ctx["absent_global"],
    )
    ctx["resolved"] = config.resolve_review_steps()


# ---------------------------------------------------------------------------
# Then: observable membership in the active reviewer set (GREEN-today locks)
# ---------------------------------------------------------------------------


def _active_ids(ctx: dict[str, Any]) -> set[str]:
    return {step.id for step in ctx["resolved"].active()}


@then(parsers.parse('the "{step_id}" review step is among the active reviewers'))
def then_step_present(ctx: dict[str, Any], step_id: str) -> None:
    assert step_id in _active_ids(ctx)


@then(parsers.parse('the "{step_id}" review step is not among the active reviewers'))
def then_step_absent(ctx: dict[str, Any], step_id: str) -> None:
    assert step_id not in _active_ids(ctx)


# ---------------------------------------------------------------------------
# Then: explicit hard-pin observable (ACTIVE-RED -- not-yet-present accessor)
# ---------------------------------------------------------------------------


def _is_always_on(ctx: dict[str, Any]):
    """Fetch the not-yet-present ``is_always_on`` accessor, guarded for RED.

    Returns the bound accessor; the caller asserts it is callable so a missing
    accessor surfaces as a semantic ``AssertionError`` (guidance), NOT a raw
    ``AttributeError`` -- this is the slice-04 RED-not-BROKEN mechanism.
    """
    return getattr(ctx["resolved"], "is_always_on", None)


@then(
    parsers.parse(
        'the resolved set reports the "{step_id}" review step as hard-pinned always-on'
    )
)
def then_hard_pinned(ctx: dict[str, Any], step_id: str) -> None:
    is_always_on = _is_always_on(ctx)
    assert callable(is_always_on), (
        "ResolvedReviewStepSet must expose is_always_on(step_id) so the hard-pin "
        "on Sentinel is an explicit, inspectable contract rather than an implicit "
        "always_on short-circuit -- DELIVER target for slice-04"
    )
    assert is_always_on(step_id) is True, (
        f"{step_id!r} must be reported as a hard-pinned always-on review step "
        "that no config can disable"
    )


@then(
    parsers.parse(
        'the resolved set does not report the "{step_id}" review step '
        "as hard-pinned always-on"
    )
)
def then_not_hard_pinned(ctx: dict[str, Any], step_id: str) -> None:
    is_always_on = _is_always_on(ctx)
    assert callable(is_always_on), (
        "ResolvedReviewStepSet must expose is_always_on(step_id) so the hard-pin "
        "is specific to Sentinel and falsifiable for cost-driven reviewers -- "
        "DELIVER target for slice-04"
    )
    assert is_always_on(step_id) is False, (
        f"{step_id!r} is a cost-driven (toggleable) reviewer and must NOT be "
        "reported as hard-pinned always-on"
    )
