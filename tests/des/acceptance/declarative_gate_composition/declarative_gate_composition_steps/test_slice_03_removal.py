"""pytest-bdd binding for f-declarative-gate-composition slice-03 (removal-only).

Driving surface (Mandate-13 driving-port-only): a repo-source read over the SHIPPED
production modules (the prose-surface case -- the real file from the repo) for the
ABSENCE leg, plus the REAL SubagentStopService.validate via the production
composition root (Layer 3 composition) for the NON-REGRESSION leg. Step bodies
delegate to the composition root; no business logic in step bodies (Mandate-12).

Active-RED scaffold (atdd_pure -- NOT @skip): RED at HEAD because the imperative
DISCUSS branches are still PRESENT (the lift has not happened). GREEN once DELIVER
removes them and the DISCUSS gate-OUT still vetoes via the declared composition.
The scenario fails with a semantic AssertionError naming the surviving branch,
never a collection / import error.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_03_removal import RemovalComposition


scenarios("../slice-03-removal.feature")


@pytest.fixture
def removal() -> RemovalComposition:
    return RemovalComposition()


# --- Given -----------------------------------------------------------------


@given("the DISCUSS wave is migrated to the declarative composition")
def given_discuss_wave_migrated_to_declarative(
    removal: RemovalComposition, tmp_path: Path
) -> None:
    removal.given_discuss_wave_migrated_to_declarative(tmp_path)


# --- When ------------------------------------------------------------------


@when("the codebase is inspected and the gate-out runs")
def when_the_codebase_is_inspected_and_the_gate_runs(
    removal: RemovalComposition,
) -> None:
    removal.when_the_codebase_is_inspected_and_the_gate_runs()


# --- Then ------------------------------------------------------------------


@then("no imperative discuss gate-stack branch survives")
def then_no_imperative_discuss_branch_survives(
    removal: RemovalComposition,
) -> None:
    removal.then_no_imperative_discuss_branch_survives()


@then("the discuss gate-out still vetoes the infra-only slice plan")
def then_discuss_gate_out_still_vetoes(removal: RemovalComposition) -> None:
    removal.then_discuss_gate_out_still_vetoes()
