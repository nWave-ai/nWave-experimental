"""slice-01 acceptance: per-step ``require_agreement`` resolved through DESConfig.

Driving port (Mandate-13 / DSN-1, ADR-RST-002): the REAL
``DESConfig.resolve_review_steps()`` read over a REAL ``.nwave/des-config.json``
under ``tmp_path`` (in-process, real-IO -- the feature's driving surface is the
SAME config-adapter method the sibling `rigor-review-step-toggles` feature
already drives, and the SAME method the nw-distill review dispatch will consult
in slice-02; no interpreter fork is warranted per the Architecture-of-Reference
in-process Driving default).

Active-RED topology (nw-distill-red-scaffolding P1-P4, mirrors the sibling's
own slice-04 ``is_always_on`` pattern exactly -- see ADR-RST-002 decision 2):
  P1  module-top imports ONLY the stable ``DESConfig`` entry (present at HEAD,
      shipped/sealed by the sibling feature); the pure-domain
      ``ReviewStepResolver``/``ResolvedReviewStepSet`` are NEVER imported here
      -> collection cannot ImportError -> RED, not BROKEN.
  P2  the driving call goes through ``DESConfig.resolve_review_steps()``
      in-process; that method + ``ResolvedReviewStepSet.active()`` /
      ``.is_always_on()`` are shipped and green today, so the call resolves
      cleanly to a real set -- calling it raises nothing.
  P3  the absent behaviour is reached at RUNTIME: ``ResolvedReviewStepSet``
      does NOT yet expose a ``requires_agreement(step_id)`` accessor (DD-2 /
      DSN-1, this feature's net-new fourth per-step derived value), so the
      explicit agreement-requirement observable is missing today.
  P4  the failure is a semantic ``AssertionError`` -- the ``Then`` steps that
      exercise the new accessor ``getattr``-guard it (``callable(None) is
      False``) and assert a DELIVER-target guidance message, NOT a raw
      ``AttributeError``. DELIVER (slice-01) adds
      ``ResolvedReviewStepSet.requires_agreement(step_id)`` +
      ``ReviewStepResolver.resolve()``'s fourth derived value, and these
      ``Then``s take over.

RED strategy (explicit, mirrors the sibling's slice-04 note): every scenario in
this slice carries at least one ``Then`` on the not-yet-existing
``requires_agreement`` accessor, so every scenario is active-RED today. The
membership (``among the active reviewers``) and hard-pin (``hard-pinned
always-on``) ``Then``s reused verbatim from the sibling feature are
GREEN-today regression locks -- ``active()``/``is_always_on()`` already ship
and are UNAFFECTED by this feature (DD-4/DD-5 orthogonality proven by
composition, not by new resolver code).

Resolution is a pure read (config in -> resolved set out, config file
unchanged): @contract-shape:pure-function. No observable state mutates ->
Mandate-8 state-delta does not apply; example-based assertions per Mandate-9
(layer-3 example-only).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when

from des.adapters.driven.config.des_config import DESConfig

from .conftest import _write_project_config


scenarios("../slice-01-per-step-require-agreement.feature")


# ---------------------------------------------------------------------------
# Given: real project rigor configs under tmp_path
# ---------------------------------------------------------------------------


@given("a project rigor config with review enabled and no per-step toggles")
def given_no_toggles(ctx: dict[str, Any], tmp_path: Path) -> None:
    ctx["config_path"] = _write_project_config(tmp_path, {"review_enabled": True})
    ctx["absent_global"] = tmp_path / "home" / ".nwave" / "global-config.json"


@given(
    parsers.parse(
        'a project rigor config that requires agreement for the "{step_id}" review step'
    )
)
def given_step_requires_agreement(
    ctx: dict[str, Any], tmp_path: Path, step_id: str
) -> None:
    ctx["config_path"] = _write_project_config(
        tmp_path,
        {
            "review_enabled": True,
            "review_steps": {step_id: {"require_agreement": True}},
        },
    )
    ctx["absent_global"] = tmp_path / "home" / ".nwave" / "global-config.json"


@given(
    parsers.parse(
        "a project rigor config that explicitly does not require agreement "
        'for the "{step_id}" review step'
    )
)
def given_step_explicitly_no_agreement(
    ctx: dict[str, Any], tmp_path: Path, step_id: str
) -> None:
    ctx["config_path"] = _write_project_config(
        tmp_path,
        {
            "review_enabled": True,
            "review_steps": {step_id: {"require_agreement": False}},
        },
    )
    ctx["absent_global"] = tmp_path / "home" / ".nwave" / "global-config.json"


@given(
    parsers.parse(
        'a project rigor config that disables the "{step_id}" review step '
        "and requires agreement for it"
    )
)
def given_step_disabled_and_requires_agreement(
    ctx: dict[str, Any], tmp_path: Path, step_id: str
) -> None:
    ctx["config_path"] = _write_project_config(
        tmp_path,
        {
            "review_enabled": True,
            "review_steps": {step_id: {"enabled": False, "require_agreement": True}},
        },
    )
    ctx["absent_global"] = tmp_path / "home" / ".nwave" / "global-config.json"


@given(
    parsers.parse(
        'a project rigor config that requires agreement for the "{first}" '
        'and "{second}" review steps'
    )
)
def given_two_steps_require_agreement(
    ctx: dict[str, Any], tmp_path: Path, first: str, second: str
) -> None:
    ctx["config_path"] = _write_project_config(
        tmp_path,
        {
            "review_enabled": True,
            "review_steps": {
                first: {"require_agreement": True},
                second: {"require_agreement": True},
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
# Then: membership + hard-pin (GREEN-today, shipped accessors, regression locks)
# ---------------------------------------------------------------------------


def _active_ids(ctx: dict[str, Any]) -> set[str]:
    return {step.id for step in ctx["resolved"].active()}


@then(parsers.parse('the "{step_id}" review step is among the active reviewers'))
def then_step_present(ctx: dict[str, Any], step_id: str) -> None:
    assert step_id in _active_ids(ctx)


@then(parsers.parse('the "{step_id}" review step is not among the active reviewers'))
def then_step_absent(ctx: dict[str, Any], step_id: str) -> None:
    assert step_id not in _active_ids(ctx)


@then(
    parsers.parse(
        'the resolved set reports the "{step_id}" review step as hard-pinned always-on'
    )
)
def then_hard_pinned(ctx: dict[str, Any], step_id: str) -> None:
    assert ctx["resolved"].is_always_on(step_id) is True, (
        f"{step_id!r} must remain reported as hard-pinned always-on -- "
        "require_agreement must not disturb the DD-D3 hard-pin (DD-5 orthogonality)"
    )


# ---------------------------------------------------------------------------
# Then: explicit agreement-requirement observable (ACTIVE-RED -- not-yet-present)
# ---------------------------------------------------------------------------


def _requires_agreement(ctx: dict[str, Any]):
    """Fetch the not-yet-present ``requires_agreement`` accessor, guarded for RED.

    Returns the bound accessor; the caller asserts it is callable so a missing
    accessor surfaces as a semantic ``AssertionError`` (guidance), NOT a raw
    ``AttributeError`` -- this is the slice-01 RED-not-BROKEN mechanism
    (mirrors the sibling feature's slice-04 ``is_always_on`` guard exactly).
    """
    return getattr(ctx["resolved"], "requires_agreement", None)


@then(
    parsers.parse(
        'the resolved set reports the "{step_id}" review step as requiring agreement'
    )
)
def then_requires_agreement(ctx: dict[str, Any], step_id: str) -> None:
    requires_agreement = _requires_agreement(ctx)
    assert callable(requires_agreement), (
        "ResolvedReviewStepSet must expose requires_agreement(step_id) so a "
        "per-step opt-in into double-dispatch-and-agreement is an explicit, "
        "inspectable contract -- DELIVER target for slice-01 (ADR-RST-002)"
    )
    assert requires_agreement(step_id) is True, (
        f"{step_id!r} must resolve requires_agreement=True: an override with "
        '"require_agreement": true was set for it'
    )


@then(
    parsers.parse(
        'the resolved set does not report the "{step_id}" review step '
        "as requiring agreement"
    )
)
def then_not_requires_agreement(ctx: dict[str, Any], step_id: str) -> None:
    requires_agreement = _requires_agreement(ctx)
    assert callable(requires_agreement), (
        "ResolvedReviewStepSet must expose requires_agreement(step_id) so the "
        "DD-4 strict opt-in default (absent override -> False, no profile "
        "cascade) is falsifiable -- DELIVER target for slice-01 (ADR-RST-002)"
    )
    assert requires_agreement(step_id) is False, (
        f"{step_id!r} must resolve requires_agreement=False: no override, or "
        'an explicit "require_agreement": false override, was set for it -- '
        "DD-4 forbids any profile-level cascaded default"
    )
