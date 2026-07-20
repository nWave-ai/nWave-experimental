"""Composition root + shared fixtures for parallel-work-cleans-up-after-merge-back
slice-01 (the walking skeleton -- charter
`a-finished-parallel-unit-of-works-worktree-disappears-on-its-own.md`,
feature-delta Slice Plan row slice-01, Locked Decisions D-2/D-3, ADR-SWARM-002).

Pillar 3 (App as in production): the SUT is the REAL `des verify-worktree-cleanup`
driving surface -- driven via the SAME production `des.cli.__main__` dispatcher
`tests/common/in_process_cli.py:run_cli_in_process` uses in-process for every
scenario except the feature's SINGLE `@walking_skeleton`, which forks the REAL
installed `des` console-script (mirrors the `blast-radius-measured-tier`
slice-01 precedent verbatim). This module NEVER imports
`des.cli.verify_worktree_cleanup` directly (P1 -- the module does not exist
yet; a top-level import would BREAK collection). The absent subcommand
surfaces as a RUNTIME dispatcher error ("invalid choice") inside the call,
never a collection-time ImportError (P1-P4, `nw-distill-red-scaffolding`).

-- D-1 REUSE, not rebuild --
`GitWorktreePort` / `GitWorktreeAdapter` (`des-refactor-fixer-swarm`,
ADR-SWARM-001) are SHIPPED and reused HERE as fixture substrate -- NOT the
SUT -- to build a realistic worktree + a realistic confirmed merge-back:
`create_worktree_from_tip` cuts the linked worktree, `merge_into` performs the
SAME merge-back mechanism `RefactorDrainService` uses. Building state through
the real adapter (rather than hand-rolled git plumbing) means the "confirmed
merged" precondition is genuinely git-state-true, not asserted by fixture
fiat -- the exact discipline D-D2 (state-based, never signal-based) demands
of the classifier this slice ships.

-- THE OBSERVABLE OUTCOME (Mandate 8 Universe) --
Every `CleanupSweepOutcome` field is re-derived from REAL git state
(`git worktree list --porcelain`) and the REAL `AtCompletionLedger` JSONL,
independent of whether the not-yet-existing CLI produces a parseable JSON
payload -- so the RED reason is genuine missing business behaviour, never a
parsing artifact.

Layer 3 (real git repo + real ledger JSONL + one real subprocess fork for the
walking skeleton, @real-io): example-only (Mandate 9 v2). No PBT machinery
imported -- sad paths enumerated explicitly (Mandate 11).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Precondition-substrate + observation reader (NOT the SUT) -- the SAME
# singleton-shape ledger the shipped feature-end machinery writes to.
from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

# SHIPPED worktree-lifecycle adapter (D-1 reuse) -- fixture substrate only,
# builds realistic worktrees + a realistic confirmed merge-back. NEVER the
# SUT (the SUT is the not-yet-existing `verify-worktree-cleanup` CLI).
from des.adapters.driven.refactor.git_worktree_adapter import GitWorktreeAdapter
from tests.common.in_process_cli import run_cli_in_process

from .steps.domain_types_slice_01 import CleanupSweepOutcome


_TARGET_BRANCH = "trunk"
_FEATURE_END_PENDING_EVENT = "FeatureEndPending"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout


def _venv_des_cmd() -> list[str]:
    """The `des` console-script belonging to the CURRENTLY-RUNNING Python
    environment -- derived from `sys.executable`, never PATH. A stale
    global `des` shim (an older nWave install missing this feature's
    subcommand) is immune to shadowing this way, unlike `shutil.which`."""
    venv_des = Path(sys.executable).parent / "des"
    if venv_des.exists():
        return [str(venv_des)]
    return [sys.executable, "-m", "des.cli.__main__"]


def _last_json_line(stdout: str) -> dict | None:
    """The last `{...}`-shaped stdout line, parsed, or `None` if absent.

    Mirrors the `_last_json_line` precedent in
    `blast_radius_measured_tier/test_blast_radius_slice01_walking_skeleton.py`
    -- today's dispatcher error ("invalid choice") lands on stderr with no
    JSON stdout line at all, so `None` is the honest, expected RED reading.
    """
    json_lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    if not json_lines:
        return None
    return json.loads(json_lines[-1])


class WorktreeCleanupFixture:
    """Composition-root service for parallel-work-cleans-up-after-merge-back
    slice-01 ATs.

    Pillar 3: builds a real trunk repo under `tmp_path`, cuts real linked
    worktrees via the SHIPPED `GitWorktreeAdapter`, optionally confirms a
    real merge-back, fires the SAME `des` driving surface production code
    will use, and observes the outcome from REAL git state + the REAL
    AT-completion ledger.

    Mandate-12 criterion 3: every public method is the SSOT for one piece of
    business logic. Step bodies do a typed lookup + one method call; nothing
    more.
    """

    def __init__(self, tmp_path: Path) -> None:
        self._repo = tmp_path / "trunk-repo"
        self._adapter = GitWorktreeAdapter()
        self._worktree_paths: dict[str, Path] = {}

    # --- repo + worktree provisioning --------------------------------------

    def build_trunk_repo(self) -> None:
        """Lay out a real trunk repo with a deterministic `trunk` branch name
        (never relies on the host's `init.defaultBranch` config)."""
        self._repo.mkdir(parents=True, exist_ok=True)
        _git(self._repo, "init", "-q")
        _git(self._repo, "config", "user.email", "cleanup-slice01@example.test")
        _git(self._repo, "config", "user.name", "Cleanup Slice 01 AT")
        (self._repo / "README.md").write_text("trunk seed\n", encoding="utf-8")
        _git(self._repo, "add", "README.md")
        _git(self._repo, "commit", "-q", "-m", "chore: seed trunk")
        _git(self._repo, "branch", "-m", _TARGET_BRANCH)

    def create_linked_worktree(self, name: str) -> None:
        """Cut a real linked worktree from trunk's tip (D-1 reuse) with one
        committed change on its own branch."""
        path = self._repo.parent / f"trunk-repo-{name}"
        self._adapter.create_worktree_from_tip(self._repo, name, path)
        (path / f"{name}.py").write_text(f"# work: {name}\n", encoding="utf-8")
        _git(path, "add", "-A")
        _git(path, "commit", "-q", "-m", f"feat: {name} work")
        self._worktree_paths[name] = path

    def create_detached_worktree(self, name: str) -> None:
        """Cut a real DETACHED-HEAD linked worktree (`git worktree add
        --detach`) from trunk's tip -- no branch line in the porcelain
        output. Regression fixture (detached-worktree-excluded-from-
        cleanup-sweep bugfix): the scan's most common real shape."""
        path = self._repo.parent / f"trunk-repo-{name}"
        _git(self._repo, "worktree", "add", "--detach", str(path), _TARGET_BRANCH)
        (path / f"{name}.py").write_text(f"# work: {name}\n", encoding="utf-8")
        _git(path, "add", "-A")
        _git(path, "commit", "-q", "-m", f"feat: {name} work")
        self._worktree_paths[name] = path

    def confirm_merge_back_detached(self, name: str) -> None:
        """Merge a detached worktree's HEAD sha directly into trunk -- no
        branch to merge from, so this confirms via `head_sha` ancestry
        (the classifier's actual state-based mechanism, D-D2), never
        branch presence."""
        head_sha = _git(self._worktree_paths[name], "rev-parse", "HEAD").strip()
        _git(self._repo, "merge", "-q", "--no-edit", head_sha)

    def confirm_merge_back(self, name: str) -> None:
        """Perform a REAL merge-back of `name`'s branch into the trunk
        target branch (D-1 reuse, the SAME `merge_into` mechanism
        `RefactorDrainService` uses) -- the state-based "confirmed merged"
        precondition D-D2 demands, never asserted by fixture fiat."""
        result = self._adapter.merge_into(
            self._repo, integration_branch=_TARGET_BRANCH, source_branch=name
        )
        assert result.merged, (
            f"fixture setup failed to merge {name!r} back into "
            f"{_TARGET_BRANCH!r}: {result.blocked_reason}"
        )

    # --- real-git observation (independent of the payload) -----------------

    def registered_worktree_paths(self) -> set[str]:
        output = _git(self._repo, "worktree", "list", "--porcelain")
        return {
            line[len("worktree ") :]
            for line in output.splitlines()
            if line.startswith("worktree ")
        }

    def _feature_end_pending_count(self) -> int:
        ledger = AtCompletionLedger(project_root=self._repo)
        try:
            records = ledger.read_records()
        except Exception:
            return 0
        return sum(1 for r in records if r.get("event") == _FEATURE_END_PENDING_EVENT)

    # --- driving-port invocation (the CLI under specification) -------------

    def run_sweep_in_process(
        self, *, check_only: bool = False, scope_to: str | None = None
    ) -> CleanupSweepOutcome:
        """Drive `verify-worktree-cleanup` IN-PROCESS through the SAME
        production `des` dispatcher (`des.cli.__main__.main`) every other
        `des <subcommand>` invocation goes through. `verify-worktree-cleanup`
        is not yet a registered subcommand (P1-P4): the dispatcher's own
        "invalid choice" argparse error is a RUNTIME failure inside this
        call, never a collection-time error."""
        argv = [
            "verify-worktree-cleanup",
            "--repo",
            str(self._repo),
            "--target-branch",
            _TARGET_BRANCH,
        ]
        if check_only:
            argv.append("--check-only")
        if scope_to is not None:
            argv += ["--worktree", str(self._worktree_paths[scope_to])]
        before_registered = self.registered_worktree_paths()
        before_pending = self._feature_end_pending_count()
        exit_code, stdout, _stderr = run_cli_in_process(argv, cwd=str(self._repo))
        return self._interpret(
            exit_code, stdout, before_registered, before_pending, scope_to
        )

    def run_sweep_subprocess(self, *, check_only: bool = False) -> CleanupSweepOutcome:
        """Drive `verify-worktree-cleanup` as a REAL, forked `des`
        console-script subprocess -- the feature's SINGLE `@walking_skeleton`
        scenario, proving the installed artifact is wired end-to-end.

        Env-fragility fix: a bare `shutil.which("des")` picks up WHATEVER
        `des` is first on PATH -- often a STALE global install predating
        this feature. Empirically confirmed the shared `resolve_des_cli_cmd`
        helper (`tests/cli_resolve.py`) does NOT catch this class: its
        `--help`-probes-cleanly check passes for a STALE-BUT-RUNNABLE global
        shim (it lacks `verify-worktree-cleanup` specifically, not `des`
        itself, so `--help` still exits 0). `_venv_des_cmd` instead resolves
        DETERMINISTICALLY from the ACTIVE Python environment (`sys.executable`'s
        own venv `bin/`), never consulting PATH at all -- immune to shadowing
        by any other installed `des`, stale or not."""
        argv = _venv_des_cmd() + [
            "verify-worktree-cleanup",
            "--repo",
            str(self._repo),
            "--target-branch",
            _TARGET_BRANCH,
        ]
        if check_only:
            argv.append("--check-only")
        before_registered = self.registered_worktree_paths()
        before_pending = self._feature_end_pending_count()
        completed = subprocess.run(argv, capture_output=True, text=True, check=False)
        return self._interpret(
            completed.returncode,
            completed.stdout,
            before_registered,
            before_pending,
            None,
        )

    def _interpret(
        self,
        exit_code: int,
        stdout: str,
        before_registered: set[str],
        before_pending: int,
        scope_to: str | None,
    ) -> CleanupSweepOutcome:
        payload = _last_json_line(stdout)
        after_registered = self.registered_worktree_paths()
        watched_path = (
            str(self._worktree_paths[scope_to])
            if scope_to is not None
            else (
                str(next(iter(self._worktree_paths.values())))
                if self._worktree_paths
                else None
            )
        )
        worktree_removed = bool(
            watched_path
            and watched_path in before_registered
            and watched_path not in after_registered
        )
        still_registered = bool(watched_path and watched_path in after_registered)
        entries = payload.get("entries", []) if payload else []
        has_what_why_how = bool(
            payload and all(k in payload for k in ("what", "why", "how"))
        )
        return CleanupSweepOutcome(
            exit_code=exit_code,
            event=payload.get("event") if payload else None,
            entry_count=len(entries),
            worktree_removed=worktree_removed,
            still_registered=still_registered,
            has_what_why_how=has_what_why_how,
            new_feature_end_pending_count=self._feature_end_pending_count()
            - before_pending,
        )


@pytest.fixture
def cleanup_fixture(tmp_path) -> WorktreeCleanupFixture:
    """The single composition-root service all slice-01 step methods delegate to."""
    return WorktreeCleanupFixture(tmp_path)


@pytest.fixture
def state_01() -> dict:
    """Per-scenario scratchpad: `outcome`, `before`."""
    return {}


__all__ = [
    "WorktreeCleanupFixture",
]
