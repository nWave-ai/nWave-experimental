"""Bounded maintenance of DES-owned disposable verification workspaces.

Ownership is a POSITIVE proof, two ways and no third -- location is never
authority:

* candidate checkouts: a per-candidate receipt (``.nwave-des-candidate.json``)
  written by the PRODUCER at creation, binding version, candidate, and this
  repository's common Git dir. A registered worktree without a matching
  receipt is someone else's checkout -- preserved, never force-removed;
* generated output caches: the creation marker DES wrote when it FIRST
  materialized the root (never for a root that already existed), or the
  project's explicit ``adopt_outputs`` declaration, both bound to the same
  common Git dir;
* the reuse workspace: byte-exact ownership metadata plus phase ``idle``.

Ownership is re-proven at EVICTION time against the repository's CURRENT
tracked set (``HEAD`` tree plus staged index adds): a cache root that DES
once marked can later acquire committed or staged project files -- a
cache -> tracked transition with no config change -- and is then project
source again: preserved with the named path, recovered with the native
property tool, never blind removal.

Quiescence: two independent gates. The exclusive verification lease
proves no DES measurement writer is active -- it does NOT cover
manually-run native builds; those are out of contract for marker/adoption
roots (the exclusive-managed-output contract) and protected by
non-ownership everywhere else. Owned output caches and the reuse
workspace are additionally gated on the OBSERVED native quiescence
receipt -- the reuse metadata's ``idle`` phase, the same Core guard the
runner writes after its writers are reaped: after a crash the receipt is
non-idle and every owned cache is preserved even with the lease free.
Marker confidence is ownership, never a quiescence observation. Age is
NEVER an ownership signal. Platform capability limit: the group observer
requires a POSIX-capable platform (not Linux specifically -- any platform
with os.killpg semantics qualifies); the OBSERVED smoke coverage is Linux
only. On a platform without the observer a measured cold checkout is
RETAINED UNPROVEN (receipt non-idle, worktree kept, recovery named in
the report) -- an unproven retention is not portable proof of quiescence,
never a traceback, and no platform-specific job API is implemented.

Budget accounting is OBSERVED, not assumed: an unobservable registry or an
unreadable size degrades the whole budget to INDETERMINATE -- never a
fake-empty green. Pressure exists only when a limit is configured AND the
observed total exceeds it; without pressure the only action is empty
residue removal. Post-eviction the budget is re-observed and that
re-observation is authoritative: an unmet budget is an explicit
maintenance failure and no new DES growth may start on top of it.

Cache VALIDITY is deliberately not checked here: native commands validate
and rebuild their own caches.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from des.adapters.driven.config.workspace_paths import (
    CANDIDATE_RECEIPT,
    OWNERSHIP_MARKER,
    WorkspacePaths,
)
from des.adapters.driven.git.git_observation import observe_text
from des.application.handover import Blocked, DeliveryLock
from des.application.verification_workspace import acquire_verification_lock


@dataclass(frozen=True)
class WorkspaceMaintenance:
    """The one observable maintenance result; ``report`` carries step facts.

    ``within_limit`` is tri-state: True (budget met), False (budget
    unmet), None (INDETERMINATE -- an unobservable registry, size, or a
    declared root behind an intermediate symlink can never be honestly
    called green). ``failure`` is a maintenance-level failure
    (unobservable registry, unmet budget with unknown/protected
    blockers); ``None`` means the maintenance itself is healthy -- it is
    independent of the candidate verification verdict.
    """

    report: tuple[str, ...]
    evicted: tuple[str, ...]
    preserved: tuple[str, ...]
    within_limit: bool | None
    failure: str | None = None


def workspace_maintenance(
    paths: WorkspacePaths,
    *,
    lease_held: bool = False,
    apply: bool | None = None,
) -> WorkspaceMaintenance:
    """Report (and, in automatic mode, apply) bounded workspace cleanup.

    ``apply=None`` follows ``verification.reuse.workspace.automatic``;
    ``apply=False`` forces the explicit dry run. ``lease_held`` marks the
    verification lease as already held by the caller. Budget eviction runs
    only under actual pressure (a configured limit and an observed total
    above it); empty residue removal is the separate always-hygienic
    action, also under lease.
    """
    effective = paths.automatic if apply is None else apply
    limit = paths.cache_limit_bytes
    observed = _observe(paths)
    if observed is None:
        report = (
            "WORKSPACE-MAINTENANCE: workspace registry or sizes unobservable; "
            "budget not green and nothing evicted",
        )
        return WorkspaceMaintenance(report, (), (), None, "workspace unobservable")
    total, candidates, output_bytes, _reuse_bytes = observed
    within = limit is None or total <= limit
    report = [_summary(paths, candidates, total, output_bytes, within)]
    if not effective:
        report.append(
            "WORKSPACE-MAINTENANCE: dry-run; automatic eviction is disabled "
            "(verification.reuse.workspace.automatic)"
        )
        return WorkspaceMaintenance(report, (), (), within)
    pressure = limit is not None and total > limit
    residue = _empty_residue(paths.candidate, registered=candidates)
    if not pressure and not residue:
        report.append(
            "WORKSPACE-MAINTENANCE: no budget pressure; nothing to evict"
            if limit is not None
            else "WORKSPACE-MAINTENANCE: no configured limit; budget eviction inactive"
        )
        return WorkspaceMaintenance(report, (), (), within)
    lock: DeliveryLock | None = None
    evicted: list[str] = []
    preserved: list[str] = []
    try:
        if not lease_held:
            acquired = acquire_verification_lock(paths.root)
            if isinstance(acquired, Blocked):
                report.append(
                    "WORKSPACE-MAINTENANCE: verification lease held elsewhere; "
                    "nothing evicted while a DES writer may be active"
                )
                return WorkspaceMaintenance(report, (), (), within)
            lock = acquired
        over = total - limit if pressure else None
        quiescent, quiescence_note = _native_quiescence(paths)
        tracked = None
        if over is not None:
            tracked = _tracked_paths(paths)
            if tracked is None:
                preserved.append(
                    "generated output caches: Git tracked-source guard "
                    "unobservable; preserved"
                )
        if over is not None:
            for path, size in candidates:
                if over <= 0:
                    break
                outcome = _remove_candidate(paths, path)
                if outcome is None:
                    evicted.append(str(path))
                    over -= size
                else:
                    preserved.append(f"{path}: {outcome}")
            if quiescent and tracked is not None:
                for output, root, size in _owned_output_roots(paths, output_bytes):
                    if over <= 0:
                        break
                    blocking = _tracked_inside(output, tracked)
                    if blocking is not None:
                        preserved.append(
                            f"{root}: currently tracked project source "
                            f"{blocking} is inside; recover that path with "
                            "the native property tool -- never blind removal"
                        )
                        continue
                    outcome = _evict_output_cache(paths, root)
                    if outcome is None:
                        evicted.append(f"{root}: owned generated cache")
                        over -= size
                    else:
                        preserved.append(f"{root}: {outcome}")
                if over > 0:
                    evicted_over, note = _evict_reuse_workspace(paths)
                    if evicted_over:
                        evicted.append(str(paths.verification))
                    if note is not None:
                        preserved.append(note)
            elif over > 0:
                preserved.append(
                    "owned generated cache and reuse workspace: "
                    f"{quiescence_note}; preserved"
                )
        for path in residue:
            try:
                path.rmdir()
            except OSError as error:
                preserved.append(f"{path}: {type(error).__name__}: {error}")
            else:
                evicted.append(f"{path}: empty residue")
        post = _observe(paths)
        report.extend(f"WORKSPACE-MAINTENANCE: evicted {item}" for item in evicted)
        report.extend(f"WORKSPACE-MAINTENANCE: preserved {item}" for item in preserved)
        if post is None:
            report.append(
                "WORKSPACE-MAINTENANCE: post-eviction re-observation failed; "
                "budget not green"
            )
            return WorkspaceMaintenance(
                tuple(report),
                tuple(evicted),
                tuple(preserved),
                None,
                "workspace unobservable after eviction",
            )
        post_total = post[0]
        within = limit is None or post_total <= limit
        if not within:
            failure = (
                "budget unmet; remaining materializations are unknown or "
                "protected and no owned-inactive cache was left to evict"
            )
            report.append(
                "WORKSPACE-MAINTENANCE: over limit with no owned-inactive "
                "materialization left to evict; new DES workspace growth is "
                "refused until the named unknown caches are removed or adopted"
            )
            return WorkspaceMaintenance(
                tuple(report), tuple(evicted), tuple(preserved), within, failure
            )
        return WorkspaceMaintenance(
            tuple(report), tuple(evicted), tuple(preserved), within
        )
    finally:
        if lock is not None:
            lock.release()


def _summary(
    paths: WorkspacePaths,
    candidates: list[tuple[Path, int]],
    total: int,
    output_bytes: dict[str, int],
    within: bool,
) -> str:
    limit = paths.cache_limit_bytes
    return (
        f"WORKSPACE-MAINTENANCE: reuse={_reuse_phase(paths)} "
        f"candidates={len(candidates)} "
        f"outputs_bytes={sum(output_bytes.values())} bytes={total} "
        f"limit={'unbounded' if limit is None else limit} "
        f"within-limit="
        f"{'yes' if within else 'no' if within is not None else 'unknown'}"
    )


def _observe(
    paths: WorkspacePaths,
) -> tuple[int, list[tuple[Path, int]], dict[str, int], int] | None:
    """One consistent observation of every budgeted materialization.

    Returns ``(total, candidates_with_sizes, output_sizes, reuse_bytes)``
    or ``None`` when any component is unobservable -- an unobservable
    budget is INDETERMINATE, never a fake-empty green.
    """
    code, out = _git(paths.root, "worktree", "list", "--porcelain")
    if code:
        return None
    candidates: list[tuple[Path, int]] = []
    for line in out.splitlines():
        if not line.startswith("worktree "):
            continue
        path = Path(line[len("worktree ") :])
        if path != paths.candidate and path.is_relative_to(paths.candidate):
            size = _tree_bytes(path)
            if size is None:
                return None
            candidates.append((path, size))
    candidates.sort(key=lambda item: item[0].as_posix())
    reuse_bytes = _tree_bytes(paths.verification)
    if reuse_bytes is None:
        return None
    output_sizes: dict[str, int] = {}
    for output in paths.outputs or ():
        root = _output_root(paths, output)
        if root is None:
            return None
        if _intermediate_symlink(paths.root, root):
            # A declared root reached through an intermediate symlink
            # would count FOREIGN bytes: unknown, never walked.
            return None
        size = _tree_bytes(root)
        if size is None:
            return None
        output_sizes[output] = size
    # Unknown bytes under the candidate root -- unregistered checkouts,
    # foreign payloads, loose files -- are budget-visible even though they
    # are never evictable: a blocker that cannot be counted cannot be
    # honestly refused against.
    known = {path for path, _ in candidates}
    unknown_bytes = 0
    if paths.candidate.is_dir():
        try:
            children = list(paths.candidate.iterdir())
        except OSError:
            return None
        for child in children:
            if child in known:
                continue
            size = _tree_bytes(child)
            if size is None:
                return None
            unknown_bytes += size
    total = (
        reuse_bytes
        + sum(size for _, size in candidates)
        + sum(output_sizes.values())
        + unknown_bytes
    )
    return total, candidates, output_sizes, reuse_bytes


def _common_dir(paths: WorkspacePaths) -> str | None:
    code, out = _git(
        paths.root, "rev-parse", "--path-format=absolute", "--git-common-dir"
    )
    return str(Path(out).resolve()) if not code else None


def _git(root: Path, *args: str) -> tuple[int, str]:
    result = observe_text(root, *args)
    return result.returncode, (result.stderr or result.stdout).strip()


def _ownership_fields(recorded: object, keys: tuple[str, ...]) -> dict[str, str] | None:
    """The ONE bounded typed decode of ownership JSON bytes.

    Admits only a JSON object whose every requested field is a nonempty
    string; absent, malformed, or mistyped documents (including
    wrong-typed values where ``Path()`` would raise) decode as ``None`` --
    never an exception, never a fallback to green. Integer fields (the
    version) are checked by ``_version_one``.
    """
    if not isinstance(recorded, dict):
        return None
    fields: dict[str, str] = {}
    for key in keys:
        value = recorded.get(key)
        if not isinstance(value, str) or not value:
            return None
        fields[key] = value
    return fields


def _version_one(recorded: object) -> bool:
    return (
        isinstance(recorded, dict)
        and type(recorded.get("version")) is int
        and recorded["version"] == 1
    )


def _remove_candidate(paths: WorkspacePaths, path: Path) -> str | None:
    """Remove one candidate worktree; a preservation reason, or None.

    The worktree REGISTRY is not DES ownership: only the producer's
    per-candidate receipt, bound to this repository's common Git dir, the
    exact registered path, and the checkout's CURRENT candidate identity,
    authorizes a force removal -- and only at phase ``idle``. Absent,
    malformed, or mistyped receipts (including wrong-typed JSON fields)
    decode as "not ours": preserved with a named reason, never an
    exception.
    """
    common = _common_dir(paths)
    if common is None:
        return "Git ownership unprovable; preserved"
    try:
        receipt = json.loads((path / CANDIDATE_RECEIPT).read_bytes())
    except (OSError, ValueError):
        receipt = None
    fields = _ownership_fields(
        receipt, ("common_git_dir", "workspace", "candidate", "phase")
    )
    if fields is None or not _version_one(receipt):
        return "receipt is absent or malformed; preserved"
    try:
        bound = (
            Path(fields["common_git_dir"]).resolve() == Path(common)
            and Path(fields["workspace"]) == path
        )
    except (OSError, ValueError, RuntimeError):
        return "receipt is malformed for this platform; preserved"
    if not bound:
        return "receipt does not bind this registered checkout; preserved"
    code, head = _git(path, "rev-parse", "HEAD")
    if code or head != fields["candidate"]:
        return (
            "receipt's candidate identity does not match the checkout's "
            "current HEAD; preserved"
        )
    if fields["phase"] != "idle":
        return (
            f"receipt phase is {fields['phase']!r}, not idle: interrupted "
            "native execution may hold pending evidence; recover per the "
            "receipt, preserved"
        )
    code, out = _git(paths.root, "worktree", "remove", "--force", str(path))
    return None if not code else f"git worktree remove refused: {out}"


def _empty_residue(
    candidate_root: Path, *, registered: list[tuple[Path, int]]
) -> list[Path]:
    """Unregistered, EMPTY directories directly under the candidate root.

    A registered worktree is never residue; a directory with contents is
    unknown bytes -- preserved, never swept. Only the candidate root's own
    children are considered: one bounded level, not a recursive sweep.
    """
    if not candidate_root.is_dir():
        return []
    known = {path for path, _ in registered}
    found: list[Path] = []
    for child in candidate_root.iterdir():
        if child in known or not child.is_dir():
            continue
        try:
            if not any(child.iterdir()):
                found.append(child)
        except OSError:
            continue
    return found


def _native_quiescence(paths: WorkspacePaths) -> tuple[bool, str]:
    """The Core observed-native-quiescence receipt: metadata phase ``idle``.

    Ownership markers and adoption declare WHO may evict a root; only
    this observed receipt says the last native generation actually
    finished and its writers were reaped. A missing, foreign, unreadable,
    or non-idle receipt preserves every owned cache -- including after a
    crash with the lease free -- because marker confidence is not a
    quiescence observation.
    """
    metadata = paths.evidence / "verification-reuse.json"
    if not metadata.exists():
        return False, "no native quiescence receipt (no reuse metadata)"
    try:
        recorded = json.loads(metadata.read_bytes())
    except (OSError, ValueError):
        return False, "native quiescence receipt unreadable"
    if not _metadata_proves_ownership(paths, recorded):
        return False, "native quiescence receipt does not prove this repository"
    phase = recorded.get("phase")
    if phase != "idle":
        return False, f"native quiescence phase {phase!r}"
    return True, "idle"


def _tracked_paths(paths: WorkspacePaths) -> set[str] | None:
    """Every CURRENT tracked path: HEAD's tree plus the index's staged adds.

    The eviction-time source guard: a cache root that DES once created can
    later acquire committed or staged project files (a cache -> tracked
    transition with no config change), so ownership must be re-proven
    against the repository's CURRENT tracked set, not the bytes it held
    at creation. ``None`` means Git is unobservable and nothing may be
    evicted.
    """
    code, out = _git(paths.root, "ls-tree", "-r", "-z", "HEAD")
    if code:
        return None
    tracked = {entry.split("\t", 1)[-1] for entry in out.split("\0") if entry}
    code, out = _git(paths.root, "ls-files", "-z")
    if code:
        return None
    tracked.update(path for path in out.split("\0") if path)
    return tracked


def _tracked_inside(output: str, tracked: set[str]) -> str | None:
    """One tracked path at or under the output root, or None if disjoint."""
    for path in sorted(tracked):
        if path == output or path.startswith(output + "/"):
            return path
    return None


def _output_root(paths: WorkspacePaths, output: str) -> Path | None:
    """The principal-side root of one declared output, or None if unsafe.

    A declaration that is not a normalized repository-relative path is
    never joined onto the repository root -- an absolute or escaping
    spelling would otherwise silently point the accounting outside the
    repository. ``None`` degrades the budget to INDETERMINATE; the same
    malformed declaration keeps its pre-existing refusal at workspace
    acquisition.
    """
    path = PurePosixPath(output)
    if (
        path.is_absolute()
        or path.as_posix() != output
        or "\\" in output
        or any(
            part in {"", ".", "..", ".git", ".nwave", ".venv"} or part.startswith("~")
            for part in path.parts
        )
    ):
        return None
    return paths.root.joinpath(*path.parts)


def _owned_output_roots(
    paths: WorkspacePaths, output_bytes: dict[str, int]
) -> list[tuple[str, Path, int]]:
    """Declared output caches whose ownership is PROVED, path-sorted.

    Creation marker or explicit adoption, both bound to this repository's
    common Git dir. An unknown preexisting cache -- including one carrying
    a marker written by ANOTHER repository -- is accounted but never
    evicted.
    """
    common = _common_dir(paths)
    if common is None:
        return []
    owned: list[tuple[str, Path, int]] = []
    for output in paths.outputs or ():
        root = _output_root(paths, output)
        if root is None or not root.is_dir() or root.is_symlink():
            continue
        if output in paths.adopted:
            owned.append((output, root, output_bytes.get(output, 0)))
            continue
        try:
            recorded = json.loads((root / OWNERSHIP_MARKER).read_bytes())
        except (OSError, ValueError):
            recorded = None
        fields = _ownership_fields(recorded, ("output", "common_git_dir"))
        if fields is None or not _version_one(recorded):
            continue
        try:
            bound = fields["output"] == output and Path(
                fields["common_git_dir"]
            ).resolve() == Path(common)
        except (OSError, ValueError, RuntimeError):
            continue
        if bound:
            owned.append((output, root, output_bytes.get(output, 0)))
    return sorted(owned, key=lambda item: item[1].as_posix())


def _evict_output_cache(paths: WorkspacePaths, root: Path) -> str | None:
    """Remove one OWNED generated cache root; a refusal string, or None.

    Deletion re-proves the path AT REMOVAL TIME with anchored, no-follow
    traversal: the repository root is opened O_DIRECTORY|O_NOFOLLOW and
    every component of the declared relative path is opened through it
    with O_NOFOLLOW, so an intermediate symlink (``a`` -> outside) can
    never redirect the removal onto someone else's subtree. The tree is
    then emptied and removed THROUGH the anchored directory descriptors
    (``unlinkat``/``rmdir`` with ``dir_fd`` at every level). Platforms
    without these primitives are REFUSED (preserved, named) -- never
    deleted lexically. The whole tree goes, marker included: the next
    reuse reconcile or the next native run rebuilds it (cache validity
    stays delegated to the native command).
    """
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        return "anchored no-follow deletion is unavailable on this platform; preserved"
    relative = root.relative_to(paths.root)
    opened: list[int] = []
    try:
        dir_fd = os.open(
            paths.root,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
        opened.append(dir_fd)
        current = dir_fd
        parent = dir_fd
        last = relative.parts[-1]
        for part in relative.parts:
            parent = current
            fd = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=current,
            )
            opened.append(fd)
            current = fd
        _anchored_rmtree(current)
        os.rmdir(last, dir_fd=parent)
        return None
    except (OSError, ValueError, RuntimeError) as error:
        return f"anchored deletion refused ({type(error).__name__}: {error}); preserved"
    finally:
        for fd in opened:
            try:
                os.close(fd)
            except OSError:
                pass


def _anchored_rmtree(dir_fd: int) -> None:
    """Empty and remove the directory anchored by ``dir_fd``.

    Every entry is stat'd WITHOUT following symlinks: a symlink entry is
    unlinked as a link (one byte), never descended through, so the
    removal cannot escape the anchored directory.
    """
    for name in os.listdir(dir_fd):
        try:
            info = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
        except OSError:
            continue
        if stat.S_ISDIR(info.st_mode):
            fd = os.open(
                name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=dir_fd
            )
            try:
                _anchored_rmtree(fd)
            finally:
                os.close(fd)
            os.rmdir(name, dir_fd=dir_fd)
        else:
            os.unlink(name, dir_fd=dir_fd)


def _evict_reuse_workspace(paths: WorkspacePaths) -> tuple[bool, str | None]:
    """Evict the warm reuse workspace only when provably owned and idle.

    Returns ``(evicted, preservation_note)``. The workspace is rebuildable
    (``git worktree add`` + reconcile), so eviction is safe only when every
    ownership fact in the metadata matches this repository and the phase
    is ``idle`` -- an interrupted or unknown workspace is preserved
    together with its pending evidence.
    """
    metadata = paths.evidence / "verification-reuse.json"
    if not paths.verification.exists():
        return False, None
    if not metadata.exists():
        return False, (
            f"{paths.verification}: no ownership metadata; refusing to adopt "
            "or evict a preexisting workspace"
        )
    try:
        recorded = json.loads(metadata.read_bytes())
    except (OSError, ValueError):
        recorded = None
    if not _metadata_proves_ownership(paths, recorded):
        return False, (
            f"{metadata}: ownership metadata does not prove this repository "
            "owns this workspace; preserved"
        )
    phase = recorded.get("phase")
    if phase != "idle":
        return False, (
            f"{paths.verification}: phase {phase!r}; interrupted native "
            "execution may hold pending evidence; recover manually"
        )
    code, out = _git(
        paths.root, "worktree", "remove", "--force", str(paths.verification)
    )
    if code:
        return False, f"{paths.verification}: git worktree remove refused: {out}"
    try:
        metadata.unlink()
    except OSError as error:
        return False, (
            f"{metadata}: workspace removed but metadata unlink failed: "
            f"{type(error).__name__}: {error}"
        )
    return True, None


def _metadata_proves_ownership(paths: WorkspacePaths, recorded: object) -> bool:
    if not _version_one(recorded):
        return False
    fields = _ownership_fields(recorded, ("common_git_dir", "workspace"))
    if fields is None:
        return False
    common = _common_dir(paths)
    if common is None:
        return False
    try:
        if Path(fields["common_git_dir"]).resolve() != Path(common):
            return False
    except (OSError, ValueError, RuntimeError):
        return False
    if Path(fields["workspace"]) != paths.verification:
        return False
    return isinstance(recorded.get("outputs"), list) and recorded["outputs"] == list(
        paths.outputs or ()
    )


def _reuse_phase(paths: WorkspacePaths) -> str:
    metadata = paths.evidence / "verification-reuse.json"
    try:
        recorded = json.loads(metadata.read_bytes())
    except (OSError, ValueError):
        return "absent"
    fields = _ownership_fields(recorded, ("phase",))
    return "unknown" if fields is None else fields["phase"]


def _intermediate_symlink(anchor: Path, directory: Path) -> bool:
    """True when any INTERMEDIATE component of ``directory`` is a symlink.

    A declared root reached through an intermediate link would make the
    budget count (or delete-reason about) bytes that live on the far side
    of the link; such a root is UNKNOWN, never walked. The final
    component is excluded: a top-level symlink entry stays zero-weight.
    """
    try:
        relative = directory.relative_to(anchor)
    except ValueError:
        return True
    current = anchor
    for part in relative.parts[:-1]:
        current = current / part
        try:
            info = os.lstat(current)
        except OSError:
            return True
        if stat.S_ISLNK(info.st_mode):
            return True
    return False


def _tree_bytes(directory: Path) -> int | None:
    """Byte size of regular files, never following symlinks; None if unobservable.

    Output links bind workspace paths to principal directories; a symlink
    -- anywhere, including the entry itself -- is zero-weight and is never
    descended through, so bytes on the far side of a link are never
    accounted under the link's name. A dangling path is zero bytes. A stat
    or walk failure makes the budget INDETERMINATE instead of silently
    under-counting.
    """
    try:
        info = os.lstat(directory)
    except OSError:
        return 0
    if stat.S_ISLNK(info.st_mode):
        return 0
    if not stat.S_ISDIR(info.st_mode):
        return info.st_size
    total = 0
    try:
        for current, directories, files in os.walk(
            directory, followlinks=False, onerror=_raise
        ):
            for name in list(directories):
                if Path(current, name).is_symlink():
                    directories.remove(name)
            for name in files:
                entry = os.path.join(current, name)
                info = os.lstat(entry)
                total += 0 if stat.S_ISLNK(info.st_mode) else info.st_size
    except OSError:
        return None
    return total


def _raise(error: OSError) -> None:
    raise error
