"""Composition-root extension for parallel-work-cleans-up-after-merge-back
slice-02 (an attempt to remove a worktree before its merge-back is confirmed
is refused -- charter
`removing-a-worktree-before-its-merge-is-confirmed-is-refused.md`,
feature-delta Slice Plan row slice-02, Locked Decision D-3, ADR-SWARM-002).

REUSES the SAME mechanism slice-01 introduces -- the SHIPPED
`des verify-worktree-cleanup` CLI, `WorktreeCleanupService`, and the
`is_ancestor` state check (feature-delta D-D4: "zero new plumbing"; Test
Reuse & Consolidation note: "slice-02 ... expected to reuse
WorktreeCleanupFixture ... rather than re-authoring a second trunk-repo
fixture builder"). `PrematureRemovalFixture` EXTENDS `WorktreeCleanupFixture`
(composition_slice_01.py) with two capabilities slice-01 never needed:

1. a real, direct-git commit-reachability observation (`commit_reachable`)
   -- the charter's own oracle explicitly names `git log` as the observation
   surface, independent of whatever the CLI's own JSON payload reports;
2. per-entry verdict extraction (`target_verdict`, via an `_interpret`
   override) -- the self-explaining "why" this slice's refusal names (D-D4:
   a NOT_YET_MERGEABLE entry is never removed; the verdict string itself is
   the message naming "not yet merged").

Never re-authors `build_trunk_repo` / `create_linked_worktree` / the git
subprocess seam -- all inherited verbatim from `WorktreeCleanupFixture`.
This module does NOT import or extend slice-01's Then-step bodies (see the
`.feature` file's header comment: those bodies pair a wide `SWEEP_UNIVERSE`
with an under-declared `expected` set, which makes every slice-01 Then-step
fail on `undeclared_change` regardless of production correctness --
confirmed empirically this pass, flagged to the team, not fixed here since
that file is mid-A_GREEND by another agent).
"""

from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from .composition_slice_01 import WorktreeCleanupFixture, _git, _last_json_line
from .steps.domain_types_slice_02 import PrematureRemovalOutcome


class PrematureRemovalFixture(WorktreeCleanupFixture):
    """Extends slice-01's fixture with the direct-git commit-reachability
    check + per-entry verdict extraction slice-02's refusal oracle needs.

    Pillar 3 unchanged: same real trunk repo, same SHIPPED `GitWorktreeAdapter`
    substrate, same production `des verify-worktree-cleanup` driving surface
    -- this slice differs ONLY in what it asserts about the SAME mechanism.
    """

    def _interpret(
        self,
        exit_code: int,
        stdout: str,
        before_registered: set[str],
        before_pending: int,
        scope_to: str | None,
    ) -> PrematureRemovalOutcome:
        base = super()._interpret(
            exit_code, stdout, before_registered, before_pending, scope_to
        )
        payload = _last_json_line(stdout)
        target_verdict: str | None = None
        has_reason = False
        if payload and scope_to is not None:
            watched_path = str(self._worktree_paths[scope_to])
            for entry in payload.get("entries", []):
                if entry.get("path") == watched_path:
                    target_verdict = entry.get("verdict")
                    has_reason = bool(entry.get("reason"))
                    break
        return PrematureRemovalOutcome(
            exit_code=base.exit_code,
            event=base.event,
            entry_count=base.entry_count,
            worktree_removed=base.worktree_removed,
            still_registered=base.still_registered,
            has_what_why_how=base.has_what_why_how,
            new_feature_end_pending_count=base.new_feature_end_pending_count,
            target_verdict=target_verdict,
            has_reason=has_reason,
            commit_reachable=None,
        )

    # --- direct-git observation (independent of the CLI's own payload) -----

    def sealed_commit_sha(self, name: str) -> str:
        """The real, CURRENT HEAD sha of the named worktree's own branch,
        read directly via git -- exactly the observation surface the
        charter names (`git log`)."""
        path = self._worktree_paths[name]
        return _git(path, "rev-parse", "HEAD").strip()

    def commit_reachable(self, sha: str) -> bool:
        """True iff `sha` is still a real, resolvable commit object in the
        repository -- the direct git-log-equivalent reachability check the
        charter's oracle demands, independent of whether the worktree
        registration itself still lists the path."""
        result = subprocess.run(
            ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
            cwd=self._repo,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    # --- driving-port invocation (the CLI under specification) -------------

    def check_cleanup_readiness(self, name: str) -> PrematureRemovalOutcome:
        """`--check-only`, scoped to ONE worktree -- the pure-read done-check
        persona action ("is this worktree ready for cleanup?")."""
        sha = self.sealed_commit_sha(name)
        outcome = self.run_sweep_in_process(check_only=True, scope_to=name)
        return replace(outcome, commit_reachable=self.commit_reachable(sha))

    def attempt_removal(self, name: str) -> PrematureRemovalOutcome:
        """ACT mode (default, no `--check-only`), scoped to ONE worktree --
        the concrete "attempt to remove/clean up the worktree" persona
        action the charter's Preconditions name."""
        sha = self.sealed_commit_sha(name)
        outcome = self.run_sweep_in_process(check_only=False, scope_to=name)
        return replace(outcome, commit_reachable=self.commit_reachable(sha))


@pytest.fixture
def cleanup_fixture(tmp_path: Path) -> PrematureRemovalFixture:
    """This slice's composition-root service -- the EXTENDED fixture, bound
    to the SAME `cleanup_fixture` name the reused Given step expects."""
    return PrematureRemovalFixture(tmp_path)


__all__ = ["PrematureRemovalFixture", "cleanup_fixture"]
