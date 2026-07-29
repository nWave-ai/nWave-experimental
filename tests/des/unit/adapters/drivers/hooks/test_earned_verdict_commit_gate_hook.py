"""Regression -- earned-verdict commit gate must not decide on DESIGNATION.

Hook-audit fix 2026-07-29 (GDP-8): ``evaluate_commit_gate`` used to rule a
``git commit`` by matching literal substrings ("a theater AT" / "all earned")
in the raw command TEXT, or by fabricating a hard-coded honest verdict the
instant a ``Slice-Id:`` trailer was present -- deciding on the commit's
DESIGNATION rather than the PROPERTY the gate exists to measure (whether the
slice's acceptance tests actually flip red when their dependency breaks). No
slice->AT->seam-manifest resolver exists to supply that property honestly
today, so the fixed gate always ABSTAINs (returns ``None``) on real commit
traffic instead of fabricating a decision.

The natural regression witness: two commits that carry the SAME real property
(neither has been perturb-loop-verified -- the gate has no way to know either
way) but DIFFERENT command text must receive IDENTICAL treatment. Before the
fix these two commands were ruled oppositely (one denied, one allowed) purely
because of which substring happened to appear in the message.
"""

from __future__ import annotations

from des.adapters.drivers.hooks.earned_verdict_commit_gate_hook import (
    evaluate_commit_gate,
    is_git_commit,
)


def test_theater_phrase_no_longer_flips_the_decision() -> None:
    """A commit whose message happens to contain the old trigger phrase.

    Pre-fix, this text alone fabricated a RED (block) verdict with no test ever
    re-run. Post-fix it must ABSTAIN like any other commit -- the gate cannot
    verify the property from text.
    """
    command = "git commit -m 'slice (a theater AT)'"
    assert is_git_commit(command)
    assert evaluate_commit_gate(command) is None


def test_all_earned_phrase_no_longer_flips_the_decision() -> None:
    """The opposite fixture phrase must be treated identically: ABSTAIN."""
    command = "git commit -m 'slice (all earned)'"
    assert is_git_commit(command)
    assert evaluate_commit_gate(command) is None


def test_real_slice_id_trailer_commit_no_longer_fabricates_earned() -> None:
    """A real slice commit (Slice-Id trailer, no fixture phrase) must ABSTAIN.

    Pre-fix, the mere presence of a ``Slice-Id:`` trailer -- which EVERY real
    slice commit carries by construction via ``des commit-slice`` -- was enough
    to fabricate a hard-coded GREEN/"earned" verdict, without a single test
    ever re-running. That is the most dangerous instance of the defect: it
    fired (silently, as a false ALLOW) on ordinary production traffic, not
    just on a contrived test phrase.
    """
    command = "git commit -m 'feat: real work\\n\\nSlice-Id: slice-07'"
    assert is_git_commit(command)
    assert evaluate_commit_gate(command) is None


def test_two_commits_same_unknown_property_different_text_get_same_verdict() -> None:
    """Two commits the gate cannot verify must not be discriminated by text.

    Neither command has been through a real perturb-loop, so both are equally
    UNKNOWN to the gate -- they must receive the identical (ABSTAIN) verdict.
    Pre-fix these two would have been ruled oppositely (denied vs. allowed)
    purely from which literal substring appeared in the message -- proof the
    old code decided on designation, not property.
    """
    theater_text = "git commit -m 'slice (a theater AT)'"
    earned_text = "git commit -m 'slice (all earned)'"
    assert evaluate_commit_gate(theater_text) == evaluate_commit_gate(earned_text)
    assert evaluate_commit_gate(theater_text) is None


def test_non_commit_bash_is_not_the_gates_concern() -> None:
    """A non-commit Bash command is not even recognised as a commit event."""
    assert is_git_commit("git status") is False
    assert is_git_commit("ls -la") is False
