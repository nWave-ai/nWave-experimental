#!/usr/bin/env python3
"""
nWave Tag Cleanup Script

One-time utility to audit, plan, and execute cleanup of legacy git tags
and GitHub releases on nwave-dev.

Behavior:
  - RENAME all nWave_v* tags to v* format (e.g. nWave_v1.1.21 -> v1.1.21)
  - DELETE everything else (all v2.x tags, all old v1.x tags, etc.)
  - The ONLY tags that survive are the ones renamed from nWave_v*

Usage:
    python cleanup_tags.py --repo owner/repo [--plan] [--execute] [--remote origin]

Modes:
    (default)   Audit: list and classify all tags
    --plan      Show what would change, without modifying anything
    --execute   Actually rename and delete tags (local + remote)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class TagClassification(Enum):
    """How a tag should be handled during cleanup."""

    RENAME = "rename"
    DELETE = "delete"


@dataclass
class ClassifiedTag:
    """A tag with its classification."""

    name: str
    classification: TagClassification


@dataclass
class RenameEntry:
    """A tag rename operation: old_name -> new_name."""

    old_name: str
    new_name: str


@dataclass
class AuditReport:
    """Result of an audit run."""

    tags: list[ClassifiedTag] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.tags)

    @property
    def rename_count(self) -> int:
        return sum(1 for t in self.tags if t.classification == TagClassification.RENAME)

    @property
    def delete_count(self) -> int:
        return sum(1 for t in self.tags if t.classification == TagClassification.DELETE)


@dataclass
class CleanupPlan:
    """What would change in an execute run."""

    to_rename: list[RenameEntry] = field(default_factory=list)
    to_delete: list[ClassifiedTag] = field(default_factory=list)


@dataclass
class ExecuteResult:
    """Result of an execute run."""

    renamed_count: int = 0
    renamed_tags: list[str] = field(default_factory=list)
    deleted_count: int = 0
    deleted_tags: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


NWAVE_PREFIX = "nWave_v"


def classify_tag(tag: str) -> TagClassification:
    """Classify a single tag as RENAME or DELETE.

    nWave_v* tags are renamed to v* format.
    Everything else is deleted.
    """
    if tag.startswith(NWAVE_PREFIX):
        return TagClassification.RENAME
    return TagClassification.DELETE


def rename_target(tag: str) -> str:
    """Compute the rename target for an nWave_v* tag.

    Example: nWave_v1.1.21 -> v1.1.21
    """
    return "v" + tag[len(NWAVE_PREFIX) :]


class TagCleaner:
    """Orchestrates tag audit, planning, and cleanup."""

    def __init__(
        self,
        repo_path: Path,
        gh_repo: str | None = None,
    ):
        self.repo_path = repo_path
        self.gh_repo = gh_repo

    def _run_git(self, *args: str) -> subprocess.CompletedProcess:
        """Run a git command in the repo."""
        return subprocess.run(
            ["git", *args],
            cwd=self.repo_path,
            check=True,
            capture_output=True,
            text=True,
        )

    def _list_tags(self) -> list[str]:
        """List all tags in the repo."""
        result = self._run_git("tag", "--list")
        return sorted(
            line.strip() for line in result.stdout.splitlines() if line.strip()
        )

    def _get_tag_commit(self, tag: str) -> str:
        """Return the commit hash a tag points to."""
        result = self._run_git("rev-list", "-n", "1", tag)
        return result.stdout.strip()

    def audit(self) -> AuditReport:
        """List all tags with their classification. Does not modify anything."""
        tags = self._list_tags()
        report = AuditReport()
        for tag in tags:
            report.tags.append(
                ClassifiedTag(name=tag, classification=classify_tag(tag))
            )
        return report

    def plan(self) -> CleanupPlan:
        """Show what would change. Does not modify anything."""
        tags = self._list_tags()
        result = CleanupPlan()
        for tag in tags:
            classification = classify_tag(tag)
            if classification == TagClassification.RENAME:
                result.to_rename.append(
                    RenameEntry(old_name=tag, new_name=rename_target(tag))
                )
            else:
                result.to_delete.append(
                    ClassifiedTag(name=tag, classification=classification)
                )
        return result

    def execute(self, *, remote: str | None = None) -> ExecuteResult:
        """Rename nWave_v* tags to v* and delete everything else.

        Rename phase runs first, then delete phase.
        Tags created by renames are protected from deletion.
        """
        cleanup_plan = self.plan()
        result = ExecuteResult()

        # Track tags created by rename so they survive the delete phase
        protected_tags: set[str] = set()

        # --- Phase 1: Rename nWave_v* -> v* ---
        for entry in cleanup_plan.to_rename:
            old_tag = entry.old_name
            new_tag = entry.new_name

            # Check if target tag already exists
            existing_tags = self._list_tags()
            if new_tag in existing_tags:
                # Conflict: target already exists
                old_commit = self._get_tag_commit(old_tag)
                new_commit = self._get_tag_commit(new_tag)

                if old_commit == new_commit:
                    # Same commit: just delete the old nWave_v* tag
                    self._delete_tag_local(old_tag, result)
                    if remote:
                        self._delete_tag_remote(old_tag, remote, result)
                    protected_tags.add(new_tag)
                    result.renamed_count += 1
                    result.renamed_tags.append(
                        f"{old_tag} -> {new_tag} (conflict resolved)"
                    )
                    continue
                else:
                    # Different commit: report error, skip
                    result.errors.append(
                        f"Conflict: {old_tag} and {new_tag} point to different commits. "
                        f"Old: {old_commit[:8]}, existing: {new_commit[:8]}. Skipped."
                    )
                    continue

            # No conflict: create new tag at same commit, delete old one
            commit = self._get_tag_commit(old_tag)
            try:
                self._run_git("tag", new_tag, commit)
            except subprocess.CalledProcessError as e:
                result.errors.append(f"Failed to create tag {new_tag}: {e.stderr}")
                continue

            if remote:
                try:
                    self._run_git("push", remote, f"refs/tags/{new_tag}")
                except subprocess.CalledProcessError as e:
                    result.errors.append(
                        f"Failed to push tag {new_tag} to remote: {e.stderr}"
                    )

            # Delete the old nWave_v* tag
            self._delete_tag_local(old_tag, result)
            if remote:
                self._delete_tag_remote(old_tag, remote, result)

            protected_tags.add(new_tag)
            result.renamed_count += 1
            result.renamed_tags.append(f"{old_tag} -> {new_tag}")

        # --- Phase 2: Delete everything else ---
        # Re-read tags because renames changed them
        current_tags = self._list_tags()
        for tag in current_tags:
            if tag in protected_tags:
                continue
            if classify_tag(tag) == TagClassification.DELETE:
                if self._delete_tag_local(tag, result):
                    if remote:
                        self._delete_tag_remote(tag, remote, result)
                    result.deleted_count += 1
                    result.deleted_tags.append(tag)

                    # Delete GitHub release if gh_repo is set
                    if self.gh_repo:
                        self._delete_gh_release(tag)

        return result

    def _delete_tag_local(self, tag: str, result: ExecuteResult) -> bool:
        """Delete a local tag. Returns True on success."""
        try:
            self._run_git("tag", "-d", tag)
            return True
        except subprocess.CalledProcessError as e:
            result.errors.append(f"Failed to delete local tag {tag}: {e.stderr}")
            return False

    def _delete_tag_remote(self, tag: str, remote: str, result: ExecuteResult) -> bool:
        """Delete a remote tag. Returns True on success."""
        try:
            self._run_git("push", remote, f":refs/tags/{tag}")
            return True
        except subprocess.CalledProcessError as e:
            result.errors.append(f"Failed to delete remote tag {tag}: {e.stderr}")
            return False

    def _delete_gh_release(self, tag: str) -> None:
        """Delete a GitHub release for a tag. Silently ignores failures."""
        try:
            subprocess.run(
                [
                    "gh",
                    "release",
                    "delete",
                    tag,
                    "--repo",
                    self.gh_repo,
                    "--yes",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass  # Release may not exist for every tag


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_audit(report: AuditReport) -> None:
    """Print audit report as a table."""
    print(f"\n{'Tag':<30} {'Classification':<15}")
    print("-" * 45)
    for tag in report.tags:
        label = tag.classification.value.upper()
        print(f"{tag.name:<30} {label:<15}")
    print("-" * 45)
    print(
        f"Total: {report.total}  |  Rename: {report.rename_count}  |  Delete: {report.delete_count}"
    )


def _print_plan(plan: CleanupPlan) -> None:
    """Print cleanup plan."""
    print(f"\nTags to RENAME ({len(plan.to_rename)}):")
    for entry in plan.to_rename:
        print(f"  ~ {entry.old_name} -> {entry.new_name}")

    print(f"\nTags to DELETE ({len(plan.to_delete)}):")
    for tag in plan.to_delete:
        print(f"  - {tag.name}")


def _print_result(result: ExecuteResult) -> None:
    """Print execution result."""
    if result.renamed_tags:
        print(f"\nRenamed {result.renamed_count} tag(s):")
        for tag in result.renamed_tags:
            print(f"  ~ {tag}")

    if result.deleted_tags:
        print(f"\nDeleted {result.deleted_count} tag(s):")
        for tag in result.deleted_tags:
            print(f"  - {tag}")

    if result.errors:
        print(f"\nErrors ({len(result.errors)}):")
        for err in result.errors:
            print(f"  ! {err}")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Cleanup legacy git tags on nwave-dev: rename nWave_v* to v*, delete everything else.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="GitHub repo in owner/repo format (e.g. Undeadgrishnackh/crafter-ai)",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Show what would change without modifying anything",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually rename and delete tags (requires explicit flag for safety)",
    )
    parser.add_argument(
        "--remote",
        default=None,
        help="Git remote name for remote tag operations (default: None)",
    )
    parser.add_argument(
        "--repo-path",
        type=Path,
        default=Path.cwd(),
        help="Path to local git repo (default: cwd)",
    )

    args = parser.parse_args(argv)

    cleaner = TagCleaner(
        repo_path=args.repo_path,
        gh_repo=args.repo,
    )

    if args.execute:
        plan = cleaner.plan()
        _print_plan(plan)
        print("\nExecuting cleanup...")
        result = cleaner.execute(remote=args.remote)
        _print_result(result)
        return 1 if result.errors else 0

    if args.plan:
        plan = cleaner.plan()
        _print_plan(plan)
        print("\nDry run. Pass --execute to actually rename and delete.")
        return 0

    # Default: audit mode
    report = cleaner.audit()
    _print_audit(report)
    print("\nAudit only. Pass --plan to see change plan, --execute to apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
