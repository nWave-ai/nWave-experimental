"""slice-04 (gate-outcome-record-seam): `run-contract-gate` writes a per-run
outcome record.

DDD-5 named `run-contract-gate` the first population target ("already
self-times, already accepts an injectable OutputPort -- the natural
exemplar"). Today it emits ad-hoc JSON events (`GateScopeDigest`,
`MalformedInput`, ...) but never calls
`AtCompletionLedger.append_gate_event(..., gate="run-contract-gate",
outcome=<GateVerdict>)` -- its pass/fail history is invisible to any ledger
reader.

This gate has no single natural `--feature-id` in its digest/verify-gate-scope
modes (both run feature-agnostic), so the singleton-shape ledger
(`AtCompletionLedger(project_root=...)`, `.nwave/audit/atdd-pure-events.jsonl`)
is the reuse target -- already the documented alternative construction shape
(`at_completion_ledger.py` docstring) and already used by a production
caller with the same feature-agnostic shape
(`des/cli/verify_deliver_integrity.py:448`). `feature_id` is omitted
(``None``) on these two feature-agnostic modes.

Two terminating paths exercised here, deterministically, without spawning a
real nested pytest collection (`_collect_scope_with_marker_fallback` and
`_maybe_route_digest_through_runner` are monkeypatched -- the same technique
`test_run_contract_gate_collect_memo.py` already uses on this module's
collection internals):

  * `--collect-only --print-digest` on a canned successful scope -> exit 0 ->
    outcome=PASS.
  * `--verify-gate-scope` with no `--commit` -> exit 2 (`MalformedInput`,
    already-established behaviour) -> outcome=INDETERMINATE (a malformed
    invocation cannot be evaluated, the could-not-determine third state).

Driving surface (Mandate 16, driving-port-only): the REAL `run_contract_gate`
CLI edge (`main(argv) -> int`), driven in-process via
`tests/common/in_process_cli.run_cli_in_process` -- no interpreter fork for
this unit-level pair (the feature's single subprocess-e2e walking skeleton
lives elsewhere, see `tests/des/acceptance/gate_outcome_wired_walking_skeleton/`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli import run_contract_gate
from des.cli.run_contract_gate import main as _run_contract_gate_main
from des.domain.gate_outcome import GateVerdict
from tests.common.in_process_cli import run_cli_in_process


_GATE_NAME = "run-contract-gate"


def _outcome_records(repo_root: Path) -> list[dict[str, object]]:
    """Every `GateOutcomeRecorded` record this gate wrote, singleton shape."""
    ledger = AtCompletionLedger(project_root=repo_root)
    return [
        record
        for record in ledger.read_records(event_type="GateOutcomeRecorded")
        if record.get("gate") == _GATE_NAME
    ]


# =============================================================================
# POSITIVE ATs -- active-RED today (no append_gate_event(outcome=...) call site
# exists anywhere in run_contract_gate.py)
# =============================================================================


def test_print_digest_pass_records_outcome_in_the_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A successful `--collect-only --print-digest` run appends exactly one
    `GateOutcomeRecorded` record naming this gate with `outcome=PASS`, without
    changing the existing exit-code/stdout contract (sibling-branch pin)."""
    monkeypatch.setattr(
        run_contract_gate, "_maybe_route_digest_through_runner", lambda repo: None
    )
    canned = run_contract_gate._CollectedScope(
        node_ids=["tests/fixture_repo/test_x.py::test_ok"], collected_count=1
    )
    monkeypatch.setattr(
        run_contract_gate,
        "_collect_scope_with_marker_fallback",
        lambda repo: canned,
    )

    exit_code, _stdout, _stderr = run_cli_in_process(
        ["--repo", str(tmp_path), "--collect-only", "--print-digest"],
        cwd=tmp_path,
        main=_run_contract_gate_main,
    )

    # Sibling-branch pin -- the existing PASS contract is untouched.
    assert exit_code == 0, f"expected exit 0 on a successful digest, got {exit_code}"

    records = _outcome_records(tmp_path)
    assert len(records) == 1, (
        f"expected exactly one GateOutcomeRecorded record for {_GATE_NAME!r} "
        f"after a PASS run -- got {records!r}"
    )
    assert records[0].get("outcome") == GateVerdict.PASS.value, records[0]


def test_verify_gate_scope_without_commit_records_indeterminate_outcome(
    tmp_path: Path,
) -> None:
    """`--verify-gate-scope` with no `--commit` is malformed input -- already
    exit 2 today (`MalformedInput`, unchanged) -- and must now ALSO append a
    `GateOutcomeRecorded` record naming `outcome=INDETERMINATE`: a malformed
    invocation cannot be evaluated PASS or FAIL, the could-not-determine
    third state GDP-8's arity corollary requires."""
    exit_code, _stdout, _stderr = run_cli_in_process(
        ["--repo", str(tmp_path), "--verify-gate-scope"],
        cwd=tmp_path,
        main=_run_contract_gate_main,
    )

    # Sibling-branch pin -- the existing malformed-input contract is untouched.
    assert exit_code == 2, (
        f"expected exit 2 on malformed --verify-gate-scope, got {exit_code}"
    )

    records = _outcome_records(tmp_path)
    assert len(records) == 1, (
        f"expected exactly one GateOutcomeRecorded record for {_GATE_NAME!r} "
        f"after a malformed-input run -- got {records!r}"
    )
    assert records[0].get("outcome") == GateVerdict.INDETERMINATE.value, records[0]


# =============================================================================
# NEGATIVE AT -- control: a run that writes NO ledger directory at all today
# must not regress once the outcome-recording call site lands elsewhere.
# =============================================================================


@pytest.mark.negative_at
def test_a_run_never_writes_two_outcome_records_for_one_invocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One invocation writes exactly one outcome record, never a duplicate --
    control pinning the once-per-terminating-path shape DDD-5's criterion
    names ("exactly one record")."""
    monkeypatch.setattr(
        run_contract_gate, "_maybe_route_digest_through_runner", lambda repo: None
    )
    canned = run_contract_gate._CollectedScope(
        node_ids=["tests/fixture_repo/test_x.py::test_ok"], collected_count=1
    )
    monkeypatch.setattr(
        run_contract_gate,
        "_collect_scope_with_marker_fallback",
        lambda repo: canned,
    )

    run_cli_in_process(
        ["--repo", str(tmp_path), "--collect-only", "--print-digest"],
        cwd=tmp_path,
        main=_run_contract_gate_main,
    )

    records = _outcome_records(tmp_path)
    assert len(records) == 1, (
        f"one invocation must append exactly one GateOutcomeRecorded record "
        f"-- got {len(records)}: {records!r}"
    )
