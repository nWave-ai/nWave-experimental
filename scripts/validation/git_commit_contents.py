#!/usr/bin/env python3
"""Pure-Python "what did this commit change?", read straight off ``.git/``.

Sibling of :mod:`git_commit_reachability`, same contract and same discipline:
the only runtime dependency is Python -- no ``git`` binary, no external
package -- and the answer has a mandatory third state, so a caller can never
mistake "I could not tell" for "it changed nothing".

Scope of the AVAILABLE answer
-----------------------------
The reader decodes *loose* objects only (a commit, then the tree pair it and
its parent point at, recursively). Two trees that carry the same oid are equal
by construction, so an unchanged subtree is never opened -- the walk only ever
touches objects the commit actually rewrote. When some object on that path is
packed, the reader says INDETERMINATE and names the object; it never returns a
short path list as if it were complete.

A merge is diffed against its FIRST parent, which is the honest reading of
"what did landing this commit change": for a lane merged into trunk, that is
the whole set of files the lane contributed. The answer records how many
parents it was computed against, so a caller can weigh it.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    from pathlib import Path

from git_commit_reachability import LooseObjectReachability, locate_git_dirs
from git_packed_objects import PackedObjectStore


class ContentAvailability(str, Enum):
    """Whether the changed-path set could be computed. Three states, always."""

    AVAILABLE = "AVAILABLE"
    INDETERMINATE = "INDETERMINATE"


@dataclass(frozen=True)
class ChangedPathsAnswer:
    """The paths a commit rewrote, or the reason they are not knowable."""

    outcome: ContentAvailability
    paths: tuple[str, ...]
    detail: str
    resolved_sha: str | None = None
    #: How many parents the commit has. >1 means ``paths`` is a first-parent
    #: diff -- what the merge brought onto the branch it landed on.
    parent_count: int = 0

    @property
    def is_available(self) -> bool:
        return self.outcome is ContentAvailability.AVAILABLE


class CommitContentsPort(Protocol):
    """Driven port: which paths did ``sha_prefix`` rewrite?"""

    def changed_paths(self, sha_prefix: str) -> ChangedPathsAnswer: ...


class UnavailableContents:
    """Null adapter: no object store, so every question is INDETERMINATE."""

    def __init__(self, reason: str) -> None:
        self._reason = reason

    def changed_paths(self, sha_prefix: str) -> ChangedPathsAnswer:
        return ChangedPathsAnswer(
            ContentAvailability.INDETERMINATE, (), self._reason, None
        )


class LooseObjectContents:
    """Changed-path sets by diffing loose tree objects under ``.git/objects``."""

    #: Upper bound on tree objects opened for one commit, so a pathological
    #: rewrite cannot hang a hook. Exhausting it yields INDETERMINATE.
    TREE_BUDGET = 4000

    def __init__(self, repo_path: Path) -> None:
        located = locate_git_dirs(repo_path)
        self._common = located[1] if located else None
        self._resolver = LooseObjectReachability(repo_path)
        #: Packed objects are read too. A reader that saw only loose objects
        #: decayed silently: `git gc` packs on its own schedule, so a closure
        #: naming an artifact became unverifiable for an environmental reason
        #: the author never caused. Still pure Python -- no `git` dependency.
        self._packed = (
            PackedObjectStore(self._common / "objects")
            if self._common is not None
            else None
        )

    # -- objects ----------------------------------------------------------

    def _read_loose(self, sha: str) -> tuple[str, bytes] | None:
        """Return ``(type, body)`` for a loose object, or None if not loose."""
        if self._common is None:
            return None
        path = self._common / "objects" / sha[:2] / sha[2:]
        if not path.is_file():
            return None
        try:
            raw = zlib.decompress(path.read_bytes())
        except (OSError, zlib.error):
            return None
        header, _, body = raw.partition(b"\x00")
        kind = header.split(b" ", 1)[0].decode("ascii", errors="replace")
        return kind, body

    def _read_object(self, sha: str) -> tuple[str, bytes] | None:
        """``(type, body)`` from a loose object, else from a pack, else None.

        Loose first because it is the cheaper read; the pack lookup only pays
        its index parse when the loose path misses. None still means the honest
        INDETERMINATE -- neither reader guesses.
        """
        loaded = self._read_loose(sha)
        if loaded is not None:
            return loaded
        return self._packed.read(sha) if self._packed is not None else None

    @staticmethod
    def _tree_entries(body: bytes) -> dict[str, tuple[str, str]]:
        """Parse a tree body into ``{name: (mode, oid_hex)}``."""
        entries: dict[str, tuple[str, str]] = {}
        cursor = 0
        end = len(body)
        while cursor < end:
            space = body.find(b" ", cursor)
            null = body.find(b"\x00", space + 1)
            if space < 0 or null < 0 or null + 20 > end:
                break
            mode = body[cursor:space].decode("ascii", errors="replace")
            name = body[space + 1 : null].decode("utf-8", errors="replace")
            oid = body[null + 1 : null + 21].hex()
            entries[name] = (mode, oid)
            cursor = null + 21
        return entries

    @staticmethod
    def _header_field(commit_body: bytes, field: bytes) -> list[str]:
        values: list[str] = []
        for line in commit_body.split(b"\n"):
            if not line:
                break
            if line.startswith(field + b" "):
                values.append(
                    line[len(field) + 1 :].decode("ascii", errors="replace").strip()
                )
        return values

    # -- the diff ---------------------------------------------------------

    def changed_paths(self, sha_prefix: str) -> ChangedPathsAnswer:
        matches, is_packed = self._resolver.resolve_object(sha_prefix)
        if len(matches) > 1:
            return ChangedPathsAnswer(
                ContentAvailability.INDETERMINATE,
                (),
                f"prefix `{sha_prefix}` is ambiguous: {len(matches)} objects match",
            )
        if not matches:
            return ChangedPathsAnswer(
                ContentAvailability.INDETERMINATE,
                (),
                f"no object `{sha_prefix}` exists in this repository",
            )
        sha = matches[0]

        loaded = self._read_object(sha)
        if loaded is None or loaded[0] != "commit":
            packed = " (neither a loose object nor readable in any pack)"
            return ChangedPathsAnswer(
                ContentAvailability.INDETERMINATE,
                (),
                f"commit `{sha[:9]}` is not readable as a loose object"
                + (packed if is_packed else ""),
                sha,
            )
        body = loaded[1]

        trees = self._header_field(body, b"tree")
        parents = self._header_field(body, b"parent")
        if not trees:
            return ChangedPathsAnswer(
                ContentAvailability.INDETERMINATE,
                (),
                f"commit `{sha[:9]}` carries no tree header",
                sha,
            )
        new_tree = trees[0]
        old_tree: str | None = None
        if parents:
            parent_loaded = self._read_object(parents[0])
            if parent_loaded is None or parent_loaded[0] != "commit":
                return ChangedPathsAnswer(
                    ContentAvailability.INDETERMINATE,
                    (),
                    (
                        f"the parent `{parents[0][:9]}` of `{sha[:9]}` is not readable as "
                        "a loose object: the diff base is missing"
                    ),
                    sha,
                )
            parent_trees = self._header_field(parent_loaded[1], b"tree")
            if not parent_trees:
                return ChangedPathsAnswer(
                    ContentAvailability.INDETERMINATE,
                    (),
                    f"the parent `{parents[0][:9]}` carries no tree header",
                    sha,
                )
            old_tree = parent_trees[0]

        collected: list[str] = []
        budget = [self.TREE_BUDGET]
        unreadable = self._walk(old_tree, new_tree, "", collected, budget)
        if unreadable is not None:
            return ChangedPathsAnswer(
                ContentAvailability.INDETERMINATE, (), unreadable, sha, len(parents)
            )
        against = " (first-parent diff of a merge)" if len(parents) > 1 else ""
        return ChangedPathsAnswer(
            ContentAvailability.AVAILABLE,
            tuple(sorted(collected)),
            f"{len(collected)} paths rewritten by `{sha[:9]}`{against}",
            sha,
            len(parents),
        )

    def recent_commits(self, ref: str, limit: int) -> tuple[list[str], bool]:
        """Walk first-parent from ``ref`` and return ``(shas, walk_was_complete)``.

        Used to answer "which commit DOES carry this artifact?" -- an
        affordance, not a gate decision, so a truncated walk is fine as long as
        the caller is told it was truncated.
        """
        tip = self._resolver.resolve_ref(ref)
        if tip is None:
            return [], False
        walked: list[str] = []
        sha: str | None = tip
        while sha is not None and len(walked) < limit:
            walked.append(sha)
            loaded = self._read_object(sha)
            if loaded is None or loaded[0] != "commit":
                return walked, False
            parents = self._header_field(loaded[1], b"parent")
            sha = parents[0] if parents else None
        return walked, sha is None

    def _walk(
        self,
        old_tree: str | None,
        new_tree: str | None,
        prefix: str,
        out: list[str],
        budget: list[int],
    ) -> str | None:
        """Collect changed paths; return a reason string when undecidable."""
        if old_tree == new_tree:
            return None
        if budget[0] <= 0:
            return (
                f"tree budget ({self.TREE_BUDGET} objects) exhausted before the diff "
                "was complete"
            )

        def side(oid: str | None) -> dict[str, tuple[str, str]] | str:
            if oid is None:
                return {}
            budget[0] -= 1
            loaded = self._read_object(oid)
            if loaded is None or loaded[0] != "tree":
                return (
                    f"tree object `{oid[:9]}` (at `{prefix or '/'}`) is not readable as "
                    "a loose object: the diff cannot be completed"
                )
            return self._tree_entries(loaded[1])

        old_entries = side(old_tree)
        if isinstance(old_entries, str):
            return old_entries
        new_entries = side(new_tree)
        if isinstance(new_entries, str):
            return new_entries

        for name in sorted(set(old_entries) | set(new_entries)):
            old = old_entries.get(name)
            new = new_entries.get(name)
            if old == new:
                continue
            path = f"{prefix}{name}"
            old_is_tree = old is not None and old[0] == "40000"
            new_is_tree = new is not None and new[0] == "40000"
            if old_is_tree or new_is_tree:
                reason = self._walk(
                    old[1] if old_is_tree else None,
                    new[1] if new_is_tree else None,
                    path + "/",
                    out,
                    budget,
                )
                if reason is not None:
                    return reason
                if old is not None and new is not None and old_is_tree != new_is_tree:
                    out.append(path)
            else:
                out.append(path)
        return None


def build_contents(repo_path: Path) -> CommitContentsPort:
    """Pick the adapter that this machine can actually honour."""
    if locate_git_dirs(repo_path) is None:
        return UnavailableContents(
            f"no git checkout under `{repo_path}`: commit contents not verifiable"
        )
    return LooseObjectContents(repo_path)
