"""Hook-gate binding — project-activation-gating.

Gate behaviour: inactive → allow/exit-0 without mutation; active → dispatch;
stdin re-injected intact.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from pytest_bdd import scenarios

from tests.des.acceptance.activation_gating.steps.steps_activation_gating import *


scenarios("hook-gate.feature")


def test_real_hook_entrypoint_leaves_inactive_project_byte_identical(
    tmp_path: Path,
) -> None:
    """The installed module boundary must gate before freshness or audit writes."""
    project = tmp_path / "project"
    home = tmp_path / "home"
    project.mkdir()
    home.mkdir()
    before = list(project.rglob("*"))
    payload = json.dumps(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Agent",
            "tool_input": {"subagent_type": "nw-software-crafter"},
            "cwd": str(project),
        }
    )
    repo_root = Path(__file__).parents[4]
    env = dict(os.environ)
    env.update({"HOME": str(home), "PYTHONPATH": str(repo_root / "src")})

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "des.adapters.drivers.hooks.claude_code_hook_adapter",
            "pre-task",
        ],
        cwd=project,
        input=payload,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert list(project.rglob("*")) == before
