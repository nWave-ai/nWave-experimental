"""User-visible contract for the lean ``des feature-end`` namespace."""

from __future__ import annotations

from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process


def test_feature_end_help_does_not_advertise_removed_run_batch(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change

    The public help omits the removed batch-closing ceremony.
    """
    exit_code, stdout, stderr = run_cli_in_process(
        ["feature-end", "--help"], cwd=tmp_path
    )

    assert exit_code == 0
    assert stderr == ""
    assert "run-batch" not in stdout


def test_feature_end_rejects_removed_run_batch_argv(tmp_path: Path) -> None:
    """CONTRACT_SHAPE: bounded-change

    The public command rejects the removed batch-closing ceremony.
    """
    exit_code, stdout, stderr = run_cli_in_process(
        ["feature-end", "run-batch"], cwd=tmp_path
    )

    assert exit_code == 2
    assert stdout == ""
    assert "invalid choice: 'run-batch'" in stderr
