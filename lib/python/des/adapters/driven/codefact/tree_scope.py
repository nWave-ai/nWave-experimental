"""``TreeScope`` — the shared ignore-derived, cached tree-walk floor.

Both `CodeFactPort` floor tiers (:class:`AstAdapter`, :class:`TextSearchAdapter`)
walk the SAME target tree for every capability query. This module is the ONE
shared component both delegate to (Reuse Analysis, `fix-blast-radius-reparses-
tree-per-symbol`), so the properties below are fixed ONCE, never duplicated
(and possibly drifting) per tier:

1. **Ignore-derived exclusion** — a directory NAME, a wildcard-free NESTED
   PATH, or a single-level-wildcard entry (``name/*``, real ``.gitignore``
   shape this repo's own ``.nwave/*`` uses) declared in the target's own
   root ``.gitignore`` is excluded from every walk, with per-child
   ``!name/child/`` negation honored as an override — see
   :meth:`_parse_ignore_file`'s own docstring for the exact supported
   dialect and its deliberate limits. Parsed in pure Python (``pathlib`` +
   no external dependency, GDP-7) — NEVER a hardcoded per-repo-shape name
   list, and NEVER a ``git check-ignore`` shell-out. An absent ignore file
   preserves today's unfiltered walk (GDP-6: never a silently narrower
   default).
2. **Binary-content exclusion** — a file whose own bytes are not text (the
   NUL-byte heuristic, the same one ``git``/most diffing tools use) is
   excluded BY CONSTRUCTION (GDP-0), unconditionally — never dependent on an
   ignore file being present. A non-textual file cannot contain a textual
   call site; scanning one anyway (defect measured 2026-08-24,
   `query.never-wired` counting a JPEG and a WOFF2 as evidence) is not a
   downstream filtering concern, it is a walk-scope one.
3. **VCS-metadata exclusion** — the ``.git`` directory itself is ALWAYS
   excluded, unconditionally, never dependent on ``.gitignore`` declaring it
   (nobody declares it — a repo does not name its own VCS root in its own
   ignore file). This is deliberately NOT the hardcoded-vendor-list disease
   `test_tree_scope_fix_slice01.py`'s own module docstring names and guards
   against (``.venv``/``node_modules``/``.git`` as one undifferentiated
   per-project guess list): every OTHER name in that forbidden list is a
   per-language/per-tool CONVENTION that varies project to project (Rust's
   ``target/``, OCaml's ``_build/``, ...) and could in principle hold real
   source in a pathological repo shape; ``.git`` is git's OWN reserved
   internal directory name, structurally defined BY GIT ITSELF, identical
   and non-negotiable in every git repository that exists — never a guess,
   never project-specific. Measured 2026-08-24: a real installed git hook
   (``.git/hooks/commit_msg.py``, gitlint's own commit-msg hook) is real,
   on-disk, valid Python a naive ``*.py`` walk finds. Structural providers
   omit ``.git`` internals too, so this exclusion keeps their scopes aligned.
4. **Single-pass-per-glob caching** — a ``root``/glob-pattern pair is walked at
   most ONCE per :class:`TreeScope` instance; a second call with the same
   pattern reuses the prior result. This is the no-reparse-per-symbol contract:
   an adapter constructed once and queried for N distinct symbols costs one walk,
   not N.

The health signal (GDP-6, degrade-LOUD) is read via :meth:`health_event`:

* ``"filtered"`` — the walk actually dropped at least one path this instance's
  lifetime (ignore-derived OR binary-content) — a caller (e.g. an empty
  answer) must not treat that answer as an unqualified, confident zero. Takes
  priority over ``"unfiltered"``: binary-content exclusion can fire even with
  no ignore file present, so "no ignore file" alone no longer implies nothing
  was ever dropped.
* ``"unfiltered"`` — no ignore file was present AND nothing was ever dropped
  by binary-content exclusion either; the walk could not have excluded
  anything ignore-derived, distinct from "an ignore file ran and excluded
  nothing".
* ``None`` — an ignore file was present but nothing under it (nor any binary
  content) was ever excluded (no signal needed; the caller's answer is a
  genuine, unfiltered-equivalent result).

Ignore-file dialect: only ``.gitignore`` at the root, one entry per line
(trailing ``/`` optional), ``#`` comments, blank lines skipped, and a leading
``!`` negates a prior exclusion. An entry is either a bare NAME (``target``,
matched against any ancestor directory component, anywhere in the tree) or a
wildcard-free NESTED PATH (``.claude/worktrees``, containing ``/`` but no
``*``, matched ANCHORED at the tree root only — the same anchoring a root
``.gitignore`` gives a slashed pattern) — the minimum bar this feature's
DISTILL dispatch pinned, extended 2026-08-24 to the nested-path shape a real
declared entry (``.claude/worktrees/``) needed. A GLOBBED line (containing
``*``) is still skipped rather than guessed at, never silently mismatched.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


_IGNORE_FILE_NAME = ".gitignore"

#: The NUL-byte heuristic reads only this many leading bytes — enough to
#: reliably discriminate text from binary content (the same bound ``git``'s
#: own binary-detection uses) without reading a large file in full just to
#: decide whether to exclude it.
_BINARY_SNIFF_BYTES = 8000

#: ALWAYS excluded, unconditionally, never derived from (or negatable by)
#: ``.gitignore`` — see the module docstring's point 3 for why ``.git`` is
#: not the hardcoded-vendor-list disease its sibling names in that anti-
#: pattern are.
_ALWAYS_EXCLUDED_NAMES = frozenset({".git"})


class TreeScope:
    """Ignore-derived + binary-content exclusion, single-pass-per-glob cache.

    Constructed once per adapter instance with the tree's ``root``. Cheap to
    construct — the ignore file (if any) is parsed once, up front; the tree
    itself is walked lazily, on the first :meth:`files` call for a given glob.
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self.ignore_file_present = (root / _IGNORE_FILE_NAME).is_file()
        (
            self._excluded_names,
            self._excluded_paths,
            self._included_paths,
        ) = self._parse_ignore_file(root)
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
            walked = (
                [self._root]
                if self._root.match(glob_pattern) and not self._is_excluded(self._root)
                else []
            )
        else:
            walked = [
                path
                for path in sorted(self._root.rglob(glob_pattern))
                if path.is_file() and not self._is_excluded(path)
            ]
        self._file_cache[glob_pattern] = walked
        return walked

    def health_event(self) -> str | None:
        """``"filtered"`` / ``"unfiltered"`` / ``None`` — see module docstring.

        ``excluded_any`` (fired by EITHER exclusion reason) takes priority:
        binary-content exclusion is unconditional, so an absent ignore file
        no longer guarantees nothing was ever dropped.
        """
        if self.excluded_any:
            return "filtered"
        if not self.ignore_file_present:
            return "unfiltered"
        return None

    # -- internals -----------------------------------------------------------

    def _is_excluded(self, path: Path) -> bool:
        """True iff ``path`` must be dropped from the walk — its own ancestor
        directory is ignore-declared-excluded (bare name or anchored nested
        path), OR its content is binary. Records :attr:`excluded_any` the
        first time EITHER reason actually drops a path (the "filtered" health
        signal's trigger) — one vocabulary, regardless of which reason fired.
        """
        if self._is_ignore_excluded(path) or self._is_binary(path):
            self.excluded_any = True
            return True
        return False

    def _is_ignore_excluded(self, path: Path) -> bool:
        """True iff any ANCESTOR directory of ``path`` (relative to root)
        matches a declared-excluded bare name (or the ALWAYS-excluded
        ``.git``, see :data:`_ALWAYS_EXCLUDED_NAMES`), or the ancestor
        sequence starts with a declared-excluded anchored nested path AND is
        NOT itself inside a more specific, explicitly re-included one
        (``!name/child/`` overriding a broader ``name/*``)."""
        directory_parts = path.relative_to(self._root).parts[:-1]
        if any(
            part in self._excluded_names or part in _ALWAYS_EXCLUDED_NAMES
            for part in directory_parts
        ):
            return True
        excluded_by_path = any(
            directory_parts[: len(anchored)] == anchored
            for anchored in self._excluded_paths
        )
        if not excluded_by_path:
            return False
        return not any(
            directory_parts[: len(included)] == included
            for included in self._included_paths
        )

    @staticmethod
    def _is_binary(path: Path) -> bool:
        """NUL-byte heuristic: a file whose leading bytes contain a NUL byte
        cannot be source text a call-site scan could ever validly match
        against. A read failure (permission, a path that vanished mid-walk)
        degrades to "not binary" here — the existing per-file read-fault path
        (`TextSearchAdapter._read`'s own `UnicodeDecodeError`/`OSError`
        handling) still catches it downstream; this check must never itself
        silently drop a file it merely failed to sniff.
        """
        try:
            with path.open("rb") as handle:
                chunk = handle.read(_BINARY_SNIFF_BYTES)
        except OSError:
            return False
        return b"\x00" in chunk

    @staticmethod
    def _parse_ignore_file(
        root: Path,
    ) -> tuple[frozenset[str], frozenset[tuple[str, ...]], frozenset[tuple[str, ...]]]:
        """The declared (excluded bare names, excluded anchored paths,
        included/override anchored paths) from ``root``'s ``.gitignore``.

        A line with no ``/`` and no ``*`` is a bare NAME (``target/``,
        ``_build``), matched against any ancestor directory component
        anywhere in the tree. A line with a ``/`` but no ``*``
        (``.claude/worktrees/``) is an ANCHORED NESTED PATH — a segment
        sequence matched only from the tree root, the same anchoring real
        ``.gitignore`` semantics give a slashed pattern at the file that
        declares it. A line shaped EXACTLY ``<segments>/*`` (a trailing
        single-level wildcard, no OTHER ``*`` anywhere else in the line) is
        ALSO an anchored-path exclusion of ``<segments>`` — for pure
        exclusion this behaves identically to the same line without the
        ``/*`` (recognized because a real declared entry, ``.nwave/*``,
        needed it); its own real purpose in git's dialect is enabling
        per-child negation, which this parser supports too (below). Any
        OTHER line carrying ``*`` (a real recursive/character-class glob,
        e.g. ``**/pytest.log``) is skipped, never guessed at — this parser
        deliberately does not reimplement full ``.gitignore`` precedence.

        A leading ``!`` negates a prior declaration. For a bare NAME this is
        simple set subtraction (un-excludes that exact name). For an
        anchored path this is an OVERRIDE, checked as a prefix match at scan
        time, not mere set subtraction — ``!name/child/`` re-includes
        ``name/child`` and everything under it even though the broader
        ``name/*`` (or ``name/``) still excludes every OTHER child of
        ``name`` — the exact, common gitignore idiom this repo's own
        ``.nwave/*`` + per-subdirectory ``!.nwave/telemetry/`` (etc.) shape
        uses. This is a deliberate SIMPLIFICATION of real gitignore negation
        precedence (which is fully line-order-dependent); it is correct for
        this common "broad glob, then re-include specific children" idiom
        and is not claimed to be a general re-implementation.
        """
        ignore_file = root / _IGNORE_FILE_NAME
        if not ignore_file.is_file():
            return frozenset(), frozenset(), frozenset()
        excluded_names: set[str] = set()
        negated_names: set[str] = set()
        excluded_paths: set[tuple[str, ...]] = set()
        included_paths: set[tuple[str, ...]] = set()
        for raw_line in ignore_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            negate = line.startswith("!")
            if negate:
                line = line[1:].strip()
            entry = line.rstrip("/")
            if not entry:
                continue
            single_level_wildcard = entry.endswith("/*") and entry.count("*") == 1
            if single_level_wildcard:
                entry = entry[: -len("/*")]
            elif "*" in entry:
                continue
            if "/" in entry:
                segments = tuple(part for part in entry.split("/") if part)
                if not segments:
                    continue
                (included_paths if negate else excluded_paths).add(segments)
            elif single_level_wildcard:
                # A top-level `name/*` (no nested segments) — same shape,
                # single-segment anchored path.
                (included_paths if negate else excluded_paths).add((entry,))
            else:
                (negated_names if negate else excluded_names).add(entry)
        return (
            frozenset(excluded_names - negated_names),
            frozenset(excluded_paths),
            frozenset(included_paths),
        )
