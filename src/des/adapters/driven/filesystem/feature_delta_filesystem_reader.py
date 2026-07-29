"""Filesystem adapter for the feature-delta content reader (slice-07).

Implements ``FeatureDeltaReader`` over the DESIGN-PINNED feature-delta location
``{project_root}/docs/feature/{feature_id}/feature-delta.md`` (git-free, Python
stdlib only). The PATH layout is the design-owned contract (one SSOT shared with
the AT-seed); only the read MECHANICS are this adapter's choice.

degrade-LOUD (§17): an absent / unreadable artefact yields ``None`` so the pure
``DiscussGateOut.evaluate`` core decides INDETERMINATE -- NEVER a fabricated
empty content that would pass as a silent green.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.domain.repo_path_resolver import feature_delta_path as _delta_path
from des.ports.driven_ports.feature_delta_reader import FeatureDeltaReader


if TYPE_CHECKING:
    from pathlib import Path


class FeatureDeltaFilesystemReader(FeatureDeltaReader):
    """Reads the feature-delta content off the pinned docs/feature/ layout."""

    def read(self, project_root: Path, feature_id: str) -> str | None:
        """Read the feature-delta content (None on absent / unreadable)."""
        delta = _delta_path(project_root, feature_id)
        try:
            return delta.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

    def probe(self, project_root: Path) -> None:
        """Earned-trust probe (principle 13): round-trip + absent-artefact -> None.

        Writes a known delta to a probe subdirectory, reads it back, asserts
        round-trip fidelity, then asserts an absent artefact reads ``None`` (never
        a fabricated content). A failed probe refuses startup.
        """
        probe_root = project_root / ".nwave" / "discuss-gate" / "_probe_delta"
        feature_id = "_probe"
        delta = _delta_path(probe_root, feature_id)
        content = "# probe feature-delta\n"
        try:
            delta.parent.mkdir(parents=True, exist_ok=True)
            delta.write_text(content, encoding="utf-8")
            roundtrip = self.read(probe_root, feature_id)
            if roundtrip != content:
                raise RuntimeError(
                    "health.startup.refused: feature-delta probe round-trip "
                    f"mismatch (wrote {content!r}, read {roundtrip!r})"
                )
            absent = self.read(probe_root, "_does_not_exist")
            if absent is not None:
                raise RuntimeError(
                    "health.startup.refused: feature-delta probe fabricated "
                    f"content for an absent artefact (got {absent!r})"
                )
        finally:
            self._cleanup_probe(probe_root)

    @staticmethod
    def _cleanup_probe(probe_root: Path) -> None:
        import shutil

        shutil.rmtree(probe_root, ignore_errors=True)
