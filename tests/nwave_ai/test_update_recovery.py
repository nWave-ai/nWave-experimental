"""Interrupted updates remain visible until real, owner-bound recovery succeeds."""

from __future__ import annotations

import json
import os
import signal
import subprocess
from pathlib import Path

import pytest

from tests.nwave_ai.test_update_continuity import _events, _startup_environment


def _installation(tmp_path: Path):
    python, events, env = _startup_environment(tmp_path)
    root = tmp_path / "project"
    root.mkdir()
    home = Path(env["NWAVE_AGENTS_HOME"])
    config = home / ".nwave" / "config.json"
    config.parent.mkdir(parents=True)
    config.write_text(
        json.dumps(
            {
                "schema-version": 1,
                "install": {
                    "target_platforms": ["codex"],
                    "dev_mode": False,
                    "host_paths": {
                        "agents_home": str(home),
                        "claude_config_dir": env["CLAUDE_CONFIG_DIR"],
                        "codex_config_dir": env["CODEX_HOME"],
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    failure = tmp_path / "refuse-sync"
    external = (
        f"#!{python}\n"
        "import json, os, pathlib, sys\n"
        "tool = pathlib.Path(sys.argv[0]).name\n"
        "with pathlib.Path(os.environ['UPDATE_ORACLE_EVENTS']).open('a') as output:\n"
        "    output.write(json.dumps({'tool':tool, 'argv':sys.argv[1:]}) + '\\n')\n"
        "if tool == 'nwave-ai' and sys.argv[1:] == ['--version']:\n"
        "    print('nwave-ai 999.0.0')\n"
        f"elif tool == 'nwave-ai' and '--dry-run' not in sys.argv and pathlib.Path({str(failure)!r}).exists():\n"
        "    print('selected host synchronization refused', file=sys.stderr)\n"
        "    raise SystemExit(51)\n"
    )
    for executable in (
        python.with_name("nwave-ai"),
        python.with_name("des"),
        tmp_path / "tools" / "uv",
    ):
        executable.write_text(external, encoding="utf-8")
        executable.chmod(0o755)
    marker = home / ".nwave" / "activity" / "update-in-progress.json"
    package_marker = (
        python.parent.parent.parent
        / f".{python.parent.parent.name}.nwave-activity.lock.state"
        / ".nwave"
        / "activity"
        / "update-in-progress.json"
    )
    return python, root, env, events, config, failure, marker, package_marker


def _cli(python: Path, root: Path, env: dict[str, str], *args: str):
    return subprocess.run(
        [str(python), "-P", "-m", "nwave_ai.cli", "update", *args],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_failed_sync_blocks_checks_and_replacement_until_verified_recovery(
    tmp_path: Path,
):
    python, root, env, events, _config, failure, marker, shared = _installation(
        tmp_path
    )
    failure.touch()
    refused = _cli(python, root, env, "--yes", "--root", str(root))
    assert refused.returncode == 1 and "synchronize-framework" in refused.stderr
    document = json.loads(marker.read_text())
    assert document["target_version"] == "999.0.0"
    assert document["completed_stages"] == [
        "replace-package",
        "verify-executable",
        "preflight-framework",
    ]
    assert document["running_stage"] == "synchronize-framework"
    assert json.loads(shared.read_text()) == document
    # Model the installed distribution after replacement: discovery's 999.0.0
    # now equals the running package, but selected-host synchronization failed.
    (tmp_path / "nwave_ai-1.4.0.dist-info" / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: nwave-ai\nVersion: 999.0.0\n",
        encoding="utf-8",
    )
    version = subprocess.run(
        [str(python), "-P", "-m", "nwave_ai.cli", "--version"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert version.returncode == 0 and version.stdout.strip() == "nwave-ai 999.0.0"
    observations = _events(events)
    for args in (("--check",), ("--yes", "--root", str(root))):
        blocked = _cli(python, root, env, *args)
        assert blocked.returncode == 1 and "update-incomplete" in blocked.stderr
        assert "--recover --yes --confirm-stopped" in blocked.stderr
        assert "up-to-date" not in blocked.stdout and _events(events) == observations

    # A recovery refusal cannot clear either journal or replace the package again.
    incomplete = _cli(python, root, env, "--recover", "--yes", "--confirm-stopped")
    assert incomplete.returncode == 1 and marker.exists() and shared.exists()
    failure.unlink()
    recovered = _cli(python, root, env, "--recover", "--yes", "--confirm-stopped")
    assert recovered.returncode == 0, recovered.stderr
    assert "migrate-artifacts: completed" in recovered.stdout
    assert not marker.exists() and not shared.exists()
    assert sum(event["tool"] == "uv" for event in _events(events)) == 1


@pytest.mark.skipif(os.name != "posix", reason="SIGKILL interruption is POSIX-specific")
def test_killed_replacement_leaves_package_journal_visible_from_another_home(
    tmp_path: Path,
):
    python, root, env, events, config, _failure, marker, shared = _installation(
        tmp_path
    )
    uv = tmp_path / "tools" / "uv"
    uv.write_text(
        f"#!{python}\nimport os, signal\nos.kill(os.getppid(), signal.SIGKILL)\n",
        encoding="utf-8",
    )
    killed = _cli(python, root, env, "--yes", "--root", str(root))
    assert killed.returncode == -signal.SIGKILL
    original = json.loads(marker.read_text())
    assert (
        original["running_stage"] == "replace-package"
        and original["completed_stages"] == []
    )
    assert json.loads(shared.read_text()) == original

    other_home = tmp_path / "other-home"
    other_config = other_home / ".nwave" / "config.json"
    other_config.parent.mkdir(parents=True)
    document = json.loads(config.read_text())
    document["install"]["host_paths"]["agents_home"] = str(other_home)
    other_config.write_text(json.dumps(document), encoding="utf-8")
    other_env = env | {"NWAVE_AGENTS_HOME": str(other_home)}
    before = _events(events)
    for args in (
        ("--check",),
        ("--yes", "--root", str(root)),
        ("--recover", "--yes", "--confirm-stopped"),
    ):
        blocked = _cli(python, root, other_env, *args)
        assert (
            blocked.returncode == 1
            and str(Path(env["NWAVE_AGENTS_HOME"])) in blocked.stderr
        )
        assert _events(events) == before
        assert shared.exists() and marker.exists()
    recovered = _cli(python, root, env, "--recover", "--yes", "--confirm-stopped")
    assert recovered.returncode == 0, recovered.stderr
    assert not marker.exists() and not shared.exists()


def test_broken_progress_pipe_keeps_completed_stage_evidence(tmp_path: Path):
    python, root, env, _events_path, _config, _failure, marker, shared = _installation(
        tmp_path
    )
    driver = (
        "from pathlib import Path\n"
        "from packaging.version import Version\n"
        "from nwave_ai.update.service import UpdateService\n"
        "def closed_output(stage, state):\n"
        "    if state == 'completed':\n"
        "        raise BrokenPipeError('operator output closed')\n"
        "outcome = UpdateService().apply(current_version=Version('1.4.0'), "
        f"discovered_version=Version('999.0.0'), root=Path({str(root)!r}), "
        "on_stage=closed_output)\n"
        "raise SystemExit(0 if outcome.state == 'refused' else 2)\n"
    )
    refused = subprocess.run(
        [str(python), "-P", "-c", driver],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert refused.returncode == 0, refused.stderr
    assert json.loads(marker.read_text())["completed_stages"] == ["replace-package"]
    assert json.loads(shared.read_text())["completed_stages"] == ["replace-package"]
    check = _cli(python, root, env, "--check")
    assert check.returncode == 1 and "update-incomplete" in check.stderr


def test_recorded_cross_home_destination_cannot_bypass_active_registry(
    tmp_path: Path,
):
    python, root, env, events, config, _failure, marker, shared = _installation(
        tmp_path
    )
    document = json.loads(config.read_text())
    document["install"]["host_paths"]["agents_home"] = str(tmp_path / "foreign-home")
    config.write_text(json.dumps(document), encoding="utf-8")
    refused = _cli(python, root, env, "--yes", "--root", str(root))
    assert refused.returncode == 1 and "install-provenance" in refused.stderr
    assert "agents_home" in refused.stderr and "active" in refused.stderr
    assert [event["tool"] for event in _events(events)] == ["public-index"]
    assert not marker.exists() and not shared.exists()


def test_recovery_survives_interruption_between_local_and_package_marker_clearance(
    tmp_path: Path,
):
    python, root, env, _events_path, _config, failure, marker, shared = _installation(
        tmp_path
    )
    failure.touch()
    refused = _cli(python, root, env, "--yes", "--root", str(root))
    assert refused.returncode == 1
    # The remaining package journal is sufficient to recreate local evidence;
    # recovery still verifies every remaining effect instead of simply resetting.
    marker.unlink()
    failure.unlink()
    recovered = _cli(python, root, env, "--recover", "--yes", "--confirm-stopped")
    assert recovered.returncode == 0, recovered.stderr
    assert "verify-executable: completed" in recovered.stdout
    assert "migrate-artifacts: completed" in recovered.stdout
    assert not marker.exists() and not shared.exists()
