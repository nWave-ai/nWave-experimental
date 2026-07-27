"""Public installer regression for legacy Codex SessionStart reconciliation."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path

from nwave_ai.state_delta import assert_state_delta, set_to


REPO_ROOT = Path(__file__).resolve().parents[4]
INSTALLER = REPO_ROOT / "scripts" / "install" / "install_nwave.py"


def _run_public_reinstall(home: Path) -> subprocess.CompletedProcess[str]:
    """Run Vera's documented Codex reinstall command in an isolated home."""
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "CODEX_HOME": str(home / ".codex"),
            "NWAVE_AGENTS_HOME": str(home),
            "CLAUDE_CONFIG_DIR": str(home / ".claude"),
        }
    )
    return subprocess.run(
        ["uv", "run", "python", str(INSTALLER), "--dev", "--platform", "codex"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )


def _session_start_commands(document: dict) -> list[str]:
    return [
        handler["command"]
        for group in document["hooks"]["SessionStart"]
        for handler in group["hooks"]
    ]


def test_reinstall_does_not_refuse_exact_legacy_session_start_hook(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation

    Outcome anchor: DISCUSS Elevator Pitch — developer reinstalls nWave with one
    current Codex hook.

    A developer can reinstall through the public Codex surface after removing
    only the current hook's provenance argument from its observed command.
    """
    home = tmp_path / "developer-home"
    home.mkdir()
    first_install = _run_public_reinstall(home)
    assert first_install.returncode == 0, (
        "WHAT: the first public Codex installation did not complete. WHY: the "
        "legacy fixture must be derived from an actual current install. HOW: make "
        "the documented --dev --platform codex installation return success.\n"
        f"command: {first_install.args}\ncwd: {REPO_ROOT}\n"
        f"HOME: {home}\nCODEX_HOME: {home / '.codex'}\n"
        f"stdout:\n{first_install.stdout}\nstderr:\n{first_install.stderr}"
    )

    hooks_path = home / ".codex" / "hooks.json"
    document = json.loads(hooks_path.read_text(encoding="utf-8"))
    commands = _session_start_commands(document)
    current_command = next(
        command
        for command in commands
        if "nwave_orchestrator_affordance_launcher.py" in command
        and "--host-provenance=codex" in command
    )
    current_argv = shlex.split(current_command)
    legacy_argv = [arg for arg in current_argv if arg != "--host-provenance=codex"]
    assert len(legacy_argv) == len(current_argv) - 1, (
        "WHAT: the observed current SessionStart command does not contain exactly "
        "one provenance argument. WHY: this regression must model the public legacy "
        "form precisely. HOW: expose one canonical --host-provenance=codex argument."
    )
    legacy_command = shlex.join(legacy_argv)
    lyra_command = "lyra session-start"
    near_miss_command = shlex.join([*current_argv, "--extra"])

    for group in document["hooks"]["SessionStart"]:
        for handler in group["hooks"]:
            if handler["command"] == current_command:
                handler["command"] = legacy_command
    document["hooks"]["SessionStart"].extend(
        [
            {
                "matcher": "startup",
                "hooks": [{"type": "command", "command": lyra_command}],
            },
            {
                "matcher": "startup",
                "hooks": [{"type": "command", "command": near_miss_command}],
            },
        ]
    )
    hooks_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    def state() -> dict[str, object]:
        commands = _session_start_commands(
            json.loads(hooks_path.read_text(encoding="utf-8"))
        )
        return {
            "session_start.current_nwave_count": commands.count(current_command),
            "session_start.legacy_nwave_present": legacy_command in commands,
            "session_start.lyra_present": lyra_command in commands,
            "session_start.near_miss_present": near_miss_command in commands,
        }

    before = state()
    reinstall = _run_public_reinstall(home)
    after = state()

    assert reinstall.returncode == 0, (
        "WHAT: public reinstall refused the exact legacy nWave SessionStart hook. "
        "WHY: reinstall is the recovery route for an older current hook. HOW: let "
        "ownership preflight recognize the exact no-provenance legacy command before "
        "reconciliation.\n"
        f"command: {reinstall.args}\ncwd: {REPO_ROOT}\n"
        f"HOME: {home}\nCODEX_HOME: {home / '.codex'}\n"
        f"stdout:\n{reinstall.stdout}\nstderr:\n{reinstall.stderr}"
    )
    assert_state_delta(
        before,
        after,
        universe=set(before),
        expected={
            "session_start.current_nwave_count": set_to(1),
            "session_start.legacy_nwave_present": set_to(False),
        },
    )
