"""Repository-owned source lifetime, independent of native cache semantics."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path, PurePosixPath

from des.adapters.driven.config.workspace_paths import (
    OWNERSHIP_MARKER,
    WorkspacePaths,
)
from des.adapters.driven.git.git_observation import observe_bytes, observe_text
from des.application.handover import Blocked, DeliveryLock, acquire_file_lock


class WorkspaceUnavailable(ValueError):
    """Ownership or exact materialization cannot be established."""


class CandidateSourceChanged(WorkspaceUnavailable):
    """Native execution invalidated the source identity it was measuring."""


def _git(root: Path, *args: str) -> str:
    result = observe_text(root, *args)
    if result.returncode:
        raise WorkspaceUnavailable(result.stderr or result.stdout)
    return result.stdout.strip()


def _real_path(root: Path, relative: str) -> Path:
    path = root
    for part in PurePosixPath(relative).parts:
        path /= part
        if path.is_symlink():
            raise WorkspaceUnavailable(f"symlink in owned path: {path}")
    return path


def acquire_verification_lock(root: Path) -> DeliveryLock | Blocked:
    common = Path(
        _git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    ).resolve()
    path = _real_path(common, "nwave-verification.lock")
    lock = acquire_file_lock(path)
    if isinstance(lock, Blocked):
        return Blocked(
            lock.what,
            f"verification lock {path}: {lock.why}",
            lock.how,
            retry=lock.retry,
        )
    return lock


def candidate_entries(root: Path, candidate: str) -> dict[str, tuple[str, str]]:
    result = observe_bytes(root, "ls-tree", "-rz", candidate)
    if result.returncode:
        raise WorkspaceUnavailable(f"cannot enumerate candidate {candidate}")
    entries = {}
    for row in result.stdout.split(b"\0"):
        if not row:
            continue
        header, raw_path = row.split(b"\t", 1)
        mode, kind, digest = header.decode().split()
        if kind != "blob":
            raise WorkspaceUnavailable(
                "reusable verification requires a materialized blob tree; "
                "use isolated cold verification for submodules"
            )
        entries[os.fsdecode(raw_path)] = (mode, digest)
    return entries


def source_mismatches(
    directory: Path, entries: dict[str, tuple[str, str]], algorithm: str
) -> list[str]:
    changed = []
    for relative, (mode, expected) in entries.items():
        path = directory / relative
        try:
            # Never follow an altered source parent into someone else's directory.
            _real_path(directory, str(PurePosixPath(relative).parent))
            info = path.lstat()
            if mode == "120000":
                if not stat.S_ISLNK(info.st_mode):
                    changed.append(relative)
                    continue
                raw = os.fsencode(os.readlink(path))  # noqa: PTH115 -- hash unnormalized Git symlink bytes
                digest = hashlib.new(algorithm, f"blob {len(raw)}\0".encode())
                digest.update(raw)
            else:
                if not stat.S_ISREG(info.st_mode) or bool(info.st_mode & 0o111) != (
                    mode == "100755"
                ):
                    changed.append(relative)
                    continue
                digest = hashlib.new(algorithm, f"blob {info.st_size}\0".encode())
                with path.open("rb") as stream:
                    while chunk := stream.read(1024 * 1024):
                        digest.update(chunk)
            if digest.hexdigest() != expected:
                changed.append(relative)
        except (OSError, WorkspaceUnavailable):
            changed.append(relative)
    return changed


class VerificationWorkspace:
    """The managed reuse workspace, placed by the configured workspace roots.

    ``resolve_workspace_paths`` owns placement (``verification.reuse``
    ``workspace.root``, default ``lanes/.des-verification``), so a project's
    configured root governs reuse exactly as it governs cold isolation; this
    class owns source lifetime inside that placement.
    """

    def __init__(self, paths: WorkspacePaths):
        if os.name != "posix":
            raise WorkspaceUnavailable(
                "managed reuse requires POSIX process-group ownership; "
                "omit reuse for cold isolation (cold runs on this platform "
                "but its process group is UNPROVEN -- the checkout is "
                "retained non-idle until cleaned on a POSIX host)"
            )
        if paths.outputs is None:
            raise WorkspaceUnavailable(
                "reuse requires declared verification.reuse.outputs; "
                "remove reuse to select cold isolation"
            )
        self.principal = paths.root
        self.common = Path(
            _git(paths.root, "rev-parse", "--path-format=absolute", "--git-common-dir")
        ).resolve()
        principal_common = Path(
            _git(
                self.principal,
                "rev-parse",
                "--path-format=absolute",
                "--git-common-dir",
            )
        ).resolve()
        if self.common != principal_common:
            raise WorkspaceUnavailable(
                "principal repository and caller have different Git owners"
            )
        self.directory = paths.verification
        self.metadata = paths.evidence / "verification-reuse.json"
        self.outputs = paths.outputs
        self.lock: DeliveryLock | None = None
        self.entries: dict[str, tuple[str, str]] = {}
        self.algorithm = _git(paths.root, "rev-parse", "--show-object-format")
        self.owner = {
            "version": 1,
            "common_git_dir": str(self.common),
            "workspace": str(self.directory),
            "outputs": list(paths.outputs),
        }

    def _record(self, phase: str) -> None:
        self.metadata.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(
            dir=self.metadata.parent, prefix=".verification-reuse-"
        )
        try:
            with os.fdopen(descriptor, "w") as stream:
                json.dump({**self.owner, "phase": phase}, stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            Path(name).replace(self.metadata)
        finally:
            Path(name).unlink(missing_ok=True)

    def acquire(self, candidate: str, *, lease_held: bool = False) -> None:
        if not lease_held:
            lock = acquire_verification_lock(self.principal)
            if isinstance(lock, Blocked):
                raise WorkspaceUnavailable(f"{lock.what}: {lock.why}; {lock.how}")
            self.lock = lock
        try:
            self.entries = candidate_entries(self.principal, candidate)
            principal_tracked = candidate_entries(self.principal, "HEAD")
            self._validate_outputs(set(self.entries) | set(principal_tracked))
            if self.metadata.exists():
                recorded = json.loads(self.metadata.read_text())
                if not isinstance(recorded, dict) or any(
                    recorded.get(key) != value for key, value in self.owner.items()
                ):
                    raise WorkspaceUnavailable(
                        f"incompatible ownership metadata: {self.metadata}"
                    )
                if recorded.get("phase") not in {"idle", "materializing"}:
                    raise WorkspaceUnavailable(
                        f"interrupted native execution at {self.directory}; establish that all "
                        "native writers stopped, preserve pending evidence, then remove only "
                        "this managed source workspace and its ownership metadata before retrying"
                    )
            elif self.directory.exists():
                raise WorkspaceUnavailable(
                    f"refusing to adopt preexisting workspace {self.directory}"
                )
            self._record("materializing")
            if not self.directory.exists():
                self.directory.parent.mkdir(parents=True, exist_ok=True)
                _git(
                    self.principal,
                    "worktree",
                    "add",
                    "--detach",
                    str(self.directory),
                    candidate,
                )
            if (self.directory / ".git").is_symlink():
                raise WorkspaceUnavailable(
                    f"workspace Git marker is a symlink: {self.directory}"
                )
            registered = _git(self.principal, "worktree", "list", "--porcelain")
            if f"worktree {self.directory}" not in registered.splitlines():
                raise WorkspaceUnavailable(
                    f"workspace is not registered to its owner: {self.directory}"
                )
            actual_common = Path(
                _git(
                    self.directory,
                    "rev-parse",
                    "--path-format=absolute",
                    "--git-common-dir",
                )
            ).resolve()
            if actual_common != self.common or _git(
                self.directory, "rev-parse", "--show-toplevel"
            ) != str(self.directory):
                raise WorkspaceUnavailable(
                    f"workspace Git ownership differs: {self.directory}"
                )
            administrative = Path(
                _git(self.directory, "rev-parse", "--absolute-git-dir")
            ).resolve()
            backlink = administrative / "gitdir"
            if (
                not administrative.is_relative_to(self.common / "worktrees")
                or backlink.is_symlink()
                or Path(backlink.read_text().strip()).resolve()
                != self.directory / ".git"
            ):
                raise WorkspaceUnavailable(
                    f"workspace Git marker is not reciprocally owned: {self.directory}"
                )
            self._reconcile(candidate)
        except BaseException:
            self.release()
            raise

    def _validate_outputs(self, tracked: set[str]) -> None:
        for output in self.outputs:
            path = PurePosixPath(output)
            if (
                path.is_absolute()
                or path.as_posix() != output
                or not path.parts
                or any(part in {".", "..", ".git"} for part in path.parts)
                or path.parts[0] in {".nwave", "lanes", ".venv"}
            ):
                raise WorkspaceUnavailable(f"unsafe generated output root {output!r}")
            if any(
                name == output
                or name.startswith(output + "/")
                or output.startswith(name + "/")
                for name in tracked
            ):
                raise WorkspaceUnavailable(
                    f"generated output overlaps tracked source: {output}"
                )
            if any(
                other != output
                and (other.startswith(output + "/") or output.startswith(other + "/"))
                for other in self.outputs
            ):
                raise WorkspaceUnavailable(
                    f"overlapping generated output declarations: {output}"
                )
            target = _real_path(self.principal, output)
            if target.exists() and not target.is_dir():
                raise WorkspaceUnavailable(
                    f"generated output is not a directory: {target}"
                )
        if any(name == "lanes" or name.startswith("lanes/") for name in tracked):
            raise WorkspaceUnavailable(
                "tracked lanes paths collide with managed verification workspace"
            )

    def _reconcile(self, candidate: str) -> None:
        # Output links are the only untracked entries retained. They never grant
        # deletion authority over their principal-repository targets.
        for output in self.outputs:
            link = self.directory / output
            _real_path(self.directory, str(PurePosixPath(output).parent))
            if link.is_symlink():
                if link.resolve() != self.principal / output:
                    raise WorkspaceUnavailable(f"output binding changed: {link}")
                link.unlink()
            elif link.exists():
                raise WorkspaceUnavailable(f"non-owned output binding at {link}")
        _git(self.directory, "reset", "--hard", candidate)
        _git(self.directory, "clean", "-ffdx")
        changed = source_mismatches(self.directory, self.entries, self.algorithm)
        if changed:
            # Repair same-stat edits which Git's index stat shortcut can miss.
            for relative in changed:
                _real_path(self.directory, str(PurePosixPath(relative).parent))
                _git(self.directory, "checkout", candidate, "--", relative)
        if changed and source_mismatches(self.directory, self.entries, self.algorithm):
            raise WorkspaceUnavailable(
                "candidate bytes remain different after reconciliation"
            )
        for relative, (mode, _) in self.entries.items():
            if mode == "120000" and not (
                self.directory / relative
            ).resolve().is_relative_to(self.directory):
                raise WorkspaceUnavailable(
                    f"candidate symlink escapes isolated source: {relative}"
                )
        for output in self.outputs:
            target = _real_path(self.principal, output)
            preexisting = target.exists()
            if preexisting and (target / OWNERSHIP_MARKER).exists():
                # A marker this repository did not write is not ownership.
                try:
                    marker = json.loads((target / OWNERSHIP_MARKER).read_bytes())
                except (OSError, ValueError):
                    marker = None
                if (
                    not isinstance(marker, dict)
                    or marker.get("version") != 1
                    or marker.get("output") != output
                    or marker.get("common_git_dir") != str(self.common)
                ):
                    raise WorkspaceUnavailable(
                        f"generated output carries foreign ownership marker: {target}"
                    )
            target.mkdir(parents=True, exist_ok=True)
            if not preexisting:
                # Creation is the ownership event: DES materialized this
                # root, so DES may later evict it under lease. A root that
                # already existed is the project's own build cache and is
                # never marked, never auto-adopted.
                (target / OWNERSHIP_MARKER).write_text(
                    json.dumps(
                        {
                            "version": 1,
                            "output": output,
                            "common_git_dir": str(self.common),
                        }
                    ),
                    encoding="utf-8",
                )
            link = self.directory / output
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(target, target_is_directory=True)
        self._record("running")

    def finish(self) -> None:
        if source_mismatches(self.directory, self.entries, self.algorithm):
            self._record("idle")
            raise CandidateSourceChanged(
                "native commands mutated tracked candidate source; no candidate verification can be claimed"
            )
        self._record("idle")

    def release(self) -> None:
        if self.lock is not None:
            self.lock.release()
            self.lock = None
