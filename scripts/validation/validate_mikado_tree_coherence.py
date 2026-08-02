#!/usr/bin/env python3
"""Tree-coherence gate for a Mikado execution SSOT.

A node's state used to be written down in three places in the same document --
the lane table (`## CORSIE`), the mindmap (`## L'ALBERO`) and the per-node
tables (`## STATO NODO PER NODO`). Nothing compared them, so a node could read
INTEGRATA with a sha in one carrier and PRONTO with an empty closure reference
in another, at the same time -- and `carrier-contradiction` (below) only fires
on a CLOSED-vs-OPEN split, so eight drifts across five classes between
`## L'ALBERO` and `## STATO NODO PER NODO` went uncaught: two states (D12
table BLOCCATO-SERVE-DESIGN vs tree CONTESO; D24 table PRONTO vs tree
CONTESO), one effort (D12 table `M (era XS)` vs tree `S/M (non XS)`), one
Verdetto (D53 table MISURATO vs tree detail NON_MISURATO), one title (D29,
wrong in BOTH carriers -- 3 vs 4, and the node's own `CORREZIONE MISURATA
2026-07-28` line says the measured answer is 5), and three closure-sha
citations naming another node's commit (D31a cited D17's sha; D31b and D46a
both cited D14's sha). Every one of them was OPEN-vs-OPEN or a non-state
field, structurally invisible to that rule.

State is now typed ONCE: `## STATO NODO PER NODO` is the SOLE carrier of a
node's state. `## L'ALBERO` keeps the tree's SHAPE -- dependency rings, node
ids, curated per-node prose -- and carries no state word at all; a state word
on an `## L'ALBERO` node row is rejected by `state-typed-outside-its-carrier`
and withdrawn mechanically with `mikado_board.py --withdraw-tree-state`, never
by hand. `## CORSIE` is unaffected -- it types state for its own population
(lane-level work, 24 of its 42 rows describing work with no tree node at all)
and remains a live second axis: `carrier-contradiction` still compares it
against `## STATO NODO PER NODO`.

This gate decides on the PROPERTY -- *is there attested evidence of closure?* --
never on the DESIGNATION -- *the row says PRONTO*. It answers with three states
and never collapses the third into the first.

A sha that EXISTS is still a designation
----------------------------------------
Resolving the pointer was itself only half the property. A node can close on a
sha that is a perfectly good ancestor of trunk and still not be closed, because
that commit does not carry the work the node declares. So the gate also reads
what each cited commit actually rewrote and compares it with what the closure
note claims.

What that comparison can and cannot decide is stated in the report itself, and
the honest half is the second: **the gate cannot verify that a commit implements
a node**, and does not try. It decides one narrow, falsifiable conjunction -- the
note NAMES an artifact (a source path, a `des` subcommand) AND the commit
rewrote nothing outside the plan's own bookkeeping documentation. A closure note
that names no artifact is unfalsifiable by construction; those are counted and
reported, never passed off as verified.

Only dependency: Python. Commit ancestry and commit contents are read straight
off ``.git/`` through ports that degrade LOUD when the object store cannot
answer.

Usage:
    python3 scripts/validation/validate_mikado_tree_coherence.py --file DOC
    python3 scripts/validation/validate_mikado_tree_coherence.py --file DOC --explain D22
    python3 scripts/validation/validate_mikado_tree_coherence.py --file DOC --find-carrier D32

Exit codes:
    0: COHERENT
    1: INCOHERENT -- at least one node carries contradictory or unattested state
    2: NOT_VERIFIABLE -- a check could not be decided; never collapsed into 0
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from gate_ratchet import RatchetDecision, decide_ratchet, undecidable_baseline
from git_commit_contents import (
    BlobOutcome,
    CommitContentsPort,
    UnavailableContents,
    build_contents,
)
from git_commit_reachability import (
    CommitReachabilityPort,
    Reachability,
    build_reachability,
    locate_worktree_root,
)
from mikado_closure_ledger import (
    NodeState,
    RefusalCause,
    evaluate_node,
    node_refusal_cause,
)


DEFAULT_TRUNK_REF = "feature/atdd-pure-staging"

CARRIER_LANES = "CORSIE"
CARRIER_TREE = "L'ALBERO"
CARRIER_NODES = "STATO NODO PER NODO"
#: Three sections, but ONE carrier of node STATE plus two carriers of other
#: facts. `CARRIER_NODES` (`## STATO NODO PER NODO`) is the sole carrier of
#: state -- `_rule_state_typed_outside_its_carrier` rejects a state word
#: anywhere on a `CARRIER_TREE` node row. `CARRIER_TREE` (`## L'ALBERO`)
#: carries the dependency SHAPE (rings, node ids) and curated per-node prose,
#: never a state word. `CARRIER_LANES` (`## CORSIE`) carries closure claims
#: for its own lane-level population, which is not always a tree node, and
#: stays the second live axis `carrier-contradiction` reconciles against
#: `CARRIER_NODES`. Collapsing state to one carrier does not collapse the
#: carrier COUNT: `population-floor` still requires >= 2 carriers present.
CANONICAL_CARRIERS = (CARRIER_LANES, CARRIER_TREE, CARRIER_NODES)

#: The document's own legend: FATTO means "chiuso **con riferimento**". CHIUSO/CHIUSA
#: are the document's other closure designation (closed-without-work, e.g. a refuted
#: premise) -- the orchestrator's own prose treats them as closed for open/closed
#: purposes (`## IL GATE ... DESIGNAZIONE`: "le otto righe sono corrette FATTO/CHIUSO").
#: `MISURATO` is closure for a node whose deliverable IS the measurement -- the
#: board has always drawn it closed (`[m]`, rank 9) and the document tallies it
#: beside FATTO/CHIUSO. It was missing here, and the miss was silent rather than
#: loud: with the word unknown, the column-drift rescue in `parse_node_table_claims`
#: walked past the `Stato` cell and read D46a/D46b/D81's state out of the `Verdetto`
#: column next door, which happens to hold `NON_MISURATO`. Board said closed, gate
#: said open, and nothing reported the disagreement -- the same shape as the seven
#: nodes that vanished, one word further along.
CLOSED_STATES = frozenset(
    {"FATTO", "INTEGRATA", "INTEGRATE", "CHIUSO", "CHIUSA", "MISURATO"}
)
#: `BLOCCATO-SERVE-DESIGN` is the document's own word for "open, and cannot be
#: scheduled until a DESIGN decision lands". It was missing from this set, and a
#: row carrying it did not become UNVERIFIABLE -- it vanished from the gate's
#: population entirely, D03b and D27 among the seven.
#: `<closed word>-SOSPESO` says the one thing the legend could not: the work is
#: FINISHED and the closure is SUSPENDED, because a node this one waits for is
#: still open. It exists because both available words lied -- `FATTO` overstates
#: (it reports a closure standing on nothing) and `PRONTO`/`AL LAVORO` erase work
#: that genuinely happened, sending the next reader to redo it.
#:
#: Built as a SUFFIX over every closing word rather than as one new token, because
#: the property is "this closure is suspended" and not the particular word in front
#: of it: `MISURATO-SOSPESO` is the same fact about a measurement node that
#: `FATTO-SOSPESO` is about an implementation node, and a vocabulary that needed a
#: hand-written entry per closing word would have grown a gap the day someone added
#: the seventh. Every one classifies OPEN, never closed: a suspended closure counted
#: as closed would reproduce the exact overstatement `closed-over-open-child` exists
#: to stop, one token further along.
SUSPENDED_STATES = frozenset(f"{state}-SOSPESO" for state in CLOSED_STATES)
OPEN_STATES = (
    frozenset(
        {
            "PRONTO",
            "IN CORSO",
            "QUARANTENA",
            "CONTESO",
            "NON_MISURATO",
            "SOSPESO",
            "BLOCCATO-SERVE-DESIGN",
        }
    )
    | SUSPENDED_STATES
)
NOT_WORK_STATES = frozenset({"GUARDIA", "—", "–", "-", ""})

#: `FUSO IN <target>` -- this node's work was folded into another node. Fusion is
#: not a closure of its own: it CARRIES the target's state. Fused into an open node
#: it has closed nothing, so it reads OPEN; it turns CLOSED only when the node it
#: fused into closes. Classified as the safe direction (OPEN) here and upgraded by
#: `resolve_fusions` once every node's class is known, because the answer depends on
#: a node other than this one. Before this existed the word was unknown to the
#: legend, and the column-drift fallback below walked past the `Stato` cell and read
#: D47's state out of the `Verdetto` column instead.
_FUSED_INTO = re.compile(r"^FUSO\s+IN\s+([A-Z]{1,2}\d{1,3}[A-Za-z]?)\b", re.IGNORECASE)


def fusion_target(raw: str) -> str | None:
    """The node id a `FUSO IN X` state defers to, or None when not a fusion."""
    match = _FUSED_INTO.match(normalize_state(raw))
    return match.group(1).upper() if match else None


#: Completion words that predicted a wrong state 3 times out of 3 when they
#: appeared WITHOUT a pointer next to them. An inferred signal, so advisory only.
COMPLETION_LEXICON = (
    "sigillato",
    "sigillata",
    "review-approvato",
    "review approvato",
    "resta solo il commit",
    "resta la chiusura",
    "manca solo il commit",
)

_NODE_ID = re.compile(r"\b([A-Z]{1,2}\d{1,3}[a-z]?)\b")
_LANE_NODE = re.compile(r"\bnodo\s+([A-Z]{1,2}\d{1,3}[a-z]?)\b", re.IGNORECASE)
#: Node ids reach this function already uppercased (every parser calls
#: `.upper()` on the raw text) -- so a suffix, if present, is uppercase too.
_NODE_BASE = re.compile(r"^([A-Z]{1,2}\d{1,3})([A-Za-z]?)$")
#: A CORSIA name can carry its node id as a head (`d07`, `d25-deadtests`) without the
#: word "nodo" next to it. Anchored to the start and boundary-checked so it can never
#: clip a longer number in half (`d071x` does not yield `D07`).
_LANE_ID_HEAD = re.compile(r"^([A-Za-z]{1,2}\d{1,3})([a-z]?)(?![A-Za-z0-9])")
_SHA_IN_BACKTICKS = re.compile(r"`([0-9a-fA-F]{7,40})`")
_SHA_AFTER_COMMIT = re.compile(r"\bcommit\s+([0-9a-fA-F]{7,40})\b")
_PLACEHOLDER = re.compile(r"da\s+compilare|^n/?a$|^tbd$|^\?+$", re.IGNORECASE)

#: Extensions that make a token in a closure note read as a source artifact.
_SOURCE_EXT = "py|json|ya?ml|toml|sh|js|ts|cfg|ini|feature"
#: `scripts/validation/foo.py` -- a path, named as a deliverable.
_NOTE_PATH = re.compile(r"\b([\w.\-]+(?:/[\w.\-]+)+\.(?:" + _SOURCE_EXT + r"))\b")
#: `foo_bar.py` in backticks -- a file, named without its directory.
_NOTE_FILE = re.compile(r"`([\w.\-]+\.(?:" + _SOURCE_EXT + r"))`")
#: `des report-delivery-metrics` -- a CLI surface, named as a deliverable.
_NOTE_CLI = re.compile(r"`(des\s+[a-z][a-z0-9-]+)")
_SEPARATOR_CELL = re.compile(r"^:?-{2,}:?$")
_TREE_NODE_LINE = re.compile(r"^\s+([A-Z]{1,2}\d{1,3}[a-z]?)\s+\|")
_TREE_ATTRIBUTE = re.compile(r"^\s*:\s*(.*?)\s*\|\s*(.*)$")
_ATTRIBUTE_SPLIT = re.compile(r"(?=\s{2,}:\s)")


class Verdict(str, Enum):
    COHERENT = "COHERENT"
    INCOHERENT = "INCOHERENT"
    UNVERIFIABLE = "NOT_VERIFIABLE"


class Severity(str, Enum):
    REJECT = "reject"
    UNVERIFIABLE = "unverifiable"
    ADVISORY = "advisory"


class ClosureClass(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    NOT_WORK = "NOT_WORK"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class StateClaim:
    """One carrier's statement about one node's state."""

    node_id: str
    carrier: str
    raw_state: str
    reference: str
    line: int

    @property
    def closure(self) -> ClosureClass:
        return classify_state(self.raw_state)

    @property
    def shas(self) -> tuple[str, ...]:
        return extract_shas(self.reference)

    @property
    def is_attested(self) -> bool:
        return bool(self.shas)


@dataclass(frozen=True)
class _LaneAmbiguity:
    """A CORSIA row whose closure claim names a base shared by >1 real node.

    Never guessed at: recorded so the aggregate can surface it as the third
    state instead of silently treating the row as if it said nothing.
    """

    lane: str
    base: str
    candidates: tuple[str, ...]
    raw_state: str
    line: int


@dataclass(frozen=True)
class Finding:
    rule: str
    node_id: str
    severity: Severity
    what: str
    why: str
    how: str
    locations: tuple[str, ...] = ()

    def render(self) -> str:
        head = f"[{self.severity.value}] {self.rule} · {self.node_id}"
        body = [f"  WHAT  {self.what}", f"  WHY  {self.why}", f"  HOW  {self.how}"]
        if self.locations:
            body.insert(1, "  WHERE  " + " · ".join(self.locations))
        return "\n".join([head, *body])


@dataclass
class _CarryCoverage:
    """How much of the closed population the carry-check could actually judge.

    Printed with every verdict. A gate that reports only what it caught invites
    the reader to mistake its silence for a clean bill: these counters are how
    the third state -- and the unfalsifiable majority -- reach the aggregate.
    """

    closures: int = 0
    carried: int = 0
    not_carried: int = 0
    undecidable: int = 0
    unmatched: int = 0
    unfalsifiable: int = 0

    @property
    def evaluable(self) -> int:
        return self.carried + self.not_carried

    def render(self) -> str:
        return (
            f"  carry-check · {self.closures} attested closures · "
            f"{self.evaluable} decided ({self.carried} carry the claim, "
            f"{self.not_carried} do not) · {self.undecidable} undecidable · "
            f"{self.unmatched} named-but-unmatched (a `des` subcommand no changed "
            "path evidences) · "
            f"{self.unfalsifiable} unfalsifiable (the note names no artifact)\n"
            "  cannot catch: a note whose NAMED artifact the commit did rewrite but "
            "did not actually implement,\n"
            "  and any claim about work done outside the diff (a measurement, a "
            "review, a run on real data)."
        )


@dataclass(frozen=True)
class GateReport:
    verdict: Verdict
    findings: tuple[Finding, ...]
    nodes_examined: int
    carriers_seen: tuple[str, ...]
    claims: tuple[StateClaim, ...] = ()
    carry: _CarryCoverage = None  # type: ignore[assignment]

    def by_severity(self, severity: Severity) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity is severity)


# ---------------------------------------------------------------------------
# vocabulary
# ---------------------------------------------------------------------------


def normalize_state(raw: str) -> str:
    cleaned = raw.strip().strip("*`_ ").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.upper()


def classify_state(raw: str) -> ClosureClass:
    state = normalize_state(raw)
    if state in CLOSED_STATES:
        return ClosureClass.CLOSED
    if state in OPEN_STATES:
        return ClosureClass.OPEN
    if state in NOT_WORK_STATES:
        return ClosureClass.NOT_WORK
    # A fusion carries the target's state, which this function cannot see. OPEN is
    # the only safe answer from here: `resolve_fusions` turns it CLOSED when -- and
    # only when -- the target is closed, so a fusion never reports a closure early.
    if fusion_target(state) is not None:
        return ClosureClass.OPEN
    return ClosureClass.UNKNOWN


def resolve_fusions(
    states: dict[str, ClosureClass], targets: dict[str, str | None]
) -> dict[str, ClosureClass]:
    """A fused node reads CLOSED only once the node it fused INTO is closed.

    Fusion defers work instead of finishing it, so a fused node's class is the
    TARGET's, never its own -- `FUSO IN X` while X is open has closed nothing. A
    chain of fusions is walked to its end. A cycle of fusions, and a fusion naming a
    target the document does not carry, both stay OPEN: the safe direction, because
    the alternative is reporting a closure nobody can point at.
    """
    resolved = dict(states)
    for node, target in targets.items():
        if target is None:
            continue
        seen = {node}
        cursor: str | None = target
        while cursor is not None and targets.get(cursor) is not None:
            if cursor in seen:
                cursor = None  # a ring of fusions closes nothing
                break
            seen.add(cursor)
            cursor = targets[cursor]
        resolved[node] = (
            ClosureClass.CLOSED
            if cursor is not None and states.get(cursor) is ClosureClass.CLOSED
            else ClosureClass.OPEN
        )
    return resolved


def _state_token_in(text: str) -> str | None:
    """Find a declared state word inside a free-form cell, longest first."""
    upper = text.upper()
    known = sorted(CLOSED_STATES | OPEN_STATES | {"GUARDIA"}, key=len, reverse=True)
    for word in known:
        if re.search(rf"\b{re.escape(word)}\b", upper):
            return word
    # A fusion keeps its target: `FUSO` alone would name a deferral without saying
    # what it defers TO, and `resolve_fusions` would have nothing to resolve.
    fusion = _FUSED_INTO.match(normalize_state(text))
    if fusion is not None:
        return fusion.group(0)
    stripped = normalize_state(text)
    if stripped in NOT_WORK_STATES:
        return stripped
    return None


def extract_shas(text: str) -> tuple[str, ...]:
    """Commit pointers only: backticked hex, or hex right after ``commit``."""
    found = [m.lower() for m in _SHA_IN_BACKTICKS.findall(text)]
    found += [m.lower() for m in _SHA_AFTER_COMMIT.findall(text)]
    ordered: list[str] = []
    for sha in found:
        if sha not in ordered:
            ordered.append(sha)
    return tuple(ordered)


def is_placeholder(text: str) -> bool:
    cleaned = text.strip().strip("*`_() ").strip()
    return not cleaned or bool(_PLACEHOLDER.search(cleaned))


def is_bookkeeping_path(path: str) -> bool:
    """True when the path is the plan talking about itself, not the product.

    ``docs/`` is the internal narrative (the mikado tree, feature deltas, audit
    notes) and a root-level ``*.md`` is a repo-level note. Everything else --
    including ``nWave/`` and every skill and data asset under it -- is shipped,
    so rewriting it IS work and must never read as "documentation only".
    """
    return path.startswith("docs/") or ("/" not in path and path.endswith(".md"))


def artifact_claims(note: str) -> tuple[str, ...]:
    """Artifacts a closure note NAMES as delivered.

    Only two shapes count, both of them things the note itself declares rather
    than something the gate infers from prose: a source path/file, and a `des`
    subcommand. A bookkeeping path names no artifact.
    """
    found: list[str] = []
    for token in (
        *_NOTE_PATH.findall(note),
        *_NOTE_FILE.findall(note),
        *_NOTE_CLI.findall(note),
    ):
        cleaned = re.sub(r"\s+", " ", token.strip())
        if cleaned.startswith("des ") or not is_bookkeeping_path(cleaned):
            if cleaned not in found:
                found.append(cleaned)
    return tuple(found)


def path_fragments_for(claim_token: str) -> tuple[str, ...]:
    """Path fragments that would evidence ``claim_token`` in a changed-path set."""
    if claim_token.startswith("des "):
        sub = claim_token.split(None, 1)[1]
        return (sub, sub.replace("-", "_"))
    return (claim_token,)


def _base_id(node_id: str) -> str:
    """Strip one trailing lowercase suffix letter: `D25a` -> `D25`, `D07` unchanged."""
    match = _NODE_BASE.match(node_id)
    return match.group(1) if match else node_id


def lane_id_candidate(lane_name: str) -> str | None:
    """Extract a node-id-shaped head from a CORSIA name, or None if it has none."""
    match = _LANE_ID_HEAD.match(lane_name.strip())
    if match is None:
        return None
    return (match.group(1) + match.group(2)).upper()


def resolve_node_reference(
    candidate: str, known_ids: frozenset[str]
) -> tuple[str | None, tuple[str, ...]]:
    """Decide which real node a closure-claim candidate names.

    Three outcomes, on the PROPERTY (does this id, or its base, name exactly one
    real node?) rather than the DESIGNATION (how the row happened to be written):
      - confident single match  -> (node_id, ())
      - the base is shared by >1 suffixed node (`D25` -> D25a, D25b) -> (None, group)
        -- an ambiguous join, never silently guessed.
      - no real node carries this id or base at all -> (None, ()) -- not a tree
        node claim (a feature slice, a defect lane, ...); untouched.
    """
    if candidate in known_ids:
        return candidate, ()
    group = tuple(sorted(i for i in known_ids if _base_id(i) == candidate))
    if len(group) == 1:
        return group[0], ()
    if len(group) > 1:
        return None, group
    return None, ()


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Section:
    title: str
    start: int  # 1-based line of the heading
    lines: tuple[tuple[int, str], ...]


def _split_sections(lines: list[str]) -> list[_Section]:
    sections: list[_Section] = []
    current_title: str | None = None
    current_start = 0
    buffer: list[tuple[int, str]] = []
    for index, line in enumerate(lines, start=1):
        if line.startswith("## "):
            if current_title is not None:
                sections.append(_Section(current_title, current_start, tuple(buffer)))
            current_title = line[3:].strip()
            current_start = index
            buffer = []
        elif current_title is not None:
            buffer.append((index, line))
    if current_title is not None:
        sections.append(_Section(current_title, current_start, tuple(buffer)))
    return sections


def _find_section(sections: list[_Section], key: str) -> _Section | None:
    for section in sections:
        if section.title.upper().startswith(key.upper()):
            return section
    return None


def _table_rows(section: _Section):
    """Yield ``(line_no, header_cells, data_cells)`` for every markdown table."""
    header: list[str] | None = None
    for line_no, raw in section.lines:
        stripped = raw.strip()
        if not stripped.startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if all(_SEPARATOR_CELL.match(c) for c in cells if c):
            continue
        if header is None:
            header = [c.lower() for c in cells]
            continue
        yield line_no, header, cells


def _column(header: list[str], *names: str) -> int | None:
    for name in names:
        for index, cell in enumerate(header):
            if name in cell:
                return index
    return None


def parse_lane_claims(
    section: _Section, known_node_ids: frozenset[str] = frozenset()
) -> tuple[list[StateClaim], list[_LaneAmbiguity]]:
    claims: list[StateClaim] = []
    ambiguities: list[_LaneAmbiguity] = []
    for line_no, header, cells in _table_rows(section):
        joined = " | ".join(cells)
        state_index = _column(header, "stato")
        cell = (
            cells[state_index]
            if state_index is not None and state_index < len(cells)
            else ""
        )
        token = _state_token_in(cell) or _state_token_in(joined)
        if token is None:
            continue
        match = _LANE_NODE.search(joined)
        if match is not None:
            subject = match.group(1).upper()
            candidate: str | None = subject
        else:
            # A lane closing a feature or a bugfix is not a tree node, but it
            # still cites a closure sha -- and that sha is checked all the same.
            lane_index = _column(header, "corsia")
            raw_lane = (
                cells[lane_index]
                if lane_index is not None and lane_index < len(cells)
                else ""
            )
            subject = raw_lane.strip().strip("`*_ ") or "(corsia senza nome)"
            candidate = lane_id_candidate(subject)
        if candidate is not None:
            resolved, ambiguous_group = resolve_node_reference(
                candidate, known_node_ids
            )
            if resolved is not None:
                subject = resolved
            elif ambiguous_group:
                ambiguities.append(
                    _LaneAmbiguity(
                        lane=subject,
                        base=candidate,
                        candidates=ambiguous_group,
                        raw_state=token,
                        line=line_no,
                    )
                )
        claims.append(
            StateClaim(
                node_id=subject,
                carrier=CARRIER_LANES,
                raw_state=token,
                reference=cell or joined,
                line=line_no,
            )
        )
    return claims, ambiguities


def node_table_ids(section: _Section) -> frozenset[str]:
    """Every node id named in the STATO table's first column.

    Independent of state-vocabulary recognition -- a node the table lists but
    whose state word the gate does not (yet) know is still a real node, and
    the lane-join must be able to see it as a candidate.
    """
    ids: set[str] = set()
    for _line_no, _header, cells in _table_rows(section):
        if not cells:
            continue
        match = _NODE_ID.search(cells[0])
        if match is not None:
            ids.add(match.group(1).upper())
    return frozenset(ids)


def parse_node_table_claims(section: _Section) -> list[StateClaim]:
    claims: list[StateClaim] = []
    for line_no, header, cells in _table_rows(section):
        if not cells:
            continue
        node_match = _NODE_ID.search(cells[0])
        if node_match is None:
            continue
        state_index = _column(header, "stato")
        raw_state = ""
        if state_index is not None and state_index < len(cells):
            candidate = cells[state_index]
            if _state_token_in(candidate) is not None:
                raw_state = candidate
        if not raw_state:
            # Column drift: decide on the property, not on the position.
            for candidate in cells[1:]:
                if _state_token_in(candidate) is not None:
                    raw_state = candidate
                    break
        if not raw_state:
            # A word the legend does not know must become UNVERIFIABLE, never
            # disappear. Dropping the row silently shrank the population by
            # seven nodes and took D03b with it, so every rule that asks about
            # a child's state got "no such node" instead of "still open".
            if state_index is not None and state_index < len(cells):
                raw_state = cells[state_index]
            if not normalize_state(raw_state):
                continue
        reference_index = _column(header, "riferimento")
        reference = ""
        if reference_index is not None and reference_index < len(cells):
            reference = cells[reference_index]
        elif len(cells) > 1:
            reference = cells[-1]
        claims.append(
            StateClaim(
                node_id=node_match.group(1).upper(),
                carrier=CARRIER_NODES,
                raw_state=_state_token_in(raw_state) or raw_state,
                reference=reference,
                line=line_no,
            )
        )
    return claims


@dataclass
class _TreeNode:
    node_id: str
    raw_state: str
    line: int
    reference: str = ""
    prose: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.prose is None:
            self.prose = []


def parse_tree_nodes(section: _Section) -> list[_TreeNode]:
    """Parse the mindmap, tolerating attributes glued onto a node line."""
    nodes: list[_TreeNode] = []
    current: _TreeNode | None = None
    for line_no, raw in section.lines:
        for segment in _ATTRIBUTE_SPLIT.split(raw):
            if not segment.strip():
                continue
            node_match = _TREE_NODE_LINE.match(segment)
            if node_match is not None:
                parts = [p.strip() for p in segment.split("|")]
                state = ""
                for part in parts[2:]:
                    if _state_token_in(part) is not None:
                        state = _state_token_in(part) or part
                        break
                current = _TreeNode(node_match.group(1).upper(), state, line_no)
                nodes.append(current)
                continue
            attribute = _TREE_ATTRIBUTE.match(segment)
            if attribute is None or current is None:
                continue
            key, value = attribute.group(1), attribute.group(2)
            if "riferimento" in key.lower():
                current.reference = value
            else:
                current.prose.append(value)
    return nodes


def parse_tree_claims(nodes: list[_TreeNode]) -> list[StateClaim]:
    return [
        StateClaim(
            node_id=node.node_id,
            carrier=CARRIER_TREE,
            raw_state=node.raw_state,
            reference=node.reference,
            line=node.line,
        )
        for node in nodes
        if node.raw_state
    ]


# ---------------------------------------------------------------------------
# rules
# ---------------------------------------------------------------------------


def _how_explain(doc_path: Path, node_id: str) -> str:
    script = Path(__file__).resolve()
    try:
        rendered = script.relative_to(Path.cwd())
    except ValueError:
        rendered = script
    return f"python3 {rendered} --file {doc_path} --explain {node_id}"


def _how_report(doc_path: Path) -> str:
    script = Path(__file__).resolve()
    try:
        rendered = script.relative_to(Path.cwd())
    except ValueError:
        rendered = script
    return f"python3 {rendered} --file {doc_path}"


def _where(doc_path: Path, claim: StateClaim) -> str:
    return f"{doc_path}:{claim.line} ({claim.carrier})"


def _rule_carrier_contradiction(
    doc_path: Path, node_id: str, claims: list[StateClaim]
) -> list[Finding]:
    closed = [c for c in claims if c.closure is ClosureClass.CLOSED]
    opened = [c for c in claims if c.closure is ClosureClass.OPEN]
    if not (closed and opened):
        return []
    said = " · ".join(
        f"{c.carrier} says {normalize_state(c.raw_state)}" for c in claims
    )
    return [
        Finding(
            rule="carrier-contradiction",
            node_id=node_id,
            severity=Severity.REJECT,
            what=(
                f"the same node `{node_id}` is declared CLOSED and OPEN in the same "
                f"document: {said}"
            ),
            why=(
                "two incompatible claims about the same node: at least one is false, and "
                "the reader has no way to know which. A closed state only holds if every "
                "carrier attests it"
            ),
            how=_how_explain(doc_path, node_id),
            locations=tuple(_where(doc_path, c) for c in claims),
        )
    ]


def _rule_state_typed_outside_its_carrier(
    doc_path: Path, tree_nodes: list[_TreeNode]
) -> list[Finding]:
    """A state word on an `## L'ALBERO` node row -- REJECT.

    `## STATO NODO PER NODO` is the sole carrier of a node's state (module
    docstring). A second typing on the `L'ALBERO` node row is exactly how
    this document drifted eight times across five classes without
    `carrier-contradiction` ever seeing it -- every one of the eight was
    OPEN-vs-OPEN or a non-state field, the one shape that rule cannot see.
    Reuses `_TREE_NODE_LINE` (via
    `parse_tree_nodes`, which already walks it) and `_state_token_in` against
    the SAME legend `CLOSED_STATES`/`OPEN_STATES`/`SUSPENDED_STATES`/
    `NOT_WORK_STATES` populate -- never a private second vocabulary.

    Fires only on a node ROW (`parse_tree_nodes` populates `raw_state` only
    from a field after the title on the `_TREE_NODE_LINE` itself), so a
    `: <key> | <value>` detail line, the `GOAL |` line, and the `R0 ·`..`R6 ·`
    ring headings -- none of which `parse_tree_nodes` reads a state out of --
    can never trip it.
    """
    findings: list[Finding] = []
    for node in tree_nodes:
        if not node.raw_state:
            continue
        findings.append(
            Finding(
                rule="state-typed-outside-its-carrier",
                node_id=node.node_id,
                severity=Severity.REJECT,
                what=(
                    f"`{node.node_id}` carries the state word "
                    f"`{normalize_state(node.raw_state)}` on its {CARRIER_TREE} node "
                    f"row at {doc_path}:{node.line}"
                ),
                why=(
                    f"state is typed once, in `{CARRIER_NODES}`: a second typing on "
                    f"`{CARRIER_TREE}` drifted from it eight times across five classes "
                    "(two states, one effort, one Verdetto, one title, three "
                    "closure-sha citations naming another node's commit) and none of "
                    "the eight was caught, because `carrier-contradiction` only fires "
                    "on a CLOSED-vs-OPEN split and every one of these eight was "
                    "same-class"
                ),
                how=(
                    "withdraw it mechanically -- never by hand -- with the "
                    "producing tool: "
                    f"uv run python scripts/mikado_board.py --withdraw-tree-state "
                    f"--file {doc_path}"
                ),
                locations=(f"{doc_path}:{node.line} ({CARRIER_TREE})",),
            )
        )
    return findings


def _rule_quarantine_split(
    doc_path: Path, node_id: str, claims: list[StateClaim]
) -> list[Finding]:
    states = {normalize_state(c.raw_state) for c in claims}
    if "QUARANTENA" not in states or len(states) == 1:
        return []
    others = sorted(states - {"QUARANTENA"})
    if not any(s in OPEN_STATES for s in others):
        return []  # the CLOSED/OPEN split is already reported by the rule above
    return [
        Finding(
            rule="quarantine-contradicted",
            node_id=node_id,
            severity=Severity.REJECT,
            what=(
                f"`{node_id}` is QUARANTENA per one carrier and {', '.join(others)} per "
                "another"
            ),
            why=(
                "the document's own legend says QUARANTENA means 'never schedule before': "
                "a carrier that declares it schedulable can let blocked work start"
            ),
            how=_how_explain(doc_path, node_id),
            locations=tuple(_where(doc_path, c) for c in claims),
        )
    ]


def _rule_closed_without_reference(
    doc_path: Path, node_id: str, claims: list[StateClaim]
) -> list[Finding]:
    findings: list[Finding] = []
    for claim in claims:
        if claim.closure is not ClosureClass.CLOSED or claim.is_attested:
            continue
        shown = claim.reference.strip() or "(empty cell)"
        findings.append(
            Finding(
                rule="closed-without-reference",
                node_id=node_id,
                severity=Severity.REJECT,
                what=(
                    f"`{node_id}` is {normalize_state(claim.raw_state)} in {claim.carrier} "
                    f"but the closure reference is {shown}"
                ),
                why=(
                    "the document's own legend defines closure as 'closed **with a "
                    "reference** (sha / record / gate output)': without a pointer, closure "
                    "is a designation, not a verifiable property"
                ),
                how=_how_explain(doc_path, node_id),
                locations=(_where(doc_path, claim),),
            )
        )
    return findings


def _rule_sha_on_trunk(
    doc_path: Path,
    node_id: str,
    claims: list[StateClaim],
    reachability: CommitReachabilityPort,
    trunk_ref: str,
) -> list[Finding]:
    findings: list[Finding] = []
    checked: set[str] = set()
    for claim in claims:
        for sha in claim.shas:
            if sha in checked:
                continue
            checked.add(sha)
            answer = reachability.reachable_from(sha, trunk_ref)
            if answer.outcome is Reachability.REACHABLE:
                continue
            if answer.outcome is Reachability.NOT_REACHABLE:
                findings.append(
                    Finding(
                        rule="closure-sha-not-on-trunk",
                        node_id=node_id,
                        severity=Severity.REJECT,
                        what=(
                            f"`{node_id}` is closed on `{sha[:9]}`, which is not an ancestor "
                            f"of `{trunk_ref}` — {answer.detail}"
                        ),
                        why=(
                            "a node closed on work that is not in the product is open: the "
                            "commit may live on an abandoned branch or never got merged"
                        ),
                        how=_how_explain(doc_path, node_id),
                        locations=(_where(doc_path, claim),),
                    )
                )
            else:
                findings.append(
                    Finding(
                        rule="closure-sha-unverifiable",
                        node_id=node_id,
                        severity=Severity.UNVERIFIABLE,
                        what=(
                            f"the position of `{sha[:9]}` relative to `{trunk_ref}` is not "
                            f"decidable — {answer.detail}"
                        ),
                        why=(
                            "without an answer this node is neither coherent nor incoherent: "
                            "treating it as coherent would be a silent pass"
                        ),
                        how=_how_explain(doc_path, node_id),
                        locations=(_where(doc_path, claim),),
                    )
                )
    return findings


def _how_find_carrier(doc_path: Path, node_id: str) -> str:
    script = Path(__file__).resolve()
    try:
        rendered = script.relative_to(Path.cwd())
    except ValueError:
        rendered = script
    return f"python3 {rendered} --file {doc_path} --find-carrier {node_id}"


def _named_path_never_touched(
    doc_path: Path,
    node_id: str,
    claim: StateClaim,
    missing: list[str],
    product: list[str],
) -> Finding:
    touched = ", ".join(f"`{p}`" for p in product[:3])
    return Finding(
        rule="closure-names-a-path-the-commit-never-touched",
        node_id=node_id,
        severity=Severity.REJECT,
        what=(
            f"`{node_id}` closes on {', '.join(f'`{s[:9]}`' for s in claim.shas)} and "
            f"its note names {', '.join(f'`{n}`' for n in missing)}, which no cited "
            f"commit rewrote — they rewrote {touched}"
        ),
        why=(
            "the commit carries product work, so the bookkeeping-only check passes — "
            "and it is still not the work the note names. Accepting SOME work for THE "
            "named work decides on the DESIGNATION (a diff is non-empty) instead of "
            "the PROPERTY (the diff contains what was claimed)"
        ),
        how=_how_find_carrier(doc_path, node_id),
        locations=(_where(doc_path, claim),),
    )


def _subcommand_unevidenced(
    doc_path: Path,
    node_id: str,
    claim: StateClaim,
    named: tuple[str, ...],
    product: list[str],
) -> Finding:
    touched = ", ".join(f"`{p}`" for p in product[:3])
    return Finding(
        rule="closure-names-a-subcommand-no-path-evidences",
        node_id=node_id,
        severity=Severity.ADVISORY,
        what=(
            f"`{node_id}` names {', '.join(f'`{n}`' for n in named)} and no path the "
            f"cited commits rewrote evidences it — they rewrote {touched}"
        ),
        why=(
            "a subcommand is matched by name fragments, and a subcommand can ship in "
            "a file named nothing like it, so an absent match is too weak to block; "
            "it is never counted as carrying the claim either"
        ),
        how=_how_find_carrier(doc_path, node_id),
        locations=(_where(doc_path, claim),),
    )


def _rule_closure_does_not_carry(
    doc_path: Path,
    node_id: str,
    claims: list[StateClaim],
    contents: CommitContentsPort,
    coverage: _CarryCoverage,
) -> list[Finding]:
    """The sha exists AND is on trunk -- but does it carry what the note claims?

    Falsifiable conjunction only: the note NAMES an artifact, and the cited
    commits rewrote nothing outside the plan's own bookkeeping documentation.
    Everything softer than that is counted, not asserted.

    "Rewrote SOME product file" is itself a designation: it answers a question
    the note never asked. A named PATH is inspectable exactly -- absent from the
    changed set, the note is false, and that rejects. A named `des` subcommand
    is matched by heuristic fragments (`des next` ships in
    `deliver_loop_projection.py`), so an absent match there is a weaker signal:
    it is reported and it never counts as carried, but it does not block.
    """
    findings: list[Finding] = []
    already: set[tuple[str, str]] = set()
    for claim in claims:
        if claim.closure is not ClosureClass.CLOSED or not claim.shas:
            continue
        signature = (node_id, claim.reference.strip())
        if signature in already:
            continue
        already.add(signature)
        coverage.closures += 1

        named = artifact_claims(claim.reference)
        if not named:
            coverage.unfalsifiable += 1
            continue

        changed: set[str] = set()
        undecidable: list[str] = []
        for sha in claim.shas:
            answer = contents.changed_paths(sha)
            if answer.is_available:
                changed |= set(answer.paths)
            else:
                undecidable.append(answer.detail)

        product = sorted(p for p in changed if not is_bookkeeping_path(p))
        if product:
            evidenced = {
                token: [
                    p for p in product if any(f in p for f in path_fragments_for(token))
                ]
                for token in named
            }
            missing_paths = [
                t for t in named if not t.startswith("des ") and not evidenced[t]
            ]
            if missing_paths:
                coverage.not_carried += 1
                findings.append(
                    _named_path_never_touched(
                        doc_path, node_id, claim, missing_paths, product
                    )
                )
                continue
            if any(evidenced.values()):
                coverage.carried += 1
                continue
            coverage.unmatched += 1
            findings.append(
                _subcommand_unevidenced(doc_path, node_id, claim, named, product)
            )
            continue
        if undecidable:
            coverage.undecidable += 1
            findings.append(
                Finding(
                    rule="closure-carry-unverifiable",
                    node_id=node_id,
                    severity=Severity.UNVERIFIABLE,
                    what=(
                        f"`{node_id}` names the artifact {', '.join(f'`{n}`' for n in named)} "
                        f"in its closure note, and what the cited commit rewrote cannot be "
                        f"read — {undecidable[0]}"
                    ),
                    why=(
                        "without the changed-path set this closure is neither carried nor "
                        "empty: calling it coherent would be the silent pass this rule "
                        "exists to prevent"
                    ),
                    how=_how_find_carrier(doc_path, node_id),
                    locations=(_where(doc_path, claim),),
                )
            )
            continue

        coverage.not_carried += 1
        touched = ", ".join(f"`{p}`" for p in sorted(changed)[:3]) or "nothing"
        findings.append(
            Finding(
                rule="closure-sha-does-not-carry-the-claim",
                node_id=node_id,
                severity=Severity.REJECT,
                what=(
                    f"`{node_id}` closes on {', '.join(f'`{s[:9]}`' for s in claim.shas)} "
                    f"and its note names {', '.join(f'`{n}`' for n in named)}, but those "
                    f"commits rewrote only bookkeeping documentation ({touched})"
                ),
                why=(
                    "the pointer resolves and sits on trunk, so every earlier check passes "
                    "— and the commit still does not carry the work the node declares. "
                    "Closure was decided on the DESIGNATION (a sha exists) instead of the "
                    "PROPERTY (the sha carries the work)"
                ),
                how=_how_find_carrier(doc_path, node_id),
                locations=(_where(doc_path, claim),),
            )
        )
    return findings


def _rule_unknown_state(
    doc_path: Path, node_id: str, claims: list[StateClaim]
) -> list[Finding]:
    findings: list[Finding] = []
    for claim in claims:
        if claim.closure is not ClosureClass.UNKNOWN:
            continue
        findings.append(
            Finding(
                rule="state-not-in-vocabulary",
                node_id=node_id,
                severity=Severity.UNVERIFIABLE,
                what=(
                    f"`{node_id}` carries the state `{normalize_state(claim.raw_state)}` in "
                    f"{claim.carrier}, which is not in the legend"
                ),
                why=(
                    "a state outside the vocabulary cannot be classified as closed or open: "
                    "the gate cannot decide and must not pretend it did"
                ),
                how=_how_explain(doc_path, node_id),
                locations=(_where(doc_path, claim),),
            )
        )
    return findings


def _rule_lane_join_ambiguous(
    doc_path: Path, ambiguities: list[_LaneAmbiguity]
) -> list[Finding]:
    findings: list[Finding] = []
    for amb in ambiguities:
        findings.append(
            Finding(
                rule="lane-closure-join-ambiguous",
                node_id=amb.base,
                severity=Severity.UNVERIFIABLE,
                what=(
                    f"the CORSIA row `{amb.lane}` declares {normalize_state(amb.raw_state)} "
                    f"for `{amb.base}`, which matches {len(amb.candidates)} real nodes "
                    f"({', '.join(amb.candidates)}) and none of them exactly"
                ),
                why=(
                    "joining to one of them would be a guess: an ambiguous closure claim "
                    "is neither coherent nor incoherent until the row names the exact node"
                ),
                how=(
                    f"name the exact node in the CORSIA row at {doc_path}:{amb.line} "
                    f"(e.g. `nodo {amb.candidates[0]}`) instead of the shared base "
                    f"`{amb.base}`"
                ),
                locations=(f"{doc_path}:{amb.line} ({CARRIER_LANES})",),
            )
        )
    return findings


def _rule_completion_word(
    doc_path: Path,
    tree_nodes: list[_TreeNode],
    claims_by_node: dict[str, list[StateClaim]],
) -> list[Finding]:
    """The re-calibrated predictor: a completion word with no pointer next to it.

    An INFERRED signal, never a declared fact, so it can only warn.
    """
    findings: list[Finding] = []
    for node in tree_nodes:
        node_claims = claims_by_node.get(node.node_id, [])
        if any(claim.is_attested for claim in node_claims):
            continue
        haystack = " ".join(node.prose).lower()
        hit = next((word for word in COMPLETION_LEXICON if word in haystack), None)
        if hit is None:
            continue
        findings.append(
            Finding(
                rule="completion-word-without-pointer",
                node_id=node.node_id,
                severity=Severity.ADVISORY,
                what=(
                    f"`{node.node_id}` describes the work as «{hit}» but no carrier "
                    "carries a closure pointer"
                ),
                why=(
                    "a completion word with no pointer next to it has predicted a wrong "
                    "state 3 times out of 3; it is an INFERRED signal, so it warns and "
                    "does not block"
                ),
                how=_how_explain(doc_path, node.node_id),
                locations=(f"{doc_path}:{node.line} ({CARRIER_TREE})",),
            )
        )
    return findings


#: The two REFUSED causes `mikado_closure_ledger.RefusalCause` can name,
#: rendered as distinguishable WHAT-clause prose (orchestrator's own
#: constraint, f-mikado-node-closure-record slice-02: "citazione a un
#: commit irraggiungibile e citazione a un commit che non porta il path
#: dichiarato sono due cause DISTINTE dello stesso REFUSED -- distinguibili
#: nell'output, non collassate"). Never a new Finding.rule/Severity --
#: `ledger-closure-refused` stays the ONE rule name (Reuse Analysis: "zero
#: new Finding/Severity vocabulary"), the distinction lives in this text.
_REFUSAL_CAUSE_TEXT = {
    RefusalCause.SHA_NOT_REACHABLE: "the cited commit is not reachable from trunk at all",
    RefusalCause.PATH_NOT_CARRIED: (
        "the cited commit is reachable but did not rewrite the cited path"
    ),
}


def _ledger_closure_refused_finding(
    doc_path: Path, node_id: str, cause: RefusalCause | None
) -> Finding:
    """`ledger-closure-refused` (ADR-D70 D70-6): REJECT, unconditional,
    never ratcheted -- mirrors `_rule_carrier_contradiction`'s own severity
    exactly. Prose reads a CLOSED-class state AND the ledger's independent
    re-verification reads REFUSED: an actively false closure claim."""
    cause_text = _REFUSAL_CAUSE_TEXT.get(
        cause, "the ledger's independent re-verification contradicts it"
    )
    return Finding(
        rule="ledger-closure-refused",
        node_id=node_id,
        severity=Severity.REJECT,
        what=(
            f"`{node_id}` is closed in {CARRIER_NODES}, and the MIKADO ledger's "
            f"independent re-verification of its closure record is REFUSED -- "
            f"{cause_text}"
        ),
        why=(
            "a false closure claim is worse than silence: this is an actively "
            "contradicted record, not merely an unattested one, so it blocks "
            "absolutely and is never ratcheted (mirrors carrier-contradiction's "
            "own severity, ADR-D70 D70-6) -- write a NEW, correctly-citing "
            "closure record via `des mikado-attest-node-closure`; the ledger "
            "is append-only, so a later verifying record supersedes this false "
            "one for read purposes rather than editing history"
        ),
        how=_how_explain(doc_path, node_id),
        locations=(str(doc_path),),
    )


def _ledger_closure_unattested_finding(
    doc_path: Path, node_id: str, ledger_state: NodeState
) -> Finding:
    """`ledger-closure-unattested` (ADR-D70 D70-6): ADVISORY, unconditional,
    NEVER blocking, no ratchet (reviewed and declined -- `gate_ratchet.py`'s
    baseline precondition does not hold for a non-git-tracked ledger).
    Prose reads CLOSED AND the ledger reads OPEN or COULD_NOT_DETERMINE: an
    honest gap the forward-only convention does not retrofit."""
    return Finding(
        rule="ledger-closure-unattested",
        node_id=node_id,
        severity=Severity.ADVISORY,
        what=(
            f"`{node_id}` is closed in {CARRIER_NODES}, and the MIKADO ledger "
            f"carries no verified closure record for it (ledger reads "
            f"{ledger_state.value})"
        ),
        why=(
            "forward-only convention (ADR-D70 D70-6): the historical, "
            "non-retrofitted backlog is never held hostage -- this is "
            "printed, named, and counted every run, and never blocks the "
            "commit. Run `des mikado-attest-node-closure` to attest this "
            "node going forward, purely advisory, never required to unblock"
        ),
        how=_how_explain(doc_path, node_id),
        locations=(str(doc_path),),
    )


def check_ledger_closure_reconciliation(
    doc_path: Path,
    states: dict[str, ClosureClass],
    *,
    ledger_root: Path | None,
    reachability: CommitReachabilityPort,
    contents: CommitContentsPort,
    trunk_ref: str,
) -> list[Finding]:
    """The fourth carrier (ADR-D70 D70-6): for every node whose RESOLVED
    prose state is CLOSED, reconcile against the MIKADO ledger's own
    independent re-verification (`mikado_closure_ledger.evaluate_node`).

    `ledger_root is None` (no repo root supplied to this gate invocation,
    e.g. a caller exercising only the three prose carriers) degrades to
    `NodeState.COULD_NOT_DETERMINE` for every CLOSED node -- never a silent
    skip (GDP-6): the sibling ADVISORY finding still fires, it simply never
    escalates to REJECT, exactly the weakest-honest-answer discipline this
    file already applies to an absent `contents` port (`UnavailableContents`).
    """
    findings: list[Finding] = []
    for node_id, klass in sorted(states.items()):
        if klass is not ClosureClass.CLOSED:
            continue
        if ledger_root is None:
            ledger_state = NodeState.COULD_NOT_DETERMINE
        else:
            ledger_state = evaluate_node(
                node_id,
                project_root=ledger_root,
                reachability=reachability,
                contents=contents,
                trunk_ref=trunk_ref,
            )
        if ledger_state is NodeState.CLOSED:
            continue
        if ledger_state is NodeState.REFUSED:
            cause = (
                node_refusal_cause(
                    node_id,
                    project_root=ledger_root,
                    reachability=reachability,
                    contents=contents,
                    trunk_ref=trunk_ref,
                )
                if ledger_root is not None
                else None
            )
            findings.append(_ledger_closure_refused_finding(doc_path, node_id, cause))
            continue
        # OPEN or COULD_NOT_DETERMINE
        findings.append(
            _ledger_closure_unattested_finding(doc_path, node_id, ledger_state)
        )
    return findings


# ---------------------------------------------------------------------------
# gate
# ---------------------------------------------------------------------------


#: The dependency graph lives in the consolidated register's ``dipende-da``
#: column -- the same source the board generator reads. Kept here rather than
#: imported so the gate stays a single file with Python as its only dependency.
_DECISIONS_REL = "2026-07-28-decisions-consolidated.md"
_DEP_ROW_RE = re.compile(r"^\| (D\d+) \|")
_DEP_ID_RE = re.compile(r"\bD\d+\b")
#: The cell declares this node depends on NOTHING. Any id after it is prose.
_DEP_NONE_RE = re.compile(r"\bNONE\b|\bnessun[ao]?\b", re.IGNORECASE)
#: Phrases under which a neighbouring id is NOT something this node waits for.
#: `X e' prerequisito di D44` says D44 waits for X -- the opposite edge. Reading
#: the id and ignoring the phrase inverts the arrow.
_DEP_INVERSE_RE = re.compile(
    r"prerequisit\w*\s+(?:di|per)|precede|distint\w+\s+da|non\s+avviare|"
    r"beneficia|contende|si\s+toccherebbero",
    re.IGNORECASE,
)


def read_dependency_edges(
    doc_path: Path,
) -> tuple[dict[str, set[str]], dict[str, str]]:
    """``(edges, undecidable)`` from the register's ``dipende-da`` column.

    ``edges`` maps a node to the set it WAITS FOR, and carries only cells whose
    declaration is unambiguous -- ids, or nothing. ``undecidable`` maps a node
    to why its cell could not be turned into edges.

    The previous reader took every ``D\\d+`` token in the cell as a dependency.
    That decides on the DESIGNATION (an id appears) rather than the PROPERTY
    (this cell declares a wait), and the register's prose says the opposite at
    least as often as it agrees: ``NONE -- e' prerequisito di D44`` became "waits
    for D44" when it means D44 waits for this node; ``NON avviare insieme a
    D22`` -- an anti-affinity -- became a dependency. Twelve of eighty rows
    manufactured edges this way, and the phantom arrows closed cycles that hid
    five real nodes from every view built on this graph.
    """
    return read_dependency_register(doc_path.parent / _DECISIONS_REL)


def read_dependency_register(
    register: Path,
) -> tuple[dict[str, set[str]], dict[str, str]]:
    """``read_dependency_edges`` against an explicit register path.

    The board renders from the same register, and calls this directly so the
    two cannot drift into disagreeing about what the graph is.
    """
    try:
        text = register.read_text(encoding="utf-8")
    except OSError:
        return {}, {}
    edges: dict[str, set[str]] = {}
    undecidable: dict[str, str] = {}
    for line in text.split("\n"):
        if _DEP_ROW_RE.match(line) is None:
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) <= 7:
            continue
        node = _DEP_ROW_RE.match(line).group(1)  # type: ignore[union-attr]
        cell = cells[7]
        named = {d for d in _DEP_ID_RE.findall(cell) if d != node}
        says_none = bool(_DEP_NONE_RE.search(cell))
        inverse = bool(_DEP_INVERSE_RE.search(cell))
        if not named:
            edges[node] = set()
        elif says_none or inverse:
            # The cell names ids AND says they are not what it waits for (or
            # says it waits for nothing at all). Which of the two the author
            # meant is not mechanically decidable: record it, invent nothing.
            undecidable[node] = (
                f"names {', '.join(sorted(named))} inside a cell that "
                + ("declares NONE" if says_none else "states the inverse relation")
                + f": {cell[:70]}"
            )
        else:
            edges[node] = named
    return edges, undecidable


def check_closed_over_open_child(
    doc_path: Path, states: dict[str, ClosureClass]
) -> list[Finding]:
    """A parent cannot be closed while a node it WAITS FOR is still open.

    Ale 2026-07-29, looking at D48 closed above an open D03b: "una
    precondizione per poter chiudere un nodo padre e' assicurarsi che tutti i
    nodi figli siano chiusi". The parent's own work being finished is not
    sufficient -- the tree's whole purpose is that a node's value is only real
    once what it stands on is real too. Decides on the PROPERTY (is the child
    in a closed state) and never on the parent's own designation.

    A base id split into sub-slices is waited for THROUGH its sub-slices, the
    same resolution the board generator applies, so ``D31`` resolves to
    ``D31a``/``D31b`` and a missing literal id is never read as a missing node.
    """
    findings: list[Finding] = []
    edges, undecidable = read_dependency_edges(doc_path)
    if not edges and not undecidable:
        return findings
    for node, reason in sorted(undecidable.items()):
        if states.get(node) is not ClosureClass.CLOSED:
            continue
        findings.append(
            Finding(
                rule="closure-prerequisites-undecidable",
                node_id=node,
                severity=Severity.UNVERIFIABLE,
                what=(f"`{node}` is closed and its `dipende-da` cell {reason}"),
                why=(
                    "whether this node still waits for those ids cannot be decided from "
                    "the cell, so the closure is neither sound nor unsound: inventing "
                    "the edge is how five nodes ended up hidden behind phantom cycles"
                ),
                how=(
                    f"rewrite the `dipende-da` cell of `{node}` in "
                    f"{doc_path.parent / _DECISIONS_REL} as ids only (`D47 + D03`) or "
                    "`NONE`, and put the prose in a neighbouring column"
                ),
                locations=(str(doc_path.parent / _DECISIONS_REL),),
            )
        )
    for node, klass in sorted(states.items()):
        if klass is not ClosureClass.CLOSED:
            continue
        # `_base_id` is case-insensitive on the suffix; a bare `[ab]$` strip is
        # not, and every node id reaches this map already uppercased -- so
        # `D03B` never resolved as a sub-slice of `D03` and every dependency on
        # a split node silently found nothing to wait for.
        base = _base_id(node)
        waited: set[str] = set()
        for dep in edges.get(base, set()):
            subs = [s for s in states if _base_id(s) == dep and s != dep]
            waited.update(subs or ([dep] if dep in states else []))
        open_children = sorted(
            c for c in waited - {node} if states.get(c) is not ClosureClass.CLOSED
        )
        if not open_children:
            continue
        findings.append(
            Finding(
                rule="closed-over-open-child",
                node_id=node,
                severity=Severity.REJECT,
                what=(
                    f"`{node}` is closed while it still waits for "
                    + ", ".join(f"`{c}`" for c in open_children)
                ),
                why=(
                    "a parent stands on the nodes it waits for: closing it while one "
                    "of them is open reports finished work whose foundation does not "
                    "exist yet, which is the overstatement the board exists to prevent"
                ),
                how=_how_explain(doc_path, node),
                locations=(),
            )
        )
    return findings


def check_node_visible_from_a_root(
    doc_path: Path, states: dict[str, ClosureClass]
) -> list[Finding]:
    """A node the tables list but no view can reach is present-and-invisible.

    Every view of this tree is rendered by walking down from the roots -- the
    nodes nobody waits for. A node that no root reaches is in the tables and in
    nobody's field of view: real work, invisible to the person reading the map.
    Catalogued is not wired, applied to the map instead of to the code.

    Unreachability is never a free-standing fact: a detached but acyclic
    subgraph has a root of its own and is therefore reachable. So a node is
    unreachable only when a CYCLE sits above it, and this rule names the cycle
    rather than the symptom -- a Mikado tree is a DAG by definition, and "A
    cannot start before B, B cannot start before A" is unschedulable work.
    """
    edges, _ = read_dependency_edges(doc_path)
    if not edges or not states:
        return []

    deps: dict[str, set[str]] = {}
    for node in states:
        resolved: set[str] = set()
        for dep in edges.get(_base_id(node), set()):
            subs = [s for s in states if _base_id(s) == dep and s != dep]
            resolved.update(subs or ([dep] if dep in states else []))
        deps[node] = resolved - {node}

    waited_for = {d for ds in deps.values() for d in ds}
    roots = sorted(n for n in deps if n not in waited_for)
    seen: set[str] = set()
    stack = list(roots)
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(deps.get(node, set()))
    unreachable = sorted(set(states) - seen)
    if not unreachable:
        return []

    cycles = _cycles_among(deps, unreachable)
    findings: list[Finding] = []
    for cycle in cycles:
        findings.append(
            Finding(
                rule="dependency-cycle-hides-nodes",
                node_id=cycle[0],
                severity=Severity.REJECT,
                what=(
                    "the dependency graph closes a cycle over "
                    + " -> ".join(f"`{c}`" for c in [*cycle, cycle[0]])
                    + ": no root reaches these nodes, so no view of the tree shows them"
                ),
                why=(
                    "a Mikado tree is a DAG -- a cycle says each of these cannot start "
                    "before the other, which is unschedulable, and the renderer walks "
                    "down from the roots so it drops them in silence instead of saying so"
                ),
                how=(
                    f"break the cycle in {doc_path.parent / _DECISIONS_REL}: exactly "
                    f"one of {' / '.join(cycle)} must stop declaring the other in its "
                    f"`dipende-da` cell, then re-run {_how_report(doc_path)}"
                ),
                locations=(str(doc_path.parent / _DECISIONS_REL),),
            )
        )
    in_a_cycle = {n for cycle in cycles for n in cycle}
    for node in unreachable:
        if node in in_a_cycle:
            continue
        findings.append(
            Finding(
                rule="node-unreachable-from-every-root",
                node_id=node,
                severity=Severity.REJECT,
                what=(
                    f"`{node}` is listed in the tables but no root of the dependency "
                    "graph reaches it, so no rendered view of the tree shows it"
                ),
                why=(
                    "a node present in the register and absent from every view is work "
                    "nobody can see to schedule: present-and-invisible, which is how "
                    "D27 stayed out of the board"
                ),
                how=_how_explain(doc_path, node),
                locations=(str(doc_path.parent / _DECISIONS_REL),),
            )
        )
    return findings


def _cycles_among(deps: dict[str, set[str]], candidates: list[str]) -> list[list[str]]:
    """Strongly connected components of size > 1 among ``candidates``."""
    pool = set(candidates)
    found: list[list[str]] = []
    unassigned = set(pool)
    while unassigned:
        start = min(unassigned)
        # forward closure
        fwd: set[str] = set()
        stack = [start]
        while stack:
            n = stack.pop()
            if n in fwd:
                continue
            fwd.add(n)
            stack.extend(d for d in deps.get(n, set()) if d in pool)
        # backward closure
        back: set[str] = set()
        stack = [start]
        while stack:
            n = stack.pop()
            if n in back:
                continue
            back.add(n)
            stack.extend(m for m in pool if n in deps.get(m, set()))
        component = fwd & back
        unassigned -= component or {start}
        if len(component) > 1:
            found.append(sorted(component))
    return found


def check_tree_coherence(
    doc_path: Path,
    *,
    reachability: CommitReachabilityPort,
    trunk_ref: str = DEFAULT_TRUNK_REF,
    contents: CommitContentsPort | None = None,
    ledger_root: Path | None = None,
) -> GateReport:
    if contents is None:
        contents = UnavailableContents(
            "no commit-contents port supplied: what each closure sha rewrote was "
            "not read"
        )
    carry = _CarryCoverage()
    lines = doc_path.read_text(encoding="utf-8").splitlines()
    sections = _split_sections(lines)

    claims: list[StateClaim] = []
    tree_nodes: list[_TreeNode] = []
    lane_ambiguities: list[_LaneAmbiguity] = []

    # The tree and the node table are parsed first: their node ids are the real
    # population a CORSIA row's closure claim must join against -- decided on
    # after the fact, never assumed while reading the lane.
    tree_section = _find_section(sections, CARRIER_TREE)
    if tree_section is not None:
        tree_nodes = parse_tree_nodes(tree_section)
        claims += parse_tree_claims(tree_nodes)
    node_section = _find_section(sections, CARRIER_NODES)
    known_node_ids = frozenset(n.node_id for n in tree_nodes)
    if node_section is not None:
        claims += parse_node_table_claims(node_section)
        known_node_ids |= node_table_ids(node_section)

    lane_section = _find_section(sections, CARRIER_LANES)
    if lane_section is not None:
        lane_claims, lane_ambiguities = parse_lane_claims(lane_section, known_node_ids)
        claims += lane_claims

    claims_by_node: dict[str, list[StateClaim]] = {}
    for claim in claims:
        claims_by_node.setdefault(claim.node_id, []).append(claim)

    carriers_seen = tuple(
        c for c in CANONICAL_CARRIERS if any(x.carrier == c for x in claims)
    )

    findings: list[Finding] = []

    # The checker is not exempt from the class it checks: an empty population is
    # a failure, never a green.
    if len(claims_by_node) == 0 or len(carriers_seen) < 2:
        findings.append(
            Finding(
                rule="population-floor",
                node_id="(no node)",
                severity=Severity.REJECT,
                what=(
                    f"insufficient population: {len(claims_by_node)} nodes over "
                    f"{len(carriers_seen)} carriers ({', '.join(carriers_seen) or 'none'})"
                ),
                why=(
                    "with fewer than two carriers there is nothing to reconcile: a green "
                    "here would be green-by-absence-of-cases, exactly how a checker "
                    "self-invalidates"
                ),
                how=_how_report(doc_path),
                locations=(str(doc_path),),
            )
        )

    findings += _rule_state_typed_outside_its_carrier(doc_path, tree_nodes)

    for node_id in sorted(claims_by_node):
        node_claims = claims_by_node[node_id]
        findings += _rule_carrier_contradiction(doc_path, node_id, node_claims)
        findings += _rule_quarantine_split(doc_path, node_id, node_claims)
        findings += _rule_closed_without_reference(doc_path, node_id, node_claims)
        findings += _rule_unknown_state(doc_path, node_id, node_claims)
        findings += _rule_sha_on_trunk(
            doc_path, node_id, node_claims, reachability, trunk_ref
        )
        findings += _rule_closure_does_not_carry(
            doc_path, node_id, node_claims, contents, carry
        )

    findings += _rule_completion_word(doc_path, tree_nodes, claims_by_node)
    findings += _rule_lane_join_ambiguous(doc_path, lane_ambiguities)
    node_states = resolve_fusions(
        {
            nid: (
                ClosureClass.CLOSED
                if any(c.closure is ClosureClass.CLOSED for c in cs)
                else ClosureClass.OPEN
            )
            for nid, cs in claims_by_node.items()
        },
        {
            nid: next((t for t in (fusion_target(c.raw_state) for c in cs) if t), None)
            for nid, cs in claims_by_node.items()
        },
    )
    findings += check_closed_over_open_child(doc_path, node_states)
    findings += check_node_visible_from_a_root(doc_path, node_states)
    findings += check_ledger_closure_reconciliation(
        doc_path,
        node_states,
        ledger_root=ledger_root,
        reachability=reachability,
        contents=contents,
        trunk_ref=trunk_ref,
    )

    if any(f.severity is Severity.REJECT for f in findings):
        verdict = Verdict.INCOHERENT
    elif any(f.severity is Severity.UNVERIFIABLE for f in findings):
        verdict = Verdict.UNVERIFIABLE
    else:
        verdict = Verdict.COHERENT

    return GateReport(
        verdict=verdict,
        findings=tuple(findings),
        nodes_examined=len(claims_by_node),
        carriers_seen=carriers_seen,
        claims=tuple(claims),
        carry=carry,
    )


# ---------------------------------------------------------------------------
# the ratchet: decide the EXIT CODE on the delta, never on the absolute count
# ---------------------------------------------------------------------------


def third_state_keys(report: GateReport) -> tuple[str, ...]:
    """One identity per could-not-verify finding: the complaint and its subject.

    ``(rule, node)`` and not the rendered text: the text carries a sha prefix
    and a path list, so an author who merely reworded a closure note would read
    as having introduced a brand new unverifiable claim.
    """
    return tuple(
        f"{f.rule} · {f.node_id}" for f in report.by_severity(Severity.UNVERIFIABLE)
    )


def baseline_findings(
    doc_path: Path,
    *,
    repo: Path,
    reachability: CommitReachabilityPort,
    contents: CommitContentsPort,
    trunk_ref: str,
) -> tuple[tuple[str, ...] | None, str]:
    """This gate's third-state population over the SAME paths as HEAD holds them.

    ``(keys, provenance)`` when the previous state could be measured, and
    ``(None, reason)`` when it could not -- which the caller must treat as a
    refusal, never as permission.

    RECOMPUTED, never stored. A count kept in a file is an artifact an author
    can edit to buy a pass; worse, it is measured in a PAST environment, and the
    incident this ratchet exists for is precisely an environmental change with
    the document held constant -- a stored count from before the repack would
    have read 0 and blocked all 88 findings, reproducing the hostage it was
    meant to release. Recomputing here, in this process, against this object
    store, is what makes the delta attributable to the AUTHOR's edit: whatever
    the environment is doing, it is doing it to both measurements equally.

    The same port instances are reused, so the second pass inherits the first
    pass's decoded-commit cache instead of re-inflating the same ancestors.
    """
    root = locate_worktree_root(repo)
    if root is None:
        return None, f"`{repo}` is not a checkout, so it records no previous state"
    try:
        rel_doc = doc_path.resolve().relative_to(root)
    except ValueError:
        return None, (
            f"`{doc_path}` is not inside the checkout `{root}`, so that checkout "
            "records no previous version of it"
        )
    head = getattr(reachability, "resolve_head", lambda: None)()
    if head is None:
        return None, f"HEAD does not resolve in `{root}`"

    #: The register is an INPUT to this gate as much as the document is -- the
    #: dependency rules read it -- so the baseline must be measured against its
    #: HEAD version too. Reading today's register beside yesterday's document
    #: would attribute the difference between them to the author's edit.
    rel_register = rel_doc.parent / _DECISIONS_REL
    provenance = [f"HEAD `{head[:9]}`"]
    materialize: list[tuple[Path, bytes]] = []

    doc_blob = contents.blob_at(head, rel_doc.as_posix())
    if doc_blob.outcome is BlobOutcome.INDETERMINATE:
        return (
            None,
            f"the previous version of `{rel_doc}` is unreadable: {doc_blob.detail}",
        )
    if doc_blob.outcome is BlobOutcome.ABSENT:
        return (), (
            f"HEAD `{head[:9]}` does not record `{rel_doc}` at all, so this "
            "document is new and every finding in it is introduced here"
        )
    assert doc_blob.data is not None  # PRESENT, by the two branches above
    materialize.append((rel_doc, doc_blob.data))
    provenance.append(
        f"`{rel_doc}` = blob `{doc_blob.oid[:9] if doc_blob.oid else '?'}`"
    )

    register_blob = contents.blob_at(head, rel_register.as_posix())
    if register_blob.outcome is BlobOutcome.INDETERMINATE:
        return None, (
            f"the previous version of `{rel_register}` is unreadable: "
            f"{register_blob.detail}"
        )
    if register_blob.outcome is BlobOutcome.PRESENT:
        assert register_blob.data is not None
        materialize.append((rel_register, register_blob.data))
        provenance.append(
            f"`{rel_register}` = blob "
            f"`{register_blob.oid[:9] if register_blob.oid else '?'}`"
        )

    with tempfile.TemporaryDirectory(prefix="mikado-baseline-") as staging:
        stage = Path(staging)
        for rel, data in materialize:
            target = stage / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        previous = check_tree_coherence(
            stage / rel_doc,
            reachability=reachability,
            trunk_ref=trunk_ref,
            contents=contents,
        )
    return third_state_keys(previous), " · ".join(provenance) + (
        f" (check it: git rev-parse {head[:9]}:{rel_doc})"
    )


def ratchet_decision(
    report: GateReport,
    doc_path: Path,
    *,
    repo: Path,
    reachability: CommitReachabilityPort,
    contents: CommitContentsPort,
    trunk_ref: str,
) -> RatchetDecision:
    current = third_state_keys(report)
    baseline, note = baseline_findings(
        doc_path,
        repo=repo,
        reachability=reachability,
        contents=contents,
        trunk_ref=trunk_ref,
    )
    if baseline is None:
        return undecidable_baseline(current, note)
    decision = decide_ratchet(current, baseline, note)
    if not decision.introduced:
        return decision
    # Route the refusal at the FIRST claim it actually names, through this
    # gate's own affordance -- the operator should not have to work out which of
    # the printed findings is the new one, nor how to interrogate it.
    first_node = decision.introduced[0][0].rsplit(" · ", 1)[-1]
    return replace(decision, how=_how_explain(doc_path, first_node))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _explain(report: GateReport, node_id: str, doc_path: Path) -> None:
    wanted = node_id.upper()
    claims = [c for c in report.claims if c.node_id.upper() == wanted]
    if claims:
        wanted = claims[0].node_id
    print(f"NODE {wanted} — {len(claims)} claims in document {doc_path}")
    if not claims:
        print("  no carrier names this node.")
        return
    for claim in sorted(claims, key=lambda c: c.line):
        pointer = claim.reference.strip() or "(empty)"
        print(
            f"  {claim.carrier:<22} line {claim.line:>4}  state="
            f"{normalize_state(claim.raw_state):<14} reference={pointer}"
        )
        for sha in claim.shas:
            print(f"      sha cited: {sha}")
    print("\n  The claims above must agree. Fix the carrier that is wrong,")
    print("  or fill the closure reference with the sha actually on trunk.")
    for finding in report.findings:
        if finding.node_id.upper() == wanted.upper():
            print()
            print(finding.render())


def _find_carrier(
    report: GateReport,
    node_id: str,
    contents: CommitContentsPort,
    trunk_ref: str,
    search_depth: int,
) -> int:
    """Name the commits that DID rewrite what a node's closure note claims.

    The repair for a closure that does not carry its claim is a different sha,
    and finding it by hand is exactly the manual work a HOW must not ask for.
    """
    wanted = node_id.upper()
    claims = [c for c in report.claims if c.node_id.upper() == wanted]
    named: list[str] = []
    for claim in claims:
        for token in artifact_claims(claim.reference):
            if token not in named:
                named.append(token)
    print(f"NODE {wanted} — artifacts named in its closure notes: {named or 'none'}")
    if not named:
        print(
            "  Nothing to search for: the note names no source path and no `des` "
            "subcommand,\n  so no commit can be shown to carry it. Name the artifact "
            "in the closure note first."
        )
        return 2
    if not hasattr(contents, "recent_commits"):
        print("  the commit-contents port cannot walk history: no candidates")
        return 2

    fragments = {t: path_fragments_for(t) for t in named}
    walked, complete = contents.recent_commits(trunk_ref, search_depth)  # type: ignore[attr-defined]
    hits: dict[str, list[tuple[str, str]]] = {t: [] for t in named}
    for sha in walked:
        answer = contents.changed_paths(sha)
        if not answer.is_available:
            continue
        for token, frags in fragments.items():
            # A bookkeeping path never evidences delivery, so it is never a
            # candidate carrier -- the same rule the gate itself decides on.
            matched = [
                p
                for p in answer.paths
                if any(f in p for f in frags) and not is_bookkeeping_path(p)
            ]
            if matched:
                hits[token].append((sha, matched[0]))

    found_any = False
    for token in named:
        print(f"\n  `{token}`")
        if not hits[token]:
            print(
                f"    no commit among the {len(walked)} walked from `{trunk_ref}` "
                "rewrote a matching path"
            )
            continue
        found_any = True
        for sha, path in hits[token][:5]:
            print(f"    {sha[:9]}  rewrote {path}")
    print(
        f"\n  walked {len(walked)} commits from `{trunk_ref}`"
        + ("" if complete else " (walk truncated: older commits not searched)")
    )
    if found_any:
        print("  Put the sha that carries the work in the closure reference cell.")
    return 0 if found_any else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--file", required=True, type=Path, help="Mikado execution SSOT"
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=None,
        help="checkout used to resolve commit ancestry (default: the document's own)",
    )
    parser.add_argument("--trunk-ref", default=DEFAULT_TRUNK_REF)
    parser.add_argument(
        "--explain", default=None, help="print every claim for one node"
    )
    parser.add_argument(
        "--find-carrier",
        default=None,
        metavar="NODE",
        help="name the commits that rewrote the artifact a node's closure note claims",
    )
    parser.add_argument(
        "--search-depth",
        type=int,
        default=600,
        help="commits to walk back from trunk when searching for a carrier",
    )
    args = parser.parse_args(argv)

    if not args.file.is_file():
        print(f"file not found: {args.file}", file=sys.stderr)
        return 2

    repo = args.repo or args.file.resolve().parent
    contents = build_contents(repo)
    reachability = build_reachability(repo)
    # The MIKADO ledger lives at `.nwave/telemetry/mikado/` under the repo's
    # OWN root, joined literally by `telemetry_paths.ledger_path` (no
    # upward walk) -- so, unlike `reachability`/`contents` (which walk up
    # from `repo` themselves via `locate_git_dirs`), the fourth carrier
    # needs the resolved worktree root explicitly, not `repo` as given
    # (`repo` defaults to the DOCUMENT's own directory, e.g. `docs/mikado/`,
    # not the checkout root).
    report = check_tree_coherence(
        args.file,
        reachability=reachability,
        trunk_ref=args.trunk_ref,
        contents=contents,
        ledger_root=locate_worktree_root(repo) or repo,
    )

    if args.explain:
        _explain(report, args.explain, args.file)
        return 0

    if args.find_carrier:
        return _find_carrier(
            report, args.find_carrier, contents, args.trunk_ref, args.search_depth
        )

    print(f"VERDICT {report.verdict.value}")
    print(
        f"  {report.nodes_examined} nodes · carriers: "
        f"{', '.join(report.carriers_seen) or 'none'} · trunk `{args.trunk_ref}`"
    )
    if report.carry is not None:
        print(report.carry.render())
    for severity in (Severity.REJECT, Severity.UNVERIFIABLE, Severity.ADVISORY):
        group = report.by_severity(severity)
        if not group:
            continue
        print(f"\n--- {severity.value} ({len(group)}) ---")
        for finding in group:
            print(finding.render())
            print()

    exit_code = {Verdict.COHERENT: 0, Verdict.INCOHERENT: 1, Verdict.UNVERIFIABLE: 2}[
        report.verdict
    ]

    # The ratchet is reached ONLY on the third state -- which by construction
    # means at least one unverifiable finding and NOT ONE reject. So a coherent
    # document pays nothing for it (not a line of output, not a second pass over
    # history), and a document carrying a real incoherence never sees an
    # allowance printed beside its rejection.
    if report.verdict is Verdict.UNVERIFIABLE:
        decision = ratchet_decision(
            report,
            args.file,
            repo=repo,
            reachability=reachability,
            contents=contents,
            trunk_ref=args.trunk_ref,
        )
        print()
        print(decision.render())
        if not decision.blocks:
            exit_code = 0
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
