"""Tests for scripts/release/discover_tag.py

Discovers the highest semantic version tag for a given pattern (dev or rc).
Uses packaging.Version to guarantee integer sort (dev10 > dev9, rc10 > rc9).

Scenario inventory (15 scenarios, 6 error/edge = 40%):

  Walking skeleton:
    1. Auto-discover highest dev tag from a tag list

  Dev happy path:
    2. Mixed base versions return globally highest dev tag

  Dev sort correctness:
    3. Digit transition: dev11 beats dev9 with 11 tags (1-digit to 2-digit)

  RC happy path:
    4. Auto-discover highest RC tag from a tag list

  RC sort correctness:
    5. Digit transition: rc11 beats rc9 with 11 tags (1-digit to 2-digit)

  Explicit tag validation:
    6. Validate existing tag returns it directly
    7. Validate missing tag returns not-found error

  Error paths:
    8. No dev tags returns not-found with Stage 1 guidance
    9. No RC tags returns not-found with Stage 2 guidance
   10. Invalid pattern returns exit code 2
   11. Invalid tags are filtered; valid ones still sorted correctly

  Staleness detection (integration, requires tmp_path git repo):
   12. Tag at HEAD shows zero commits behind
   13. Tag behind HEAD shows correct commit count
   14. commits_behind is null when --tag-list is provided

  Edge cases:
   15. Empty tag list string treated as no tags
"""

import json
import subprocess
import sys
from pathlib import Path


SCRIPT = "scripts/release/discover_tag.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def run_discover_tag(*args: str) -> subprocess.CompletedProcess:
    """Run discover_tag.py as a subprocess, returning the CompletedProcess."""
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        capture_output=True,
        text=True,
    )


def parse_output(result: subprocess.CompletedProcess) -> dict:
    """Parse JSON output from a subprocess run."""
    return json.loads(result.stdout.strip())


# ===========================================================================
# Walking Skeleton: simplest end-to-end path with observable value
# ===========================================================================
class TestWalkingSkeleton:
    """The simplest user journey: auto-discover the highest dev tag.

    This is the ONLY test enabled at the start. It proves the script
    accepts --pattern dev --tag-list, sorts with packaging.Version,
    and returns JSON with found: true and the correct tag.
    """

    def test_auto_discover_highest_dev_tag(self, dev_tags_mixed_versions):
        """Given dev tags for versions 1.1.22 and 1.1.23 exist,
        when discovering the latest dev tag,
        then the highest semantic version v1.1.23.dev1 is returned.
        """
        tag_list = ",".join(dev_tags_mixed_versions)
        result = run_discover_tag("--pattern", "dev", "--tag-list", tag_list)

        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = parse_output(result)

        assert output["found"] is True
        assert output["tag"] == "v1.1.23.dev1"
        assert output["version"] == "1.1.23.dev1"


# ===========================================================================
# Dev tag discovery: happy path
# ===========================================================================
class TestDevTagHappyPath:
    """Dev tag auto-discovery selects the highest semantic version."""

    def test_mixed_base_versions_returns_globally_highest(
        self, dev_tags_mixed_versions
    ):
        """Given dev tags across base versions 1.1.22 and 1.1.23,
        when discovering the latest dev tag,
        then v1.1.23.dev1 wins over v1.1.22.dev2 (cross-base comparison).
        """
        tag_list = ",".join(dev_tags_mixed_versions)
        result = run_discover_tag("--pattern", "dev", "--tag-list", tag_list)

        assert result.returncode == 0
        output = parse_output(result)
        assert output["tag"] == "v1.1.23.dev1"
        # v1.1.22.dev2 is NOT the highest despite higher devN within 1.1.22
        assert output["version"] == "1.1.23.dev1"


# ===========================================================================
# Dev tag sort correctness: integer sort, not string sort
# ===========================================================================
class TestDevTagDigitTransition:
    """packaging.Version sort guarantees dev10 > dev9, dev11 > dev10."""

    def test_digit_transition_dev11_beats_dev9(self, dev_tags_digit_transition):
        """Given 11 dev tags (dev1 through dev11) for version 1.1.23,
        when discovering the latest dev tag,
        then v1.1.23.dev11 is returned (not dev9 from string sort).

        This is the critical behavioral test that enforces packaging.Version
        over string sort or bash sort -V.
        """
        assert len(dev_tags_digit_transition) == 11, (
            "Fixture must have exactly 11 entries to prove 1-digit to 2-digit transition"
        )

        tag_list = ",".join(dev_tags_digit_transition)
        result = run_discover_tag("--pattern", "dev", "--tag-list", tag_list)

        assert result.returncode == 0
        output = parse_output(result)
        assert output["tag"] == "v1.1.23.dev11"
        assert output["version"] == "1.1.23.dev11"


# ===========================================================================
# RC tag discovery: happy path
# ===========================================================================
class TestRCTagHappyPath:
    """RC tag auto-discovery selects the highest semantic version."""

    def test_auto_discover_highest_rc_tag(self, rc_tags_mixed):
        """Given RC tags for versions 1.1.22 and 1.1.23 exist,
        when discovering the latest RC tag,
        then the highest semantic version v1.1.23rc1 is returned.
        """
        tag_list = ",".join(rc_tags_mixed)
        result = run_discover_tag("--pattern", "rc", "--tag-list", tag_list)

        assert result.returncode == 0
        output = parse_output(result)
        assert output["found"] is True
        assert output["tag"] == "v1.1.23rc1"
        assert output["version"] == "1.1.23rc1"


# ===========================================================================
# RC tag sort correctness: integer sort, not string sort
# ===========================================================================
class TestRCTagDigitTransition:
    """packaging.Version sort guarantees rc10 > rc9, rc11 > rc10."""

    def test_digit_transition_rc11_beats_rc9(self, rc_tags_digit_transition):
        """Given 11 RC tags (rc1 through rc11) for version 1.1.23,
        when discovering the latest RC tag,
        then v1.1.23rc11 is returned (not rc9 from string sort).

        This is the critical behavioral test for RC integer sort.
        """
        assert len(rc_tags_digit_transition) == 11, (
            "Fixture must have exactly 11 entries to prove 1-digit to 2-digit transition"
        )

        tag_list = ",".join(rc_tags_digit_transition)
        result = run_discover_tag("--pattern", "rc", "--tag-list", tag_list)

        assert result.returncode == 0
        output = parse_output(result)
        assert output["tag"] == "v1.1.23rc11"
        assert output["version"] == "1.1.23rc11"


# ===========================================================================
# Explicit tag validation
# ===========================================================================
class TestExplicitTagValidation:
    """When a user provides an explicit tag, validate it exists in the list."""

    def test_validate_existing_tag_returns_it_directly(self, dev_tags_mixed_versions):
        """Given dev tag v1.1.22.dev2 exists in the tag list,
        when validating that specific tag,
        then it is returned directly without discovery sort.
        """
        tag_list = ",".join(dev_tags_mixed_versions)
        result = run_discover_tag(
            "--pattern",
            "dev",
            "--validate",
            "v1.1.22.dev2",
            "--tag-list",
            tag_list,
        )

        assert result.returncode == 0
        output = parse_output(result)
        assert output["found"] is True
        assert output["tag"] == "v1.1.22.dev2"
        assert output["version"] == "1.1.22.dev2"

    def test_validate_missing_tag_returns_not_found(self, dev_tags_mixed_versions):
        """Given dev tag v9.9.9.dev1 does NOT exist in the tag list,
        when validating that specific tag,
        then exit code is 1 and error indicates tag not found.
        """
        tag_list = ",".join(dev_tags_mixed_versions)
        result = run_discover_tag(
            "--pattern",
            "dev",
            "--validate",
            "v9.9.9.dev1",
            "--tag-list",
            tag_list,
        )

        assert result.returncode == 1
        output = parse_output(result)
        assert output["found"] is False
        assert output["tag"] is None
        assert "not found" in output["error"].lower()


# ===========================================================================
# Error paths
# ===========================================================================
class TestNoTagsExist:
    """When no matching tags exist, the script returns actionable guidance."""

    def test_no_dev_tags_returns_stage_1_guidance(self):
        """Given no dev tags exist (empty tag list),
        when discovering the latest dev tag,
        then exit code is 1 and error guides user to run Stage 1 first.
        """
        result = run_discover_tag(
            "--pattern",
            "dev",
            "--tag-list",
            "",
        )

        assert result.returncode == 1
        output = parse_output(result)
        assert output["found"] is False
        assert output["tag"] is None
        assert (
            "stage 1" in output["error"].lower()
            or "dev release" in output["error"].lower()
        )

    def test_no_rc_tags_returns_stage_2_guidance(self):
        """Given no RC tags exist (empty tag list),
        when discovering the latest RC tag,
        then exit code is 1 and error guides user to run Stage 2 first.
        """
        result = run_discover_tag(
            "--pattern",
            "rc",
            "--tag-list",
            "",
        )

        assert result.returncode == 1
        output = parse_output(result)
        assert output["found"] is False
        assert output["tag"] is None
        assert (
            "stage 2" in output["error"].lower()
            or "rc release" in output["error"].lower()
        )


class TestInvalidInput:
    """Invalid CLI arguments produce exit code 2 with a clear error."""

    def test_invalid_pattern_returns_exit_code_2(self):
        """Given --pattern 'stable' (not dev or rc),
        when running discover_tag.py,
        then exit code is 2 and error indicates invalid pattern.
        """
        result = run_discover_tag(
            "--pattern",
            "stable",
            "--tag-list",
            "v1.0.0",
        )

        assert result.returncode == 2
        output = parse_output(result)
        assert (
            "invalid" in output["error"].lower() or "pattern" in output["error"].lower()
        )

    def test_invalid_tags_filtered_valid_ones_sorted(self):
        """Given a tag list with a mix of valid and non-PEP-440 tags,
        when discovering the latest dev tag,
        then invalid tags are silently filtered and valid ones are sorted.
        """
        tag_list = "not-a-version,v1.1.22.dev1,garbage,v1.1.23.dev1"
        result = run_discover_tag(
            "--pattern",
            "dev",
            "--tag-list",
            tag_list,
        )

        assert result.returncode == 0
        output = parse_output(result)
        assert output["found"] is True
        assert output["tag"] == "v1.1.23.dev1"


# ===========================================================================
# Edge cases
# ===========================================================================
class TestEdgeCases:
    """Boundary conditions and corner cases."""

    def test_empty_tag_list_string_treated_as_no_tags(self):
        """Given --tag-list is an empty string,
        when discovering the latest dev tag,
        then it is treated as 'no matching tags' (exit 1, not a crash).
        """
        result = run_discover_tag(
            "--pattern",
            "dev",
            "--tag-list",
            "",
        )

        assert result.returncode == 1
        output = parse_output(result)
        assert output["found"] is False


# ===========================================================================
# Staleness detection (integration tests requiring a real git repo)
# ===========================================================================
class TestStalenessDetection:
    """Commits-behind detection requires a real git repository.

    These tests create a temporary git repo with tags and commits
    to verify the commits_behind field in the JSON output.
    """

    def test_tag_at_head_shows_zero_commits_behind(self, tmp_path):
        """Given a git repo where the latest dev tag points at HEAD,
        when discovering the latest dev tag (without --tag-list),
        then commits_behind is 0.
        """
        # Set up a temp git repo with a dev tag at HEAD
        _init_git_repo(tmp_path)
        _create_commit(tmp_path, "initial commit")
        _create_tag(tmp_path, "v1.1.23.dev1")

        result = _run_discover_in_repo(tmp_path, "--pattern", "dev")

        assert result.returncode == 0
        output = parse_output(result)
        assert output["found"] is True
        assert output["tag"] == "v1.1.23.dev1"
        assert output["commits_behind"] == 0

    def test_tag_behind_head_shows_commit_count(self, tmp_path):
        """Given a git repo where 3 commits landed after the latest dev tag,
        when discovering the latest dev tag (without --tag-list),
        then commits_behind is 3.
        """
        _init_git_repo(tmp_path)
        _create_commit(tmp_path, "initial commit")
        _create_tag(tmp_path, "v1.1.23.dev1")
        _create_commit(tmp_path, "fix: first change after tag")
        _create_commit(tmp_path, "feat: second change after tag")
        _create_commit(tmp_path, "docs: third change after tag")

        result = _run_discover_in_repo(tmp_path, "--pattern", "dev")

        assert result.returncode == 0
        output = parse_output(result)
        assert output["found"] is True
        assert output["tag"] == "v1.1.23.dev1"
        assert output["commits_behind"] == 3

    def test_commits_behind_is_null_with_tag_list(self, dev_tags_mixed_versions):
        """Given --tag-list is provided (no git context),
        when discovering the latest dev tag,
        then commits_behind is null (cannot compute without git).
        """
        tag_list = ",".join(dev_tags_mixed_versions)
        result = run_discover_tag(
            "--pattern",
            "dev",
            "--tag-list",
            tag_list,
        )

        assert result.returncode == 0
        output = parse_output(result)
        assert output["commits_behind"] is None


# ---------------------------------------------------------------------------
# Git helpers for integration tests
# ---------------------------------------------------------------------------
def _git(path, *command):
    """Run a git command in the given repo directory."""
    subprocess.run(
        ["git", *command],
        cwd=str(path),
        capture_output=True,
        check=True,
    )


def _init_git_repo(path):
    """Initialize a git repo in the given directory."""
    _git(path, "init")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test")


def _create_commit(path, message):
    """Create an empty commit in the given git repo."""
    _git(path, "commit", "--allow-empty", "-m", message)


def _create_tag(path, tag_name):
    """Create a lightweight tag at HEAD in the given git repo."""
    _git(path, "tag", tag_name)


def _project_root():
    """Resolve project root from this test file's location."""
    return str(Path(__file__).resolve().parents[2])


def _run_discover_in_repo(repo_path, *args):
    """Run discover_tag.py inside a specific git repo directory."""
    script_path = str(Path(_project_root()) / SCRIPT)
    return subprocess.run(
        [sys.executable, script_path, *args],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
    )
