"""Controlled host processes, shared package activity, and explicit commitment."""

from __future__ import annotations

import os
import select
import signal
import subprocess
from pathlib import Path

from tests.nwave_ai.test_update_continuity import _active_project, _events
from tests.nwave_ai.test_update_recovery import _cli, _installation


def _host(python: Path, directory: Path, body: str) -> Path:
    executable = directory / "claude"
    executable.write_text(f"#!{python}\n" + body, encoding="utf-8")
    executable.chmod(0o755)
    return executable


def _run(python: Path, root: Path, env: dict[str, str], *args: str):
    return subprocess.run(
        [str(python), "-P", "-m", "nwave_ai.cli", "run", "claude-code", "--", *args],
        cwd=root,
        env=env,
        input="\n",
        capture_output=True,
        text=True,
        timeout=30,
    )


def _consent(python: Path, root: Path, env: dict[str, str]) -> None:
    for args in (
        ("consent", "check", "on"),
        ("consent", "install", "on", "--confirm-old-sessions-closed"),
        ("consent", "controlled-launch", "on", "--confirm-controlled-launch"),
    ):
        outcome = _cli(python, root, env, *args)
        assert outcome.returncode == 0, outcome.stderr


def test_other_home_blocks_replacement_then_idle_succeeds_and_revocation_checks_only(
    tmp_path: Path,
):
    python, _, env, events, _, _, marker, shared = _installation(tmp_path)
    root = tmp_path / "clean"
    _active_project(root)
    _host(
        python,
        tmp_path / "tools",
        (
            "import json, os, pathlib, sys\n"
            "with pathlib.Path(os.environ['UPDATE_ORACLE_EVENTS']).open('a') as out:\n"
            "    out.write(json.dumps({'tool':'host','argv':sys.argv[1:]})+'\\n')\n"
            "print('HOST_READY', flush=True)\n"
            "sys.stdin.readline()\n"
        ),
    )
    default_off = _run(python, root, env)
    assert default_off.returncode == 0, default_off.stderr
    assert [event["tool"] for event in _events(events)] == ["host"], (
        "WHAT: managed startup checked a release or replaced a package with no consent. "
        "WHY: a recorded install choice grants neither automatic action. "
        "HOW: launch the host without release HTTP or package replacement."
    )
    events.unlink()
    check_grant = _cli(python, root, env, "consent", "check", "on")
    assert check_grant.returncode == 0, check_grant.stderr
    check_only = _run(python, root, env)
    assert check_only.returncode == 0, check_only.stderr
    assert [event["tool"] for event in _events(events)] == ["public-index", "host"], (
        "WHAT: check-only startup skipped the release check or replaced a package. "
        "WHY: a check grant needs neither install consent nor either install confirmation. "
        "HOW: check the release and launch the host without uv or DES."
    )
    events.unlink()
    _consent(python, root, env)
    other_home = tmp_path / "other-home"
    other_home.mkdir()
    other_env = env | {
        "NWAVE_AGENTS_HOME": str(other_home),
        "CLAUDE_CONFIG_DIR": str(other_home / ".claude"),
        "CODEX_HOME": str(other_home / ".codex"),
    }
    other = subprocess.Popen(
        [str(python), "-P", "-m", "nwave_ai.cli", "run", "claude-code", "--"],
        cwd=root,
        env=other_env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert select.select([other.stdout], [], [], 15)[0], "other host never started"
        assert other.stdout.readline().strip() == "HOST_READY"
        blocked = _run(python, root, env)
        assert blocked.returncode == 0, blocked.stderr
        assert all(event["tool"] == "host" for event in _events(events))
    finally:
        other.communicate(input="\n", timeout=10)
    assert other.returncode == 0
    events.unlink()
    installed = _run(python, root, env, "literal ; no shell", "two words")
    assert installed.returncode == 0, installed.stderr
    observed = _events(events)
    tools = [event["tool"] for event in observed]
    assert tools.count("uv") == 1 and tools.index("uv") < tools.index(
        "des"
    ) < tools.index("host")
    assert observed[-1] == {"tool": "host", "argv": ["literal ; no shell", "two words"]}
    assert not marker.exists() and not shared.exists()
    assert not list(
        (Path(env["NWAVE_AGENTS_HOME"]) / ".nwave/activity/sessions").iterdir()
    )
    install_off = _cli(python, root, env, "consent", "install", "off")
    assert install_off.returncode == 0, install_off.stderr
    events.unlink()
    install_revoked = _run(python, root, env)
    assert install_revoked.returncode == 0, install_revoked.stderr
    assert [event["tool"] for event in _events(events)] == ["public-index", "host"], (
        "WHAT: revoking install also stopped the check or still replaced the package. "
        "WHY: check remains granted while installation is independently revoked. "
        "HOW: keep the release check and host launch, with no uv or DES."
    )
    install_restored = _cli(python, root, env, "consent", "install", "on")
    assert install_restored.returncode == 0, install_restored.stderr
    assert (
        _cli(python, root, env, "consent", "controlled-launch", "off").returncode == 0
    )
    events.unlink()
    revoked = _run(python, root, env)
    assert revoked.returncode == 0, revoked.stderr
    assert [event["tool"] for event in _events(events)] == ["public-index", "host"]
    events.unlink()
    (root / "README.md").write_text("Unfinished local work\n")
    dirty = _run(python, root, env)
    assert dirty.returncode == 0, dirty.stderr
    assert [event["tool"] for event in _events(events)] == ["host"]


def test_surviving_descendant_retains_activity_and_copied_key_cannot_authorize_update(
    tmp_path: Path,
):
    python, root, env, events, _, _, _, shared = _installation(tmp_path)
    _host(
        python,
        tmp_path / "tools",
        (
            "import subprocess, sys\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], "
            "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
            "print(child.pid, flush=True)\n"
        ),
    )
    result = _run(python, root, env)
    child = int(result.stdout.strip())
    try:
        assert result.returncode == 0 and "uncertain" in result.stderr
        records = list(
            (Path(env["NWAVE_AGENTS_HOME"]) / ".nwave/activity/sessions").glob("*.json")
        )
        assert len(records) == 1
        key = records[0].stem
        assert (shared.parent / "sessions" / f"{key}.json").exists()
        forged = _cli(
            python,
            root,
            env | {"NWAVE_MANAGED_SESSION_KEY": key},
            "--yes",
            "--root",
            str(root),
            "--automatic-session",
            key,
        )
        assert forged.returncode == 1 and _events(events) == []
    finally:
        os.kill(child, signal.SIGKILL)
    closed = _cli(python, root, env, "sessions", "close", key, "--confirm-closed")
    assert closed.returncode == 0, closed.stderr
    assert not records[0].exists()
    assert not (shared.parent / "sessions" / f"{key}.json").exists()
