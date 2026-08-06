from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from scripts.release import smoke_opencode_installed_hook as smoke


def test_nonworking_rendered_adapter_route_makes_smoke_red(tmp_path: Path) -> None:
    rendered = (
        f'PYTHONPATH: "{tmp_path}"\n'
        f'["{sys.executable}", "-m", "definitely.missing.adapter", action]'
    )

    with pytest.raises(SystemExit, match="OpenCode installed-hook smoke failed"):
        smoke._verify_rendered_adapter_route(
            rendered,
            runtime_dir=tmp_path,
            cwd=tmp_path,
            environment=os.environ.copy(),
        )


def test_run_reaps_the_process_group_when_the_wall_clock_fires(tmp_path: Path) -> None:
    """A release smoke timeout must not leave a Bun/Python child tree behind."""
    process = Mock()
    process.pid = 4242
    process.returncode = -9
    process.communicate.side_effect = [
        subprocess.TimeoutExpired(["bun", "run", "hook.ts"], 12),
        ("partial output", "partial errors"),
    ]

    with (
        patch.object(smoke.subprocess, "Popen", return_value=process) as popen,
        patch.object(smoke.os, "killpg") as killpg,
        patch.dict(os.environ, {smoke._TIMEOUT_ENV: "12"}, clear=False),
        pytest.raises(SystemExit, match="timed out after 12s"),
    ):
        smoke._run(["bun", "run", "hook.ts"], cwd=tmp_path, env=os.environ.copy())

    assert popen.call_args.kwargs["stdin"] is subprocess.DEVNULL
    assert popen.call_args.kwargs["start_new_session"] is (os.name == "posix")
    process.communicate.assert_any_call(input=None, timeout=12.0)
    if os.name == "posix":
        killpg.assert_called_once_with(4242, smoke.signal.SIGKILL)
    else:
        process.kill.assert_called_once_with()
