"""Unit tests for the worktree anti-rot triage predicate.

`triage_worktree` IS the Sentinel's "worktree anti-rot triage" predicate
(`nWave/skills/nw-throughput/SKILL.md` "Throughput Sentinel"), made real. It
takes already-collected signals (never touches `/proc` or shells `git`
itself) and returns a `WorktreeAntiRotReceipt`. GDP-8 is the contract under
test -- a definitively-live signal classifies LIVE with named facts, and a
could-not-verify (`Indeterminate`) signal classifies INDETERMINATE, on its
own distinct footing, never silently dropped or collapsed into either
extreme. CLEAN requires ALL FOUR available signals to agree there is no
liveness AND no at-risk work -- convergent evidence, not a single signal.
"""

from __future__ import annotations

from des.domain.worktree_anti_rot_triage import (
    RECOMMENDED_ACTIONS,
    ProcessMatch,
    TriageState,
    triage_worktree,
)
from des.ports.driven_ports.committed_scope_port import Indeterminate


def _clean_signals():
    return {
        "process_matches": (),
        "locked": False,
        "dirty": False,
        "unmerged_commits": (),
    }


def test_clean_when_every_signal_is_definitively_clear() -> None:
    receipt = triage_worktree(target_path="/wt/lane", **_clean_signals())
    assert receipt.state is TriageState.CLEAN
    assert receipt.evidence == ()
    assert receipt.actions == ()


def test_live_on_process_naming_pid_and_cwd() -> None:
    signals = _clean_signals()
    signals["process_matches"] = (ProcessMatch(pid=4242, cwd="/wt/lane/sub"),)
    receipt = triage_worktree(target_path="/wt/lane", **signals)
    assert receipt.state is TriageState.LIVE
    finding = next(e for e in receipt.evidence if e.category == "pid")
    assert "4242" in finding.what
    assert "/wt/lane/sub" in finding.what


def test_live_on_explicit_lock() -> None:
    signals = _clean_signals()
    signals["locked"] = True
    receipt = triage_worktree(target_path="/wt/lane", **signals)
    assert receipt.state is TriageState.LIVE
    finding = next(e for e in receipt.evidence if e.category == "lock")
    assert "/wt/lane" in finding.what


def test_single_live_signal_is_sufficient_no_second_confirmation_needed() -> None:
    """Convergence binds declaring NO liveness, never the opposite direction:
    one strong live signal (a lock, with the process axis clean) must
    classify LIVE immediately -- withholding it pending a second confirming
    signal would repeat the exact failure this predicate closes."""
    signals = _clean_signals()
    signals["locked"] = True
    receipt = triage_worktree(target_path="/wt/lane", **signals)
    assert receipt.state is TriageState.LIVE


def test_abandoned_candidate_on_unintegrated_work_alone() -> None:
    signals = _clean_signals()
    signals["unmerged_commits"] = ("abc123 wip", "def456 more wip")
    receipt = triage_worktree(target_path="/wt/lane", **signals)
    assert receipt.state is TriageState.ABANDONED_CANDIDATE
    assert receipt.actions == RECOMMENDED_ACTIONS
    finding = next(e for e in receipt.evidence if e.category == "unintegrated-work")
    assert "abc123 wip" in finding.what
    assert "def456 more wip" in finding.what


def test_abandoned_candidate_on_dirty_state_alone() -> None:
    """Dirty state (uncommitted changes) is its OWN evidence category,
    distinct from unmerged COMMITS -- a fully-merged branch can still carry
    uncommitted work that would be destroyed outright."""
    signals = _clean_signals()
    signals["dirty"] = True
    receipt = triage_worktree(target_path="/wt/lane", **signals)
    assert receipt.state is TriageState.ABANDONED_CANDIDATE
    assert receipt.actions == RECOMMENDED_ACTIONS
    finding = next(e for e in receipt.evidence if e.category == "dirty-state")
    assert "/wt/lane" in finding.what


def test_process_indeterminate_and_no_live_finding_yields_indeterminate() -> None:
    signals = _clean_signals()
    signals["process_matches"] = Indeterminate("/proc is not available on this host")
    receipt = triage_worktree(target_path="/wt/lane", **signals)
    assert receipt.state is TriageState.INDETERMINATE
    finding = next(e for e in receipt.evidence if e.category == "pid-indeterminate")
    assert "/proc is not available" in finding.why


def test_lock_indeterminate_yields_indeterminate() -> None:
    signals = _clean_signals()
    signals["locked"] = Indeterminate("git worktree list failed")
    receipt = triage_worktree(target_path="/wt/lane", **signals)
    assert receipt.state is TriageState.INDETERMINATE
    assert any(e.category == "lock-indeterminate" for e in receipt.evidence)


def test_dirty_indeterminate_yields_indeterminate() -> None:
    signals = _clean_signals()
    signals["dirty"] = Indeterminate("git status failed")
    receipt = triage_worktree(target_path="/wt/lane", **signals)
    assert receipt.state is TriageState.INDETERMINATE
    assert any(e.category == "dirty-state-indeterminate" for e in receipt.evidence)


def test_unmerged_indeterminate_yields_indeterminate() -> None:
    signals = _clean_signals()
    signals["unmerged_commits"] = Indeterminate("target branch could not be resolved")
    receipt = triage_worktree(target_path="/wt/lane", **signals)
    assert receipt.state is TriageState.INDETERMINATE
    assert any(
        e.category == "unintegrated-work-indeterminate" for e in receipt.evidence
    )


def test_live_wins_over_indeterminate_when_both_present() -> None:
    """A DEFINITIVE live fact is stronger evidence than an unrelated
    could-not-verify -- the receipt reports what it KNOWS for certain
    (LIVE), not the weaker "could not fully verify everything" framing,
    while still surfacing the indeterminate finding in the evidence list
    (GDP-3: never withhold a computed fact)."""
    signals = _clean_signals()
    signals["locked"] = True
    signals["dirty"] = Indeterminate("git status failed")
    receipt = triage_worktree(target_path="/wt/lane", **signals)
    assert receipt.state is TriageState.LIVE
    categories = {e.category for e in receipt.evidence}
    assert categories == {"lock", "dirty-state-indeterminate"}


def test_multiple_findings_all_surface_together() -> None:
    """A receipt must not withhold a fact it already computed (GDP-3): two
    simultaneously-live findings both appear, not just the first."""
    signals = {
        "process_matches": (ProcessMatch(pid=1, cwd="/wt/lane"),),
        "locked": True,
        "dirty": False,
        "unmerged_commits": (),
    }
    receipt = triage_worktree(target_path="/wt/lane", **signals)
    assert receipt.state is TriageState.LIVE
    categories_seen = {e.category for e in receipt.evidence}
    assert categories_seen == {"pid", "lock"}


def test_abandoned_candidate_receipt_carries_a_how() -> None:
    signals = _clean_signals()
    signals["dirty"] = True
    receipt = triage_worktree(target_path="/wt/lane", **signals)
    assert "MERGE" in receipt.how
    assert "REMOVE" in receipt.how


def test_clean_receipt_carries_no_how() -> None:
    receipt = triage_worktree(target_path="/wt/lane", **_clean_signals())
    assert receipt.how == ""


def test_every_receipt_names_the_unavailable_evidence_categories() -> None:
    """Two spec-named evidence categories -- owner receipt and recent
    host-log activity -- are not yet mechanically available. Every receipt
    says so explicitly rather than silently omitting them (a reader must
    never mistake "not checked" for "checked and clear")."""
    receipt = triage_worktree(target_path="/wt/lane", **_clean_signals())
    assert "owner-receipt" in receipt.unavailable_evidence
    assert "recent-host-log-activity" in receipt.unavailable_evidence
