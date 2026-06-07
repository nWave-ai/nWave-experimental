"""Tests for simulate_preflight -- preflight checks (step 03-02).

Validates CI status, worktree merge detection, and git cleanliness.
Network-dependent checks (CI) produce WARN on failure, never FAIL.
"""

from __future__ import annotations

import subprocess

from scripts.release.simulate import Status, simulate_preflight


# ---------------------------------------------------------------------------
# Acceptance: clean repo with green CI returns PASS
# ---------------------------------------------------------------------------


class TestSimulatePreflightAcceptance:
    """Acceptance: simulate_preflight returns PASS on clean repo with green CI."""

    def test_clean_repo_green_ci_returns_pass(self, monkeypatch):
        """Given CI is green, no extra worktrees, and clean working tree,
        simulate_preflight should return PASS."""

        def fake_run(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "gh" in cmd_str and "run" in cmd_str:
                # CI green
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout='[{"conclusion":"success"}]',
                )
            if "worktree" in cmd_str:
                # Only main worktree
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout="/repo  abc1234 [master]\n",
                )
            if "status" in cmd_str and "--porcelain" in cmd_str:
                # Clean working tree
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = simulate_preflight()

        assert result.status == Status.PASS
        assert result.name == "Preflight checks"
        assert "success" in result.message.lower() or "clean" in result.message.lower()


# ---------------------------------------------------------------------------
# Unit: CI failure returns WARN (never FAIL)
# ---------------------------------------------------------------------------


class TestSimulatePreflightCIFailed:
    """Unit: CI reports failure -> WARN (not FAIL, since CI failure is informational)."""

    def test_ci_failure_returns_warn(self, monkeypatch):
        """When gh run list returns failure conclusion, result is WARN."""

        def fake_run(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "gh" in cmd_str and "run" in cmd_str:
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout='[{"conclusion":"failure"}]',
                )
            if "worktree" in cmd_str:
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout="/repo  abc1234 [master]\n",
                )
            if "status" in cmd_str and "--porcelain" in cmd_str:
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = simulate_preflight()

        assert result.status == Status.WARN
        assert "ci" in result.message.lower()


# ---------------------------------------------------------------------------
# Unit: worktrees exist returns WARN
# ---------------------------------------------------------------------------


class TestSimulatePreflightWorktrees:
    """Unit: extra worktrees detected -> WARN."""

    def test_extra_worktrees_returns_warn(self, monkeypatch):
        """When git worktree list shows multiple worktrees, result is WARN."""

        def fake_run(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "gh" in cmd_str and "run" in cmd_str:
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout='[{"conclusion":"success"}]',
                )
            if "worktree" in cmd_str:
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout=(
                        "/repo  abc1234 [master]\n/repo-wt  def5678 [feature/foo]\n"
                    ),
                )
            if "status" in cmd_str and "--porcelain" in cmd_str:
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = simulate_preflight()

        assert result.status == Status.WARN
        assert "worktree" in result.message.lower()


# ---------------------------------------------------------------------------
# Unit: dirty working tree returns WARN
# ---------------------------------------------------------------------------


class TestSimulatePreflightDirtyTree:
    """Unit: uncommitted changes -> WARN."""

    def test_dirty_tree_returns_warn(self, monkeypatch):
        """When git status --porcelain returns output, result is WARN."""

        def fake_run(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "gh" in cmd_str and "run" in cmd_str:
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout='[{"conclusion":"success"}]',
                )
            if "worktree" in cmd_str:
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout="/repo  abc1234 [master]\n",
                )
            if "status" in cmd_str and "--porcelain" in cmd_str:
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout=" M scripts/release/simulate.py\n",
                )
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = simulate_preflight()

        assert result.status == Status.WARN
        assert (
            "dirty" in result.message.lower() or "uncommitted" in result.message.lower()
        )


# ---------------------------------------------------------------------------
# Unit: network error on CI check returns WARN (never FAIL)
# ---------------------------------------------------------------------------


class TestSimulatePreflightNetworkError:
    """Unit: gh command fails (network) -> WARN, never FAIL."""

    def test_network_error_returns_warn(self, monkeypatch):
        """When gh run list raises an error, result is WARN."""

        def fake_run(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "gh" in cmd_str and "run" in cmd_str:
                raise subprocess.SubprocessError("network unreachable")
            if "worktree" in cmd_str:
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout="/repo  abc1234 [master]\n",
                )
            if "status" in cmd_str and "--porcelain" in cmd_str:
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = simulate_preflight()

        assert result.status == Status.WARN
        assert "ci" in result.message.lower()
