"""``des verify-worktree-cleanup`` -- the mechanical worktree-cleanup gate.

CREATE_NEW (parallel-work-cleans-up-after-merge-back slice-01, D-2/D-3,
ADR-SWARM-002). ``_emit``'s JSON-payload convention
(``des.cli.verify_red_green``) is the shape this CLI's output follows,
not code it calls (Reuse Analysis).

ACT-by-default (D-D3): sweeps every registered worktree (or the ONE named via
``--worktree``), removes any worktree whose branch is a CONFIRMED ancestor of
``--target-branch`` (state-based, never signal-based -- D-D2), and leaves
everything else untouched. ``--check-only`` turns the sweep into a pure read
-- the DONE-check backstop that refuses (exit 1) while a ``CLEANUP_DUE`` entry
lingers, naming WHAT/WHY/HOW (GDP-3).

Emits a single ``nwave.worktree_cleanup.v1``-shaped JSON line
(``WorktreeCleanupReport``). Exit 0 iff no ``CLEANUP_DUE`` entry remains
unresolved after the run; exit 1 otherwise.

Contract: bounded-change -- this CLI is a thin driving wrapper over
``WorktreeCleanupService.sweep``; its own mutation set is IDENTICAL to and
bounded by the service's (``--check-only`` narrows the invocation to
read-only, never widens it).

slice-02 (D-3, ADR-SWARM-002) additive CLI-layer-only presentation: when a
sweep is scoped to ONE worktree via ``--worktree`` (a maintainer's explicit
removal attempt) and that entry's verdict is ``NOT_YET_MERGEABLE``, the entry
gains a ``"reason"`` string naming that the merge-back has not happened yet
(GDP-3 self-explaining). No domain/application/port change -- D-D4's
structural refusal (mutation unreachable for a non-``CLEANUP_DUE`` entry)
stays untouched.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from des.adapters.driven.git.git_subprocess import is_merged_contribution
from des.adapters.driven.refactor.git_worktree_adapter import GitWorktreeAdapter
from des.application.worktree_cleanup_service import WorktreeCleanupService
from des.cli._emit_json import emit_json_line as _emit
from des.cli._repo_root_arg import add_repo_root_argument
from des.domain.worktree_cleanup import WorktreeCleanupVerdict


if TYPE_CHECKING:
    from des.application.worktree_cleanup_service import WorktreeCleanupEntry


_SCHEMA = "nwave.worktree_cleanup.v1"
_EXIT_CLEAN = 0
_EXIT_REFUSED = 1


def _entry_payload(entry: WorktreeCleanupEntry, *, scoped: bool) -> dict[str, object]:
    """One entry's JSON row. Adds a self-explaining ``reason`` (GDP-3) for a
    ``--worktree``-scoped attempt whose verdict refuses removal --
    ``NOT_YET_MERGEABLE`` (not merged yet) or ``HAS_UNCOMMITTED_CHANGES``
    (uncommitted work would be lost) -- the refusals a maintainer's explicit
    removal attempt can hit.

    ``branch`` is ``None`` for a detached-HEAD worktree (detached-worktree-
    excluded-from-cleanup-sweep bugfix) -- reported as JSON ``null``, never
    a crash."""
    row: dict[str, object] = {
        "path": entry.path,
        "branch": entry.branch,
        "verdict": entry.verdict.value,
        "removed": entry.removed,
    }
    if not scoped:
        return row
    subject = (
        f"{entry.branch!r}"
        if entry.branch is not None
        else "this detached-HEAD worktree"
    )
    if entry.verdict is WorktreeCleanupVerdict.NOT_YET_MERGEABLE:
        row["reason"] = (
            f"{subject} has not been merged into the target branch yet "
            "-- removal is refused until the merge-back is confirmed."
        )
    elif entry.verdict is WorktreeCleanupVerdict.HAS_UNCOMMITTED_CHANGES:
        row["reason"] = (
            f"{subject} has uncommitted changes in its working tree "
            "-- removal is refused so the work is not lost; commit or discard "
            "it first."
        )
    return row


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="des verify-worktree-cleanup",
        description=(
            "Ties worktree removal to a CONFIRMED successful merge-back "
            "(D-2 enforcing gate). ACT-by-default; --check-only is a pure "
            "DONE-check backstop that never mutates."
        ),
    )
    add_repo_root_argument(
        parser, "--repo", default=".", help="Path to the repository root."
    )
    parser.add_argument(
        "--target-branch",
        required=True,
        help=(
            "The branch a worktree's own branch must be a confirmed ancestor "
            "of before its worktree is cleanup-due. No implicit default "
            "(DESIGN Open Question #2) -- pass this repo's own trunk name."
        ),
    )
    parser.add_argument(
        "--worktree",
        default=None,
        help="Scope the sweep to ONE registered worktree path (default: all).",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Pure read -- report, never mutate (the DONE-check backstop).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo = Path(args.repo).resolve()
    scope_to = Path(args.worktree) if args.worktree else None

    service = WorktreeCleanupService(
        git_worktree=GitWorktreeAdapter(), merge_check=is_merged_contribution
    )
    result = service.sweep(
        repo=repo,
        target_branch=args.target_branch,
        check_only=args.check_only,
        scope_to=scope_to,
    )

    payload: dict[str, object] = {
        "event": "WorktreeCleanupReport",
        "schema": _SCHEMA,
        "entries": [
            _entry_payload(entry, scoped=args.worktree is not None)
            for entry in result.entries
        ],
    }

    if result.has_unresolved_cleanup_due:
        lingering = ", ".join(
            f"{entry.path} ({entry.branch or 'detached'})"
            for entry in result.entries
            if entry.verdict is WorktreeCleanupVerdict.CLEANUP_DUE and not entry.removed
        )
        payload["what"] = (
            f"worktree(s) confirmed merged but still registered: {lingering}"
        )
        payload["why"] = (
            f"confirmed merged into {args.target_branch!r} but still registered "
            "-- removing a worktree is never done implicitly by a --check-only run."
        )
        payload["how"] = (
            "re-run `des verify-worktree-cleanup` without --check-only to remove "
            "them automatically, or run `git worktree remove` by hand if this "
            "repeats."
        )
        _emit(payload)
        print(f"✗ REFUSED — {payload['what']}")
        return _EXIT_REFUSED

    _emit(payload)
    count = len(result.entries)
    noun = "entry" if count == 1 else "entries"
    print(f"✓ CLEAN — {count} worktree {noun} evaluated")
    return _EXIT_CLEAN


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
