#!/usr/bin/env python3
"""Pure-Python commit reachability, read straight off ``.git/``.

The only runtime dependency is Python: no ``git`` binary, no external package.
The port answers one question -- *is commit X reachable from ref R?* -- with a
mandatory third state, so a caller can never mistake "I could not tell" for
"yes".

Loose-first-then-packed walk
-----------------------------
The walk reads commit objects loose first, falling back to
``git_packed_objects.PackedObjectStore`` the moment a commit is not loose --
the same discipline ``git_commit_contents.LooseObjectContents`` already
applies to its own object reads. ``git gc``/``git repack -ad`` packs objects
on its own schedule, so a walk that only ever opened loose commits decayed
silently the moment history got packed: a real ancestor pinned in a Mikado
closure, once repacked, could no longer be *proven* an ancestor even though
nothing about the history changed. Reading packed commits directly removes
that decay.

The closure argument that used to carry the whole adapter -- *a pack is
closed under reachability, so a target absent from every pack means every
commit on the path to it is loose* -- still holds, but now only as
defense-in-depth for the residual truly-unreadable case: a commit that is
neither loose NOR decodable from any pack (corrupt pack, unresolvable delta
base, an object present in no pack at all). That case still degrades to
INDETERMINATE, never a silent NOT_REACHABLE or a wrong REACHABLE. Shallow
clones and promisor/partial packs break the underlying object-completeness
assumption entirely, so they are detected up front and downgrade the whole
adapter to INDETERMINATE before any walk starts.

Relocated from ``scripts/validation/git_commit_reachability.py`` (gate-
ratchet-skill-normative, Mikado D86): ``src/des/`` production code (the
skill-normative gate's ratchet baseline) needed this reader too, and
``src/des/`` cannot import ``scripts/`` (dev-only, not shipped).
``scripts/validation/git_commit_reachability.py`` is now a thin shim
re-exporting this module's public names, so the pre-commit-invoked
``validate_mikado_tree_coherence.py`` keeps working byte-identically.
"""

from __future__ import annotations

import binascii
import struct
import zlib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

from des.adapters.driven.git.git_packed_objects import PackedObjectStore


class Reachability(str, Enum):
    """Whether a commit is an ancestor of a ref. Three states, always."""

    REACHABLE = "REACHABLE"
    NOT_REACHABLE = "NOT_REACHABLE"
    INDETERMINATE = "INDETERMINATE"


@dataclass(frozen=True)
class ReachabilityAnswer:
    """A verdict plus the reason it can be trusted (or cannot)."""

    outcome: Reachability
    detail: str
    resolved_sha: str | None = None


class CommitReachabilityPort(Protocol):
    """Driven port: resolve whether ``sha_prefix`` is an ancestor of ``ref``."""

    def reachable_from(self, sha_prefix: str, ref: str) -> ReachabilityAnswer: ...

    def resolve_head(self) -> str | None: ...


class UnavailableReachability:
    """Null adapter: no object store, so every question is INDETERMINATE.

    Used when ``.git/`` is absent (a released tarball, a CI checkout without
    history). It degrades LOUD -- it never answers REACHABLE.
    """

    def __init__(self, reason: str) -> None:
        self._reason = reason

    def reachable_from(self, sha_prefix: str, ref: str) -> ReachabilityAnswer:
        return ReachabilityAnswer(Reachability.INDETERMINATE, self._reason)

    def resolve_head(self) -> str | None:
        return None


def _read_gitdir_pointer(dot_git: Path) -> Path | None:
    """A worktree's ``.git`` is a file holding ``gitdir: <path>``."""
    try:
        text = dot_git.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        if line.startswith("gitdir:"):
            return Path(line.split(":", 1)[1].strip())
    return None


def locate_git_dirs(start: Path) -> tuple[Path, Path] | None:
    """Return ``(gitdir, commondir)`` for ``start``, or None if not a checkout.

    ``commondir`` is where objects and packed-refs live; in a linked worktree
    it differs from ``gitdir``.
    """
    current = start.resolve()
    for candidate in [current, *current.parents]:
        dot_git = candidate / ".git"
        if dot_git.is_dir():
            gitdir = dot_git
        elif dot_git.is_file():
            pointed = _read_gitdir_pointer(dot_git)
            if pointed is None:
                continue
            gitdir = pointed if pointed.is_absolute() else (candidate / pointed)
        else:
            continue
        common_marker = gitdir / "commondir"
        if common_marker.is_file():
            raw = common_marker.read_text(encoding="utf-8").strip()
            common = Path(raw) if Path(raw).is_absolute() else (gitdir / raw)
            return gitdir.resolve(), common.resolve()
        return gitdir.resolve(), gitdir.resolve()
    return None


def locate_worktree_root(start: Path) -> Path | None:
    """The directory that OWNS the ``.git`` entry above ``start``, or None.

    ``locate_git_dirs`` answers where the objects live; this answers where the
    tracked paths are rooted, which is what a caller needs to turn an absolute
    file path into the repo-relative path a git tree is keyed by.
    """
    current = start.resolve()
    for candidate in [current, *current.parents]:
        dot_git = candidate / ".git"
        if dot_git.is_dir() or dot_git.is_file():
            return candidate
    return None


class LooseObjectReachability:
    """Reachability by walking commit objects under ``.git/objects``, loose first then packed."""

    #: Upper bound on commits visited, so a pathological history cannot hang a
    #: pre-commit hook. Exhausting it yields INDETERMINATE, never a pass.
    WALK_BUDGET = 20000

    def __init__(self, repo_path: Path) -> None:
        located = locate_git_dirs(repo_path)
        self._gitdir = located[0] if located else None
        self._common = located[1] if located else None
        self._unsound_reason = self._detect_broken_closure()
        self._pack_index_cache: list[tuple[Path, bytes, int]] | None = None
        self._commit_cache: dict[str, bytes | None] = {}
        #: sha -> its commit's parent shas, memoized alongside `_commit_cache`.
        #: Parents are a pure function of a commit's (immutable) body, and
        #: `reachable_from` calls `_parents_of` once per visit to every sha in
        #: every walk -- without this, a body already sitting in
        #: `_commit_cache` still pays a fresh `bytes.split()` re-parse on
        #: every walk that revisits it.
        self._parents_cache: dict[str, list[str]] = {}
        self._packed = (
            PackedObjectStore(self._common / "objects")
            if self._common is not None
            else None
        )

    # -- preconditions ----------------------------------------------------

    def _detect_broken_closure(self) -> str | None:
        """Name the conditions under which pack-closure does not hold."""
        if self._common is None:
            return "no git object store found: reachability not verifiable"
        if (self._common / "shallow").exists():
            return "shallow clone: history is truncated, ancestry not verifiable"
        pack_dir = self._common / "objects" / "pack"
        if pack_dir.is_dir() and any(pack_dir.glob("*.promisor")):
            return "promisor pack (partial clone): objects missing locally"
        config = self._common / "config"
        if config.is_file():
            text = config.read_text(encoding="utf-8", errors="replace")
            if "sha256" in text.replace(" ", "").lower():
                return "sha256 repository: this reader only decodes 20-byte oids"
        return None

    # -- refs -------------------------------------------------------------

    def resolve_head(self) -> str | None:
        """The commit THIS checkout's HEAD points at, or None when undecidable.

        Read from the per-worktree ``gitdir``, never from the shared common
        dir. A linked worktree keeps its own ``HEAD`` beside its index while
        its branch refs stay shared, so asking ``resolve_ref("HEAD")`` would
        find the MAIN checkout's HEAD instead -- a different commit, silently,
        and any measurement taken against it would be a measurement of bytes
        nobody asked about.
        """
        if self._gitdir is None:
            return None
        head = self._gitdir / "HEAD"
        if not head.is_file():
            return None
        value = head.read_text(encoding="utf-8", errors="replace").strip()
        if value.startswith("ref:"):
            return self.resolve_ref(value.split(":", 1)[1].strip())
        return value if _looks_like_sha(value) else None

    def resolve_ref(self, ref: str) -> str | None:
        """Resolve a ref name to a full sha, loose ref first then packed-refs."""
        if self._common is None:
            return None
        candidates = [
            ref,
            f"refs/heads/{ref}",
            f"refs/remotes/{ref}",
            f"refs/tags/{ref}",
        ]
        for name in candidates:
            loose = self._common / name
            if loose.is_file():
                value = loose.read_text(encoding="utf-8", errors="replace").strip()
                if value.startswith("ref:"):
                    return self.resolve_ref(value.split(":", 1)[1].strip())
                if _looks_like_sha(value):
                    return value
        packed = self._common / "packed-refs"
        if packed.is_file():
            wanted = set(candidates)
            for line in packed.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines():
                if not line or line.startswith(("#", "^")):
                    continue
                parts = line.split(None, 1)
                if len(parts) == 2 and parts[1].strip() in wanted:
                    return parts[0].strip()
        return None

    # -- objects ----------------------------------------------------------

    def _loose_path(self, sha: str) -> Path | None:
        if self._common is None:
            return None
        return self._common / "objects" / sha[:2] / sha[2:]

    def _read_loose_commit(self, sha: str) -> bytes | None:
        path = self._loose_path(sha)
        if path is None or not path.is_file():
            return None
        try:
            raw = zlib.decompress(path.read_bytes())
        except (OSError, zlib.error):
            return None
        header, _, body = raw.partition(b"\x00")
        if not header.startswith(b"commit "):
            return None
        return body

    def _read_commit(self, sha: str) -> bytes | None:
        """Commit body, loose first then packed. None means unreadable via EITHER path.

        Loose stays first because it is the cheaper read; the packed fallback
        only pays its index parse when the loose path misses, mirroring
        ``git_commit_contents.LooseObjectContents._read_object``. A ``None``
        here is the sole trigger for the walk's frontier-miss handling below --
        it is never treated as "does not exist", only as "could not read".

        Results are memoized per instance, keyed by sha. Commit objects are
        immutable once written, so a decoded body stays valid for the life of
        this process -- and an unreadable verdict (``None``) is exactly as
        durable: the same object will still be unreadable on a later call
        within the same run. This is what lets repeated ``reachable_from``
        calls on one instance share the ancestor decode work instead of
        re-walking and re-inflating the same near-tip commits from scratch
        every time.
        """
        if sha in self._commit_cache:
            return self._commit_cache[sha]
        body = self._read_commit_uncached(sha)
        self._commit_cache[sha] = body
        return body

    def _read_commit_uncached(self, sha: str) -> bytes | None:
        loose = self._read_loose_commit(sha)
        if loose is not None:
            return loose
        if self._packed is None:
            return None
        packed = self._packed.read(sha)
        if packed is None or packed[0] != "commit":
            return None
        return packed[1]

    def _parents_of_sha(self, sha: str, body: bytes) -> list[str]:
        """``_parents_of(body)``, memoized by ``sha``.

        The module-level `_parents_of` remains the single parser -- this
        wraps it, it does not replace it. Commit bytes are immutable, so the
        memo cannot go stale within a run.
        """
        cached = self._parents_cache.get(sha)
        if cached is not None:
            return cached
        parents = _parents_of(body)
        self._parents_cache[sha] = parents
        return parents

    def _pack_indexes(self) -> list[tuple[Path, bytes, int]]:
        """Load every ``*.idx`` as ``(path, sorted_oid_table, count)``."""
        if self._pack_index_cache is not None:
            return self._pack_index_cache
        loaded: list[tuple[Path, bytes, int]] = []
        if self._common is not None:
            pack_dir = self._common / "objects" / "pack"
            if pack_dir.is_dir():
                for idx in sorted(pack_dir.glob("*.idx")):
                    parsed = _parse_pack_idx_v2(idx)
                    if parsed is not None:
                        loaded.append((idx, parsed[0], parsed[1]))
        self._pack_index_cache = loaded
        return loaded

    def _packed_matches(self, prefix_bytes: bytes, odd_nibble: bool) -> list[str]:
        # A v2 idx oid table is sorted by full oid, therefore also sorted by
        # every prefix of it, so the rows whose oid begins with a given
        # WHOLE-BYTE prefix are contiguous -- found in O(log n) instead of a
        # scan of every one of (possibly 100k+) packed oids. Only the
        # whole-byte part of the prefix bounds the window (`prefix_bytes[:-1]`
        # when `odd_nibble`, else `prefix_bytes` itself); the odd nibble is
        # left for `_oid_matches` to apply inside that window, unchanged, so
        # the odd-nibble predicate cannot drift between the two call sites.
        whole = prefix_bytes[:-1] if odd_nibble else prefix_bytes
        found: list[str] = []
        for _, table, count in self._pack_indexes():
            start, stop = self._prefix_window(table, count, whole)
            for i in range(start, stop):
                oid = table[i * 20 : (i + 1) * 20]
                if _oid_matches(oid, prefix_bytes, odd_nibble):
                    found.append(binascii.hexlify(oid).decode())
        return found

    @staticmethod
    def _prefix_window(table: bytes, count: int, whole: bytes) -> tuple[int, int]:
        """Return the ``[start, stop)`` row range whose oids begin with ``whole``.

        A v2 idx oid table is sorted by full oid, therefore also sorted by
        every prefix of it, so the matches for one prefix are contiguous and
        findable in O(log n) instead of a scan of the whole pack.
        """
        width = len(whole)
        if width == 0:
            return 0, count
        lo, hi = 0, count
        while lo < hi:
            mid = (lo + hi) // 2
            if table[mid * 20 : mid * 20 + width] < whole:
                lo = mid + 1
            else:
                hi = mid
        start, hi = lo, count
        while lo < hi:
            mid = (lo + hi) // 2
            if table[mid * 20 : mid * 20 + width] <= whole:
                lo = mid + 1
            else:
                hi = mid
        return start, lo

    def _loose_matches(self, prefix: str) -> list[str]:
        if self._common is None or len(prefix) < 2:
            return []
        directory = self._common / "objects" / prefix[:2]
        if not directory.is_dir():
            return []
        rest = prefix[2:]
        return [
            prefix[:2] + entry.name
            for entry in directory.iterdir()
            if entry.is_file() and entry.name.startswith(rest)
        ]

    def resolve_object(self, sha_prefix: str) -> tuple[list[str], bool]:
        """Return ``(full_shas_matching_prefix, is_present_in_some_pack)``."""
        prefix = sha_prefix.strip().lower()
        odd = len(prefix) % 2 == 1
        try:
            prefix_bytes = binascii.unhexlify(prefix[:-1] if odd else prefix)
        except binascii.Error:
            return [], False
        packed = self._packed_matches(
            prefix_bytes + (bytes([int(prefix[-1], 16)]) if odd else b""), odd
        )
        loose = self._loose_matches(prefix)
        return sorted(set(packed) | set(loose)), bool(packed)

    # -- the walk ---------------------------------------------------------

    def reachable_from(self, sha_prefix: str, ref: str) -> ReachabilityAnswer:
        if self._unsound_reason is not None:
            return ReachabilityAnswer(Reachability.INDETERMINATE, self._unsound_reason)

        tip = self.resolve_ref(ref)
        if tip is None:
            return ReachabilityAnswer(
                Reachability.INDETERMINATE,
                f"ref `{ref}` not resolvable in this object store",
            )

        matches, is_packed = self.resolve_object(sha_prefix)
        if len(matches) > 1:
            return ReachabilityAnswer(
                Reachability.INDETERMINATE,
                f"prefix `{sha_prefix}` is ambiguous: {len(matches)} objects match",
            )
        if not matches:
            return ReachabilityAnswer(
                Reachability.NOT_REACHABLE,
                f"no object `{sha_prefix}` exists in this repository",
            )
        target = matches[0]

        seen: set[str] = set()
        frontier_packed = False
        pending = [tip]
        visited = 0
        while pending:
            sha = pending.pop()
            if sha in seen:
                continue
            seen.add(sha)
            if sha == target:
                # A sha matching the target in the idx/loose-filename table
                # only proves the OID is *indexed* -- not that its bytes are
                # actually decodable (a corrupt pack entry can still have a
                # valid idx row). Confirm the object itself reads clean
                # before trusting REACHABLE; a match that fails to decode
                # stays INDETERMINATE, never a silently-wrong REACHABLE.
                if self._read_commit(sha) is None:
                    return ReachabilityAnswer(
                        Reachability.INDETERMINATE,
                        (
                            f"`{target[:9]}` is indexed in this repository but its "
                            "object bytes are not decodable via the loose or the "
                            "packed path: reachability not verifiable"
                        ),
                        target,
                    )
                return ReachabilityAnswer(
                    Reachability.REACHABLE,
                    f"reachable from `{ref}` in {len(seen)} commits visited",
                    target,
                )
            visited += 1
            if visited > self.WALK_BUDGET:
                return ReachabilityAnswer(
                    Reachability.INDETERMINATE,
                    f"walk budget ({self.WALK_BUDGET} commits) exhausted without deciding",
                    target,
                )
            body = self._read_commit(sha)
            if body is None:
                frontier_packed = True
                continue
            pending.extend(self._parents_of_sha(sha, body))

        if is_packed and frontier_packed:
            return ReachabilityAnswer(
                Reachability.INDETERMINATE,
                (
                    f"`{target[:9]}` lives in a packfile and the walk hit a commit "
                    "unreadable via either the loose or the packed path: not "
                    "decidable"
                ),
                target,
            )
        return ReachabilityAnswer(
            Reachability.NOT_REACHABLE,
            (
                f"`{target[:9]}` does not appear among the {len(seen)} ancestors of "
                f"`{ref}`"
                + ("" if is_packed else " (loose object: the walk is complete)")
            ),
            target,
        )


def _looks_like_sha(value: str) -> bool:
    return len(value) == 40 and all(c in "0123456789abcdef" for c in value.lower())


def _parents_of(commit_body: bytes) -> list[str]:
    parents: list[str] = []
    for raw_line in commit_body.split(b"\n"):
        if raw_line.startswith(b"parent "):
            parents.append(raw_line[7:].decode("ascii", errors="replace").strip())
        elif not raw_line:
            break
    return parents


def _oid_matches(oid: bytes, prefix_bytes: bytes, odd_nibble: bool) -> bool:
    if odd_nibble:
        whole = prefix_bytes[:-1]
        if not oid.startswith(whole):
            return False
        return oid[len(whole)] >> 4 == prefix_bytes[-1]
    return oid.startswith(prefix_bytes)


def _parse_pack_idx_v2(path: Path) -> tuple[bytes, int] | None:
    """Return ``(sorted_oid_table, object_count)`` from a v2 pack index."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) < 8 + 256 * 4 or data[:4] != b"\xfftOc":
        return None
    if struct.unpack(">I", data[4:8])[0] != 2:
        return None
    count = struct.unpack(">I", data[8 + 255 * 4 : 8 + 256 * 4])[0]
    start = 8 + 256 * 4
    end = start + count * 20
    if len(data) < end:
        return None
    return data[start:end], count


def build_reachability(repo_path: Path) -> CommitReachabilityPort:
    """Pick the adapter that this machine can actually honour."""
    if locate_git_dirs(repo_path) is None:
        return UnavailableReachability(
            f"no git checkout under `{repo_path}`: reachability not verifiable"
        )
    return LooseObjectReachability(repo_path)
