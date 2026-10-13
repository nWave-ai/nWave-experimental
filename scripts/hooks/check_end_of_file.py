"""Check (or repair) end-of-file newlines.

Modes:
  --fix   (default): append the missing newline, exit 0. The route the
                     rejection message points the operator at.
  --check : report missing newlines, exit 1 if any found.

Scope:
  With FILE arguments, only those files are examined -- this is how the
  pre-commit hook runs it, so a commit is graded on ITS OWN files and not on
  pre-existing offenders elsewhere in the tree. With no arguments it falls back
  to every git-tracked file, which is how CI runs it as the whole-tree backstop.
  Imported receipts and verbatim ATD measurement artifacts are excluded in both
  modes: artifact SHA-256 values bind their bytes, so EOF normalization would
  corrupt the evidence. Canonical measurement reports and protocols stay checked.

The hook deliberately runs `--check`, never `--fix`: auto-modifying hooks were
removed on 2026-05-28 (commit 11a24c637) because concurrent rewrites race across
parallel worktrees. Repair stays an explicit operator action.
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

# Receipt artifact SHA-256 values bind these bytes; EOF normalization corrupts evidence.
BYTE_EXACT_EVIDENCE_PREFIXES = (
    "tests/des/architect_handoff/fixtures/v9lb1/",
    "docs/feature/atd-policy-alignment/measurement/baseline-1/presence/",
    "docs/feature/atd-policy-alignment/measurement/baseline-1/scoring/",
    "docs/feature/atd-policy-alignment/measurement/baseline-1/turns/",
    "docs/feature/atd-policy-alignment/measurement/baseline-1/prompts/",
    "docs/feature/atd-policy-alignment/measurement/iterations/scoring/",
    "docs/feature/atd-policy-alignment/measurement/iterations/turns/",
    "docs/feature/atd-policy-alignment/measurement/iterations/prompts/",
)
BYTE_EXACT_EVIDENCE_FILES = frozenset(
    {
        "docs/feature/atd-policy-alignment/measurement/baseline-1/matrix-summary.json",
        "docs/feature/atd-policy-alignment/measurement/iterations/iter1-matrix-summary.json",
        # DES handover codec writes canonical JSON without a final LF; read_handover
        # refuses any other bytes (src/des/application/handover.py).
        "tests/des/acceptance/atd_prompt_dedup/fixture/.nwave/des/handover.json",
        "tests/des/acceptance/atd_prompt_dedup/fixture/run5/.nwave/des/handover.json",
    }
)


FIX_COMMAND = "python3 scripts/hooks/check_end_of_file.py --fix"


def _is_scannable(path: str) -> bool:
    return (
        bool(path)
        and path not in BYTE_EXACT_EVIDENCE_FILES
        and not path.startswith(BYTE_EXACT_EVIDENCE_PREFIXES)
        and not any(path.lower().endswith(ext) for ext in BINARY_EXT)
    )


def _get_tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=False
    )
    return [
        f
        for f in result.stdout.splitlines()
        if _is_scannable(f) and not f.startswith(("dist/", ".git/"))
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
    args = sys.argv[1:]
    check_only = "--check" in args

    # Explicit file arguments scope the run to the caller's own files; with
    # none, fall back to the whole tracked tree (the CI backstop invocation).
    targets = [a for a in args if not a.startswith("-")]
    files = (
        [f for f in targets if _is_scannable(f)] if targets else _get_tracked_files()
    )
    bad = _find_missing_newlines(files)

    if not bad:
        return 0

    if check_only:
        for b in bad[:20]:
            print(f"Missing newline at end of file: {b}")
        if len(bad) > 20:
            print(f"... and {len(bad) - 20} more")
        print()
        print("WHY: a file without a final newline breaks diff/concat tooling and")
        print("     is rejected by the CI file-quality job, costing a full push")
        print("     round-trip to discover.")
        print(f"HOW: {FIX_COMMAND} {' '.join(bad)}")
        print("     (or run it with no file arguments to repair the whole tree)")
        return 1

    # Repair mode: append the newline. Re-stage only when the caller did not
    # name the files itself (whole-tree operator run); an explicit file list
    # comes from a hook or a test, which owns its own staging.
    for filepath in bad:
        with open(filepath, "ab") as fw:
            fw.write(b"\n")
    if not targets:
        subprocess.run(["git", "add", "--", *bad], check=False)
    for f in bad[:10]:
        print(f"Fixed missing newline: {f}")
    if len(bad) > 10:
        print(f"... and {len(bad) - 10} more")

    return 0


if __name__ == "__main__":
    sys.exit(main())
