"""Mechanically derive DeliveryContract skeleton facts from one architecture
brief's own citations -- the parsing half of ``des compile-contract``
(ADR-SSOT-002 Section 4, ``targets`` row: "DESIGN's prefactoring/reuse
decision, candidate overlap, imports...").

Pure text parsing plus base-tree grounding through the EXISTING
``declared_import_resolver`` (never a second resolution algorithm): every
extracted fact is either a literal substring of the brief (a citation, an
obligation token) or independently verified against the base tree before
being trusted (a declared-import candidate). Nothing here invents a fact the
brief does not already state or the base tree does not already ground --
mirrors the "never invent" discipline ``declared_import_resolver``'s own
module docstring states for K4 failure-to-design matrix row 12.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from des.domain.declared_import_resolver import (
    is_name_bound_in_target_file,
    resolve_declared_import,
)


if TYPE_CHECKING:
    from pathlib import Path


#: A repository-relative file path followed by ``:<line>`` -- the exact
#: shape DESIGN's own architecture authority cites for an insertion point.
#: `des dispatch`'s own EXTEND-citation validator (deleted, Ale's
#: construction-over-file correction 2026-08-20, "the contract has one
#: writer -- `des fill-contract` is the constructor": Agda-proved vacuous
#: once this exact regex is what GENERATES `overlap`, never just checks it
#: -- ~/nwave-formal/2026-08-19-gates) required this same shape in return;
#: this module is now the sole owner of it.
FILE_LINE_CITATION_RE = re.compile(r"[\w/.-]+\.\w+:\d+")

#: One backtick-quoted bare or dotted identifier -- the shape a brief cites
#: an existing symbol in (`` `Check.get_grace_start` ``, `` `CronSim` ``,
#: `` `hc.api.views.guess_kind` ``). A prose word that happens to sit in
#: backticks and never binds anywhere real is filtered out downstream by
#: ``is_name_bound_in_target_file``, never here -- extraction never decides
#: truth, only shape.
_BACKTICK_SYMBOL_RE = re.compile(
    r"`([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)`"
)

#: ``thin-delivery-contract.schema.json`` ``$defs/obligations`` closed
#: vocabulary. Duplicated here as a literal frozenset (not imported from the
#: schema JSON, which is data, not Python) because this module only needs a
#: name FILTER -- authority to invent a new obligation kind is not granted
#: here or anywhere else in this compiler.
SCHEMA_OBLIGATION_TOKENS = frozenset(
    {
        "CONTESTED_LAW",
        "REPRESENTATION_CHANGE",
        "INVALID_STATE",
        "PRESERVATION",
        "BROAD_INPUT_DOMAIN",
        "REUSE_CANDIDATE",
        "ARCHITECTURE_BOUNDARY_CHANGE",
    }
)

_OBLIGATION_TOKEN_RE = re.compile(r"\*\*([A-Z][A-Z_]*)\*\*")

_BACKTICK_SPAN_RE = re.compile(r"`([^`]*)`", re.DOTALL)


def _join_wrapped_backticks(text: str) -> str:
    """Markdown word-wraps a long inline-code span at the author's column
    width with no space marker (e.g. a long ``file:line`` citation split
    mid-path at a line break). Join such a span's internal line breaks back
    into one token before matching citations/symbols against it, so a
    wrapped ``path/to/file.py:12`` is treated as the single citation the
    author wrote, never as two fragments split at the wrap point (the
    shorter fragment after the break would otherwise be mistaken for its
    own, wrong, file citation)."""

    def _join(match: re.Match[str]) -> str:
        return "`" + re.sub(r"\s*\n\s*", "", match.group(1)) + "`"

    return _BACKTICK_SPAN_RE.sub(_join, text)


def extract_target_citations(brief_text: str) -> dict[str, list[str]]:
    """Every repository-relative file cited in a ``file:line`` shape, mapped
    to the DEDUPED, ORDER-PRESERVING citation substrings the brief actually
    wrote for it (e.g. ``"hc/api/models.py:1149"``) -- the exact evidence
    ``des dispatch``'s EXTEND-citation validator (a
    ``FILE_LINE_CITATION_RE`` search over ``overlap``/``justification``)
    requires to find verbatim."""
    brief_text = _join_wrapped_backticks(brief_text)
    by_file: dict[str, list[str]] = {}
    for match in FILE_LINE_CITATION_RE.finditer(brief_text):
        citation = match.group(0)
        file_path = citation.rsplit(":", 1)[0]
        seen = by_file.setdefault(file_path, [])
        if citation not in seen:
            seen.append(citation)
    return by_file


def extract_obligations(brief_text: str) -> list[str]:
    """Every schema-closed obligation token the brief itself bold-labels
    (``**REUSE_CANDIDATE**``, ...), in first-appearance order, deduplicated.
    A brief that never labels an obligation this way yields an empty list --
    ATD authors ``obligations`` from scratch rather than this compiler ever
    guessing one."""
    found: list[str] = []
    for match in _OBLIGATION_TOKEN_RE.finditer(brief_text):
        token = match.group(1)
        if token in SCHEMA_OBLIGATION_TOKENS and token not in found:
            found.append(token)
    return found


def extract_declared_import_candidates(brief_text: str) -> list[str]:
    """Every backtick-quoted bare/dotted identifier-shaped token in the
    brief, deduplicated in first-appearance order. Shape only -- grounding
    against a specific target's own file happens in
    ``declared_imports_for_target``."""
    brief_text = _join_wrapped_backticks(brief_text)
    found: list[str] = []
    for match in _BACKTICK_SYMBOL_RE.finditer(brief_text):
        token = match.group(1)
        if token not in found:
            found.append(token)
    return found


def declared_imports_for_target(
    repo_root: Path, target_candidate: str, brief_text: str
) -> list[str]:
    """Every backtick-quoted candidate from ``brief_text`` this compiler can
    prove resolves in the base tree for ``target_candidate`` -- the
    IDENTICAL two-part admission `des dispatch`'s own declared-import
    validator used to apply in CHECK mode (deleted, Ale's construction-
    over-file correction 2026-08-20, "the contract has one writer --
    `des fill-contract` is the constructor": Agda-proved vacuous once
    THIS function is what generates `declared-imports`, never just checks
    it -- ~/nwave-formal/2026-08-19-gates), run here in GENERATE mode:
    either the literal token is a bare name ``target_candidate``'s own file
    binds at module level (``is_name_bound_in_target_file``, K4 Run 6
    admission -- single-segment names only, e.g. ``CronSim``), or the token
    is a genuinely resolvable dotted base-tree module/symbol path
    (``resolve_declared_import``, e.g. ``hc.api.views.guess_kind``). A
    dotted ``ClassName.method`` chain citing an attribute of a bound class
    (e.g. ``Check.get_grace_start``) satisfies NEITHER check -- the
    validator itself cannot verify that shape today, so emitting it here
    would fail "passes by construction"; it is correctly dropped, never
    invented into a guess."""
    verified: list[str] = []
    for token in extract_declared_import_candidates(brief_text):
        if is_name_bound_in_target_file(
            repo_root, target_candidate, token
        ) or resolve_declared_import(repo_root, token):
            verified.append(token)
    return verified
