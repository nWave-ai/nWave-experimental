"""slice-06 acceptance (FINAL slice): a brand-new review step registers swarm-ready.

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
      in-process; that method + ``ResolvedReviewStepSet.active()``/``model_for()``/
      ``is_always_on()`` are shipped (slices 01-04 green), so the call resolves
      cleanly to a real set.
  P3  the absent behaviour is reached at RUNTIME: the catalog does not yet carry
      a ``swarm`` entry (``REVIEW_STEP_CATALOG`` ships only
      eclipse/architect/forge/sentinel), so ``swarm`` is simply absent from the
      resolved ``.active()`` ids and from ``model_for``'s backing dict.
  P4  the failure is a semantic ``AssertionError`` on membership (a value
      mismatch) -- a scenario asserting "swarm is among the active reviewers"
      fails because ``swarm`` is not yet a catalog id, NOT a ``KeyError`` /
      ``AttributeError``. ``_resolved_model`` below guards the
      membership-before-model-lookup ordering so a model assertion on an
      absent id ALSO surfaces as the same semantic AssertionError, never the
      raw ``KeyError`` that a direct ``model_for("swarm")`` lookup would raise
      (``ResolvedReviewStepSet._models`` only carries active steps). DELIVER
      appends ONE ``ReviewStepDefinition(id="swarm", agent="nw-epic-end-swarm-reviewer",
      always_on=False)`` to ``REVIEW_STEP_CATALOG`` -- NO resolver-logic change
      (DSN-5) -- and the membership/model assertions take over.

RED strategy (slice-06): scenarios #1-#3 are genuine active-RED -- they assert
presence/model resolution for a catalog id (``swarm``) that does not exist yet,
so they fail with a semantic AssertionError (membership / guarded-model-lookup),
never a vacuous green and never a BROKEN KeyError/AttributeError. Scenario #4
is a GREEN-today regression lock: it proves disabling an UNKNOWN id
(``swarm``) alongside a REAL one (``architect``) leaves every other registered
step's independent resolution untouched -- i.e. extending the override map
with an as-yet-unregistered key is inert to existing resolution, which is the
behavioral witness that adding the swarm catalog entry requires ZERO resolver
change (DSN-5 swarm-readiness, contract requirement (b)).

Resolution is a pure read (config in -> resolved set out, config file unchanged):
@contract-shape:pure-function. No observable state mutates -> Mandate-8 state-
delta does not apply; example-based assertions per Mandate-9 (layer-3 example-only).

EXTEND of the slice-01/02/03 binding shape: ``when_resolve`` + the
``{step_id}``-parameterized membership/model ``Then``s are mirrored inline (kept
per-module, unconsolidated -- see ``steps/conftest.py``). The ``ctx`` fixture
and ``_write_project_config`` helper were consolidated into
``steps/conftest.py`` at feature-end (whole-feature L1-L6 batch refactor) --
the consolidation deferred by slices 02-05 docstrings.

This is the LAST slice (DISCUSS Slice Plan, all six rows ship after this lands).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when

from des.adapters.driven.config.des_config import DESConfig

from .conftest import _write_project_config


scenarios("../slice-06-swarm-ready-registration.feature")


# ---------------------------------------------------------------------------
# Given: real project rigor configs under tmp_path
# ---------------------------------------------------------------------------


@given("a project rigor config with review enabled and no per-step toggles")
def given_no_toggles(ctx: dict[str, Any], tmp_path: Path) -> None:
    ctx["config_path"] = _write_project_config(tmp_path, {"review_enabled": True})
    ctx["absent_global"] = tmp_path / "home" / ".nwave" / "global-config.json"


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
# Then: observable membership + per-step resolved model
# ---------------------------------------------------------------------------


def _active_ids(ctx: dict[str, Any]) -> set[str]:
    return {step.id for step in ctx["resolved"].active()}


def _resolved_model(ctx: dict[str, Any], step_id: str) -> str:
    """Ask the resolved set for a step's model, membership-guarded for RED.

    ``model_for`` is shipped (slice-02), but its backing dict only carries
    ACTIVE steps -- a direct ``model_for("swarm")`` lookup before the catalog
    carries ``swarm`` would raise a raw ``KeyError`` (BROKEN, not a semantic
    AssertionError). Asserting membership FIRST converts the not-yet-registered
    case into the same guided ``AssertionError`` every other slice-06 RED
    scenario produces (P4 RED-not-BROKEN).
    """
    resolved = ctx["resolved"]
    assert step_id in _active_ids(ctx), (
        f"{step_id!r} review step is not yet a REVIEW_STEP_CATALOG member "
        "(slice-06 DELIVER target: append one ReviewStepDefinition -- "
        "id='swarm', agent='nw-epic-end-swarm-reviewer', always_on=False -- "
        "to src/des/domain/rigor/review_step_registry.py; no resolver change)"
    )
    return resolved.model_for(step_id)


@then(parsers.parse('the "{step_id}" review step is among the active reviewers'))
def then_step_present(ctx: dict[str, Any], step_id: str) -> None:
    assert step_id in _active_ids(ctx), (
        f"{step_id!r} review step is not yet a REVIEW_STEP_CATALOG member "
        "(slice-06 DELIVER target: append one ReviewStepDefinition -- "
        "id='swarm', agent='nw-epic-end-swarm-reviewer', always_on=False -- "
        "to src/des/domain/rigor/review_step_registry.py; no resolver change)"
    )


@then(parsers.parse('the "{step_id}" review step is not among the active reviewers'))
def then_step_absent(ctx: dict[str, Any], step_id: str) -> None:
    assert step_id not in _active_ids(ctx)


@then(parsers.parse('the "{step_id}" review step resolves to the "{model}" model'))
def then_step_resolves_model(ctx: dict[str, Any], step_id: str, model: str) -> None:
    assert _resolved_model(ctx, step_id) == model
