"""Integration test for the OpenCode DES shim's protocol parity.

This test invokes the Python DES adapter via subprocess with CC-format JSON,
exactly as the TypeScript shim would. It verifies the end-to-end contract:
the adapter accepts CC-format JSON on stdin and, in an enabled repo, an
ordinary nWave-adjacent Agent dispatch with no retired DES markers is
allowed, without requiring or recreating the retired execution-log carrier.

`tests/opencode/test_protocol_translation.py` separately owns the
TypeScript action/tool mapping.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


# Project root for PYTHONPATH
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)

# The adapter module invoked by the TS shim
ADAPTER_MODULE = "des.adapters.drivers.hooks.claude_code_hook_adapter"


def _run_adapter(
    action: str, stdin_json: dict, env_extra: dict | None = None
) -> subprocess.CompletedProcess:
    """Invoke the Python DES adapter as a subprocess, same as TS shim would.

    Args:
        action: CLI action (pre-task, pre-write, pre-edit, session-start)
        stdin_json: JSON dict piped to stdin
        env_extra: Additional environment variables

    Returns:
        CompletedProcess with stdout, stderr, returncode
    """
    env = os.environ.copy()
    # Src-layout: `des/` lives under PROJECT_ROOT/src/, not PROJECT_ROOT.
    # Pytest's `pythonpath = ["src", "."]` covers in-process imports but does
    # NOT propagate to subprocesses. Without `src/` here, the subprocess
    # gets ModuleNotFoundError: No module named 'des.adapters' → exit 1
    # instead of the expected policy exit code (0 allow / 2 block).
    env["PYTHONPATH"] = os.pathsep.join([str(Path(PROJECT_ROOT) / "src"), PROJECT_ROOT])
    if env_extra:
        env.update(env_extra)

    return subprocess.run(
        [sys.executable, "-m", ADAPTER_MODULE, action],
        input=json.dumps(stdin_json),
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )


class TestOpenCodeShimProtocolParity:
    """The OpenCode shim's current value: CC-format JSON reaches the Python
    adapter, and an ordinary nWave-adjacent dispatch is allowed without any
    retired DES marker or execution-log carrier."""

    def test_ordinary_agent_dispatch_allowed(self, tmp_path):
        """Adapter allows an ordinary Agent dispatch with no DES markers."""
        config_dir = tmp_path / ".nwave"
        config_dir.mkdir()
        (config_dir / "local-config.json").write_text(
            json.dumps({"enabled_for_repo": True}), encoding="utf-8"
        )

        cc_json = {
            "tool_name": "Agent",
            "tool_input": {
                "prompt": "Implement the user repository",
                "subagent_type": "nw-software-crafter",
            },
        }

        result = _run_adapter(
            "pre-task",
            cc_json,
            env_extra={"DES_PROJECT_DIR": str(tmp_path)},
        )

        assert result.returncode == 0, (
            f"Expected exit 0 (allow), got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

        response = json.loads(result.stdout)
        hook_specific_output = response.get("hookSpecificOutput", {})
        assert hook_specific_output.get("permissionDecision") == "allow", (
            f"Expected permissionDecision 'allow', got: {response}"
        )
        additional_context = hook_specific_output.get("additionalContext", "")
        assert "nw-mode-select" in additional_context, (
            f"additionalContext should name nw-mode-select, got: {additional_context!r}"
        )

        assert not (tmp_path / ".des" / "execution-log.json").exists(), (
            "a supported dispatch must not require or recreate the retired "
            "execution-log carrier"
        )
