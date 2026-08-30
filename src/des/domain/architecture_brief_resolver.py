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
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from des.domain.declared_import_resolver import (
    is_name_bound_in_target_file,
    resolve_declared_import,
)
from des.domain.oracle_locator_resolver import is_test_shaped_path


if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterable


#: The ONE character class every repository-relative path citation in this
#: module shares -- four hand-copied spellings of it existed before
#: 2026-08-23 and drifted as a class. ``@`` is admitted because the
#: contract schema's own ``repositoryRelativePath`` now admits the Go
#: module-proxy ``@v`` DIRECTORY segment (schema 1.3, SF blocker
#: 2026-08-23). Extraction is deliberately a SUPERSET of what the schema
#: admits: it recognises the cited shape VERBATIM so an inadmissible path
#: is refused LOUD by the schema, never silently rewritten here. Probed on
#: the unfixed module: ``vendor/example.com/mod/@v/v1.2.0.info:1`` was
#: captured as ``v/v1.2.0.info:1`` (a different, plausible-looking path),
#: and a declared ``@v`` target locator vanished from the result entirely
#: -- both silent-wrong, the failure mode GDP-6 forbids. The schema, never
#: this regex, is the admissibility authority.
_PATH_CITATION_CHARS = r"[\w/.@-]"

#: A repository-relative file path followed by ``:<line>`` -- the exact
#: shape DESIGN's own architecture authority cites for an insertion point.
#: `des dispatch`'s own EXTEND-citation validator (deleted, Ale's
#: construction-over-file correction 2026-08-20, "the contract has one
#: writer -- `des fill-contract` is the constructor": Agda-proved vacuous
#: once this exact regex is what GENERATES `overlap`, never just checks it
#: -- ~/nwave-formal/2026-08-19-gates) required this same shape in return;
#: this module is now the sole owner of it.
FILE_LINE_CITATION_RE = re.compile(_PATH_CITATION_CHARS + r"+\.\w+:\d+")

#: A ``path::Selector`` oracle citation -- the shape a brief binds a
#: specific test by name in (Go's ``x_test.go::TestName``, pytest's
#: ``test_x.py::TestClass::test_name``). A ``file:line`` citation cannot
#: express a test selector; only an oracle binding uses ``::``. The
#: selector chain is preserved verbatim (the start of the OracleIdentity
#: shape recorded in techdebt), never split into fragments.
ORACLE_SELECTOR_CITATION_RE = re.compile(
    _PATH_CITATION_CHARS + r"+\.\w+(?:::[A-Za-z_]\w*)+"
)

#: Durable declaration of one whole-file test dependency. ``Test dependency
#: locator`` is the canonical product term; ``Acceptance support locator`` is
#: retained as a read-only compatibility spelling for already-sealed
#: authorities. The captured value is intentionally broader than the schema
#: path grammar so the compiler can refuse a selector/traversal/absolute
#: spelling by name rather than silently dropping it. Lines carrying either
#: label but not this shape are exposed separately as malformed producer input.
_ACCEPTANCE_SUPPORT_LOCATOR_RE = re.compile(
    r"^[ \t]*(?:Test dependency|Acceptance support) locator:[ \t]*"
    r"`(?P<locator>[^`\n]+)`(?:[ \t]+[^\n]*)?$",
    re.MULTILINE,
)
_ACCEPTANCE_SUPPORT_LABEL_RE = re.compile(
    r"^[ \t]*(?:Test dependency|Acceptance support) locator:[^\n]*$",
    re.MULTILINE,
)
_REPOSITORY_RELATIVE_WHOLE_FILE_RE = re.compile(
    r"^(?!.*(?:^|/)\.{1,2}(?:/|$))"
    r"(?:(?:[A-Za-z0-9._-]+|@v)/)*[A-Za-z0-9._-]+$"
)


def extract_acceptance_support_locators(brief_text: str) -> list[str]:
    """Return every declared test-dependency locator in durable order.

    The legacy acceptance-support label projects to the same representation.
    Unlike ordinary citations, duplicates remain visible: the compiler owns
    the construction rule and must reject duplicate or reordered declarations
    rather than normalising them into a different authority.
    """
    return [
        match.group("locator")
        for match in _ACCEPTANCE_SUPPORT_LOCATOR_RE.finditer(brief_text)
    ]


def malformed_acceptance_support_locator_lines(brief_text: str) -> list[str]:
    """Label-bearing lines which are not the exact backticked declaration."""
    valid_lines = {
        match.group(0) for match in _ACCEPTANCE_SUPPORT_LOCATOR_RE.finditer(brief_text)
    }
    return [
        match.group(0)
        for match in _ACCEPTANCE_SUPPORT_LABEL_RE.finditer(brief_text)
        if match.group(0) not in valid_lines
    ]


def is_repository_relative_whole_file_locator(locator: str) -> bool:
    """The schema's repositoryRelativePath grammar, excluding selectors."""
    return _REPOSITORY_RELATIVE_WHOLE_FILE_RE.fullmatch(locator) is not None


#: SF friction report 2026-08-20, item 2b: a brief may cite a documentary or
#: formal-proof file (``docs/design.md:1``, ``spec/Law.agda:42``) as
#: SUPPORTING EVIDENCE for a reuse/obligation claim -- that citation shape
#: is indistinguishable from a real code target under ``FILE_LINE_CITATION_
#: RE`` alone. DESIGN/DELIVER only ever change and verify CODE; a document
#: or formal artifact can never become a contract TARGET (no ``EXTEND``/
#: ``CREATE_NEW`` decision, no ``boundary`` obligations apply to prose).
#: A closed DENYLIST, not an allowlist: an allowlist of "code" extensions
#: would reject genuine languages this repository has never seen (GDP-10 --
#: the smaller, more defensible claim is "these specific shapes are never
#: code", not "only these shapes are code").
NON_CODE_TARGET_EXTENSIONS = frozenset(
    {
        ".md",
        ".rst",
        ".txt",
        ".adoc",
        ".tex",
        ".rtf",
        ".pdf",
        ".agda",
        ".agdai",
        ".lean",
        ".v",
        ".thy",
    }
)


def is_code_target_citation(path: str) -> bool:
    """``False`` for a documentary or formal-proof file citation -- shape
    only (extension check), mirrors the same filter-never-invent discipline
    ``declared_imports_for_target``'s own language boundary already
    applies."""
    return Path(path).suffix.lower() not in NON_CODE_TARGET_EXTENSIONS


#: One backtick-quoted bare or dotted identifier -- the shape a brief cites
#: an existing symbol in (`` `Check.get_grace_start` ``, `` `CronSim` ``,
#: `` `hc.api.views.guess_kind` ``). A prose word that happens to sit in
#: backticks and never binds anywhere real is filtered out downstream by
#: ``is_name_bound_in_target_file``, never here -- extraction never decides
#: truth, only shape.
_BACKTICK_SYMBOL_RE = re.compile(
    r"`([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)`"
)

#: One backtick-quoted ``nw-*`` skill name -- the shape a brief cites an
#: nWave skill in (e.g. `` `nw-pbt-python` ``). Row 13 (K4 run 18): a brief
#: citing a skill by NAME never translates into a carried fact today -- ATD
#: reads it as prose, same as any other word, and a citation this compiler
#: cannot ground stays exactly that: prose, never a workaround guess.
_SKILL_CITATION_RE = re.compile(r"`(nw-[a-z0-9]+(?:-[a-z0-9]+)*)`")

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

#: Run 17 (K4 matrix, $3.13/791s): `des compile-contract` refused a real
#: DESIGN brief because its obligation labels were `**N. TOKEN**` (the
#: numbering INSIDE the bold span) while this regex only ever recognized
#: `N. **TOKEN**` (numbering outside, matched trivially since anything
#: outside the `**...**` markers was never part of the match anyway).
#: The parse is on the SEMANTICS -- a numbered bold obligation label --
#: never the exact byte layout, so the optional `\d+\.\s*` prefix and an
#: optional trailing `:` (both tolerated inside the bold span) admit
#: both unambiguous shapes identically. Genuinely ambiguous or malformed
#: labels (no digits, mixed case, stray punctuation) still fail to
#: match, exactly as before.
_OBLIGATION_TOKEN_RE = re.compile(r"\*\*\s*(?:\d+\.\s*)?([A-Z][A-Z_]*)\s*:?\s*\*\*")

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
    """Every repository-relative CODE file cited in a ``file:line`` shape,
    mapped to the DEDUPED, ORDER-PRESERVING citation substrings the brief
    actually wrote for it (e.g. ``"hc/api/models.py:1149"``) -- the exact
    evidence ``des dispatch``'s EXTEND-citation validator (a
    ``FILE_LINE_CITATION_RE`` search over ``overlap``/``justification``)
    requires to find verbatim.

    A documentary or formal-proof citation (``is_code_target_citation``
    false) is dropped here, never carried into ``targets`` -- SF friction
    report 2026-08-20, item 2b: a brief citing ``docs/design.md:1`` as
    supporting evidence for a code target must never itself BECOME a
    contract target.

    A BARE-NAME citation (no ``/`` in the path -- ADR-CFG-001 reproduction,
    2026-08-20: prose re-citing ``artifact_versioning.py:131`` after the
    path-qualified ``src/des/domain/artifact_versioning.py:106``) never
    becomes its own target: it is the SAME file cited again, so it folds
    into the unique qualified citation sharing its basename, as extra
    verbatim evidence. No qualified sibling (or an ambiguous pair of them)
    means the bare name resolves to nothing this parser can ground --
    dropped, never promoted to a new file at repository root."""
    folded, _dropped = extract_target_citations_with_drops(brief_text)
    return folded


@dataclass(frozen=True, slots=True)
class DroppedCitation:
    """One citation this parser could not ground into any target, kept
    VISIBLE (GDP-6: degrade loud, never silent-wrong) instead of silently
    vanishing from the compiled skeleton -- reviewer counterexample
    2026-08-20: an orphan bare-name citation next to an unrelated
    qualified one disappeared without a trace while the rest compiled."""

    citation: str
    reason: str


def extract_target_citations_with_drops(
    brief_text: str,
) -> tuple[dict[str, list[str]], list[DroppedCitation]]:
    """``extract_target_citations`` plus the citations it had to DROP,
    each with the reason -- the caller surfaces them (skeleton
    ``dropped-citations`` field, or a Blocked WHAT when the whole target
    set collapses) so ATD/human review sees every discard."""
    brief_text = _join_wrapped_backticks(brief_text)
    by_file: dict[str, list[str]] = {}
    for match in FILE_LINE_CITATION_RE.finditer(brief_text):
        citation = match.group(0)
        file_path = citation.rsplit(":", 1)[0]
        if not is_code_target_citation(file_path):
            continue
        if is_test_shaped_path(file_path):
            # SF friction report 2026-08-20, sister reproduction: a
            # test/spec-shaped citation is an ORACLE-BINDING candidate
            # (``extract_oracle_citations``), never a contract target --
            # targets are production files only.
            continue
        seen = by_file.setdefault(file_path, [])
        if citation not in seen:
            seen.append(citation)
    return _fold_bare_name_citations(by_file)


def _fold_bare_name_citations(
    by_file: dict[str, list[str]],
) -> tuple[dict[str, list[str]], list[DroppedCitation]]:
    """Fold every bare-basename key of ``by_file`` into its unique
    qualified sibling (same basename, path containing ``/``), preserving
    first-appearance order and citation dedup; a bare key with zero or
    more than one qualified sibling is dropped (unresolvable is never a
    CREATE_NEW at repository root) -- and every drop is RETURNED with its
    reason, never swallowed."""
    qualified_by_basename: dict[str, list[str]] = {}
    for file_path in by_file:
        if "/" in file_path:
            qualified_by_basename.setdefault(Path(file_path).name, []).append(file_path)
    folded: dict[str, list[str]] = {}
    dropped: list[DroppedCitation] = []
    for file_path, citations in by_file.items():
        if "/" in file_path:
            owner = file_path
        else:
            owners = qualified_by_basename.get(file_path, [])
            if len(owners) != 1:
                reason = (
                    f"bare-name citation with no path-qualified sibling "
                    f"sharing basename {file_path!r} in the brief -- "
                    "unresolvable to any file, never promoted to a "
                    "repository-root CREATE_NEW"
                    if not owners
                    else f"bare-name citation ambiguous across "
                    f"{len(owners)} path-qualified siblings "
                    f"({', '.join(owners)}) -- never guessed"
                )
                dropped.extend(
                    DroppedCitation(citation=citation, reason=reason)
                    for citation in citations
                )
                continue
            owner = owners[0]
        merged = folded.setdefault(owner, [])
        for citation in citations:
            if citation not in merged:
                merged.append(citation)
    return folded, dropped


@dataclass(frozen=True, slots=True)
class DeclaredTargetLocator:
    """One TYPED target declaration from an authority's obligations block
    -- the ``Oracle target locator: `<path>::<symbol>` (<DECISION>, ...)``
    shape ``nw-solution-architect`` emits (ADR-CFG-001, 2026-08-20). The
    ``path`` IS a contract target with the declared ``decision``; the
    ``symbol`` is the oracle-side binding (the start of the OracleIdentity
    shape recorded in techdebt), never a test selector."""

    path: str
    symbol: str
    decision: str | None
    citation: str


#: The declared-locator line shape: optional prose between the label and
#: the backtick span (``same `` when an obligation repeats the first
#: declaration), then a ``path::symbol`` citation, then optionally a
#: parenthesized decision token that may wrap to the next line AFTER the
#: token itself.
_DECLARED_TARGET_LOCATOR_RE = re.compile(
    r"Oracle target locator:[^`\n]*"
    "`(?P<citation>" + _PATH_CITATION_CHARS + r"+\.\w+(?:::[A-Za-z_]\w*)+)`"
    r"(?:\s*\(\s*(?P<decision>CREATE_NEW|EXTEND)\b)?"
)


def extract_declared_target_locators(
    brief_text: str,
) -> list[DeclaredTargetLocator]:
    """Every typed target declaration the brief's obligations state, in
    first-appearance order, deduplicated by path (a later repeat may fill
    a missing decision, never overturn a declared one). ADR-CFG-001
    reproduction, 2026-08-20: the compiler IGNORED the brief's own
    ``Oracle target locator: `src/des/domain/config_merge.py::merge_config`
    (CREATE_NEW, ...)`` declaration and promoted two files the same brief
    textually excluded from scope. A declaration is DESIGN's explicit
    statement, so it always outranks prose inference downstream -- never
    the other way. Documentary/formal-proof paths never qualify; a
    test-shaped path is an oracle binding, never a target."""
    brief_text = _join_wrapped_backticks(brief_text)
    by_path: dict[str, DeclaredTargetLocator] = {}
    for match in _DECLARED_TARGET_LOCATOR_RE.finditer(brief_text):
        citation = match.group("citation")
        decision = match.group("decision")
        path, _, symbol = citation.partition("::")
        if not is_code_target_citation(path) or is_test_shaped_path(path):
            continue
        existing = by_path.get(path)
        if existing is None:
            by_path[path] = DeclaredTargetLocator(
                path=path, symbol=symbol, decision=decision, citation=citation
            )
        elif existing.decision is None and decision is not None:
            by_path[path] = DeclaredTargetLocator(
                path=path,
                symbol=existing.symbol,
                decision=decision,
                citation=existing.citation,
            )
    return list(by_path.values())


#: A markdown pipe-table separator cell (``---``, ``:---:``, ...).
_TABLE_SEPARATOR_CELL_RE = re.compile(r"^:?-+:?$")

#: The Decision-column closed vocabulary -- the same two tokens the
#: targetPlan schema admits; transcription never widens it.
_TARGET_TABLE_DECISIONS = frozenset({"EXTEND", "CREATE_NEW"})


@dataclass(frozen=True, slots=True)
class DeclaredTargetTableRow:
    """One row of an authority's explicit target-declaration table -- a
    markdown pipe table whose header names both a ``Target`` and a
    ``Decision`` column (ADR-CFG-001 Amendment shape, 2026-08-21). The row
    IS the declaration: ``path`` transcribed from the Target cell,
    ``decision`` from the Decision cell -- never inferred."""

    path: str
    decision: str


@dataclass(frozen=True, slots=True)
class TargetTableProblem:
    """A target-declaration table this parser refuses to half-read:
    ambiguity (two matching tables) or an untranscribable row surfaces
    LOUD downstream with this WHAT/WHY/HOW, never a silently-picked
    interpretation (GDP-6)."""

    what: str
    why: str
    how: str


@dataclass(frozen=True, slots=True)
class TargetTableProblems:
    """EVERY problem one pass over the target-declaration table found --
    reject-all-at-once (Ale, 2026-08-22).

    Row-level problems are INDEPENDENT of one another: a bad Decision cell
    in row 1 tells this parser nothing about row 3. Stopping at the first
    charged the architect one full consult->compile round-trip per defect
    (ADR-CFG-001, four rounds, 2026-08-21). ``rows`` carries the rows that
    DID transcribe, so the caller can keep checking what it can;
    ``enumerable`` is False when the table itself could not be read at all
    (two matching tables), and then ``rows`` is empty BY FACT -- every
    row-level check the caller would have run is unrun, and must be
    declared so, never silently passed (GDP-6)."""

    problems: tuple[TargetTableProblem, ...]
    rows: tuple[DeclaredTargetTableRow, ...] = ()
    enumerable: bool = True


def _table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _declaration_cell_text(cell: str) -> str:
    """A Target/Decision cell stripped of its markdown emphasis -- the
    backticks around the path, the ``**`` around the decision token."""
    return cell.replace("`", "").replace("*", "").strip()


def _is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(
        _TABLE_SEPARATOR_CELL_RE.fullmatch(cell) for cell in cells
    )


def _pipe_table_blocks(brief_text: str) -> list[list[list[str]]]:
    blocks: list[list[list[str]]] = []
    current: list[list[str]] = []
    for line in brief_text.splitlines():
        if line.lstrip().startswith("|"):
            current.append(_table_cells(line))
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def extract_declared_target_table(
    brief_text: str,
) -> list[DeclaredTargetTableRow] | TargetTableProblems | None:
    """The authority's explicit target-declaration table, transcribed:
    EXACTLY its rows, in declaration order (GDP-0 -- the architect
    DECLARES, this compiler TRANSCRIBES; inference never applies where a
    declaration exists). ``None`` when no such table is present, so
    citation inference stays the unchanged fallback. More than one
    matching table, a duplicate path, an empty Target cell, or a Decision
    cell outside ``EXTEND|CREATE_NEW`` is a problem -- ambiguity is
    refused loud, never resolved silently. ADR-CFG-001 reproduction,
    2026-08-21 (third same-producer incident): the amendment's
    ``| Target | Decision | Why |`` table declared five targets; citation
    inference compiled two, one of them a file the same authority declared
    REUSE-as-is, and missed four of the five rows.

    ONE pass reports EVERY row-level problem it found
    (``TargetTableProblems``, Ale 2026-08-22) -- row problems are mutually
    independent, so refusing at the first one charged the architect a
    round-trip per defect. Two matching tables is the one non-enumerable
    case: no row can be read at all, so ``enumerable`` is False."""
    matching: list[list[list[str]]] = []
    for block in _pipe_table_blocks(brief_text):
        header = [_declaration_cell_text(cell).lower() for cell in block[0]]
        if "target" in header and "decision" in header:
            matching.append(block)
    if not matching:
        return None
    if len(matching) > 1:
        return TargetTableProblems(
            enumerable=False,
            problems=(
                TargetTableProblem(
                    what=f"the authority carries {len(matching)} target-"
                    "declaration tables (markdown pipe tables whose header "
                    "names both a Target and a Decision column) -- only one "
                    "can be THE declared target set",
                    why="two declarations are an ambiguity; silently picking "
                    "one would compile a target set the architect may never "
                    "have declared (GDP-6: no silent-wrong)",
                    how="merge the declarations into ONE table in the "
                    "authority document, or rename the non-authoritative "
                    "table's Target/Decision header columns so exactly one "
                    "declaration remains",
                ),
            ),
        )

    block = matching[0]
    header = [_declaration_cell_text(cell).lower() for cell in block[0]]
    target_index = header.index("target")
    decision_index = header.index("decision")
    rows: list[DeclaredTargetTableRow] = []
    problems: list[TargetTableProblem] = []
    seen: set[str] = set()
    for cells in block[1:]:
        if _is_separator_row(cells):
            continue
        row_text = " | ".join(cells)
        if len(cells) <= max(target_index, decision_index):
            problems.append(
                TargetTableProblem(
                    what="a target-declaration table row carries fewer cells "
                    f"than its own header: {row_text!r}",
                    why="a row this parser cannot line up with the Target/"
                    "Decision columns cannot be transcribed -- guessing a "
                    "column would fabricate a declaration",
                    how="restore the row's missing '|'-delimited cells so "
                    "every header column is present",
                )
            )
            continue
        path = _declaration_cell_text(cells[target_index])
        decision = _declaration_cell_text(cells[decision_index])
        if not path:
            problems.append(
                TargetTableProblem(
                    what="a target-declaration table row has an empty Target "
                    f"cell: {row_text!r}",
                    why="a declared target with no path is not a declaration",
                    how="fill the Target cell with the repository-relative "
                    "path, or delete the row",
                )
            )
            continue
        row_problems: list[TargetTableProblem] = []
        if path in seen:
            row_problems.append(
                TargetTableProblem(
                    what=f"the target-declaration table declares {path!r} twice",
                    why="two rows for one path are two contradicting-or-"
                    "redundant declarations; the table must state each target "
                    "exactly once",
                    how=f"delete or merge the duplicate {path!r} row",
                )
            )
        seen.add(path)
        if decision not in _TARGET_TABLE_DECISIONS:
            row_problems.append(
                TargetTableProblem(
                    what=f"target-declaration table row for {path!r} declares "
                    f"decision {decision!r}, outside EXTEND|CREATE_NEW",
                    why="the Decision column is the targetPlan schema's closed "
                    "vocabulary; transcription never widens or reinterprets it",
                    how="declare EXTEND or CREATE_NEW for the row, or remove "
                    f"{path!r} from the table if it is not a target (a "
                    "REUSE-as-is file belongs in prose or a reuse survey, "
                    "never the target table)",
                )
            )
        if row_problems:
            problems.extend(row_problems)
            continue
        rows.append(DeclaredTargetTableRow(path=path, decision=decision))
    if problems:
        return TargetTableProblems(problems=tuple(problems), rows=tuple(rows))
    if not rows:
        return TargetTableProblems(
            problems=(
                TargetTableProblem(
                    what="the target-declaration table carries a header but zero data rows",
                    why="an empty declaration declares no target set; falling back "
                    "to citation inference would silently overrule the architect's "
                    "explicit (if incomplete) declaration",
                    how="fill the table with one '| <path> | EXTEND or "
                    "CREATE_NEW | <why> |' row per target",
                ),
            ),
        )
    return rows


#: The declared verification-command line shape -- the same declarative
#: family as ``Oracle target locator:`` above: a label, optional prose
#: between the label and the backtick span, then ONE backtick-delimited
#: native command per line (``Verification command: `go test ./...```).
#: SF friction 2026-08-20 (verification-scope ownership): the authority
#: that already declares the subject's exact native argv is where they
#: belong -- requiring a duplicate declaration in the subject's CLAUDE.md
#: was prose duplicated in the wrong place.
_DECLARED_VERIFICATION_COMMAND_RE = re.compile(
    r"Verification command:[^`\n]*`(?P<command>[^`\n]+)`"
)


def extract_declared_verification_commands(brief_text: str) -> list[list[str]]:
    """Every ``Verification command: `<argv...>``` declaration the cited
    authority states, one shell-split argv per declaration line, in
    first-appearance order, deduplicated by exact argv. The split is data
    extraction only (``shlex.split``, POSIX rules) -- the argv is contract
    DATA handed to the executor's own argv-array invocation, never a
    string this parser or anything downstream feeds to a shell. A span
    that ``shlex`` cannot split (unbalanced quote) or that splits to
    nothing is skipped, never half-guessed."""
    commands: list[list[str]] = []
    for match in _DECLARED_VERIFICATION_COMMAND_RE.finditer(brief_text):
        try:
            tokens = shlex.split(match.group("command"))
        except ValueError:
            continue
        if tokens and tokens not in commands:
            commands.append(tokens)
    return commands


#: The declared verification-authority DELEGATION line shape -- the same
#: declarative family as ``Oracle target locator:``/``Verification
#: command:`` above: a label, optional prose, then ONE backtick-delimited
#: ``<repo-relative-doc>#<heading-anchor>`` reference. SF friction
#: 2026-08-21 (verification-authority delegation): the sister's real Slice
#: brief declares NO per-line labels -- prose delegates the whole scope to
#: an ADR heading whose fenced block carries the LITERAL script, so
#: ``extract_declared_verification_commands`` over that brief returns
#: ``[]`` and the campaign would stay Blocked. The delegation is resolved
#: by ``des.domain.verification_authority_resolver`` (never here: this
#: module only extracts the brief's own declared reference).
_DECLARED_VERIFICATION_AUTHORITY_LOCATOR_RE = re.compile(
    r"Verification authority locator:[^`\n]*`(?P<locator>[^`\n]+)`"
)


def extract_declared_verification_authority_locators(
    brief_text: str,
) -> list[str]:
    """Every ``Verification authority locator: `<doc>#<anchor>```
    declaration the brief states, verbatim, in first-appearance order,
    deduplicated exactly. Shape only: existence/resolvability of the
    reference is ``resolve_verification_authority``'s own concern -- a
    declared-but-unresolvable delegation must surface as a typed refusal
    downstream, never be silently dropped here."""
    found: list[str] = []
    for match in _DECLARED_VERIFICATION_AUTHORITY_LOCATOR_RE.finditer(brief_text):
        locator = match.group("locator").strip()
        if locator and locator not in found:
            found.append(locator)
    return found


#: The declared-ORACLE-locator line shape: the SAME ``Oracle target
#: locator:`` label ``_DECLARED_TARGET_LOCATOR_RE`` already reads, but with
#: the ``::symbol`` suffix OPTIONAL. ADR-AUM-001 reproduction, 2026-08-22
#: (second same-class occurrence -- ADR-CFG-001's own declarations are the
#: same bare shape and only ever survived because their all-Python target
#: set reached the pytest-convention fallback): a RED_TO_GREEN oracle is
#: authored at a path that does NOT exist yet, so the authority can cite it
#: neither as ``file:line`` (no lines to cite) nor necessarily as
#: ``path::TestName`` (the test function may be unnamed at DESIGN time).
#: The bare declared path under this explicit label IS the judgment call
#: and is unambiguous: the label says oracle, and admissibility still turns
#: on the same shape rule every other citation source obeys.
_DECLARED_ORACLE_LOCATOR_RE = re.compile(
    r"Oracle target locator:[^`\n]*"
    "`(?P<citation>" + _PATH_CITATION_CHARS + r"+\.\w+(?:::[A-Za-z_]\w*)*)`"
)


def extract_declared_oracle_locator_candidates(brief_text: str) -> list[str]:
    """Every backtick-quoted path an ``Oracle target locator:`` line
    declares, verbatim, in first-appearance order, deduplicated exactly.
    SHAPE only -- whether a candidate is ADMISSIBLE as an oracle
    (test/spec-shaped, non-documentary) is ``extract_oracle_citations``'
    concern. Exported so a refusal can name the declaration it did NOT
    admit and WHY, rather than claim the brief declared nothing (GDP-3: a
    rejection that lies is worse than a bare traceback)."""
    brief_text = _join_wrapped_backticks(brief_text)
    found: list[str] = []
    for match in _DECLARED_ORACLE_LOCATOR_RE.finditer(brief_text):
        citation = match.group("citation")
        if citation not in found:
            found.append(citation)
    return found


def extract_oracle_citations(brief_text: str) -> list[str]:
    """Every citation naming the acceptance oracle, deduplicated per file
    in first-appearance order (SF friction report 2026-08-20, sister
    reproduction): a ``path::Selector`` citation is kept VERBATIM
    (selector preserved); a ``file:line`` citation whose own filename is
    test/spec-shaped (``is_test_shaped_path``) yields its plain path. When
    the same file is cited both ways, its first durable identity remains
    primary -- a later technical selector cannot rewrite public oracle
    ownership. A
    typed ``Oracle target locator: `<path>``` declaration is admitted with
    NO line and NO selector required (``_DECLARED_ORACLE_LOCATOR_RE``):
    RED_TO_GREEN's oracle does not exist yet, so demanding either shape
    made the one explicit declaration DESIGN can make unrepresentable.
    Documentary/formal-proof files (``is_code_target_citation`` false) and
    production files are never oracle candidates. Shape only: existence is
    the resolvers' own concern (required for GREEN_TO_GREEN's
    already-committed oracle, deliberately NOT for RED_TO_GREEN's
    to-be-authored one)."""
    brief_text = _join_wrapped_backticks(brief_text)
    matches = sorted(
        [
            (match.start(), True, match.group(0))
            for match in ORACLE_SELECTOR_CITATION_RE.finditer(brief_text)
        ]
        + [
            (match.start(), False, match.group(0))
            for match in FILE_LINE_CITATION_RE.finditer(brief_text)
        ]
        + [
            (
                match.start("citation"),
                "::" in match.group("citation"),
                match.group("citation"),
            )
            for match in _DECLARED_ORACLE_LOCATOR_RE.finditer(brief_text)
        ]
    )
    by_file: dict[str, str] = {}
    for _, has_selector, citation in matches:
        if has_selector:
            file_part = citation.partition("::")[0]
        else:
            file_part = citation.rsplit(":", 1)[0]
        if not is_code_target_citation(file_part):
            continue
        if has_selector:
            by_file.setdefault(file_part, citation)
        elif is_test_shaped_path(file_part):
            by_file.setdefault(file_part, file_part)
    return list(by_file.values())


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


_BOLD_SPAN_LINE_RE = re.compile(r"\*\*[^*\n]*\*\*")


def first_unparsed_obligation_candidate(brief_text: str) -> str | None:
    """The first LINE carrying a bold span that LOOKS like an attempted
    obligation label (contains an uppercase letter) but does not match
    `_OBLIGATION_TOKEN_RE`'s accepted shapes -- `None` when no such line
    exists. Run 17 (K4 matrix): a bare "no obligation token found"
    refusal, with nothing to diagnose against, is far weaker evidence
    than one that quotes the exact line a real root/DESIGN pair can
    compare against the accepted shapes directly."""
    for line in brief_text.splitlines():
        for span in _BOLD_SPAN_LINE_RE.finditer(line):
            text = span.group(0)
            if not any(character.isupper() for character in text):
                continue
            if _OBLIGATION_TOKEN_RE.fullmatch(text):
                continue
            return line.strip()
    return None


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


def _non_python_target_local_candidates(
    brief_text: str, target_candidate: str, grounded_atoms: Collection[str]
) -> list[str]:
    """Every backtick-quoted symbol candidate cited on a line that names
    ``target_candidate`` itself AND that is a member of ``grounded_atoms``
    -- the target file's own resolved atom set -- in first-appearance
    order, minus the target path. Line proximity is the PRE-filter (a
    Target-table row, a ``path:line`` citation and prose naming the path
    all put the path on the symbol's own line); atom membership is the
    final filter. Q-90/Q-91 acceptance law (SF mechanical falsification
    2026-08-21 of the previous textual grounding): a whole-word text scan
    of the file admitted a symbol occurring only in a COMMENT or a STRING
    LITERAL as existing. Existence is therefore decided against the ATOMS
    the CodeFact port resolves for the target file -- a token the file
    merely mentions in prose is not an atom, so it is excluded by
    construction. This function does NO I/O: the caller resolves
    ``grounded_atoms`` outside the domain boundary and an unreliable
    resolution arrives here as the empty set (honest absence)."""
    brief_text = _join_wrapped_backticks(brief_text)
    proximate: list[str] = []
    for line in brief_text.splitlines():
        if target_candidate not in line:
            continue
        for match in _BACKTICK_SYMBOL_RE.finditer(line):
            token = match.group(1)
            if token == target_candidate:
                continue
            if token not in proximate:
                proximate.append(token)
    return [token for token in proximate if token in grounded_atoms]


def declared_imports_for_target(
    repo_root: Path,
    target_candidate: str,
    brief_text: str,
    *,
    target_atoms: Callable[[str], Collection[str]],
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
    invented into a guess.

    SF friction report 2026-08-20, item 3: both ``is_name_bound_in_
    target_file`` (Python AST parse) and ``resolve_declared_import``
    (searches for a Python FILE matching the dotted path) are
    Python-specific checkers -- for a non-Python target (Go, Rust, TS,
    ...) they reject EVERY candidate, including genuine language stdlib
    names (``os``/``strings``/``testing`` for Go), since no Python file
    ever backs them, so a non-Python target's list is admitted
    UNVERIFIED. SF friction FAIL 2026-08-21 (polyglot root): admitting
    the WHOLE brief's candidate list gave every non-Python target the
    identical global symbol set, conflating (a) unverifiable-here with
    admitted-here and (b) the prose's global scope with a target-local
    binding -- consumer ATD correctly refused EVIDENCE_GAP. The honest
    admission this brief format permits is structural proximity plus
    atom grounding (``_non_python_target_local_candidates``): a
    candidate counts for THIS target only when it sits on a line that
    itself names ``target_candidate`` (its Target-table row, a
    ``path:line`` citation, or prose naming the path) AND the symbol is
    among the target file's own resolved ATOMS at base. Q-90/Q-91
    acceptance law (SF mechanical falsification 2026-08-21): the
    previous whole-word TEXT scan of the file admitted a symbol whose
    only occurrence was a comment or a string literal -- textual
    presence is not existence. Atoms are resolved through the CodeFact
    port (``query.atoms-in-file``) OUTSIDE this domain boundary and
    injected via ``target_atoms``; the composing caller decides on the
    resolution ENVELOPE (confidence/provider), never on the payload's
    shape alone -- only a ``binding-resolved`` answer yields atoms, and
    a noisy/failed/unsupported resolution arrives here as the empty set.
    Grounding is what excludes delivery products: a future symbol is not
    an atom at base, whatever grammar the authority used to declare it
    (an ``Oracle target locator:`` line, a table row, or "Extend with
    `X`" prose -- Q-83 residual friction 2026-08-21 showed the locator
    syntax alone missed the other two shapes). Scoping that finds
    nothing yields an empty list: honest absence, never the global
    fallback."""
    if not target_candidate.endswith(".py"):
        return _non_python_target_local_candidates(
            brief_text, target_candidate, target_atoms(target_candidate)
        )
    verified: list[str] = []
    for token in extract_declared_import_candidates(brief_text):
        if is_name_bound_in_target_file(
            repo_root, target_candidate, token
        ) or resolve_declared_import(repo_root, token):
            verified.append(token)
    return verified


def extract_skill_citations(brief_text: str) -> list[str]:
    """Every backtick-quoted ``nw-*`` skill name literally cited in the
    brief, in first-appearance order, deduplicated. Shape only -- grounding
    against the installed skill registry happens in
    ``skill_citations_for_repo``."""
    brief_text = _join_wrapped_backticks(brief_text)
    found: list[str] = []
    for match in _SKILL_CITATION_RE.finditer(brief_text):
        token = match.group(1)
        if token not in found:
            found.append(token)
    return found


def skill_citations_for_repo(repo_root: Path, brief_text: str) -> list[str]:
    """Every ``extract_skill_citations`` candidate that resolves to a real,
    installed skill under the base tree's own ``nWave/skills/<name>/
    SKILL.md`` -- the identical base-tree grounding discipline
    ``declared_imports_for_target`` already applies to a symbol citation,
    applied here to a skill-name citation: a cited name alone is never
    trusted, only a name the base tree can independently prove exists.
    A brief citing no skill, or citing one this repository does not ship,
    yields an empty list -- never invented, never assumed."""
    verified: list[str] = []
    for token in extract_skill_citations(brief_text):
        if (repo_root / "nWave" / "skills" / token / "SKILL.md").is_file():
            verified.append(token)
    return verified


#: The ``nw-property-based-testing`` family skill's own name -- citing IT
#: (rather than a specific ``nw-pbt-<lang>`` variant) is the language-
#: agnostic shape Ale asked for: nWave is language-agnostic, so a brief
#: should never have to guess or hardcode a Python-shaped variant name.
PBT_FAMILY_SKILL = "nw-property-based-testing"

#: Source-file extension -> (language name, ``nw-pbt-<lang>`` adapter this
#: repository ships for it). Literal duplication (not parsed from the skill
#: file, which is prose), of the EXACT table `nw-test-design-mandates-
#: layered-mechanics/SKILL.md` documents under "Adapter family | Languages
#: | PBT binding | Test/step idiom" -- same duplication discipline
#: ``SCHEMA_OBLIGATION_TOKENS`` above already applies: this module needs a
#: name+extension FILTER, never authority to invent a ninth family. A
#: language with no adapter (that table lists exactly eight), or one not
#: actually installed in THIS repository, degrades to ``PBT_FAMILY_SKILL``
#: (``"family-fallback"``), never an invented ninth family and never a
#: bare refusal -- language specificity is an upgrade when available, never
#: a requirement (Ale, 2026-08-20 follow-up).
_EXTENSION_TO_PBT_ADAPTER: dict[str, tuple[str, str]] = {
    ".py": ("Python", "nw-pbt-python"),
    ".ts": ("TypeScript", "nw-pbt-typescript"),
    ".tsx": ("TypeScript", "nw-pbt-typescript"),
    ".js": ("JavaScript", "nw-pbt-typescript"),
    ".jsx": ("JavaScript", "nw-pbt-typescript"),
    ".cs": ("C#", "nw-pbt-dotnet"),
    ".fs": ("F#", "nw-pbt-dotnet"),
    ".java": ("Java", "nw-pbt-jvm"),
    ".kt": ("Kotlin", "nw-pbt-jvm"),
    ".kts": ("Kotlin", "nw-pbt-jvm"),
    ".scala": ("Scala", "nw-pbt-jvm"),
    ".rs": ("Rust", "nw-pbt-rust"),
    ".go": ("Go", "nw-pbt-go"),
    ".hs": ("Haskell", "nw-pbt-haskell"),
    ".erl": ("Erlang", "nw-pbt-erlang-elixir"),
    ".ex": ("Elixir", "nw-pbt-erlang-elixir"),
    ".exs": ("Elixir", "nw-pbt-erlang-elixir"),
}


def _skill_is_installed(repo_root: Path, skill_name: str) -> bool:
    return (repo_root / "nWave" / "skills" / skill_name / "SKILL.md").is_file()


def resolve_pbt_adapter(
    repo_root: Path, cited_skills: list[str], target_paths: Iterable[str]
) -> dict[str, str | None] | None:
    """Mechanically resolve which PBT skill a citation implies for THIS
    contract's own targets -- never the bare citation's own claimed
    language, never a silent default to Python (Ale, 2026-08-20: "nw-pbt-
    python e' troppo python-centric ... nWave e' language agnostic").
    Reads ``cited_skills`` (``skill_citations_for_repo``'s own output) for
    a PBT citation -- the family skill (``PBT_FAMILY_SKILL``) or any
    specific ``nw-pbt-*`` variant -- and ``target_paths`` (the contract's
    own already-known target file paths) for the language evidence.

    ``None`` when ``cited_skills`` carries no PBT citation at all --
    nothing to resolve. Otherwise always a fully-populated dict naming a
    REAL, installed skill, never a silent partial one and never a bare
    refusal (Ale, 2026-08-20 follow-up: "il campo porta sempre una skill
    utilizzabile; la specificita' di linguaggio e' un upgrade quando
    disponibile, mai un requisito"). ``status`` is one of

    * ``"resolved"`` -- every target maps to the SAME installed adapter,
      and (when a specific variant was cited) it agrees with the citation.
    * ``"discrepancy"`` -- a specific variant was cited but disagrees with
      the target-derived, installed adapter; ``resolved-variant`` is the
      target-derived one (targets win, the citation's own claimed language
      never does), and ``reason`` names the mismatch.
    * ``"family-fallback"`` -- targets span more than one adapter, no
      target extension maps to any of the eight shipped adapters, or the
      one target-derived adapter is not actually installed in THIS
      repository; ``resolved-variant`` degrades to ``PBT_FAMILY_SKILL``
      (still a real, usable, language-agnostic skill) rather than either
      guessing a language-specific one or naming none at all.
    * ``"unresolved"`` -- the doubly-degenerate case: a fallback was
      needed and even ``PBT_FAMILY_SKILL`` itself is not installed in this
      repository; ``resolved-variant`` is ``None``. LOUD, never silent.
    """
    pbt_citations = [
        token
        for token in cited_skills
        if token == PBT_FAMILY_SKILL or token.startswith("nw-pbt-")
    ]
    if not pbt_citations:
        return None
    cited = pbt_citations[0]

    def _family_fallback(reason: str) -> dict[str, str | None]:
        if _skill_is_installed(repo_root, PBT_FAMILY_SKILL):
            return {
                "cited": cited,
                "resolved-variant": PBT_FAMILY_SKILL,
                "status": "family-fallback",
                "reason": reason,
            }
        return {
            "cited": cited,
            "resolved-variant": None,
            "status": "unresolved",
            "reason": f"{reason}, and the generic {PBT_FAMILY_SKILL!r} "
            "fallback is not installed in this repository either",
        }

    adapters_seen: dict[str, str] = {}  # variant -> one exemplar extension
    unmapped_extensions: list[str] = []
    for target_path in target_paths:
        suffix = Path(target_path).suffix
        adapter = _EXTENSION_TO_PBT_ADAPTER.get(suffix)
        if adapter is None:
            if suffix and suffix not in unmapped_extensions:
                unmapped_extensions.append(suffix)
            continue
        _, variant = adapter
        adapters_seen.setdefault(variant, suffix)

    if len(adapters_seen) == 1:
        ((variant, extension),) = adapters_seen.items()
        if not _skill_is_installed(repo_root, variant):
            return _family_fallback(
                f"target extension {extension!r} maps to {variant!r}, but "
                "this repository does not ship it -- a usable skill always "
                "wins over an absent language-specific upgrade"
            )
        if cited in (PBT_FAMILY_SKILL, variant):
            return {
                "cited": cited,
                "resolved-variant": variant,
                "status": "resolved",
                "reason": f"target extension {extension!r} maps to {variant!r}",
            }
        return {
            "cited": cited,
            "resolved-variant": variant,
            "status": "discrepancy",
            "reason": (
                f"brief cited {cited!r}, but target extension {extension!r} "
                f"maps to {variant!r} -- the target-derived variant wins, "
                "never the citation's own claimed language"
            ),
        }
    if adapters_seen:
        return _family_fallback(
            "targets span more than one nw-pbt-<lang> adapter: "
            f"{', '.join(sorted(adapters_seen))}"
        )
    return _family_fallback(
        "no target file extension maps to a known nw-pbt-<lang> adapter"
        + (
            f" (observed: {', '.join(sorted(unmapped_extensions))})"
            if unmapped_extensions
            else ""
        )
    )
