"""slice-04 (gate-outcome-record-seam): `verify-deliver-entry-contract`
writes a per-run outcome record.

DDD-5 named `verify-deliver-entry-contract` a first-population target
("peer-named live blocking gate, currently silent"). It already computes a
typed `outcome.verdict: GateVerdict` (PASS/FAIL/INDETERMINATE, `_EXIT_BY_
VERDICT`) and already constructs `AtCompletionLedger(args.feature_id,
args.repo_root)` (legacy per-feature shape) to write its `ContractFrozen`
record on PASS -- but never calls `append_gate_event(...,
gate="verify-deliver-entry-contract", outcome=...)` for ANY of its three
verdicts. This is the smallest-risk gate of the five: no new ledger-shape
decision is needed, the SAME already-constructed legacy-shape instance is
the reuse target for the new call too.

Two terminating paths exercised, reusing the established fixture shape from
`tests/bugs/des/test_verify_deliver_entry_contract_rejection_names_repair_tool.py`
(`_write_feature_delta` / `_write_slice_01_at_module` -- a real,
structurally-complete-or-incomplete `feature-delta.md` + a real bound AT
module):

  * a structurally-complete feature-delta -> exit 0 -> outcome=PASS.
  * a feature-delta missing a locked section -> exit 1 -> outcome=FAIL.

Driving surface (Mandate 16): the REAL `verify_deliver_entry_contract.main()`
CLI edge, driven in-process via `run_cli_in_process`.
"""

from __future__ import annotations

from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.domain.gate_outcome import GateVerdict
from tests.common.in_process_cli import run_cli_in_process
from tests.env_parity import seed_dev_checkout_marker


_GATE_NAME = "verify-deliver-entry-contract"
_FEATURE_ID = "outcome-record-fixture-verify-deliver"

_SLICE_PLAN = (
    "## Wave: DISCUSS / [REF] Slice Plan\n\n"
    "| Slice | Value statement | Status | Annotation | Justification |\n"
    "|-------|-----------------|--------|------------|---------------|\n"
    "| slice-01 | A thin DELIVER-IN vertical. | pending | "
    "@walking-skeleton @driving_port | ~4 ATs. |\n"
)
_ARCH_TESTS = (
    "## Wave: DESIGN / [REF] Architecture & Contract Tests\n\n"
    "| ID | Contract | SUT | Verdict | Consumed-by |\n"
    "|----|----------|-----|---------|-------------|\n"
    "| CT-1 | a contract is frozen | x::main | FAIL | DISTILL |\n"
)
_ADR_REFS = "## Wave: DESIGN / [REF] ADR Refs\n\n- slice-01: ADR-FLOW-004\n"
_REUSE_ANALYSIS = (
    "## Reuse Analysis\n\n"
    "| Existing Component | File | Overlap | Decision | Justification |\n"
    "|--------------------|------|---------|----------|---------------|\n"
    "| gate | x.py | none | CREATE_NEW | new gate. |\n"
)


def _write_feature_delta(repo_root: Path, *, complete: bool) -> None:
    """A feature-delta with all 4 locked sections, optionally dropping one."""
    feature_dir = repo_root / "docs" / "feature" / _FEATURE_ID
    feature_dir.mkdir(parents=True, exist_ok=True)
    sections = [_ARCH_TESTS, _ADR_REFS, _SLICE_PLAN]
    if complete:
        sections.append(_REUSE_ANALYSIS)
    header = f"# Feature Delta: {_FEATURE_ID}\n\n"
    (feature_dir / "feature-delta.md").write_text(
        header + "\n".join(sections) + "\n", encoding="utf-8"
    )


def _write_slice_01_at_module(repo_root: Path) -> None:
    """A `.feature` binding slice-01 to an AT (the `feature_tag_files` resolution)."""
    at_dir = repo_root / "tests" / "acceptance" / _FEATURE_ID.replace("-", "_")
    at_dir.mkdir(parents=True, exist_ok=True)
    (at_dir / "slice-01.feature").write_text(
        f"@feature-{_FEATURE_ID}\n"
        "Feature: the slice-01 walking skeleton\n\n"
        "  @slice-01 @walking_skeleton @driving_port\n"
        "  Scenario: the thin vertical is exercised\n"
        "    Given a structurally-complete contract\n"
        "    When the freeze gate runs\n"
        "    Then the contract is frozen\n",
        encoding="utf-8",
    )


def _outcome_records(repo_root: Path) -> list[dict[str, object]]:
    ledger = AtCompletionLedger(_FEATURE_ID, repo_root)
    return [
        record
        for record in ledger.read_records(event_type="GateOutcomeRecorded")
        if record.get("gate") == _GATE_NAME
    ]


# =============================================================================
# POSITIVE ATs -- active-RED today
# =============================================================================


def test_structurally_complete_contract_records_pass_outcome(tmp_path: Path) -> None:
    """A structurally-complete feature-delta freezes clean (exit 0,
    unchanged -- `ContractFrozen` still written) AND ALSO appends a
    GateOutcomeRecorded record with outcome=PASS."""
    _write_feature_delta(tmp_path, complete=True)
    _write_slice_01_at_module(tmp_path)
    seed_dev_checkout_marker(tmp_path)

    exit_code, _stdout, _stderr = run_cli_in_process(
        [
            "verify-deliver-entry-contract",
            "--feature-id",
            _FEATURE_ID,
            "--repo-root",
            str(tmp_path),
            "--format=json",
        ],
        cwd=tmp_path,
    )

    assert exit_code == 0, (
        f"expected a complete contract to freeze (exit 0), got {exit_code}"
    )

    records = _outcome_records(tmp_path)
    assert len(records) == 1, (
        f"expected exactly one GateOutcomeRecorded record for {_GATE_NAME!r} "
        f"after a PASS run -- got {records!r}"
    )
    assert records[0].get("outcome") == GateVerdict.PASS.value, records[0]


def test_missing_locked_section_records_fail_outcome(tmp_path: Path) -> None:
    """A feature-delta missing a locked [REF] section is REJECTED (exit 1,
    unchanged -- floor intact) AND appends a GateOutcomeRecorded record with
    outcome=FAIL."""
    _write_feature_delta(tmp_path, complete=False)
    seed_dev_checkout_marker(tmp_path)

    exit_code, _stdout, _stderr = run_cli_in_process(
        [
            "verify-deliver-entry-contract",
            "--feature-id",
            _FEATURE_ID,
            "--repo-root",
            str(tmp_path),
            "--format=json",
        ],
        cwd=tmp_path,
    )

    assert exit_code == 1, (
        f"expected a missing-section contract to be rejected, got {exit_code}"
    )

    records = _outcome_records(tmp_path)
    assert len(records) == 1, (
        f"expected exactly one GateOutcomeRecorded record for {_GATE_NAME!r} "
        f"after a FAIL run -- got {records!r}"
    )
    assert records[0].get("outcome") == GateVerdict.FAIL.value, records[0]
