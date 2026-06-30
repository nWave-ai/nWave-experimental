"""Slice-03 loud-absence + hook-wiring step bindings (Mandate-12 c3).

Thin delegation. Reuses the dispatcher-run When and the INDETERMINATE verdict
Then from earlier slices; the hook-spine steps are slice-03 unique.
"""

from __future__ import annotations

from pytest_bdd import given, then, when

from .domain_types import AssetFault, ClauseId
from .steps_slice_01 import when_run_gate_via_dispatcher  # noqa: F401

# Reuse the dispatcher-run When and the INDETERMINATE verdict Then.
from .steps_slice_02 import then_verdict_indeterminate  # noqa: F401


# --- Given (dispatcher: AC-06 / AC-10) ------------------------------------


@given("a manifest that references a skill asset path that does not exist on disk")
def given_manifest_absent_asset(composition) -> None:
    composition.author_manifest_with_faulted_asset(AssetFault.ABSENT)


@given("a manifest that references a skill asset that exists but is not UTF-8 text")
def given_manifest_undecodable_asset(composition) -> None:
    composition.author_manifest_with_faulted_asset(AssetFault.UNDECODABLE)


# --- Then (dispatcher verdict naming) -------------------------------------


@then("the verdict names the missing asset path and is not PASS")
def then_names_missing_asset(composition) -> None:
    assert composition.outcome.exit_code != composition.expected_exit_pass()
    assert "nw-faulted" in composition.outcome.stdout


@then("the verdict names the asset path and the read failure and is not PASS")
def then_names_undecodable_asset(composition) -> None:
    assert composition.outcome.exit_code != composition.expected_exit_pass()
    assert "nw-faulted" in composition.outcome.stdout


# --- Given / When / Then (hook spine: AC-07 + H-1) ------------------------


@given("a maintainer edit to a skill file under the nWave skills tree")
def given_skill_edit_under_skills_tree(composition, state) -> None:
    state["edit_clause"] = ClauseId.PROTOCOL_DRIVER


@given("the skill-normative gate intercept is forced to raise during the edit")
def given_intercept_forced_to_raise(composition, state) -> None:
    state["inject_fault"] = True


@when("the pre_write hook evaluates the skill edit")
def when_pre_write_evaluates(composition, state) -> None:
    composition.inject_intercept_fault_via_pre_write_hook(state["edit_clause"])


@then("the hook decision is block with exit code 2")
def then_hook_blocks_exit_2(composition) -> None:
    assert composition.hook.decision == "block"
    assert composition.hook.exit_code == 2


@then("the block reason carries the skill-normative gate intercept error")
def then_block_reason_names_intercept_error(composition) -> None:
    assert "skill-normative-gate intercept error" in composition.hook.reason
