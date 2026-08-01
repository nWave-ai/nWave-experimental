"""Regression: the Sentinel's activity axis must never read an observable its
own dirty-state probe writes.

Mikado node D85 (`docs/feature/fix-sentinel-activity-self-contamination/feature-delta.md`).
`read_activity_age_seconds` (`src/des/application/worktree_activity_signal.py:147-189`)
currently returns `min(age(.git/HEAD), age(.git/index))`. Measured (feature-delta
§Problem & Root Causes, reproduced again here on contact) that `git status
--porcelain` -- which the Sentinel's own dirty-state axis runs on every sweep --
REWRITES `.git/index`'s mtime as a side effect, and leaves `.git/HEAD`
untouched. Because `min` takes the YOUNGEST reading, the instrument's own write
always dominates: a worktree abandoned for days reads as zero seconds old the
moment ANY prior sweep has probed it, and with a measured invocation rate of
2.59 runs/hour (all four consecutive gaps inside the 3600s recency window) the
blindness is CONTINUOUS, not occasional.

Chosen repair (D85-1): drop `.git/index` from the axis, read `HEAD` alone --
no probe the Sentinel runs writes `HEAD` (measured in the table below).

No `docs/feature/fix-sentinel-activity-self-contamination/distill/
requirement-checklist.md` exists for this feature (checked on contact) -- the
covers-markers below cite the feature-delta's own Decision ids (D85-1..D85-4)
and Definition-of-Done bullets instead of inventing requirement ids.

|   command                                | HEAD      | index         |
|-------------------------------------------|-----------|---------------|
| `git rev-parse --abbrev-ref HEAD`          | untouched | untouched     |
| `git worktree list --porcelain`            | untouched | untouched     |
| `git status --porcelain`                   | untouched | reset to now  |

Driving surface (Mandate-16 driving-port-only): `read_activity_age_seconds`
and `classify_sentinel` ARE the application/domain production entry points
under regression -- the established precedent this file follows is
`tests/bugs/des/test_cargo_digest_reuses_worktree_target_dir.py` (real `git`
subprocess against real fixture repos, no CLI wrapping needed for a
function-level defect whose fix is entirely inside these two functions). No
`@walking_skeleton` subprocess-E2E is added: this is the `/nw-bugfix`
pytest-regression path (`nw-acceptance-designer`'s own "Mechanical Seal"
contract) -- the regression tests ARE the slice's ATs, cleared by
`des verify-red-green --record-red` + `des verify-negative-at --all-critical`
rather than a Gherkin walking skeleton.

CI-safe: real `git init` / `git commit` / `git status` subprocess calls
against throwaway `tmp_path` repos -- no network, no shared state, fast
(sub-second per case).
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from des.application.worktree_activity_signal import read_activity_age_seconds
from des.domain.worktree_anti_rot_triage import TriageState, WorktreeAntiRotReceipt
from des.domain.worktree_sentinel_verdict import SentinelState, classify_sentinel
from des.ports.driven_ports.committed_scope_port import Indeterminate


def _real_git_repo(tmp_path: Path) -> Path:
    """A real, throwaway git repository -- `git init` + one commit -- so
    `git status --porcelain` exercises the REAL racy-index re-stat that no
    `utime`-only fixture (the existing `_write_gitdir` helper in
    `tests/des/unit/application/test_worktree_activity_signal.py`) can ever
    observe. This is the discriminating fixture shape the feature-delta's
    Reuse Analysis names as the reason this file is CREATE_NEW rather than
    an extension of that helper."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.example"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "f.txt").write_text("hi\n", encoding="utf-8")
    subprocess.run(["git", "add", "f.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
    return repo


def _age_baseline_seconds(repo: Path, *, seconds_old: float) -> float:
    """Baseline both `.git/HEAD` and `.git/index` to `seconds_old` in the
    past, and return the `now` this baseline was computed against so callers
    assert against the SAME clock reading rather than re-sampling `time.time()`
    a second time (which would itself add slack the assertions must tolerate)."""
    now = time.time()
    old = now - seconds_old
    os.utime(repo / ".git" / "HEAD", (old, old))
    os.utime(repo / ".git" / "index", (old, old))
    return now


# ---------------------------------------------------------------------------
# Discriminator 1 -- a real `git status`, then a re-read, must not erase age.
# covers: D85-1, D85-3, Architecture & Contract Tests bullet 1
# ---------------------------------------------------------------------------
def test_real_git_status_probe_does_not_reset_the_reported_activity_age(
    tmp_path: Path,
) -> None:
    """The exact counterexample the feature-delta measured: baseline HEAD and
    index to 2 days old, run a REAL `git status --porcelain` (the Sentinel's
    own dirty-state probe), then re-read the activity age. A `utime`-only
    fixture can never express this defect -- only a real git write does.
    RED against the pre-fix `min(HEAD, index)` axis: `git status` resets
    `index` to ~0s old, and `min` picks that."""
    repo = _real_git_repo(tmp_path)
    _age_baseline_seconds(repo, seconds_old=2 * 86400)

    subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True)

    age = read_activity_age_seconds(repo, now=time.time())

    assert isinstance(age, int)
    # HEAD was never touched by `git status`; the true age is ~2 days, not
    # reset to ~0 by the index write. Generous slack (1 hour) absorbs test
    # wall-clock drift while still failing hard against a near-zero reading.
    assert age > 3600, (
        f"activity age reported {age}s after a real `git status --porcelain` -- "
        f"expected ~{2 * 86400}s (HEAD's true age); a reading this low means "
        "the axis is still contaminated by the probe's own index write"
    )


# ---------------------------------------------------------------------------
# Discriminator 3 -- a SECOND invocation after a prior probe: ordering cannot
# fix a cross-invocation effect (Root Cause B).
# covers: D85-1, Root Cause B, Definition of Done bullet 5
# ---------------------------------------------------------------------------
def test_second_invocation_after_a_prior_probe_still_reports_the_true_age(
    tmp_path: Path,
) -> None:
    """Reproduces the feature-delta's measured two-pass sequence verbatim:
    PASS 1 reads age BEFORE any probe runs (the shipped, already-correct
    within-invocation ordering); the sweep's dirty-state probe then runs;
    PASS 2 is a LATER invocation, again reading age first. `read
    -before-probe` ordering protects PASS 1 but cannot undo what PASS 1's own
    probe wrote for PASS 2 -- this is the defect that "read the age
    earlier" cannot close, and the reason HEAD-only (not reordering) is the
    chosen repair."""
    repo = _real_git_repo(tmp_path)
    _age_baseline_seconds(repo, seconds_old=3 * 86400)

    # PASS 1 -- read age FIRST, exactly like the shipped `worktree_sentinel.py`
    # ordering (module docstring lines 29-39).
    age_pass_1 = read_activity_age_seconds(repo, now=time.time())
    assert isinstance(age_pass_1, int)
    assert age_pass_1 > 86400, "sanity: PASS 1 must observe the 3-day baseline"

    # ...the sweep's dirty-state probe now runs (the SAME probe every real
    # sweep runs via `collect_worktree_triage_receipt`).
    subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True)

    # PASS 2 -- a LATER invocation, still reading age first. Ordering within
    # THIS invocation cannot undo PASS 1's probe.
    age_pass_2 = read_activity_age_seconds(repo, now=time.time())

    assert isinstance(age_pass_2, int)
    assert age_pass_2 > 3600, (
        f"PASS 2 reported {age_pass_2}s -- 3 days of real abandonment erased by "
        "the PREVIOUS invocation's own probe; case-ordering within one "
        "invocation cannot fix a cross-invocation contamination"
    )


# ---------------------------------------------------------------------------
# Discriminator 2 -- the AGGREGATE verdict, not just the raw age: a stale
# worktree must reach ABANDONED_CANDIDATE, never OWNED.
# covers: D85-1, feature-delta §Problem statement ("permanently hides every
#         abandoned worktree"), Definition of Done bullet 1
# ---------------------------------------------------------------------------
def test_stale_worktree_reaches_abandoned_candidate_not_owned_after_self_probe(
    tmp_path: Path,
) -> None:
    """The harm the defect causes is a VERDICT flip, not a number: a genuinely
    abandoned worktree (no declared owner, anti-rot triage already says
    ABANDONED_CANDIDATE) must still classify ABANDONED_CANDIDATE at the
    `classify_sentinel` aggregate after a real `git status` has run against
    it -- not flip to OWNED because the contaminated axis reports a fresh
    reading. A unit assertion on the age number alone is weaker than this:
    the number could stay wrong while the verdict happened to still land
    right, or vice versa."""
    repo = _real_git_repo(tmp_path)
    _age_baseline_seconds(repo, seconds_old=4 * 86400)

    # The Sentinel's own dirty-state probe, run exactly as
    # `collect_worktree_triage_receipt` runs it during a real sweep.
    subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True)

    activity_age = read_activity_age_seconds(repo, now=time.time())

    anti_rot = WorktreeAntiRotReceipt(state=TriageState.ABANDONED_CANDIDATE)
    verdict = classify_sentinel(
        declared_owned=False,
        declared_how="",
        anti_rot=anti_rot,
        activity_age_seconds=activity_age,
    )

    assert verdict.state is SentinelState.ABANDONED_CANDIDATE, (
        f"expected ABANDONED_CANDIDATE for a 4-day-stale worktree, got "
        f"{verdict.state.value} -- the Sentinel's own dirty-state probe "
        f"(activity_age={activity_age!r}) contaminated the verdict, exactly "
        "the class of harm this repair closes: an instrument consulted "
        "before every scheduling decision permanently hides abandonment"
    )


# ---------------------------------------------------------------------------
# Discriminator 4 -- the third state is preserved, never traded for another
# collapse: HEAD alone unreadable must still be Indeterminate/UNDECIDABLE
# even when `index` is perfectly readable (a case the CURRENT min-based axis
# gets WRONG in the other direction -- it silently substitutes `index`).
# covers: D85-1, GDP-8 arity corollary, Definition of Done bullet 4
# ---------------------------------------------------------------------------
def test_activity_axis_is_indeterminate_when_head_alone_is_unreadable(
    tmp_path: Path,
) -> None:
    """Under the repaired HEAD-only contract, an unreadable `HEAD` must yield
    `Indeterminate` regardless of whether `index` happens to be readable --
    `index` is no longer part of the axis at all, so it cannot rescue a
    reading `HEAD` cannot supply. RED against the CURRENT code: today, when
    `HEAD` is absent but `index` is present, `min` over the filtered list
    silently substitutes `index`'s age and returns a fabricated int instead
    of `Indeterminate` -- exactly the "trade one collapse for another"
    failure mode this scenario exists to catch."""
    worktree = tmp_path / "wt"
    gitdir = tmp_path / "gitdir-for-wt"
    gitdir.mkdir()
    worktree.mkdir()
    (worktree / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
    # Deliberately no HEAD file at all -- only `index` exists and is stat'able.
    index = gitdir / "index"
    index.write_text("", encoding="utf-8")
    now = time.time()
    os.utime(index, (now - 100, now - 100))

    age = read_activity_age_seconds(worktree, now=now)

    assert isinstance(age, Indeterminate), (
        f"expected Indeterminate when HEAD cannot be stat'd, got {age!r} -- "
        "the axis is still falling back to `index` instead of treating HEAD "
        "as the sole observable"
    )

    verdict = classify_sentinel(
        declared_owned=False,
        declared_how="",
        anti_rot=WorktreeAntiRotReceipt(state=TriageState.ABANDONED_CANDIDATE),
        activity_age_seconds=age,
    )
    assert verdict.state is SentinelState.UNDECIDABLE, (
        f"an unreadable activity signal must reach the aggregate as "
        f"UNDECIDABLE, got {verdict.state.value} -- never silently folded "
        "into ABANDONED_CANDIDATE (absence-from-silence) nor into OWNED "
        "(hiding a genuinely quiet, unowned worktree)"
    )


# ---------------------------------------------------------------------------
# Discriminator 5 -- negative direction: a genuinely active worktree must
# NOT be reported abandoned. Without this, "always say abandoned" would pass
# every scenario above.
# covers: D85-1, Definition of Done (sibling-branch preservation)
# ---------------------------------------------------------------------------
def test_genuinely_active_worktree_is_not_reported_abandoned(
    tmp_path: Path,
) -> None:
    """Sibling-branch pin (Critical Rules): a worktree committed to seconds
    ago -- HEAD genuinely fresh, not contaminated-fresh -- must classify
    OWNED via the activity axis, exactly as it does today. This scenario is
    expected to hold on BOTH the pre-fix and post-fix axis (HEAD was never
    contaminated by any probe in this case); it exists so a "flatten
    everything to ABANDONED_CANDIDATE" bad fix would fail here even though
    it would accidentally pass every OTHER scenario in this file."""
    repo = _real_git_repo(tmp_path)
    # HEAD and index are both fresh from the commit `_real_git_repo` just
    # made -- no baselining backward. A real `git status` may still run
    # (mirrors a real sweep) without changing the expected outcome.
    subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True)

    activity_age = read_activity_age_seconds(repo, now=time.time())

    anti_rot = WorktreeAntiRotReceipt(state=TriageState.ABANDONED_CANDIDATE)
    verdict = classify_sentinel(
        declared_owned=False,
        declared_how="",
        anti_rot=anti_rot,
        activity_age_seconds=activity_age,
    )

    assert verdict.state is SentinelState.OWNED, (
        f"a worktree committed to seconds ago must classify OWNED (recent "
        f"activity), got {verdict.state.value} -- a fix that over-corrects "
        "toward always reporting abandonment is just as wrong as the defect "
        "it replaces"
    )


# ---------------------------------------------------------------------------
# Discriminator 6 -- neither observable readable, or the worktree directory
# itself gone: the axis must never fabricate a reading, and UNDECIDABLE must
# stay genuinely distinguishable from a DIFFERENT unreadable-cause, never
# collapsing into one indistinguishable "could not read" blob.
#
# Raised by the coordinator after accepting discriminators 1-5: scenario 4
# only covers "HEAD unreadable, index readable" (the fabrication case this
# repair's own contract calls out). This closes the adjacent, sharper
# question -- can the SAME kind of silent-wrong (a guessed answer standing
# in for "cannot determine") happen when BOTH observables are gone, or when
# the worktree directory itself was deleted out from under a live `git
# worktree list` enumeration (measured for real: `git worktree add` then
# `rm -rf` the linked checkout -- `git worktree list --porcelain` keeps
# listing it, annotated `prunable gitdir file points to non-existent
# location`, so this IS a reachable production shape, not a synthetic one).
#
# covers: D85-1, GDP-8 arity corollary, Definition of Done bullet 4
# ---------------------------------------------------------------------------
def test_activity_axis_never_fabricates_a_reading_when_the_worktree_directory_is_gone(
    tmp_path: Path,
) -> None:
    """A real linked worktree, `git worktree add`-created then `rm -rf`'d out
    from under the parent repo -- the exact shape `git worktree list
    --porcelain` still reports (measured: `prunable gitdir file points to
    non-existent location`). `read_activity_age_seconds` must still return
    `Indeterminate`, never a fabricated int derived from whatever happens to
    still be readable nearby."""
    main_repo = _real_git_repo(tmp_path)
    linked = tmp_path / "linked-wt"
    subprocess.run(
        ["git", "worktree", "add", "-q", str(linked), "-b", "lane1"],
        cwd=main_repo,
        check=True,
    )
    subprocess.run(["rm", "-rf", str(linked)], check=True)

    age_gone = read_activity_age_seconds(linked, now=time.time())

    assert isinstance(age_gone, Indeterminate), (
        f"expected Indeterminate for a worktree directory deleted out from "
        f"under a live git enumeration, got {age_gone!r} -- a fabricated "
        "reading here is the same silent-wrong class as substituting index "
        "for an unreadable HEAD"
    )
    assert age_gone.reason, (
        "Indeterminate.reason must never be empty -- an unexplained "
        "'cannot determine' is as unusable as a fabricated number"
    )

    verdict_gone = classify_sentinel(
        declared_owned=False,
        declared_how="",
        anti_rot=WorktreeAntiRotReceipt(state=TriageState.ABANDONED_CANDIDATE),
        activity_age_seconds=age_gone,
    )
    assert verdict_gone.state is SentinelState.UNDECIDABLE, (
        f"a deleted worktree directory must reach UNDECIDABLE at the "
        f"aggregate, got {verdict_gone.state.value}"
    )

    # A SECOND, differently-caused Indeterminate (gitdir resolves, but
    # neither HEAD nor index inside it can be stat'd) -- the state is
    # deliberately the SAME (GDP-8: exactly three states, never a fourth
    # carved out per cause), but the EXPLANATION must not collapse into one
    # indistinguishable blob. If it did, an operator staring at two
    # UNDECIDABLE rows could never tell "the worktree is gone" from "the
    # worktree exists but something inside its gitdir is broken".
    worktree_b = tmp_path / "wt_both_missing"
    gitdir_b = tmp_path / "gitdir_both_missing"
    gitdir_b.mkdir()
    worktree_b.mkdir()
    (worktree_b / ".git").write_text(f"gitdir: {gitdir_b}\n", encoding="utf-8")
    age_both_missing = read_activity_age_seconds(worktree_b, now=time.time())

    assert isinstance(age_both_missing, Indeterminate)
    verdict_both_missing = classify_sentinel(
        declared_owned=False,
        declared_how="",
        anti_rot=WorktreeAntiRotReceipt(state=TriageState.ABANDONED_CANDIDATE),
        activity_age_seconds=age_both_missing,
    )
    assert verdict_both_missing.state is SentinelState.UNDECIDABLE

    assert age_gone.reason != age_both_missing.reason, (
        f"two DIFFERENT unreadable causes produced the IDENTICAL reason "
        f"string {age_gone.reason!r} -- UNDECIDABLE has collapsed into one "
        "indistinguishable 'could not read' blob instead of naming which "
        "probe failed and why"
    )
    gone_evidence = next(
        e for e in verdict_gone.evidence if e.category == "activity-indeterminate"
    )
    missing_evidence = next(
        e
        for e in verdict_both_missing.evidence
        if e.category == "activity-indeterminate"
    )
    assert gone_evidence.why != missing_evidence.why, (
        "the SAME collapse, but observed at the SentinelVerdict.evidence "
        "level rather than the raw Indeterminate.reason -- an operator "
        "reading the aggregate receipt must still be able to tell the two "
        "causes apart"
    )
