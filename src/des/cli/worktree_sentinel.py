"""`des sentinel` -- the Throughput Sentinel's worktree-triage receipt.

lane/sentinel-tool (team-lead dispatch 2026-07-30). Promotes the Sentinel
from an unversioned scratchpad script into a tested, versioned `des`
subcommand -- spec: `nWave/skills/nw-throughput/SKILL.md`, section
"Throughput Sentinel". An instrument consulted before every scheduling
decision is production code, not a scratch script; a defect in it is a
defect in every decision downstream (three wrong readings in one afternoon
from the scratchpad version, each costing real work -- see
`des.domain.worktree_sentinel_verdict` for the three defects and their
fixes).

REUSE, NOT REINVENTION (GDP-4). This CLI is thin wiring over already-built,
already-tested pieces:
  - `sweep_worktrees` + `GitWorktreeAdapter` -- the population (2026-07-29,
    already production).
  - `classify_sentinel` -- the OWNED/ABANDONED_CANDIDATE/UNDECIDABLE
    predicate, composing the reused anti-rot receipt with the two axes this
    lane adds (declared ownership, recent activity).
  - `read_capacity_snapshot` -- nproc/load/MemAvailable/real-pytest-count.

ADVISORY, GDP-6: this command NEVER removes, merges, dispatches, or
authorizes anything. It always exits 0 when the sweep itself ran (whatever
the individual verdicts say -- INFORMING is its whole job); it exits
non-zero only when the sweep could not run at all (no receipt possible),
never as a soft "some worktree looks abandoned" signal a caller might
mistake for a gate.

SELF-PROBE ORDERING, FOUND ON CONTACT (beyond the three named defects):
`git status --porcelain` -- which the reused anti-rot collector runs to
read the dirty-state axis -- REWRITES the on-disk `.git/index` file as a
side effect (git's own racy-index protection re-stats and re-serializes
it), which resets the index's mtime to "now". Reading activity age AFTER
the triage probes ran would therefore make the SENTINEL'S OWN dirty-state
check masquerade as fresh developer activity on every single invocation --
a self-inflicted false-OWNED on every genuinely abandoned worktree the tool
ever inspects. `main` below reads every worktree's activity age FIRST, in
one pass, strictly before `sweep_worktrees` runs any git probe against any
of them.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from des.adapters.driven.refactor.git_worktree_adapter import GitWorktreeAdapter
from des.application.capacity_snapshot import read_capacity_snapshot
from des.application.worktree_activity_signal import (
    qualified_name,
    read_activity_age_seconds,
    resolve_declared_ownership,
)
from des.application.worktree_sentinel_sweep import sweep_worktrees
from des.application.worktree_triage_collector import (
    collect_worktree_triage_receipt,
    resolve_target_branch,
)
from des.cli._emit_json import emit_json_line as _emit
from des.cli._repo_root_arg import add_repo_root_argument
from des.cli.human_surface import Verdict, print_human_summary
from des.domain.worktree_sentinel_verdict import SentinelState, classify_sentinel
from des.ports.driven_ports.committed_scope_port import Indeterminate


_MARKER_RELATIVE_PATH = Path(".nwave") / "lane-owner.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des sentinel",
        description=(
            "Read-only worktree-triage receipt: classifies every linked "
            "worktree OWNED / ABANDONED_CANDIDATE / UNDECIDABLE, offers "
            "MERGE/RESUME/DEFER/REMOVE for a candidate, and snapshots host "
            "capacity. Never mutates, merges, removes, or dispatches."
        ),
    )
    add_repo_root_argument(
        parser, "--repo", default=".", help="Path to the repository root."
    )
    parser.add_argument(
        "--owned",
        action="append",
        default=[],
        metavar="NAME[,NAME...]",
        help=(
            "Comma-separated lane names the orchestrator has dispatched and "
            "not yet released -- a manual fallback for worktrees not yet "
            "carrying a `.nwave/lane-owner.json` marker. Matched against "
            "both the qualified name (`parent/basename`) and the "
            "normalized bare name (`wt-`/`nWave-dev-`-prefix-insensitive)."
        ),
    )
    parser.add_argument(
        "--target-branch",
        default=None,
        help=(
            "Reference branch the unintegrated-work axis compares against. "
            "Defaults to the repo's current branch; pass explicitly when "
            "invoking from a worktree other than trunk."
        ),
    )
    return parser


def _owned_tokens(raw: list[str]) -> frozenset[str]:
    tokens: set[str] = set()
    for group in raw:
        tokens.update(t.strip() for t in group.split(",") if t.strip())
    return frozenset(tokens)


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    repo = Path(args.repo).resolve()
    owned_tokens = _owned_tokens(args.owned)
    target_branch = args.target_branch or resolve_target_branch(repo)
    worktree_port = GitWorktreeAdapter()

    try:
        # Read activity age for EVERY worktree BEFORE any triage probe runs
        # against any of them (see module docstring: `git status` rewrites
        # the index mtime as a side effect, which would otherwise make the
        # Sentinel's own dirty-state probe masquerade as fresh activity).
        handles = worktree_port.list_worktrees(repo)
        activity_by_path = {
            handle.path: read_activity_age_seconds(handle.path) for handle in handles
        }

        report = sweep_worktrees(
            repo=repo,
            worktree_port=worktree_port,
            target_branch=target_branch,
            collect_receipt=collect_worktree_triage_receipt,
        )
    except OSError as exc:
        failure_payload: dict[str, object] = {
            "event": "WorktreeSentinelSweepFailed",
            "reason": str(exc),
        }
        _emit(failure_payload)
        print_human_summary(
            Verdict.INDETERMINATE,
            "worktree sentinel could not enumerate worktrees",
            why=str(exc),
            how="verify `git worktree list --porcelain` runs cleanly against "
            f"{repo}, then re-run `des sentinel`.",
        )
        return 1

    rows: list[dict[str, object]] = []
    for entry in report.entries:
        path = entry.handle.path
        marker_present = (path / _MARKER_RELATIVE_PATH).is_file()
        declared_owned, declared_how = resolve_declared_ownership(
            path=path, owned_tokens=owned_tokens, marker_present=marker_present
        )
        activity_age = activity_by_path.get(
            path, Indeterminate(f"{path} was not in the pre-sweep activity pass")
        )
        verdict = classify_sentinel(
            declared_owned=declared_owned,
            declared_how=declared_how,
            anti_rot=entry.receipt,
            activity_age_seconds=activity_age,
        )
        rows.append(
            {
                "path": str(path),
                "name": qualified_name(path),
                "branch": entry.handle.branch,
                "state": verdict.state.value,
                "offers": list(verdict.offers),
                "how": verdict.how,
                "evidence": [
                    {"category": e.category, "what": e.what, "why": e.why}
                    for e in verdict.evidence
                ],
                "activity_age_seconds": (
                    None if isinstance(activity_age, Indeterminate) else activity_age
                ),
            }
        )

    capacity = read_capacity_snapshot()
    capacity_payload: dict[str, object] = {
        "nproc": (
            None if isinstance(capacity.nproc, Indeterminate) else capacity.nproc
        ),
        "load_avg": (
            None
            if isinstance(capacity.load_avg, Indeterminate)
            else list(capacity.load_avg)
        ),
        "mem_available_kb": (
            None
            if isinstance(capacity.mem_available_kb, Indeterminate)
            else capacity.mem_available_kb
        ),
        "real_pytest_count": (
            None
            if isinstance(capacity.real_pytest_count, Indeterminate)
            else capacity.real_pytest_count
        ),
    }

    payload: dict[str, object] = {
        "event": "WorktreeSentinelReport",
        "target_branch": target_branch,
        "capacity": capacity_payload,
        "worktrees": rows,
    }
    _emit(payload)

    candidates = [
        r for r in rows if r["state"] == SentinelState.ABANDONED_CANDIDATE.value
    ]
    undecidable = [r for r in rows if r["state"] == SentinelState.UNDECIDABLE.value]
    overall_verdict: Verdict
    if candidates:
        overall_verdict = Verdict.DEGRADED
        why = (
            f"{len(candidates)} worktree(s) are ABANDONED_CANDIDATE: "
            f"{', '.join(str(r['name']) for r in candidates)}"
        )
    elif undecidable:
        overall_verdict = Verdict.INDETERMINATE
        why = (
            f"{len(undecidable)} worktree(s) could not be classified: "
            f"{', '.join(str(r['name']) for r in undecidable)}"
        )
    else:
        overall_verdict = Verdict.PASS
        why = f"{len(rows)} worktree(s) triaged, none abandoned or undecidable"
    print_human_summary(
        overall_verdict,
        "worktree sentinel sweep complete",
        why=why,
        how="a candidate offers exactly MERGE/RESUME/DEFER/REMOVE in the JSON "
        "payload's `offers` field -- a human picks one; this command never "
        "removes anything itself.",
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
