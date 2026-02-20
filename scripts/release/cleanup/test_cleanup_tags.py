#!/usr/bin/env python3
"""
Tests for the nWave tag cleanup script.

Uses temporary git repos as fixtures. No network calls, no real GitHub API.
All tests are local and fast.
"""

import subprocess

import pytest

from scripts.release.cleanup.cleanup_tags import (
    TagClassification,
    TagCleaner,
    classify_tag,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_git_repo(tmp_path):
    """Create a temp git repo with simulated nwave-dev tags.

    Given a fresh temporary directory,
    When we initialise a git repo with representative tags,
    Then the fixture yields a repo path with tags that mirror
    the nwave-dev tag landscape:
      - v2.17.0 through v2.17.6 (7 legacy tags to DELETE)
      - nWave_v1.1.20, nWave_v1.1.21 (2 marker tags to RENAME)
      - v1.4.8 (old legacy dev tag to DELETE)
    """
    repo = tmp_path / "test-repo"
    repo.mkdir()

    def _git(*args):
        subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )

    _git("init")
    _git("config", "user.email", "test@test.com")
    _git("config", "user.name", "Test")

    # Create an initial commit so we can tag it
    (repo / "README.md").write_text("init")
    _git("add", "README.md")
    _git("commit", "-m", "initial commit")

    # Legacy nwave-dev tags (v2.17.x series, should be deleted)
    for minor in range(7):
        _git("tag", f"v2.17.{minor}")

    # Production-equivalent marker tags (should be renamed to v*)
    _git("tag", "nWave_v1.1.21")
    _git("tag", "nWave_v1.1.20")

    # Old legacy dev tag (NOT a marker, should be deleted)
    _git("tag", "v1.4.8")

    return repo


@pytest.fixture
def empty_git_repo(tmp_path):
    """Create a temp git repo with no tags at all.

    Given a fresh temporary directory,
    When we initialise a bare git repo with one commit and zero tags,
    Then the fixture yields a repo path with no tags.
    """
    repo = tmp_path / "empty-repo"
    repo.mkdir()

    def _git(*args):
        subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )

    _git("init")
    _git("config", "user.email", "test@test.com")
    _git("config", "user.name", "Test")

    (repo / "README.md").write_text("init")
    _git("add", "README.md")
    _git("commit", "-m", "initial commit")

    return repo


@pytest.fixture
def temp_git_repo_with_remote(tmp_path):
    """Create a temp git repo with a local 'remote' to test remote operations.

    Given two git repos (origin and clone),
    When origin has tags and clone has them as remote refs,
    Then we can test remote rename + delete without network access.
    """
    origin = tmp_path / "origin"
    origin.mkdir()
    clone = tmp_path / "clone"

    def _git(cwd, *args):
        subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )

    # Set up origin
    _git(origin, "init", "--bare")

    # Clone it
    subprocess.run(
        ["git", "clone", str(origin), str(clone)],
        check=True,
        capture_output=True,
        text=True,
    )
    _git(clone, "config", "user.email", "test@test.com")
    _git(clone, "config", "user.name", "Test")

    # Create initial commit
    (clone / "README.md").write_text("init")
    _git(clone, "add", "README.md")
    _git(clone, "commit", "-m", "initial commit")
    _git(clone, "push", "origin", "master")

    # Create tags and push them
    for minor in range(3):
        _git(clone, "tag", f"v2.17.{minor}")
    _git(clone, "tag", "nWave_v1.1.21")
    _git(clone, "tag", "v1.4.8")
    _git(clone, "push", "origin", "--tags")

    return clone


@pytest.fixture
def conflict_same_commit_repo(tmp_path):
    """Create a repo where nWave_v1.1.21 and v1.1.21 point to the same commit.

    This tests the conflict resolution: when target tag already exists at the
    same commit, just delete the old nWave_v* tag.
    """
    repo = tmp_path / "conflict-repo"
    repo.mkdir()

    def _git(*args):
        subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )

    _git("init")
    _git("config", "user.email", "test@test.com")
    _git("config", "user.name", "Test")

    (repo / "README.md").write_text("init")
    _git("add", "README.md")
    _git("commit", "-m", "initial commit")

    # Both tags on the same commit
    _git("tag", "nWave_v1.1.21")
    _git("tag", "v1.1.21")

    return repo


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _list_tags(repo_path):
    """Return sorted list of tag names in the given repo."""
    result = subprocess.run(
        ["git", "tag", "--list"],
        cwd=repo_path,
        check=True,
        capture_output=True,
        text=True,
    )
    return sorted(line.strip() for line in result.stdout.splitlines() if line.strip())


def _get_tag_commit(repo_path, tag_name):
    """Return the commit hash that a tag points to."""
    result = subprocess.run(
        ["git", "rev-list", "-n", "1", tag_name],
        cwd=repo_path,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Test: Tag classification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tag,expected",
    [
        ("nWave_v1.1.21", TagClassification.RENAME),
        ("nWave_v1.1.20", TagClassification.RENAME),
        ("nWave_v2.0.0", TagClassification.RENAME),
        ("v2.17.0", TagClassification.DELETE),
        ("v2.17.6", TagClassification.DELETE),
        ("v2.0.0", TagClassification.DELETE),
        ("v1.4.8", TagClassification.DELETE),
        ("v1.5.1", TagClassification.DELETE),
        ("v1.5.2", TagClassification.DELETE),
        ("some-random-tag", TagClassification.DELETE),
    ],
)
def test_classify_tag_correctly(tag, expected):
    """Classify individual tags as rename or delete.

    Given a tag name from nwave-dev,
    When we classify it,
    Then nWave_v* tags are marked RENAME
      and all other tags are marked DELETE.
    """
    assert classify_tag(tag) == expected


# ---------------------------------------------------------------------------
# Test: Audit mode
# ---------------------------------------------------------------------------


def test_audit_finds_all_tags_and_classifies_correctly(temp_git_repo):
    """Audit mode lists all tags with correct classification.

    Given a repo with 7 legacy v2.17.x tags, 2 nWave_v* marker tags,
      and 1 old legacy dev tag v1.4.8,
    When we run audit,
    Then all 10 tags appear in the result,
      with 2 RENAME (nWave_v*) and 8 DELETE (everything else).
    """
    cleaner = TagCleaner(repo_path=temp_git_repo)
    report = cleaner.audit()

    assert report.total == 10
    assert report.rename_count == 2  # nWave_v1.1.20, nWave_v1.1.21
    assert report.delete_count == 8  # v2.17.0-6 + v1.4.8

    rename_tags = {
        t.name for t in report.tags if t.classification == TagClassification.RENAME
    }
    assert rename_tags == {"nWave_v1.1.20", "nWave_v1.1.21"}


# ---------------------------------------------------------------------------
# Test: Plan mode
# ---------------------------------------------------------------------------


def test_plan_shows_renames_and_deletes_without_changing_anything(temp_git_repo):
    """Plan mode shows what would change but does not modify the repo.

    Given a repo with legacy tags and nWave_v* marker tags,
    When we run plan,
    Then the plan lists renames and deletes,
      and the actual tags in the repo remain unchanged.
    """
    tags_before = _list_tags(temp_git_repo)

    cleaner = TagCleaner(repo_path=temp_git_repo)
    plan = cleaner.plan()

    assert len(plan.to_rename) == 2
    rename_map = {r.old_name: r.new_name for r in plan.to_rename}
    assert rename_map == {
        "nWave_v1.1.20": "v1.1.20",
        "nWave_v1.1.21": "v1.1.21",
    }

    assert len(plan.to_delete) == 8
    delete_names = {t.name for t in plan.to_delete}
    assert delete_names == {f"v2.17.{i}" for i in range(7)} | {"v1.4.8"}

    tags_after = _list_tags(temp_git_repo)
    assert tags_before == tags_after


# ---------------------------------------------------------------------------
# Test: Execute mode (local only)
# ---------------------------------------------------------------------------


def test_execute_renames_and_deletes_tags_locally(temp_git_repo):
    """Execute mode renames nWave_v* tags and deletes everything else locally.

    Given a repo with nWave_v* marker tags and legacy tags,
    When we execute cleanup,
    Then nWave_v* tags are renamed to v* format,
      legacy tags are deleted,
      and only the renamed v* tags remain.
    """
    cleaner = TagCleaner(repo_path=temp_git_repo)
    result = cleaner.execute(remote=None)

    assert result.renamed_count == 2
    assert result.deleted_count == 8

    remaining = _list_tags(temp_git_repo)
    assert sorted(remaining) == ["v1.1.20", "v1.1.21"]


# ---------------------------------------------------------------------------
# Test: Renamed tags point to same commit
# ---------------------------------------------------------------------------


def test_renamed_tags_point_to_same_commit(temp_git_repo):
    """Renamed tags preserve the commit reference.

    Given a repo with nWave_v1.1.21 pointing to a specific commit,
    When we execute cleanup and it gets renamed to v1.1.21,
    Then v1.1.21 points to the exact same commit as nWave_v1.1.21 did.
    """
    original_commit = _get_tag_commit(temp_git_repo, "nWave_v1.1.21")

    cleaner = TagCleaner(repo_path=temp_git_repo)
    cleaner.execute(remote=None)

    renamed_commit = _get_tag_commit(temp_git_repo, "v1.1.21")
    assert renamed_commit == original_commit


# ---------------------------------------------------------------------------
# Test: Execute mode (with remote)
# ---------------------------------------------------------------------------


def test_execute_with_remote_renames_and_deletes_on_remote(
    temp_git_repo_with_remote,
):
    """Execute with --remote renames and deletes tags on both local and remote.

    Given a repo with a local 'origin' remote that has pushed tags,
    When we execute cleanup with remote='origin',
    Then nWave_v* tags are renamed to v* on both local and remote,
      and legacy tags are removed from both local and remote.
    """
    repo = temp_git_repo_with_remote

    cleaner = TagCleaner(repo_path=repo)
    result = cleaner.execute(remote="origin")

    assert result.renamed_count == 1  # nWave_v1.1.21
    assert result.deleted_count == 4  # v2.17.0, v2.17.1, v2.17.2, v1.4.8

    # Local: only renamed tag remains
    local_remaining = _list_tags(repo)
    assert "v2.17.0" not in local_remaining
    assert "v1.4.8" not in local_remaining
    assert "nWave_v1.1.21" not in local_remaining
    assert "v1.1.21" in local_remaining

    # Remote: renamed tag present, legacy tags gone
    ls_remote = subprocess.run(
        ["git", "ls-remote", "--tags", "origin"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "v2.17.0" not in ls_remote.stdout
    assert "v1.4.8" not in ls_remote.stdout
    assert "nWave_v1.1.21" not in ls_remote.stdout
    assert "v1.1.21" in ls_remote.stdout


# ---------------------------------------------------------------------------
# Test: Safety - renamed tags are never deleted
# ---------------------------------------------------------------------------


def test_renamed_tags_are_never_deleted(temp_git_repo):
    """Tags created by renaming nWave_v* must survive the delete phase.

    Given a repo with nWave_v1.1.20 and nWave_v1.1.21,
    When we execute cleanup (which renames them to v1.1.20, v1.1.21
      and then deletes all non-nWave_v* tags),
    Then the newly renamed v1.1.20 and v1.1.21 are NOT deleted.
    """
    cleaner = TagCleaner(repo_path=temp_git_repo)
    result = cleaner.execute(remote=None)

    remaining = _list_tags(temp_git_repo)
    assert "v1.1.20" in remaining
    assert "v1.1.21" in remaining
    assert result.errors == []


# ---------------------------------------------------------------------------
# Test: Edge case - empty repo
# ---------------------------------------------------------------------------


def test_empty_repo_handles_gracefully(empty_git_repo):
    """Script handles a repo with no tags without errors.

    Given a repo with zero tags,
    When we run audit, plan, and execute,
    Then each completes without error and reports zero tags.
    """
    cleaner = TagCleaner(repo_path=empty_git_repo)

    report = cleaner.audit()
    assert report.total == 0
    assert report.rename_count == 0
    assert report.delete_count == 0

    plan = cleaner.plan()
    assert len(plan.to_rename) == 0
    assert len(plan.to_delete) == 0

    result = cleaner.execute(remote=None)
    assert result.renamed_count == 0
    assert result.deleted_count == 0


# ---------------------------------------------------------------------------
# Test: Conflict handling - same commit
# ---------------------------------------------------------------------------


def test_conflict_same_commit_just_removes_old_tag(conflict_same_commit_repo):
    """When nWave_v* and v* both exist at the same commit, just remove the old one.

    Given a repo where nWave_v1.1.21 and v1.1.21 point to the same commit,
    When we execute cleanup,
    Then nWave_v1.1.21 is deleted and v1.1.21 remains,
      with no errors reported.
    """
    repo = conflict_same_commit_repo
    original_commit = _get_tag_commit(repo, "v1.1.21")

    cleaner = TagCleaner(repo_path=repo)
    result = cleaner.execute(remote=None)

    remaining = _list_tags(repo)
    assert "v1.1.21" in remaining
    assert "nWave_v1.1.21" not in remaining
    assert result.errors == []

    # The surviving tag still points to the same commit
    assert _get_tag_commit(repo, "v1.1.21") == original_commit
