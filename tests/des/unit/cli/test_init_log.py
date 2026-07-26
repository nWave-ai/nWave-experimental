"""Safety regressions for the retired classic ``init-log`` carrier."""

from __future__ import annotations

from pathlib import Path

import pytest

from des.cli.init_log import main


def _write_mode(project_dir: Path, mode: str) -> bytes:
    nwave_dir = project_dir / ".nwave"
    nwave_dir.mkdir(parents=True, exist_ok=True)
    config = nwave_dir / "config.yaml"
    config.write_text(f"workflow:\n  mode: {mode}\n", encoding="utf-8")
    return config.read_bytes()


@pytest.mark.parametrize("mode", ("classic", "atdd_pure"))
def test_init_log_never_creates_a_runnable_classic_execution_log(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    mode: str,
) -> None:
    before = _write_mode(tmp_path, mode)

    exit_code = main(["--project-dir", str(tmp_path), "--feature-id", "retired-spine"])

    assert exit_code != 0
    assert not (tmp_path / "execution-log.json").exists()
    assert (tmp_path / ".nwave" / "config.yaml").read_bytes() == before
    captured = capsys.readouterr()
    output = captured.out + captured.err
    if mode == "classic":
        assert "CLASSIC_MODE_REMOVED" in output
        assert "MIGRATION_REQUIRED" in output
    else:
        assert "atdd_pure" in output
        assert "execution-log-free" in output


def test_existing_historical_log_is_not_mutated_or_resumed(
    tmp_path: Path,
) -> None:
    _write_mode(tmp_path, "classic")
    historical = tmp_path / "execution-log.json"
    historical.write_bytes(b'{"schema_version":"4.0","events":[]}')
    before = historical.read_bytes()

    exit_code = main(["--project-dir", str(tmp_path), "--feature-id", "retired-spine"])

    assert exit_code != 0
    assert historical.read_bytes() == before


def test_missing_project_is_still_a_non_mutating_refusal(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    nonexistent = tmp_path / "nonexistent"
    exit_code = main(
        ["--project-dir", str(nonexistent), "--feature-id", "retired-spine"]
    )
    assert exit_code != 0
    assert "does not exist" in capsys.readouterr().out
    assert not nonexistent.exists()
