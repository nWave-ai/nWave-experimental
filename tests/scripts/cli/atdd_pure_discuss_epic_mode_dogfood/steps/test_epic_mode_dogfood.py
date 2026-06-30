"""Step definitions: the flow-v2 wave-migrations epic-delta -- the first real run.

discuss-epic-mode slice-06 (the DOGFOOD: the first real epic-mode run on the REAL
flow-v2 wave-migrations follow-on list).

Honest mechanical-vs-prompt boundary: the epic-delta is AUTHORED by the Luna PO
agent during an LLM-mediated discuss session following the epic-mode procedure
(slice-02 authoring + slice-04 escalation + slice-05 maintenance). That authoring
is a prompt-surface act, not mechanically testable. What these ATs pin is the
dogfood contract DESIGN declared for the PRODUCED artifact -- observed read-only at
the REAL production path ``docs/epic/flow-v2-wave-migrations/epic-delta.md``:
  - the gate-OUT contract (EDC-8) via slice-01's real CLI;
  - the keystone + backward-only dependency order (EDC-5 / EDC-6, the checks DESIGN
    DEFERRED to this slice via DC-2);
  - §13-completeness (the dogfood's honesty): every item of the closed 7-item
    change-set follow-on coverage universe maps to a Feature Plan row OR a
    documented exclusion.

Unlike the sibling epic-mode suites, slice-06 uses NO reference oracle: the REAL
artifact is the deliverable (authored at DELIVER), not a golden-file analogue. The
composition only OBSERVES the real repository path, read-only -- zero filesystem
mutation, so running these ATs never writes the deliverable.

Layer 3 (subprocess/FS acceptance). Example-only, no PBT machinery (Mandate 9/11):
the EDC + the 7-item change-set coverage universe are finite, enumerable closed
contract sets.

Step bodies delegate to ``DogfoodComposition``; no inline business logic
(Mandate-12 criterion 3) -- each body is a composition call, or a composition
observation plus a single assertion.

Active-RED contract (atdd_pure): every observation FAILS on the current tip and
PASSES once slice-06 lands. The dogfood run has not happened, so the production-path
epic-delta does not exist -- the gate-OUT reads ``EPIC_DELTA_ABSENT`` and the
structural / keystone / coverage observations read an absent artifact. A deliberate
missing-functionality RED, not a test bug. The composition module imports cleanly
(slice-01's CLI exists today), so the RED is a semantic AssertionError, never a
collection / import error.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition import (
    DogfoodComposition,
    DogfoodObservation,
    GateOutResult,
    real_repo_root,
)
from .domain_types import DOGFOOD_EPIC_ID, DogfoodVerdict


scenarios("../epic-mode-dogfood.feature")


# EDC-4 fixed five-column header the produced Feature Plan must carry.
_EXPECTED_FEATURE_PLAN_COLUMNS = (
    "Feature",
    "Value statement",
    "Status",
    "Annotation",
    "Justification",
)


@pytest.fixture
def composition() -> DogfoodComposition:
    """Composition root over the REAL repository root (read-only observation).

    The dogfood deliverable is the REAL artifact at
    ``docs/epic/flow-v2-wave-migrations/epic-delta.md`` under the real repo root --
    NOT a tmp_path. The composition only reads that path; it never writes it.
    """
    return DogfoodComposition(repo_dir=real_repo_root(), epic_id=DOGFOOD_EPIC_ID)


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for observations across When -> Then steps."""
    return {}


# --- Given -------------------------------------------------------------------


@given("the flow-v2 wave-migrations epic is decomposed by the first real epic-mode run")
def given_dogfood_epic(composition: DogfoodComposition) -> None:
    composition.epic_id = DOGFOOD_EPIC_ID


# --- When --------------------------------------------------------------------


@when("the flow-v2 epic-delta is validated by the keystone gate")
def when_validate_gate_out(
    composition: DogfoodComposition,
    result_box: dict[str, object],
) -> None:
    result_box["universe_before"] = _read_only_universe(composition)
    result_box["gate_out"] = composition.validate_gate_out()
    result_box["observation"] = composition.observe_dogfood_epic_delta()


@when("the flow-v2 epic-delta is observed for keystone and dependency order")
def when_observe_keystone_and_deps(
    composition: DogfoodComposition,
    result_box: dict[str, object],
) -> None:
    result_box["observation"] = composition.observe_dogfood_epic_delta()


@when("the flow-v2 epic-delta is observed for change-set follow-on coverage")
def when_observe_coverage(
    composition: DogfoodComposition,
    result_box: dict[str, object],
) -> None:
    result_box["observation"] = composition.observe_dogfood_epic_delta()


# --- Then --------------------------------------------------------------------


@then("the keystone gate accepts the flow-v2 epic-delta")
def then_gate_out_accepts(
    composition: DogfoodComposition,
    result_box: dict[str, object],
) -> None:
    """EDC-8: the REAL produced epic-delta clears slice-01's validator gate.

    Slice-01's CLI is a read-only pure-function surface
    (@contract-shape:pure-function): the gate-OUT validation must leave the REAL
    production-path artifact unchanged. The captured ``universe_before`` is consumed
    here as the state-delta baseline, so the read-only contract is asserted rather
    than captured-and-discarded. On the current tip the artifact is absent, so the
    verdict reads EPIC_DELTA_ABSENT and the assertion fires -- the active-RED signal.
    """
    gate_out = result_box["gate_out"]
    assert isinstance(gate_out, GateOutResult)
    assert gate_out.verdict is DogfoodVerdict.ACCEPTED, (
        "EDC-8: the flow-v2 epic-delta clears the keystone gate (accepted)"
    )
    assert_state_delta(
        before=result_box["universe_before"],
        after=_read_only_universe(composition),
        universe={"epic_delta.exists", "epic_delta.bytes"},
        expected={
            "epic_delta.exists": unchanged(),
            "epic_delta.bytes": unchanged(),
        },
    )


@then("the flow-v2 epic-delta carries the dogfood structural shape")
def then_dogfood_structural_shape(result_box: dict[str, object]) -> None:
    """EDC-1..EDC-7 on the REAL artifact (the dogfood structural happy path)."""
    observation = result_box["observation"]
    assert isinstance(observation, DogfoodObservation)
    assert observation.exists, "EDC-1: epic-delta produced at the production path"
    assert observation.title_line == "# Epic Delta: flow-v2-wave-migrations", (
        "EDC-2: title line"
    )
    assert observation.has_epic_jtbd_section, "EDC-3: epic-JTBD section"
    assert observation.has_feature_plan_heading, "EDC-4: R1 Feature Plan heading"
    assert observation.feature_plan_columns == _EXPECTED_FEATURE_PLAN_COLUMNS, (
        "EDC-4: fixed five-column header"
    )
    assert all(
        token in {"pending", "in-flight", "shipped"}
        for token in observation.status_tokens_in_authored_rows
    ), "EDC-7: Status tokens from the R2 closed set"


@then("the flow-v2 epic-delta designates exactly one keystone feature")
def then_one_keystone(result_box: dict[str, object]) -> None:
    """EDC-5 (DC-2 deferral realized here): exactly one @walking-skeleton row."""
    observation = result_box["observation"]
    assert isinstance(observation, DogfoodObservation)
    assert observation.exists, "EDC-1: epic-delta produced at the production path"
    assert observation.keystone_row_count == 1, (
        "EDC-5: exactly one @walking-skeleton keystone row (DC-2 deferred to slice-06)"
    )


@then("the flow-v2 epic-delta orders its features backward-only")
def then_backward_only_deps(result_box: dict[str, object]) -> None:
    """EDC-6 (DC-2 deferral realized here): backward-only dependency order."""
    observation = result_box["observation"]
    assert isinstance(observation, DogfoodObservation)
    assert observation.exists, "EDC-1: epic-delta produced at the production path"
    assert observation.dependency_order_backward_only, (
        "EDC-6: backward-only dependency order (DC-2 deferred to slice-06)"
    )


@then("every change-set follow-on item maps to a feature row or a documented exclusion")
def then_section13_complete(result_box: dict[str, object]) -> None:
    """The dogfood's honesty: every §13 follow-on item is represented (EDC + slice-06
    completeness contract).

    The closed 7-item change-set coverage universe (the four wave migrations +
    declarative gate-composition extraction + manifest/gate-G track + self-attest
    verdict layer) MUST each map to a Feature Plan row OR a documented exclusion. On
    the current tip the artifact is absent, so every item is uncovered and the
    assertion names the full uncovered set -- the active-RED signal.
    """
    observation = result_box["observation"]
    assert isinstance(observation, DogfoodObservation)
    assert observation.exists, "EDC-1: epic-delta produced at the production path"
    assert observation.uncovered_items == frozenset(), (
        "slice-06 completeness: every §13 follow-on item maps to a feature row "
        f"or a documented exclusion; uncovered = {sorted(i.value for i in observation.uncovered_items)}"
    )


# --- read-only universe (Mandate 8, fail-closed) ----------------------------
# Port-exposed filesystem observables of the REAL production path. Both asserted
# `unchanged` across the gate-OUT validation (the validator's read-only
# pure-function contract). No internal struct fields. Module-level so the When/Then
# step bodies stay delegations (Mandate-12 criterion 3).


def _read_only_universe(composition: DogfoodComposition) -> dict[str, object]:
    path = composition.epic_delta_path
    exists = path.exists()
    return {
        "epic_delta.exists": exists,
        "epic_delta.bytes": path.stat().st_size if exists else 0,
    }
