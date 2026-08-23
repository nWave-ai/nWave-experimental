"""The installer refuses to run concurrently against one destination.

Empirical anchor: 2026-08-21/22, 11:23 and 11:25 -- a second ``install --dev``
started while another install was mid-flight; 51 agents were written and then
swept. The prose rule "one install at a time" had been in place the whole time.
These tests pin the MECHANICAL guarantee that replaces it (GDP-0: make the
concurrent state unrepresentable, do not ask the operator to remember).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

import pytest

from scripts.install import install_nwave
from scripts.install.install_lock import (
    EXIT_INSTALL_LOCK_HELD,
    install_lock,
)
from scripts.shared.install_paths import install_lock_path


REPO_ROOT = Path(__file__).resolve().parents[3]
_REFUSED_BY_CHILD = 9


@dataclass(frozen=True)
class Contention:
    """What a SEPARATE process saw when it tried to take the same lock."""

    refused: bool
    message: str


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """One install destination, fully isolated from the operator's real tree."""
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("NWAVE_AGENTS_HOME", str(home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home / ".claude"))
    return home


def _contend(home: Path) -> Contention:
    """Try to take the lock on ``home`` from a SEPARATE process.

    Not a second ``install_lock()`` inside this process: on POSIX a lock is
    keyed to the open file description, and asserting against a same-process
    contender would risk a suite that passes without ever proving anything
    about two concurrent installs. The contention has to cross a real process
    boundary -- that is the failure mode being guarded.
    """
    probe = textwrap.dedent(
        """
        import sys
        from pathlib import Path

        sys.path.insert(0, sys.argv[1])
        from scripts.install.install_lock import InstallLockHeld, install_lock

        try:
            with install_lock(home=Path(sys.argv[2])):
                print("ACQUIRED")
        except InstallLockHeld as held:
            sys.stdout.write(str(held))
            sys.exit(9)
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe, str(REPO_ROOT), str(home)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if completed.returncode == _REFUSED_BY_CHILD:
        return Contention(refused=True, message=completed.stdout)
    assert completed.returncode == 0, completed.stderr
    return Contention(refused=False, message=completed.stdout)


class TestLockPrimitive:
    """The lock itself: exclusive, non-blocking, per-destination, released."""

    def test_second_acquisition_of_the_same_destination_is_refused(self, tmp_path):
        with install_lock(target_platforms="claude_code", home=tmp_path):
            contention = _contend(tmp_path)

        assert contention.refused, "a concurrent install took the same destination"

    def test_the_refusal_names_the_holder_pid_start_time_and_target(self, tmp_path):
        with install_lock(target_platforms="claude_code", home=tmp_path):
            record = json.loads(install_lock_path(tmp_path).read_text())
            contention = _contend(tmp_path)

        assert record["pid"] == os.getpid()
        assert f"PID {record['pid']}" in contention.message
        assert record["started_at"] in contention.message
        assert "claude_code" in contention.message

    def test_the_refusal_states_what_why_and_how(self, tmp_path):
        with install_lock(home=tmp_path):
            contention = _contend(tmp_path)

        assert "WHAT:" in contention.message
        assert "WHY :" in contention.message
        assert "HOW :" in contention.message
        # The HOW must name the isolation escape hatch, not only "wait" --
        # a lane verifying an install has no one to wait for.
        assert "NWAVE_AGENTS_HOME" in contention.message
        assert "0 files" in contention.message

    def test_the_refusal_is_immediate_not_a_wait(self, tmp_path):
        """An unbounded wait is the same operator-visible failure as no lock."""
        import time

        with install_lock(home=tmp_path):
            started = time.monotonic()
            contention = _contend(tmp_path)
            elapsed = time.monotonic() - started

        assert contention.refused
        assert elapsed < 30, f"the contender waited {elapsed:.1f}s instead of refusing"

    def test_the_lock_is_released_when_the_install_fails_mid_way(self, tmp_path):
        with pytest.raises(RuntimeError):
            with install_lock(home=tmp_path):
                raise RuntimeError("install exploded after writing half a runtime")

        # Must be re-acquirable: a crashed install that left the lock held
        # would wedge every later install into this destination.
        assert not _contend(tmp_path).refused

    def test_the_lock_is_released_on_keyboard_interrupt(self, tmp_path):
        with pytest.raises(KeyboardInterrupt):
            with install_lock(home=tmp_path):
                raise KeyboardInterrupt

        assert not _contend(tmp_path).refused

    def test_two_distinct_destinations_do_not_collide(self, tmp_path):
        """Per-destination, NOT machine-global: an isolated lane must not be
        serialized behind an unrelated install into a different root."""
        first = tmp_path / "dest-a"
        second = tmp_path / "dest-b"

        with install_lock(home=first):
            assert not _contend(second).refused
            assert install_lock_path(first) != install_lock_path(second)

    def test_the_destination_defaults_to_the_agents_home_override(self, isolated_home):
        assert install_lock_path() == isolated_home / ".nwave" / "install.lock"

    def test_a_contender_does_not_perturb_the_holders_record(self, tmp_path):
        with install_lock(target_platforms="codex", home=tmp_path):
            before = install_lock_path(tmp_path).read_bytes()
            assert _contend(tmp_path).refused
            assert install_lock_path(tmp_path).read_bytes() == before


class TestInstallerRefusesConcurrentRun:
    """``install_nwave.main()`` is the seam the lock has to sit behind."""

    def test_the_second_install_refuses_with_the_dedicated_exit_code(
        self, isolated_home, monkeypatch
    ):
        _forbid_every_install_stage(monkeypatch)
        monkeypatch.setattr(
            sys, "argv", ["install_nwave.py", "--platform", "claude-code"]
        )

        with install_lock(target_platforms="claude_code", home=isolated_home):
            exit_code = install_nwave.main()

        assert exit_code == EXIT_INSTALL_LOCK_HELD
        assert exit_code not in (0, 1, 2), "must differ from every other outcome"

    def test_the_second_install_prints_the_refusal_and_writes_nothing(
        self, isolated_home, monkeypatch, capsys
    ):
        _forbid_every_install_stage(monkeypatch)
        monkeypatch.setattr(
            sys, "argv", ["install_nwave.py", "--platform", "claude-code"]
        )
        claude_dir = isolated_home / ".claude"
        before = sorted(path.name for path in claude_dir.iterdir())

        with install_lock(target_platforms="claude_code", home=isolated_home):
            install_nwave.main()

        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "another nWave install is already running" in combined
        assert "WHAT:" in combined and "WHY :" in combined and "HOW :" in combined
        assert sorted(path.name for path in claude_dir.iterdir()) == before

    def test_the_lock_is_taken_before_any_install_effort_is_spent(
        self, isolated_home, monkeypatch
    ):
        """GDP-1: intercept EARLY -- before title panel, preflight, backup and
        install, not after the effort they cost has been spent."""
        reached: list[str] = []
        _forbid_every_install_stage(monkeypatch, record=reached)
        monkeypatch.setattr(
            sys, "argv", ["install_nwave.py", "--platform", "claude-code"]
        )

        with install_lock(home=isolated_home):
            install_nwave.main()

        assert reached == []

    def test_a_failing_install_releases_the_lock_for_the_next_run(
        self, isolated_home, monkeypatch
    ):
        def _explode(_self):
            raise RuntimeError("mid-install failure")

        monkeypatch.setattr(install_nwave, "show_title_panel", lambda *a, **k: None)
        monkeypatch.setattr(
            install_nwave.PreflightChecker, "run_all_checks", lambda self: []
        )
        monkeypatch.setattr(
            install_nwave.NWaveInstaller,
            "validate_codex_ownership_preflight",
            lambda self: True,
        )
        monkeypatch.setattr(
            install_nwave.NWaveInstaller, "create_backup", lambda self: None
        )
        monkeypatch.setattr(
            install_nwave.NWaveInstaller,
            "adopt_legacy_codex_dev_assets",
            lambda self: True,
        )
        monkeypatch.setattr(install_nwave.NWaveInstaller, "install_framework", _explode)
        monkeypatch.setattr(
            sys, "argv", ["install_nwave.py", "--platform", "claude-code"]
        )

        with pytest.raises(RuntimeError):
            install_nwave.main()

        # The next install into this destination must not be wedged.
        assert not _contend(isolated_home).refused

    def test_a_dry_run_neither_takes_nor_waits_on_the_lock(
        self, isolated_home, monkeypatch
    ):
        """A dry run writes nothing, so it has nothing to serialize -- and must
        stay usable for diagnosing an install that is currently running."""
        monkeypatch.setattr(install_nwave, "show_title_panel", lambda *a, **k: None)
        monkeypatch.setattr(
            install_nwave.PreflightChecker, "run_all_checks", lambda self: []
        )
        monkeypatch.setattr(
            install_nwave.NWaveInstaller,
            "validate_codex_ownership_preflight",
            lambda self: True,
        )
        monkeypatch.setattr(
            install_nwave.NWaveInstaller, "install_framework", lambda self: True
        )
        monkeypatch.setattr(
            sys,
            "argv",
            ["install_nwave.py", "--platform", "claude-code", "--dry-run"],
        )

        with install_lock(home=isolated_home):
            exit_code = install_nwave.main()

        assert exit_code == 0


def _forbid_every_install_stage(monkeypatch, record: list[str] | None = None) -> None:
    """Make any stage past the lock observable -- and fatal when reached."""

    def _stage(name):
        def _fail(*_args, **_kwargs):
            if record is not None:
                record.append(name)
                return None
            raise AssertionError(f"{name} ran while another install held the lock")

        return _fail

    monkeypatch.setattr(install_nwave, "show_title_panel", _stage("show_title_panel"))
    monkeypatch.setattr(
        install_nwave.PreflightChecker, "run_all_checks", _stage("preflight")
    )
    monkeypatch.setattr(
        install_nwave.NWaveInstaller, "create_backup", _stage("create_backup")
    )
    monkeypatch.setattr(
        install_nwave.NWaveInstaller, "install_framework", _stage("install_framework")
    )
