#!/usr/bin/env python3
"""Bulk-replace /nw-command references with /nw-command across the codebase.

Part of the commands→skills migration (BREAKING CHANGE).

Patterns replaced:
  /nw-foo     → /nw-foo      (slash command invocations)
  `nw-foo`    → `nw-foo`     (backtick code references)
  "nw-foo"    → "nw-foo"     (string literals)
  'nw-foo'    → 'nw-foo'     (string literals)

Excluded directories: .git, dist, .venv, __pycache__, .pytest_cache, .hypothesis, node_modules

Usage:
    python scripts/update_command_references.py          # dry-run
    python scripts/update_command_references.py --apply   # write changes
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


EXCLUDE_DIRS = {
    ".git",
    "dist",
    ".venv",
    ".venv-mutation",
    "__pycache__",
    ".pytest_cache",
    ".hypothesis",
    "node_modules",
    ".mypy_cache",
    ".ruff_cache",
    ".nwave",
}

# File extensions to process
INCLUDE_EXTENSIONS = {
    ".md",
    ".py",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".txt",
    ".sh",
}

# Pattern: nw: followed by a word character or hyphen (command name)
# Matches: /nw-deliver, `nw-execute`, "nw-design", '/nw:*'
NW_COLON_PATTERN = re.compile(r"nw:(\w[\w-]*)")


def should_process(path: Path) -> bool:
    """Check if file should be processed."""
    # Check exclusions
    for part in path.parts:
        if part in EXCLUDE_DIRS:
            return False
    # Check extension
    return path.suffix in INCLUDE_EXTENSIONS


def process_file(path: Path, *, apply: bool = False) -> list[str]:
    """Replace nw: patterns in a single file. Returns list of changes."""
    try:
        content = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    if "nw:" not in content:
        return []

    new_content = NW_COLON_PATTERN.sub(r"nw-\1", content)

    if new_content == content:
        return []

    # Count changes
    old_matches = NW_COLON_PATTERN.findall(content)
    changes = [f"  {len(old_matches)} replacements"]

    if apply:
        path.write_text(new_content, encoding="utf-8")

    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(),
    )
    args = parser.parse_args()

    mode = "APPLYING" if args.apply else "DRY-RUN"
    print(f"{'=' * 70}")
    print(f"  /nw: → /nw- Reference Update ({mode})")
    print(f"{'=' * 70}")

    total_files = 0
    total_replacements = 0

    for path in sorted(args.root.rglob("*")):
        if not path.is_file():
            continue
        if not should_process(path):
            continue

        changes = process_file(path, apply=args.apply)
        if changes:
            rel = path.relative_to(args.root)
            count = int(changes[0].strip().split()[0])
            print(f"  {rel}: {count} replacements")
            total_files += 1
            total_replacements += count

    print(f"\n{'=' * 70}")
    print(f"  Files: {total_files}, Replacements: {total_replacements}")
    if not args.apply and total_replacements > 0:
        print("  Run with --apply to write changes.")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
