"""nwave-ai sync — master worktree mirror sync command (DDD-4).

Per DDD-4 (lean-wave-documentation feature-delta.md):
- On-demand CLI subcommand (NOT a git hook — vendor-neutrality rule).
- Enumerates `git worktree list` for `feature/*` branches.
- Copies each worktree's `docs/feature/{id}/feature-delta.md` to
  `<master-repo>/.nwave/in-flight/{id}.md`.
- Removes mirror entries for features that have merged (file present at
  master's `docs/feature/{id}/feature-delta.md`) or whose worktree is gone.
- Idempotent: re-running with unchanged sources is a no-op (same bytes).
- `.nwave/in-flight/` is gitignored (caller responsibility on the master).

Architecture:
- Pure-functional core (`compute_sync_plan`) — takes already-enumerated
  worktree records + master state, returns a list of `SyncOp` describing
  what should happen. No I/O, fully testable as a pure function.
- Thin IO shell (`sync_in_flight`, `run_sync`, `main`) — performs the
  enumeration via `git worktree list --porcelain`, runs `compute_sync_plan`,
  and applies each op via `Path.read_text` / `Path.write_text` / `Path.unlink`.

The split keeps the planning logic deterministic and trivially testable
without spinning up real git repositories for every edge case.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


# Marker the test suite uses to assert this module is still a RED scaffold.
# Real implementation: marker disabled (set to False) so the GREEN scenario
# guard does not trigger.
__SCAFFOLD__ = False


SyncOpType = Literal["copy", "remove"]


@dataclass(frozen=True)
class WorktreeRecord:
    """One row from `git worktree list --porcelain` for a feature worktree.

    Attributes:
        worktree_path: Absolute path to the worktree root.
        branch: Branch name (e.g. ``feature/feat-alpha``). May be empty for
            detached HEAD worktrees, in which case it is filtered upstream.
        feature_id: The feature id (``feat-alpha``) extracted from the
            ``feature/<id>`` branch name. Empty when branch is not a
            feature branch.
    """

    worktree_path: Path
    branch: str
    feature_id: str


@dataclass(frozen=True)
class SyncOp:
    """One planned filesystem operation produced by `compute_sync_plan`.

    Attributes:
        op_type: Either ``"copy"`` (write feature-delta from a worktree to
            the mirror) or ``"remove"`` (delete a stale mirror entry).
        feature_id: The feature id the op pertains to.
        source_path: For ``copy`` ops, the absolute path inside the source
            worktree to read from. For ``remove`` ops, the same value as
            ``target_path`` (purely informational).
        target_path: Absolute path under the master's
            ``.nwave/in-flight/`` directory.
    """

    op_type: SyncOpType
    feature_id: str
    source_path: Path
    target_path: Path


# ---------------------------------------------------------------------------
# Pure-function core — no I/O.
# ---------------------------------------------------------------------------


def parse_worktree_porcelain(porcelain: str) -> list[WorktreeRecord]:
    """Parse the output of `git worktree list --porcelain` into records.

    The porcelain format emits blank-line-separated blocks; each block has
    `worktree <path>` and (for non-detached worktrees) `branch <ref>` lines.
    We only keep worktrees whose branch matches `refs/heads/feature/<id>`.

    Args:
        porcelain: Output of `git worktree list --porcelain`.

    Returns:
        One `WorktreeRecord` per feature worktree found.
    """
    records: list[WorktreeRecord] = []
    block: dict[str, str] = {}

    def _flush(block: dict[str, str]) -> None:
        if "worktree" not in block:
            return
        branch_ref = block.get("branch", "")
        # branch lines look like: "branch refs/heads/feature/feat-alpha"
        prefix = "refs/heads/feature/"
        if not branch_ref.startswith(prefix):
            return
        feature_id = branch_ref[len(prefix) :]
        if not feature_id:
            return
        records.append(
            WorktreeRecord(
                worktree_path=Path(block["worktree"]),
                branch=branch_ref[len("refs/heads/") :],
                feature_id=feature_id,
            )
        )

    for raw_line in porcelain.splitlines():
        line = raw_line.rstrip()
        if line == "":
            _flush(block)
            block = {}
            continue
        if " " in line:
            key, _, value = line.partition(" ")
            block[key] = value
        else:
            # Lines like "bare" or "detached" — single-token state markers.
            block[line] = ""

    # Flush trailing block (no terminating blank line).
    _flush(block)

    return records


def _is_master_worktree(record: WorktreeRecord, master_path: Path) -> bool:
    """Return True when this record refers to the master worktree itself."""
    return record.worktree_path.resolve() == master_path.resolve()


def compute_sync_plan(
    feature_worktrees: list[WorktreeRecord],
    master_path: Path,
    existing_mirror_ids: set[str],
) -> list[SyncOp]:
    """Compute the set of filesystem ops to bring the in-flight mirror current.

    Pure function. No I/O, no logging. Caller is responsible for invoking
    `git worktree list` and listing existing mirror files; this function
    consumes those parsed inputs and returns a deterministic op list.

    Op rules (per DDD-4):
        1. For each feature worktree (excluding the master itself), if its
           `docs/feature/<id>/feature-delta.md` source path exists, plan a
           ``copy`` to ``master/.nwave/in-flight/<id>.md``.
        2. For each existing mirror entry whose feature id has no matching
           feature worktree (merged, deleted, or never existed), plan a
           ``remove`` of the mirror file.

    Note: this function does NOT inspect file contents to detect "no-op
    copies" — that optimization belongs in the IO shell since reading file
    bytes is I/O. Idempotency is achieved at the apply step by writing the
    same bytes (overwrites are byte-identical when the source has not
    changed).

    Args:
        feature_worktrees: Records returned by `parse_worktree_porcelain`.
        master_path: Absolute path to the master repository root.
        existing_mirror_ids: Set of feature ids currently present under
            ``master_path / ".nwave" / "in-flight"`` (filenames without
            the trailing ``.md``).

    Returns:
        Ordered list of `SyncOp`s: copies first (deterministic by feature
        id), then removes (deterministic by feature id).
    """
    in_flight_dir = master_path / ".nwave" / "in-flight"

    # Skip the master record itself; it cannot host an in-flight feature.
    candidate_records = [
        wt for wt in feature_worktrees if not _is_master_worktree(wt, master_path)
    ]

    copies: list[SyncOp] = []
    seen_feature_ids: set[str] = set()
    for record in sorted(candidate_records, key=lambda wt: wt.feature_id):
        feature_id = record.feature_id
        if feature_id in seen_feature_ids:
            # Two worktrees of the same feature; pick the lexicographically
            # earlier path deterministically. Already first in the sort, so
            # subsequent duplicates are skipped.
            continue
        seen_feature_ids.add(feature_id)

        source = (
            record.worktree_path / "docs" / "feature" / feature_id / "feature-delta.md"
        )
        target = in_flight_dir / f"{feature_id}.md"
        copies.append(
            SyncOp(
                op_type="copy",
                feature_id=feature_id,
                source_path=source,
                target_path=target,
            )
        )

    # Stale entries: present in the mirror but no longer associated with a
    # live feature worktree.
    stale_ids = sorted(existing_mirror_ids - seen_feature_ids)
    removes: list[SyncOp] = [
        SyncOp(
            op_type="remove",
            feature_id=feature_id,
            source_path=in_flight_dir / f"{feature_id}.md",
            target_path=in_flight_dir / f"{feature_id}.md",
        )
        for feature_id in stale_ids
    ]

    return copies + removes


# ---------------------------------------------------------------------------
# IO shell — enumerates worktrees, lists mirror files, applies ops.
# ---------------------------------------------------------------------------


def _enumerate_worktrees(master_path: Path) -> list[WorktreeRecord]:
    """Run `git worktree list --porcelain` against ``master_path`` and parse.

    Subprocess timeout: 30s — well above the practical worktree-count budget
    while still capping a wedged git invocation.
    """
    completed = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=str(master_path),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        # Surface the git stderr verbatim — the caller's CLI shell turns this
        # into a non-zero exit code.
        raise RuntimeError(
            f"git worktree list failed (rc={completed.returncode}): "
            f"{completed.stderr.strip()}"
        )
    return parse_worktree_porcelain(completed.stdout)


def _existing_mirror_ids(master_path: Path) -> set[str]:
    """List feature ids currently present in the in-flight mirror."""
    in_flight_dir = master_path / ".nwave" / "in-flight"
    if not in_flight_dir.is_dir():
        return set()
    return {
        path.stem
        for path in in_flight_dir.iterdir()
        if path.is_file() and path.suffix == ".md"
    }


def _apply_op(op: SyncOp, *, log_lines: list[str]) -> None:
    """Apply one `SyncOp` against the real filesystem.

    Logs one informational line per op into ``log_lines`` so the caller can
    render them to stdout (matches the AC for "Marco sees an informational
    line announcing the mirror cleanup").
    """
    if op.op_type == "copy":
        if not op.source_path.is_file():
            # Worktree exists but has no feature-delta yet (early-stage
            # feature). Skip silently — re-syncing will pick it up.
            return
        op.target_path.parent.mkdir(parents=True, exist_ok=True)
        op.target_path.write_bytes(op.source_path.read_bytes())
        log_lines.append(f"sync: mirrored {op.feature_id} -> {op.target_path}")
        return

    if op.op_type == "remove":
        if op.target_path.exists():
            op.target_path.unlink()
            log_lines.append(
                f"sync: removed stale mirror entry {op.feature_id} "
                f"({op.target_path.name})"
            )
        return


def sync_in_flight(master_path: Path) -> tuple[list[SyncOp], list[str]]:
    """Synchronize the in-flight mirror under ``master_path``.

    Args:
        master_path: Master worktree repository root.

    Returns:
        A tuple ``(applied_ops, log_lines)`` where ``applied_ops`` is the
        exact plan that was executed (informational; exposed for tests) and
        ``log_lines`` are human-readable info messages produced during the
        run (one per real change; empty when nothing changed).
    """
    feature_worktrees = _enumerate_worktrees(master_path)
    existing = _existing_mirror_ids(master_path)
    plan = compute_sync_plan(feature_worktrees, master_path, existing)

    log_lines: list[str] = []
    for op in plan:
        _apply_op(op, log_lines=log_lines)

    return plan, log_lines


def run_sync(repo_root: Path) -> int:
    """CLI-callable entry: sync, render log lines, return exit code.

    Args:
        repo_root: Master worktree repository root.

    Returns:
        ``0`` on success. Non-zero only on a hard git/IO failure (which
        currently surface as exceptions; this function lets them propagate
        for the test harness to inspect rather than swallowing them).
    """
    _, log_lines = sync_in_flight(repo_root)
    for line in log_lines:
        print(line)
    return 0


def main() -> int:
    """CLI entry point for `nwave-ai sync`.

    Determines the master repository by running `git rev-parse --show-toplevel`
    from the current working directory.
    """
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if completed.returncode != 0:
        print(
            f"nwave-ai sync: not inside a git repository ({completed.stderr.strip()})",
            file=sys.stderr,
        )
        return 1
    repo_root = Path(completed.stdout.strip())
    return run_sync(repo_root)


if __name__ == "__main__":
    raise SystemExit(main())
