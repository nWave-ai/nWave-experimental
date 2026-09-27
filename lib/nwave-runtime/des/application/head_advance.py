"""The ONE owner of "move a destination's HEAD forward", for every caller.

WHY THIS MODULE EXISTS.  Two callers advance a repository's HEAD onto work that
was built elsewhere.  `DeliveryContinuationRunner._integrate` swaps the ref onto
the candidate it just built, and the `des lane integrate` step fast-forwards the
orchestrator's live checkout onto a lane branch.  Written twice, the two would
be two places to get the stale-destination refusal wrong, and the first one to
drift would do so silently -- the destination moving is exactly the case neither
caller ever sees in a green run.  So the observation, the comparison and the
refusal vocabulary live here once, and each caller maps the refusal into its own
terminal shape.

WHY TWO ENACTMENTS AND NOT ONE.  They advance different KINDS of destination,
and the difference is not a flag.

- `swap` is a true compare-and-swap on the REF alone: `update-ref HEAD <new>
  <expected-old>` writes only if the destination is still where the caller last
  observed it.  Its caller has ALREADY written the new bytes into the working
  tree -- the crafter wrote them there -- so the tree needs no update and only
  the ref and the owned index have to catch up.  Running a merge there would be
  refused by Git for local changes that are in fact the very content being
  integrated.
- `fast_forward` advances a LIVE CHECKOUT whose working tree holds NONE of the
  new bytes, because they were committed in another worktree.  `merge --ff-only`
  moves the ref, the index and the files together, and refuses rather than
  overwriting an operator's uncommitted work.  A bare `update-ref` there would
  leave the tree at the old commit while the ref names the new one, so every
  integrated file would read as a reverse-diff modification the operator never
  made -- a silent-wrong (GDP-6) on a live human checkout.

So the runner's compare-and-swap is NOT reusable as-is for a live checkout, and
the honest shape is one module owning both, each named by the property it has,
rather than one function with a switch deciding whether to destroy a working
tree.

WHAT IS SHARED REGARDLESS: `_destination`, the single observation of where HEAD
is now, and `AdvanceRefusal`, the single vocabulary for "the destination is not
where you think it is" and "Git never answered".
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from des.adapters.driven.git.git_observation import (
    GitObservation,
    GitUnanswered,
    observe_text,
)


if TYPE_CHECKING:
    from pathlib import Path


#: One text observation of Git in a root.  The runner injects its own bound
#: method so a caller substituting Git in a test still substitutes it here.
GitObserver = Callable[..., GitObservation]

#: `git merge-base --is-ancestor` answers the QUESTION with exit 1, which is not
#: a failure of the tool.  Any other non-zero status is.
_NOT_AN_ANCESTOR = 1

_STALE_HOW = "re-observe workspace"

_FAST_FORWARD_HOW = (
    "pull the destination into the branch being integrated, re-run its "
    "verification there, then re-run this step; nothing was written, so the "
    "destination and the branch both still hold exactly what they held"
)


@dataclass(frozen=True, slots=True)
class AdvanceRefusal:
    """Why HEAD was not advanced, already WHAT / WHY / HOW.

    `unanswered` is the discriminant a caller needs and a returncode cannot
    carry: Git REFUSING is a repository fact, Git never ANSWERING is not, and a
    caller that reports the second as the first asserts a state it never
    observed.  Every caller maps a non-`None` `unanswered` to its own
    indeterminate terminal, carrying the seam's own WHAT / WHY / HOW.
    """

    what: str
    why: str
    how: str
    unanswered: GitUnanswered | None = None


@dataclass(frozen=True, slots=True)
class HeadAdvance:
    """Advance one destination's HEAD, or say exactly why it was not advanced."""

    observe: GitObserver = field(default=observe_text)

    def destination(self, root: Path) -> str | AdvanceRefusal:
        """Where `root`'s HEAD is NOW -- the primitive both enactments start from."""
        observed = self.observe(root, "rev-parse", "HEAD")
        if observed.returncode:
            return AdvanceRefusal(
                "GitUnavailable", observed.stderr, "restore Git", observed.unanswered
            )
        return observed.stdout.strip()

    def swap(self, root: Path, new: str, expected_old: str) -> AdvanceRefusal | None:
        """One compare-and-swap of the ref alone; `None` means it was written.

        The swap is its own named observation rather than a `.returncode` folded
        into the comparison above it: a Git that never ANSWERED would otherwise
        have read as "the destination moved", asserting a repository fact the
        caller did not observe.
        """
        destination = self.destination(root)
        if isinstance(destination, AdvanceRefusal):
            return destination
        if destination == new:
            return None
        if destination != expected_old:
            return self._stale(new)
        swapped = self.observe(root, "update-ref", "HEAD", new, expected_old)
        if swapped.returncode:
            return AdvanceRefusal(
                "IntegrationStale",
                f"destination moved before the compare-and-swap of {new}",
                _STALE_HOW,
                swapped.unanswered,
            )
        return None

    def fast_forward(self, root: Path, new: str) -> str | AdvanceRefusal:
        """Advance a live checkout onto `new`; the commit it advanced FROM.

        The ancestry is MEASURED before the merge rather than left to the merge
        to discover, so the refusal names both commits and the caller can say
        which one moved.  `--ff-only` then makes the enactment itself incapable
        of writing a merge commit if the measurement were ever wrong.
        """
        destination = self.destination(root)
        if isinstance(destination, AdvanceRefusal):
            return destination
        ancestry = self.observe(root, "merge-base", "--is-ancestor", destination, new)
        if ancestry.unanswered is not None:
            return AdvanceRefusal(
                "GitUnavailable", ancestry.stderr, "restore Git", ancestry.unanswered
            )
        if ancestry.returncode == _NOT_AN_ANCESTOR:
            return AdvanceRefusal(
                "IntegrationStale",
                f"the destination {destination} is not an ancestor of {new}, so "
                "no fast-forward is possible: the destination moved after the "
                "branch was based on it",
                _FAST_FORWARD_HOW,
            )
        if ancestry.returncode:
            return AdvanceRefusal(
                "GitUnavailable", ancestry.stderr, "restore Git", ancestry.unanswered
            )
        merged = self.observe(root, "merge", "--ff-only", new)
        if merged.returncode:
            return AdvanceRefusal(
                "FastForwardRefused",
                f"git refused to fast-forward {destination} onto {new}: "
                f"{merged.stderr.strip()}",
                "resolve what the destination checkout is holding -- most often "
                "an uncommitted change to a file the delta also changes -- then "
                "re-run this step",
                merged.unanswered,
            )
        return destination

    @staticmethod
    def _stale(new: str) -> AdvanceRefusal:
        return AdvanceRefusal(
            "IntegrationStale",
            f"destination moved before the compare-and-swap of {new}",
            _STALE_HOW,
        )


__all__ = ["AdvanceRefusal", "GitObserver", "HeadAdvance"]
