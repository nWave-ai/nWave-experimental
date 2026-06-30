"""Slice-01 walking-skeleton step bindings (Mandate-12 c3: thin delegation).

Every step body is ≤2 statements and delegates to `composition`
(SkillNormativeGateComposition) — zero inline business logic, zero control flow.
The verdict/exit assertions go through `assert_state_delta` over the port-exposed
universe (Mandate 8).
"""

from __future__ import annotations

from pytest_bdd import given, then, when
from tests.common.state_delta import assert_state_delta, set_to

from ._universe import GATE_UNIVERSE, snapshot
from .domain_types import ClauseId, Verdict


# --- Given ----------------------------------------------------------------


@given(
    "the real shipped skill carrying clause "
    '"protocol-driver:assert-shipped-artifact" exists'
)
def given_real_protocol_driver_skill(composition) -> None:
    composition.require_real_skill_present(ClauseId.PROTOCOL_DRIVER)


@given("a manifest that points at a skill copy with that clause's marker removed")
def given_manifest_marker_removed(composition) -> None:
    composition.author_manifest_with_deleted_clause(ClauseId.PROTOCOL_DRIVER)


@given("the real shipped manifest and the real Mandate-13 skill are present")
def given_real_manifest_and_skill(composition) -> None:
    composition.require_real_skill_present(ClauseId.PROTOCOL_DRIVER)


@given(
    'a manifest registering clause "protocol-driver:assert-shipped-artifact" '
    "against the real shipped skill"
)
def given_manifest_against_real_skill(composition) -> None:
    composition.author_single_clause_manifest(ClauseId.PROTOCOL_DRIVER)


# --- When -----------------------------------------------------------------


@when("the maintainer runs the skill-normative gate through the des dispatcher")
def when_run_gate_via_dispatcher(composition, state) -> None:
    state["before"] = snapshot(None)
    composition.run_gate_via_dispatcher()


# --- Then -----------------------------------------------------------------


@then("the gate verdict is FAIL with exit code 1")
def then_verdict_fail(composition, state) -> None:
    after = snapshot(composition.outcome)
    assert_state_delta(
        before=state["before"],
        after=after,
        universe=GATE_UNIVERSE,
        expected={"outcome.exit_code": set_to(composition.expected_exit(Verdict.FAIL))},
    )


@then(
    'the verdict names skill "nw-test-design-mandates" and clause '
    '"protocol-driver:assert-shipped-artifact"'
)
def then_verdict_names_skill_and_clause(composition) -> None:
    assert "nw-test-design-mandates" in composition.outcome.stdout
    assert "protocol-driver:assert-shipped-artifact" in composition.outcome.stdout


@then("the gate verdict is PASS with exit code 0")
def then_verdict_pass(composition, state) -> None:
    after = snapshot(composition.outcome)
    assert_state_delta(
        before=state["before"],
        after=after,
        universe=GATE_UNIVERSE,
        expected={"outcome.exit_code": set_to(composition.expected_exit(Verdict.PASS))},
    )


@then("the verdict reports zero failing clauses")
def then_zero_failing_clauses(composition) -> None:
    assert composition.outcome.exit_code == composition.expected_exit(Verdict.PASS)
