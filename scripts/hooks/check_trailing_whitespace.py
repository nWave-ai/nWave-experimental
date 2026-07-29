"""Check (or repair) trailing whitespace.

Modes:
  --check (default): report offenders, exit 1 if any. Used by CI and by the
                     pre-commit hook -- never modifies a file.
  --fix            : strip the trailing whitespace in place, exit 0. The route
                     the rejection message points the operator at.

Scope:
  With FILE arguments, only those files are examined -- this is how the
  pre-commit hook runs it, so a commit is graded on ITS OWN files and not on
  pre-existing offenders elsewhere in the tree. With no arguments it falls back
  to every git-tracked file, which is how CI runs it as the whole-tree backstop.

The hook deliberately runs `--check`, never `--fix`: auto-modifying hooks were
removed on 2026-05-28 (commit 11a24c637) because concurrent rewrites race across
parallel worktrees. Repair stays an explicit operator action.
"""

import subprocess
import sys


BINARY_EXT = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".ico",
        ".bmp",
        ".webp",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".zip",
        ".gz",
        ".tar",
        ".bz2",
        ".pdf",
        ".pyc",
        ".pyo",
        ".so",
        ".dll",
    }
)

FIX_COMMAND = "python3 scripts/hooks/check_trailing_whitespace.py --fix"


def _is_scannable(path: str) -> bool:
    return bool(path) and not any(path.lower().endswith(ext) for ext in BINARY_EXT)


def _tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=False
    )
    return [
        f
        for f in result.stdout.splitlines()
        if _is_scannable(f) and not f.startswith(("dist/", ".git/"))
    ]


def _offending_lines(filepath: str) -> list[int]:
    """1-based line numbers carrying trailing spaces/tabs."""
    try:
        with open(filepath, errors="ignore") as fh:
            return [
                i
                for i, line in enumerate(fh, 1)
                if line.rstrip("\n\r") != line.rstrip("\n\r").rstrip(" \t")
            ]
    except (OSError, UnicodeDecodeError):
        return []


def _strip_file(filepath: str) -> None:
    """Rewrite the file with trailing whitespace removed, newlines preserved."""
    with open(filepath, newline="", errors="ignore") as fh:
        content = fh.read()

    fixed = "".join(
        line.rstrip("\n\r").rstrip(" \t") + line[len(line.rstrip("\n\r")) :]
        for line in content.splitlines(keepends=True)
    )

    with open(filepath, "w", newline="", errors="ignore") as fh:
        fh.write(fixed)


def main() -> int:
    args = sys.argv[1:]
    fix_mode = "--fix" in args
    targets = [a for a in args if not a.startswith("-")]
    files = [f for f in targets if _is_scannable(f)] if targets else _tracked_files()

    offenders = {f: lines for f in files if (lines := _offending_lines(f))}

    if not offenders:
        print("No trailing whitespace found")
        return 0

    if fix_mode:
        for filepath in offenders:
            _strip_file(filepath)
        for filepath in list(offenders)[:10]:
            print(f"Stripped trailing whitespace: {filepath}")
        if len(offenders) > 10:
            print(f"... and {len(offenders) - 10} more")
        return 0

    flat = [f"{f}:{n}" for f, lines in offenders.items() for n in lines]
    for entry in flat[:20]:
        print(f"Trailing whitespace: {entry}")
    if len(flat) > 20:
        print(f"... and {len(flat) - 20} more")

    print()
    print("WHY: trailing whitespace produces noisy diffs and is rejected by the")
    print("     CI file-quality job, costing a full push round-trip to discover.")
    print(f"HOW: {FIX_COMMAND} {' '.join(sorted(offenders))}")
    print("     (or run it with no file arguments to repair the whole tree)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
