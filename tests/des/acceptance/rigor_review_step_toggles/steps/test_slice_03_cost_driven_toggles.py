"""slice-03 acceptance: the three cost-driven DISTILL reviewers toggle independently.

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
      (slices 01/02 green), so the call resolves cleanly to a real set.
  P3  the absent behaviour is reached at RUNTIME: the catalog ships with only
      ``eclipse`` + ``sentinel`` today, so ``architect`` / ``forge`` are simply
      absent from the resolved ``.active()`` ids.
  P4  the failure is a semantic ``AssertionError`` on membership -- a scenario
      asserting "architect/forge is among the active reviewers" fails because
      ``architect``/``forge`` is not yet in the catalog ids (a value mismatch,
      NOT a KeyError/AttributeError). DELIVER adds the two catalog entries and
      the membership ``Then``s take over.

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


scenarios("../slice-03-cost-driven-toggles.feature")


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


@given(
    parsers.parse(
        'a project rigor config that disables the "{first}" and "{second}" review steps'
    )
)
def given_two_steps_disabled(
    ctx: dict[str, Any], tmp_path: Path, first: str, second: str
) -> None:
    ctx["config_path"] = _write_project_config(
        tmp_path,
        {
            "review_enabled": True,
            "review_steps": {
                first: {"enabled": False},
                second: {"enabled": False},
            },
        },
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
# Then: observable membership in the active reviewer set
# ---------------------------------------------------------------------------


def _active_ids(ctx: dict[str, Any]) -> set[str]:
    return {step.id for step in ctx["resolved"].active()}


@then(parsers.parse('the "{step_id}" review step is among the active reviewers'))
def then_step_present(ctx: dict[str, Any], step_id: str) -> None:
    assert step_id in _active_ids(ctx)


@then(parsers.parse('the "{step_id}" review step is not among the active reviewers'))
def then_step_absent(ctx: dict[str, Any], step_id: str) -> None:
    assert step_id not in _active_ids(ctx)
