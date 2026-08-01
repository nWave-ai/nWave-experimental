"""HeadSkillCorpusReader -- read the skill-normative manifest + assets from HEAD.

Feature: gate-ratchet-skill-normative (Mikado D86).
Layer: Driven adapter.

Same two-method shape as `SkillCorpusReader` (`read_manifest`, `read_asset`),
backed by a commit's git blobs instead of the working tree. Feeds
`SkillNormativeGateService` a PAST corpus with ZERO duplication of its
matching logic -- the service does not know or care whether `read_asset`
reads today's working tree or a blob frozen at a past commit.

Exception vocabulary mirrors `SkillCorpusReader` (reads-and-catches, no
TOCTOU) with one addition:
  - `BlobOutcome.ABSENT`        -> `ManifestAssetAbsent` (a DECIDABLE fact --
    HEAD genuinely did not carry that path -- caught INSIDE
    `SkillNormativeGateService._read_clause_asset` and turned into a counted
    `UnreadableClause` finding, exactly as the working-tree case does).
  - undecodable (not UTF-8)     -> `ManifestAssetUndecodable` (same as above).
  - `BlobOutcome.INDETERMINATE` -> `HeadBlobUnreadable` (NOT one of the two
    the service catches -- deliberately left to propagate UNCAUGHT through
    `evaluate()`, so the baseline orchestrator, the only intended catcher,
    can refuse the WHOLE baseline rather than silently count a could-not-read
    git object as a decided finding).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from des.adapters.driven.git.git_commit_contents import BlobOutcome
from des.domain.skill_normative_clause import (
    ManifestAssetAbsent,
    ManifestAssetUndecodable,
)


if TYPE_CHECKING:
    from pathlib import Path

    from des.adapters.driven.git.git_commit_contents import CommitContentsPort


class HeadBlobUnreadable(Exception):
    """A HEAD blob genuinely could not be read (git object store INDETERMINATE).

    Distinct from `ManifestAssetAbsent`/`ManifestAssetUndecodable` on purpose:
    those two mean a DECIDABLE fact ("not present" / "not text"), which
    `SkillNormativeGateService` turns into a counted `UnreadableClause`
    finding. This one means "I could not tell" -- the object store itself
    refused to answer -- and must make the WHOLE baseline undecidable, never a
    silently-counted finding.
    """


class HeadSkillCorpusReader:
    """`SkillCorpusReaderPort` backed by one commit's git blobs."""

    def __init__(self, contents: CommitContentsPort, head: str, root: Path) -> None:
        self._contents = contents
        self._head = head
        self._root = root

    def read_manifest(self, manifest_path: Path) -> dict[str, Any]:
        """Parse the manifest JSON as HEAD recorded it."""
        return cast("dict[str, Any]", json.loads(self._read_text(manifest_path)))

    def read_asset(self, asset_path: Path) -> str:
        """Read a skill asset as HEAD recorded it (UTF-8 text)."""
        return self._read_text(asset_path)

    def _read_text(self, path: Path) -> str:
        rel = _relative_to_root(path, self._root)
        answer = self._contents.blob_at(self._head, rel)
        if answer.outcome is BlobOutcome.ABSENT:
            raise ManifestAssetAbsent(
                f"HEAD `{self._head[:9]}` does not record `{rel}`"
            )
        if answer.outcome is BlobOutcome.INDETERMINATE:
            raise HeadBlobUnreadable(
                f"`{rel}` at HEAD `{self._head[:9]}` is not readable: {answer.detail}"
            )
        assert answer.data is not None  # PRESENT, by the two branches above
        try:
            return answer.data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ManifestAssetUndecodable(
                f"`{rel}` at HEAD `{self._head[:9]}` is not valid UTF-8 text"
            ) from exc


def _relative_to_root(path: Path, root: Path) -> str:
    """`path`, made relative to `root` and POSIX-slashed, for a git tree lookup."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()
