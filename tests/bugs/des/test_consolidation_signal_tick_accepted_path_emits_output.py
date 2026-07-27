"""Regression: `des consolidation-signal-tick` must not succeed in total
silence while its refusal branch speaks.

defects.md item
`consolidation-signal-tick-succeeds-in-total-silence-while-its-refusal-branch-speaks`:
``des.cli.consolidation_signal_tick.main``'s REJECTED branch emits a loud
``CONSOLIDATION_SIGNAL_INTAKE_REJECTED: <reason>`` line (an earlier EXAMINE
fix), but the ACCEPTED/ALREADY_QUEUED paths fell straight through to
``return 0`` with zero output -- a caller watching only the CLI's own
output (never opening the ledger) had no way to tell whether a signal was
recorded, or to learn the derived ``defect_id``.

Fix: `main` now emits one line naming the decision
(``CONSOLIDATION_SIGNAL_INTAKE_ACCEPTED`` / ``..._ALREADY_QUEUED``), the
``signal_type``/``signal_key`` inputs, and the derived ``defect_id`` -- on
every non-REJECTED outcome. This file drives the REAL CLI entry in-process
(Mandate-13 driving-port-only), never the domain seam directly.

THIS FILE IS TEST-ONLY. Production fix lives in
``src/des/cli/consolidation_signal_tick.py``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from des.cli.consolidation_signal_tick import main as consolidation_signal_tick_main
from tests.common.in_process_cli import run_cli_in_process


_FEATURE_ID = "consolidation-signal-tick-accepted-output-regression"
_NOW = (
    datetime(2026, 7, 26, 10, 0, 0, tzinfo=timezone.utc)
    .isoformat()
    .replace("+00:00", "Z")
)


def _tick(
    repo_root: Path, *, signal_type: str, signal_key: str
) -> tuple[int, str, str]:
    argv = [
        "--feature-id",
        _FEATURE_ID,
        "--project-root",
        str(repo_root),
        "--signal-type",
        signal_type,
        "--signal-key",
        signal_key,
        "--now",
        _NOW,
    ]
    return run_cli_in_process(argv, cwd=repo_root, main=consolidation_signal_tick_main)


def test_accepted_intake_emits_a_named_output_line(tmp_path: Path) -> None:
    """POSITIVE (the defect): a first-time, supported signal (ACCEPTED) must
    emit a non-empty line naming the signal and its derived defect_id --
    never silent exit 0.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    exit_code, stdout, _stderr = _tick(
        repo_root, signal_type="drift", signal_key="module-x"
    )

    assert exit_code == 0, f"expected exit 0 on ACCEPTED: got {exit_code}, {stdout!r}"
    assert stdout.strip(), (
        "ACCEPTED intake must emit a non-empty output line -- the CLI must "
        "not succeed in total silence while its REJECTED branch speaks"
    )
    assert "CONSOLIDATION_SIGNAL_INTAKE_ACCEPTED" in stdout
    assert "drift" in stdout
    assert "module-x" in stdout
    assert "consolidation-drift-module-x" in stdout


def test_already_queued_intake_emits_a_named_output_line(tmp_path: Path) -> None:
    """POSITIVE: re-detecting the SAME signal (ALREADY_QUEUED) must also
    emit a non-empty, decision-naming output line -- not just the first
    (ACCEPTED) tick.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _tick(repo_root, signal_type="stale-branch", signal_key="feature/foo")

    exit_code, stdout, _stderr = _tick(
        repo_root, signal_type="stale-branch", signal_key="feature/foo"
    )

    assert exit_code == 0, f"expected exit 0 on ALREADY_QUEUED: got {exit_code}"
    assert stdout.strip(), "ALREADY_QUEUED intake must not exit in silence"
    assert "CONSOLIDATION_SIGNAL_INTAKE_ALREADY_QUEUED" in stdout


def test_rejected_intake_still_emits_its_own_pre_existing_line(tmp_path: Path) -> None:
    """NEGATIVE ORACLE (must not regress): the REJECTED branch's own
    pre-existing loud line must be unaffected by this fix.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    exit_code, stdout, _stderr = _tick(
        repo_root, signal_type="not-a-real-signal-type", signal_key="x"
    )

    assert exit_code == 1
    assert "CONSOLIDATION_SIGNAL_INTAKE_REJECTED" in stdout
