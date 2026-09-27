"""Canonical, byte-preserving workspace projections for native capture.

The filesystem is an effect boundary.  This module keeps its successful result
small and typed, and refuses observations that cannot be made stable or whose
meaning is not portable to Git's regular-file/symlink model.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
import subprocess
from collections.abc import Iterable, Mapping
from pathlib import Path


class FilesystemProjectionError(ValueError):
    """A supplied projection value is outside the closed grammar."""


class ProjectionIndeterminate(RuntimeError):
    """The filesystem cannot provide one safe, stable projection."""


_REGULAR_MODES = frozenset({0o100644, 0o100755})
_GIT_DIR = b".git"
_DES_PREFIX = b".nwave/des/"
_FILE_STATE_TOKEN = object()

# These are setup-created roots, not delivery content.  They intentionally use
# exact repository-relative names: the observer can therefore prune a whole
# unsafe subtree before it reads a child or resolves a link within it.  Unlike
# the basename rules below, a delivery may use these names below its own tree.
_STRICT_DELIVERY_EXCLUDED_ROOT_BYTES = (
    b"k4-fixture-venv",
    b".k4-user-environment.md",
    b"hc.sqlite",
    b"hc.sqlite.pristine",
    b"hc.sqlite.lock",
    b"server.pid",
    b"supervisor.pid",
    b"k4-supervisor.py",
    b"supervisor.lock",
    b"supervisor.log",
    b".k4-reset",
    b"server.log",
)

# These names were historically passed to ``shutil.ignore_patterns``.  That
# API matches an entry basename at every directory level, so delivery capture
# must retain the same scope rather than treating them as workspace roots.
_STRICT_DELIVERY_EXCLUDED_BASENAME_BYTES = (
    b".claude-k4",
    b".credentials.json",
    b".claude.json",
    b".nwave",
    b"CLAUDE.md",
    b".k4-acceptance-venv",
    b".mypy_cache",
    b".hypothesis",
    b"__pycache__",
    b".git",
    b"AGENTS.md",
    b"test_k4_acceptance.py",
)

# ``.venv*`` was the one legacy glob.  Model it as this narrow basename-prefix
# rule, not as a general pattern language.
_STRICT_DELIVERY_EXCLUDED_BASENAME_PREFIX_BYTES = (b".venv",)


class GitPath:
    """A validated repository-relative filename represented by raw bytes."""

    __slots__ = ("_raw",)

    def __init__(self, raw: bytes) -> None:
        if not isinstance(raw, bytes):
            raise FilesystemProjectionError("GitPath must be constructed from bytes")
        if not raw or b"\x00" in raw or raw.startswith(b"/"):
            raise FilesystemProjectionError("GitPath must be a non-empty relative path")
        parts = raw.split(b"/")
        if any(part in (b"", b".", b"..") for part in parts):
            raise FilesystemProjectionError("GitPath has an unsafe path component")
        object.__setattr__(self, "_raw", raw)

    def __setattr__(self, _: str, __: object) -> None:
        raise AttributeError("GitPath is immutable")

    def __delattr__(self, _: str) -> None:
        raise AttributeError("GitPath is immutable")

    @classmethod
    def from_base64(cls, encoded: str) -> GitPath:
        if not isinstance(encoded, str) or not encoded:
            raise FilesystemProjectionError("GitPath base64 must be a non-empty string")
        try:
            raw = base64.b64decode(encoded.encode("ascii"), validate=True)
        except (UnicodeEncodeError, ValueError) as error:
            raise FilesystemProjectionError("GitPath base64 is malformed") from error
        path = cls(raw)
        if path.base64 != encoded:
            raise FilesystemProjectionError("GitPath base64 is not canonical")
        return path

    @property
    def raw(self) -> bytes:
        """Return the canonical repository-relative filename bytes."""
        return self._raw

    @property
    def base64(self) -> str:
        """Return the canonical ASCII identity used in JSON."""
        return base64.b64encode(self._raw).decode("ascii")

    def is_below(self, root: GitPath) -> bool:
        return self._raw == root._raw or self._raw.startswith(root._raw + b"/")

    def __eq__(self, other: object) -> bool:
        return isinstance(other, GitPath) and self._raw == other._raw

    def __hash__(self) -> int:
        return hash(self._raw)

    def __lt__(self, other: GitPath) -> bool:
        if not isinstance(other, GitPath):
            return NotImplemented
        return self._raw < other._raw

    def __repr__(self) -> str:
        return f"GitPath.from_base64({self.base64!r})"


class FileState:
    """One Git-representable path state, constructible only by its variants."""

    __slots__ = ("_kind", "_mode", "_sha256", "_size")

    def __init__(
        self,
        token: object,
        kind: str,
        mode: int | None,
        size: int | None,
        sha256: str | None,
    ) -> None:
        if token is not _FILE_STATE_TOKEN:
            raise TypeError("use FileState.absent(), regular(), or symlink()")
        object.__setattr__(self, "_kind", kind)
        object.__setattr__(self, "_mode", mode)
        object.__setattr__(self, "_size", size)
        object.__setattr__(self, "_sha256", sha256)

    def __setattr__(self, _: str, __: object) -> None:
        raise AttributeError("FileState is immutable")

    def __delattr__(self, _: str) -> None:
        raise AttributeError("FileState is immutable")

    @classmethod
    def absent(cls) -> FileState:
        return cls(_FILE_STATE_TOKEN, "absent", None, None, None)

    @classmethod
    def regular(cls, mode: int, size: int, sha256: str) -> FileState:
        cls._validate_payload(mode, size, sha256, _REGULAR_MODES)
        return cls(_FILE_STATE_TOKEN, "regular", mode, size, sha256)

    @classmethod
    def symlink(cls, size: int, sha256: str) -> FileState:
        cls._validate_payload(0o120000, size, sha256, frozenset({0o120000}))
        return cls(_FILE_STATE_TOKEN, "symlink", 0o120000, size, sha256)

    @staticmethod
    def _validate_payload(
        mode: int, size: int, sha256: str, allowed_modes: frozenset[int]
    ) -> None:
        if (
            isinstance(mode, bool)
            or not isinstance(mode, int)
            or mode not in allowed_modes
        ):
            raise FilesystemProjectionError("FileState mode is not Git-representable")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise FilesystemProjectionError(
                "FileState size must be a non-negative integer"
            )
        if (
            not isinstance(sha256, str)
            or len(sha256) != 64
            or any(character not in "0123456789abcdef" for character in sha256)
        ):
            raise FilesystemProjectionError("FileState sha256 must be lowercase hex")

    @property
    def kind(self) -> str:
        return self._kind

    @property
    def mode(self) -> int | None:
        return self._mode

    @property
    def size(self) -> int | None:
        return self._size

    @property
    def sha256(self) -> str | None:
        return self._sha256

    def __eq__(self, other: object) -> bool:
        return isinstance(other, FileState) and (
            self._kind,
            self._mode,
            self._size,
            self._sha256,
        ) == (other._kind, other._mode, other._size, other._sha256)

    def __hash__(self) -> int:
        return hash((self._kind, self._mode, self._size, self._sha256))

    def __repr__(self) -> str:
        if self._kind == "absent":
            return "FileState.absent()"
        if self._kind == "regular":
            return (
                f"FileState.regular({self._mode!r}, {self._size!r}, {self._sha256!r})"
            )
        return f"FileState.symlink({self._size!r}, {self._sha256!r})"


class PathTransition:
    """One changed path between two complete workspace projections."""

    __slots__ = ("_after", "_before", "_path")

    def __init__(self, *_: object) -> None:
        raise TypeError("use PathTransition.changed()")

    def __setattr__(self, _: str, __: object) -> None:
        raise AttributeError("PathTransition is immutable")

    def __delattr__(self, _: str) -> None:
        raise AttributeError("PathTransition is immutable")

    @classmethod
    def changed(
        cls, path: GitPath, before: FileState, after: FileState
    ) -> PathTransition:
        if (
            not isinstance(path, GitPath)
            or not isinstance(before, FileState)
            or not isinstance(after, FileState)
        ):
            raise FilesystemProjectionError("PathTransition requires validated values")
        if before == after:
            raise FilesystemProjectionError("PathTransition requires unequal states")
        value = object.__new__(cls)
        object.__setattr__(value, "_path", path)
        object.__setattr__(value, "_before", before)
        object.__setattr__(value, "_after", after)
        return value

    @property
    def path(self) -> GitPath:
        return self._path

    @property
    def before(self) -> FileState:
        return self._before

    @property
    def after(self) -> FileState:
        return self._after

    def __eq__(self, other: object) -> bool:
        return isinstance(other, PathTransition) and (
            self._path,
            self._before,
            self._after,
        ) == (other._path, other._before, other._after)

    def __hash__(self) -> int:
        return hash((self._path, self._before, self._after))


class WorkspaceProjection:
    """A complete sorted filesystem state under one policy."""

    __slots__ = ("_states",)

    def __init__(self, *_: object) -> None:
        raise TypeError("use WorkspaceProjection.from_states()")

    def __setattr__(self, _: str, __: object) -> None:
        raise AttributeError("WorkspaceProjection is immutable")

    def __delattr__(self, _: str) -> None:
        raise AttributeError("WorkspaceProjection is immutable")

    @classmethod
    def from_states(
        cls, states: Mapping[GitPath, FileState] | Iterable[tuple[GitPath, FileState]]
    ) -> WorkspaceProjection:
        items = states.items() if isinstance(states, Mapping) else states
        materialized = list(items)
        if any(
            not isinstance(path, GitPath) or not isinstance(state, FileState)
            for path, state in materialized
        ):
            raise FilesystemProjectionError(
                "WorkspaceProjection requires validated states"
            )
        if any(state.kind == "absent" for _, state in materialized):
            raise FilesystemProjectionError(
                "WorkspaceProjection cannot contain absent paths"
            )
        ordered = tuple(sorted(materialized, key=lambda item: item[0].raw))
        if len({path for path, _ in ordered}) != len(ordered):
            raise FilesystemProjectionError("WorkspaceProjection has duplicate paths")
        value = object.__new__(cls)
        object.__setattr__(value, "_states", ordered)
        return value

    @property
    def states(self) -> tuple[tuple[GitPath, FileState], ...]:
        return self._states

    def state_at(self, path: GitPath) -> FileState:
        for candidate, state in self._states:
            if candidate == path:
                return state
        return FileState.absent()

    def transitions_to(self, later: WorkspaceProjection) -> tuple[PathTransition, ...]:
        if not isinstance(later, WorkspaceProjection):
            raise FilesystemProjectionError("transitions require a WorkspaceProjection")
        paths = {path for path, _ in self._states} | {path for path, _ in later._states}
        return tuple(
            PathTransition.changed(path, self.state_at(path), later.state_at(path))
            for path in sorted(paths, key=lambda candidate: candidate.raw)
            if self.state_at(path) != later.state_at(path)
        )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, WorkspaceProjection) and self._states == other._states

    def __hash__(self) -> int:
        return hash(self._states)


class ProjectionPolicy:
    """One closed set of roots and basename rules excluded from observation."""

    __slots__ = (
        "_excluded_basename_prefixes",
        "_excluded_basenames",
        "_excluded_roots",
    )

    def __init__(self, excluded_roots: Iterable[GitPath] = ()) -> None:
        supplied = tuple(excluded_roots)
        if any(not isinstance(root, GitPath) for root in supplied):
            raise FilesystemProjectionError(
                "ProjectionPolicy roots must be GitPath values"
            )
        roots = tuple(sorted(set(supplied), key=lambda root: root.raw))
        if any(not root.raw.startswith(_DES_PREFIX) for root in roots):
            raise FilesystemProjectionError(
                "ProjectionPolicy may exclude only DES-owned paths"
            )
        object.__setattr__(self, "_excluded_roots", roots)
        object.__setattr__(self, "_excluded_basenames", ())
        object.__setattr__(self, "_excluded_basename_prefixes", ())

    def __setattr__(self, _: str, __: object) -> None:
        raise AttributeError("ProjectionPolicy is immutable")

    def __delattr__(self, _: str) -> None:
        raise AttributeError("ProjectionPolicy is immutable")

    @classmethod
    def native_capture(cls) -> ProjectionPolicy:
        return cls((GitPath(b".nwave/des/logs/turns"),))

    @classmethod
    def from_excluded_roots(cls, roots: Iterable[GitPath]) -> ProjectionPolicy:
        """Construct a policy from explicitly validated repository roots.

        This is deliberately separate from the native constructor: callers
        that own a delivery boundary may exclude arbitrary *validated*
        GitPath roots, while ordinary DES capture stays confined to its own
        record directory.
        """
        supplied = tuple(roots)
        if any(not isinstance(root, GitPath) for root in supplied):
            raise FilesystemProjectionError(
                "ProjectionPolicy roots must be GitPath values"
            )
        return cls.from_rules(excluded_roots=supplied)

    @classmethod
    def from_rules(
        cls,
        *,
        excluded_roots: Iterable[GitPath] = (),
        excluded_basenames: Iterable[bytes] = (),
        excluded_basename_prefixes: Iterable[bytes] = (),
    ) -> ProjectionPolicy:
        """Construct explicit rules without admitting a general glob language."""
        roots = tuple(excluded_roots)
        basenames = tuple(excluded_basenames)
        prefixes = tuple(excluded_basename_prefixes)
        if any(not isinstance(root, GitPath) for root in roots):
            raise FilesystemProjectionError(
                "ProjectionPolicy roots must be GitPath values"
            )
        if any(not _is_basename(value) for value in (*basenames, *prefixes)):
            raise FilesystemProjectionError(
                "ProjectionPolicy basename rules must be non-empty path components"
            )
        value = object.__new__(cls)
        object.__setattr__(
            value,
            "_excluded_roots",
            tuple(sorted(set(roots), key=lambda root: root.raw)),
        )
        object.__setattr__(value, "_excluded_basenames", tuple(sorted(set(basenames))))
        object.__setattr__(
            value,
            "_excluded_basename_prefixes",
            tuple(sorted(set(prefixes))),
        )
        return value

    @classmethod
    def strict_delivery(cls) -> ProjectionPolicy:
        """Return the one canonical policy for D0 and strict delivery capture."""
        return cls.from_rules(
            excluded_roots=(
                GitPath(root) for root in _STRICT_DELIVERY_EXCLUDED_ROOT_BYTES
            ),
            excluded_basenames=_STRICT_DELIVERY_EXCLUDED_BASENAME_BYTES,
            excluded_basename_prefixes=_STRICT_DELIVERY_EXCLUDED_BASENAME_PREFIX_BYTES,
        )

    @property
    def excluded_roots(self) -> tuple[GitPath, ...]:
        return self._excluded_roots

    @property
    def excluded_basenames(self) -> tuple[bytes, ...]:
        """Return exact entry names excluded at every directory level."""
        return self._excluded_basenames

    @property
    def excluded_basename_prefixes(self) -> tuple[bytes, ...]:
        """Return the deliberately narrow entry-name prefix exclusions."""
        return self._excluded_basename_prefixes

    def excludes(self, path: GitPath) -> bool:
        basename = path.raw.rsplit(b"/", 1)[-1]
        return (
            any(path.is_below(root) for root in self._excluded_roots)
            or basename in self._excluded_basenames
            or any(
                basename.startswith(prefix)
                for prefix in self._excluded_basename_prefixes
            )
        )

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, ProjectionPolicy)
            and self._excluded_roots == other._excluded_roots
            and self._excluded_basenames == other._excluded_basenames
            and self._excluded_basename_prefixes == other._excluded_basename_prefixes
        )

    def __hash__(self) -> int:
        return hash(
            (
                self._excluded_roots,
                self._excluded_basenames,
                self._excluded_basename_prefixes,
            )
        )


def _is_basename(value: object) -> bool:
    return (
        isinstance(value, bytes)
        and bool(value)
        and b"/" not in value
        and b"\x00" not in value
        and value not in {b".", b".."}
    )


# The delivery boundary has one fixed policy.  Consumers share its canonical
# root list; reservations persist that list as bytes rather than object identity.
STRICT_DELIVERY_POLICY = ProjectionPolicy.strict_delivery()


def projection_to_bytes(projection: WorkspaceProjection) -> bytes:
    """Serialize exactly one canonical, ASCII JSON projection with a final LF."""
    if not isinstance(projection, WorkspaceProjection):
        raise FilesystemProjectionError("only WorkspaceProjection can be serialized")
    payload = {
        "schema_version": 1,
        "states": [
            {"path": path.base64, "state": _state_to_json(state)}
            for path, state in projection.states
        ],
    }
    return (
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        + b"\n"
    )


def projection_from_bytes(raw: bytes) -> WorkspaceProjection:
    """Decode only the exact canonical bytes emitted by :func:`projection_to_bytes`."""
    if not isinstance(raw, bytes):
        raise FilesystemProjectionError("projection JSON must be bytes")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        FilesystemProjectionError,
    ) as error:
        raise FilesystemProjectionError("projection JSON is malformed") from error
    if not isinstance(value, dict) or set(value) != {"schema_version", "states"}:
        raise FilesystemProjectionError("projection JSON has an invalid root")
    version = value["schema_version"]
    if isinstance(version, bool) or not isinstance(version, int) or version != 1:
        raise FilesystemProjectionError("projection schema_version must be 1")
    states = value["states"]
    if not isinstance(states, list):
        raise FilesystemProjectionError("projection states must be an array")
    parsed: list[tuple[GitPath, FileState]] = []
    for item in states:
        if not isinstance(item, dict) or set(item) != {"path", "state"}:
            raise FilesystemProjectionError("projection state entry has invalid keys")
        parsed.append(
            (GitPath.from_base64(item["path"]), _state_from_json(item["state"]))
        )
    projection = WorkspaceProjection.from_states(parsed)
    if projection_to_bytes(projection) != raw:
        raise FilesystemProjectionError("projection JSON is not canonical")
    return projection


def observe_workspace(workspace: Path, policy: ProjectionPolicy) -> WorkspaceProjection:
    """Observe all policy-visible paths once, or fail closed with no projection."""
    if not isinstance(workspace, Path) or not isinstance(policy, ProjectionPolicy):
        raise FilesystemProjectionError(
            "workspace and policy must be constructed values"
        )
    _refuse_gitlinks(workspace)
    if os.name == "nt":
        return _observe_windows(workspace, policy)
    return _observe_posix(workspace, policy)


def _state_to_json(state: FileState) -> dict[str, object]:
    if state.kind == "absent":
        return {"kind": "absent"}
    assert (
        state.mode is not None and state.size is not None and state.sha256 is not None
    )
    return {
        "kind": state.kind,
        "mode": format(state.mode, "06o"),
        "sha256": state.sha256,
        "size": state.size,
    }


def _state_from_json(value: object) -> FileState:
    if not isinstance(value, dict) or not isinstance(value.get("kind"), str):
        raise FilesystemProjectionError("FileState JSON is malformed")
    kind = value["kind"]
    if kind == "absent":
        if set(value) != {"kind"}:
            raise FilesystemProjectionError("absent FileState has extra fields")
        return FileState.absent()
    if kind not in {"regular", "symlink"} or set(value) != {
        "kind",
        "mode",
        "size",
        "sha256",
    }:
        raise FilesystemProjectionError("FileState JSON has invalid keys")
    mode = value["mode"]
    size = value["size"]
    digest = value["sha256"]
    if (
        not isinstance(mode, str)
        or len(mode) != 6
        or any(char not in "01234567" for char in mode)
    ):
        raise FilesystemProjectionError(
            "FileState mode must be a six-digit octal string"
        )
    if isinstance(size, bool) or not isinstance(size, int):
        raise FilesystemProjectionError("FileState size must be an integer")
    parsed_mode = int(mode, 8)
    if kind == "regular":
        return FileState.regular(parsed_mode, size, digest)
    if parsed_mode != 0o120000:
        raise FilesystemProjectionError("symlink FileState must have mode 120000")
    return FileState.symlink(size, digest)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise FilesystemProjectionError("projection JSON has a duplicate key")
        value[key] = item
    return value


def _refuse_gitlinks(workspace: Path) -> None:
    """Refuse Gitlinks when this workspace has Git metadata to inspect."""
    metadata = workspace / ".git"
    if not os.path.lexists(metadata):
        return
    modes = _git_index_modes(workspace)
    if any(mode == 0o160000 for mode in modes.values()):
        raise ProjectionIndeterminate("workspace index contains a Gitlink")


def _git_index_modes(workspace: Path) -> dict[bytes, int]:
    """Read Git index modes in its NUL-delimited, byte-preserving form."""
    try:
        completed = subprocess.run(
            ["git", "-C", str(workspace), "ls-files", "--stage", "-z"],
            check=False,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ProjectionIndeterminate(
            f"Git cannot inspect workspace index modes: {error}"
        ) from error
    if completed.returncode != 0:
        raise ProjectionIndeterminate("Git cannot inspect workspace index modes")
    modes: dict[bytes, int] = {}
    for record in completed.stdout.split(b"\0"):
        if not record:
            continue
        metadata, separator, path = record.partition(b"\t")
        parts = metadata.split(b" ")
        if not separator or len(parts) != 3 or len(parts[0]) != 6:
            raise ProjectionIndeterminate("Git returned malformed index mode data")
        try:
            mode = int(parts[0], 8)
        except ValueError as error:
            raise ProjectionIndeterminate(
                "Git returned malformed index mode data"
            ) from error
        if path in modes:
            raise ProjectionIndeterminate("Git returned duplicate index path data")
        modes[path] = mode
    return modes


def _observe_posix(workspace: Path, policy: ProjectionPolicy) -> WorkspaceProjection:
    root = os.fsencode(workspace)
    try:
        root_stat = os.stat(root, follow_symlinks=False)  # noqa: PTH116 - raw bytes
    except OSError as error:
        raise ProjectionIndeterminate(f"workspace is not readable: {error}") from error
    if not stat.S_ISDIR(root_stat.st_mode):
        raise ProjectionIndeterminate("workspace is not a directory")
    states: list[tuple[GitPath, FileState]] = []
    root_real = os.path.realpath(root)

    def visit(directory: bytes, prefix: bytes) -> None:
        before = _identity(directory)
        if before is None or not stat.S_ISDIR(before[0]):
            raise ProjectionIndeterminate(
                "workspace directory changed during observation"
            )
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError as error:
            raise ProjectionIndeterminate(
                f"workspace directory is unreadable: {error}"
            ) from error
        for entry in entries:
            name = entry.name
            assert isinstance(name, bytes)
            rel = name if not prefix else prefix + b"/" + name
            path = GitPath(rel)
            if policy.excludes(path):
                continue
            if name == _GIT_DIR:
                if prefix:
                    raise ProjectionIndeterminate(
                        "workspace contains nested Git metadata"
                    )
                continue
            child = entry.path
            mode = _identity(child)
            if mode is None:
                raise ProjectionIndeterminate(
                    "workspace path disappeared during observation"
                )
            if stat.S_ISDIR(mode[0]):
                visit(child, rel)
            elif stat.S_ISREG(mode[0]):
                states.append(
                    (path, _read_regular(child, mode, require_no_follow=True))
                )
            elif stat.S_ISLNK(mode[0]):
                states.append((path, _read_symlink(root_real, child, mode)))
            else:
                raise ProjectionIndeterminate(
                    "workspace contains an unsupported filesystem type"
                )
        if _identity(directory) != before:
            raise ProjectionIndeterminate(
                "workspace directory changed during observation"
            )

    visit(root, b"")
    return WorkspaceProjection.from_states(states)


def _identity(path: str | bytes) -> tuple[int, int, int, int, int, int] | None:
    try:
        observed = os.lstat(path)
    except OSError:
        return None
    return (
        observed.st_mode,
        observed.st_dev,
        observed.st_ino,
        observed.st_size,
        observed.st_mtime_ns,
        observed.st_ctime_ns,
    )


def _read_regular(
    path: str | bytes,
    expected: tuple[int, int, int, int, int, int],
    *,
    require_no_follow: bool,
) -> FileState:
    if expected[0] & (stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX):
        raise ProjectionIndeterminate(
            "regular file has unsupported special permission bits"
        )
    no_follow = getattr(os, "O_NOFOLLOW", None)
    if require_no_follow and no_follow is None:
        raise ProjectionIndeterminate(
            "platform cannot open a regular file without following links"
        )
    descriptor = -1
    try:
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        if no_follow is not None:
            flags |= no_follow
        descriptor = os.open(path, flags)
        opened = _identity_from_stat(os.fstat(descriptor))
        if opened != expected:
            raise ProjectionIndeterminate(
                "regular file identity changed before reading"
            )
        first = _read_descriptor(descriptor)
        after_first = _identity_from_stat(os.fstat(descriptor))
        if after_first != expected or _identity(path) != expected:
            raise ProjectionIndeterminate("regular file changed while being read")
        os.lseek(descriptor, 0, os.SEEK_SET)
        second = _read_descriptor(descriptor)
        if (
            second != first
            or _identity_from_stat(os.fstat(descriptor)) != expected
            or _identity(path) != expected
        ):
            raise ProjectionIndeterminate("regular file changed while being read")
    except OSError as error:
        raise ProjectionIndeterminate(
            f"regular file cannot be read safely: {error}"
        ) from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    git_mode = 0o100755 if expected[0] & 0o111 else 0o100644
    return FileState.regular(git_mode, len(second), hashlib.sha256(second).hexdigest())


def _read_descriptor(descriptor: int) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _identity_from_stat(
    observed: os.stat_result,
) -> tuple[int, int, int, int, int, int]:
    return (
        observed.st_mode,
        observed.st_dev,
        observed.st_ino,
        observed.st_size,
        observed.st_mtime_ns,
        observed.st_ctime_ns,
    )


def _read_symlink(
    root_real: str | bytes,
    path: str | bytes,
    expected: tuple[int, int, int, int, int, int],
) -> FileState:
    try:
        target = os.readlink(path)  # noqa: PTH115 - raw link-target bytes
        target_bytes = (
            target if isinstance(target, bytes) else target.encode("utf-8", "strict")
        )
        target_real = os.path.realpath(path)
        os.stat(path)  # noqa: PTH116 - validates the raw-byte symlink target
        if os.path.commonpath((root_real, target_real)) != root_real:
            raise ProjectionIndeterminate("symlink target escapes the workspace")
        if _identity(path) != expected:
            raise ProjectionIndeterminate("symlink changed while being read")
    except ProjectionIndeterminate:
        raise
    except (OSError, ValueError) as error:
        raise ProjectionIndeterminate(
            f"symlink is not safely realizable: {error}"
        ) from error
    return FileState.symlink(
        len(target_bytes), hashlib.sha256(target_bytes).hexdigest()
    )


def _observe_windows(workspace: Path, policy: ProjectionPolicy) -> WorkspaceProjection:
    """Use Git's tracked modes on Windows; reject unrepresentable filenames."""
    try:
        root = workspace.resolve(strict=True)
    except OSError as error:
        raise ProjectionIndeterminate(f"workspace is not readable: {error}") from error
    tracked = _windows_tracked_modes(root)
    states: list[tuple[GitPath, FileState]] = []
    root_real = os.path.realpath(os.fspath(root))

    def visit(directory: str | Path, prefix: bytes) -> None:
        before = _identity(os.fspath(directory))
        if before is None or not stat.S_ISDIR(before[0]):
            raise ProjectionIndeterminate(
                "workspace directory changed during observation"
            )
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError as error:
            raise ProjectionIndeterminate(
                f"workspace directory is unreadable: {error}"
            ) from error
        for entry in entries:
            name = entry.name
            try:
                raw_name = name.encode("utf-8", "strict")
            except UnicodeEncodeError as error:
                raise ProjectionIndeterminate(
                    "Windows path is not strict UTF-8"
                ) from error
            rel = raw_name if not prefix else prefix + b"/" + raw_name
            path = GitPath(rel)
            if policy.excludes(path):
                continue
            if raw_name == _GIT_DIR:
                if prefix:
                    raise ProjectionIndeterminate(
                        "workspace contains nested Git metadata"
                    )
                continue
            full = entry.path
            identity = _identity(full)
            if identity is None:
                raise ProjectionIndeterminate(
                    "workspace path disappeared during observation"
                )
            if stat.S_ISDIR(identity[0]):
                visit(full, rel)
            elif stat.S_ISREG(identity[0]):
                mode = tracked.get(path.raw, 0o100644)
                if mode not in _REGULAR_MODES:
                    raise ProjectionIndeterminate(
                        "Windows tracked regular-file mode is unsupported"
                    )
                state = _read_regular(full, identity, require_no_follow=False)
                states.append(
                    (path, FileState.regular(mode, state.size or 0, state.sha256 or ""))
                )
            elif stat.S_ISLNK(identity[0]):
                states.append((path, _read_symlink(root_real, full, identity)))
            else:
                raise ProjectionIndeterminate(
                    "workspace contains an unsupported filesystem type"
                )
        if _identity(os.fspath(directory)) != before:
            raise ProjectionIndeterminate(
                "workspace directory changed during observation"
            )

    visit(root, b"")
    return WorkspaceProjection.from_states(states)


def _windows_tracked_modes(workspace: Path) -> dict[bytes, int]:
    return _git_index_modes(workspace)


__all__ = [
    "STRICT_DELIVERY_POLICY",
    "FileState",
    "FilesystemProjectionError",
    "GitPath",
    "PathTransition",
    "ProjectionIndeterminate",
    "ProjectionPolicy",
    "WorkspaceProjection",
    "observe_workspace",
    "projection_from_bytes",
    "projection_to_bytes",
]
