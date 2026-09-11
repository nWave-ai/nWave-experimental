"""Open one lane worktree, integrate it, and clean it up when asked.

ADR-SSOT-002 Section 4b: the DES is a tool the orchestrating model invokes.  Each
step is a command invoked ALONE; it measures, constructs and enacts, returns one
closed outcome, and NAMES the canonical next step as DATA it does not execute.

These are the invocable steps of the lane cycle an orchestrator runs around the
delivery steps. Before them the cycle was hand-typed Git -- `worktree add`,
`merge --ff-only`, `worktree remove`, `branch -d` -- and the repository's own
CLAUDE.md named `des` subcommands for it that no longer exist, so the standing
instruction taught a contract the CLI could not honour.

WHERE THE LANE IS PUT, and why the software decides it.  The path is derived,
never passed: `<system temp>/nwave-<name>-lane`.  Derived, because a caller that
chooses the path can open two worktrees for one lane and the software has
nothing left to refuse; derived THIS way, because it is what the lanes on this
project already do -- `/tmp/nwave-<name>-lane` was the measured shape of every
live lane when this step was written.  `tempfile.gettempdir()` rather than a
literal `/tmp` keeps the only runtime dependency Python: the same code answers on
a platform that has no `/tmp`, and a caller isolating itself (a test, a second
operator on one box) redirects the whole family with `TMPDIR`.

WHY `integrate` TAKES THE WORKTREE AND NOT THE BRANCH.  One form, and this one,
because `worktree list --porcelain` maps a path to its branch AND its tip, so
the caller passes the single fact `open` handed it and the software measures the
rest.  Taking the branch instead would make the caller supply what the software
can observe, and would leave the worktree -- the thing that must be proven clean
and then removed -- to be searched for.

WHAT THIS STEP WILL NOT DO.  It never forces.  A lane holding uncommitted or
untracked bytes is REFUSED with those paths named, never removed with `--force`:
the runner's own candidate worktrees are ephemeral and wholly owned, so forcing
them costs nothing, while a lane is where a person's or an agent's unpushed work
lives.  That is why this step does not reuse the runner's
`_remove_candidate_worktree`, and why the two are not merged behind a flag --
"destroy uncommitted content, or don't" is not a parameter.
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from des.adapters.driven.git.git_observation import GitObservation, observe_text
from des.application.head_advance import AdvanceRefusal, GitObserver, HeadAdvance
from des.cli._repo_root_arg import add_repo_root_argument
from des.cli.step_terminal import (
    NOTHING_OWED as _NO_STEP_OWED,
)
from des.cli.step_terminal import (
    StepRefusal,
)
from des.cli.step_terminal import (
    refuse as _refuse,
)
from des.cli.step_terminal import (
    resolved_root as _root,
)
from des.cli.step_terminal import (
    succeed as _succeed,
)
from des.domain.delivery_disposition import Disposition


#: A lane name is ONE path segment and ONE branch segment at the same time.
#: Dots are excluded outright rather than filtered case by case: `..` escapes the
#: derived directory and a trailing `.lock` is a name Git reserves, and a grammar
#: that cannot express either is shorter than the checks that would catch them.
LANE_NAME = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")

#: A delta touching any of these leaves the INSTALLED projection behind this
#: checkout, so the canonical next step after integrating it is a reinstall.
#: Everything else is repository-local and owes nothing.
SHIPPED_ASSET_PREFIXES = ("nWave/", "src/des/", "scripts/install/")

#: How many changed shipped paths the `NEXT` line names before it stops. The
#: line exists to tell a reader WHY a reinstall is owed, not to reprint a diff.
_NAMED_PATHS = 3

NOTHING_OWED = f"{_NO_STEP_OWED} -- the integrated delta touches no shipped asset"


@dataclass(frozen=True, slots=True)
class OpenedLane:
    worktree: Path
    branch: str
    base: str


@dataclass(frozen=True, slots=True)
class IntegratedLane:
    integrated: str
    worktree: Path
    branch: str
    shipped: tuple[str, ...]
    retained: bool


@dataclass(frozen=True, slots=True)
class RegisteredLane:
    """One worktree of this root, as Git itself reports it."""

    worktree: Path
    branch: str | None
    tip: str


@dataclass(frozen=True, slots=True)
class LaneSteps:
    """The lane steps, over one injected Git observation seam."""

    observe: GitObserver = field(default=observe_text)

    @property
    def _advance(self) -> HeadAdvance:
        return HeadAdvance(self.observe)

    # ---------------------------------------------------------------- open

    def open(
        self, root: Path, name: str, base_ref: str | None
    ) -> OpenedLane | StepRefusal:
        """Create the lane worktree and its branch, or refuse without writing."""
        if LANE_NAME.match(name) is None:
            return StepRefusal(
                "InvalidLaneName",
                f"{name!r} is not one path-and-branch segment: a lane name is "
                "1 to 64 characters of letters, digits, hyphen and underscore, "
                "starting with a letter or a digit",
                "re-run with a name inside that grammar, for example "
                "`--name lane-open-and-integrate-steps`",
            )
        branch = f"lane/{name}"
        worktree = Path(tempfile.gettempdir()).resolve() / f"nwave-{name}-lane"
        base = self._resolve(root, base_ref)
        if isinstance(base, StepRefusal):
            return base
        held = self._existing(root, worktree, branch)
        if held is not None:
            return held
        added = self.observe(root, "worktree", "add", str(worktree), "-b", branch, base)
        if added.returncode:
            return self._git_refusal(
                added,
                "LaneNotOpened",
                f"git could not create the lane worktree at {worktree}",
                "read the git error above, clear what it names, then re-run "
                "this step; no worktree and no branch were created",
            )
        return OpenedLane(worktree, branch, base)

    def _resolve(self, root: Path, base_ref: str | None) -> str | StepRefusal:
        """The commit the lane starts from -- the root's HEAD unless told otherwise."""
        if base_ref is None:
            destination = self._advance.destination(root)
            if isinstance(destination, AdvanceRefusal):
                return self._from_advance(destination)
            return destination
        observed = self.observe(root, "rev-parse", "--verify", f"{base_ref}^{{commit}}")
        if observed.returncode:
            return self._git_refusal(
                observed,
                "InvalidLaneBase",
                f"{base_ref!r} does not name a commit in {root}",
                "re-run with a base this repository resolves, or omit --base to "
                "start the lane from the root's own HEAD",
            )
        return observed.stdout.strip()

    def _existing(self, root: Path, worktree: Path, branch: str) -> StepRefusal | None:
        """Refuse a lane that is already there -- NEVER overwrite one.

        Both halves are checked, because they can exist apart: a removed
        directory can leave the branch, and a pruned registration can leave the
        directory.  Either one alone means a `worktree add` would fail or, worse,
        would land on top of work in flight.
        """
        if worktree.exists():
            return StepRefusal(
                "LaneExists",
                f"{worktree} already exists, and this step never writes into a "
                "path it did not create",
                "integrate or release that lane first -- `des lane integrate "
                f"--repo-root {root} --worktree {worktree}` -- or open this one "
                "under a different --name",
            )
        held = self.observe(
            root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"
        )
        if held.unanswered is not None:
            return self._git_refusal(
                held,
                "GitUnavailable",
                held.stderr,
                "restore Git",
            )
        if held.returncode == 0:
            return StepRefusal(
                "LaneExists",
                f"the branch {branch} already exists at {held.stdout.strip()}, "
                f"while {worktree} does not: a previous lane of this name was "
                "removed without its branch",
                "integrate the branch from a worktree of its own, or delete it "
                "once its work is elsewhere, then re-run this step",
            )
        return None

    # ----------------------------------------------------------- integrate

    def integrate(
        self, root: Path, worktree: Path, *, keep_worktree: bool = False
    ) -> IntegratedLane | StepRefusal:
        """Fast-forward the root onto the lane, optionally retaining the lane."""
        registered = self._registered(root, worktree)
        if isinstance(registered, StepRefusal):
            return registered
        dirty = self._dirty(registered.worktree)
        if dirty is not None:
            return dirty
        advanced = self._advance.fast_forward(root, registered.tip)
        if isinstance(advanced, AdvanceRefusal):
            return self._from_advance(advanced)
        shipped = self._shipped(root, advanced, registered.tip)
        if isinstance(shipped, StepRefusal):
            return shipped
        if not keep_worktree:
            closed = self._close(root, registered)
            if closed is not None:
                return closed
        return IntegratedLane(
            registered.tip,
            registered.worktree,
            registered.branch or "",
            shipped,
            keep_worktree,
        )

    def finalize(self, root: Path, worktree: Path) -> RegisteredLane | StepRefusal:
        """Close a clean lane only after its tip is reachable from ``root``.

        This intentionally does not advance the destination.  A retained lane
        can remain open while the destination gains an evolution document (or
        other whole-feature evidence); its tip need only be an ancestor of the
        destination at cleanup time.
        """
        registered = self._registered(root, worktree)
        if isinstance(registered, StepRefusal):
            return registered
        dirty = self._dirty(registered.worktree)
        if dirty is not None:
            return dirty
        integrated = self._is_integrated(root, registered)
        if isinstance(integrated, StepRefusal):
            return integrated
        closed = self._close(root, registered)
        if closed is not None:
            return closed
        return registered

    def _is_integrated(self, root: Path, lane: RegisteredLane) -> StepRefusal | None:
        """Refuse cleanup unless Git proves the lane tip is destination history."""
        destination = self._advance.destination(root)
        if isinstance(destination, AdvanceRefusal):
            return self._from_advance(destination)
        ancestry = self.observe(
            root, "merge-base", "--is-ancestor", lane.tip, destination
        )
        if ancestry.unanswered is not None:
            return self._git_refusal(
                ancestry, "GitUnavailable", ancestry.stderr, "restore Git"
            )
        if ancestry.returncode == 1:
            return StepRefusal(
                "LaneNotIntegrated",
                f"the lane tip {lane.tip} is not an ancestor of destination "
                f"{destination}, so removing {lane.worktree} could discard "
                "unintegrated commits",
                "integrate the lane with `des lane integrate`, or preserve its "
                "commits elsewhere, then re-run finalize; this step never merges "
                "or reintegrates a lane",
            )
        if ancestry.returncode:
            return self._git_refusal(
                ancestry, "GitUnavailable", ancestry.stderr, "restore Git"
            )
        return None

    def _registered(self, root: Path, worktree: Path) -> RegisteredLane | StepRefusal:
        """The lane as GIT reports it -- its real branch and its real tip.

        Measured rather than taken from the caller: a path is what the caller
        knows, while the branch and the tip are what the repository knows, and
        the step must integrate the second.
        """
        listed = self.observe(root, "worktree", "list", "--porcelain")
        if listed.returncode:
            return self._git_refusal(
                listed, "GitUnavailable", listed.stderr, "restore Git"
            )
        for entry in listed.stdout.split("\n\n"):
            fields = dict(
                [*line.split(" ", 1), ""][:2] for line in entry.splitlines() if line
            )
            listed_path = fields.get("worktree", "")
            if not listed_path or Path(listed_path).resolve() != worktree:
                continue
            branch = fields.get("branch") or None
            return RegisteredLane(
                Path(listed_path),
                branch.removeprefix("refs/heads/") if branch else None,
                fields.get("HEAD", "").strip(),
            )
        return StepRefusal(
            "LaneNotRegistered",
            f"{worktree} is not a worktree of {root}",
            "pass the path `des lane open` reported for this lane, or run "
            f"`git -C {root} worktree list` to see the lanes this root has",
        )

    def _dirty(self, worktree: Path) -> StepRefusal | None:
        """Refuse a lane holding bytes no commit carries, and NAME them."""
        status = self.observe(
            worktree, "status", "--porcelain=v1", "--untracked-files=all"
        )
        if status.returncode:
            return self._git_refusal(
                status,
                "GitUnavailable",
                status.stderr,
                "restore Git",
            )
        if not status.stdout.strip():
            return None
        return StepRefusal(
            "LaneDirty",
            f"{worktree} holds changes no commit carries, so integrating it "
            "would leave them behind: " + "; ".join(status.stdout.split("\n")).strip(),
            "commit what belongs to the lane, or remove what does not, in that "
            "worktree, then re-run this step; this step never discards a byte "
            "it did not see committed",
        )

    def _shipped(
        self, root: Path, base: str, tip: str
    ) -> tuple[str, ...] | StepRefusal:
        """Which SHIPPED paths the integrated delta changed -- a measurement."""
        changed = self.observe(root, "diff", "--name-only", base, tip)
        if changed.returncode:
            return self._git_refusal(
                changed,
                "IntegratedDeltaUnobservable",
                f"the delta between {base} and {tip} cannot be read, so whether "
                "a reinstallation is owed is unknown; the fast-forward itself "
                "already succeeded",
                f"run `git -C {root} diff --name-only {base} {tip}` and reinstall "
                "if it names a shipped asset",
                Disposition.Indeterminate,
            )
        return tuple(
            path
            for path in changed.stdout.splitlines()
            if path.startswith(SHIPPED_ASSET_PREFIXES)
        )

    def _close(self, root: Path, lane: RegisteredLane) -> StepRefusal | None:
        """Remove the lane worktree, then its branch -- in that order, unforced.

        The order is a Git fact, not a preference: a branch checked out in a
        worktree cannot be deleted.  `-d` and never `-D`, so Git itself measures
        reachability and refuses a branch carrying anything the destination does
        not already hold.
        """
        removed = self.observe(root, "worktree", "remove", str(lane.worktree))
        if removed.returncode:
            return self._git_refusal(
                removed,
                "CleanupUnproven",
                f"the fast-forward succeeded, but {lane.worktree} could not be "
                f"removed: {removed.stderr.strip()}",
                f"inspect {lane.worktree} and remove it once you have read what "
                "it holds; the integration itself is done and must not be repeated",
                Disposition.Indeterminate,
            )
        if lane.branch is None:
            return None
        deleted = self.observe(root, "branch", "-d", lane.branch)
        if deleted.returncode:
            return self._git_refusal(
                deleted,
                "CleanupUnproven",
                f"the fast-forward succeeded and {lane.worktree} is gone, but "
                f"the branch {lane.branch} could not be deleted: "
                f"{deleted.stderr.strip()}",
                f"run `git -C {root} branch -d {lane.branch}` and read what it "
                "refuses; the integration itself is done and must not be repeated",
                Disposition.Indeterminate,
            )
        return None

    # ------------------------------------------------------------- shared

    @staticmethod
    def _from_advance(refused: AdvanceRefusal) -> StepRefusal:
        """One mapping from the shared HEAD-advance vocabulary into this step's."""
        if refused.unanswered is not None:
            return StepRefusal(
                refused.unanswered.what,
                refused.unanswered.why,
                refused.unanswered.how,
                Disposition.Indeterminate,
            )
        return StepRefusal(refused.what, refused.why, refused.how)

    @staticmethod
    def _git_refusal(
        observed: GitObservation,
        what: str,
        why: str,
        how: str,
        *,
        indeterminate: bool = False,
    ) -> StepRefusal:
        """A Git that never ANSWERED is never reported as a repository fact."""
        if observed.unanswered is not None:
            return StepRefusal(
                observed.unanswered.what,
                observed.unanswered.why,
                observed.unanswered.how,
                Disposition.Indeterminate,
            )
        disposition = (
            Disposition.Indeterminate if indeterminate else Disposition.Refusal
        )
        return StepRefusal(what, why, how, disposition)


def _next_after_open(root: Path, lane: OpenedLane) -> str:
    """The canonical next step for an open lane, in its exact invocation form.

    It names what EXISTS today.  `des dispatch` was named here while it was the
    only entry point; it is retired (ADR-SSOT-002 Section 4b, ADR-DES-003
    Section 11) and the invocable steps ARE the shape now, so this names the
    FIRST of them and nothing after it.  Naming the whole sequence here would
    make this line a software-authored plan over more than one invocation, which
    is the thing the retirement removed; `des state` inside the lane answers
    what is owed next, one step at a time.
    """
    return (
        f"des po --repo-root {lane.worktree} -- one Request on stdin, decomposed "
        f"inside the lane; then `des state --repo-root {lane.worktree}` names "
        f"each following step, and close the lane with "
        f"`des lane integrate --repo-root {root} --worktree {lane.worktree}`"
    )


def _next_after_integrate(root: Path, lane: IntegratedLane) -> str:
    if not lane.shipped:
        return NOTHING_OWED
    named = ", ".join(lane.shipped[:_NAMED_PATHS])
    more = len(lane.shipped) - _NAMED_PATHS
    return (
        f"python {root / 'scripts' / 'install' / 'install_nwave.py'} -- the "
        f"integrated delta changes shipped assets ({named}"
        + (f" and {more} more" if more > 0 else "")
        + "), so the installed projection is behind this checkout"
    )


def _next_after_retained_integrate(root: Path, lane: IntegratedLane) -> str:
    """An advisory only; the caller, not this command, chooses intervening work."""
    return (
        f"the integrated lane remains at {lane.worktree}; after any caller-selected "
        f"whole-feature work, cleanup is available as `des lane finalize "
        f"--repo-root {root} --worktree {lane.worktree}`"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="des lane")
    steps = parser.add_subparsers(dest="step", required=True)
    opening = steps.add_parser("open", help="create one lane worktree and branch")
    add_repo_root_argument(opening, "--repo-root", type=Path, required=True)
    opening.add_argument("--name", required=True)
    opening.add_argument("--base", default=None)
    closing = steps.add_parser(
        "integrate", help="fast-forward the root onto one lane, then close it"
    )
    add_repo_root_argument(closing, "--repo-root", type=Path, required=True)
    closing.add_argument("--worktree", type=Path, required=True)
    closing.add_argument(
        "--keep-worktree",
        action="store_true",
        help="retain the clean integrated lane for caller-selected whole-feature work",
    )
    finalizing = steps.add_parser(
        "finalize", help="remove one clean lane already integrated into the root"
    )
    add_repo_root_argument(finalizing, "--repo-root", type=Path, required=True)
    finalizing.add_argument("--worktree", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    root = _root(args.repo_root)
    if isinstance(root, StepRefusal):
        return _refuse(root, "re-invoke this step with a real repository root")
    steps = LaneSteps()
    if args.step == "open":
        opened = steps.open(root, args.name, args.base)
        if isinstance(opened, StepRefusal):
            return _refuse(
                opened,
                f"des lane open --repo-root {root} --name <name> -- after the HOW above",
            )
        _succeed(
            [
                f"WORKTREE: {opened.worktree}",
                f"BRANCH: {opened.branch}",
                f"BASE: {opened.base}",
            ],
            _next_after_open(root, opened),
        )
        return 0
    worktree = args.worktree.resolve()
    if args.step == "integrate":
        integrated = steps.integrate(root, worktree, keep_worktree=args.keep_worktree)
        if isinstance(integrated, StepRefusal):
            return _refuse(
                integrated,
                f"des lane integrate --repo-root {root} --worktree {worktree} -- "
                "after the HOW above",
            )
        fields = [f"INTEGRATED: {integrated.integrated}"]
        if integrated.retained:
            fields.extend(
                [
                    f"RETAINED: {integrated.worktree}",
                    f"BRANCH-RETAINED: {integrated.branch}",
                ]
            )
            next_step = _next_after_retained_integrate(root, integrated)
        else:
            fields.extend(
                [
                    f"REMOVED: {integrated.worktree}",
                    f"BRANCH-REMOVED: {integrated.branch}",
                ]
            )
            next_step = _next_after_integrate(root, integrated)
        _succeed(fields, next_step)
        return 0
    finalized = steps.finalize(root, worktree)
    if isinstance(finalized, StepRefusal):
        return _refuse(
            finalized,
            f"des lane finalize --repo-root {root} --worktree {worktree} -- "
            "after the HOW above",
        )
    _succeed(
        [
            f"REMOVED: {finalized.worktree}",
            f"BRANCH-REMOVED: {finalized.branch or ''}",
        ],
        _NO_STEP_OWED,
    )
    return 0
