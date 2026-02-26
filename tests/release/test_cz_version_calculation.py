"""Tests for CZ-driven version calculation via --base-version arg.

Validates that next_version.py accepts --base-version to override
the hardcoded _bump_patch fallback, enabling Commitizen-driven
version bumps (minor, major) alongside the existing patch behavior.

BDD scenario mapping:
  - journey-dev-release.feature: Scenarios 1-5, 16-18, 20-27
  - US-CZ-01: CZ-Driven Version Bump (Step 01)
  - US-CZ-03: Graceful Fallback (Step 01)
  - US-CZ-04: Full Promotion Chain (Step 05)
"""

import sys
from pathlib import Path

import pytest
from packaging.version import Version

from tests.release.test_discover_tag import parse_output as parse_discover_output
from tests.release.test_discover_tag import run_discover_tag
from tests.release.test_next_version import parse_output, run_next_version


# tomllib is stdlib in 3.11+; tomli is the backport for 3.10
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parents[2]


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


class TestPromotionChainDevToRC:
    """Full promotion chain validation: dev -> RC -> stable.

    Tests discover_tag.py and next_version.py behavior through
    the complete release promotion pipeline, including mid-cycle
    escalation scenarios where multiple base versions coexist.

    Maps to: US-CZ-04, Scenarios 20-27 (Roadmap Step 05).
    """

    @pytest.mark.parametrize(
        "tag_list, expected_tag, expected_version",
        [
            pytest.param(
                ",".join(
                    [f"v1.1.26.dev{n}" for n in range(1, 9)]
                    + ["v1.2.0.dev1", "v1.2.0.dev2"]
                ),
                "v1.2.0.dev2",
                "1.2.0.dev2",
                id="highest-dev-after-escalation",
            ),
            pytest.param(
                ",".join(
                    [f"v1.1.26.dev{n}" for n in range(1, 9)]
                    + ["v1.2.0.dev1", "v1.2.0.dev2"]
                ),
                "v1.2.0.dev2",
                "1.2.0.dev2",
                id="orphaned-tags-ignored",
            ),
        ],
    )
    def test_discover_tag_picks_highest_dev_after_escalation(
        self, tag_list, expected_tag, expected_version
    ):
        """Given dev tags from pre-escalation (v1.1.26.dev*) and
        post-escalation (v1.2.0.dev*) bases coexist,
        when discover_tag sorts by packaging.Version,
        then the globally highest version wins (v1.2.0.dev2 > v1.1.26.dev8).

        Maps to: Scenarios 20-21 (highest dev after escalation;
        orphaned dev tags from pre-escalation base are not selected).
        """
        result = run_discover_tag("--pattern", "dev", "--tag-list", tag_list)
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = parse_discover_output(result)
        assert output["found"] is True
        assert output["tag"] == expected_tag
        assert output["version"] == expected_version

    def test_sequential_rc_counter_increments(self):
        """Given a dev tag v1.2.0.dev3 is the current version
        and an existing RC tag v1.2.0rc1 exists,
        when calculating the next RC version,
        then the counter increments to rc2.

        Maps to: Scenario 22 "Sequential RC counter increments".
        """
        result = run_next_version(
            "--stage",
            "rc",
            "--current-version",
            "v1.2.0.dev3",
            "--existing-tags",
            "v1.2.0rc1",
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = parse_output(result)
        assert output["version"] == "1.2.0rc2"
        assert output["base_version"] == "1.2.0"

    def test_rc_to_stable_strips_rc_suffix(self):
        """Given RC tags v1.2.0rc1 and v1.2.0rc2 exist,
        when discover_tag picks the highest RC tag,
        then v1.2.0rc2 is selected.

        When stable is calculated from v1.2.0rc2,
        then the RC suffix is stripped producing 1.2.0.

        Maps to: Scenario 23 "RC to stable promotion strips RC suffix".
        """
        # Sub-test A: discover_tag picks highest RC
        discover_result = run_discover_tag(
            "--pattern", "rc", "--tag-list", "v1.2.0rc1,v1.2.0rc2"
        )
        assert discover_result.returncode == 0, f"stderr: {discover_result.stderr}"
        discover_output = parse_discover_output(discover_result)
        assert discover_output["tag"] == "v1.2.0rc2"

        # Sub-test B: stable strips RC suffix
        stable_result = run_next_version(
            "--stage",
            "stable",
            "--current-version",
            "v1.2.0rc2",
        )
        assert stable_result.returncode == 0, f"stderr: {stable_result.stderr}"
        stable_output = parse_output(stable_result)
        assert stable_output["version"] == "1.2.0"
        assert stable_output["tag"] == "v1.2.0"

    def test_wrong_tag_promotion_self_heals_at_stable(self):
        """Given RC tags from an accidental promotion (v1.1.26rc1) and
        the correct promotion (v1.2.0rc1) coexist,
        when discover_tag sorts by packaging.Version,
        then v1.2.0rc1 is selected (higher version wins).

        When stable is calculated from v1.2.0rc1,
        then the version is 1.2.0 (self-healed).

        Maps to: Scenario 24 "Accidental wrong-tag RC promotion self-heals".
        """
        # discover_tag picks the highest RC (ignores accidental v1.1.26rc1)
        discover_result = run_discover_tag(
            "--pattern", "rc", "--tag-list", "v1.1.26rc1,v1.2.0rc1"
        )
        assert discover_result.returncode == 0, f"stderr: {discover_result.stderr}"
        discover_output = parse_discover_output(discover_result)
        assert discover_output["tag"] == "v1.2.0rc1"

        # stable from the correct RC
        stable_result = run_next_version(
            "--stage",
            "stable",
            "--current-version",
            "v1.2.0rc1",
        )
        assert stable_result.returncode == 0, f"stderr: {stable_result.stderr}"
        stable_output = parse_output(stable_result)
        assert stable_output["version"] == "1.2.0"

    def test_floor_not_consulted_at_rc_stage(self):
        """Given a dev tag v1.2.0.dev2 as current version,
        when calculating the RC version (without --version-floor),
        then RC derives its base from the dev tag suffix (1.2.0),
        not from any floor value.

        Maps to: Scenario 25 "Floor override does not affect RC stage".
        """
        result = run_next_version(
            "--stage",
            "rc",
            "--current-version",
            "v1.2.0.dev2",
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = parse_output(result)
        assert output["version"] == "1.2.0rc1"
        assert output["base_version"] == "1.2.0"

    def test_floor_not_consulted_at_stable_stage(self):
        """Given an RC tag v1.2.0rc1 as current version,
        when calculating the stable version,
        then the RC suffix is stripped producing 1.2.0,
        independent of any floor configuration.

        Maps to: Scenario 26 "Floor override does not affect stable stage".
        """
        result = run_next_version(
            "--stage",
            "stable",
            "--current-version",
            "v1.2.0rc1",
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = parse_output(result)
        assert output["version"] == "1.2.0"

    def test_full_three_stage_promotion_chain(self):
        """Walking skeleton: complete dev -> RC -> stable promotion chain.

        Validates that version lineage is preserved across all three stages
        using the same version family (1.2.0).

        Stage 1: dev with --base-version '1.2.0' and existing v1.2.0.dev1
                 produces v1.2.0.dev2
        Stage 2: discover_tag picks v1.2.0.dev2, then RC produces 1.2.0rc1
        Stage 3: discover_tag picks v1.2.0rc1, then stable produces 1.2.0

        Maps to: Scenario 27 "Full three-stage promotion chain".
        """
        # --- Stage 1: Dev release ---
        dev_result = run_next_version(
            "--stage",
            "dev",
            "--current-version",
            "1.1.25",
            "--base-version",
            "1.2.0",
            "--existing-tags",
            "v1.2.0.dev1",
        )
        assert dev_result.returncode == 0, f"Stage 1 stderr: {dev_result.stderr}"
        dev_output = parse_output(dev_result)
        assert dev_output["version"] == "1.2.0.dev2"

        # --- Stage 2: Discover highest dev tag, then promote to RC ---
        discover_dev = run_discover_tag(
            "--pattern", "dev", "--tag-list", "v1.2.0.dev1,v1.2.0.dev2"
        )
        assert discover_dev.returncode == 0, f"Stage 2a stderr: {discover_dev.stderr}"
        discover_dev_output = parse_discover_output(discover_dev)
        assert discover_dev_output["tag"] == "v1.2.0.dev2"

        rc_result = run_next_version(
            "--stage",
            "rc",
            "--current-version",
            "v1.2.0.dev2",
        )
        assert rc_result.returncode == 0, f"Stage 2b stderr: {rc_result.stderr}"
        rc_output = parse_output(rc_result)
        assert rc_output["version"] == "1.2.0rc1"

        # --- Stage 3: Discover highest RC tag, then promote to stable ---
        discover_rc = run_discover_tag("--pattern", "rc", "--tag-list", "v1.2.0rc1")
        assert discover_rc.returncode == 0, f"Stage 3a stderr: {discover_rc.stderr}"
        discover_rc_output = parse_discover_output(discover_rc)
        assert discover_rc_output["tag"] == "v1.2.0rc1"

        stable_result = run_next_version(
            "--stage",
            "stable",
            "--current-version",
            "v1.2.0rc1",
        )
        assert stable_result.returncode == 0, f"Stage 3b stderr: {stable_result.stderr}"
        stable_output = parse_output(stable_result)
        assert stable_output["version"] == "1.2.0"
        assert stable_output["tag"] == "v1.2.0"


class TestCZConfigExpansion:
    """Config verification: CZ expanded, PSR removed, .releaserc deleted.

    Maps to: US-CZ-05, Scenarios 27-30 (Roadmap Step 06).
    These are file-content assertions, not subprocess tests.
    """

    def test_cz_config_includes_version_files(self):
        """Given pyproject.toml at repo root,
        when parsing [tool.commitizen],
        then version_files includes nWave/VERSION and framework-catalog.yaml,
        and changelog_file is set to CHANGELOG.md.

        Maps to: Scenario 27 "CZ config includes version_files".
        """
        pyproject_path = REPO_ROOT / "pyproject.toml"
        with pyproject_path.open("rb") as f:
            toml = tomllib.load(f)
        cz = toml["tool"]["commitizen"]

        assert "nWave/VERSION" in cz["version_files"]
        assert "nWave/framework-catalog.yaml:version" in cz["version_files"]
        assert cz["changelog_file"] == "CHANGELOG.md"

    def test_releaserc_file_removed(self):
        """Given the repo root,
        when checking for .releaserc,
        then the file does not exist.

        Maps to: Scenario 28 ".releaserc file removed".
        """
        releaserc_path = REPO_ROOT / ".releaserc"
        assert not releaserc_path.exists(), (
            f".releaserc still exists at {releaserc_path}"
        )

    def test_psr_config_sections_removed_from_pyproject(self):
        """Given pyproject.toml at repo root,
        when parsing [tool],
        then 'semantic_release' key does not exist,
        and 'commitizen' key still exists.

        Maps to: Scenario 29 "PSR config sections removed".
        """
        pyproject_path = REPO_ROOT / "pyproject.toml"
        with pyproject_path.open("rb") as f:
            toml = tomllib.load(f)
        tool = toml.get("tool", {})

        assert "semantic_release" not in tool, (
            "[tool.semantic_release] still present in pyproject.toml"
        )
        assert "commitizen" in tool, "[tool.commitizen] missing from pyproject.toml"

    def test_psr_removed_from_dev_dependencies(self):
        """Given pyproject.toml at repo root,
        when reading [project.optional-dependencies].dev,
        then no entry contains 'python-semantic-release',
        and at least one entry contains 'commitizen'.

        Maps to: Scenario 30 "PSR removed from dev dependencies".
        """
        pyproject_path = REPO_ROOT / "pyproject.toml"
        with pyproject_path.open("rb") as f:
            toml = tomllib.load(f)
        dev_deps = toml["project"]["optional-dependencies"]["dev"]

        psr_entries = [d for d in dev_deps if "python-semantic-release" in d]
        assert psr_entries == [], (
            f"python-semantic-release still in dev deps: {psr_entries}"
        )

        cz_entries = [d for d in dev_deps if "commitizen" in d]
        assert len(cz_entries) >= 1, "commitizen not found in dev dependencies"


class TestLegacyWorkflowMigration:
    """Workflow YAML migration verification: PSR commands replaced by CZ.

    Maps to: US-CZ-05, Scenarios 31-32 (Roadmap Step 07).
    These are file-content assertions, not subprocess tests.
    """

    def test_release_yml_uses_cz_bump_instead_of_psr(self):
        """Given .github/workflows/release.yml at repo root,
        when reading the file content,
        then 'cz bump' is present (auto and force modes),
        'cz bump --dry-run' is present (dry-run mode),
        'semantic-release version' is absent,
        and 'python-semantic-release' is absent.

        Maps to: Scenario 31 "Legacy release.yml uses CZ instead of PSR".
        """
        workflow_path = REPO_ROOT / ".github" / "workflows" / "release.yml"
        content = workflow_path.read_text()

        # CZ commands present
        assert "cz bump" in content, "release.yml missing 'cz bump' command"
        assert "cz bump --dry-run" in content, (
            "release.yml missing 'cz bump --dry-run' for dry-run mode"
        )
        assert "cz bump --increment" in content, (
            "release.yml missing 'cz bump --increment' for force-bump mode"
        )

        # PSR commands absent
        assert "semantic-release version" not in content, (
            "release.yml still contains 'semantic-release version' (PSR command)"
        )
        assert "python-semantic-release" not in content, (
            "release.yml still references 'python-semantic-release' package"
        )

    def test_cz_changelog_generation_configured(self):
        """Given pyproject.toml has [tool.commitizen] with changelog_file,
        and .gitignore contains CHANGELOG.md,
        then CZ changelog generation is properly configured.

        Maps to: Scenario 32 "CZ generates changelog during stable release".
        """
        # Verify pyproject.toml changelog_file config
        pyproject_path = REPO_ROOT / "pyproject.toml"
        with pyproject_path.open("rb") as f:
            toml = tomllib.load(f)
        cz = toml["tool"]["commitizen"]
        assert cz["changelog_file"] == "CHANGELOG.md", (
            f"changelog_file is '{cz.get('changelog_file')}', expected 'CHANGELOG.md'"
        )

        # Verify .gitignore has CHANGELOG.md (auto-generated, not committed)
        gitignore_path = REPO_ROOT / ".gitignore"
        gitignore_content = gitignore_path.read_text()
        assert "CHANGELOG.md" in gitignore_content, (
            ".gitignore does not contain 'CHANGELOG.md'"
        )


class TestCIDocumentationCleanup:
    """CI and documentation reference cleanup: PSR to CZ.

    Maps to: US-CZ-05, Scenario 33 (Roadmap Step 08).
    These are file-content assertions verifying that CI workflows
    and documentation no longer reference python-semantic-release.
    """

    def test_ci_yml_references_commitizen_not_psr(self):
        """Given .github/workflows/ci.yml exists,
        when reading the file content,
        then 'python-semantic-release' is absent
        and 'commitizen' is present in the version-drift context.

        Maps to: Scenario 33 "CI and documentation references updated from PSR to CZ".
        """
        ci_path = REPO_ROOT / ".github" / "workflows" / "ci.yml"
        content = ci_path.read_text()

        assert "python-semantic-release" not in content, (
            "ci.yml still references 'python-semantic-release'"
        )
        assert "commitizen" in content, (
            "ci.yml missing 'commitizen' reference in version-drift context"
        )

    def test_readme_references_commitizen_not_psr(self):
        """Given .github/workflows/README.md exists,
        when reading the file content,
        then 'python-semantic-release' is absent,
        'commitizen' is present,
        and '--dry-run' is used instead of '--print'.

        Maps to: Scenario 33 (README documentation portion).
        """
        readme_path = REPO_ROOT / ".github" / "workflows" / "README.md"
        content = readme_path.read_text()

        assert "python-semantic-release" not in content, (
            "README.md still references 'python-semantic-release'"
        )
        assert "commitizen" in content, "README.md missing 'commitizen' reference"
        assert "--dry-run" in content, "README.md missing '--dry-run' (CZ flag)"
