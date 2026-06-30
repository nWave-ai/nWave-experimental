#!/usr/bin/env python3
"""commit-msg hook: fire `des run-slice-ats` on a slice commit (the FIRING SURFACE).

f-spine-runs-tests-not-git-hooks (ADR-FLOW-005 D1): the SPINE, not a git hook,
is the commit-time test authority -- but the spine slice-AT EXECUTOR
(`des run-slice-ats`, src/des/cli/run_slice_ats.py) must be REACHED from a real
commit-path firing surface, not only named in crafter-skill prose. This hook is
that surface: on a slice commit it reads the entering slice from the commit
message's `Slice-Id:` / `Step-Id:` trailer and invokes the shipped executor,
which genuinely RUNS only that slice's acceptance tests (a real execution, not a
collect-only walk) and vetoes (exit 1) on a RED slice AT.

Degrade-LOUD / fail-open discipline (the executor owns the no-silent-pass
contract, this hook only routes):

  * No `Slice-Id:` / `Step-Id:` trailer in the commit -> NOT a slice commit ->
    PASS (exit 0). A non-slice commit (chore, docs, merge) is not in scope.
  * A slice trailer present -> fire `des run-slice-ats --repo . --entering-slice
    <slice>`; propagate its exit code. The executor itself returns FAIL (exit 1)
    on a RED slice AT, NOT_APPLICABLE (exit 0) on a no-real-AT slice (no
    fabricated green), and INDETERMINATE (exit 4, degrade-LOUD) on an
    unresolved/absent target runner -- NEVER a silent pass.
  * The `des` executor unreachable on this machine (spawn error) -> the hook
    fails OPEN with a LOUD stderr note (the interim git-hook net is a
    convenience layer; the spine's own feature-end full-suite is the certainty,
    ADR-FLOW-005 D4). It does NOT block a commit on a missing dev toolchain.

Git-free in its own logic (Python + filesystem only, AD-21): it reads the commit
message FILE git hands it ($1 / argv[1]) and shells the shipped `des` gate. The
target's OWN runner is resolved inside the executor via `TestRunnerPort`, never
hardcoded here.

Wired in `.pre-commit-config.yaml` at the `commit-msg` stage (the stage where
the message file -- and thus the Slice-Id trailer -- is available).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


_REPO = Path(__file__).resolve().parents[2]

# The canonical entering-slice binding: a `Slice-Id:` / `Step-Id:` commit trailer
# (mirrors spine_ledger_pre_commit_hook._SLICE_TRAILER_RE). The fallback token
# form (`slice-NN: subject`) is matched only when no trailer is present.
_SLICE_TRAILER_RE = re.compile(
    r"^(?:Slice-Id|Step-Id):\s*(slice-\d+[a-z]?)\s*$", re.MULTILINE
)
_SLICE_TOKEN_RE = re.compile(r"\bslice-\d+[a-z]?\b")


def _entering_slice(commit_message: str) -> str | None:
    """The entering slice id from the commit message, or None (not a slice commit)."""
    trailer = _SLICE_TRAILER_RE.search(commit_message)
    if trailer is not None:
        return trailer.group(1)
    token = _SLICE_TOKEN_RE.search(commit_message)
    return token.group(0) if token is not None else None


def _read_commit_message(argv: list[str]) -> str:
    """Read the commit-message file git passes as argv[1] (empty when absent)."""
    if not argv:
        return ""
    try:
        return Path(argv[0]).read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, IsADirectoryError, OSError):
        return ""


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    message = _read_commit_message(args)
    entering = _entering_slice(message)
    if entering is None:
        # Not a slice commit -> nothing for the slice-AT executor to run.
        return 0

    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "des",
                "run-slice-ats",
                "--repo",
                str(_REPO),
                "--entering-slice",
                entering,
            ],
            cwd=str(_REPO),
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        # The des executor could not be spawned (missing dev toolchain) -> fail
        # OPEN with a LOUD note. The spine's feature-end full-suite is the
        # certainty; this commit-path net is the interim convenience layer.
        print(
            f"run-slice-ats: could not invoke the spine slice-AT executor "
            f"({exc}); the commit is NOT blocked (interim git-hook net, "
            f"ADR-FLOW-005 D4). The feature-end full-suite remains the certainty.",
            file=sys.stderr,
        )
        return 0

    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.returncode != 0 and proc.stderr.strip():
        print(proc.stderr.strip(), file=sys.stderr)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
