"""slice-04 (gate-outcome-record-seam): `mode-locus-gate` writes a per-run
outcome record.

DDD-5 named `mode-locus-gate` a first-population target ("peer-named live
blocking gate, currently silent"). It scans `nWave/{skills,agents,tasks}`
under `--root` and returns exit 0 (clean) / 2 (offenders found) / 3
(INDETERMINATE -- an `nWave/` tree exists but none of the scanned families
exist under it, so zero files were scanned) / 1 (no `nWave/` tree at all --
a misconfigured `--root`, out of scope here). It never calls
`AtCompletionLedger.append_gate_event(..., gate="mode-locus-gate",
outcome=<GateVerdict>)`.

This gate has no per-feature concept at all in its current CLI surface (a
repo-wide invariant scan, not a per-slice gate) -- the singleton-shape
ledger (`AtCompletionLedger(project_root=...)`) is the reuse target, same
choice as `run-contract-gate` and `validate-feature-delta`; `feature_id` is
omitted (``None``).

Three terminating paths exercised -- the gate's own three meaningful exit
codes (0/2/3), mapped onto the three `GateVerdict` states its own docstring
already names in prose (clean / offenders / zero-file-scan):

  * a clean `nWave/skills` tree -> exit 0 -> outcome=PASS.
  * `nWave/skills` containing a naked mode literal -> exit 2 -> outcome=FAIL.
  * an `nWave/` tree with NONE of the scanned families present -> exit 3 ->
    outcome=INDETERMINATE.

Driving surface (Mandate 16): the REAL `mode_locus_gate.main()` CLI edge,
driven in-process via `run_cli_in_process`.
"""

from __future__ import annotations

from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.mode_locus_gate import main as _mode_locus_gate_main
from des.domain.gate_outcome import GateVerdict
from tests.common.in_process_cli import run_cli_in_process


_GATE_NAME = "mode-locus-gate"


def _outcome_records(repo_root: Path) -> list[dict[str, object]]:
    ledger = AtCompletionLedger(project_root=repo_root)
    return [
        record
        for record in ledger.read_records(event_type="GateOutcomeRecorded")
        if record.get("gate") == _GATE_NAME
    ]


# =============================================================================
# POSITIVE ATs -- active-RED today
# =============================================================================


def test_clean_tree_records_pass_outcome(tmp_path: Path) -> None:
    """A `nWave/skills` tree with no naked mode literal scans clean (exit 0,
    unchanged) AND appends a GateOutcomeRecorded record with outcome=PASS."""
    skills_dir = tmp_path / "nWave" / "skills" / "demo-skill"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(
        "This skill discusses the classic mode of operation in prose.\n",
        encoding="utf-8",
    )

    exit_code, _stdout, _stderr = run_cli_in_process(
        ["--root", str(tmp_path)], cwd=tmp_path, main=_mode_locus_gate_main
    )

    assert exit_code == 0, (
        f"expected a clean tree to scan PASS (exit 0), got {exit_code}"
    )

    records = _outcome_records(tmp_path)
    assert len(records) == 1, (
        f"expected exactly one GateOutcomeRecorded record for {_GATE_NAME!r} "
        f"after a PASS run -- got {records!r}"
    )
    assert records[0].get("outcome") == GateVerdict.PASS.value, records[0]


def test_naked_literal_records_fail_outcome(tmp_path: Path) -> None:
    """A naked, unconditional `atdd_pure` literal outside a sanctuary is
    flagged (exit 2, unchanged -- floor intact) AND appends a
    GateOutcomeRecorded record with outcome=FAIL."""
    skills_dir = tmp_path / "nWave" / "skills" / "demo-skill"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(
        "workflow.mode == atdd_pure\n", encoding="utf-8"
    )

    exit_code, _stdout, _stderr = run_cli_in_process(
        ["--root", str(tmp_path)], cwd=tmp_path, main=_mode_locus_gate_main
    )

    assert exit_code == 2, (
        f"expected a naked literal to be flagged (exit 2), got {exit_code}"
    )

    records = _outcome_records(tmp_path)
    assert len(records) == 1, (
        f"expected exactly one GateOutcomeRecorded record for {_GATE_NAME!r} "
        f"after a FAIL run -- got {records!r}"
    )
    assert records[0].get("outcome") == GateVerdict.FAIL.value, records[0]


def test_zero_file_scan_records_indeterminate_outcome(tmp_path: Path) -> None:
    """An `nWave/` tree with NONE of the scanned families
    (skills/agents/tasks) present scans zero files -- already exit 3
    (INDETERMINATE, unchanged -- the gate's own docstring: "not the same
    fact as a clean scan") -- AND appends a GateOutcomeRecorded record with
    outcome=INDETERMINATE."""
    (tmp_path / "nWave").mkdir()

    exit_code, _stdout, _stderr = run_cli_in_process(
        ["--root", str(tmp_path)], cwd=tmp_path, main=_mode_locus_gate_main
    )

    assert exit_code == 3, (
        f"expected a zero-family scan to degrade LOUD (exit 3), got {exit_code}"
    )

    records = _outcome_records(tmp_path)
    assert len(records) == 1, (
        f"expected exactly one GateOutcomeRecorded record for {_GATE_NAME!r} "
        f"after an INDETERMINATE run -- got {records!r}"
    )
    assert records[0].get("outcome") == GateVerdict.INDETERMINATE.value, records[0]
