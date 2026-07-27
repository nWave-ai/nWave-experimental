"""Validate that every agent file on disk has a corresponding catalog entry.

Runs as a CI gate to ensure no agent is accidentally left uncatalogued.
Uses ``is_agent_on_disk_catalogued()`` from ``agent_catalog.py`` for the
actual validation logic.

Usage::

    python scripts/validation/validate_catalog_completeness.py [nwave-dir]

Exits 0 if all agents are catalogued, 1 otherwise.
"""

from __future__ import annotations

import sys
from pathlib import Path


# Standalone-script bootstrap: this file is invoked as a bare
# `python scripts/validation/validate_catalog_completeness.py` (per the
# Usage docstring above, and as a `language: system` pre-commit/CI hook with
# no venv on sys.path) -- the repo root is not on sys.path in that form, so
# the absolute `from scripts.shared...` import below raises
# `ModuleNotFoundError: No module named 'scripts'` unless the repo root is
# prepended first. Mirrors the identical bootstrap in the sibling
# `validate_skill_agent_mapping.py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.shared.agent_catalog import is_agent_on_disk_catalogued


def main(nwave_dir: Path | None = None) -> int:
    """Validate catalog completeness.

    Returns 0 if all agents are catalogued, 1 otherwise.
    """
    if nwave_dir is None:
        # Default: project root nWave/ directory
        nwave_dir = Path(__file__).resolve().parent.parent.parent / "nWave"

    agents_dir = nwave_dir / "agents"

    uncatalogued = is_agent_on_disk_catalogued(agents_dir, nwave_dir)

    if not uncatalogued:
        print("Catalog completeness: PASS - all agents catalogued")
        return 0

    print("Catalog completeness: FAIL - uncatalogued agents found:", file=sys.stderr)
    for entry in uncatalogued:
        print(f"  - {entry}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    nwave_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    sys.exit(main(nwave_path))
