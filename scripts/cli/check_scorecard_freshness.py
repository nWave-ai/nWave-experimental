"""Scorecard freshness audit CLI -- slice-01 walking skeleton.

F-CROSS-TREE-SCORECARD-FRESHNESS-AUDIT-CLI slice-01. Sibling of the spine-gate
CLIs in ``scripts/cli/`` (``at_review_verdict.py``, ``carpaccio_slice_gate.py``,
``check_robustness_density.py``, ``verify_coverage_map.py``). nwave-dev has NO
sequencer/engine (Ale 2026-05-24): the CLI is hook-only -- invoked by cron, CI
badge, or human PRR review.

For every cell that cites an F-id, asks the backing git history "is there a
recent commit naming this F-id?". If yes the cell is FRESH; otherwise STALE.
Top-level verdict is PASS iff every cited F-id is FRESH; otherwise FAIL. The
CLI is READ-ONLY -- invoking it never mutates the scorecard file.

Exit codes (mirroring sibling gate CLIs):
    0 = PASS -- every cited F-id has a recent commit
    1 = FAIL -- at least one cited F-id has no recent commit
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from des.cli.human_surface import Verdict, print_human_summary


_EXIT_PASS = 0
_EXIT_FAIL = 1

_STDOUT_TOKEN_PREFIX = "scorecard_freshness"
_DEFAULT_STALE_THRESHOLD_DAYS = 14

# Match F-id citations like ``F-01``, ``F-FRESH-EXAMPLE``,
# ``F-CROSS-TREE-SCORECARD-FRESHNESS-AUDIT-CLI``. Cells embed the F-id in a
# Markdown table cell; the regex scans the whole scorecard text and dedupes.
_FID_RE = re.compile(r"\bF-[A-Z0-9][A-Z0-9-]*\b")


def _parse_scorecard_fids(scorecard_path: Path) -> list[str]:
    """Return the de-duplicated, order-preserving list of F-ids cited."""
    text = scorecard_path.read_text(encoding="utf-8")
    seen: set[str] = set()
    fids: list[str] = []
    for match in _FID_RE.finditer(text):
        fid = match.group(0)
        if fid not in seen:
            seen.add(fid)
            fids.append(fid)
    return fids


def _fid_has_recent_commit(fid: str, since_days: int, cwd: Path) -> bool:
    """Return True iff ``git log --grep <fid> --since=<N> days ago`` is non-empty."""
    proc = subprocess.run(
        [
            "git",
            "log",
            f"--grep={fid}",
            "-i",
            f"--since={since_days} days ago",
            "--pretty=%H",
        ],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )
    return bool(proc.stdout.strip())


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_scorecard_freshness",
        description=(
            "Scorecard freshness audit (slice-01 walking skeleton). For each "
            "F-id cited in the scorecard, asserts a commit naming the F-id "
            "exists in the backing git history within the staleness threshold."
        ),
    )
    parser.add_argument(
        "--scorecard",
        required=True,
        help="Path to the scorecard Markdown file to audit.",
    )
    parser.add_argument(
        "--stale-threshold-days",
        type=int,
        default=_DEFAULT_STALE_THRESHOLD_DAYS,
        help=(
            "F-id commits older than this many days are STALE. "
            f"Default {_DEFAULT_STALE_THRESHOLD_DAYS}."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the scorecard freshness audit; return the verdict exit code."""
    args = _build_parser().parse_args(argv)
    scorecard_path = Path(args.scorecard)

    fids = _parse_scorecard_fids(scorecard_path)
    fresh: list[str] = []
    stale: list[str] = []
    for fid in fids:
        if _fid_has_recent_commit(
            fid, args.stale_threshold_days, scorecard_path.parent
        ):
            fresh.append(fid)
        else:
            stale.append(fid)

    verdict = "PASS" if not stale else "FAIL"
    token = (
        f"{_STDOUT_TOKEN_PREFIX} "
        f"scorecard={scorecard_path} "
        f"cells={len(fids)} "
        f"fresh={len(fresh)} "
        f"stale={len(stale)} "
        f"missing=0 "
        f"verdict={verdict}"
    )
    sys.stdout.write(token + "\n")
    for fid in stale:
        sys.stdout.write(f"stale cell: {fid}\n")
    if verdict == "PASS":
        print_human_summary(
            Verdict.PASS,
            f"scorecard freshness verified: {len(fids)} cited F-id(s) "
            f"have a recent commit within the staleness threshold",
        )
    else:
        print_human_summary(
            Verdict.FAIL,
            f"scorecard freshness refused: {len(stale)} of {len(fids)} cited "
            f"F-id(s) lack a recent commit (stale: {sorted(stale)})",
        )
    return _EXIT_PASS if verdict == "PASS" else _EXIT_FAIL


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
