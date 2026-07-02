"""slice-01 acceptance: per-step review toggle resolved through DESConfig.

Driving port (Mandate-13 / DSN-1): the REAL ``DESConfig.resolve_review_steps()``
read over a REAL ``.nwave/des-config.json`` under ``tmp_path`` (in-process,
real-IO -- the feature's driving surface is the config-adapter method consulted
by the nw-distill review dispatch, NOT a CLI, so no interpreter fork is warranted
per the Architecture-of-Reference in-process Driving default).

Active-RED topology (nw-distill-red-scaffolding P1-P4):
  P1  module-top imports ONLY the stable ``DESConfig`` entry (present at HEAD);
      the not-yet-authored ``des.domain.rigor.review_step_registry`` resolver is
      NEVER imported here -> collection cannot ImportError -> RED, not BROKEN.
  P2  the driving call goes through ``DESConfig.resolve_review_steps()``
      in-process.
  P3  the absent behaviour is reached at RUNTIME inside that call (the scaffold
      method body raises) -- a runtime value, not a collection error.
  P4  the failure is a semantic ``AssertionError`` raised by the scaffold; the
      meaningful ``Then`` membership assertions go live once DELIVER implements
      the resolver.

Resolution is a pure read (config in -> active set out, config file unchanged):
@contract-shape:pure-function. No observable state mutates -> Mandate-8 state-
delta does not apply; example-based assertions per Mandate-9 (layer-3 example-only).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when

from des.adapters.driven.config.des_config import DESConfig

from .conftest import _write_project_config


scenarios("../slice-01-per-step-toggle.feature")


# ---------------------------------------------------------------------------
# Given: real project rigor configs under tmp_path
# ---------------------------------------------------------------------------


@given(
    parsers.parse('a project rigor config that disables the "{step_id}" review step')
)
def given_step_disabled(ctx: dict[str, Any], tmp_path: Path, step_id: str) -> None:
    ctx["config_path"] = _write_project_config(
        tmp_path,
        {"review_enabled": True, "review_steps": {step_id: {"enabled": False}}},
    )
    ctx["absent_global"] = tmp_path / "home" / ".nwave" / "global-config.json"


@given("a project rigor config with review enabled and no per-step toggles")
def given_no_toggles(ctx: dict[str, Any], tmp_path: Path) -> None:
    ctx["config_path"] = _write_project_config(tmp_path, {"review_enabled": True})
    ctx["absent_global"] = tmp_path / "home" / ".nwave" / "global-config.json"


@given(parsers.parse('a project rigor config that enables the "{step_id}" review step'))
def given_step_enabled(ctx: dict[str, Any], tmp_path: Path, step_id: str) -> None:
    ctx["config_path"] = _write_project_config(
        tmp_path,
        {"review_enabled": True, "review_steps": {step_id: {"enabled": True}}},
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
    # Active-RED: the scaffold body raises AssertionError here (P3/P4).
    # Once DELIVER wires the resolver, this yields a ResolvedReviewStepSet and
    # the Then membership assertions below take over.
    ctx["resolved"] = config.resolve_review_steps()


# ---------------------------------------------------------------------------
# Then: observable membership in the active reviewer set
# ---------------------------------------------------------------------------


def _active_ids(ctx: dict[str, Any]) -> set[str]:
    return {step.id for step in ctx["resolved"].active()}


@then(parsers.parse('the "{step_id}" review step is not among the active reviewers'))
def then_step_absent(ctx: dict[str, Any], step_id: str) -> None:
    assert step_id not in _active_ids(ctx)


@then(parsers.parse('the "{step_id}" review step is among the active reviewers'))
def then_step_present(ctx: dict[str, Any], step_id: str) -> None:
    assert step_id in _active_ids(ctx)
