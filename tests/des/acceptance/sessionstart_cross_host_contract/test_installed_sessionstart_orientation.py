# @feature-sessionstart-cross-host-contract
"""Installed host acceptance contract for the SessionStart orientation boundary."""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from tests.e2e.conftest import (
    _REPO_ROOT_FOR_WHEEL,
    _build_pypi_shape_wheel,
    _copy_repo_subset,
)


_MAX_ORIENTATION_BYTES = 2 * 1024


@pytest.fixture(scope="session")
def release_candidate_wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    sandbox = tmp_path_factory.mktemp("cross-host-sessionstart-candidate")
    _copy_repo_subset(_REPO_ROOT_FOR_WHEEL, sandbox)
    return _build_pypi_shape_wheel(sandbox)


def _candidate_paths(venv: Path) -> tuple[Path, Path]:
    executable = "Scripts" if os.name == "nt" else "bin"
    return venv / executable / "python", venv / executable / "nwave-ai"


def _environment(home: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.update(
        {
            "HOME": str(home),
            "CODEX_HOME": str(home / ".codex"),
            "CLAUDE_CONFIG_DIR": str(home / ".claude"),
            "PYTHONNOUSERSITE": "1",
        }
    )
    return environment


def _install_candidate(
    wheel: Path, home: Path, host: str, project: Path
) -> dict[str, str]:
    venv = home / "candidate"
    created = subprocess.run(
        [sys.executable, "-m", "venv", str(venv)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert created.returncode == 0, created.stderr
    python, nwave_ai = _candidate_paths(venv)
    installed = subprocess.run(
        [str(python), "-m", "pip", "install", str(wheel)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert installed.returncode == 0, installed.stderr
    environment = _environment(home)
    result = subprocess.run(
        [str(nwave_ai), "install", "--yes", "--platform", host],
        cwd=project,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    return environment


def _sessionstart_groups(home: Path, host: str) -> list[dict[str, object]]:
    config = home / (
        ".codex/hooks.json" if host == "codex" else ".claude/settings.json"
    )
    payload = json.loads(config.read_text(encoding="utf-8"))
    return payload["hooks"]["SessionStart"]


def _snapshot(paths: tuple[Path, ...]) -> dict[str, str]:
    observed: dict[str, str] = {}
    for root in paths:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file():
                observed[str(path.relative_to(root))] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
    return observed


def _write_mutation_traps(project: Path, home: Path) -> None:
    """Seed state that the retired mutable SessionStart path would consume.

    The installed SessionStart command must leave each byte untouched.  These
    are deliberately real lifecycle request names rather than fixture-only
    sentinels: a regression that reconnects the old handler has useful work to
    apply, clean up, or tick.
    """
    project_nwave = project / ".nwave"
    project_nwave.mkdir()
    (project_nwave / "loop-tick-work-exhausted.json").write_text(
        '{"request":"keep-me"}\n', encoding="utf-8"
    )
    (project_nwave / "loop-tick-bugfix-pipeline.json").write_text(
        '{"request":"keep-me"}\n', encoding="utf-8"
    )
    (project_nwave / "loop-tick-consolidation-signal.json").write_text(
        '{"request":"keep-me"}\n', encoding="utf-8"
    )
    home_nwave = home / ".nwave"
    home_nwave.mkdir(exist_ok=True)
    (home_nwave / "pending-update.json").write_text(
        '{"pm":"uv","target_version":"never-apply"}\n', encoding="utf-8"
    )


@pytest.fixture
def housekeeping_owned_mutation_trap() -> Callable[[Path], None]:
    """Seed records the legacy housekeeping routine is expected to delete."""

    def seed(project: Path) -> None:
        des_dir = project / ".nwave" / "des"
        audit_log = des_dir / "logs" / "audit-2000-01-01.log"
        stale_signal = des_dir / "des-task-active-sessionstart--step-1"
        stale_deliver = des_dir / "deliver-session.json"
        audit_log.parent.mkdir(parents=True)
        audit_log.write_text('{"owned_by":"housekeeping"}\n', encoding="utf-8")
        stale_signal.write_text('{"owned_by":"housekeeping"}\n', encoding="utf-8")
        stale_deliver.write_text('{"owned_by":"housekeeping"}\n', encoding="utf-8")
        stale_timestamp = 946684800
        for path in (audit_log, stale_signal, stale_deliver):
            os.utime(path, (stale_timestamp, stale_timestamp))

    return seed


def _canonical_orientation_command(host: str, command: str) -> str:
    if host == "codex":
        expected = "nwave_orchestrator_affordance_launcher.py"
    else:
        expected = "orchestrator_affordance_refresh.py"
    assert expected in command, (
        f"WHAT: installed {host} SessionStart command is not the canonical "
        f"orientation entry. WHY: one registration must not hide a legacy mutable "
        f"handler. HOW: install the host-owned {expected} entry."
    )
    return command


def _invoke_registered_sessionstart(
    host: str, command: str, project: Path, environment: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    """Drive the installed command in the syntax each host actually declares."""
    if host == "claude-code":
        # Claude retains a shell-shaped command: its leading DES marker is a
        # comment and must be interpreted by a shell, never split into argv.
        return subprocess.run(
            command,
            cwd=project,
            env=environment,
            input=json.dumps({"cwd": str(project)}),
            text=True,
            capture_output=True,
            check=False,
            shell=True,
            timeout=15,
        )
    # Codex declares the launcher as argv-shaped JSON configuration.  Preserve
    # exact-string inspection above, then execute its tokenized command without
    # a shell so the tested driver matches Codex's process contract.
    return subprocess.run(
        shlex.split(command),
        cwd=project,
        env=environment,
        input=json.dumps({"cwd": str(project)}),
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )


@pytest.mark.walking_skeleton
@pytest.mark.negative_at
@pytest.mark.parametrize("host", ("codex", "claude-code"))
def test_installed_host_sessionstart_emits_one_compact_read_only_orientation(
    host: str,
    tmp_path: Path,
    release_candidate_wheel: Path,
    housekeeping_owned_mutation_trap: Callable[[Path], None],
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    Permitted effect: one SessionStart protocol envelope on stdout. The
    maintainer project, nWave runtime state, and installed host configuration
    remain byte-identical.

    # covers: R1 R2 R3 R4
    """
    home = tmp_path / f"{host}-home"
    project = tmp_path / f"{host}-project"
    home.mkdir()
    project.mkdir()
    (project / "README.md").write_text("maintainer-owned\n", encoding="utf-8")
    environment = _install_candidate(release_candidate_wheel, home, host, project)
    _write_mutation_traps(project, home)
    housekeeping_owned_mutation_trap(project)

    groups = _sessionstart_groups(home, host)
    assert len(groups) == 1, (
        f"WHAT: installed {host} registers {len(groups)} SessionStart groups. "
        "WHY: a maintainer must receive one aggregate orientation, not competing "
        "handler groups with independent lifecycle effects. HOW: register one host-owned "
        "aggregate SessionStart entry and move maintenance ticking to an explicitly "
        "authorized surface."
    )
    hooks = groups[0].get("hooks")
    assert isinstance(hooks, list) and len(hooks) == 1, (
        f"WHAT: installed {host} SessionStart group does not contain exactly one hook. "
        "WHY: filtering only command hooks can conceal an additional lifecycle entry. "
        "HOW: retain exactly one canonical orientation hook in the entire population."
    )
    hook = hooks[0]
    assert isinstance(hook, dict) and hook.get("type") == "command", (
        f"WHAT: installed {host} SessionStart entry is not one executable command. "
        "WHY: the host must invoke one observable orientation surface. HOW: emit the "
        "canonical command hook as the sole SessionStart entry."
    )
    command = hook.get("command")
    assert isinstance(command, str), "SessionStart command must be a string."
    canonical_command = _canonical_orientation_command(host, command)

    before = _snapshot((project, home / ".nwave", home / ".codex", home / ".claude"))
    invocation = _invoke_registered_sessionstart(
        host, canonical_command, project, environment
    )
    assert invocation.returncode == 0, invocation.stderr
    assert invocation.stdout.strip(), (
        f"WHAT: installed {host} SessionStart command emitted no protocol envelope. "
        "WHY: a maintainer must receive the compact orientation when a session opens. "
        "HOW: make the sole canonical command emit one SessionStart JSON envelope."
    )
    output = json.loads(invocation.stdout)
    assert output["hookSpecificOutput"]["hookEventName"] == "SessionStart", (
        "WHAT: the installed hook emitted an envelope for the wrong lifecycle event. "
        "WHY: the orientation must be delivered when a session starts. HOW: emit a "
        "SessionStart hook protocol envelope from the canonical command."
    )
    orientation = output["hookSpecificOutput"]["additionalContext"]
    assert len(orientation.encode("utf-8")) <= _MAX_ORIENTATION_BYTES, (
        "WHAT: SessionStart orientation exceeds 2 KiB. WHY: every new session pays "
        "this shared prompt cost. HOW: emit only the compact aggregate orientation."
    )
    assert (
        _snapshot((project, home / ".nwave", home / ".codex", home / ".claude"))
        == before
    ), (
        "WHAT: SessionStart changed maintainer project or nWave state while update and "
        "loop-work requests were present. WHY: orientation is read-only and cannot "
        "silently apply updates, run housekeeping, or tick loops. HOW: keep maintenance "
        "behind an explicitly authorized DES command or separately authorized hook."
    )


@pytest.mark.negative_at
@pytest.mark.parametrize("host", ("codex", "claude-code"))
def test_installed_sessionstart_includes_conditional_throughput_directive(
    host: str, tmp_path: Path, release_candidate_wheel: Path
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    Permitted effect: one SessionStart protocol envelope on stdout.

    # covers: R2 R5
    """
    home = tmp_path / f"{host}-home"
    project = tmp_path / f"{host}-project"
    home.mkdir()
    project.mkdir()
    environment = _install_candidate(release_candidate_wheel, home, host, project)

    command = _sessionstart_groups(home, host)[0]["hooks"][0]["command"]
    assert isinstance(command, str)
    invocation = _invoke_registered_sessionstart(host, command, project, environment)
    assert invocation.returncode == 0, invocation.stderr
    orientation = json.loads(invocation.stdout)["hookSpecificOutput"][
        "additionalContext"
    ]
    directive = (
        "For multi-slice or multi-feature work, load `nw-throughput` before scheduling."
    )
    assert directive in orientation, (
        "WHAT: SessionStart does not state the conditional throughput directive. WHY: an "
        "orchestrator needs coordination guidance before scheduling parallel delivery, but "
        "must not load it for every session. HOW: include the concise multi-slice or "
        "multi-feature condition verbatim in the compact orientation."
    )
    assert len(orientation.encode("utf-8")) <= _MAX_ORIENTATION_BYTES
