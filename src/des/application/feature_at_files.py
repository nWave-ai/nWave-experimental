"""SSOT for resolving a feature's ``.feature`` AT files on disk.

The ``@feature-{id}`` resolver: given a repo and a feature id, return every
``.feature`` file authored for that feature, wherever DISTILL placed it.

This is application-layer logic -- it orchestrates a filesystem walk (``rglob``)
and reads file contents -- so it lives above the domain but below the CLI.
``run_contract_gate``, ``carpaccio_slice_gate``, ``carpaccio_precheck`` (CLI
driving ports) and ``slice_at_completeness`` (application) all import it from
here. It previously lived in ``des.cli.carpaccio_format`` and was imported
DOWNWARD by the application layer, inverting the hexagonal layering (AD-05 /
the AD-22 application->CLI cycle). The CLI may depend on the application layer;
the reverse is illegal.

Pure-read, stdlib-only (no ``import yaml``) per the DES-bundle contract: it
reads the filesystem and mutates nothing.
"""

from __future__ import annotations

import itertools
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from des.domain.slice_id_trailer import SLICE_TAG_RE


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
            if wanted in _file_head_window(path):
                matched.add(path)
    return sorted(matched)


def _file_head_window(path: Path) -> str:
    """The first ``_HEAD_SCAN_LINES`` lines of ``path``, or ``""`` if unreadable."""
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            return "".join(itertools.islice(handle, _HEAD_SCAN_LINES))
    except (OSError, UnicodeError):
        return ""


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
_COVERS_SUBTAG_RE = re.compile(r"@covers-(R\d+)\b", re.IGNORECASE)


@dataclass(frozen=True)
class TestFileAttribution:
    """The ``@slice-NN`` / ``@covers-Rn`` sub-tag attribution parsed from a
    test file's head-comment window.

    ``slice_id`` is ``None`` (never a raise) when the head window carries no
    ``@slice-NN`` tag -- "no attribution" is a valid, non-exceptional
    resolution outcome (slice-02 guardrail).
    """

    slice_id: str | None
    covers: tuple[str, ...]


def resolve_test_file_attribution(path: Path) -> TestFileAttribution:
    """Resolve the ``@slice-NN`` / ``@covers-Rn`` sub-tags carried on ``path``'s
    head-comment window.

    Scans the SAME bounded ``_HEAD_SCAN_LINES`` window
    ``feature_tagged_test_files`` (slice-01) already scans -- no new window,
    no per-comment-syntax branching (plain regex match, same idiom slice-03
    will prove works for ``//``/``--`` comments with no code change).
    ``slice_id`` is ``None`` when no ``@slice-NN`` tag is present -- "no
    attribution" is a valid, non-exceptional outcome, never a raise.
    """
    window = _file_head_window(path)
    slice_match = _SLICE_SUBTAG_RE.search(window)
    slice_id = slice_match.group(1) if slice_match else None
    covers = tuple(
        match.group(1).upper() for match in _COVERS_SUBTAG_RE.finditer(window)
    )
    return TestFileAttribution(slice_id=slice_id, covers=covers)
