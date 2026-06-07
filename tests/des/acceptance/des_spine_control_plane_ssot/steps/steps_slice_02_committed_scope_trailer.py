"""Step bodies for des-spine-control-plane-ssot slice-02 (committed-scope trailer).

Mandate-12 criterion 3: every step body is ≤2 statements, ends in a single
`contract_gate_fixture.<method>(...)` call (or one `assert_state_delta` /
assertion), and contains zero control flow (`if`/`for`/`while`/`try`). All
business logic lives in `ContractGateFixture` (composition_slice_02.py).

Mandate 8: state-mutating assertions go through `assert_state_delta(before,
after, universe, expected)` from `tests.common.state_delta`. Universe entries are
port-exposed observables on `ProducerRun` (exit_code, outcome, stamped_digest,
indeterminate_emitted) — never Popen handles, never env dicts, never raw stream
bytes.

Mandate 9 v2: layer 3 (subprocess against tmp_path, @real-io — the driven set
includes a real filesystem adapter + a real git work-tree) → example-only. PBT
machinery is intentionally NOT imported.

Mandate 11: AT-02 (git-absent degrade-LOUD) is one explicit named example. No PBT.

Mandate-13: ATs drive through the production `des run-contract-gate` CLI
(subprocess) — NEVER a direct `from des.cli.run_contract_gate import ...` or
`from des.adapters.driven.git... import ...` invocation in test bodies.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from tests.common.state_delta import assert_state_delta, set_to

from .domain_types_slice_02 import (
    REVISION_CONTROL_BY_PHRASE,
    ProducerOutcome,
    VerifyOutcome,
)


# --- Universe (Mandate 8): port-exposed observables only -----------------

PRODUCER_UNIVERSE = frozenset(
    {
        "producer.exit_code",
        "producer.outcome",
        "producer.stamped_digest",
        "producer.indeterminate_emitted",
    }
)


def _producer_snapshot(state: dict) -> dict:
    """Build a universe snapshot of the producer observables. Pure function.

    Returns None sentinels for unobserved keys so the before-snapshot is
    well-defined before the producer is fired.
    """
    run = state.get("producer_run")
    return {
        "producer.exit_code": getattr(run, "exit_code", None),
        "producer.outcome": getattr(run, "outcome", None),
        "producer.stamped_digest": getattr(run, "stamped_digest", None),
        "producer.indeterminate_emitted": getattr(run, "indeterminate_emitted", None),
    }


# --- Given ----------------------------------------------------------------


@given(parsers.parse("a contract tree that is a {revision_phrase}"))
def given_contract_tree(contract_gate_fixture, state, revision_phrase: str) -> None:
    state["tree"] = contract_gate_fixture.build_contract_tree(
        revision_control=REVISION_CONTROL_BY_PHRASE[revision_phrase]
    )


# --- When -----------------------------------------------------------------


@when("the operator runs the contract gate over that tree")
def when_operator_runs_contract_gate(contract_gate_fixture, state) -> None:
    state["before"] = _producer_snapshot(state)
    state["producer_run"] = contract_gate_fixture.run_contract_gate(state["tree"])


@when("the stamped commit-scope trailer is verified against the tree it was stamped on")
def when_stamped_trailer_verified(contract_gate_fixture, state) -> None:
    state["verify_run"] = contract_gate_fixture.verify_stamped_trailer(state["tree"])


# --- Then -----------------------------------------------------------------


@then(
    "the contract gate stamps a portable commit-scope trailer and proceeds with "
    "exit code 0"
)
def then_stamps_portable_trailer(state) -> None:
    after = _producer_snapshot(state)
    assert_state_delta(
        before={k: state["before"][k] for k in PRODUCER_UNIVERSE},
        after={k: after[k] for k in PRODUCER_UNIVERSE},
        universe=PRODUCER_UNIVERSE,
        expected={
            "producer.exit_code": set_to(0),
            "producer.outcome": set_to(ProducerOutcome.STAMPED_PORTABLE),
            "producer.indeterminate_emitted": set_to(False),
            "producer.stamped_digest": _is_present,
        },
    )


@then("the stamped trailer matches the committed scope of the tree")
def then_trailer_matches_committed_scope(contract_gate_fixture, state) -> None:
    assert contract_gate_fixture.stamped_digest_matches_committed_scope(
        state["producer_run"], state["tree"]
    ), (
        "ADR-CP-001 producer==verifier: the stamped trailer must EQUAL the "
        "independent committed-scope digest of the same tree (committed-scope, "
        f"NOT working-tree); stamped={state['producer_run'].stamped_digest!r}"
    )


@then(
    "the contract gate runs the suite and stamps no trailer and proceeds with "
    "exit code 0"
)
def then_runs_suite_no_trailer(state) -> None:
    after = _producer_snapshot(state)
    assert_state_delta(
        before={k: state["before"][k] for k in PRODUCER_UNIVERSE},
        after={k: after[k] for k in PRODUCER_UNIVERSE},
        universe=PRODUCER_UNIVERSE,
        expected={
            "producer.exit_code": set_to(0),
            "producer.outcome": set_to(ProducerOutcome.RAN_NO_TRAILER),
            "producer.indeterminate_emitted": set_to(True),
            "producer.stamped_digest": set_to(None),
        },
    )


@then(
    parsers.parse(
        "the operator sees a LOUD `{marker}` marker naming the missing revision control"
    )
)
def then_operator_sees_loud_marker(state, marker: str) -> None:
    run = state["producer_run"]
    assert run.indeterminate_emitted, (
        f"degrade-LOUD (AD-23 / ADR-CP-001): expected the LOUD {marker!r} "
        "marker on the producer stream when git is absent (never a silent "
        f"working-tree fallback); stdout={run.stdout!r} stderr={run.stderr!r}"
    )


@then("no un-verifiable trailer is stamped")
def then_no_unverifiable_trailer(state) -> None:
    run = state["producer_run"]
    assert run.stamped_digest is None, (
        "KPI-4 (0 un-verifiable trailers): the producer must stamp NO digest on "
        "a git-absent tree — a trailer no checkout can verify is worse than none; "
        f"got stamped_digest={run.stamped_digest!r}"
    )


@then("the contract gate confirms the trailer verifies with exit code 0")
def then_trailer_verifies(state) -> None:
    run = state["verify_run"]
    assert run.outcome is VerifyOutcome.VERIFIED and run.exit_code == 0, (
        "ADR-CP-001 producer==verifier round-trip: a producer-stamped portable "
        "trailer must VERIFY (the verifier re-derives the SAME committed-scope "
        f"digest), proving portability; got outcome={run.outcome!r} "
        f"exit={run.exit_code} stdout={run.stdout!r} stderr={run.stderr!r}"
    )


# --- universe predicate (Mandate 8): trailer present without pinning a value ---


def _is_present(old, new) -> bool:
    """state-delta predicate `(old, new) -> bool`: changed to a non-None value.

    On the portable path the stamped digest's exact bytes are commit-specific;
    the universe assertion only pins that SOME digest was stamped (presence). The
    exact-equality-to-committed-scope check is a separate Then (AT-01's second
    step), keeping the universe predicate value-agnostic.
    """
    return new is not None and new != ""


_is_present.__name__ = "is_present"
