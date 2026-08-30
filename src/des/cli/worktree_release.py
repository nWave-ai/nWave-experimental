"""Atomically release one positively identified worktree owner lease."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from des.adapters.driven.marker_file_owner_lease_adapter import (
    MarkerFileOwnerLeaseAdapter,
    MarkerTransitionError,
)
from des.adapters.driven.refactor.git_worktree_adapter import GitWorktreeAdapter
from des.domain.worktree_residence import LaneIdentity, OwnerLease


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des worktree-release",
        description="Write RELEASED only over a matching HELD owner assertion.",
    )
    parser.add_argument("--repo", required=True)
    parser.add_argument("--worktree", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    repo = Path(args.repo).resolve()
    worktree = Path(args.worktree).resolve()
    git_worktree = GitWorktreeAdapter()
    linked_worktrees = git_worktree.list_worktrees(repo)
    if repo == worktree:
        admitted = not git_worktree.is_linked_worktree(repo)
    else:
        admitted = any(handle.path.resolve() == worktree for handle in linked_worktrees)
    if not admitted:
        print("WHAT: owner lease was not released", file=sys.stderr)
        print(
            "WHY: the path is neither an exact linked worktree nor the Git-primary checkout",
            file=sys.stderr,
        )
        print(
            "HOW: pass the Git-primary repository and its exact owned lane.",
            file=sys.stderr,
        )
        return 1
    identity = LaneIdentity.observe(worktree)
    probe = MarkerFileOwnerLeaseAdapter()
    observed = probe.observe(worktree, identity)
    if observed is OwnerLease.INDETERMINATE:
        print("WHAT: owner lease was not released", file=sys.stderr)
        print(
            "WHY: the marker is missing, unreadable, malformed, stale, or identity-mismatched",
            file=sys.stderr,
        )
        print(
            "HOW: recover the matching HELD assertion; absence never means release.",
            file=sys.stderr,
        )
        return 1
    try:
        probe.write_released(worktree, identity)
    except MarkerTransitionError as exc:
        print("WHAT: owner lease was not released", file=sys.stderr)
        print(f"WHY: {exc}", file=sys.stderr)
        print(
            "HOW: release only the lane whose HELD identity matches.", file=sys.stderr
        )
        return 1
    print(worktree)
    return 0


__all__ = ["main"]
