"""Tests for scripts/release/next_version.py

Calculates the next PEP 440 version for dev, RC, and stable stages.
Also handles nwave-ai public version (floor override vs auto-bump).

BDD scenario mapping:
  - journey-dev-release.feature: "Sequential dev counter increments correctly" (Scenario 2)
  - journey-dev-release.feature: "No conventional commits since last tag" (Scenario 8)
  - journey-rc-release.feature: "Sequential RC counter increments correctly" (Scenario 3)
  - journey-stable-release.feature: "Version floor override takes effect" (Scenario 3)
  - journey-stable-release.feature: "Auto-bump when floor is below current" (Scenario 4)
"""

import json
import subprocess
import sys

import pytest
from packaging.version import Version


SCRIPT = "scripts/release/next_version.py"


def run_next_version(*args: str) -> subprocess.CompletedProcess:
    """Run next_version.py as a subprocess, returning the CompletedProcess."""
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        capture_output=True,
        text=True,
    )


def parse_output(result: subprocess.CompletedProcess) -> dict:
    """Parse JSON output from a successful run."""
    return json.loads(result.stdout.strip())


class TestDevVersionCalculation:
    """PEP 440 .devN version calculation for Stage 1 (dev releases)."""

    @pytest.mark.parametrize(
        "current_version, existing_tags, expected_version",
        [
            pytest.param(
                "1.1.21",
                [],
                "1.1.22.dev1",
                id="first-dev-release",
            ),
            pytest.param(
                "1.1.21",
                ["v1.1.22.dev1"],
                "1.1.22.dev2",
                id="second-dev-release",
            ),
            pytest.param(
                "1.1.21",
                ["v1.1.22.dev1", "v1.1.22.dev2"],
                "1.1.22.dev3",
                id="third-dev-sequential",
            ),
        ],
    )
    def test_dev_version_sequential_counter(
        self, current_version, existing_tags, expected_version
    ):
        """Given existing dev tags for a version,
        when calculating the next dev version,
        then the devN counter increments from the highest existing N.

        Maps to: "Sequential dev counter increments correctly".
        """
        args = ["--stage", "dev", "--current-version", current_version]
        if existing_tags:
            args += ["--existing-tags", ",".join(existing_tags)]
        result = run_next_version(*args)
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = parse_output(result)
        assert output["version"] == expected_version

    def test_dev_version_gaps_in_counter_handled(self):
        """Given tags v1.1.22.dev1 and v1.1.22.dev5 exist (gap in sequence),
        when calculating the next dev version,
        then the result is v1.1.22.dev6 (highest + 1, not fill gaps).
        """
        result = run_next_version(
            "--stage",
            "dev",
            "--current-version",
            "1.1.21",
            "--existing-tags",
            "v1.1.22.dev1,v1.1.22.dev5",
        )
        assert result.returncode == 0
        output = parse_output(result)
        assert output["version"] == "1.1.22.dev6"

    def test_no_version_bump_commits_exits_cleanly(self):
        """Given all commits since the last tag are chore/ci type,
        when calculating with --stage dev,
        then exit code is 1 and message says 'No version bump needed'.

        Maps to: "No conventional commits since last tag".
        """
        result = run_next_version(
            "--stage",
            "dev",
            "--current-version",
            "1.1.21",
            "--no-bump",
        )
        assert result.returncode == 1
        output = parse_output(result)
        assert "No version bump needed" in output["error"]

    def test_output_includes_tag_and_base_version(self):
        """The JSON output must include 'version', 'tag', and 'base_version'.
        Example: {"version": "1.1.22.dev1", "tag": "v1.1.22.dev1", "base_version": "1.1.22"}.
        """
        result = run_next_version(
            "--stage",
            "dev",
            "--current-version",
            "1.1.21",
        )
        assert result.returncode == 0
        output = parse_output(result)
        assert output["version"] == "1.1.22.dev1"
        assert output["tag"] == "v1.1.22.dev1"
        assert output["base_version"] == "1.1.22"

    def test_dev_version_is_pep440_compliant(self):
        """The returned version string must be parseable by packaging.version.Version."""
        result = run_next_version(
            "--stage",
            "dev",
            "--current-version",
            "1.1.21",
        )
        assert result.returncode == 0
        output = parse_output(result)
        parsed = Version(output["version"])
        assert parsed.dev is not None
        assert output["pep440_valid"] is True


class TestRCVersionCalculation:
    """PEP 440 rcN version calculation for Stage 2 (RC releases)."""

    @pytest.mark.parametrize(
        "base_version, existing_tags, expected_version",
        [
            pytest.param(
                "1.1.22",
                [],
                "1.1.22rc1",
                id="first-rc-for-version",
            ),
            pytest.param(
                "1.1.22",
                ["v1.1.22rc1"],
                "1.1.22rc2",
                id="second-rc-sequential",
            ),
            pytest.param(
                "1.1.22",
                ["v1.1.22rc1", "v1.1.22rc2", "v1.1.22rc3"],
                "1.1.22rc4",
                id="fourth-rc-sequential",
            ),
        ],
    )
    def test_rc_version_sequential_counter(
        self, base_version, existing_tags, expected_version
    ):
        """Given existing RC tags for a version,
        when calculating the next RC version,
        then the rcN counter increments from the highest existing N.

        Maps to: "Sequential RC counter increments correctly".
        """
        args = ["--stage", "rc", "--current-version", base_version]
        if existing_tags:
            args += ["--existing-tags", ",".join(existing_tags)]
        result = run_next_version(*args)
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = parse_output(result)
        assert output["version"] == expected_version

    def test_rc_version_extracts_base_from_dev_tag(self):
        """Given source dev tag 'v1.1.22.dev3',
        when calculating the RC version,
        then the base version is '1.1.22' (dev suffix stripped).
        """
        result = run_next_version(
            "--stage",
            "rc",
            "--current-version",
            "v1.1.22.dev3",
        )
        assert result.returncode == 0
        output = parse_output(result)
        assert output["base_version"] == "1.1.22"
        assert output["version"] == "1.1.22rc1"

    def test_rc_version_is_pep440_compliant(self):
        """The returned RC version string must be parseable by packaging.version.Version."""
        result = run_next_version(
            "--stage",
            "rc",
            "--current-version",
            "1.1.22",
        )
        assert result.returncode == 0
        output = parse_output(result)
        parsed = Version(output["version"])
        assert parsed.pre is not None and parsed.pre[0] == "rc"
        assert output["pep440_valid"] is True


class TestStableVersionCalculation:
    """Stable version extraction for Stage 3 (stable releases)."""

    def test_stable_strips_rc_suffix(self):
        """Given source RC tag 'v1.1.22rc1',
        when calculating the stable version,
        then the version is '1.1.22' (rc suffix stripped).
        """
        result = run_next_version(
            "--stage",
            "stable",
            "--current-version",
            "v1.1.22rc1",
        )
        assert result.returncode == 0
        output = parse_output(result)
        assert output["version"] == "1.1.22"
        assert output["tag"] == "v1.1.22"

    def test_stable_version_is_pep440_compliant(self):
        """The returned stable version must be parseable by packaging.version.Version."""
        result = run_next_version(
            "--stage",
            "stable",
            "--current-version",
            "v1.1.22rc1",
        )
        assert result.returncode == 0
        output = parse_output(result)
        parsed = Version(output["version"])
        assert parsed.pre is None
        assert parsed.dev is None
        assert output["pep440_valid"] is True


class TestNwaveAIVersionCalculation:
    """Public nwave-ai version calculation (floor override vs auto-bump)."""

    @pytest.mark.parametrize(
        "floor, current_public, expected",
        [
            pytest.param(
                "1.1.0",
                "1.1.21",
                "1.1.22",
                id="floor-below-current-auto-bumps-patch",
            ),
            pytest.param(
                "2.0.0",
                "1.1.21",
                "2.0.0",
                id="floor-above-current-uses-floor",
            ),
            pytest.param(
                "1.1.21",
                "1.1.21",
                "1.1.22",
                id="floor-equals-current-auto-bumps-patch",
            ),
        ],
    )
    def test_nwave_ai_version_floor_logic(self, floor, current_public, expected):
        """Given a public_version_floor and the current public repo version,
        when calculating the nwave-ai version,
        then if floor > current, use floor; else patch-bump current.

        Maps to: "Version floor override takes effect" and
                 "Auto-bump when floor is below current".
        """
        result = run_next_version(
            "--stage",
            "nwave-ai",
            "--current-version",
            "1.1.22",
            "--public-version-floor",
            floor,
            "--current-public-version",
            current_public,
        )
        assert result.returncode == 0, (
            f"stderr: {result.stderr}, stdout: {result.stdout}"
        )
        output = parse_output(result)
        assert output["version"] == expected


class TestVersionInputValidation:
    """Edge cases and invalid inputs."""

    def test_invalid_stage_returns_error(self):
        """Given --stage 'beta' (not dev/rc/stable),
        then exit code is 2 and message indicates invalid input.
        """
        result = run_next_version(
            "--stage",
            "beta",
            "--current-version",
            "1.1.21",
        )
        assert result.returncode == 2
        output = parse_output(result)
        assert "Invalid stage" in output["error"]

    def test_malformed_tag_returns_error(self):
        """Given --existing-tags contains 'not-a-version',
        then exit code is 2 and message mentions PEP 440 format.

        Maps to: Error matrix "Tag {tag} does not match PEP 440 format".
        """
        result = run_next_version(
            "--stage",
            "dev",
            "--current-version",
            "1.1.21",
            "--existing-tags",
            "not-a-version",
        )
        assert result.returncode == 2
        output = parse_output(result)
        assert "PEP 440" in output["error"]

    def test_empty_current_version_returns_error(self):
        """Given --current-version is empty string,
        then exit code is 2 and message indicates missing version.
        """
        result = run_next_version(
            "--stage",
            "dev",
            "--current-version",
            "",
        )
        assert result.returncode == 2
        output = parse_output(result)
        assert (
            "missing" in output["error"].lower() or "empty" in output["error"].lower()
        )
