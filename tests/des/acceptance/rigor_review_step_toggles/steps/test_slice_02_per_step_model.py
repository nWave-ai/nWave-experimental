"""slice-02 acceptance: per-step review MODEL resolved through DESConfig.

Driving port (Mandate-13 / DSN-1): the REAL ``DESConfig.resolve_review_steps()``
read over a REAL ``.nwave/des-config.json`` under ``tmp_path`` (in-process,
real-IO -- the feature's driving surface is the config-adapter method consulted
by the nw-distill review dispatch, NOT a CLI, so no interpreter fork is warranted
per the Architecture-of-Reference in-process Driving default). Mirrors the
slice-01 binding-module / inline-fixture pattern.

Active-RED topology (nw-distill-red-scaffolding P1-P4):
  P1  module-top imports ONLY the stable ``DESConfig`` entry (present at HEAD);
      the per-step ``model`` accessor is NEVER referenced at module-top -> no
      ImportError / AttributeError at collection -> RED, not BROKEN.
  P2  the driving call goes through ``DESConfig.resolve_review_steps()``
      in-process (shipped + green since slice-01).
  P3  the absent behaviour (per-step model resolution) is reached at RUNTIME:
      ``ResolvedReviewStepSet.model_for`` does not yet exist, so the ``Then``
      asks for it via ``getattr(resolved, "model_for", None)``.
  P4  the failure is a semantic ``AssertionError`` (the guard asserts the
      accessor is present, then asserts the resolved model equals the expected
      value) -- NOT an ``AttributeError`` (which would be BROKEN). DELIVER adds
      the ``model_for`` accessor + threads ``reviewer_model`` into the resolver,
      and the assertions go live.

slice-02 model precedence (DSN-3):
  ``model = override.model if (override present and has model) else reviewer_model``
A model-only override (no ``enabled`` key) still resolves ``enabled`` per the
profile default (DD-D5 additive back-compat) -> the step stays active AND adopts
the override model.

Resolution is a pure read (config in -> resolved set out, config file unchanged):
@contract-shape:pure-function. No observable state mutates -> Mandate-8 state-
delta does not apply; example-based assertions per Mandate-9 (layer-3 example-only).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when

from des.adapters.driven.config.des_config import DESConfig

from .conftest import _write_project_config


scenarios("../slice-02-per-step-model.feature")


# ---------------------------------------------------------------------------
# Given: real project rigor configs (with a profile reviewer model) under tmp_path
# ---------------------------------------------------------------------------


@given(
    parsers.parse(
        'a project rigor config with reviewer model "{reviewer_model}" that pins '
        'the "{step_model}" model for the "{step_id}" review step'
    )
)
def given_step_model_override(
    ctx: dict[str, Any],
    tmp_path: Path,
    reviewer_model: str,
    step_model: str,
    step_id: str,
) -> None:
    ctx["config_path"] = _write_project_config(
        tmp_path,
        {
            "review_enabled": True,
            "reviewer_model": reviewer_model,
            "review_steps": {step_id: {"enabled": True, "model": step_model}},
        },
    )
    ctx["absent_global"] = tmp_path / "home" / ".nwave" / "global-config.json"


@given(
    parsers.parse(
        'a project rigor config with reviewer model "{reviewer_model}" and no '
        "per-step model overrides"
    )
)
def given_no_model_override(
    ctx: dict[str, Any], tmp_path: Path, reviewer_model: str
) -> None:
    ctx["config_path"] = _write_project_config(
        tmp_path,
        {"review_enabled": True, "reviewer_model": reviewer_model},
    )
    ctx["absent_global"] = tmp_path / "home" / ".nwave" / "global-config.json"


@given(
    parsers.parse(
        'a project rigor config with reviewer model "{reviewer_model}" that pins '
        'the "{step_model}" model for the "{step_id}" review step without toggling it'
    )
)
def given_model_only_override(
    ctx: dict[str, Any],
    tmp_path: Path,
    reviewer_model: str,
    step_model: str,
    step_id: str,
) -> None:
    # model-only override: NO ``enabled`` key -> enabled resolves from profile.
    ctx["config_path"] = _write_project_config(
        tmp_path,
        {
            "review_enabled": True,
            "reviewer_model": reviewer_model,
            "review_steps": {step_id: {"model": step_model}},
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
# Then: observable per-step resolved model (+ membership for the edge case)
# ---------------------------------------------------------------------------


def _active_ids(ctx: dict[str, Any]) -> set[str]:
    return {step.id for step in ctx["resolved"].active()}


def _resolved_model(ctx: dict[str, Any], step_id: str) -> str:
    """Ask the resolved set for a step's model via a RED-not-BROKEN guard.

    ``ResolvedReviewStepSet.model_for`` is the slice-02 DELIVER target; until it
    exists ``getattr`` yields ``None`` and the assertion below fails as a semantic
    ``AssertionError`` (P4) -- never an ``AttributeError`` (which would be BROKEN).
    """
    resolved = ctx["resolved"]
    model_for = getattr(resolved, "model_for", None)
    assert model_for is not None, (
        "ResolvedReviewStepSet.model_for() is not yet implemented "
        "(slice-02 DELIVER target) -- per-step model resolution absent"
    )
    return model_for(step_id)


@then(parsers.parse('the "{step_id}" review step is among the active reviewers'))
def then_step_present(ctx: dict[str, Any], step_id: str) -> None:
    assert step_id in _active_ids(ctx)


@then(parsers.parse('the "{step_id}" review step resolves to the "{model}" model'))
def then_step_resolves_model(ctx: dict[str, Any], step_id: str, model: str) -> None:
    assert _resolved_model(ctx, step_id) == model
