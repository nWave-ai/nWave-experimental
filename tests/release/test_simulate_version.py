"""Tests for simulate_version -- version calculation simulation (step 01-01).

Validates that simulate_version() calls next_version.py with correct arguments,
parses JSON output, and returns structured StepResult with version data.
"""

from __future__ import annotations

import subprocess

from scripts.release.simulate import Status, simulate_version


# ---------------------------------------------------------------------------
# Acceptance: simulate_version returns PASS with version from next_version.py
# ---------------------------------------------------------------------------


class TestSimulateVersionAcceptance:
    """Acceptance: simulate_version returns PASS with parsed version."""

    def test_pass_returns_version_in_message(self, monkeypatch):
        """Given next_version.py succeeds, simulate_version returns PASS
        with the calculated version in the message."""
        import json

        call_log: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd

            # Intercept tomllib version read
            if "-c" in cmd and "tomllib" in cmd_str:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout="3.2.0\n"
                )

            # Intercept next_version.py call
            if "next_version.py" in cmd_str:
                call_log.append(list(cmd))
                output = json.dumps(
                    {
                        "version": "3.2.1.dev1",
                        "tag": "v3.2.1.dev1",
                        "base_version": "3.2.1",
                        "pep440_valid": True,
                    }
                )
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout=output
                )

            # Default: succeed silently
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")

        # Mock discover_tag to avoid real git calls
        import scripts.release.discover_tag as dt_mod

        monkeypatch.setattr(dt_mod, "_git_tags", lambda: [])
        monkeypatch.setattr(dt_mod, "_filter_by_pattern", lambda tags, pat: [])
        monkeypatch.setattr(subprocess, "run", fake_run)

        result = simulate_version("dev")

        assert result.status == Status.PASS
        assert result.name == "Version calculation"
        assert "3.2.1.dev1" in result.message

        # Verify next_version.py was called with --current-version
        assert len(call_log) == 1, "next_version.py should be called exactly once"
        next_version_args = call_log[0]
        assert "--current-version" in next_version_args, (
            f"Missing --current-version in call: {next_version_args}"
        )
        assert "--stage" in next_version_args


class TestSimulateVersionForceBump:
    """Unit: force_bump flag is passed correctly to next_version.py subprocess."""

    def test_force_bump_passes_base_version_flag(self, monkeypatch):
        """When force_bump is specified, it should be forwarded
        as a valid argument to next_version.py."""
        import json

        call_log: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd

            if "-c" in cmd and "tomllib" in cmd_str:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout="3.2.0\n"
                )

            if "next_version.py" in cmd_str:
                call_log.append(list(cmd))
                output = json.dumps(
                    {
                        "version": "3.3.0.dev1",
                        "tag": "v3.3.0.dev1",
                        "base_version": "3.3.0",
                        "pep440_valid": True,
                    }
                )
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout=output
                )

            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")

        import scripts.release.discover_tag as dt_mod

        monkeypatch.setattr(dt_mod, "_git_tags", lambda: [])
        monkeypatch.setattr(dt_mod, "_filter_by_pattern", lambda tags, pat: [])
        monkeypatch.setattr(subprocess, "run", fake_run)

        result = simulate_version("dev", force_bump="minor")

        assert result.status == Status.PASS
        assert len(call_log) == 1
        next_version_args = call_log[0]
        # next_version.py has no --force-bump flag; force_bump should map
        # to --base-version with the computed version
        assert "--force-bump" not in next_version_args, (
            "next_version.py has no --force-bump flag"
        )
        assert "--base-version" in next_version_args, (
            f"force_bump should map to --base-version: {next_version_args}"
        )
        # minor bump of 3.2.0 -> 3.3.0
        base_idx = next_version_args.index("--base-version")
        assert next_version_args[base_idx + 1] == "3.3.0"


class TestSimulateVersionFailure:
    """Unit: next_version.py failure returns FAIL or degraded PASS."""

    def test_next_version_nonzero_returns_fallback_version(self, monkeypatch):
        """When next_version.py returns non-zero, simulate_version should
        still return PASS but with a fallback version (current+)."""

        def fake_run(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd

            if "-c" in cmd and "tomllib" in cmd_str:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout="3.2.0\n"
                )

            if "next_version.py" in cmd_str:
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=1,
                    stdout='{"error": "No version bump needed."}',
                    stderr="",
                )

            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")

        import scripts.release.discover_tag as dt_mod

        monkeypatch.setattr(dt_mod, "_git_tags", lambda: [])
        monkeypatch.setattr(dt_mod, "_filter_by_pattern", lambda tags, pat: [])
        monkeypatch.setattr(subprocess, "run", fake_run)

        result = simulate_version("dev")

        # Should still PASS but with fallback version
        assert result.status == Status.PASS
        assert "3.2.0+" in result.message


class TestSimulateVersionDataField:
    """Unit: simulate_version returns version in structured data field (D8)."""

    def test_version_in_data_field(self, monkeypatch):
        """The returned StepResult should include version in the data dict."""
        import json

        def fake_run(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd

            if "-c" in cmd and "tomllib" in cmd_str:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout="3.2.0\n"
                )

            if "next_version.py" in cmd_str:
                output = json.dumps(
                    {
                        "version": "3.2.1.dev1",
                        "tag": "v3.2.1.dev1",
                        "base_version": "3.2.1",
                        "pep440_valid": True,
                    }
                )
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout=output
                )

            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")

        import scripts.release.discover_tag as dt_mod

        monkeypatch.setattr(dt_mod, "_git_tags", lambda: [])
        monkeypatch.setattr(dt_mod, "_filter_by_pattern", lambda tags, pat: [])
        monkeypatch.setattr(subprocess, "run", fake_run)

        result = simulate_version("dev")

        assert result.status == Status.PASS
        assert result.data is not None, "StepResult should have a data field"
        assert "version" in result.data
        assert result.data["version"] == "3.2.1.dev1"
