"""Step bindings: the whole-tree digest is derived from the target's runner (slice-02).

Layer-3 subprocess e2e (Mandate-13). Each step body delegates to the SAME
``WholeTreeGateComposition`` the slice-01 keystone established (REUSE: fixture
staging + the combined-channel ``GateOutcome`` event parse) -- only the digest
mode argv differs. No inline business logic (Mandate-12 criterion 3); domain
nouns are typed via ``domain_types`` (criterion 1); the composition service
signatures consume those typed parameters (criterion 2).

active-RED (atdd_pure): the whole-tree router is mode-AGNOSTIC at HEAD -- every
Cargo digest-mode invocation routes through the slice-01 RUN leg and stamps the
D6 placeholder ``digest_degraded=True`` (the enumerate facet does not exist).
Each Rust Then asserts ``digest_degraded`` is NOT True, so it RED-fails for the
right reason (missing functionality: ``RunnerAdapter.list_scope`` + the
digest-mode wiring). DELIVER ships the enumerate facet to turn these GREEN.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition import WholeTreeGateComposition
from .domain_types import CARGO_RUNNER, PYTEST_RUNNER, DigestMode, TargetKind


scenarios("../slice-02-runner-aware-digest.feature")


@pytest.fixture
def composition() -> WholeTreeGateComposition:
    """Production-wired driving port over the real run-contract-gate CLI."""
    return WholeTreeGateComposition()


# --- Given (reuse slice-01 fixture-staging service) --------------------------


@given("a single-lockfile Rust target the contract gate can run against")
def given_rust_target(composition: WholeTreeGateComposition, tmp_path: Path) -> None:
    composition.given_single_lockfile_target(TargetKind.RUST, tmp_path)


@given("a single-lockfile Python target the contract gate can run against")
def given_python_target(composition: WholeTreeGateComposition, tmp_path: Path) -> None:
    composition.given_single_lockfile_target(TargetKind.PYTHON, tmp_path)


# --- When: drive a whole-tree digest mode ------------------------------------


@when("the maintainer prints the committed-scope digest for the target")
def when_committed_scope_digest(composition: WholeTreeGateComposition) -> None:
    composition.run_whole_tree_digest_mode(DigestMode.COMMITTED_SCOPE_DIGEST)


@when("the maintainer verifies the target's gate-scope trailer")
def when_verify_gate_scope(composition: WholeTreeGateComposition) -> None:
    composition.run_whole_tree_digest_mode(DigestMode.VERIFY_GATE_SCOPE)


@when("the maintainer prints the working-tree digest for the target")
def when_print_digest(composition: WholeTreeGateComposition) -> None:
    composition.run_whole_tree_digest_mode(DigestMode.PRINT_DIGEST)


# --- Then --------------------------------------------------------------------


@then(
    "the gate derives the digest through the target's cargo enumerate facet, not "
    "the no-digest placeholder"
)
def then_committed_digest_runner_aware(composition: WholeTreeGateComposition) -> None:
    obs = composition.observable()
    ev = obs.resolution_event()
    assert (
        ev is not None
        and ev.get("runner") == CARGO_RUNNER
        and obs.resolution_digest_degraded() is not True
    ), (
        "on a single-Cargo.toml target the --committed-scope-digest leg must "
        f"enumerate through the cargo runner ({CARGO_RUNNER!r}) -- the resolution "
        "event must name cargo with digest_degraded NOT True (the enumerate facet "
        "is wired: a real cargo digest, or a degrade-LOUD INDETERMINATE naming "
        "`cargo nextest list` when the binary is absent) -- but at HEAD the "
        "mode-agnostic router stamps the slice-01 D6 placeholder digest_degraded="
        f"True for every Cargo invocation. {composition.diag()}"
    )


@then("the gate never fabricates a pytest node-id digest over the non-Python tree")
def then_no_fabricated_pytest_digest_committed(
    composition: WholeTreeGateComposition,
) -> None:
    obs = composition.observable()
    ev = obs.resolution_event()
    assert (
        ev is not None
        and ev.get("runner") == CARGO_RUNNER
        and not obs.emitted_interpreter_unavailable()
    ), (
        "the committed-scope digest over a Rust tree must come from the resolved "
        "cargo enumerate facet (or degrade-LOUD), NEVER a fabricated pytest "
        "node-id digest and NEVER the #73 InterpreterUnavailable crash -- the "
        "resolution event must name the cargo runner, proving the digest leg is "
        f"runner-aware, not pytest-hardcoded. {composition.diag()}"
    )


@then(
    "the gate re-derives the digest through the target's cargo enumerate facet, "
    "not the no-digest placeholder"
)
def then_verify_runner_aware(composition: WholeTreeGateComposition) -> None:
    obs = composition.observable()
    ev = obs.resolution_event()
    assert (
        ev is not None
        and ev.get("runner") == CARGO_RUNNER
        and obs.resolution_digest_degraded() is not True
    ), (
        "on a single-Cargo.toml target --verify-gate-scope must RE-DERIVE the "
        f"fresh digest through the cargo enumerate facet ({CARGO_RUNNER!r}) -- the "
        "resolution event must name cargo with digest_degraded NOT True (a real "
        "re-derived cargo digest, or a degrade-LOUD INDETERMINATE naming `cargo "
        "nextest list`) -- but at HEAD the mode-agnostic router stamps the "
        f"slice-01 D6 placeholder digest_degraded=True. {composition.diag()}"
    )


@then(
    "the gate never verifies against a fabricated pytest node-id digest over the "
    "non-Python tree"
)
def then_no_fabricated_pytest_digest_verify(
    composition: WholeTreeGateComposition,
) -> None:
    obs = composition.observable()
    ev = obs.resolution_event()
    assert (
        ev is not None
        and ev.get("runner") == CARGO_RUNNER
        and not obs.emitted_interpreter_unavailable()
    ), (
        "verification over a Rust tree must re-derive through the cargo enumerate "
        "facet, NEVER compare against a fabricated pytest node-id digest and "
        "NEVER hit the #73 InterpreterUnavailable crash -- the resolution event "
        f"must name the cargo runner. {composition.diag()}"
    )


@then(
    "the gate derives a real pytest node-id digest through the resolved pytest "
    "enumerate facet"
)
def then_python_real_pytest_digest(composition: WholeTreeGateComposition) -> None:
    obs = composition.observable()
    ev = obs.resolution_event()
    assert (
        ev is not None
        and ev.get("runner") == PYTEST_RUNNER
        and ev.get("routed") is False
        and obs.printed_digest() is not None
    ), (
        "on a single-pyproject.toml target the digest mode must resolve pytest "
        f"({PYTEST_RUNNER!r}, router -> None, routed=False) and print a REAL "
        "SHA-256 node-id digest derived through the registry-dispatched pytest "
        "enumerate facet (no-regression: the Python digest path stays runner-"
        f"aware-but-byte-unchanged). {composition.diag()}"
    )


@then("the gate never degrades the Python digest to the no-digest placeholder")
def then_python_digest_not_degraded(composition: WholeTreeGateComposition) -> None:
    obs = composition.observable()
    assert obs.resolution_digest_degraded() is not True, (
        "the resolved pytest target must produce a real digest -- the digest leg "
        "must NEVER carry digest_degraded=True on the pytest path (that placeholder "
        f"is reserved for an un-enumerable non-pytest target). {composition.diag()}"
    )
