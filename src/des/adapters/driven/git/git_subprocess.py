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

import subprocess
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


def git_text(repo: Path, *args: str) -> str:
    """Run a git command in ``repo`` and return stdout (raises on non-zero).

    Byte-for-byte identical to the three former ``_git`` copies: a checked,
    text-mode ``git`` subprocess rooted at ``repo`` whose stdout is returned.
    """
    completed = subprocess.run(
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
    completed = subprocess.run(
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
    completed = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
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
