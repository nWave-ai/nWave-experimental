#!/usr/bin/env python3
"""Pre-commit "ran" marker -- companion to nwave-bypass-detector (post-commit).

Writes `$GIT_DIR/.nwave-precommit-ran` whenever the pre-commit stage runs. A
`git commit --no-verify` SKIPS the pre-commit stage, so the marker is NOT
written -- which is exactly the signal the post-commit `nwave-bypass-detector`
reads to tell a verification BYPASS from a verified commit (the prior
`PRE_COMMIT_ALLOW_NO_CONFIG` env check never fired and silently logged every
`--no-verify` commit as normal).

post-commit is NOT skipped by `--no-verify`, so the detector always runs and can
observe the marker's absence. Stdlib-only, fail-open (never blocks a commit).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    try:
        git_dir = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        if git_dir:
            (Path(git_dir) / ".nwave-precommit-ran").write_text("1", encoding="utf-8")
    except Exception:
        pass  # fail-open: a marker-write failure must never block the commit
    return 0


if __name__ == "__main__":
    sys.exit(main())
