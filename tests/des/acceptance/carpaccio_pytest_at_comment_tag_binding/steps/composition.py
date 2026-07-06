"""Composition root for the pytest-AT comment-tag discovery slice (slice-01).

carpaccio-pytest-at-comment-tag-binding: drives the NEW
``feature_tagged_test_files`` resolver (``des.application.feature_at_files``)
directly -- the same shape the sibling ``carpaccio_slice_plan_parser`` slice
uses for a shared application-layer parser entry point (Layer 3 composition,
Mandate 13): this resolver IS the driving surface a future CLI (slice-04's
``des carpaccio-slice-gate`` auto-discovery) will consume, so calling it via a
composition root is driving the production surface, not a direct-domain
bypass.

Layer 3 composition-root acceptance over a real filesystem under pytest
``tmp_path`` (``@real-io`` -- Architecture of Reference: no fake, no mock).
Example-only, no PBT machinery (Mandate 9/11) -- slice-01 pins the two closed
cases (head-tagged file discovered, untagged file excluded / empty-set
guardrail), not a property.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path

from .domain_types import FeatureId


@dataclass(frozen=True)
class AttributionResult:
    """The observable slice + covered spec-row attribution of one head-tagged
    test file (slice-02) -- resolved from the SAME bounded head-window
    ``feature_tagged_test_files`` (slice-01) already scans.
    """

    slice_id: str | None
    covers: tuple[str, ...]

    def names_slice(self, slice_id: str) -> bool:
        return self.slice_id == slice_id

    def covers_row(self, row_id: str) -> bool:
        return row_id in self.covers


@dataclass(frozen=True)
class DiscoveryResult:
    """The observable result of one ``feature_tagged_test_files`` call."""

    resolved_files: tuple[Path, ...]

    def includes(self, path: Path) -> bool:
        return path in self.resolved_files

    def excludes(self, path: Path) -> bool:
        return path not in self.resolved_files


class FeatureTaggedTestFilesComposition:
    """Production-wired access to the real ``feature_tagged_test_files`` resolver."""

    def __init__(self, repo_dir: Path) -> None:
        self._repo = repo_dir
        self._repo.mkdir(parents=True, exist_ok=True)

    # --- scratch-repo authoring (preconditions, never the expected output) --

    def write_test_file(self, relative_path: str, content: str) -> Path:
        """Write a test-file fixture under the scratch repo; returns its real path."""
        path = self._repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    # --- driving the real resolver ------------------------------------------

    def resolve(self, feature_id: FeatureId) -> DiscoveryResult:
        """Drive the real ``feature_tagged_test_files`` over the scratch repo."""
        feature_at_files = importlib.import_module("des.application.feature_at_files")
        resolved = feature_at_files.feature_tagged_test_files(self._repo, feature_id)
        return DiscoveryResult(resolved_files=tuple(resolved))

    def resolve_attribution(self, relative_path: str) -> AttributionResult:
        """Drive the real ``resolve_test_file_attribution`` (slice-02) over a
        written scratch-repo file, identified by its repo-relative path.
        """
        feature_at_files = importlib.import_module("des.application.feature_at_files")
        path = self._repo / relative_path
        attribution = feature_at_files.resolve_test_file_attribution(path)
        return AttributionResult(
            slice_id=attribution.slice_id, covers=tuple(attribution.covers)
        )
