"""pytest-bdd binding -- fix-verify-wave-dispatch-exemption-ssot slice-01.

Reconciles the two dispatch-exemption checks onto the AT-3-BLOCK canonical model
(Ale 2026-06-23). The SUT is driven through TWO real driving surfaces (Mandate-16,
Driving-Port-Only):

  * verify-wave-dispatch -- the IN-TREE gate ``python -m des.cli.verify_wave_dispatch``
    (Layer-3 subprocess), reading the seeded wave-active floor from its ``cwd``.
  * PreToolUse AT-3 -- the REAL ``PreToolUseService`` (Layer-3 composition) reading
    the SAME floor. This is the CANONICAL reference verify-wave-dispatch aligns to.

Step bodies delegate to the composition root (Mandate-12; <=2 statements, final
statement a composition call, no control flow). The Examples columns are coerced to
typed domain enums at the step boundary.

ACTIVE-RED / live-green split (atdd_pure -- NOT @skip):
  * AC-1 + AC-5 (collision -> BLOCK / agreement) are ACTIVE-RED: at HEAD
    decide_dispatch is floor-blind and ALLOWs the collision while AT-3 BLOCKs it,
    so these fire semantic AssertionErrors against the observed ALLOW.
  * AC-2 / AC-3 / AC-4 (preserved ALLOW/BLOCK paths) are live-green regression
    guards: they assert the verdicts the current code ALREADY emits, pinning the
    invariant the reconcile must not break.

S1 (step-text uniqueness): the exemption-reconcile verbs are UNIQUE to this
feature (distinct vocabulary from the slice-05 wave-dispatch-guard verbs:
"verify-wave-dispatch blocks/allows the dispatch", "the two exemption checks agree
on the verdict"). No cross-module step shadow.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, scenarios, then, when

from .steps.composition import ExemptionReconcileComposition, reconcile  # noqa: F401
from .steps.domain_types import (
    DispatchMarker,
    FloorState,
    SkipAuthorization,
    WaveOwner,
)


scenarios("slice-01-verify-wave-dispatch-at3-canonical.feature")


_OWNER_BY_LABEL = {
    "acceptance-designer": WaveOwner.ACCEPTANCE_DESIGNER,
    "solution-architect": WaveOwner.SOLUTION_ARCHITECT,
    "product-owner": WaveOwner.PRODUCT_OWNER,
}

_SKIP_BY_LABEL = {
    "form-valid witness": SkipAuthorization.FORM_VALID_WITNESS,
    "valid pre-grant": SkipAuthorization.VALID_PRE_GRANT,
    "expired pre-grant": SkipAuthorization.EXPIRED_PRE_GRANT,
}


# --- Given ------------------------------------------------------------------


@given("a wave-owner dispatch under an active wave floor that is not entering the wave")
def given_owner_active_non_entering(
    reconcile: ExemptionReconcileComposition, tmp_path
) -> None:
    reconcile.use_project_root(tmp_path)
    _arm_owner_floor(reconcile, WaveOwner.ACCEPTANCE_DESIGNER)


@given(
    parsers.parse(
        'the wave owner "{owner}" is dispatched under an active non-entering floor'
    )
)
def given_named_owner_active_non_entering(
    reconcile: ExemptionReconcileComposition, tmp_path, owner: str
) -> None:
    reconcile.use_project_root(tmp_path)
    _arm_owner_floor(reconcile, _OWNER_BY_LABEL[owner])


@given("a wave-owner dispatch entering the wave with the matching wave marker")
def given_owner_entering(reconcile: ExemptionReconcileComposition, tmp_path) -> None:
    reconcile.use_project_root(tmp_path)
    _arm_entering_owner(reconcile)


@given("a reviewer dispatch under an active wave floor that is not entering the wave")
def given_reviewer_active_non_entering(
    reconcile: ExemptionReconcileComposition, tmp_path
) -> None:
    reconcile.use_project_root(tmp_path)
    _arm_reviewer_floor(reconcile)


@given(
    "the dispatch carries only the matching wave marker without the validation marker"
)
def given_partial_marker(reconcile: ExemptionReconcileComposition) -> None:
    reconcile.given_marker(DispatchMarker.PARTIAL_WAVE_ONLY)


@given("the dispatch carries no wave marker")
def given_no_marker(reconcile: ExemptionReconcileComposition) -> None:
    reconcile.given_marker(DispatchMarker.NONE)


@given(parsers.parse("the dispatch carries a {authorization} skip authorization"))
def given_skip_authorization(
    reconcile: ExemptionReconcileComposition, authorization: str
) -> None:
    reconcile.given_skip_authorization(_SKIP_BY_LABEL[authorization])


# --- When -------------------------------------------------------------------


@when("verify-wave-dispatch evaluates the dispatch")
def when_verify_evaluates(reconcile: ExemptionReconcileComposition) -> None:
    reconcile.when_verify_wave_dispatch_evaluates()


@when("both exemption checks evaluate the dispatch")
def when_both_evaluate(reconcile: ExemptionReconcileComposition) -> None:
    reconcile.when_both_checks_evaluate()


# --- Then -------------------------------------------------------------------


@then("verify-wave-dispatch blocks the dispatch")
def then_verify_blocks(reconcile: ExemptionReconcileComposition) -> None:
    reconcile.then_verify_wave_dispatch_blocks()


@then("verify-wave-dispatch allows the dispatch")
def then_verify_allows(reconcile: ExemptionReconcileComposition) -> None:
    reconcile.then_verify_wave_dispatch_allows()


@then(parsers.parse("verify-wave-dispatch {expected} the dispatch"))
def then_verify_expected(
    reconcile: ExemptionReconcileComposition, expected: str
) -> None:
    _assert_expected_verdict(reconcile, expected)


@then("the PreToolUse floor check blocks the dispatch")
def then_at3_blocks(reconcile: ExemptionReconcileComposition) -> None:
    reconcile.then_pre_tool_use_at3_blocks()


@then("the two exemption checks agree on the verdict")
def then_checks_agree(reconcile: ExemptionReconcileComposition) -> None:
    reconcile.then_both_checks_agree()


# --- helpers (Mandate-12: typed-parameter dispatch, no logic in step bodies) -


def _arm_owner_floor(comp: ExemptionReconcileComposition, owner: WaveOwner) -> None:
    comp.given_owner(owner)
    comp.given_floor(FloorState.ACTIVE_NON_ENTERING)


def _arm_entering_owner(comp: ExemptionReconcileComposition) -> None:
    comp.given_owner(WaveOwner.ACCEPTANCE_DESIGNER)
    comp.given_floor(FloorState.ACTIVE_ENTERING)
    comp.given_marker(DispatchMarker.PARTIAL_WAVE_ONLY)


def _arm_reviewer_floor(comp: ExemptionReconcileComposition) -> None:
    comp.given_reviewer()
    comp.given_floor(FloorState.ACTIVE_NON_ENTERING)


def _assert_expected_verdict(
    comp: ExemptionReconcileComposition, expected: str
) -> None:
    _ASSERTION_BY_LABEL[expected](comp)


_ASSERTION_BY_LABEL = {
    "blocks": ExemptionReconcileComposition.then_verify_wave_dispatch_blocks,
    "allows": ExemptionReconcileComposition.then_verify_wave_dispatch_allows,
}
