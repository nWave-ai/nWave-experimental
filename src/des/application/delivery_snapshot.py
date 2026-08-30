"""Private construction of delivery closure and candidate Git snapshots.

This module deliberately has no CLI registration.  The public ``dispatch``
adapter constructs a closure; the PreToolUse adapter is the only caller allowed
to construct a candidate after it has made a native AT-review approval.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from unicodedata import category

from des._internal.delivery_contract_schema import delivery_contract_schema_violation
from des.domain.workspace_test_command_resolver import (
    PreservationVector,
    resolve_preservation_vector,
)
from des.runtime.spawn import git_timeout_seconds, spawn
from des.runtime.test_execution import run_timeout_seconds


@dataclass(frozen=True, slots=True)
class Snapshot:
    commit: str
    root: Path
    parent: str
    preservation: PreservationVector | None = None
    # This is deliberately an in-memory construction fact, reconstructed from
    # admitted Git ancestry when a later hook needs it.  It is not a carrier.
    authority_paths: frozenset[str] = frozenset()
    base: str | None = None


@dataclass(frozen=True, slots=True)
class ApprovedClosure:
    """Ephemeral, platform-bound admission consumed in this process only."""

    closure: Snapshot
    contract_locator: str
    oracle_locator: str
    contract_digest: str
    contract: dict | None = None
    authority_paths: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class FinalizedDelivery:
    """The only successful finalization fact, kept in process memory.

    ``commit`` is F.  The paths and preservation vector are the exact values
    admitted before F was created; ``clean_checkout`` is true only after a
    fresh detached checkout of F has verified them and run the vector.
    """

    commit: str
    authorized_paths: frozenset[str]
    preservation: PreservationVector
    clean_checkout: bool


@dataclass(frozen=True, slots=True)
class _DeliveryPaths:
    """One normalized, disjoint ownership partition for an admitted delivery.

    The type is deliberately private: it is a construction detail shared by
    the C/K boundary, not a second delivery carrier.  In particular, declared
    contract targets are a writable *universe*; an actual crafter delta is
    derived only from the current pending paths inside that universe.
    """

    authority: frozenset[str]
    oracle_dependencies: frozenset[str]
    crafter_writable: frozenset[str]

    @classmethod
    def build(
        cls,
        *,
        authority: set[str],
        oracle_dependencies: set[str],
        crafter_writable: set[str],
    ) -> _DeliveryPaths:
        roles = {
            "AuthorityPaths": _normalize_delivery_paths(authority),
            "OracleAndTestDependencyPaths": _normalize_delivery_paths(
                oracle_dependencies
            ),
            "CrafterWritableTargets": _normalize_delivery_paths(crafter_writable),
        }
        names = tuple(roles)
        for index, left_name in enumerate(names):
            for right_name in names[index + 1 :]:
                overlap = roles[left_name] & roles[right_name]
                if overlap:
                    raise ValueError(
                        "delivery path roles overlap: "
                        f"{left_name}/{right_name}: {sorted(overlap)!r}"
                    )
        return cls(
            authority=roles["AuthorityPaths"],
            oracle_dependencies=roles["OracleAndTestDependencyPaths"],
            crafter_writable=roles["CrafterWritableTargets"],
        )

    def crafter_expected_delta(self, pending: set[str]) -> frozenset[str]:
        """Derive K's eligible delta from observed, not declared, paths."""
        normalized = _normalize_delivery_paths(pending)
        outside = normalized - self.crafter_writable
        if outside:
            raise ValueError(
                "pending crafter delta is outside CrafterWritableTargets: "
                f"{sorted(outside)!r}"
            )
        return normalized


_CLOSURE_MESSAGE = "chore(des): construct delivery closure"
_CANDIDATE_MESSAGE = "chore(des): seal delivery candidate"
_FINAL_MESSAGE = "chore(des): finalize delivery"
# Kept as a message-only compatibility tuple for the P5 adapter, which reads
# only element 2 while deciding whether a commit is a possible final replay.
_FINAL_ID = (None, None, _FINAL_MESSAGE)
_EPOCH = "1970-01-01T00:00:00Z"


def _git(root: Path, *argv: str, env: dict[str, str] | None = None):
    return spawn(
        ["git", "-C", str(root), *argv],
        capture_output=True,
        text=True,
        env=env,
        timeout=git_timeout_seconds(),
    )


def _git_hook_commit(root: Path, *argv: str, env: dict[str, str] | None = None):
    """Run one Git commit that may execute ordinary repository hooks.

    Unlike repository probes, ``git commit`` runs pre-commit hooks, including
    the bounded touched-test gate.  It therefore owns the existing gate-run
    timeout tier rather than the short Git probe tier.
    """
    return spawn(
        ["git", "-C", str(root), *argv],
        capture_output=True,
        text=True,
        env=env,
        timeout=run_timeout_seconds(),
    )


def _git_bytes(root: Path, *argv: str, env: dict[str, str] | None = None):
    return spawn(
        ["git", "-C", str(root), *argv],
        capture_output=True,
        text=False,
        env=env,
        timeout=git_timeout_seconds(),
    )


def _entry(root: Path, rev: str, path: str) -> str | None:
    found = _git(root, "ls-tree", rev, "--", path)
    if found.returncode:
        raise RuntimeError(found.stderr.strip())
    line = found.stdout.strip()
    return line.split("\t", 1)[0] if line else None


def _changed_paths(root: Path, parent: str, commit: str) -> set[str]:
    result = _git(root, "diff", "--name-only", "-z", parent, commit)
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return {path for path in result.stdout.split("\0") if path}


def _status_paths(root: Path, *, env: dict[str, str]) -> set[str]:
    """Paths left dirty in the constructor worktree/private index.

    A commit diff alone cannot prove that a hook did not leave an unstaged
    change or an untracked file behind.  Constructor roots are exclusive, so
    any such residue is an indeterminate hook mutation rather than something
    to preserve for a later actor.
    """
    result = _git(root, "status", "--porcelain=v1", "-z", env=env)
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    paths: set[str] = set()
    for item in result.stdout.split("\0"):
        if not item:
            continue
        paths.add(item[3:] if len(item) > 3 else item)
    return paths


def _metadata(root: Path, commit: str) -> tuple[str, ...]:
    result = _git(
        root,
        "show",
        "-s",
        "--format=%P%x00%B%x00%an%x00%ae%x00%cn%x00%ce%x00%at%x00%ct",
        commit,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return tuple(result.stdout.rstrip("\n").split("\0"))


def _is_structurally_valid_identity(name: str, email: str) -> bool:
    """Accept a transport-shaped Git identity without applying account policy."""
    if not name or name != name.strip() or any(category(char) == "Cc" for char in name):
        return False
    if (
        email.count("@") != 1
        or any(char.isspace() or char in "<>" for char in email)
        or any(category(char) == "Cc" for char in email)
    ):
        return False
    local, domain = email.split("@")
    return bool(
        local
        and domain
        and "." in domain
        and not domain.startswith(".")
        and not domain.endswith(".")
        and ".." not in domain
    )


def _configured_constructor_identity(root: Path) -> tuple[str, str]:
    """Resolve one validated identity from the repository's effective config.

    Git hooks can export only author variables into a constructor process.
    Constructor commits must not then combine that partial ambient identity
    with a repository-configured committer.  ``git config`` deliberately runs
    with the inherited ``GIT_CONFIG_*`` environment, so an authorized
    configuration injection remains effective while author/committer override
    variables are ignored.
    """
    name_result = _git(root, "config", "--get", "user.name")
    email_result = _git(root, "config", "--get", "user.email")
    if name_result.returncode or email_result.returncode:
        raise ValueError("constructor repository identity is not configured")
    name = name_result.stdout.rstrip("\n")
    email = email_result.stdout.rstrip("\n")
    if not _is_structurally_valid_identity(name, email):
        raise ValueError("constructor repository identity is malformed")
    return name, email


def _constructor_commit_env(root: Path, index: str) -> dict[str, str]:
    """One deterministic identity/date/index environment for C, K and F."""
    name, email = _configured_constructor_identity(root)
    return {
        **os.environ,
        "GIT_INDEX_FILE": index,
        "GIT_AUTHOR_NAME": name,
        "GIT_AUTHOR_EMAIL": email,
        "GIT_COMMITTER_NAME": name,
        "GIT_COMMITTER_EMAIL": email,
        "GIT_AUTHOR_DATE": _EPOCH,
        "GIT_COMMITTER_DATE": _EPOCH,
    }


def admit_commit(
    root: Path,
    *,
    parent: str,
    commit: str,
    paths: set[str],
    message: str,
    expected_entries: dict[str, str | None] | None = None,
) -> None:
    """Read back ancestry, exact delta, blobs/modes and immutable metadata."""
    parents, stored_message, an, ae, cn, ce, ad, cd = _metadata(root, commit)
    if parents != parent or stored_message != message + "\n":
        raise ValueError("AdmitCommit parent or message mismatch")
    if (
        not _is_structurally_valid_identity(an, ae)
        or (an, ae) != (cn, ce)
        or (ad, cd) != ("0", "0")
    ):
        raise ValueError("AdmitCommit metadata mismatch")
    if _changed_paths(root, parent, commit) != paths:
        raise ValueError("AdmitCommit delta mismatch")
    for path in paths:
        # ls-tree records exactly mode/type/blob, including a deletion as None.
        entry = _entry(root, commit, path)
        if entry == _entry(root, parent, path):
            raise ValueError("AdmitCommit unchanged authorized path")
        if expected_entries is not None and entry != expected_entries.get(path):
            raise ValueError("AdmitCommit blob or mode readback mismatch")


def _assert_clean_constructor_state(
    root: Path, *, commit: str, env: dict[str, str]
) -> None:
    """Bind commit, private index and worktree to one exact admitted state."""
    if _status_paths(root, env=env):
        raise ValueError("constructor hook left index or worktree dirt")
    # A clean private index must name precisely the admitted tree.  This is a
    # separate readback from parent-to-commit: it catches an index switched or
    # rewritten after the commit while preserving the ordinary-hook route.
    index_tree = _git(root, "write-tree", env=env)
    commit_tree = _git(root, "rev-parse", f"{commit}^{{tree}}")
    if (
        index_tree.returncode
        or commit_tree.returncode
        or index_tree.stdout.strip() != commit_tree.stdout.strip()
    ):
        raise ValueError("constructor private index does not equal admitted commit")


def _base_revision(contract: dict) -> str:
    value = str(contract["repository"]["base-revision"])
    try:
        algorithm, revision = value.split(":", 1)
    except ValueError as exc:
        raise ValueError("base revision is not git-tagged") from exc
    if algorithm not in {"git-sha1", "git-sha256"} or not revision:
        raise ValueError("base revision is not git-tagged")
    return revision


def _require_schema_valid(contract: dict) -> None:
    finding = delivery_contract_schema_violation(contract)
    if finding is not None:
        raise ValueError(f"closure contract is not schema-valid: {finding}")


def _missing_repository_executable(
    root: Path, vector: PreservationVector, argv: tuple[str, ...]
) -> str | None:
    """Return a B-owned repository executable absent from this checkout.

    ``./`` is the resolver's explicit repository-executable projection.  A
    source-listed bare executable covers the direct literal-script form.  A
    slash-bearing bare path is also a repository executable when the vector
    is bound to the subject's ``CLAUDE.md`` whole-suite declaration.  All
    other bare names remain PATH-resolved toolchains: a bare ``python`` never
    acquires a repository fallback merely because a similarly named file
    happens to exist in an integration root.
    """
    if not argv or not argv[0] or Path(argv[0]).is_absolute():
        return None
    locator = argv[0].removeprefix("./")
    explicit_repository_path = argv[0].startswith("./")
    authority_paths = {path for path, _ in vector.sources}
    declared_path_executable = "/" in argv[0] and "CLAUDE.md" in authority_paths
    if not _safe_path(locator) or (
        not explicit_repository_path
        and locator not in authority_paths
        and not declared_path_executable
    ):
        return None
    candidate = _no_follow_path(root, locator)
    try:
        candidate.lstat()
    except FileNotFoundError:
        return locator
    except OSError as exc:
        raise ValueError(
            f"preservation executable is unreadable in checkout: {locator}"
        ) from exc
    return None


def _trusted_preservation_executable(execution_root: Path, locator: str) -> Path:
    """Resolve exactly one real executable from the trusted integration root."""
    candidate = _no_follow_path(execution_root, locator)
    try:
        mode = candidate.lstat().st_mode
    except OSError as exc:
        raise ValueError(
            f"trusted preservation executable is unavailable: {locator}"
        ) from exc
    if (
        candidate.is_symlink()
        or not stat.S_ISREG(mode)
        or not os.access(candidate, os.X_OK)
    ):
        raise ValueError(
            f"trusted preservation executable is not a regular non-symlink executable: {locator}"
        )
    return candidate


def run_preservation(
    root: Path,
    vector: PreservationVector,
    *,
    trusted_execution_root: Path | None = None,
) -> None:
    """Run B-authorized argv in ``root`` with an opt-in executable fallback.

    Fresh Git worktrees intentionally omit ignored environments such as
    ``.venv``.  When a B-owned repository executable is missing *there*, a
    base/final caller may provide the live integration root as a trusted
    execution root.  Only the executable path is borrowed: arguments and cwd
    remain bound to the fresh checkout, and no file is copied or linked into
    it.
    """
    for argv in vector.argv:
        execution_argv = argv
        missing = _missing_repository_executable(root, vector, argv)
        if missing is not None and trusted_execution_root is not None:
            trusted = _trusted_preservation_executable(trusted_execution_root, missing)
            execution_argv = (str(trusted), *argv[1:])
        try:
            result = spawn(
                list(execution_argv), cwd=root, capture_output=True, text=True
            )
        except OSError as exc:
            raise ValueError(
                f"EvidenceGap: preservation executable is not runnable at B: {' '.join(argv)}"
            ) from exc
        if result.returncode:
            raise ValueError(f"preservation vector failed: {' '.join(argv)}")


def _validate_preservation_sources(root: Path, vector: PreservationVector) -> None:
    """Prove that F still contains the exact B bytes that authorized argv."""
    for path, expected_digest in vector.sources:
        if not _safe_path(path):
            raise ValueError("preservation source escapes repository")
        source = _no_follow_path(root, path)
        try:
            mode = source.lstat().st_mode
        except OSError as exc:
            raise ValueError(
                f"preservation source is unreadable in final: {path}"
            ) from exc
        if not stat.S_ISREG(mode) or source.is_symlink():
            raise ValueError(f"preservation source is not regular in final: {path}")
        try:
            content = source.read_bytes()
        except OSError as exc:
            raise ValueError(
                f"preservation source is unreadable in final: {path}"
            ) from exc
        if hashlib.sha256(content).hexdigest() != expected_digest:
            raise ValueError(f"preservation source digest differs in final: {path}")


def _verify_final_checkout(
    repo: Path, *, commit: str, vector: PreservationVector
) -> bool:
    """Execute F's B-authorized verification in a clean, fresh detached root."""
    root = _worktree(repo, commit)
    try:
        head = _git(root, "rev-parse", "HEAD")
        if head.returncode or head.stdout.strip() != commit:
            raise ValueError("fresh final checkout does not name exact F")
        before = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
        if before.returncode or before.stdout:
            raise ValueError("fresh final checkout is not clean before verification")
        _validate_preservation_sources(root, vector)
        run_preservation(root, vector, trusted_execution_root=repo)
        after = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
        if after.returncode or after.stdout:
            raise ValueError("fresh final checkout is not clean after verification")
        return True
    finally:
        _remove_worktree(repo, root)


def _worktree(repo: Path, revision: str) -> Path:
    path = Path(tempfile.mkdtemp(prefix="nwave-delivery-"))
    result = _git(repo, "worktree", "add", "--detach", "--quiet", str(path), revision)
    if result.returncode:
        shutil.rmtree(path, ignore_errors=True)
        raise RuntimeError(
            result.stderr.strip() or "cannot create detached constructor root"
        )
    return path


def _remove_worktree(repo: Path, root: Path) -> None:
    removed = _git(repo, "worktree", "remove", "--force", str(root))
    if removed.returncode:
        raise RuntimeError(
            removed.stderr.strip() or "cannot remove detached constructor root"
        )
    try:
        shutil.rmtree(root)
    except FileNotFoundError:
        # Git removed the registered worktree directory itself.
        return
    except OSError as exc:
        raise RuntimeError("cannot remove detached constructor directory") from exc


def _base_preservation(
    repo: Path, *, base: str, contract: dict, excluded: set[str], locator: str
) -> PreservationVector:
    """Resolve and execute the one B-owned vector before any C/K mutation."""
    root = _worktree(repo, base)
    try:
        vector = resolve_preservation_vector(
            root, contract, excluded=excluded, contract_locator=locator
        )
        run_preservation(root, vector, trusted_execution_root=repo)
        return vector
    finally:
        _remove_worktree(repo, root)


def _commit_snapshot(
    repo: Path,
    *,
    parent: str,
    overlay: dict[str, bytes | tuple[bytes, int] | None],
    allowed: set[str],
    message: str,
    constructor_root: Path | None = None,
) -> Snapshot:
    root = constructor_root or _worktree(repo, parent)
    created_root = constructor_root is None
    if not created_root and _git(root, "rev-parse", "HEAD").stdout.strip() != parent:
        raise ValueError("constructor root HEAD is not its declared parent")
    original_worktree = (
        {path: _working_entry(root, path) for path in allowed}
        if not created_root
        else {}
    )
    original_index = _git(root, "write-tree").stdout.strip() if not created_root else ""
    fd, index = tempfile.mkstemp(prefix="nwave-delivery-", suffix=".index")
    os.close(fd)
    Path(index).unlink(missing_ok=True)
    # Tree, path set, canonical message, dates and repository-configured
    # identity are deterministic.  Explicit pairs prevent a hook's partial
    # ambient author/committer export from producing mismatched metadata.
    env = _constructor_commit_env(root, index)
    try:
        seeded = _git(root, "read-tree", parent, env=env)
        if seeded.returncode:
            raise RuntimeError(seeded.stderr.strip())
        for relative, value in overlay.items():
            destination = _no_follow_path(root, relative)
            content: bytes | None
            mode: int | None = None
            if isinstance(value, tuple):
                content, mode = value
            else:
                content = value
            if content is None:
                destination.unlink(missing_ok=True)
            else:
                _write_regular_no_follow(root, relative, content, 0o644)
                if not stat.S_ISREG(destination.lstat().st_mode):
                    raise ValueError("non-regular closure member")
                if mode is not None:
                    if stat.S_IFMT(mode) != stat.S_IFREG:
                        raise ValueError("non-regular closure member")
                    destination.chmod(stat.S_IMODE(mode))
        staged = _git(root, "add", "-A", "--", *sorted(allowed), env=env)
        if staged.returncode:
            raise RuntimeError(staged.stderr.strip())
        first = _git_hook_commit(
            root,
            "-c",
            "commit.gpgSign=false",
            "commit",
            "--quiet",
            "-m",
            message,
            env=env,
        )
        if first.returncode:
            raise RuntimeError(first.stderr.strip() or first.stdout.strip())
        commit = _git(root, "rev-parse", "HEAD").stdout.strip()
        changed = _changed_paths(root, parent, commit)
        if not changed <= allowed:
            raise ValueError("hook changed a path outside the constructor universe")
        expected_entries = {path: _entry(root, commit, path) for path in changed}
        # Normalise the post-hook authoritative state once.  A second hook run
        # must reproduce the same immutable commit exactly.
        # Git rejects a disappeared pathspec after the first commit even
        # though its deletion is already correctly present in the private
        # index.  Restage only extant hook-owned paths; deletions stay staged
        # by the first scoped ``add -A`` and are still admitted below.
        extant = [
            path
            for path in sorted(changed)
            if (
                _no_follow_path(root, path).exists()
                or _no_follow_path(root, path).is_symlink()
            )
        ]
        for path in extant:
            _working_entry(root, path)
        if extant:
            restage = _git(root, "add", "-A", "--", *extant, env=env)
            if restage.returncode:
                raise RuntimeError(restage.stderr.strip())
        amended = _git_hook_commit(
            root,
            "-c",
            "commit.gpgSign=false",
            "commit",
            "--quiet",
            "--amend",
            "--no-edit",
            env=env,
        )
        if amended.returncode:
            raise RuntimeError(amended.stderr.strip() or amended.stdout.strip())
        normalized = _git(root, "rev-parse", "HEAD").stdout.strip()
        admit_commit(
            root,
            parent=parent,
            commit=normalized,
            paths=changed,
            message=message,
            expected_entries=expected_entries,
        )
        _assert_clean_constructor_state(root, commit=normalized, env=env)
        if normalized != commit:
            raise ValueError("post-hook normalization was not idempotent")
        # The ordinary worktree index is not the exclusive constructor index.
        # Refresh it only after the full private-index readback, otherwise the
        # following unchanged CLI would see synthetic dirt in its own root.
        if not created_root:
            refreshed = _git(root, "read-tree", normalized)
            if refreshed.returncode:
                raise RuntimeError(refreshed.stderr.strip())
        return Snapshot(commit=normalized, root=root, parent=parent)
    except Exception:
        if created_root:
            _remove_worktree(repo, root)
        else:
            # Restore only the constructor's own observed entries and index;
            # never reset/clean the integration root or erase concurrent dirt.
            for path, entry in original_worktree.items():
                _restore_working_entry(root, path, entry)
            if original_index:
                _git(root, "read-tree", original_index)
        raise
    finally:
        Path(index).unlink(missing_ok=True)


def _overlay_entry(root: Path, locator: str, content: bytes) -> tuple[bytes, int]:
    """Bind imported bytes to their producer's regular-file mode."""
    item = _no_follow_path(root, locator)
    try:
        mode = item.lstat().st_mode
    except FileNotFoundError:
        # Initial contracts/oracles are allowed to be absent from B.  The
        # platform importer supplies their producer mode when available; the
        # direct private constructor's deterministic default is regular 644.
        return content, stat.S_IFREG | 0o644
    except OSError as exc:
        raise ValueError(f"unreadable authority member {locator}") from exc
    if not stat.S_ISREG(mode) or item.is_symlink():
        raise ValueError(f"authority member {locator} is not a regular file")
    return content, stat.S_IMODE(mode) | stat.S_IFREG


def _closure_overlay(
    root: Path,
    *,
    contract_locator: str,
    contract_bytes: bytes,
    oracle_locator: str,
    oracle_bytes: bytes,
    supporting: tuple[tuple[str, bytes], ...],
    imports: tuple[tuple[str, bytes, int], ...] = (),
) -> dict[str, bytes | tuple[bytes, int] | None]:
    """Normalize the ordered authority union and reject ownership collisions."""
    entries: list[tuple[str, bytes | tuple[bytes, int] | None]] = [
        (path, (content, mode)) for path, content, mode in imports
    ]
    entries.extend(
        (
            (contract_locator, _overlay_entry(root, contract_locator, contract_bytes)),
            (
                oracle_locator.split("::", 1)[0],
                _overlay_entry(root, oracle_locator.split("::", 1)[0], oracle_bytes),
            ),
        )
    )
    entries.extend(
        (path, _overlay_entry(root, path, content)) for path, content in supporting
    )
    overlay: dict[str, bytes | tuple[bytes, int] | None] = {}
    for path, content in entries:
        if not _safe_path(path):
            raise ValueError(f"authority path escapes repository: {path}")
        if path in overlay:
            raise ValueError(f"authority path has duplicate owners: {path}")
        overlay[path] = content
    return overlay


def _safe_path(path: str) -> bool:
    pure = Path(path)
    return (
        bool(path)
        and not pure.is_absolute()
        and ".." not in pure.parts
        and "\\" not in path
    )


def _normalize_delivery_paths(paths: set[str]) -> frozenset[str]:
    """Make the one lexical spelling used by ownership comparison and Git."""
    normalized: set[str] = set()
    for path in paths:
        if not isinstance(path, str) or not _safe_path(path):
            raise ValueError(f"delivery path escapes repository: {path!r}")
        canonical = PurePosixPath(path).as_posix()
        if not canonical or canonical == "." or not _safe_path(canonical):
            raise ValueError(f"delivery path escapes repository: {path!r}")
        normalized.add(canonical)
    return frozenset(normalized)


def _no_follow_path(root: Path, locator: str) -> Path:
    """Return a lexical repository child only after every present parent is real.

    Constructors never follow a symlink supplied as an authority/target path.
    A missing parent is fine for a new authority member; any present ancestor
    must be a directory reached without a link.  This deliberately keeps the
    path law at the one byte-construction boundary instead of asking every
    caller to remember an ad-hoc ``is_symlink`` check.
    """
    if not _safe_path(locator):
        raise ValueError(f"repository path escapes constructor root: {locator}")
    try:
        root_mode = root.lstat().st_mode
    except OSError as exc:
        raise ValueError("constructor root is unreadable") from exc
    if root.is_symlink() or not stat.S_ISDIR(root_mode):
        raise ValueError("constructor root is not a real directory")
    current = root
    for part in Path(locator).parts[:-1]:
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            break
        except OSError as exc:
            raise ValueError(f"repository ancestor is unreadable: {locator}") from exc
        if current.is_symlink() or not stat.S_ISDIR(mode):
            raise ValueError(f"repository ancestor is not a real directory: {locator}")
    return root / locator


def _regular_file_bytes(root: Path, locator: str, *, noun: str) -> bytes:
    """Read one non-symlink regular file beneath the constructor root."""
    item = _no_follow_path(root, locator)
    try:
        mode = item.lstat().st_mode
        if item.is_symlink() or not stat.S_ISREG(mode):
            raise ValueError(f"{noun} is not a regular file")
        return item.read_bytes()
    except FileNotFoundError as exc:
        raise ValueError(f"{noun} is missing") from exc
    except OSError as exc:
        raise ValueError(f"{noun} is unreadable") from exc


def _working_entry(root: Path, locator: str) -> tuple[bytes, int] | None:
    """Capture one regular worktree entry for a transactional constructor."""
    item = _no_follow_path(root, locator)
    try:
        mode = item.lstat().st_mode
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ValueError(f"constructor member is unreadable: {locator}") from exc
    if item.is_symlink() or not stat.S_ISREG(mode):
        raise ValueError(f"constructor member is not a regular file: {locator}")
    return item.read_bytes(), stat.S_IMODE(mode)


def _write_regular_no_follow(
    root: Path, locator: str, content: bytes, mode: int
) -> None:
    """Write a regular entry without following a final-path symlink."""
    destination = _no_follow_path(root, locator)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _no_follow_path(root, locator)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(destination, flags, mode)
    except OSError as exc:
        raise ValueError(
            f"constructor member cannot be opened without following links: {locator}"
        ) from exc
    with os.fdopen(fd, "wb") as stream:
        stream.write(content)
    destination.chmod(mode)


def _restore_working_entry(
    root: Path, locator: str, entry: tuple[bytes, int] | None
) -> None:
    destination = _no_follow_path(root, locator)
    if entry is None:
        destination.unlink(missing_ok=True)
        return
    content, mode = entry
    _write_regular_no_follow(root, locator, content, mode)


def construct_closure(
    repo: Path,
    *,
    contract: dict,
    contract_locator: str,
    contract_bytes: bytes,
    oracle_locator: str,
    oracle_bytes: bytes,
    supporting: tuple[tuple[str, bytes], ...],
    imports: tuple[tuple[str, bytes, int], ...] = (),
    constructor_root: Path | None = None,
) -> Snapshot:
    _require_schema_valid(contract)
    base = _base_revision(contract)
    resolved = _git(repo, "rev-parse", "--verify", f"{base}^{{commit}}")
    if resolved.returncode:
        raise ValueError("base revision is not a local commit")
    parent = resolved.stdout.strip()
    overlay = _closure_overlay(
        repo,
        contract_locator=contract_locator,
        contract_bytes=contract_bytes,
        oracle_locator=oracle_locator,
        oracle_bytes=oracle_bytes,
        supporting=supporting,
        imports=imports,
    )
    vector = _base_preservation(
        repo,
        base=parent,
        contract=contract,
        excluded=set(overlay),
        locator=contract_locator,
    )
    snapshot = _commit_snapshot(
        repo,
        parent=parent,
        overlay=overlay,
        allowed=set(overlay),
        message=_CLOSURE_MESSAGE,
        constructor_root=constructor_root,
    )
    return Snapshot(
        snapshot.commit,
        snapshot.root,
        snapshot.parent,
        vector,
        frozenset(overlay),
        parent,
    )


def _admitted_lineage(
    root: Path, commit: str, *, message: str, noun: str
) -> tuple[list[tuple[str, str, set[str]]], str]:
    cursor = commit
    lineage: list[tuple[str, str, set[str]]] = []
    while True:
        parent, stored_message, *_rest = _metadata(root, cursor)
        if not parent or stored_message != message + "\n":
            break
        paths = _changed_paths(root, parent, cursor)
        admit_commit(root, parent=parent, commit=cursor, paths=paths, message=message)
        lineage.append((cursor, parent, paths))
        cursor = parent
    if not lineage:
        raise ValueError(f"commit is not an admitted {noun}")
    return lineage, cursor


def construct_closure_correction(
    repo: Path,
    *,
    cited: Snapshot,
    contract: dict,
    contract_locator: str,
    contract_bytes: bytes,
    oracle_locator: str,
    oracle_bytes: bytes,
    supporting: tuple[tuple[str, bytes], ...],
    imports: tuple[tuple[str, bytes, int], ...] = (),
) -> Snapshot:
    """Construct one correction as a bounded, admitted closure child.

    The old mutable round is replaced by Git's own immutable ancestry.  Every
    cited closure is read back before use; a chain may contain C0 plus at most
    three strict corrections.  Same overlay bytes are not a correction.
    """
    _require_schema_valid(contract)
    lineage, base = _admitted_lineage(
        repo, cited.commit, message=_CLOSURE_MESSAGE, noun="closure"
    )
    if len(lineage) >= 4:
        raise ValueError("fourth closure correction is terminal")
    overlay = _closure_overlay(
        repo,
        contract_locator=contract_locator,
        contract_bytes=contract_bytes,
        oracle_locator=oracle_locator,
        oracle_bytes=oracle_bytes,
        supporting=supporting,
        imports=imports,
    )
    if all(
        (content is None and _entry(repo, cited.commit, path) is None)
        or (
            content is not None
            and _git_bytes(repo, "show", f"{cited.commit}:{path}").stdout
            == (content[0] if isinstance(content, tuple) else content)
        )
        for path, content in overlay.items()
    ):
        raise ValueError(
            "same closure bytes under the same identity are not a correction"
        )
    vector = _base_preservation(
        repo,
        base=base,
        contract=contract,
        excluded=set(cited.authority_paths) | set(overlay),
        locator=contract_locator,
    )
    snapshot = _commit_snapshot(
        repo,
        parent=cited.commit,
        overlay=overlay,
        allowed=set(overlay),
        message=_CLOSURE_MESSAGE,
    )
    return Snapshot(
        snapshot.commit,
        snapshot.root,
        snapshot.parent,
        vector,
        cited.authority_paths | frozenset(overlay),
        base,
    )


def recognize_closure(root: Path, commit: str) -> Snapshot:
    """Reconstruct only an admitted closure lineage; messages alone never do."""
    lineage, base = _admitted_lineage(
        root, commit, message=_CLOSURE_MESSAGE, noun="closure"
    )
    # A closure ancestor cannot be skipped: every link through the closure
    # message/metadata/structural postcondition must be admitted.
    authority: set[str] = set()
    for _, _, paths in reversed(lineage):
        authority.update(paths)
    current, parent, _ = lineage[0]
    return Snapshot(current, root, parent, None, frozenset(authority), base)


def recognize_candidate(root: Path, commit: str) -> Snapshot:
    """Reconstruct an admitted K lineage and its admitted closure ancestor."""
    lineage, closure_commit = _admitted_lineage(
        root, commit, message=_CANDIDATE_MESSAGE, noun="candidate"
    )
    closure = recognize_closure(root, closure_commit)
    current, parent, _paths = lineage[0]
    return Snapshot(current, root, parent, None, closure.authority_paths, closure.base)


def closure_for_candidate(root: Path, commit: str) -> Snapshot:
    """Return K's admitted C ancestor after admitting every K correction."""
    _lineage, closure_commit = _admitted_lineage(
        root, commit, message=_CANDIDATE_MESSAGE, noun="candidate"
    )
    return recognize_closure(root, closure_commit)


def _admit_final(
    root: Path, *, base: str, commit: str, tree: str, paths: set[str]
) -> None:
    """Read back the one final projection before returning or CASing it."""
    parents, message, an, ae, cn, ce, ad, cd = _metadata(root, commit)
    if parents != base or message != _FINAL_MESSAGE + "\n":
        raise ValueError(
            "final projection metadata differs from canonical finalization"
        )
    if (
        not _is_structurally_valid_identity(an, ae)
        or (an, ae) != (cn, ce)
        or (ad, cd) != ("0", "0")
    ):
        raise ValueError(
            "final projection identity or date differs from canonical finalization"
        )
    if _git(root, "rev-parse", f"{commit}^{{tree}}").stdout.strip() != tree:
        raise ValueError("final projection tree differs from admitted projection")
    if _changed_paths(root, base, commit) != paths:
        raise ValueError("final path set differs from authorized projection")


def _candidate_preservation(
    root: Path,
    approved: ApprovedClosure,
    *,
    base: str,
    excluded: set[str],
    context: str,
) -> PreservationVector:
    if approved.contract is None:
        raise ValueError("candidate has no sealed contract authority")
    vector = _base_preservation(
        root,
        base=base,
        contract=approved.contract,
        excluded=excluded,
        locator=approved.contract_locator,
    )
    if (
        approved.closure.preservation is not None
        and vector != approved.closure.preservation
    ):
        raise ValueError(
            f"EvidenceGap: {context} preservation sources differ from closure"
        )
    return vector


def _final_preservation(
    repo: Path, *, candidate: Snapshot, contract_locator: str
) -> PreservationVector:
    """Reconstruct F's vector solely from B and K's admitted C bytes."""
    closure = closure_for_candidate(repo, candidate.commit)
    if (
        not _safe_path(contract_locator)
        or contract_locator not in closure.authority_paths
    ):
        raise ValueError("final contract locator is not admitted closure authority")
    entry = _entry(repo, closure.commit, contract_locator)
    if entry is None:
        raise ValueError("final contract is absent from admitted closure")
    fields = entry.split()
    if len(fields) < 3 or not fields[0].startswith("100") or fields[1] != "blob":
        raise ValueError("final contract is not a regular admitted Git blob")
    raw = _git_bytes(repo, "show", f"{closure.commit}:{contract_locator}")
    if raw.returncode:
        raise ValueError("final contract bytes are unreadable from admitted closure")
    try:
        contract = json.loads(raw.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("final contract bytes are not JSON") from exc
    if not isinstance(contract, dict):
        raise ValueError("final contract bytes are not an object")
    _require_schema_valid(contract)
    base = closure.base or closure.parent
    vector = _base_preservation(
        repo,
        base=base,
        contract=contract,
        excluded=set(closure.authority_paths),
        locator=contract_locator,
    )
    if candidate.preservation is not None and candidate.preservation != vector:
        raise ValueError("candidate preservation differs from B-derived final vector")
    return vector


def _target_overlay(
    root: Path, targets: set[str], *, noun: str
) -> dict[str, bytes | None]:
    if any(not _safe_path(path) for path in targets):
        raise ValueError(f"{noun} target escapes repository")
    overlay: dict[str, bytes | None] = {}
    for path in targets:
        item = _no_follow_path(root, path)
        overlay[path] = (
            _regular_file_bytes(root, path, noun=f"{noun} target")
            if item.exists() or item.is_symlink()
            else None
        )
    return overlay


def finalize_candidate(
    repo: Path,
    *,
    candidate: Snapshot,
    base: str,
    authorized_paths: set[str],
    target_ref: str,
    contract_locator: str,
) -> FinalizedDelivery:
    """Project an admitted candidate once onto its original base and CAS it.

    The finalizer deliberately does not redispatch.  Hooks may run once, but
    any tree/path mutation means the projection is no longer the recorded one
    and is therefore indeterminate rather than repairable in this invocation.
    """
    admitted_candidate = recognize_candidate(repo, candidate.commit)
    if admitted_candidate.parent != candidate.parent:
        raise ValueError("final candidate parent differs from admitted lineage")
    derived_base = admitted_candidate.base
    if not derived_base or derived_base != base:
        raise ValueError(
            "final base is not derived from admitted candidate closure ancestry"
        )
    vector = _final_preservation(
        repo, candidate=candidate, contract_locator=contract_locator
    )
    expected_pre_final = set(authorized_paths)
    if _changed_paths(repo, base, candidate.commit) != expected_pre_final:
        raise ValueError("Diff(B,K) differs from ExpectedPreFinal")
    projected_paths = expected_pre_final
    root = _worktree(repo, derived_base)
    fd, index = tempfile.mkstemp(prefix="nwave-final-", suffix=".index")
    os.close(fd)
    Path(index).unlink(missing_ok=True)
    env = {**os.environ, "GIT_INDEX_FILE": index}
    try:
        if _git(root, "read-tree", base, env=env).returncode:
            raise RuntimeError("cannot seed final index")
        for path in expected_pre_final:
            entry = _entry(repo, candidate.commit, path)
            shown = _git_bytes(repo, "show", f"{candidate.commit}:{path}")
            destination = _no_follow_path(root, path)
            if entry is None:
                destination.unlink(missing_ok=True)
            else:
                if shown.returncode:
                    raise RuntimeError(f"cannot read candidate path {path}")
                mode = int(entry.split(" ", 1)[0], 8)
                _write_regular_no_follow(root, path, shown.stdout, stat.S_IMODE(mode))
        if _git(root, "add", "-A", "--", *sorted(projected_paths), env=env).returncode:
            raise RuntimeError("cannot stage final projection")
        expected_tree = _git(root, "write-tree", env=env).stdout.strip()
        # The only successful repeat is the exact projection already installed
        # by this finalizer.  Anything else at the user ref is a concurrent
        # mutation, not a permission to overwrite it.
        current = _git(repo, "rev-parse", "--verify", target_ref)
        expected_ref = base
        if current.returncode == 0 and current.stdout.strip() == candidate.commit:
            # E7 may finalize in the same isolated root that sealed K.  K is
            # an admitted, exact source for this projection, not a concurrent
            # user mutation; retain it as the explicit CAS predecessor.
            expected_ref = candidate.commit
        elif current.returncode == 0 and current.stdout.strip() != base:
            existing = current.stdout.strip()
            try:
                _admit_final(
                    repo,
                    base=base,
                    commit=existing,
                    tree=expected_tree,
                    paths=projected_paths,
                )
            except ValueError:
                raise ValueError("target ref changed before final projection") from None
            clean = _verify_final_checkout(repo, commit=existing, vector=vector)
            no_op = _git(repo, "update-ref", target_ref, existing, existing)
            if no_op.returncode:
                raise ValueError("target ref changed during final replay verification")
            return FinalizedDelivery(
                existing, frozenset(projected_paths), vector, clean
            )
        message = _FINAL_MESSAGE
        final_env = _constructor_commit_env(root, index)
        committed = _git_hook_commit(
            root,
            "-c",
            "commit.gpgSign=false",
            "commit",
            "--quiet",
            "-m",
            message,
            env=final_env,
        )
        if committed.returncode:
            raise RuntimeError(committed.stderr.strip() or committed.stdout.strip())
        final = _git(root, "rev-parse", "HEAD").stdout.strip()
        _assert_clean_constructor_state(root, commit=final, env=final_env)
        _admit_final(
            root, base=base, commit=final, tree=expected_tree, paths=projected_paths
        )
        clean = _verify_final_checkout(repo, commit=final, vector=vector)
        cas = _git(repo, "update-ref", target_ref, final, expected_ref)
        if cas.returncode:
            raise ValueError("target ref CAS failed")
        return FinalizedDelivery(final, frozenset(projected_paths), vector, clean)
    finally:
        Path(index).unlink(missing_ok=True)
        _remove_worktree(repo, root)


class CandidateConstructor:
    """Unregistered constructor invoked only by the platform hook."""

    def seal(
        self, approved: ApprovedClosure, writable_root: Path, targets: set[str]
    ) -> Snapshot:
        if (
            _git(writable_root, "rev-parse", "HEAD").stdout.strip()
            != approved.closure.commit
        ):
            raise ValueError("candidate root HEAD is not approved closure")
        authority_paths = approved.authority_paths or approved.closure.authority_paths
        if targets & authority_paths:
            raise ValueError("contract production targets intersect AuthorityPaths")
        overlay = _target_overlay(writable_root, targets, noun="candidate")
        # Reconstruct from the original base, not mutable closure/candidate
        # bytes.  The closure's exact delta is also the authoritative set of
        # newly introduced paths excluded at closure construction.
        vector = _candidate_preservation(
            writable_root,
            approved,
            base=approved.closure.base or approved.closure.parent,
            excluded=set(authority_paths),
            context="candidate",
        )
        snapshot = _commit_snapshot(
            writable_root,
            parent=approved.closure.commit,
            overlay=overlay,
            allowed=targets,
            message=_CANDIDATE_MESSAGE,
            constructor_root=writable_root,
        )
        # All closure lineage authority is immutable through candidate
        # construction, including bytes, mode and deletions.  This makes the
        # later squash's source unambiguous rather than merely path-shaped.
        for path in authority_paths:
            if _entry(snapshot.root, snapshot.commit, path) != _entry(
                writable_root, approved.closure.commit, path
            ):
                raise ValueError("candidate changed closure authority")
        # Candidate evidence runs the same B-derived argv, but against the
        # committed post-hook bytes.  Source blobs and argv were already
        # compared above; this is not a loose re-discovery from K.
        run_preservation(snapshot.root, vector)
        return Snapshot(
            snapshot.commit,
            snapshot.root,
            snapshot.parent,
            vector,
            frozenset(authority_paths),
            approved.closure.base or approved.closure.parent,
        )

    def seal_correction(
        self,
        approved: ApprovedClosure,
        cited: Snapshot,
        writable_root: Path,
        targets: set[str],
    ) -> Snapshot:
        """Construct a bounded strict child of an admitted candidate, never C.

        This replaces the retired mutable revision round.  It is intentionally
        private like ``seal``; platform joins decide which cited K is valid.
        """
        lineage, closure_cursor = _admitted_lineage(
            writable_root,
            cited.commit,
            message=_CANDIDATE_MESSAGE,
            noun="candidate",
        )
        closure = recognize_closure(writable_root, closure_cursor)
        if closure.commit != approved.closure.commit:
            raise ValueError(
                "production correction is not bound to its approved closure"
            )
        if len(lineage) >= 4:
            raise ValueError("fourth candidate correction is terminal")
        if _git(writable_root, "rev-parse", "HEAD").stdout.strip() != cited.commit:
            raise ValueError("candidate correction root HEAD is not cited candidate")
        authority_paths = approved.authority_paths or approved.closure.authority_paths
        if targets & authority_paths:
            raise ValueError("candidate correction targets intersect AuthorityPaths")
        overlay = _target_overlay(writable_root, targets, noun="candidate correction")
        if all(
            (content is None and _entry(writable_root, cited.commit, path) is None)
            or (
                content is not None
                and _git_bytes(writable_root, "show", f"{cited.commit}:{path}").stdout
                == content
            )
            for path, content in overlay.items()
        ):
            raise ValueError(
                "same candidate bytes under the same identity are not a correction"
            )
        vector = _candidate_preservation(
            writable_root,
            approved,
            base=closure.base or approved.closure.parent,
            excluded=set(authority_paths),
            context="candidate correction",
        )
        snapshot = _commit_snapshot(
            writable_root,
            parent=cited.commit,
            overlay=overlay,
            allowed=targets,
            message=_CANDIDATE_MESSAGE,
            constructor_root=writable_root,
        )
        for path in authority_paths:
            if _entry(snapshot.root, snapshot.commit, path) != _entry(
                writable_root, cited.commit, path
            ):
                raise ValueError("candidate correction changed closure authority")
        run_preservation(snapshot.root, vector)
        return Snapshot(
            snapshot.commit,
            snapshot.root,
            snapshot.parent,
            vector,
            frozenset(authority_paths),
            closure.base,
        )
