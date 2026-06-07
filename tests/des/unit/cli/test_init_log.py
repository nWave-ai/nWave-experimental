"""Unit tests for des.cli.init_log CLI module.

Tests the init_log CLI tool that initializes execution-log.json with
schema v3.0 format. All tests use tmp_path fixture.

Test Budget: 4 distinct behaviors x 1 = 4 tests.

Behaviors:
1. Success: creates file with correct schema
2. Fails if file already exists (exit 1)
3. Fails if project directory doesn't exist (exit 1)
4. Created file has correct JSON structure
"""

from __future__ import annotations

import json

from des.cli.init_log import main


def _write_classic_config(project_dir):
    """Seed an explicit `workflow.mode: classic` so init-log reaches its
    create / already-exists paths.

    DDD-7 (slice-03 mode-resolution SSOT): an absent `.nwave/config.yaml` now
    resolves to atdd_pure, under which init-log REFUSES to create the log. The
    log-CREATE mechanism these tests pin lives only on the classic spine, so the
    fixture seeds explicit-classic to exercise it. The intent (the create /
    already-exists mechanism) is unchanged; only the precondition is now explicit.
    """
    nwave_dir = project_dir / ".nwave"
    nwave_dir.mkdir(parents=True, exist_ok=True)
    (nwave_dir / "config.yaml").write_text("workflow:\n  mode: classic\n")


def test_creates_execution_log_successfully(tmp_path):
    """init_log creates execution-log.json with correct schema (explicit classic)."""
    _write_classic_config(tmp_path)
    exit_code = main(["--project-dir", str(tmp_path), "--feature-id", "my-feature"])

    assert exit_code == 0

    log_path = tmp_path / "execution-log.json"
    assert log_path.exists()

    data = json.loads(log_path.read_text())
    assert data["schema_version"] == "3.0"
    assert data["feature_id"] == "my-feature"
    assert data["events"] == []


def test_fails_if_file_already_exists(tmp_path, capsys):
    """init_log returns exit 1 when execution-log.json already exists (explicit classic)."""
    _write_classic_config(tmp_path)
    existing = tmp_path / "execution-log.json"
    existing.write_text("{}")

    exit_code = main(["--project-dir", str(tmp_path), "--feature-id", "my-feature"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "already exists" in captured.out


def test_fails_if_project_dir_missing(tmp_path, capsys):
    """init_log returns exit 1 when project directory does not exist."""
    nonexistent = tmp_path / "nonexistent"

    exit_code = main(["--project-dir", str(nonexistent), "--feature-id", "my-feature"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "does not exist" in captured.out


def test_json_structure_is_valid(tmp_path):
    """Created execution-log.json is valid JSON with exactly 3 keys (explicit classic)."""
    _write_classic_config(tmp_path)
    main(["--project-dir", str(tmp_path), "--feature-id", "test-feat"])

    data = json.loads((tmp_path / "execution-log.json").read_text())
    assert set(data.keys()) == {"schema_version", "feature_id", "events"}
