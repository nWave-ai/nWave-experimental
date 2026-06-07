"""Check and auto-fix end-of-file newlines for all tracked files.

Modes:
  --fix   (default): Auto-fix missing newlines, re-stage files, exit 0.
  --check : Report missing newlines, exit 1 if any found. For CI.

Pre-commit hook uses --fix (silent auto-fix, never blocks commits).
CI uses --check (fails the build to catch issues).
"""

import subprocess
import sys
from pathlib import Path


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


def _get_tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=False
    )
    return [
        f
        for f in result.stdout.splitlines()
        if f
        and not f.startswith(("dist/", ".git/"))
        and not any(f.lower().endswith(ext) for ext in BINARY_EXT)
    ]


def _find_missing_newlines(files: list[str]) -> list[str]:
    bad = []
    for filepath in files:
        p = Path(filepath)
        if not p.is_file() or p.stat().st_size == 0:
            continue
        try:
            with open(filepath, "rb") as fh:
                fh.seek(-1, 2)
                if fh.read(1) != b"\n":
                    bad.append(filepath)
        except OSError:
            continue
    return bad


def main() -> int:
    check_only = "--check" in sys.argv

    files = _get_tracked_files()
    bad = _find_missing_newlines(files)

    if not bad:
        return 0

    if check_only:
        for b in bad[:20]:
            print(f"Missing newline at end of file: {b}")
        if len(bad) > 20:
            print(f"... and {len(bad) - 20} more")
        return 1

    # Auto-fix mode: append newline and re-stage
    for filepath in bad:
        with open(filepath, "ab") as fw:
            fw.write(b"\n")
    subprocess.run(["git", "add", "--", *bad], check=False)
    for f in bad[:10]:
        print(f"Auto-fixed missing newline: {f}")
    if len(bad) > 10:
        print(f"... and {len(bad) - 10} more")

    return 0


if __name__ == "__main__":
    sys.exit(main())
