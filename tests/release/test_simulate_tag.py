"""Tests for simulate_tag_check — tag conflict detection (step 01-02)."""

from __future__ import annotations

import subprocess

from scripts.release.simulate import Status, simulate_tag_check


class TestSimulateTagCheckAcceptance:
    """Acceptance: simulate_tag_check returns correct StepResult for tag conflicts."""

    def test_new_tag_returns_pass(self, monkeypatch):
        """A tag that does not exist locally or remotely should PASS."""

        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = simulate_tag_check("v99.99.99")

        assert result.status == Status.PASS
        assert "v99.99.99" in result.message


class TestSimulateTagCheckLocalConflict:
    """Unit: local tag exists -> FAIL."""

    def test_local_tag_exists_returns_fail(self, monkeypatch):
        """When git tag -l finds the tag locally, result is FAIL."""

        def fake_run(cmd, **kwargs):
            if "tag" in cmd and "-l" in cmd:
                # git tag -l returns the tag name when it exists
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout="v1.2.3\n"
                )
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = simulate_tag_check("v1.2.3")

        assert result.status == Status.FAIL
        assert "already exists locally" in result.message


class TestSimulateTagCheckRemoteConflict:
    """Unit: remote tag exists -> WARN."""

    def test_remote_tag_exists_returns_warn(self, monkeypatch):
        """When tag exists on remote but not locally, result is WARN."""

        def fake_run(cmd, **kwargs):
            if "tag" in cmd and "-l" in cmd:
                # Not found locally
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")
            if "ls-remote" in cmd:
                # Found on remote
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout="abc123\trefs/tags/v1.2.3\n",
                )
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = simulate_tag_check("v1.2.3")

        assert result.status == Status.WARN
        assert "exists on remote" in result.message


class TestSimulateTagCheckNetworkError:
    """Unit: network failure -> WARN (never FAIL)."""

    def test_network_error_returns_warn(self, monkeypatch):
        """When ls-remote fails (network), result is WARN, not FAIL."""

        def fake_run(cmd, **kwargs):
            if "tag" in cmd and "-l" in cmd:
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")
            if "ls-remote" in cmd:
                raise subprocess.SubprocessError("network unreachable")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = simulate_tag_check("v1.2.3")

        assert result.status == Status.WARN
        assert "could not check remote" in result.message.lower()


class TestSimulateTagCheckDoesNotCreateTags:
    """Unit: function never creates tags — only reads."""

    def test_no_tag_creation_commands(self, monkeypatch):
        """Verify git tag create is never called."""
        commands_executed = []

        def fake_run(cmd, **kwargs):
            commands_executed.append(cmd)
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        simulate_tag_check("v1.2.3")

        for cmd in commands_executed:
            # git tag -l is OK; git tag without -l would create a tag
            if "tag" in cmd:
                assert "-l" in cmd, f"Tag command without -l detected: {cmd}"
