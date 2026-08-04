"""SSOT for resolving a feature's ``.feature`` AT files on disk.

The ``@feature-{id}`` resolver: given a repo and a feature id, return every
``.feature`` file authored for that feature, wherever DISTILL placed it.

This is application-layer logic -- it orchestrates a filesystem walk (``rglob``)
and reads file contents -- so it lives above the domain but below the CLI. Its
8 real consumers: ``subagent_stop_service``, ``slice_at_completeness``,
``carpaccio_format``, ``verify_spec_coverage``, ``carpaccio_slice_gate``,
``verify_deliver_entry_contract``, ``carpaccio_precheck``, and
``run_contract_gate`` all import it from here. It previously lived in
``des.cli.carpaccio_format`` and was imported DOWNWARD by the application
layer, inverting the hexagonal layering (AD-05 / the AD-22 application->CLI
cycle). The CLI may depend on the application layer; the reverse is illegal.

Pure-read, stdlib-only (no ``import yaml``) per the DES-bundle contract: it
reads the filesystem and mutates nothing.
"""

from __future__ import annotations

import fnmatch
import itertools
import os
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from des.domain.requirement_id import COVERS_TAG_RE
from des.domain.slice_id_trailer import SLICE_TAG_RE
from des.ports.test_runner_port import AT_KIND_SUFFIX_MAP


#: A pytest-collectible filename convention (``test_*.py`` / ``*_test.py``).
#: SSOT promotion (agnostic-at-discovery-ssot-repair): previously a private
#: copy lived ONLY in ``slice_at_completeness.py``; a second agnostic-AT-
#: discovery consumer (``verify_deliver_entry_contract._authored_slice_tags``)
#: needs the SAME filter -- without it, a doc/ADR/module that merely
#: *mentions* the ``@feature-{id}`` tag convention in its head window would be
#: wrongly counted as a delivered AT (the exact class of defect
#: F-FEATURE-END-COMPLETENESS-ORACLE-PYTEST-BLIND AT-D1 already fixed once in
#: this repo). One physical home, imported by both, closes the divergence
#: risk before a 3rd private copy could form.
PYTEST_COLLECTIBLE_PATTERNS = ("test_*.py", "*_test.py")


if TYPE_CHECKING:
    from collections.abc import Iterator


# Directories pruned during the repo-wide ``.feature`` walk (workspace-layout
# generalization, fix-feature-tag-files-workspace-layout): version control,
# virtualenvs, dependency/vendor trees, and build/cache artifacts never carry
# authored acceptance scenarios and can be arbitrarily large or vendored.
EXCLUDED_SEARCH_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "build",
        "dist",
    }
)


def _legacy_acceptance_dir(repo: Path, feature_id: str) -> Path:
    """The pre-F-04 hardcoded AT directory for ``feature_id``.

    A ``.feature`` file under ``tests/scripts/cli/{feature_id}/acceptance``
    is feature-scoped by its directory name, so it is bound to ``feature_id``
    even when it carries no file-level ``@feature-`` tag.
    """
    return repo / "tests" / "scripts" / "cli" / feature_id / "acceptance"


def feature_tag_files(repo: Path, feature_id: str) -> list[Path]:
    """Resolve every ``.feature`` file authored for ``feature_id``.

    F-04 (atdd-pure-dogfooding-friction-2026-05-20.md): the gate must find a
    feature's ``.feature`` files wherever DISTILL placed them, not only under
    a hardcoded ``tests/scripts/cli/{feature_id}/acceptance`` path. A file is
    bound to the feature when it self-identifies with a file-level
    ``@feature-{feature_id}`` tag preceding its ``Feature:`` header, OR it
    lives under the legacy feature-scoped acceptance directory. The legacy
    path stays a source -- it is no longer the ONLY source.

    Workspace-layout generalization (fix-feature-tag-files-workspace-layout):
    the search root is the repo root itself, not a hardcoded ``{repo}/tests``
    -- a ``.feature`` file under any workspace subdir (``server/tests/...``,
    ``packages/api/tests/...``) is found. ``EXCLUDED_SEARCH_DIRS`` is pruned
    DURING the walk (never post-filtered) so the search stays bounded even
    over a large or vendored tree; the ``@feature-{feature_id}`` tag filter
    keeps the result TAG-scoped, never "every .feature in the repo".
    """
    if not repo.is_dir():
        return []
    wanted = f"@feature-{feature_id}"
    legacy_dir = _legacy_acceptance_dir(repo, feature_id)
    matched: set[Path] = set()
    for path in _walk_feature_files(repo):
        if wanted in _file_feature_tags(path) or legacy_dir in path.parents:
            matched.add(path)
    return sorted(matched)


def _walk_feature_files(repo: Path) -> Iterator[Path]:
    """Yield every ``*.feature`` file under ``repo``, pruning excluded dirs.

    Pruning happens on ``dirnames`` in place (the ``os.walk`` contract) so an
    excluded subtree (``node_modules``, ``.git``, ...) is never descended
    into, keeping the walk bounded regardless of tree size.
    """
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_SEARCH_DIRS]
        for filename in filenames:
            if filename.endswith(".feature"):
                yield Path(dirpath) / filename


# ---------------------------------------------------------------------------
# carpaccio-pytest-at-comment-tag-binding slice-01
# ---------------------------------------------------------------------------
#
# ADD-not-mutate (RATIFIED design constraint): ``feature_tag_files`` above and
# its 2 production consumers (``slice_at_completeness.feature_files_for_slice``,
# ``verify_deliver_entry_contract._authored_slice_tags``) stay UNTOUCHED. This
# is a NEW, separate resolver generalizing the SAME ``@feature-{id}`` head-tag
# idiom from ``.feature`` files to ANY test file (pytest today; slice-03 proves
# the same scan already works for ``//``/``--``-commented files with no
# per-syntax special-casing -- the scan is a comment-syntax-agnostic SUBSTRING
# search over the first N lines, never a whole-file grep, never a per-comment-
# marker branch).

_HEAD_SCAN_LINES = 20  # bounded head-of-file window (slice-03 negative control)


def feature_tagged_test_files(repo: Path, feature_id: str) -> list[Path]:
    """Resolve every test file head-tagged ``@feature-{feature_id}``.

    Slice-01 (carpaccio-pytest-at-comment-tag-binding): a pytest test file whose
    first ``_HEAD_SCAN_LINES`` lines carry a ``# @feature-{feature_id}`` comment-
    tag is bound to that feature -- the pytest-native mirror of
    ``feature_tag_files``'s ``.feature``-file binding, so an infra/CLI feature
    whose DISTILL wave correctly authored pytest (non-Gherkin) ATs is no longer
    structurally invisible to the carpaccio entry gate.

    Bounded head-of-file substring scan over every file below ``repo``, pruning
    ``EXCLUDED_SEARCH_DIRS`` the same way ``_walk_feature_files`` does. The
    match is a plain substring test against the file's first
    ``_HEAD_SCAN_LINES`` lines -- no comment-prefix branching -- so slice-03's
    ``//``/``--`` fixtures pass with NO further code change here.
    """
    if not repo.is_dir():
        return []
    wanted = f"@feature-{feature_id}"
    matched: set[Path] = set()
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_SEARCH_DIRS]
        for filename in filenames:
            path = Path(dirpath) / filename
            if wanted in _declared_tag_text(path):
                matched.add(path)
    return sorted(matched)


def is_pytest_collectible(path: Path) -> bool:
    """True iff ``path``'s filename matches the pytest collection convention.

    ``feature_tagged_test_files`` walks every file with no filename/extension
    restriction, matching purely on a head-comment tag substring. Without this
    filter a non-test file (a doc, an ADR, a plain module) whose head merely
    *mentions* the tag convention is wrongly counted as a delivered AT.
    Restricting to the pytest-collectible filename convention keeps a
    consumer bound to real, delivered test artifacts.
    """
    name = path.name
    return any(
        fnmatch.fnmatch(name, pattern) for pattern in PYTEST_COLLECTIBLE_PATTERNS
    )


def _file_head_window(path: Path) -> str:
    """The first ``_HEAD_SCAN_LINES`` lines of ``path``, or ``""`` if unreadable."""
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            return "".join(itertools.islice(handle, _HEAD_SCAN_LINES))
    except (OSError, UnicodeError):
        return ""


def _declared_tag_text(path: Path) -> str:
    """The DECLARED-tag-bearing text of ``path``'s bounded head window
    (ADR-001) -- never the raw window, never a raise, never a mutation.

    Same ``_HEAD_SCAN_LINES`` bound as ``_file_head_window``. Per-format
    dispatch, since the DECLARED-vs-CITED discriminant lives in a different
    grammar plane per format: ``.py`` keeps only ``COMMENT`` token text
    (discarding ``STRING`` token text -- docstrings/literals, the CITATION
    construct for this format); every other suffix keeps only tag-line-
    grammar lines (the entire stripped line -- OR its content after an
    optional single leading line-comment marker ``#``/``//``/``--``, the
    DA-3 cross-language comment-tag idiom already shipped for non-``.py``
    source files such as ``.rs``/``.go`` -- is one or more whitespace-
    separated ``@``-prefixed tokens; indentation-independent by
    construction), and for ``.md`` additionally excludes such lines found
    inside a fenced code block (```` ``` ````) -- Markdown's own quotation
    construct for illustrative examples.
    """
    window = _file_head_window(path)
    if not window:
        return ""
    if path.suffix == ".py":
        return _declared_comment_text(window)
    return _declared_tag_lines(window, track_fences=path.suffix == ".md")


def _declared_comment_text(window: str) -> str:
    """Tokenize ``window`` and keep only ``COMMENT`` token text, discarding
    ``STRING`` token text (docstrings/literals -- the CITATION construct for
    ``.py``). A truncation-induced tokenizer error (a multi-line string open
    past the bounded window) is caught; the comments collected before the
    error stand -- never a raise, never a fallback to the raw window."""
    lines = iter(window.splitlines(keepends=True))
    comments: list[str] = []
    try:
        for tok in tokenize.generate_tokens(lambda: next(lines, "")):
            if tok.type == tokenize.COMMENT:
                comments.append(tok.string)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return "\n".join(comments)


def _declared_tag_lines(window: str, *, track_fences: bool) -> str:
    """Keep only lines whose entire stripped content is one or more
    whitespace-separated ``@``-prefixed tokens (the tag-line grammar). When
    ``track_fences`` is set (``.md``), additionally exclude such lines found
    while a fenced code block (```` ``` ````) is open."""
    declared: list[str] = []
    inside_fence = False
    for raw in window.splitlines():
        stripped = raw.strip()
        if track_fences and stripped.startswith("```"):
            inside_fence = not inside_fence
            continue
        if track_fences and inside_fence:
            continue
        if _is_tag_line(stripped):
            declared.append(stripped)
    return "\n".join(declared)


#: Recognized single-line-comment markers whose remainder, if itself a pure
#: tag line, is a DECLARATION -- the DA-3 cross-language comment-tag idiom
#: (``tests/des/acceptance/agnostic_at_discovery/test_slice_02_discover_at_kind.py``
#: already ships ``.rs``/``.go`` fixtures tagged this way). A marker followed
#: by prose (multiple non-tag words) stays a CITATION -- discussing a tag in
#: a comment is never a declaration.
_LINE_COMMENT_MARKERS = ("#", "//", "--")


def _is_tag_line(stripped: str) -> bool:
    """True iff ``stripped`` is a DECLARED tag line: either its entire
    content is one or more whitespace-separated ``@``-prefixed tokens, or a
    single recognized line-comment marker is immediately followed by content
    that is ITSELF entirely such tokens."""
    if not stripped:
        return False
    if _is_pure_tag_line(stripped):
        return True
    for marker in _LINE_COMMENT_MARKERS:
        if stripped.startswith(marker):
            return _is_pure_tag_line(stripped[len(marker) :].strip())
    return False


def _is_pure_tag_line(candidate: str) -> bool:
    """True iff ``candidate`` is one or more whitespace-separated tokens
    that each start with ``@`` and carry at least one character after it."""
    if not candidate:
        return False
    tokens = candidate.split()
    return all(len(tok) > 1 and tok.startswith("@") for tok in tokens)


def _file_feature_tags(path: Path) -> tuple[str, ...]:
    """Collect the file-level ``@`` tags appearing before the ``Feature:`` line."""
    tags: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            # Gherkin comment line -- may precede the file-level tag block.
            continue
        if stripped.startswith("@"):
            tags.extend(stripped.split())
            continue
        if stripped.startswith("Feature:"):
            break
        # Any other non-blank content before Feature: -- stop scanning tags.
        break
    return tuple(tags)


# ---------------------------------------------------------------------------
# carpaccio-pytest-at-comment-tag-binding slice-02
# ---------------------------------------------------------------------------
#
# ADD-not-mutate: ``feature_tagged_test_files`` above (slice-01) and its
# behavior stay UNCHANGED. This is a companion, PER-FILE resolver -- given one
# already-bound file, name which slice and spec rows its head-comment
# additionally attributes it to, mirroring the ``@slice-NN`` scenario-tag
# resolution ``slice_at_completeness.feature_files_for_slice`` /
# ``carpaccio_format`` already give a Gherkin ``.feature`` file.

#: Imported from the domain SSOT (fix-slice-id-grammar-drift-ssot) so a
#: letter-suffixed `@slice-04a` head-comment sub-tag resolves identically to
#: `@slice-NN`.
_SLICE_SUBTAG_RE = SLICE_TAG_RE
_COVERS_SUBTAG_RE = COVERS_TAG_RE


@dataclass(frozen=True)
class TestFileAttribution:
    """The ``@slice-NN`` / exact ``@covers-R<n>`` or ``@covers-R-Sdd-dd``
    sub-tag attribution parsed from a
    test file's head-comment window.

    ``slice_id`` is ``None`` (never a raise) when the head window carries no
    ``@slice-NN`` tag -- "no attribution" is a valid, non-exceptional
    resolution outcome (slice-02 guardrail). ``slice_id`` resolves the FIRST
    ``@slice-NN`` tag only, kept for back-compat with call sites that only
    ever cared about a single-slice file.

    ``slice_ids`` (ADD-not-mutate, additive -- fix-multi-slice-shared-at-file)
    is the FULL ordered tuple of every ``@slice-NN`` tag in the head window,
    empty when none is present. A shared multi-slice AT file (one head-
    comment block declaring ``@slice-02`` through ``@slice-07``) must resolve
    to EVERY declared slice, not only the first -- callers that need
    membership across a shared file's declared slices read ``slice_ids``;
    ``slice_id`` alone under-reports for that shape.
    """

    slice_id: str | None
    slice_ids: tuple[str, ...]
    covers: tuple[str, ...]


def resolve_test_file_attribution(path: Path) -> TestFileAttribution:
    """Resolve the ``@slice-NN`` / exact requirement-ID sub-tags carried on ``path``'s
    head-comment window.

    Scans the SAME bounded ``_HEAD_SCAN_LINES`` window
    ``feature_tagged_test_files`` (slice-01) already scans -- no new window,
    no per-comment-syntax branching (plain regex match, same idiom slice-03
    will prove works for ``//``/``--`` comments with no code change).
    ``slice_id`` is ``None`` when no ``@slice-NN`` tag is present -- "no
    attribution" is a valid, non-exceptional outcome, never a raise.
    ``slice_ids`` resolves every ``@slice-NN`` tag via ``finditer`` -- the
    same plural idiom ``covers`` already used, closing the ``search``/
    ``finditer`` asymmetry that made a shared multi-slice file resolve to
    only its first-declared slice.
    """
    window = _declared_tag_text(path)
    slice_ids = tuple(match.group(1) for match in _SLICE_SUBTAG_RE.finditer(window))
    slice_id = slice_ids[0] if slice_ids else None
    covers = tuple(match.group(1) for match in _COVERS_SUBTAG_RE.finditer(window))
    return TestFileAttribution(slice_id=slice_id, slice_ids=slice_ids, covers=covers)


# ---------------------------------------------------------------------------
# agnostic-at-discovery slice-02
# ---------------------------------------------------------------------------
#
# ADD-not-mutate (RATIFIED, ADR-AAD-001): everything above stays UNTOUCHED.
# ``discover_at_kind_for_slice`` is composed entirely from the two sibling
# resolvers this module already ships -- ``feature_tagged_test_files`` for the
# ``@feature-{id}`` head-tag candidate scan, ``resolve_test_file_attribution``
# for the ``@slice-NN`` sub-tag filter -- plus the ``AT_KIND_SUFFIX_MAP`` SSOT
# slice-01 promoted into ``des.ports.test_runner_port`` (DA-5: no 3rd private
# copy of that map).

#: DA-4: derived from the resolved RUNNER name (``AT_KIND_SUFFIX_MAP`` values),
#: never a 3rd independent suffix->at_kind mapping. ``pytest`` alone carries
#: the CLI-vocabulary ``pytest-regression`` name; every other recognized
#: runner (``cargo-test`` today, future rows for free) maps to the generic
#: port-routed ``native-regression`` path.
_PYTEST_RUNNER_NAME = "pytest"


@dataclass(frozen=True)
class AtKindResolved:
    """Exactly one tag-matched candidate whose suffix is recognized."""

    at_kind: str
    regression_test_file: Path


@dataclass(frozen=True)
class AtKindNoneFound:
    """Zero tag-matched candidates -- the honest "nothing found" outcome."""

    searched_tag: str


@dataclass(frozen=True)
class AtKindAmbiguous:
    """2+ tag-matched candidates, OR one candidate with an unrecognized suffix.

    Both are "found something, cannot auto-resolve" -- NEVER collapsed into
    ``AtKindNoneFound`` (DA-2, GDP-8 arity corollary).
    """

    candidates: tuple[Path, ...]
    reason: str


#: The 3-arity result of ``discover_at_kind_for_slice`` (DA-2).
AtKindDiscovery = AtKindResolved | AtKindNoneFound | AtKindAmbiguous


def _runner_name_to_at_kind(runner_name: str) -> str:
    """DA-4: ``pytest`` -> ``pytest-regression``; every other recognized
    runner -> the generic ``native-regression`` path."""
    if runner_name == _PYTEST_RUNNER_NAME:
        return "pytest-regression"
    return "native-regression"


def discover_at_kind_for_slice(
    repo: Path, feature_id: str, slice_id: str
) -> AtKindDiscovery:
    """Auto-resolve ``slice_id``'s AT kind from ``@feature-{id}``/``@{slice_id}``
    tag-matched files on disk (ADR-AAD-001).

    Pure: reads the filesystem, mutates nothing, never raises -- a missing or
    unreadable ``repo`` degrades to ``AtKindNoneFound`` via the sibling
    resolvers this composes (Contract-Tests row 1). Honestly reports one of
    three outcomes -- resolved / none-found / ambiguous -- never collapsing
    "found something, cannot pick" into "found nothing" (DA-2).
    """
    searched_tag = f"@feature-{feature_id} @{slice_id}"
    candidates = sorted(
        path
        for path in feature_tagged_test_files(repo, feature_id)
        if slice_id in resolve_test_file_attribution(path).slice_ids
    )

    if not candidates:
        return AtKindNoneFound(searched_tag=searched_tag)

    if len(candidates) > 1:
        return AtKindAmbiguous(
            candidates=tuple(candidates),
            reason=f"{len(candidates)} tag-matched candidates for {searched_tag}",
        )

    (only_candidate,) = candidates
    runner_name = AT_KIND_SUFFIX_MAP.get(only_candidate.suffix)
    if runner_name is None:
        return AtKindAmbiguous(
            candidates=tuple(candidates),
            reason=(
                f"{only_candidate} has an unrecognized suffix "
                f"{only_candidate.suffix!r} -- not in AT_KIND_SUFFIX_MAP"
            ),
        )

    return AtKindResolved(
        at_kind=_runner_name_to_at_kind(runner_name),
        regression_test_file=only_candidate,
    )
