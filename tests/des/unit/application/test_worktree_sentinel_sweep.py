"""Unit tests for the Sentinel's worktree sweep enumerator.

`sweep_worktrees` closes the GDP-1 gap named in `docs/mikado/EXECUTION-SSOT-
des-optimization.md` section SENTINEL: `triage_worktree` had exactly ONE
caller (the removal guard, which only fires when someone tries to remove a
worktree). This module is the periodic ENUMERATOR the Sentinel skill's prose
promised but nothing produced.

These tests are pure in-process fakes (no real git, no `/proc`) -- the fast,
deterministic layer that proves the ENUMERATION contract: every handle the
port returns gets exactly one entry, whatever state its receipt carries. The
"a live worktree must not be classified abandoned" claim itself is `triage_
worktree`'s OWN, already-tested contract (`tests/des/unit/domain/
test_worktree_anti_rot_triage.py`) -- reused here via the injected collector
stub rather than re-derived, per the reuse-first mandate this module itself
documents. A REAL end-to-end run through actual git + actual `/proc` lives in
`tests/hooks/test_worktree_removal_guard_end_to_end.py`'s sibling in
`tests/des/e2e/` (`test_worktree_sentinel_sweep_e2e.py`), which this module's
`collect_receipt` default wires into.
"""

from __future__ import annotations

from pathlib import Path

from des.application.worktree_sentinel_sweep import (
    sweep_worktrees,
)
from des.domain.worktree_anti_rot_triage import (
    EvidenceItem,
    TriageState,
    WorktreeAntiRotReceipt,
)
from des.ports.driven_ports.git_worktree_port import (
    GitWorktreePort,
    MergeResult,
    WorktreeHandle,
)


class _FakeGitWorktree(GitWorktreePort):
    """In-memory GitWorktreePort double -- answers `list_worktrees` from
    constructor state. Every method the sweep never calls raises loudly."""

    def __init__(self, handles: tuple[WorktreeHandle, ...]) -> None:
        self._handles = handles

    def list_worktrees(self, repo: Path) -> tuple[WorktreeHandle, ...]:
        return self._handles

    def probe(self, repo: Path) -> bool:  # pragma: no cover - unused by sweep
        raise NotImplementedError

    def create_worktree_from_tip(
        self, repo: Path, branch: str, path: Path
    ) -> WorktreeHandle:  # pragma: no cover - unused by sweep
        raise NotImplementedError

    def merge_into(
        self, repo: Path, integration_branch: str, source_branch: str
    ) -> MergeResult:  # pragma: no cover - unused by sweep
        raise NotImplementedError

    def remove_worktree(self, repo: Path, path: Path) -> None:  # pragma: no cover
        raise NotImplementedError

    def delete_branch(self, repo: Path, branch: str) -> None:  # pragma: no cover
        raise NotImplementedError

    def land_and_remove_integration(
        self, repo: Path, integration_branch: str
    ) -> bool:  # pragma: no cover - unused by sweep
        raise NotImplementedError

    def has_uncommitted_changes(
        self, repo: Path, path: Path
    ) -> bool:  # pragma: no cover - unused by sweep
        raise NotImplementedError


_REPO = Path("/fake/repo")

_LIVE_RECEIPT = WorktreeAntiRotReceipt(
    state=TriageState.LIVE,
    evidence=(
        EvidenceItem(category="pid", what="a live process is here", why="cwd match"),
    ),
    how="do not remove",
)
_CLEAN_RECEIPT = WorktreeAntiRotReceipt(state=TriageState.CLEAN)
_ABANDONED_RECEIPT = WorktreeAntiRotReceipt(
    state=TriageState.ABANDONED_CANDIDATE,
    evidence=(
        EvidenceItem(
            category="unintegrated-work", what="3 commits unmerged", why="at risk"
        ),
    ),
    actions=("MERGE", "RESUME", "DEFER", "REMOVE"),
    how="human picks one",
)
_INDETERMINATE_RECEIPT = WorktreeAntiRotReceipt(
    state=TriageState.INDETERMINATE,
    evidence=(
        EvidenceItem(
            category="pid-indeterminate", what="could not read /proc", why="no perm"
        ),
    ),
    how="fix the probe or get human authorisation",
)


def _receipts_by_path(
    receipts: dict[Path, WorktreeAntiRotReceipt],
):
    """A stub `collect_receipt` -- looks up a canned receipt by target_path,
    never touches `/proc` or git. Records every (repo, target_path,
    target_branch) call it received."""
    calls: list[tuple[Path, Path, str | None]] = []

    def _collect(
        repo: Path, target_path: Path, target_branch: str | None
    ) -> WorktreeAntiRotReceipt:
        calls.append((repo, target_path, target_branch))
        return receipts[target_path]

    _collect.calls = calls  # type: ignore[attr-defined]
    return _collect


def test_every_handle_gets_exactly_one_entry_no_dropping_no_collapsing() -> None:
    """GDP-8 arity corollary, the reason this module exists: a sweep across
    four worktrees in four DIFFERENT states must report all four, unchanged
    -- the defect this closes is an enumerator that silently filters states
    it finds inconvenient."""
    live_wt = Path("/fake/repo-wt-live")
    clean_wt = Path("/fake/repo-wt-clean")
    abandoned_wt = Path("/fake/repo-wt-abandoned")
    indeterminate_wt = Path("/fake/repo-wt-indeterminate")

    handles = (
        WorktreeHandle(path=live_wt, branch="lane-live", head_sha="a" * 40),
        WorktreeHandle(path=clean_wt, branch="lane-clean", head_sha="b" * 40),
        WorktreeHandle(path=abandoned_wt, branch="lane-abandoned", head_sha="c" * 40),
        WorktreeHandle(
            path=indeterminate_wt, branch="lane-indeterminate", head_sha="d" * 40
        ),
    )
    fake_port = _FakeGitWorktree(handles=handles)
    stub_collect = _receipts_by_path(
        {
            live_wt: _LIVE_RECEIPT,
            clean_wt: _CLEAN_RECEIPT,
            abandoned_wt: _ABANDONED_RECEIPT,
            indeterminate_wt: _INDETERMINATE_RECEIPT,
        }
    )

    report = sweep_worktrees(
        repo=_REPO,
        worktree_port=fake_port,
        target_branch="trunk",
        collect_receipt=stub_collect,
    )

    assert len(report.entries) == 4
    assert {entry.handle.path for entry in report.entries} == {
        live_wt,
        clean_wt,
        abandoned_wt,
        indeterminate_wt,
    }


def test_live_worktree_is_never_reported_as_abandoned() -> None:
    """The specific claim the dispatch demanded: a LIVE receipt must survive
    the sweep as LIVE, never silently reclassified or coerced toward
    ABANDONED_CANDIDATE by the enumeration layer."""
    live_wt = Path("/fake/repo-wt-live")
    handles = (WorktreeHandle(path=live_wt, branch="lane-live", head_sha="a" * 40),)
    fake_port = _FakeGitWorktree(handles=handles)
    stub_collect = _receipts_by_path({live_wt: _LIVE_RECEIPT})

    report = sweep_worktrees(
        repo=_REPO,
        worktree_port=fake_port,
        target_branch="trunk",
        collect_receipt=stub_collect,
    )

    (entry,) = report.entries
    assert entry.receipt.state is TriageState.LIVE
    assert entry.receipt.state is not TriageState.ABANDONED_CANDIDATE
    (live_entry,) = report.by_state(TriageState.LIVE)
    assert live_entry.handle.path == live_wt
    assert report.by_state(TriageState.ABANDONED_CANDIDATE) == ()


def test_an_indeterminate_signal_reaches_the_aggregate_as_its_own_state() -> None:
    """GDP-8 arity corollary: the third state must reach the AGGREGATE, not
    be collapsed at the edge into a confident CLEAN or ABANDONED_CANDIDATE
    verdict. This is the second explicit claim the dispatch demanded."""
    indeterminate_wt = Path("/fake/repo-wt-indeterminate")
    clean_wt = Path("/fake/repo-wt-clean")
    handles = (
        WorktreeHandle(
            path=indeterminate_wt, branch="lane-indeterminate", head_sha="a" * 40
        ),
        WorktreeHandle(path=clean_wt, branch="lane-clean", head_sha="b" * 40),
    )
    fake_port = _FakeGitWorktree(handles=handles)
    stub_collect = _receipts_by_path(
        {indeterminate_wt: _INDETERMINATE_RECEIPT, clean_wt: _CLEAN_RECEIPT}
    )

    report = sweep_worktrees(
        repo=_REPO,
        worktree_port=fake_port,
        target_branch="trunk",
        collect_receipt=stub_collect,
    )

    (indeterminate_entry,) = report.by_state(TriageState.INDETERMINATE)
    assert indeterminate_entry.handle.path == indeterminate_wt
    assert indeterminate_entry.receipt.state is not TriageState.CLEAN
    assert indeterminate_entry.receipt.state is not TriageState.ABANDONED_CANDIDATE
    # And it did NOT silently vanish from the total population either.
    assert len(report.entries) == 2


def test_target_branch_is_passed_through_unchanged_to_every_worktree() -> None:
    """The sweep asks 'unintegrated relative to WHAT' with ONE answer across
    the whole pass -- never a different reference branch per worktree."""
    wt_a = Path("/fake/repo-wt-a")
    wt_b = Path("/fake/repo-wt-b")
    handles = (
        WorktreeHandle(path=wt_a, branch="lane-a", head_sha="a" * 40),
        WorktreeHandle(path=wt_b, branch="lane-b", head_sha="b" * 40),
    )
    fake_port = _FakeGitWorktree(handles=handles)
    stub_collect = _receipts_by_path({wt_a: _CLEAN_RECEIPT, wt_b: _CLEAN_RECEIPT})

    sweep_worktrees(
        repo=_REPO,
        worktree_port=fake_port,
        target_branch="release/trunk",
        collect_receipt=stub_collect,
    )

    assert stub_collect.calls == [
        (_REPO, wt_a, "release/trunk"),
        (_REPO, wt_b, "release/trunk"),
    ]


def test_empty_worktree_set_produces_an_empty_report_not_an_error() -> None:
    fake_port = _FakeGitWorktree(handles=())
    report = sweep_worktrees(
        repo=_REPO,
        worktree_port=fake_port,
        target_branch="trunk",
        collect_receipt=_receipts_by_path({}),
    )
    assert report.entries == ()
