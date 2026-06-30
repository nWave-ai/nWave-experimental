"""Slice-02 discrimination + cardinality step bindings (Mandate-12 c3).

Thin delegation to `composition`. The `@when` / verdict `@then` steps share the
slice-01 vocabulary (step-reuse): the dispatcher-run When and the PASS/FAIL/
INDETERMINATE verdict Thens are imported from steps_slice_01 where identical, and
only the slice-02-unique steps are defined here (S1: no duplicate literals).
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then
from tests.common.state_delta import assert_state_delta, set_to

from ._universe import GATE_UNIVERSE, snapshot
from .domain_types import MarkerShape, Verdict

# Reuse the dispatcher-run When and the PASS-verdict Then from slice-01.
from .steps_slice_01 import (  # noqa: F401
    then_verdict_pass,
    when_run_gate_via_dispatcher,
)


# --- Given (slice-02 unique) ----------------------------------------------


@given("a manifest registering zero clauses for an as-yet-unprotected skill")
def given_zero_clause_manifest(composition) -> None:
    composition.author_zero_clause_manifest()


@given("a manifest registering one clause for one skill and many clauses for another")
def given_one_and_many_clause_manifest(composition) -> None:
    composition.author_one_and_many_clause_manifest()


@given('a manifest clause whose marker is the bare token "table"')
def given_bare_token_marker(composition) -> None:
    composition.author_marker_shape_manifest(MarkerShape.BARE_COMMON_TOKEN)


# --- Then (slice-02 unique) -----------------------------------------------


@then("the empty case is reported as a verdict, never as an error")
def then_empty_is_verdict(composition) -> None:
    assert composition.outcome.exit_code == composition.expected_exit(Verdict.PASS)


@then("every registered clause across one-skill and many-skill is checked")
def then_every_clause_checked(composition) -> None:
    # Cardinality observable: the one-and-many manifest registers 3 all-passing
    # clauses, so a genuine full-corpus check assembles the closed verdict over
    # every one of them and renders the canonical PASS line "PASS: 0 failing
    # clauses" (skill_normative_gate._render). That render is the strongest
    # cardinality witness the driving port exposes: a gate that errored or
    # short-circuited without traversing the corpus would not emit it, and the
    # "0 failing" count proves the verdict-assembly path ran over the registered
    # clauses rather than returning a bare exit code.
    #
    # Limit (no production import per the Driving-Port-Only Boundary): the PASS
    # render does not echo a per-clause checked-count, so "exactly 3 checked"
    # cannot be asserted positively from stdout. The FAIL/INDETERMINATE renders
    # name each offending clause (covered by the FAIL + non-discriminating ATs),
    # which is where the per-clause traversal is positively witnessed.
    assert composition.outcome.exit_code == composition.expected_exit(Verdict.PASS)
    assert "PASS: 0 failing clauses" in composition.outcome.stdout, (
        "full-corpus verdict-assembly render absent — the gate did not emit the "
        f"canonical closed PASS verdict over the registered clauses: "
        f"{composition.outcome.stdout!r}"
    )


@then("the gate verdict is INDETERMINATE with exit code 4")
def then_verdict_indeterminate(composition, state) -> None:
    after = snapshot(composition.outcome)
    assert_state_delta(
        before=state["before"],
        after=after,
        universe=GATE_UNIVERSE,
        expected={
            "outcome.exit_code": set_to(
                composition.expected_exit(Verdict.INDETERMINATE)
            )
        },
    )


@then(parsers.parse('the verdict names the offending clause and the marker "{marker}"'))
def then_verdict_names_marker(composition, marker: str) -> None:
    assert marker in composition.outcome.stdout
