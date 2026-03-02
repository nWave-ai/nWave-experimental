#!/usr/bin/env python3
"""Validate that nWave framework files contain no references to nWave/data/.

Scans .md files in nWave/agents/, nWave/skills/, and nWave/tasks/ for
deprecated data directory references. Exits 0 if clean, 1 if violations found.

Usage:
    python scripts/validation/validate_no_data_refs.py [--root PATH]

Exit codes:
    0: No violations found
    1: One or more files reference nWave/data/ patterns
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# Patterns that indicate a reference to the deprecated data directory.
_BAD_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"nWave/data/"),
    re.compile(r"data/config/"),
    re.compile(r"data/methodologies/"),
]

# Directories to scan (relative to project root).
_SCAN_DIRS: list[str] = [
    "nWave/agents",
    "nWave/skills",
    "nWave/tasks",
]


def scan_file(filepath: Path) -> list[tuple[int, str, str]]:
    """Scan a single file for bad patterns.

    Returns a list of (line_number, matched_pattern, line_text) tuples.
    """
    violations: list[tuple[int, str, str]] = []
    try:
        text = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return violations

    for line_no, line in enumerate(text.splitlines(), start=1):
        for pattern in _BAD_PATTERNS:
            if pattern.search(line):
                violations.append((line_no, pattern.pattern, line.strip()))
                break  # one violation per line is enough
    return violations


def scan_directory(root: Path) -> list[tuple[Path, int, str, str]]:
    """Scan all .md files in configured directories.

    Returns a list of (filepath, line_number, pattern, line_text) tuples.
    """
    all_violations: list[tuple[Path, int, str, str]] = []

    for scan_dir in _SCAN_DIRS:
        dir_path = root / scan_dir
        if not dir_path.is_dir():
            continue
        for md_file in sorted(dir_path.rglob("*.md")):
            for line_no, pattern, line_text in scan_file(md_file):
                all_violations.append((md_file, line_no, pattern, line_text))

    return all_violations


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns exit code."""
    parser = argparse.ArgumentParser(
        description="Validate no nWave/data/ references in framework files"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Project root directory (default: cwd)",
    )
    args = parser.parse_args(argv)

    violations = scan_directory(args.root)

    if not violations:
        print("No nWave/data/ references found. Clean.")
        return 0

    print(f"Found {len(violations)} violation(s):\n")
    for filepath, line_no, pattern, line_text in violations:
        try:
            rel = filepath.relative_to(args.root)
        except ValueError:
            rel = filepath
        print(f"{rel}:{line_no}: {pattern} -- {line_text}")

    return 1


if __name__ == "__main__":
    sys.exit(main())
