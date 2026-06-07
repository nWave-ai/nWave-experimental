"""Step definitions -- slice-02: atomic verify-then-record exit gate.

F-SIMPLIFY-ATDD-PURE-CARPACCIO-SPINE slice-02. Layer 3 (subprocess / FS
acceptance): the verify_slice_commit CLI with --feature-id is the driving port;
the AT-completion ledger (real JSONL) is the driven port. Example-based sad
paths (Mandate 11) -- the negative case (E2/E1 fails -> no record) is the M-3
non-vacuity contract, enumerated explicitly.

Shares ``CarpaccioSpineComposition`` (Pillar 3). The exit gate is a
bounded-change contract: it appends exactly one ledger record IFF both halves
pass, asserted via ``assert_state_delta`` over a port-exposed universe
(Mandate 8). RED-by-design held green via the suite ``conftest.py``
``xfail(strict=True)`` mechanism.

Seam contract (C_REVIEWER_AUDIT BLOCKER closure): the universe slot
``ledger.verified_slices`` is the set returned by
``AtCompletionLedger.verified_slices()`` -- the exact seam the carpaccio chain
(slice-03 predecessor check, M-2 backstop) consumes at
``.nwave/telemetry/atdd-pure/{feature_id}.jsonl``. A record at the wrong path,
or one missing the M7 ``seq`` / ``record_hash`` integrity fields, is NOT
observable here -- so an AT GREEN genuinely proves the chain-readable seam.
The idempotency scenario asserts the SET stays a singleton under a re-run, so a
re-verification cannot corrupt the predecessor ordering the chain depends on.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from tests.common.state_delta import assert_state_delta, set_to, unchanged

from .composition import CarpaccioSpineComposition
from .domain_types import (
    EXIT_CODE_BY_VERDICT,
    FAILING_GATE_HALF_BY_PHRASE,
    CommitRef,
    GateVerdict,
)


scenarios("../slice-02-atomic-verify-then-record.feature")


@pytest.fixture
def composition(tmp_path: Path) -> CarpaccioSpineComposition:
    return CarpaccioSpineComposition(project_root=tmp_path / "project")


@pytest.fixture
def result_box() -> dict[str, object]:
    return {}


# --- Given -------------------------------------------------------------------


@given("a feature project with a multi-slice plan")
def given_feature_project(composition: CarpaccioSpineComposition) -> None:
    composition.create_feature_project(composition.feature_id)


@given("a slice commit exists for the entering slice")
def given_slice_commit(composition: CarpaccioSpineComposition) -> None:
    composition.create_slice_commit()


@given("the slice commit passes both the completeness and contract checks")
def given_both_pass(composition: CarpaccioSpineComposition) -> None:
    composition.arrange_slice_commit(both_checks_pass=True)


@given(parsers.parse("the slice commit where {failure}"))
def given_one_check_fails(composition: CarpaccioSpineComposition, failure: str) -> None:
    composition.arrange_failing_exit_gate(FAILING_GATE_HALF_BY_PHRASE[failure])


@given("the orchestrator has already run the slice-commit exit gate for the slice")
def given_exit_gate_already_run(
    composition: CarpaccioSpineComposition, result_box: dict[str, object]
) -> None:
    composition.run_verify_slice_commit(CommitRef("HEAD"))


# --- When --------------------------------------------------------------------


@when("the orchestrator runs the slice-commit exit gate")
def when_run_exit_gate(
    composition: CarpaccioSpineComposition, result_box: dict[str, object]
) -> None:
    before = composition.capture_universe()
    result_box["result"] = composition.run_verify_slice_commit(CommitRef("HEAD"))
    after = composition.capture_universe()
    result_box["before"] = before
    result_box["after"] = after


@when("the orchestrator runs the slice-commit exit gate again on the same commit")
def when_rerun_exit_gate(
    composition: CarpaccioSpineComposition, result_box: dict[str, object]
) -> None:
    before = composition.capture_universe()
    result_box["result"] = composition.run_verify_slice_commit(CommitRef("HEAD"))
    after = composition.capture_universe()
    result_box["before"] = before
    result_box["after"] = after


# --- Then --------------------------------------------------------------------


@then("the slice-commit exit gate clears the slice")
def then_exit_gate_clears(result_box: dict[str, object]) -> None:
    result = result_box["result"]
    assert result.exit_code == EXIT_CODE_BY_VERDICT[GateVerdict.CLEARED], (
        f"expected exit 0 (cleared); got {result.exit_code}: {result.stderr}"
    )


@then("the slice-commit exit gate is refused")
def then_exit_gate_refused(
    composition: CarpaccioSpineComposition, result_box: dict[str, object]
) -> None:
    result = result_box["result"]
    assert "Traceback (most recent call last)" not in result.stderr, (
        f"the exit gate crashed rather than refusing "
        f"(exit {result.exit_code}); stderr:\n{result.stderr}"
    )
    # RED-honesty guard: a genuine atomic-verify refusal emits a structured
    # JSON verdict naming which half (E1 / E2) failed. An argparse usage error
    # (an unknown --feature-id flag the CLI does not yet accept) also exits
    # non-zero but emits NO such verdict -- so this step is genuinely RED until
    # the CLI composes E1+E2 and the conditional record (DDD-3).
    verdict = composition.parsed_verdict(result)
    assert verdict.get("refused_half") in {"E1", "E2"}, (
        f"expected a structured verify-then-record refusal naming the failed "
        f"half; got verdict={verdict!r}, exit {result.exit_code}: {result.stderr}"
    )
    assert result.exit_code != 0, (
        f"expected a non-zero refusal; got exit 0: {result.stdout}"
    )


@then("the entering slice is reported as verified to the carpaccio chain")
def then_slice_verified_to_chain(
    composition: CarpaccioSpineComposition, result_box: dict[str, object]
) -> None:
    # The seam is verified_slices() -- the carpaccio chain's read surface. A
    # record at the wrong substrate, or one missing the M7 integrity fields,
    # never reaches this set, so the bounded-change delta below genuinely reds
    # if the production writes the wrong seam.
    assert_state_delta(
        before=result_box["before"],
        after=result_box["after"],
        universe={"ledger.verified_slices", "tests.slice_feature_files"},
        expected={
            "ledger.verified_slices": set_to(
                frozenset({str(composition.entering_slice)})
            ),
            "tests.slice_feature_files": unchanged(),
        },
    )


@then("the carpaccio chain reports no verified slice")
def then_no_verified_slice(result_box: dict[str, object]) -> None:
    assert_state_delta(
        before=result_box["before"],
        after=result_box["after"],
        universe={"ledger.verified_slices", "tests.slice_feature_files"},
        expected={
            "ledger.verified_slices": unchanged(),
            "tests.slice_feature_files": unchanged(),
        },
    )


@then("the carpaccio chain still reports the slice as verified exactly once")
def then_slice_verified_exactly_once(
    composition: CarpaccioSpineComposition, result_box: dict[str, object]
) -> None:
    # C4a idempotency: the FIRST run (the Given) already verified the slice, so
    # the set is unchanged by the re-run -- and it is a singleton. verified_slices()
    # is set-valued, so the slice appears exactly once however many records
    # carry it; a re-run must not corrupt the predecessor ordering slice-03
    # depends on.
    assert_state_delta(
        before=result_box["before"],
        after=result_box["after"],
        universe={"ledger.verified_slices", "tests.slice_feature_files"},
        expected={
            "ledger.verified_slices": unchanged(),
            "tests.slice_feature_files": unchanged(),
        },
    )
    assert composition.verified_slices() == frozenset(
        {str(composition.entering_slice)}
    ), (
        "the carpaccio chain must see the slice verified exactly once after a "
        f"re-run; got verified_slices()={composition.verified_slices()!r}"
    )
