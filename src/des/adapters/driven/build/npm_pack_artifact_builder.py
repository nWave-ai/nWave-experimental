"""NpmPackArtifactBuilder -- build a TypeScript feature's artifact via `npm pack`.

Feature `implement-language-adapter-facets`, slice-04 (feature-delta.md
Component Decomposition D6). The TS mirror of `BuildDistArtifactBuilder`
(D5's Python sibling, `build_dist_artifact_builder.py`). Implements the
EXISTING `ArtifactBuilder` port (DDD-03) -- no port-body change; a 2nd
concrete implementation alongside the pip-based one.

Real I/O: a real `npm pack --pack-destination <dir>` subprocess. `npm` is
resolved via the SHARED `resolve_tool` discovery scale (reused from
`VITEST_KNOWN_LOCATIONS` -- the feature-delta Reuse Analysis row "D6/D7
reuse the SAME discovery scale for npm/npx/vitest binaries").
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from des.adapters.driven.runner.tool_discovery import resolve_tool
from des.adapters.driven.runner.vitest_runner import VITEST_KNOWN_LOCATIONS
from des.ports.driven_ports.artifact_builder import ArtifactBuilder, ArtifactBuildError


class NpmPackArtifactBuilder(ArtifactBuilder):
    """Build a TypeScript feature's delivered artifact via `npm pack` (D6)."""

    def build(self, feature_root: Path) -> Path:
        """Build the feature's `.tgz` tarball and return the path to it.

        Raises `ArtifactBuildError` when `npm` cannot be resolved or the
        `npm pack` subprocess fails.
        """
        feature_root = Path(feature_root)
        resolution = resolve_tool("npm", VITEST_KNOWN_LOCATIONS, base_dir=feature_root)
        if resolution.path is None:
            raise ArtifactBuildError(f"npm not found: {resolution.remediation}")
        dist_dir = feature_root / "dist"
        dist_dir.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [resolution.path, "pack", "--pack-destination", str(dist_dir)],
            cwd=str(feature_root),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise ArtifactBuildError(
                f"npm pack failed (exit {result.returncode}): "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        tarballs = sorted(dist_dir.glob("*.tgz"))
        if not tarballs:
            raise ArtifactBuildError(f"npm pack produced no tarball under {dist_dir}")
        return tarballs[-1]


__all__ = ["NpmPackArtifactBuilder"]
