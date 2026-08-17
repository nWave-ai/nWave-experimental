"""Unit tests for the live hook adapter resilience paths.

Tests resilience fixes:
- Empty stdin → exit 0 (allow passthrough) for PreToolUse
- task signal reads tolerate missing files
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch


def _invoke_hook(hook_type: str, stdin_data: str) -> tuple[int, dict]:
    """Invoke hook adapter as subprocess, matching Claude Code protocol."""
    env = os.environ.copy()
    project_root = str(Path(__file__).parent.parent.parent.parent.parent)
    src_path = str(Path(project_root) / "src")
    env["PYTHONPATH"] = src_path + os.pathsep + env.get("PYTHONPATH", "")

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "des.adapters.drivers.hooks.claude_code_hook_adapter",
            hook_type,
        ],
        input=stdin_data,
        capture_output=True,
        text=True,
        env=env,
    )
    response = json.loads(proc.stdout) if proc.stdout.strip() else {}
    return proc.returncode, response


class TestEmptyStdinResilience:
    """UT-14/UT-15: Empty stdin produces exit 0 allow for both hook types."""

    def test_empty_stdin_pre_tool_use_exits_0(self) -> None:
        """UT-14: PreToolUse with empty stdin exits 0 with allow."""
        exit_code, response = _invoke_hook("pre-tool-use", "")
        assert exit_code == 0
        assert response == {}, f"Allow path should produce no stdout. Got: {response}"

    def test_whitespace_only_stdin_pre_tool_use_exits_0(self) -> None:
        """PreToolUse with whitespace-only stdin exits 0."""
        exit_code, response = _invoke_hook("pre-tool-use", "   \n  ")
        assert exit_code == 0
        assert response == {}, f"Allow path should produce no stdout. Got: {response}"


class TestTaskStartTimeFromSignal:
    """UT-17: task_start_time is read from des-task-active signal file."""

    def test_task_start_time_read_from_namespaced_signal(self, tmp_path: Path) -> None:
        """UT-17: read_signal reads from namespaced signal file."""
        from des.adapters.drivers.hooks import des_task_signal

        # Create a namespaced signal file
        signal_dir = tmp_path / ".nwave" / "des"
        signal_dir.mkdir(parents=True)
        signal_file = signal_dir / "des-task-active-my-project--01-03"
        signal_data = {
            "step_id": "01-03",
            "project_id": "my-project",
            "created_at": "2026-02-10T14:30:00+00:00",
        }
        signal_file.write_text(json.dumps(signal_data))

        with patch.object(des_task_signal, "DES_SESSION_DIR", signal_dir):
            result = des_task_signal.read_signal(
                project_id="my-project", step_id="01-03"
            )

        assert result is not None
        assert result["created_at"] == "2026-02-10T14:30:00+00:00"
        assert result["step_id"] == "01-03"
        assert result["project_id"] == "my-project"

    def test_fallback_to_legacy_singleton(self, tmp_path: Path) -> None:
        """read_signal falls back to legacy singleton when no namespaced file."""
        from des.adapters.drivers.hooks import des_task_signal

        signal_dir = tmp_path / ".nwave" / "des"
        signal_dir.mkdir(parents=True)
        # Only legacy singleton exists (no namespaced file)
        legacy_file = signal_dir / "des-task-active"
        legacy_data = {
            "step_id": "01-03",
            "created_at": "2026-02-10T14:30:00+00:00",
        }
        legacy_file.write_text(json.dumps(legacy_data))

        with (
            patch.object(des_task_signal, "DES_SESSION_DIR", signal_dir),
            patch.object(des_task_signal, "DES_TASK_ACTIVE_FILE", legacy_file),
        ):
            result = des_task_signal.read_signal(
                project_id="my-project", step_id="01-03"
            )

        assert result is not None
        assert result["created_at"] == "2026-02-10T14:30:00+00:00"

    def test_missing_signal_returns_none(self) -> None:
        """read_signal returns None when no signal file exists."""
        from des.adapters.drivers.hooks import des_task_signal

        nonexistent_dir = Path("/tmp/nonexistent-des-dir-test")
        nonexistent = Path("/tmp/nonexistent-des-task-active-test")
        with (
            patch.object(des_task_signal, "DES_SESSION_DIR", nonexistent_dir),
            patch.object(des_task_signal, "DES_TASK_ACTIVE_FILE", nonexistent),
        ):
            result = des_task_signal.read_signal(
                project_id="my-project", step_id="01-03"
            )

        assert result is None
