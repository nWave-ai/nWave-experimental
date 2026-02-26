"""Tests for CZ-driven version calculation via --base-version arg.

Validates that next_version.py accepts --base-version to override
the hardcoded _bump_patch fallback, enabling Commitizen-driven
version bumps (minor, major) alongside the existing patch behavior.

BDD scenario mapping:
  - journey-dev-release.feature: Scenarios 1-5, 16-18
  - US-CZ-01: CZ-Driven Version Bump (Step 01)
  - US-CZ-03: Graceful Fallback (Step 01)
"""

import pytest
from packaging.version import Version

from tests.release.test_next_version import parse_output, run_next_version


class TestCZBaseVersionOverride:
    """--base-version overrides _bump_patch when provided."""

    @pytest.mark.parametrize(
        "base_version, expected_dev",
        [
            pytest.param("1.2.0", "1.2.0.dev1", id="feat-minor-bump"),
            pytest.param("1.1.23", "1.1.23.dev1", id="fix-patch-bump"),
            pytest.param("2.0.0", "2.0.0.dev1", id="breaking-major-bump"),
        ],
    )
    def test_base_version_produces_correct_dev_version(
        self, base_version, expected_dev
    ):
        """Given --base-version with a valid PEP 440 version,
        when calculating the next dev version,
        then the base is used instead of _bump_patch
        and devN counter starts at 1.

        Maps to: Scenarios 1-3 (feat/fix/breaking via CZ base).
        """
        result = run_next_version(
            "--stage",
            "dev",
            "--current-version",
            "1.1.22",
            "--base-version",
            base_version,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = parse_output(result)
        assert output["version"] == expected_dev
        assert output["base_version"] == base_version
        assert output["tag"] == f"v{expected_dev}"
        assert output["pep440_valid"] is True
        assert Version(output["version"]).dev == 1

    def test_sequential_counter_with_cz_base_version(self):
        """Given --base-version '1.2.0' and existing tag v1.2.0.dev1,
        when calculating the next dev version,
        then the counter increments to dev2.

        Maps to: Scenario 4 "Sequential counter with CZ base version".
        """
        result = run_next_version(
            "--stage",
            "dev",
            "--current-version",
            "1.1.22",
            "--base-version",
            "1.2.0",
            "--existing-tags",
            "v1.2.0.dev1",
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = parse_output(result)
        assert output["version"] == "1.2.0.dev2"

    @pytest.mark.parametrize(
        "base_version",
        [
            pytest.param("", id="empty-base-cz-fallback"),
            pytest.param("", id="cz-not-installed-fallback"),
            pytest.param("", id="cz-config-missing-fallback"),
        ],
    )
    def test_empty_base_version_falls_back_to_patch_bump(self, base_version):
        """Given --base-version is empty (CZ failure or not configured),
        when calculating the next dev version,
        then fallback to _bump_patch(current_version) is used.

        Maps to: Scenarios 5, 16, 17 (empty base fallback paths).
        """
        result = run_next_version(
            "--stage",
            "dev",
            "--current-version",
            "1.1.22",
            "--base-version",
            base_version,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = parse_output(result)
        assert output["version"] == "1.1.23.dev1"
        assert output["base_version"] == "1.1.23"

    def test_invalid_base_version_rejected_with_exit_code_2(self):
        """Given --base-version 'not-a-version' (invalid PEP 440),
        when calculating the next dev version,
        then exit code is 2 with 'Invalid base-version' in the error.

        Maps to: Scenario 18 "Invalid base-version is rejected".
        """
        result = run_next_version(
            "--stage",
            "dev",
            "--current-version",
            "1.1.22",
            "--base-version",
            "not-a-version",
        )
        assert result.returncode == 2
        output = parse_output(result)
        assert "Invalid base-version" in output["error"]


class TestVersionFloorOverride:
    """--version-floor overrides resolved base when floor > base.

    Maps to: US-CZ-02 (Scenarios 12-15, 19).
    """

    def test_floor_overrides_cz_base_when_higher(self):
        """Given --version-floor '1.3.0' > --base-version '1.2.0',
        when calculating the next dev version,
        then the floor is used as the base.

        Maps to: Scenario 12 "Floor overrides CZ when floor is higher".
        """
        result = run_next_version(
            "--stage",
            "dev",
            "--current-version",
            "1.1.22",
            "--base-version",
            "1.2.0",
            "--version-floor",
            "1.3.0",
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = parse_output(result)
        assert output["version"] == "1.3.0.dev1"
        assert output["base_version"] == "1.3.0"

    def test_floor_ignored_when_lower_than_cz_base(self):
        """Given --version-floor '1.1.0' < --base-version '1.2.0',
        when calculating the next dev version,
        then the CZ base is used (floor is ignored).

        Maps to: Scenario 13 "Floor is ignored when lower than CZ base".
        """
        result = run_next_version(
            "--stage",
            "dev",
            "--current-version",
            "1.1.22",
            "--base-version",
            "1.2.0",
            "--version-floor",
            "1.1.0",
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = parse_output(result)
        assert output["version"] == "1.2.0.dev1"
        assert output["base_version"] == "1.2.0"

    def test_floor_overrides_fallback_when_cz_fails(self):
        """Given --base-version '' (CZ failed) and --version-floor '2.0.0',
        when calculating the next dev version,
        then the floor overrides the _bump_patch fallback.

        Maps to: Scenario 14 "Floor overrides fallback when CZ fails".
        """
        result = run_next_version(
            "--stage",
            "dev",
            "--current-version",
            "1.1.22",
            "--base-version",
            "",
            "--version-floor",
            "2.0.0",
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = parse_output(result)
        assert output["version"] == "2.0.0.dev1"
        assert output["base_version"] == "2.0.0"

    def test_floor_and_cz_base_with_existing_tags(self):
        """Given --version-floor '1.3.0' > --base-version '1.2.0'
        and existing tag v1.3.0.dev1,
        when calculating the next dev version,
        then the floor base is used and counter increments to dev2.

        Maps to: Scenario 15 "Floor and CZ base with existing tags".
        """
        result = run_next_version(
            "--stage",
            "dev",
            "--current-version",
            "1.1.22",
            "--base-version",
            "1.2.0",
            "--version-floor",
            "1.3.0",
            "--existing-tags",
            "v1.3.0.dev1",
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = parse_output(result)
        assert output["version"] == "1.3.0.dev2"
        assert output["base_version"] == "1.3.0"

    def test_invalid_version_floor_rejected_with_exit_code_2(self):
        """Given --version-floor 'abc' (not PEP 440 compliant),
        when calculating the next dev version,
        then exit code is 2 with 'Invalid version-floor' in the error.

        Maps to: Scenario 19 "Invalid version-floor is rejected".
        """
        result = run_next_version(
            "--stage",
            "dev",
            "--current-version",
            "1.1.22",
            "--base-version",
            "1.2.0",
            "--version-floor",
            "abc",
        )
        assert result.returncode == 2
        output = parse_output(result)
        assert "Invalid version-floor" in output["error"]
