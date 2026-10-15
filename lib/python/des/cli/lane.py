"""Open one lane worktree, integrate it, and clean it up when asked.

ADR-SSOT-002 Section 4b: the DES is a tool the orchestrating model invokes.  Each
step is a command invoked ALONE; it measures, constructs and enacts, returns one
closed outcome, and NAMES the canonical next step as DATA it does not execute.

These are the invocable steps of the lane cycle an orchestrator runs around the
delivery steps. Before them the cycle was hand-typed Git -- `worktree add`,
`merge --ff-only`, `worktree remove`, `branch -d` -- and the repository's own
CLAUDE.md named `des` subcommands for it that no longer exist, so the standing
instruction taught a contract the CLI could not honour.

The lane path follows the repository's configured verification workspace root,
defaulting to ``<repo-root>/lanes/<name>``. It is durable, independent of TMPDIR,
and names in separate repositories do not collide. A local Git info/exclude
entry keeps nested worktrees out of the
destination's status without editing its tracked ignore policy. Existing
registered worktrees at older locations remain valid integrate/finalize inputs.

WHAT `status` IS FOR.  A lane's finished work is not delivered while its tip is
outside the destination, and no other step enumerates the lanes a root HAS:
`integrate` and `finalize` each answer one path an orchestrator already names.
`status` is the read-only inventory over the same registration table Git's
`worktree list` already is, one block per lane: whether its tip is an ancestor
of the destination (measured, never assumed from a clean worktree), which bytes
no commit carries -- uncommitted, untracked AND ignored -- whether the
registration still names a directory at all, and the next command that applies.
It observes; it never merges, writes, or removes, and `NEXT` remains data.

WHY REMOVAL REFUSES IGNORED BYTES.  Git refuses to remove a worktree holding
uncommitted or untracked files, but removes one holding only IGNORED files
without a word -- so a lane whose every extra byte is ignored reads as clean to
`git status` and is deleted with its evidence.  A lane is where a person's or
an agent's unpushed work AND uncommitted evidence live, so the removal paths
(`finalize`, and `integrate` without `--keep-worktree`) prove no ignored bytes
remain, or name them and refuse.  Retaining the worktree skips the proof: the
bytes stay where they are.

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
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

from des.adapters.driven.config.workspace_paths import (
    WorkspaceConfigInvalid,
    WorkspacePaths,
    resolve_workspace_paths,
)
from des.adapters.driven.git.git_observation import GitObservation, observe_text
from des.application.handover import Blocked, handover_path, retained_candidates
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


def _workspace_paths(root: Path) -> WorkspacePaths | StepRefusal:
    """Resolve project identity and placement through their shared owner."""
    try:
        return resolve_workspace_paths(root)
    except WorkspaceConfigInvalid as error:
        return StepRefusal(
            "WorkspaceConfigInvalid",
            str(error),
            "correct verification.reuse in the repository's .nwave/config.json "
            "and re-run this step",
        )


def _reserved_segment(path: Path, lanes_directory: Path) -> bool:
    """Whether `path` lives under a DOT-leading segment of the lanes directory.

    The lane name grammar cannot produce a dot, so dot-leading segments under
    the lanes root are reserved infrastructure (candidate and verification
    workspaces), never lanes -- however many registrations they come to hold.
    A path OUTSIDE the lanes directory is never reserved: historical external
    lanes remain first-class inputs.
    """
    try:
        relative = path.resolve().relative_to(lanes_directory.resolve())
    except ValueError:
        return False
    return any(part.startswith(".") for part in relative.parts)


@dataclass(frozen=True, slots=True)
class Principal:
    """The checkout owns Git's common directory."""


@dataclass(frozen=True, slots=True)
class LinkedLane:
    worktree: Path
    branch: str
    principal_worktree: Path
    principal_head: str


@dataclass(frozen=True, slots=True)
class Unobservable:
    why: str


def lane_integrate_invocation(principal: Path, lane: Path) -> str:
    return (
        f"des lane integrate --repo-root {shlex.quote(str(principal))} "
        f"--worktree {shlex.quote(str(lane))} --keep-worktree"
    )


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
class LaneObservation:
    """One registered lane's inventory row, every field a Git measurement.

    Three separate facts that must never collapse into one verdict:
    AVAILABILITY is the registration's own state (present, locked, missing) --
    never a readiness claim; CONTENT names bytes no commit carries; INTEGRATED
    is ancestry against the destination, the only delivery fact here.  A clean
    worktree whose tip is outside the destination is AVAILABLE, CONTENT-clean
    and NOT delivered, all at once.
    """

    worktree: Path
    branch: str | None
    tip: str
    integrated: bool | None
    changes: tuple[str, ...] | None
    ignored: tuple[str, ...]
    availability: str
    next_step: str
    content_note: str | None = None


@dataclass(frozen=True, slots=True)
class LaneInventory:
    """The whole lane surface of one destination, measured in one pass."""

    destination: Path
    head: str
    lanes: tuple[LaneObservation, ...]
    unregistered: tuple[Path, ...]


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
        """Create a project-local lane, refusing occupied or escaping paths."""
        if LANE_NAME.match(name) is None:
            return StepRefusal(
                "InvalidLaneName",
                f"{name!r} is not one path-and-branch segment: a lane name is "
                "1 to 64 characters of letters, digits, hyphen and underscore, "
                "starting with a letter or a digit",
                "re-run with a name inside that grammar, for example "
                "`--name lane-open-and-integrate-steps`",
            )
        root = root.resolve()
        branch = f"lane/{name}"
        workspace = _workspace_paths(root)
        if isinstance(workspace, StepRefusal):
            return workspace
        directory = workspace.lanes
        worktree = directory / name
        if worktree.parent.is_symlink() or (
            worktree.parent.exists() and not worktree.parent.is_dir()
        ):
            return StepRefusal(
                "UnsafeLanePath",
                f"{worktree.parent} is a symlink or is not a directory",
                "preserve that path and use a project with a real lanes directory",
            )
        base = self._resolve(root, base_ref)
        if isinstance(base, StepRefusal):
            return base
        held = self._existing(root, worktree, branch)
        if held is not None:
            return held
        excluded = self._exclude_lanes(workspace.root, directory)
        if excluded is not None:
            return excluded
        ignored = self.observe(
            workspace.root, "check-ignore", "--quiet", "--", str(worktree)
        )
        if ignored.returncode:
            return self._git_refusal(
                ignored,
                "LaneNotOpened",
                f"{worktree} is not excluded by the project's Git ignore policy",
                f"resolve ignore rules overriding the local exclusion for {directory} "
                "before re-running; no lane was created",
            )
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

    def _exclude_lanes(self, root: Path, directory: Path) -> StepRefusal | None:
        """Exclude the configured directory without changing existing bytes."""
        relative = directory.relative_to(root).as_posix()
        if "\n" in relative or "\r" in relative:
            return StepRefusal(
                "UnsafeLanePath",
                "the configured workspace path contains a line break",
                "use a workspace path representable in Git info/exclude",
            )
        escaped = re.sub(r"([\\*?\[])", r"\\\1", relative)
        pattern = f"/{escaped}/".encode()
        tracked = self.observe(root, "ls-files", "--", f":(literal){relative}")
        if tracked.returncode:
            return self._git_refusal(
                tracked,
                "LaneNotOpened",
                "could not inspect the lanes directory",
                "restore Git access and re-run this step",
            )
        if tracked.stdout.strip():
            return StepRefusal(
                "UnsafeLanePath",
                f"{directory} contains tracked project files",
                "preserve those files; reserve a source-free lanes directory "
                "before opening a lane",
            )
        observed = self.observe(root, "rev-parse", "--git-path", "info/exclude")
        if observed.returncode:
            return self._git_refusal(
                observed,
                "LaneNotOpened",
                "could not locate Git's local exclusions",
                "restore Git access and re-run this step",
            )
        exclude = Path(observed.stdout.strip())
        if not exclude.is_absolute():
            exclude = root / exclude
        try:
            if exclude.is_symlink() or exclude.parent.is_symlink():
                raise OSError("the local exclusion path is a symlink")
            existing = exclude.read_bytes() if exclude.exists() else b""
            if pattern not in existing.splitlines():
                exclude.parent.mkdir(parents=True, exist_ok=True)
                with exclude.open("ab") as stream:
                    if existing and not existing.endswith(b"\n"):
                        stream.write(b"\n")
                    stream.write(pattern + b"\n")
        except OSError as error:
            return StepRefusal(
                "LaneNotOpened",
                f"could not update {exclude}: {error}",
                "restore a writable, non-symlink Git info/exclude and re-run",
            )
        return None

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
        if worktree.exists() or worktree.is_symlink():
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

    def lane_identity(self, root: Path) -> Principal | LinkedLane | Unobservable:
        """Observe checkout identity from Git, never its directory name."""
        directories = self.observe(
            root, "rev-parse", "--path-format=absolute", "--git-dir", "--git-common-dir"
        )
        if directories.returncode:
            return Unobservable(directories.stderr)
        paths = directories.stdout.splitlines()
        if len(paths) != 2:
            return Unobservable("git rev-parse did not report both Git directories")
        if Path(paths[0]).resolve() == Path(paths[1]).resolve():
            return Principal()
        entries = self._worktree_entries(root)
        if isinstance(entries, StepRefusal):
            return Unobservable(entries.why)
        if not entries or not entries[0].get("HEAD"):
            return Unobservable("git worktree list did not report the principal HEAD")
        branch = self.observe(root, "symbolic-ref", "--quiet", "--short", "HEAD")
        if branch.returncode:
            return Unobservable(
                branch.stderr or "git symbolic-ref did not report the lane branch"
            )
        return LinkedLane(
            root,
            branch.stdout.strip(),
            Path(entries[0]["worktree"]),
            entries[0]["HEAD"],
        )

    def _stale_recovery(
        self, root: Path, lane: RegisteredLane, refused: AdvanceRefusal
    ) -> StepRefusal:
        candidates = retained_candidates(lane.worktree)
        if isinstance(candidates, Blocked):
            return StepRefusal(
                candidates.what,
                candidates.why,
                candidates.how,
                Disposition.Indeterminate,
            )
        anchors = []
        for candidate in candidates:
            ancestry = self.observe(
                lane.worktree, "merge-base", "--is-ancestor", candidate, lane.tip
            )
            if ancestry.unanswered is not None or ancestry.returncode not in (0, 1):
                return self._git_refusal(
                    ancestry,
                    "GitUnavailable",
                    ancestry.stderr,
                    "restore Git",
                    indeterminate=True,
                )
            if ancestry.returncode == 0:
                anchors.append(candidate)
        if anchors:
            maximal = self.observe(
                lane.worktree, "merge-base", "--independent", *anchors
            )
            if maximal.returncode:
                return self._git_refusal(
                    maximal,
                    "GitUnavailable",
                    maximal.stderr,
                    "restore Git",
                    indeterminate=True,
                )
            anchors = maximal.stdout.splitlines()
        if not anchors and not handover_path(lane.worktree).is_file():
            return self._from_advance(refused)
        destination = self._advance.destination(root)
        if isinstance(destination, AdvanceRefusal):
            return self._from_advance(destination)
        merge = (
            f"git -C {shlex.quote(str(lane.worktree))} merge --no-edit {destination}"
        )
        verify = f"des verify --repo-root {shlex.quote(str(lane.worktree))}"
        alternatives = (
            " or ".join(
                f"`{verify} --integrated-candidate {anchor}`" for anchor in anchors
            )
            if anchors
            else f"`{verify}`"
        )
        return StepRefusal(
            refused.what,
            refused.why,
            f"run `{merge}`, then {alternatives}, then "
            f"`{lane_integrate_invocation(root, lane.worktree)}`",
        )

    def integrate(
        self, root: Path, worktree: Path, *, keep_worktree: bool = False
    ) -> IntegratedLane | StepRefusal:
        """Fast-forward the root onto the lane, optionally retaining the lane."""
        registered = self._registered(root, worktree)
        if isinstance(registered, StepRefusal):
            return registered
        not_disposable = self._not_a_disposable_lane(root, registered)
        if not_disposable is not None:
            return not_disposable
        dirty = self._dirty(registered.worktree, removing=not keep_worktree)
        if dirty is not None:
            return dirty
        advanced = self._advance.fast_forward(root, registered.tip)
        if isinstance(advanced, AdvanceRefusal):
            if advanced.what == "IntegrationStale" and advanced.unanswered is None:
                return self._stale_recovery(root, registered, advanced)
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
        not_disposable = self._not_a_disposable_lane(root, registered)
        if not_disposable is not None:
            return not_disposable
        dirty = self._dirty(registered.worktree, removing=True)
        if dirty is not None:
            return dirty
        integrated = self._is_integrated(root, registered)
        if isinstance(integrated, StepRefusal):
            return integrated
        closed = self._close(root, registered)
        if closed is not None:
            return closed
        return registered

    def status(
        self,
        root: Path,
        destination_ref: str | None = None,
        require_integrated: tuple[Path, ...] = (),
    ) -> LaneInventory | StepRefusal:
        """Enumerate every registered lane of this root, reading nothing else.

        One pass measures, per lane, three facts it never collapses: whether
        the lane's tip is an ancestor of the destination (the ONLY delivery
        fact here), which bytes no commit carries, and whether the
        registration still names a usable directory.  It never merges, writes,
        or removes; a finished tip outside the destination is reported exactly
        as what it is -- work the destination does not hold.

        When ``require_integrated`` names lanes, this becomes the caller's
        completion assertion: the named lanes' MEASURED tips are compared
        against the destination, and any lane whose tip is outside it refuses
        the step -- so a completion claim built on this command's success is
        built on ancestry, not on a clean worktree or a lane's own word.
        Content is not consulted here: a retained lane holding ignored bytes
        is still integrated, and its removal is guarded separately.
        """
        workspace = _workspace_paths(root)
        if isinstance(workspace, StepRefusal):
            return workspace
        root = workspace.root
        directory = workspace.lanes
        entries = self._worktree_entries(root)
        if isinstance(entries, StepRefusal):
            return entries
        destination = self._destination_commit(root, destination_ref)
        if isinstance(destination, StepRefusal):
            return destination
        root_path = root.resolve()
        registered_paths: set[Path] = set()
        lanes: list[LaneObservation] = []
        for fields in entries:
            path = Path(fields["worktree"])
            registered_paths.add(path.resolve())
            if path.resolve() == root_path:
                continue  # the destination itself, rendered once from its HEAD
            if _reserved_segment(path, directory):
                continue  # reserved workspace registrations are not lanes
            branch = fields.get("branch") or None
            branch = branch.removeprefix("refs/heads/") if branch else None
            tip = fields.get("HEAD", "").strip()
            prunable = fields.get("prunable")
            try:
                linked = path.is_symlink()
                exists = path.exists()
                read_error: str | None = None
            except OSError as error:
                linked = exists = False
                read_error = str(error)
            content_note: str | None = None
            if read_error is not None:
                # Degrade THIS lane, loudly, and keep the inventory measurable.
                availability = (
                    f"UNMEASURABLE: the registered path could not be "
                    f"inspected: {read_error}"
                )
            elif prunable or not exists:
                availability = (
                    f"MISSING: {prunable or 'the registered directory is absent'}"
                )
                if linked:
                    content_note = "the registered path is a dangling symlink"
            elif "locked" in fields:
                availability = (
                    f"LOCKED: {fields.get('locked') or 'locked by Git registration'}"
                )
            else:
                availability = "AVAILABLE"
            integrated = self._ancestor_of(root, tip, destination)
            if isinstance(integrated, StepRefusal):
                return integrated
            changes: tuple[str, ...] | None = None
            ignored: tuple[str, ...] = ()
            if exists and read_error is None:
                observed = self._content(path)
                if isinstance(observed, StepRefusal):
                    return observed
                changes, ignored, content_note = observed
            lanes.append(
                LaneObservation(
                    path,
                    branch,
                    tip,
                    integrated,
                    changes,
                    ignored,
                    availability,
                    self._lane_next(
                        root,
                        RegisteredLane(path, branch, tip),
                        availability,
                        integrated,
                        (changes, ignored),
                    ),
                    content_note,
                )
            )
        unregistered = self._unregistered_entries(directory, registered_paths)
        refused = self._requirement(root, destination, lanes, require_integrated)
        if refused is not None:
            return refused
        return LaneInventory(root, destination, tuple(lanes), unregistered)

    def _destination_commit(
        self, root: Path, destination_ref: str | None
    ) -> str | StepRefusal:
        """The commit reachability is measured against: HEAD unless named."""
        if destination_ref is None:
            destination = self._advance.destination(root)
            if isinstance(destination, AdvanceRefusal):
                return self._from_advance(destination)
            return destination
        observed = self.observe(
            root, "rev-parse", "--verify", f"{destination_ref}^{{commit}}"
        )
        if observed.returncode:
            return self._git_refusal(
                observed,
                "InvalidDestination",
                f"{destination_ref!r} does not name a commit in {root}",
                "re-run with a commit this repository resolves, or omit "
                "--destination to measure against the root's own HEAD",
            )
        return observed.stdout.strip()

    def _ancestor_of(
        self, root: Path, tip: str, destination: str
    ) -> bool | StepRefusal | None:
        """Whether `tip` is destination history; refusal when Git never answered.

        `None` is for a tip that does not exist to measure (an empty
        registration), never for a Git that failed: a Git that never ANSWERED
        is never reported as a repository fact.
        """
        if not tip:
            return None
        ancestry = self.observe(root, "merge-base", "--is-ancestor", tip, destination)
        if ancestry.unanswered is not None:
            return self._git_refusal(
                ancestry, "GitUnavailable", ancestry.stderr, "restore Git"
            )
        if ancestry.returncode == 0:
            return True
        if ancestry.returncode == 1:
            return False
        return self._git_refusal(
            ancestry, "GitUnavailable", ancestry.stderr, "restore Git"
        )

    def _content(
        self, worktree: Path
    ) -> tuple[tuple[str, ...] | None, tuple[str, ...], str | None] | StepRefusal:
        """The bytes the worktree holds beyond its commit, in two classes.

        A Git that never ANSWERED is a refusal (the whole inventory is built
        on Git).  A Git that answered and FAILED on this one path degrades
        THIS lane's content to unobservable, naming why, so one unreadable
        registration cannot discard the measured rows of every other lane.
        """
        observed = self.observe(
            worktree,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--ignored=matching",
        )
        if observed.unanswered is not None:
            return self._git_refusal(
                observed, "GitUnavailable", observed.stderr, "restore Git"
            )
        if observed.returncode:
            return (
                None,
                (),
                f"git status failed in the registered path: {observed.stderr.strip()}",
            )
        carried = []
        ignored = []
        for line in observed.stdout.splitlines():
            if line.startswith("!! "):
                path = line[3:].strip()
                if path == "lanes" or path.startswith("lanes/"):
                    continue  # nested lanes are their own protected jurisdiction
                ignored.append(path)
            elif line.strip():
                carried.append(line)
        return tuple(carried), tuple(ignored), None

    def _unregistered_entries(
        self, directory: Path, registered: set[Path]
    ) -> tuple[Path, ...]:
        """Lane-directory entries NO registration owns -- disk with no Git fact.

        Dot-leading entries are skipped: the lane name grammar cannot produce
        them, so they are reserved infrastructure (candidate and verification
        workspaces), never orphaned lanes.
        """
        if not directory.is_dir() or directory.is_symlink():
            return ()
        return tuple(
            child
            for child in sorted(directory.iterdir())
            if not child.name.startswith(".") and child.resolve() not in registered
        )

    def _requirement(
        self,
        root: Path,
        destination: str,
        lanes: list[LaneObservation],
        require_integrated: tuple[Path, ...],
    ) -> StepRefusal | None:
        """The caller's opt-in completion assertion over MEASURED tips.

        Every named lane is judged in ONE pass: the refusal reports all
        independent failures together, numbered, because reporting the first
        and waiting for a second run would bill the caller N dispatches for N
        defects it could have seen at once.  A single failure keeps the exact
        rendering it always had; any unmeasurable tip makes the whole refusal
        Indeterminate -- a pass built on a tip nobody could observe is no pass.
        """
        if not require_integrated:
            return None
        measured = {lane.worktree.resolve(): lane for lane in lanes}
        problems: list[StepRefusal] = []
        unmeasured = False
        for named in require_integrated:
            lane = measured.get(named.resolve())
            if lane is None:
                problems.append(
                    StepRefusal(
                        "LaneNotRegistered",
                        f"{named} is not a worktree of {root}, so its integration "
                        "cannot be asserted",
                        "pass the path `des lane open` reported for the lane, or "
                        "run this step without --require-integrated to see the "
                        "lanes this root has",
                    )
                )
            elif lane.integrated is None:
                unmeasured = True
                problems.append(
                    StepRefusal(
                        "IntegrationUnmeasured",
                        f"the tip of {named} could not be measured against "
                        f"destination {destination}",
                        "restore Git access and re-run this assertion; it refuses "
                        "to pass on a tip it could not observe",
                        Disposition.Indeterminate,
                    )
                )
            elif not lane.integrated:
                problems.append(
                    StepRefusal(
                        "LaneNotIntegrated",
                        f"the named lane {named} is not delivered: its tip "
                        f"{lane.tip} is not an ancestor of destination "
                        f"{destination}, so a completion claim must not stand on "
                        "this assertion",
                        f"integrate it with `des lane integrate --repo-root {root} "
                        f"--worktree {named}`, or preserve its commits elsewhere, "
                        "then re-run this assertion; it never merges by itself",
                    )
                )
        if not problems:
            return None
        if len(problems) == 1:
            return problems[0]
        uniform = len({problem.what for problem in problems}) == 1
        what = problems[0].what if uniform else "RequirementsRefused"
        why = f"{len(problems)} named lanes refuse this requirement: " + " ".join(
            f"({number}) {problem.why}" for number, problem in enumerate(problems, 1)
        )
        how = " ".join(
            f"({number}) {problem.how}" for number, problem in enumerate(problems, 1)
        )
        return StepRefusal(
            what,
            why,
            how,
            Disposition.Indeterminate if unmeasured else Disposition.Refusal,
        )

    def _lane_next(
        self,
        root: Path,
        lane: RegisteredLane,
        availability: str,
        integrated: bool | None,
        content: tuple[tuple[str, ...] | None, tuple[str, ...]],
    ) -> str:
        """The next command this lane itself implies -- advisory data, always.

        A MISSING registration is cleaned PER LANE or not at all: a global
        prune sweeps every prunable registration of the root, and a detached
        registration can be the ONLY ref to its tip -- executing a prune HOW
        has destroyed sibling work, so no advice here ever names one.  An
        unintegrated missing lane is anchored BEFORE any removal is named:
        retain the bytes first, remove registration residue only after the
        tip provably lives in a ref the destination does not hold hostage.
        """
        worktree, branch, tip = lane.worktree, lane.branch, lane.tip
        changes, ignored = content
        if availability.startswith("UNMEASURABLE"):
            return "restore read access to the registered path, then re-run this step"
        if availability.startswith("MISSING"):
            if integrated:
                return (
                    "the measured tip is already in the destination, and this "
                    "clears only this registration, never the root's other "
                    "registrations: after its owner confirms no active use, "
                    f"git -C {root} worktree remove {worktree}"
                )
            if branch:
                return (
                    f"the branch {branch} still anchors tip {tip}, so retain "
                    "it before anything is cleared, and clear only this "
                    "registration, never the root's other registrations: "
                    f"(1) git -C {root} rev-parse refs/heads/{branch}; "
                    f"(2) git -C {root} worktree remove {worktree}; "
                    f"(3) git -C {root} worktree add {worktree} {branch}; "
                    "then integrate normally"
                )
            return (
                "the registration is this tip's only ref, so anchor a "
                "recoverable branch before anything is cleared, and clear "
                "only this registration, never the root's other "
                "registrations: "
                f"(1) git -C {root} branch recover/{worktree.name} {tip}; "
                f"(2) git -C {root} worktree remove {worktree}; "
                f"(3) git -C {root} worktree add {worktree} "
                f"recover/{worktree.name}; then integrate normally"
            )
        if availability.startswith("LOCKED"):
            return f"git -C {root} worktree unlock {worktree}"
        closing = "finalize" if integrated else "integrate"
        invocation = f"des lane {closing} --repo-root {root} --worktree {worktree}"
        if changes:
            return (
                "commit what belongs to the lane, or remove what does not, in "
                f"that worktree, then {invocation}"
            )
        if ignored:
            return (
                "preserve the named ignored bytes outside the lane, or delete "
                f"them deliberately in it, then {invocation}"
            )
        if integrated:
            return f"the lane tip is in the destination; cleanup is available as {invocation}"
        return invocation

    def _not_a_disposable_lane(
        self, root: Path, lane: RegisteredLane
    ) -> StepRefusal | None:
        """Refuse before cleanup when ``lane`` IS the destination workspace itself.

        Checked by path equality against ``root``, not by asking Git which
        worktree is "main": the destination can itself be a linked worktree,
        so the only fact this step owns is that ``lane`` is the workspace it
        was asked to integrate into -- never a claim that Git would refuse to
        remove it, which does not hold for every destination.
        """
        if lane.worktree.resolve() != root.resolve():
            return None
        return StepRefusal(
            "NotALane",
            f"{lane.worktree} is {root}'s own destination workspace, not a "
            "disposable lane -- this step never removes the workspace it "
            "integrates into",
            "pass the worktree path `des lane open` reported for the lane you "
            f"want to close, for example `des lane finalize --repo-root {root} "
            "--worktree <the lane path>`",
        )

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

    def _worktree_entries(self, root: Path) -> tuple[dict[str, str], ...] | StepRefusal:
        """Every registered worktree of this root, in Git's own enumeration.

        ONE observation and ONE parser over the registration table for every
        consumer: `integrate` and `finalize` look one caller-named path up in
        it, `status` enumerates it whole.  A predicate and its enumerator read
        the same source, so neither can drift from the other.
        """
        listed = self.observe(root, "worktree", "list", "--porcelain")
        if listed.returncode:
            return self._git_refusal(
                listed, "GitUnavailable", listed.stderr, "restore Git"
            )
        entries = []
        for entry in listed.stdout.split("\n\n"):
            fields = dict(
                [*line.split(" ", 1), ""][:2] for line in entry.splitlines() if line
            )
            if fields.get("worktree"):
                entries.append(fields)
        return tuple(entries)

    def _registered(self, root: Path, worktree: Path) -> RegisteredLane | StepRefusal:
        """The lane as GIT reports it -- its real branch and its real tip.

        Measured rather than taken from the caller: a path is what the caller
        knows, while the branch and the tip are what the repository knows, and
        the step must integrate the second.
        """
        entries = self._worktree_entries(root)
        if isinstance(entries, StepRefusal):
            return entries
        for fields in entries:
            listed_path = fields["worktree"]
            if Path(listed_path).resolve() != worktree:
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

    def _dirty(self, worktree: Path, *, removing: bool) -> StepRefusal | None:
        """Refuse a lane holding bytes no commit carries, and NAME them.

        When the lane will be REMOVED by this step, ignored bytes are refused
        too: Git refuses to remove a worktree holding untracked files, but
        deletes one holding only ignored files without a word, so ignored
        evidence would vanish behind a "clean" status line.
        """
        nested = worktree / "lanes"
        nested_status = None
        if nested.exists() or nested.is_symlink():
            nested_status = self.observe(
                worktree,
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
                "--ignored=matching",
                "--",
                "lanes",
            )
            if nested_status.returncode:
                return self._git_refusal(
                    nested_status,
                    "GitUnavailable",
                    nested_status.stderr,
                    "restore Git access before inspecting nested lane content",
                )
        if nested_status is not None and nested_status.stdout.strip():
            return StepRefusal(
                "LaneDirty",
                f"{nested} holds uncommitted or ignored nested content: "
                + "; ".join(nested_status.stdout.splitlines()),
                "integrate or preserve and relocate nested lanes before closing "
                "their containing worktree; never force removal",
            )
        observed = self.observe(
            worktree,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            *(("--ignored=matching",) if removing else ()),
        )
        if observed.returncode:
            return self._git_refusal(
                observed,
                "GitUnavailable",
                observed.stderr,
                "restore Git",
            )
        if not observed.stdout.strip():
            return None
        carried = []
        ignored = []
        for line in observed.stdout.splitlines():
            if line.startswith("!! "):
                path = line[3:].strip()
                if path == "lanes" or path.startswith("lanes/"):
                    continue  # the nested-lane check above owns that jurisdiction
                ignored.append(path)
            elif line.strip():
                carried.append(line)
        if carried:
            return StepRefusal(
                "LaneDirty",
                f"{worktree} holds changes no commit carries, so integrating it "
                "would leave them behind: " + "; ".join(carried),
                "commit what belongs to the lane, or remove what does not, in that "
                "worktree, then re-run this step; this step never discards a byte "
                "it did not see committed",
            )
        if ignored:
            return StepRefusal(
                "LaneIgnoredContent",
                f"{worktree} reads as clean to a plain `git status`, but holds "
                "ignored bytes no commit carries ("
                + ", ".join(ignored)
                + "), and removing the lane would delete them without a word: "
                "Git refuses untracked files yet removes ignored ones silently",
                "preserve those bytes outside the lane, or delete them "
                "deliberately in the worktree, then re-run this step; a lane is "
                "never removed merely because Git reports it clean",
            )
        return None

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
                indeterminate=True,
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

        The WHY below states one fact true of both callers: by the time
        `_close` runs, the lane tip is already present in the destination --
        `integrate` just fast-forwarded onto it, `finalize` just proved it an
        ancestor -- so neither caller needs its own wording for it.
        """
        done = "the lane tip is already present in the destination"
        removed = self.observe(root, "worktree", "remove", str(lane.worktree))
        if removed.returncode:
            return self._git_refusal(
                removed,
                "CleanupUnproven",
                f"{done}, but {lane.worktree} could not be "
                f"removed: {removed.stderr.strip()}",
                f"inspect {lane.worktree} and remove it once you have read what "
                "it holds; the integration itself is done and must not be repeated",
                indeterminate=True,
            )
        if lane.branch is None:
            return None
        deleted = self.observe(root, "branch", "-d", lane.branch)
        if deleted.returncode:
            return self._git_refusal(
                deleted,
                "CleanupUnproven",
                f"{done} and {lane.worktree} is gone, but "
                f"the branch {lane.branch} could not be deleted: "
                f"{deleted.stderr.strip()}",
                f"run `git -C {root} branch -d {lane.branch}` and read what it "
                "refuses; the integration itself is done and must not be repeated",
                indeterminate=True,
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
        f"des po --repo-root {lane.worktree} "
        "(--project | --epic ID | --feature ID | --slice FEATURE_ID SLICE_ID) "
        "--input - -- closed host DISCUSS facts on stdin, constructed "
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
    opening = steps.add_parser(
        "open",
        help="create a lane beneath the configured project workspace root",
        description="Create a durable project-local lane, independent of TMPDIR. "
        "Excludes its configured directory in Git info/exclude, not tracked .gitignore.",
    )
    add_repo_root_argument(opening, "--repo-root", type=Path, required=True)
    opening.add_argument(
        "--name", required=True, help="one unique lane name in this project"
    )
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
    reporting = steps.add_parser(
        "status",
        help="report every registered lane of this root, read-only",
        description="Enumerate the lanes this root has registered: each lane's "
        "tip measured against the destination, the bytes no commit carries, "
        "and the registration's availability. Observes only -- never merges, "
        "writes, or removes.",
    )
    add_repo_root_argument(reporting, "--repo-root", type=Path, required=True)
    reporting.add_argument(
        "--destination",
        default=None,
        help="measure reachability against this commit, not the root's HEAD",
    )
    reporting.add_argument(
        "--require-integrated",
        type=Path,
        action="append",
        default=[],
        metavar="WORKTREE",
        help="assert every named lane's measured tip is in the destination; "
        "refuses otherwise (repeatable)",
    )
    return parser


def _integrated_word(integrated: bool | None) -> str:
    if integrated is None:
        return "unknown -- the tip was not measurable against the destination"
    return "yes" if integrated else "no -- the tip is outside the destination"


def _content_word(
    changes: tuple[str, ...] | None,
    ignored: tuple[str, ...],
    note: str | None = None,
) -> str:
    """The CONTENT row: what the worktree holds beyond its commit, or so."""
    if changes is None:
        return f"unobservable -- {note or 'the registration names no directory'}"
    parts = []
    for named, paths in (("uncommitted/untracked", changes), ("ignored", ignored)):
        if not paths:
            continue
        listed = ", ".join(paths[:_NAMED_PATHS])
        more = len(paths) - _NAMED_PATHS
        parts.append(f"{named}: {listed}" + (f" and {more} more" if more > 0 else ""))
    return "; ".join(parts) if parts else "clean"


def _aggregate_next(inventory: LaneInventory) -> str:
    for lane in inventory.lanes:
        if lane.next_step:
            return lane.next_step
    if inventory.unregistered:
        return (
            "inspect each UNREGISTERED path -- no lane step registered it, so "
            "no lane step removes it"
        )
    return _NO_STEP_OWED


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
    if args.step == "status":
        inventory = steps.status(root, args.destination, tuple(args.require_integrated))
        if isinstance(inventory, StepRefusal):
            return _refuse(
                inventory,
                f"des lane status --repo-root {root} -- after the HOW above",
            )
        fields = [
            f"DESTINATION: {inventory.destination}",
            f"DESTINATION-HEAD: {inventory.head}",
        ]
        if args.require_integrated:
            fields.append(
                "REQUIRE-INTEGRATED: satisfied -- every named lane's measured "
                "tip is an ancestor of the destination"
            )
        for path in inventory.unregistered:
            fields.append(f"UNREGISTERED: {path}")
        for lane in inventory.lanes:
            fields.extend(
                [
                    f"LANE: {lane.worktree}",
                    f"BRANCH: {lane.branch or '(detached)'}",
                    f"TIP: {lane.tip}",
                    f"INTEGRATED: {_integrated_word(lane.integrated)}",
                    f"CONTENT: {_content_word(lane.changes, lane.ignored, lane.content_note)}",
                    f"AVAILABILITY: {lane.availability}",
                    f"NEXT: {lane.next_step}",
                ]
            )
        _succeed(fields, _aggregate_next(inventory))
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
