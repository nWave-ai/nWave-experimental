"""Shared decision core for the P3.2 spec-coverage gate's feature attribution.

fix-coverage-claim-names-a-feature RCA: both entry-point loci
(``des.cli.verify_spec_coverage`` and
``des.application.subagent_stop_service.spec_coverage_gate_stdout``)
independently hand-rolled a ``covered |= ...`` set-union aggregation and a
bare 1-tuple ``req.req_id not in covered`` membership predicate -- neither
key carried feature identity, so ANY AT anywhere carrying the right marker
satisfied every feature's checklist row. The gate decided coverage on the
DESIGNATION (an ``R<n>`` token appears somewhere under ``--at-dir``), never
the PROPERTY (this feature's OWN ATs cover this feature's rows).

Both loci MUST delegate aggregation, membership, and attribution-scoping
decisions to this module. One shared core, one fix point -- a faithful
re-implementation of the old predicate elsewhere in either locus file is
exactly the drift this module exists to close.

Attribution is a DECLARED BINDING between two documents, never a directory
an operator happened to point at:

    D = files an operator scanned (``--at-dir`` / the AT-corpus dirs)
    A = files SSOT-attributed to the feature, via
        ``des.application.feature_at_files`` (``feature_tag_files`` +
        ``feature_tagged_test_files``) -- never a private re-scan
    S = D ∩ A                     -- coverage is computed ONLY over S

``--at-dir`` is a FILTER that can only REDUCE the scanned corpus; it is
never itself a source of attribution.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TypeVar


if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from pathlib import Path


#: A checklist declares its identity with a LINE-ANCHORED ``@feature-{id}``
#: tag on its own line (whitespace around it tolerated by ``str.strip()``).
#: Line-anchored, never a substring -- a checklist row whose PROSE merely
#: *mentions* the tag convention (e.g. describing it) must not self-declare.
_DECLARATION_LINE_RE = re.compile(r"^@feature-(\S+)$")

#: Bounded head-of-file window the declaration scan reads, mirroring
#: ``feature_at_files._HEAD_SCAN_LINES`` for the same "bounded, never a
#: whole-file grep" discipline.
_CHECKLIST_HEAD_SCAN_LINES = 20


def _checklist_head_window(checklist_path: Path) -> list[str]:
    try:
        with checklist_path.open(encoding="utf-8", errors="replace") as handle:
            return list(itertools.islice(handle, _CHECKLIST_HEAD_SCAN_LINES))
    except OSError:
        return []


def declared_checklist_feature_id(checklist_path: Path) -> str | None:
    """The line-anchored ``@feature-{id}`` declaration in the checklist's
    bounded head window, or ``None`` if absent.

    Line-anchored (the WHOLE stripped line must match), never a substring --
    ``docs/feature/carpaccio-pytest-at-comment-tag-binding/distill/
    requirement-checklist.md`` already contains the substring ``@feature-``
    inside a requirement's PROSE; a bare substring match would wrongly
    self-declare from it.
    """
    for raw in _checklist_head_window(checklist_path):
        match = _DECLARATION_LINE_RE.match(raw.strip())
        if match:
            return match.group(1)
    return None


def checklist_mentions_undeclared_decoy(checklist_path: Path, feature_id: str) -> bool:
    """True iff the checklist's head window contains the literal substring
    ``@feature-{feature_id}`` WITHOUT it being a valid line-anchored
    declaration for that exact id.

    A decoy occurrence (the tag mentioned inside a requirement's prose, in
    backticks, etc.) is WORSE than no mention at all: a naive substring-
    matching implementation -- or a human skimming the file -- could mistake
    it for a genuine self-declaration. Distinguishing it from "no mention
    anywhere" lets a consumer flag the ambiguous case explicitly rather than
    silently treating it the same as an honestly-undeclared checklist.
    """
    if declared_checklist_feature_id(checklist_path) == feature_id:
        return False
    wanted = f"@feature-{feature_id}"
    return any(wanted in line for line in _checklist_head_window(checklist_path))


def resolve_feature_identity(declared: str | None, explicit: str | None) -> str | None:
    """An explicitly-passed feature id (an operator's declared fact, e.g.
    CLI ``--feature-id``) overrides the checklist's own declaration."""
    return explicit if explicit is not None else declared


# ---------------------------------------------------------------------------
# Attribution arity -- the three-set algebra's outcome states (GDP-8 arity
# corollary: every state reaches the caller, none silently collapsed).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NoDeclaredIdentity:
    """Neither the checklist nor an explicit override names a feature."""


@dataclass(frozen=True)
class EmptyAttribution:
    """A feature identity is known, but A = ∅ -- zero files anywhere
    declare ``@feature-{feature_id}``."""

    feature_id: str


@dataclass(frozen=True)
class WrongScope:
    """A ≠ ∅ but S = D ∩ A = ∅ -- the operator pointed the scanned corpus at
    the wrong directory. ``attributed_files`` names the ACTUAL files (so the
    caller can name the actual directories) holding A."""

    feature_id: str
    attributed_files: tuple[Path, ...]


@dataclass(frozen=True)
class Scoped:
    """S ≠ ∅ -- coverage is computed over ``scoped_files``.
    ``ignored_count`` is ``|D \\ A|``: how many scanned files were NOT this
    feature's own and were therefore excluded (S ⊊ D visibility)."""

    feature_id: str
    scoped_files: tuple[Path, ...]
    ignored_count: int


#: The 4-arity result of ``resolve_attribution`` (GDP-8).
AttributionOutcome = NoDeclaredIdentity | EmptyAttribution | WrongScope | Scoped


def resolve_attribution(
    feature_id: str | None,
    scanned_files: Iterable[Path],
    attributed_files: Iterable[Path],
) -> AttributionOutcome:
    """Decide the arity state from D (scanned) and A (attributed) via the
    three-set algebra S = D ∩ A. Never collapses "found something, cannot
    compute" into a silent pass."""
    if feature_id is None:
        return NoDeclaredIdentity()
    attributed = tuple(sorted(set(attributed_files)))
    if not attributed:
        return EmptyAttribution(feature_id=feature_id)
    scanned = tuple(sorted(set(scanned_files)))
    scoped = tuple(sorted(set(scanned) & set(attributed)))
    if not scoped:
        return WrongScope(feature_id=feature_id, attributed_files=attributed)
    ignored_count = len(set(scanned) - set(attributed))
    return Scoped(
        feature_id=feature_id, scoped_files=scoped, ignored_count=ignored_count
    )


# ---------------------------------------------------------------------------
# Coverage aggregation + membership -- the ONE home for both. Neither locus
# may carry its own copy (AXIS 2 architecture pin).
# ---------------------------------------------------------------------------


class _HasReqId(Protocol):
    @property
    def req_id(self) -> str: ...


_T = TypeVar("_T", bound=_HasReqId)


def aggregate_covered_ids(
    files: Iterable[Path],
    id_extractor: Callable[[Path], set[str] | int],
) -> set[str] | int:
    """The ONE aggregation point: union every file's covered-id set, or
    propagate the first indeterminate exit code an extractor returns."""
    covered: set[str] = set()
    for path in files:
        ids_or_exit = id_extractor(path)
        if isinstance(ids_or_exit, int):
            return ids_or_exit
        covered |= ids_or_exit
    return covered


def uncovered_requirements(requirements: Iterable[_T], covered: set[str]) -> list[_T]:
    """The ONE membership predicate: a requirement is uncovered iff its
    ``req_id`` is absent from ``covered``. Feature-scoped by construction --
    ``covered`` is aggregated only from S (the feature-attributed,
    scanned-corpus intersection), never a global unqualified namespace."""
    return [req for req in requirements if req.req_id not in covered]
