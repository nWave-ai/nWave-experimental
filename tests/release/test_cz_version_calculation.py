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

from tests.release.test_discover_tag import parse_output as parse_discover_output
from tests.release.test_discover_tag import run_discover_tag
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


class TestMidCycleEscalation:
    """Mid-cycle base version escalation resets the dev counter.

    When the CZ-computed base version changes (e.g., patch -> minor after
    a feat: commit), _highest_counter filters by the NEW base, finding
    zero matching tags, so the counter naturally resets to dev1.

    Maps to: US-CZ-01, Scenarios 6-11 (Roadmap Step 03).
    """

    @pytest.mark.parametrize(
        "base_version, existing_tags, expected_dev",
        [
            pytest.param(
                "1.2.0",
                ",".join(f"v1.1.26.dev{n}" for n in range(1, 9)),
                "1.2.0.dev1",
                id="patch-to-minor",
            ),
            pytest.param(
                "2.0.0",
                ",".join(f"v1.1.26.dev{n}" for n in range(1, 4)),
                "2.0.0.dev1",
                id="patch-to-major",
            ),
            pytest.param(
                "2.0.0",
                ",".join(f"v1.2.0.dev{n}" for n in range(1, 5)),
                "2.0.0.dev1",
                id="minor-to-major",
            ),
        ],
    )
    def test_escalation_resets_counter(self, base_version, existing_tags, expected_dev):
        """Given existing dev tags for a DIFFERENT (lower) base version,
        when calculating the next dev version with a NEW (higher) base,
        then the counter resets to dev1 because no tags match the new base.

        Maps to: Scenarios 6-8 (patch-to-minor, patch-to-major, minor-to-major).
        """
        result = run_next_version(
            "--stage",
            "dev",
            "--current-version",
            "1.1.25",
            "--base-version",
            base_version,
            "--existing-tags",
            existing_tags,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = parse_output(result)
        assert output["version"] == expected_dev
        assert output["base_version"] == base_version

    def test_reverted_feat_does_not_deescalate(self):
        """Given a revert of the feat: commit occurs but CZ still outputs '1.2.0'
        (because the original feat: is in commit history),
        when calculating the next dev version with existing v1.2.0.dev1,
        then the counter increments to dev2 (no de-escalation).

        Maps to: Scenario 9 "Reverted feat does not de-escalate".
        """
        result = run_next_version(
            "--stage",
            "dev",
            "--current-version",
            "1.1.25",
            "--base-version",
            "1.2.0",
            "--existing-tags",
            "v1.2.0.dev1",
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = parse_output(result)
        assert output["version"] == "1.2.0.dev2"

    def test_multiple_base_versions_coexist_after_escalation(self):
        """Given 8 v1.1.26.dev* tags AND 1 v1.2.0.dev1 tag coexist,
        when calculating the next dev version with base '1.2.0',
        then only v1.2.0.dev* tags are counted, producing dev2.

        Maps to: Scenario 10 "Multiple base versions coexist after escalation".
        """
        old_base_tags = ",".join(f"v1.1.26.dev{n}" for n in range(1, 9))
        all_tags = f"{old_base_tags},v1.2.0.dev1"
        result = run_next_version(
            "--stage",
            "dev",
            "--current-version",
            "1.1.25",
            "--base-version",
            "1.2.0",
            "--existing-tags",
            all_tags,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = parse_output(result)
        assert output["version"] == "1.2.0.dev2"
        assert output["base_version"] == "1.2.0"

    def test_rc_promotion_after_escalation_uses_highest_base(self):
        """Given mixed dev tags from pre- and post-escalation bases,
        when discover_tag picks the highest dev tag,
        then it selects v1.2.0.dev2 (post-escalation base wins).

        When calculate_rc receives that dev tag as current-version,
        then it strips the dev suffix and produces 1.2.0rc1.

        Maps to: Scenario 11 "RC promotion after mid-cycle escalation".
        """
        mixed_tags = (
            ",".join(f"v1.1.26.dev{n}" for n in range(1, 9))
            + ",v1.2.0.dev1,v1.2.0.dev2"
        )

        # Sub-test A: discover_tag picks the highest dev tag
        discover_result = run_discover_tag("--pattern", "dev", "--tag-list", mixed_tags)
        assert discover_result.returncode == 0, f"stderr: {discover_result.stderr}"
        discover_output = parse_discover_output(discover_result)
        assert discover_output["tag"] == "v1.2.0.dev2"
        assert discover_output["version"] == "1.2.0.dev2"

        # Sub-test B: calculate_rc strips dev suffix and produces rc1
        rc_result = run_next_version(
            "--stage",
            "rc",
            "--current-version",
            "v1.2.0.dev2",
        )
        assert rc_result.returncode == 0, f"stderr: {rc_result.stderr}"
        rc_output = parse_output(rc_result)
        assert rc_output["version"] == "1.2.0rc1"
        assert rc_output["base_version"] == "1.2.0"
