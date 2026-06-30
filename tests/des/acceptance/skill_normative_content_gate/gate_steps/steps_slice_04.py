"""Slice-04 discrimination-acceptance step bindings (Mandate-12 c3).

Thin delegation. Reuses the dispatcher-run When, the real-skill Given, and the
PASS-verdict Then from slice-01. The short-phrase Given, the multi-word
acceptance Then, and the boundary Thens are slice-04 unique (S1).
"""

from __future__ import annotations

from pytest_bdd import given, then

from .domain_types import MarkerShape, Verdict

# Reuse the dispatcher-run When, the real-skill Given, and the PASS-verdict Then.
from .steps_slice_01 import (  # noqa: F401
    given_manifest_against_real_skill,
    then_verdict_pass,
    when_run_gate_via_dispatcher,
)


@given(
    'a manifest clause whose marker is the three-word phrase "zero is an obligation"'
)
def given_short_multi_word_marker(composition) -> None:
    composition.author_marker_shape_manifest(MarkerShape.SHORT_MULTI_WORD)


@then("the clause was included in the checked set")
def then_clause_in_checked_set(composition) -> None:
    assert composition.outcome.exit_code == composition.expected_exit(Verdict.PASS)


@then("the manifest loads without a discrimination error")
def then_loads_without_discrimination_error(composition) -> None:
    assert composition.outcome.exit_code != composition.expected_exit(
        Verdict.INDETERMINATE
    )


@then("no INDETERMINATE is emitted for this clause")
def then_no_indeterminate_for_clause(composition) -> None:
    assert composition.outcome.exit_code == composition.expected_exit(Verdict.PASS)
