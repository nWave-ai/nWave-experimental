"""Shared fixtures + shared step SSOT for f-spine-runs-tests-not-git-hooks.

S1 (step-text uniqueness within feature scope): the slice-AT-gate driving verbs
that recur across slice-01 + slice-02 ("a developer commits the entering slice",
"the spine slice-AT gate runs") are declared ONCE here in conftest -- the
canonical pytest-bdd shared-step SSOT (the S1 tolerable-variant: single source of
truth, referenced from multiple slice features via pytest-bdd's step composition).
Per-slice step files declare only the steps UNIQUE to that slice, so no
``(step_type, literal)`` key is declared twice with its own body (no last-loaded
shadow).

Mandate-12: step bodies delegate to the composition root; <=2 statements, final
statement is a composition method call; no control flow.
"""

from __future__ import annotations

from pathlib import Path

from pytest_bdd import given, then, when

from .composition import SliceRunComposition, spine  # noqa: F401
from .domain_types import SliceAtColour, SliceVerdict


# --- Shared slice-AT-gate verbs (SSOT, S1) ---------------------------------
# Declared ONCE here -- used by BOTH slice-01 and slice-02. pytest-bdd resolves
# them from the conftest step registry for every slice module's scenarios (the
# S1 tolerable-variant: single-source shared step, no cross-module shadow).


@given("a developer commits the entering slice")
def given_developer_commits_entering_slice(
    spine: SliceRunComposition, tmp_path: Path
) -> None:
    spine.use_workspace(tmp_path)


@given("the entering slice has a green acceptance test")
def given_green_slice_at(spine: SliceRunComposition) -> None:
    spine.given_planted_slice_at(SliceAtColour.GREEN)


@when("the spine slice-AT gate runs")
def when_spine_slice_at_gate_runs(spine: SliceRunComposition) -> None:
    spine.when_slice_gate_runs()


@then("the spine slice-AT gate passes the commit")
def then_gate_passes(spine: SliceRunComposition) -> None:
    spine.then_verdict_is(SliceVerdict.PASS)
