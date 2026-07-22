"""BuildDistArtifactBuilder -- build a feature's delivered artifact.

Driven adapter for feature `walking-skeleton-production-like-gate` (DESIGN /
Staged-Install Fixture, step 1; Component Decomposition). Wraps the real
`pip wheel` build as a subprocess -- the build is invoked, never imported, so
this adapter stays import-light (the `des.cli` bundle-scan contract).

slice-01 (the walking skeleton): the feature under gate is a self-contained
installable Python project (a `pyproject.toml` + a package). The builder runs
`python -m pip wheel` against the project root and returns the built `.whl`
-- the delivered artifact a consumer installs.

The artifact build is real I/O (a real subprocess, a real `.whl`) -- this is
the T1 mechanism the RCA flagged.
"""

from __future__ import annotations

from pathlib import Path

from des.ports.driven_ports.artifact_builder import (
    ArtifactBuilder,
    ArtifactBuildError,
)
from des.runtime.interpreter import des_spawn


class BuildDistArtifactBuilder(ArtifactBuilder):
    """Build a feature's delivered artifact by invoking `pip wheel`."""

    def build(self, feature_root: Path) -> Path:
        """Build the feature's `.whl` and return the path to it.

        Raises `ArtifactBuildError` when the feature root has no build
        configuration or the build subprocess fails.
        """
        feature_root = Path(feature_root)
        if not (feature_root / "pyproject.toml").is_file():
            raise ArtifactBuildError(
                f"feature root has no pyproject.toml: {feature_root}"
            )
        wheel_dir = feature_root / "dist"
        wheel_dir.mkdir(parents=True, exist_ok=True)
        result = des_spawn(
            None,
            "pip",
            "wheel",
            "--no-deps",
            "--wheel-dir",
            str(wheel_dir),
            str(feature_root),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise ArtifactBuildError(
                f"pip wheel failed (exit {result.returncode}): "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        wheels = sorted(wheel_dir.glob("*.whl"))
        if not wheels:
            raise ArtifactBuildError(f"build produced no wheel under {wheel_dir}")
        return wheels[-1]


__all__ = ["BuildDistArtifactBuilder"]
