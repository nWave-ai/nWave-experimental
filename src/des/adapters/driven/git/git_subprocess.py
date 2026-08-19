"""Single SSOT for the read-only git-subprocess seam (AD-22 collapse).

Before this module the helper

    def _git(repo, *args) -> str:
        completed = subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True, check=True
        )
        return completed.stdout

was triplicated byte-identically across ``run_contract_gate``,
``slice_at_completeness`` and ``reverify_slice_commit``. AD-22 (ARCH_TECH_DEBT)
named that triplication a DRY violation; this module is the one canonical home
the three call-sites now import. ``git`` lives behind this single seam, so the
git-free mandate (AD-21) has exactly one place to grep for git usage in the
contract-gate / slice-completeness path.

Pure read of git -- ``check=True`` so a non-zero git (or a missing executable)
raises, and the call-sites translate that into their LOUD degrade signal
(``Indeterminate`` / refusal). No filesystem mutation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from des.adapters.driven.git.git_constants import GIT_REV_PARSE
from des.runtime.spawn import GIT_TIMEOUT_ENV, git_timeout_seconds, spawn


if TYPE_CHECKING:
    import subprocess
    from pathlib import Path


def _git_spawn(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """Every git spawn in this seam, on the GIT tier of the sanctioned boundary.

    Routed through ``des.runtime.spawn.spawn`` rather than bounded with two
    literal kwargs: the boundary also closes stdin (an inherited fd 0 lets a
    credential prompt block INSIDE the bound, so the bound would be the only
    thing ending it) and raises a ``SpawnTimeout`` naming the
    ``NWAVE_GIT_TIMEOUT`` lever -- a bare ``TimeoutExpired`` hands the operator
    a number and no HOW.
    """
    completed: subprocess.CompletedProcess[str] = spawn(
        argv,
        timeout=git_timeout_seconds(),
        timeout_env=GIT_TIMEOUT_ENV,
        **kwargs,
    )
    return completed


def git_text(repo: Path, *args: str) -> str:
    """Run a git command in ``repo`` and return stdout (raises on non-zero).

    Byte-for-byte identical to the three former ``_git`` copies: a checked,
    text-mode ``git`` subprocess rooted at ``repo`` whose stdout is returned.

    ``subprocess.TimeoutExpired`` propagates deliberately, exactly as
    ``CalledProcessError`` already does: collapsing "git never answered" into a
    return value would hand the caller a definite answer it has not earned. A
    bounded raise is loud; an unbounded wait is not.
    """
    completed = _git_spawn(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout


# The candidate refs probed (in order) when `origin/HEAD`'s symref does not
# resolve -- mirrors `scripts/hooks/validate_push_identity.py:_resolve_default_base`'s
# shape (reused, not reinvented), widened with the two local `refs/heads/*`
# candidates so a fully local-only clone (no `origin` remote at all) still
# resolves its own default branch.
_DEFAULT_BASE_REF_CANDIDATES: tuple[str, ...] = (
    "refs/remotes/origin/master",
    "refs/remotes/origin/main",
    "refs/heads/master",
    "refs/heads/main",
)

_REF_PREFIXES_TO_STRIP: tuple[str, ...] = ("refs/remotes/", "refs/heads/")


def resolve_default_base_ref(repo: Path) -> str | None:
    """Resolve `repo`'s default base ref for a delta-diff gate, or `None`.

    Tiered resolution, LOCAL-git-state only (never dials the network):

      1. `git symbolic-ref --short refs/remotes/origin/HEAD` -- the remote's
         OWN declared default branch (e.g. `origin/trunk`), the strongest
         signal when it resolves.
      2. A candidate probe over `refs/remotes/origin/master`,
         `refs/remotes/origin/main`, `refs/heads/master`, `refs/heads/main`
         (in that order) via `git rev-parse --verify --quiet <ref>^{commit}`.
      3. `None` when nothing resolves -- the caller degrades LOUD (a distinct,
         self-explaining Indeterminate naming the `--delta-base-ref`
         remediation), never silently defaulting to a hardcoded literal.
    """
    symref = _resolve_via_symbolic_ref(repo)
    if symref is not None:
        return symref
    return _resolve_via_candidate_probe(repo)


def _resolve_via_symbolic_ref(repo: Path) -> str | None:
    """The short form of `origin/HEAD`'s symref, or `None` if unresolvable.

    The symref DECLARES a target (e.g. `origin/trunk`) but that target may be
    dangling -- never fetched/created (shallow / single-branch / partial
    clones). Verify the declared target actually resolves to a commit before
    trusting it; a dangling target falls through to the candidate probe
    rather than leaking an unverified ref the caller cannot `git diff`
    against.
    """
    completed = _git_spawn(
        ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    short = completed.stdout.strip()
    if not short:
        return None
    if not _ref_resolves_to_commit(repo, short):
        return None
    return short


def _resolve_via_candidate_probe(repo: Path) -> str | None:
    """The first `_DEFAULT_BASE_REF_CANDIDATES` entry that resolves to a commit."""
    for candidate in _DEFAULT_BASE_REF_CANDIDATES:
        if _ref_resolves_to_commit(repo, candidate):
            return _short_ref(candidate)
    return None


def _ref_resolves_to_commit(repo: Path, ref: str) -> bool:
    """True iff `ref` resolves to a real commit in `repo` (local git state only)."""
    completed = _git_spawn(
        ["git", GIT_REV_PARSE, "--verify", "--quiet", f"{ref}^{{commit}}"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode == 0 and bool(completed.stdout.strip())


def _short_ref(ref: str) -> str:
    """Strip a `refs/remotes/` or `refs/heads/` prefix down to its short name."""
    for prefix in _REF_PREFIXES_TO_STRIP:
        if ref.startswith(prefix):
            return ref[len(prefix) :]
    return ref


def is_ancestor(repo: Path, ancestor_sha: str, descendant_sha: str) -> bool:
    """True iff ``ancestor_sha`` is reachable from ``descendant_sha``.

    Promoted verbatim (D-D7, parallel-work-cleans-up-after-merge-back) from
    ``commit_slice.py``'s former private ``_is_ancestor`` -- byte-identical
    logic, closing the AD-22 duplication this feature's Reuse Analysis
    surfaced. Deliberately OUTSIDE ``git_text``'s ``check=True`` seam: exit 1
    ("not yet merged") is a legitimate answer, not an error, so a checked
    subprocess would wrongly turn it into a raised exception.
    """
    result = _git_spawn(
        ["git", "merge-base", "--is-ancestor", ancestor_sha, descendant_sha],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _content_already_present(repo: Path, commit_sha: str, target_ref: str) -> bool:
    """Second content check (GDP-8 witness corollary), independent of
    patch-id: True iff every path ``commit_sha`` touches already holds
    byte-identical content (or the SAME absence) at ``target_ref``'s tip.

    Catches a squashed or rebuilt cherry-pick whose diff SHAPE no longer
    patch-id-matches the original but whose net file content already
    landed -- ``content_unmatched_commits`` tries this only for a commit
    ``git cherry`` itself could not equate. Any git failure degrades to
    False: still reported as unmerged, the same safe-conservative
    direction ``is_merged_contribution`` always took, never a silent
    "assume present".
    """
    changed = _git_spawn(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit_sha],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if changed.returncode != 0:
        return False
    paths = [line for line in changed.stdout.splitlines() if line]
    if not paths:
        return False
    for path in paths:
        ours = _git_spawn(
            ["git", "show", f"{commit_sha}:{path}"],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        theirs = _git_spawn(
            ["git", "show", f"{target_ref}:{path}"],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        if (ours.returncode == 0) != (theirs.returncode == 0):
            return False
        if ours.returncode == 0 and ours.stdout != theirs.stdout:
            return False
    return True


def content_unmatched_commits(
    repo: Path, head_sha: str, target_ref: str
) -> list[str] | None:
    """Subject lines of every commit reachable from ``head_sha`` but not
    ``target_ref`` whose CONTENT has not already landed on ``target_ref``.

    Our integration model is cherry-pick onto trunk, which mints a brand
    new sha for identical content -- so sha ancestry alone
    (``is_ancestor``) reports every fully-integrated lane as "not yet
    merged": a DESIGNATION (the sha never being an ancestor), never the
    PROPERTY under test (whether the work is actually there). Fixed by
    judging integration by content, with two independent checks (GDP-8
    witness corollary), either sufficient:

    1. Patch-id equivalence -- ``git cherry``, git's own comparison of
       ``git patch-id --stable`` over each commit's diff against every
       commit already unique to ``target_ref`` since the same
       merge-base (git resolves this via the same reachability
       exclusion ``rev-list``'s two-dot range uses -- no explicit
       merge-base call needed here). This IS "compute
       ``git patch-id --stable`` and look for an equal patch-id", git's
       own battle-tested implementation of exactly that, not a
       re-derived copy.
    2. Blob-content equivalence (``_content_already_present``) for a
       patch-id near-miss.

    CAVEAT (row4 incident, 2026-07-20): when ``head_sha`` IS an ancestor
    of ``target_ref``, this range is empty regardless of whether
    ``head_sha`` ever made a commit of its own -- callers with that
    ambiguity to resolve (a worktree that may simply never have
    diverged, versus one whose real work genuinely merged) must check
    ``is_ancestor`` themselves and use ``_is_genuine_ancestor_merge``
    for that branch; this function alone cannot and does not draw that
    distinction, since ``git cherry``'s own reachability exclusion
    treats both the same way (empty).

    None on any git failure -- the caller degrades LOUD, never silently
    assumes either merged or unmerged.
    """
    result = _git_spawn(
        ["git", "cherry", "-v", target_ref, head_sha],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    unmatched: list[str] = []
    for line in result.stdout.splitlines():
        if not line.startswith("+ "):
            continue
        sha, _, subject = line[2:].partition(" ")
        if _content_already_present(repo, sha, target_ref):
            continue
        unmatched.append(subject)
    return unmatched


def _is_genuine_ancestor_merge(repo: Path, head_sha: str, target_ref: str) -> bool:
    """Row4 incident, 2026-07-20 (data-loss bugfix): ``is_ancestor(head,
    target)`` is TRUE in two structurally different situations, and only
    the FIRST is a real merge:

    1. ``head``'s own commits reached ``target`` (via a fast-forward that made
       ``head`` the tip, or via a merge that brought ``head`` in off ``target``'s
       mainline) -- the safe, genuinely-merged case.
    2. ``head`` made NO commits of its own and ``target`` merely advanced PAST
       it, on ``target``'s own first-parent mainline, via unrelated work -- so
       ``head`` sits on ``target``'s mainline as a PROPER ancestor. Nothing of
       ``head``'s own could have merged, because there was nothing to merge --
       and the worktree may still be an active, unfinished lane.

    The two are told apart WITHOUT any recorded creation-base (worktrees here are
    created by many surfaces, not one): ``head`` is a genuine contribution iff it
    is reachable AND is NOT a proper ancestor lying on ``target``'s first-parent
    mainline. Equivalently: ``head`` is the tip, or it joined ``target`` off the
    first-parent spine (a merge). This is the SAFE-conservative direction -- when
    in doubt it refuses cleanup (never a false removal), since deleting a live
    worktree is data loss while leaving one is a cosmetic loose end.

    Caller's responsibility: only call this once ``is_ancestor(head, target)``
    is already known True -- it does not itself re-check ancestry.
    """
    first_parent_line = _git_spawn(
        ["git", "rev-list", "--first-parent", target_ref],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if first_parent_line.returncode != 0:
        # Cannot read target's mainline -- degrade SAFE (refuse cleanup) rather
        # than fall back to the bare-ancestor false-positive this guards against.
        return False
    mainline = first_parent_line.stdout.split()
    if not mainline:
        return True
    tip, proper_ancestors = mainline[0], mainline[1:]
    if head_sha == tip:
        return True
    return head_sha not in set(proper_ancestors)


def is_merged_contribution(repo: Path, head_sha: str, target_ref: str) -> bool:
    """True iff ``head_sha``'s OWN work is integrated onto ``target_ref``.

    Two branches, neither touching the other's territory:

    1. ``head_sha`` IS an ancestor of ``target_ref``: delegate to
       ``_is_genuine_ancestor_merge`` -- the row4 incident fix, UNCHANGED
       by the content-check fix below. This branch alone can never see a
       cherry-picked commit (a cherry-pick mints a brand new sha, so a
       cherry-picked ``head_sha`` is never an ancestor of ``target_ref``
       in the first place) -- so widening it to "ancestor implies safe"
       would silently readmit the row4 false-positive for the OTHER
       reason ancestor-is-true can hold (case 2 above).
    2. ``head_sha`` is NOT an ancestor at all: our integration model is
       cherry-pick onto trunk, which mints a brand new sha for identical
       content -- so sha ancestry alone reported every fully-integrated
       lane as "not yet merged" here: a DESIGNATION (the sha never being
       an ancestor), never the PROPERTY under test (whether the work is
       actually there). Fixed by delegating to
       ``content_unmatched_commits``, which judges by CONTENT
       (patch-id, then blob-content) instead.

    A git failure on either branch degrades SAFE (refuse cleanup), the
    conservative direction this function has always taken -- deleting a
    live worktree is data loss, leaving one is a cosmetic loose end.

    Pure read (git + Python only, target-machine agnostic). Outside
    ``git_text``'s ``check=True`` seam for the same reason ``is_ancestor``
    is: "not merged" is a legitimate answer, never an error.
    """
    if is_ancestor(repo, head_sha, target_ref):
        return _is_genuine_ancestor_merge(repo, head_sha, target_ref)
    unmatched = content_unmatched_commits(repo, head_sha, target_ref)
    if unmatched is None:
        return False
    return not unmatched
