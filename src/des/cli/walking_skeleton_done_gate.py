"""des.cli.walking_skeleton_done_gate -- the "feature done" block check.

RED scaffold created by DISTILL (ADR-025 / Mandate 7) for feature
`walking-skeleton-production-like-gate`. DELIVER replaces this scaffold with
the implementation.

Contract (DESIGN / Fail-Mode D + Done-gate block): blocks "feature done"
(exit 1) unless BOTH hold for the feature:
  (a) no `walking-skeleton-unverified` marker is present (an unparseable
      marker counts as present -> block, RM-3 ST-20), AND
  (b) a positive `WalkingSkeletonTierVerified` ledger record exists (RM-3 --
      a hand-`rm` of the marker satisfies (a) but not (b)).
An OS-sensitive feature with an unsettled `walking-skeleton-tier-debt` record
is also blocked (RM-4).
"""

from __future__ import annotations


__SCAFFOLD__ = True

import argparse
import sys


def _build_parser() -> argparse.ArgumentParser:
    """Build the done-gate CLI argument parser.

    Argparse-first so `des walking-skeleton-done-gate --help` succeeds even
    while the gate body is a RED scaffold (single-entry-point slice-02
    reachability contract — F-DES-SINGLE-ENTRY-POINT-CONSOLIDATION).
    """
    return argparse.ArgumentParser(
        prog="des walking-skeleton-done-gate",
        description=(
            "Block 'feature done' unless the walking-skeleton tier was "
            "verified (RED scaffold; DELIVER replaces this entry point)."
        ),
    )


def main(argv: list[str] | None = None) -> int:
    """Entry point -- RED scaffold; raises until DELIVER implements the done-gate.

    Argparse handles `--help` / unknown flags first so the dispatcher's
    reachability contract (every subcommand answers `--help` cleanly) is
    satisfied even while the gate body is scaffolded.
    """
    parser = _build_parser()
    parser.parse_args(argv)
    raise AssertionError(
        "Not yet implemented -- RED scaffold (walking-skeleton-production-like-gate)"
    )


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
