"""Pre-commit hook: detect stale command paths in source files.

Scans src/ and nWave/ for references to the deprecated ~/.claude/commands/nw/
path format. These paths were replaced by ~/.claude/skills/nw-{name}/SKILL.md
in the v3.0.0 command-to-skill migration.

Lines starting with # (comments) are ignored to allow migration notes.

Usage:
    python scripts/hooks/check_stale_command_paths.py
    python scripts/hooks/check_stale_command_paths.py src/des/domain/foo.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


STALE_PATH_PATTERN = re.compile(r"[~/.]*/commands/nw/")

SCAN_DIRS = ["src", "nWave"]


def check_files(files: list[Path]) -> list[str]:
    """Check files for stale command path references.

    Returns list of violation strings (empty = clean).
    Lines starting with # are ignored (comments).
    """
    violations: list[str] = []
    for file_path in files:
        if not file_path.exists():
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if STALE_PATH_PATTERN.search(line):
                violations.append(
                    f"{file_path}:{i}: stale command path: {line.strip()}"
                )
    return violations


def main() -> int:
    """Scan source directories for stale command paths."""
    project_root = Path(__file__).resolve().parent.parent.parent

    if len(sys.argv) > 1:
        files = [Path(f) for f in sys.argv[1:]]
    else:
        files = []
        for scan_dir in SCAN_DIRS:
            dir_path = project_root / scan_dir
            if dir_path.exists():
                files.extend(dir_path.rglob("*.py"))
                files.extend(dir_path.rglob("*.md"))

    violations = check_files(files)
    if violations:
        print("Stale command paths detected (use ~/.claude/skills/nw-{name}/SKILL.md):")
        for v in violations:
            print(f"  {v}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
