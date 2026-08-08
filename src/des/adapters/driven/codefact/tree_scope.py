"""``TreeScope`` — the shared ignore-derived, cached tree-walk floor.

Both `CodeFactPort` floor tiers (:class:`AstAdapter`, :class:`TextSearchAdapter`)
walk the SAME target tree for every capability query. This module is the ONE
shared component both delegate to (Reuse Analysis, `fix-blast-radius-reparses-
tree-per-symbol`), so the two properties below are fixed ONCE, never duplicated
(and possibly drifting) per tier:

1. **Ignore-derived exclusion** — a directory NAME declared in the target's own
   root ``.gitignore`` is excluded from every walk. Parsed in pure Python
   (``pathlib`` + no external dependency, GDP-7) — NEVER a hardcoded per-repo-
   shape name list, and NEVER a ``git check-ignore`` shell-out. An absent ignore
   file preserves today's unfiltered walk (GDP-6: never a silently narrower
   default).
2. **Single-pass-per-glob caching** — a ``root``/glob-pattern pair is walked at
   most ONCE per :class:`TreeScope` instance; a second call with the same
   pattern reuses the prior result. This is the no-reparse-per-symbol contract:
   an adapter constructed once and queried for N distinct symbols costs one walk,
   not N.

The health signal (GDP-6, degrade-LOUD) is read via :meth:`health_event`:

* ``"unfiltered"`` — no ignore file was present; the walk could not have
  excluded anything, distinct from "an ignore file ran and excluded nothing".
* ``"filtered"`` — the walk actually dropped at least one path this instance's
  lifetime; a caller (e.g. an empty answer) must not treat that answer as an
  unqualified, confident zero.
* ``None`` — an ignore file was present but nothing under it was ever excluded
  (no signal needed; the caller's answer is a genuine, unfiltered-equivalent
  result).

Ignore-file dialect: only ``.gitignore`` at the root, one directory NAME per
line (trailing ``/`` optional), ``#`` comments, blank lines skipped, and a
leading ``!`` negates a prior exclusion — the minimum bar this feature's
DISTILL dispatch pinned; a path-qualified or globbed line (containing ``/`` or
``*``) is skipped rather than guessed at, never silently mismatched.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


_IGNORE_FILE_NAME = ".gitignore"


class TreeScope:
    """Ignore-derived exclusion + single-pass-per-glob cache for one tree walk.

    Constructed once per adapter instance with the tree's ``root``. Cheap to
    construct — the ignore file (if any) is parsed once, up front; the tree
    itself is walked lazily, on the first :meth:`files` call for a given glob.
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self.ignore_file_present = (root / _IGNORE_FILE_NAME).is_file()
        self._excluded_names = self._parse_ignore_file(root)
        self.excluded_any = False
        self._file_cache: dict[str, list[Path]] = {}

    def files(self, glob_pattern: str) -> list[Path]:
        """Every file matching ``glob_pattern`` under ``root``, walked ONCE.

        A single file root (no directory to walk) is returned only when it
        matches ``glob_pattern``.  Returning a ``.ts`` file for ``*.py`` would
        falsely advertise Python-AST coverage.  A repeat call with the SAME
        ``glob_pattern`` reuses the cached result instead of re-walking.
        """
        cached = self._file_cache.get(glob_pattern)
        if cached is not None:
            return cached
        if self._root.is_file():
            walked = [self._root] if self._root.match(glob_pattern) else []
        else:
            walked = [
                path
                for path in sorted(self._root.rglob(glob_pattern))
                if path.is_file() and not self._is_excluded(path)
            ]
        self._file_cache[glob_pattern] = walked
        return walked

    def health_event(self) -> str | None:
        """``"unfiltered"`` / ``"filtered"`` / ``None`` — see module docstring."""
        if not self.ignore_file_present:
            return "unfiltered"
        if self.excluded_any:
            return "filtered"
        return None

    # -- internals -----------------------------------------------------------

    def _is_excluded(self, path: Path) -> bool:
        """True iff any ANCESTOR directory of ``path`` (relative to root) is a
        declared-excluded name. Records :attr:`excluded_any` the first time a
        walk actually drops a path (the "filtered" health signal's trigger)."""
        if not self._excluded_names:
            return False
        directory_parts = path.relative_to(self._root).parts[:-1]
        if any(part in self._excluded_names for part in directory_parts):
            self.excluded_any = True
            return True
        return False

    @staticmethod
    def _parse_ignore_file(root: Path) -> frozenset[str]:
        """The declared-excluded directory NAMES from ``root``'s ``.gitignore``.

        Simple name lines only (``target/``, ``_build``) — a line naming a
        nested path or carrying a glob (``/`` or ``*`` in the name) is skipped,
        never guessed at. A leading ``!`` un-excludes a name declared earlier
        in the same file (the trivial negation case this DISTILL's dangling
        decision left optional).
        """
        ignore_file = root / _IGNORE_FILE_NAME
        if not ignore_file.is_file():
            return frozenset()
        excluded: set[str] = set()
        negated: set[str] = set()
        for raw_line in ignore_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            negate = line.startswith("!")
            if negate:
                line = line[1:].strip()
            name = line.rstrip("/")
            if not name or "/" in name or "*" in name:
                continue
            (negated if negate else excluded).add(name)
        return frozenset(excluded - negated)
