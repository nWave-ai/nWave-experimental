"""Step definitions: the --epic authoring produces a validated epic-delta.

discuss-epic-mode slice-02 (the ``/nw-discuss --epic <id>`` authoring procedure).

Honest mechanical-vs-prompt boundary: the epic-delta authoring is an
LLM-mediated prompt-surface act (DESIGN slice-02/04/05 text contracts: the slice's
"code" is SKILL / COMMAND text, NO ``src/des`` surface). These ATs pin the EDC
contract on the PRODUCED artifact -- structural shape (EDC-1..EDC-7), the gate-OUT
seam through slice-01's real CLI (EDC-8), and the fractal-JIT invariant (EDC-9).
Discoverability stays prompt-surface (reviewed by Sentinel; mechanically lives in
slice-04 ESC-3).

Layer 3 (subprocess/FS acceptance). Example-only, no PBT machinery (Mandate 9/11):
the EDC is a finite, enumerable closed contract set.

Step bodies delegate to ``EpicModeAuthoringComposition``; no inline business logic
(Mandate-12 criterion 3) -- each body is a typed lookup plus a composition call,
or a composition observation plus a single assertion.

Active-RED contract (atdd_pure): every EDC observation FAILS on the current tip
and PASSES once slice-02 lands. The ``--epic`` authoring procedure is undefined
today, so the production-path epic-delta is never produced -- the gate-OUT reads
``EPIC_DELTA_ABSENT`` and the structural observation reads an absent artifact. A
deliberate missing-functionality RED (wrong/absent verdict and absent shape), not
a test bug. The composition module imports cleanly (slice-01's CLI exists today),
so the RED is a semantic AssertionError, never a collection / import error.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from tests.common.state_delta import assert_state_delta, set_to, unchanged

from .composition import (
    EpicDeltaObservation,
    EpicModeAuthoringComposition,
    GateOutResult,
)
from .domain_types import EpicDeltaVerdict, EpicId


scenarios("../epic-mode-authoring.feature")


# EDC-4 fixed five-column header the produced Feature Plan must carry.
_EXPECTED_FEATURE_PLAN_COLUMNS = (
    "Feature",
    "Value statement",
    "Status",
    "Annotation",
    "Justification",
)


@pytest.fixture
def composition(tmp_path: Path) -> EpicModeAuthoringComposition:
    """Composition root over a tmp_path repository."""
    return EpicModeAuthoringComposition(repo_dir=tmp_path / "repo")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for observations across When -> Then steps."""
    return {}


# --- Given -------------------------------------------------------------------


@given("a maintainer with a request bigger than one feature")
def given_maintainer(composition: EpicModeAuthoringComposition) -> None:
    composition.open_epic(EpicId("flow-v2-wave-migrations"))


@given("the maintainer runs the epic-mode authoring on the epic")
def given_run_epic_mode_authoring(
    composition: EpicModeAuthoringComposition,
) -> None:
    composition.run_epic_mode_authoring()


# --- When --------------------------------------------------------------------


@when("the produced epic-delta is observed against the EDC structural shape")
def when_observe_structural_shape(
    composition: EpicModeAuthoringComposition,
    result_box: dict[str, object],
) -> None:
    result_box["observation"] = composition.observe_epic_delta()


@when("the produced epic-delta is validated by the keystone gate")
def when_validate_gate_out(
    composition: EpicModeAuthoringComposition,
    result_box: dict[str, object],
) -> None:
    result_box["universe_before"] = composition.capture_universe()
    result_box["gate_out"] = composition.validate_gate_out()


@when("the produced epic-mode workspace is observed for fractal JIT")
def when_observe_fractal_jit(
    composition: EpicModeAuthoringComposition,
    result_box: dict[str, object],
) -> None:
    result_box["observation"] = composition.observe_epic_delta()
    result_box["workspace_count"] = composition.count_feature_workspaces()


# --- Then --------------------------------------------------------------------


@then("the produced epic-delta carries the EDC structural shape")
def then_edc_structural_shape(result_box: dict[str, object]) -> None:
    """EDC-1..EDC-7: the produced artifact's structural contract.

    A single conjunction of the closed EDC structural pins, asserted as one
    observation tuple so the failure names the first violated pin. On the current
    tip the artifact is absent (``exists is False``) and every pin fails -- the
    active-RED missing-functionality signal.
    """
    observation = result_box["observation"]
    assert isinstance(observation, EpicDeltaObservation)
    assert observation.exists, "EDC-1: epic-delta produced at the production path"
    assert observation.title_line == "# Epic Delta: flow-v2-wave-migrations", (
        "EDC-2: title line"
    )
    assert observation.has_epic_jtbd_section, "EDC-3: epic-JTBD section"
    assert observation.has_feature_plan_heading, "EDC-4: R1 Feature Plan heading"
    assert observation.feature_plan_columns == _EXPECTED_FEATURE_PLAN_COLUMNS, (
        "EDC-4: fixed five-column header"
    )
    assert observation.keystone_row_count == 1, (
        "EDC-5: exactly one @walking-skeleton keystone row"
    )
    assert observation.dependency_order_backward_only, (
        "EDC-6: backward-only dependency order"
    )
    assert all(
        token in {"pending", "in-flight", "shipped"}
        for token in observation.status_tokens_in_authored_rows
    ), "EDC-7: Status tokens from the R2 closed set"


@then("the keystone gate accepts the produced epic-delta")
def then_gate_out_accepts(
    composition: EpicModeAuthoringComposition,
    result_box: dict[str, object],
) -> None:
    """EDC-8: the produced epic-delta clears slice-01's real validator gate.

    Slice-01's CLI is a read-only pure-function surface (@contract-shape:
    pure-function): the gate-OUT validation must leave the produced-artifact
    universe unchanged. The captured ``universe_before`` is consumed here as the
    state-delta baseline, so the read-only contract is asserted rather than
    captured-and-discarded.
    """
    gate_out = result_box["gate_out"]
    assert isinstance(gate_out, GateOutResult)
    assert gate_out.verdict is EpicDeltaVerdict.ACCEPTED
    assert_state_delta(
        before=result_box["universe_before"],
        after=composition.capture_universe(),
        universe={"epic_delta.exists", "feature_workspaces.count"},
        expected={
            "epic_delta.exists": unchanged(),
            "feature_workspaces.count": unchanged(),
        },
    )


@then("the --epic run created no feature workspaces")
def then_no_feature_workspaces(
    composition: EpicModeAuthoringComposition,
    result_box: dict[str, object],
) -> None:
    """EDC-9 fractal JIT: the run produces only the epic-delta.

    The universe is the produced-artifact surface: the epic-delta exists (the run
    produced it) and zero feature workspaces were created. On the current tip the
    epic-delta is absent, so the ``set_to(True)`` expectation fails -- the
    active-RED signal -- proving the run has not yet produced the plan.
    """
    assert_state_delta(
        before={"epic_delta.exists": False, "feature_workspaces.count": 0},
        after=composition.capture_universe(),
        universe={"epic_delta.exists", "feature_workspaces.count"},
        expected={
            "epic_delta.exists": set_to(True),
            "feature_workspaces.count": set_to(0),
        },
    )


@then("the only artifact produced is the epic-delta")
def then_only_epic_delta(result_box: dict[str, object]) -> None:
    """EDC-9: zero feature workspaces upfront (no N feature-deltas)."""
    assert result_box["workspace_count"] == 0
