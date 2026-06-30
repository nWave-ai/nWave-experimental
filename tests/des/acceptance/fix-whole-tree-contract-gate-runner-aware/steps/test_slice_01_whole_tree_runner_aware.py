"""Step bindings: whole-tree contract gate resolves the target's runner (slice-01).

Layer-3 subprocess e2e (Mandate-13). Each step body delegates to
``WholeTreeGateComposition`` -- no inline business logic (Mandate-12 criterion 3:
<=2 statements, final = composition.<method>(...), no control flow). Domain nouns
are typed via ``domain_types`` (criterion 1); the composition service signatures
consume those typed parameters (criterion 2).

active-RED (atdd_pure): the net-new ``WholeTreeRunnerResolved`` event is absent at
HEAD, so each Then RED-fails for the right reason (the whole-tree runner router is
not implemented yet). DELIVER ships ``_maybe_route_through_runner_whole_tree`` to
turn these GREEN.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition import WholeTreeGateComposition
from .domain_types import CARGO_RUNNER, PYTEST_RUNNER, TargetKind


scenarios("../slice-01-whole-tree-runner-aware.feature")


@pytest.fixture
def composition() -> WholeTreeGateComposition:
    """Production-wired driving port over the real run-contract-gate CLI."""
    return WholeTreeGateComposition()


# --- Given -------------------------------------------------------------------


@given("a single-lockfile Rust target the contract gate can run against")
def given_rust_target(composition: WholeTreeGateComposition, tmp_path: Path) -> None:
    composition.given_single_lockfile_target(TargetKind.RUST, tmp_path)


@given("a single-lockfile Python target the contract gate can run against")
def given_python_target(composition: WholeTreeGateComposition, tmp_path: Path) -> None:
    composition.given_single_lockfile_target(TargetKind.PYTHON, tmp_path)


# --- When --------------------------------------------------------------------


@when("the maintainer runs the whole-tree contract gate against the target")
def when_run_whole_tree_gate(composition: WholeTreeGateComposition) -> None:
    composition.run_whole_tree_gate()


# --- Then --------------------------------------------------------------------


@then(
    "the gate resolves the target's runner to cargo and routes the whole-tree run "
    "through it"
)
def then_resolves_and_routes_cargo(composition: WholeTreeGateComposition) -> None:
    ev = composition.observable().resolution_event()
    assert (
        ev is not None and ev.get("runner") == CARGO_RUNNER and ev.get("routed") is True
    ), (
        "on a single-Cargo.toml target the whole-tree gate must emit a "
        f"WholeTreeRunnerResolved event with runner={CARGO_RUNNER!r} routed=True "
        "(it resolved cargo and dispatched the whole-tree run through the cargo "
        "run facet) -- but at HEAD the whole-tree path is pytest-hardcoded and no "
        f"such event exists. {composition.diag()}"
    )


@then("the gate never falls through to the pytest interpreter on the non-Python target")
def then_no_pytest_fallthrough(composition: WholeTreeGateComposition) -> None:
    assert not composition.observable().emitted_interpreter_unavailable(), (
        "the #73 symptom: on a Rust target the gate must NEVER reach the hardcoded "
        "pytest seam and emit InterpreterUnavailable -- it resolved cargo, so it "
        "either ran cargo or refused INDETERMINATE naming cargo, never crashed on "
        f"pytest. {composition.diag()}"
    )


@then(
    "the gate stamps no gate-scope digest and announces the degrade on the captured "
    "output"
)
def then_digest_degrades_loud(composition: WholeTreeGateComposition) -> None:
    ev = composition.observable().resolution_event()
    assert ev is not None and ev.get("digest_degraded") is True, (
        "D6: on a non-pytest target with no enumerate facet (slice-01) the digest "
        "leg must degrade-LOUD -- the WholeTreeRunnerResolved event must carry "
        "digest_degraded=True (gate_scope_digest stamped None) -- but at HEAD no "
        f"resolution event is emitted at all. {composition.diag()}"
    )


@then("the gate never fabricates a pytest node-id digest over the non-Python tree")
def then_no_fabricated_pytest_digest(composition: WholeTreeGateComposition) -> None:
    ev = composition.observable().resolution_event()
    assert ev is not None and ev.get("runner") == CARGO_RUNNER, (
        "the digest over a Rust tree must come from the resolved cargo runner (or "
        "degrade to None), NEVER a fabricated pytest node-id digest -- the "
        "resolution event must name the cargo runner, proving the digest leg is "
        f"runner-aware, not pytest-hardcoded. {composition.diag()}"
    )


@then(
    "the gate resolves the target's runner to pytest and runs the existing pytest "
    "path unchanged"
)
def then_resolves_pytest_unchanged(composition: WholeTreeGateComposition) -> None:
    ev = composition.observable().resolution_event()
    assert (
        ev is not None
        and ev.get("runner") == PYTEST_RUNNER
        and ev.get("routed") is False
    ), (
        "on a single-pyproject.toml target the whole-tree gate must resolve pytest "
        f"and emit WholeTreeRunnerResolved runner={PYTEST_RUNNER!r} routed=False "
        "(router returned None -> the EXISTING pytest path runs UNCHANGED) -- but "
        f"at HEAD no resolution happens in the whole-tree path. {composition.diag()}"
    )
