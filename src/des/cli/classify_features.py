"""des.cli.classify_features -- the `des-classify-features` detection CLI.

Feature `classic-spine-decommission`, slice-01/slice-03. Scans `docs/feature/*`
and emits a migration manifest classifying each feature into one of five DELIVER
spine states (DESIGN: Legacy-Feature Detection Mechanism).

Hexagonal: an argparse driving adapter over the pure `feature_classifier`
domain function plus a read-only `FeatureScanPort` driven adapter. The manifest
is written by this CLI, never through the read-only scan port.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from des.adapters.driven.filesystem.feature_scan_adapter import FeatureScanAdapter
from des.domain import feature_classifier


if TYPE_CHECKING:
    from des.ports.driven_ports.feature_scan_port import FeatureScanPort


def main(argv: list[str] | None = None) -> int:
    """Scan a feature tree and emit a migration manifest. Returns an exit code."""
    args = _parse_args(argv)
    scan: FeatureScanPort = FeatureScanAdapter()
    rows = _classify_tree(scan, args.features_root)
    _write_manifest(args.out, rows)
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the `--features-root` / `--out` argv contract."""
    parser = argparse.ArgumentParser(prog="des classify-features")
    parser.add_argument("--features-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    return parser.parse_args(argv)


def _classify_tree(
    scan: FeatureScanPort, features_root: Path
) -> list[dict[str, object]]:
    """Classify every feature directory under `features_root` into manifest rows."""
    return [
        _classify_one(scan, feature_dir)
        for feature_dir in scan.feature_dirs(features_root)
    ]


def _classify_one(scan: FeatureScanPort, feature_dir: Path) -> dict[str, object]:
    """Build one manifest row for a single feature directory.

    The ``git_state`` stamp is the feature dir's git tree-object SHA at
    ``HEAD``, read through the read-only `FeatureScanPort`. The converter's
    M7 staleness guard compares this stamp against the live tree -- an
    untracked or non-repo feature dir stamps ``""`` and is never refused as
    stale (symmetric with the comparator).
    """
    return {
        "feature_id": feature_dir.name,
        "class": feature_classifier.classify(feature_dir),
        "has_slice_plan": feature_classifier.has_slice_plan(feature_dir),
        "roadmap_steps": None,
        "committed_steps": [],
        "git_state": scan.git_tree_sha(feature_dir),
    }


def _write_manifest(out: Path, rows: list[dict[str, object]]) -> None:
    """Write the migration manifest JSON to `out`, creating parent dirs."""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"features": rows}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover - subprocess entry point
    sys.exit(main(sys.argv[1:]))
