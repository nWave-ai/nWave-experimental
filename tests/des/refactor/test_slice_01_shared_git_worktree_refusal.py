"""Regression -- des refactor must NOT mutate a SHARED common .git.

Bug (F-REFACTOR-SUITE-REAL-GIT-DRAIN-LEAKS-ONTO-HOST-REPO): when the repo
``des refactor`` resolves (``main()``: ``repo = Path.cwd()``) is a LINKED
WORKTREE, every ``git worktree add`` / ``git branch`` / ``git checkout`` /
``git merge`` the real ``GitWorktreeAdapter`` runs targets the SHARED common
``.git`` -- creating ``refactor-probe-health-check`` / ``refactor-<id>`` /
``refactor-integration`` branches and moving HEAD in the operator's live repo
(empirically: it left ``refactor-probe-health-check`` on the host and tripped
the suite's own ``_git_pollution_guard`` with ``['HEAD','refs']`` corruption).

The fix intercepts at the EARLIEST point (the startup probe, before any
worktree is created -- GDP-1): a repo whose ``git rev-parse --git-common-dir``
differs from ``--git-dir`` is a linked worktree, and the drain refuses LOUD
(WHAT/WHY/HOW) instead of corrupting the shared refs.

Both tests are hermetic: Test A only runs read-only ``git rev-parse`` against a
synthetic repo built under ``tmp_path``; Test B drives the service with an
in-memory fake port and never spawns git at all. Neither ever exercises the
real worktree-mutating path against a linked worktree.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from des.adapters.driven.refactor.git_worktree_adapter import GitWorktreeAdapter
from des.application.refactor_drain_service import RefactorDrainService
from des.ports.driven_ports.git_worktree_port import (
    GitWorktreePort,
    MergeResult,
    WorktreeHandle,
)

from .composition import RefactorSwarmComposition


pytestmark = pytest.mark.acceptance


def _init_standalone_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@nwave.test"], cwd=root, check=True
    )
    subprocess.run(["git", "config", "user.name", "T"], cwd=root, check=True)
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=root, check=True)


def test_the_real_adapter_flags_a_linked_worktree_but_not_a_standalone_repo(tmp_path):
    """AT (adapter, read-only) -- ``is_linked_worktree`` is True for a linked
    worktree (whose ``--git-common-dir`` != ``--git-dir``, so its worktree ops
    hit a SHARED ``.git``) and False for a standalone checkout and a non-git
    directory. Uses only ``git rev-parse`` -- never a mutating worktree op.
    """
    host = tmp_path / "host"
    _init_standalone_repo(host)
    linked = tmp_path / "linked"
    subprocess.run(
        ["git", "worktree", "add", "-q", str(linked), "-b", "wtbranch"],
        cwd=host,
        check=True,
    )
    non_git = tmp_path / "plain"
    non_git.mkdir()

    adapter = GitWorktreeAdapter()

    assert adapter.is_linked_worktree(linked) is True, (
        "a linked worktree shares its common .git -- worktree/branch ops here "
        "corrupt the operator's other worktrees; it MUST be flagged"
    )
    assert adapter.is_linked_worktree(host) is False, (
        "a standalone main checkout owns its own .git -- it must NOT be flagged"
    )
    assert adapter.is_linked_worktree(non_git) is False, (
        "a non-git directory is not a linked worktree (the existing git-repo "
        "probe handles that case) -- it must not be flagged here"
    )


class _RecordingGitWorktree(GitWorktreePort):
    """In-memory fake: reports a linked worktree and records whether any
    mutating op was reached (it must NOT be, per GDP-1 intercept-early)."""

    def __init__(self, *, linked: bool) -> None:
        self._linked = linked
        self.probe_called = False
        self.create_called = False

    def is_linked_worktree(self, repo: Path) -> bool:
        return self._linked

    def probe(self, repo: Path) -> bool:  # pragma: no cover - guarded against
        self.probe_called = True
        return True

    def create_worktree_from_tip(
        self, repo: Path, branch: str, path: Path
    ) -> WorktreeHandle:  # pragma: no cover - must never be reached
        self.create_called = True
        raise AssertionError("create_worktree_from_tip reached on a linked worktree")

    def merge_into(
        self, repo: Path, integration_branch: str, source_branch: str
    ) -> MergeResult:  # pragma: no cover
        raise AssertionError("merge_into reached on a linked worktree")

    def has_uncommitted_changes(
        self, repo: Path, path: Path
    ) -> bool:  # pragma: no cover - must never be reached
        raise AssertionError("has_uncommitted_changes reached on a linked worktree")

    def remove_worktree(self, repo: Path, path: Path) -> None:  # pragma: no cover
        raise AssertionError("remove_worktree reached on a linked worktree")

    def delete_branch(self, repo: Path, branch: str) -> None:  # pragma: no cover
        raise AssertionError("delete_branch reached on a linked worktree")

    def land_and_remove_integration(
        self, repo: Path, integration_branch: str
    ) -> bool:  # pragma: no cover
        raise AssertionError("land_and_remove_integration reached on a linked worktree")

    def list_worktrees(
        self, repo: Path
    ) -> tuple[WorktreeHandle, ...]:  # pragma: no cover
        return ()


class _UnusedPort:
    """Any attribute access proves the drain went past the linked-worktree
    refusal, which it must not."""

    def __getattr__(self, name):  # pragma: no cover - guarded against
        raise AssertionError(f"a downstream port ({name}) was reached after refusal")


def test_a_drain_on_a_linked_worktree_refuses_before_creating_any_worktree(tmp_path):
    """AT (service, no real git) -- Given the target repo is a linked worktree,
    When ``drain_one`` runs, Then it refuses LOUD naming WHAT/WHY/HOW and never
    reaches ``create_worktree_from_tip`` (nor any other worktree op) -- the
    shared common ``.git`` is never touched. GDP-1: intercept at the earliest
    point, before the effort is spent.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.seed_pile_item(item_id="TD-001")
    git_worktree = _RecordingGitWorktree(linked=True)
    service = RefactorDrainService(
        git_worktree=git_worktree,
        agent_invocation=_UnusedPort(),
        env_provision=_UnusedPort(),
        impacted_test_selector=_UnusedPort(),
        ledger=_UnusedPort(),
    )

    result = service.drain_one(
        repo=tmp_path,
        pile_path=composition.pile_path,
        paid_path=composition.paid_path,
        agent_cmd="true",
        integration_branch="refactor-integration",
    )

    assert result.drained is False, "a linked-worktree target must never drain"
    assert result.merged is False
    assert git_worktree.create_called is False, (
        "the refusal must fire BEFORE any worktree is created (GDP-1)"
    )
    assert git_worktree.probe_called is False, (
        "the linked-worktree check must precede the worktree probe -- the probe "
        "itself creates a throwaway worktree in the SHARED .git"
    )
    reason = (result.reason or "").lower()
    assert "linked worktree" in reason, (
        f"the refusal must name WHAT failed (a linked worktree); got: {result.reason!r}"
    )
    assert "shared" in reason or "common" in reason, (
        f"the refusal must name WHY (shared/common .git corruption); got: {result.reason!r}"
    )
    assert "main checkout" in reason or "standalone" in reason, (
        f"the refusal must name HOW to fix it (run from the main checkout / a "
        f"standalone clone); got: {result.reason!r}"
    )
