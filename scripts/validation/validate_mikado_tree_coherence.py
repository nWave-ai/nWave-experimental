#!/usr/bin/env python3
"""Tree-coherence gate for a Mikado execution SSOT.

One node's state is written down in three places in the same document -- the
lane table (`## CORSIE`), the mindmap (`## L'ALBERO`) and the per-node tables
(`## STATO NODO PER NODO`). Nothing compared them, so a node could read
INTEGRATA with a sha in one carrier and PRONTO with an empty closure reference
in another, at the same time.

This gate decides on the PROPERTY -- *is there attested evidence of closure?* --
never on the DESIGNATION -- *the row says PRONTO*. It answers with three states
and never collapses the third into the first.

Only dependency: Python. Commit ancestry is read straight off ``.git/`` through
a port that degrades LOUD when the object store cannot answer.

Usage:
    python3 scripts/validation/validate_mikado_tree_coherence.py --file DOC
    python3 scripts/validation/validate_mikado_tree_coherence.py --file DOC --explain D22

Exit codes:
    0: COHERENT
    1: INCOHERENT -- at least one node carries contradictory or unattested state
    2: NOT_VERIFIABLE -- a check could not be decided; never collapsed into 0
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from git_commit_reachability import (
    CommitReachabilityPort,
    Reachability,
    build_reachability,
)


DEFAULT_TRUNK_REF = "feature/atdd-pure-staging"

CARRIER_LANES = "CORSIE"
CARRIER_TREE = "L'ALBERO"
CARRIER_NODES = "STATO NODO PER NODO"
CANONICAL_CARRIERS = (CARRIER_LANES, CARRIER_TREE, CARRIER_NODES)

#: The document's own legend: FATTO means "chiuso **con riferimento**". CHIUSO/CHIUSA
#: are the document's other closure designation (closed-without-work, e.g. a refuted
#: premise) -- the orchestrator's own prose treats them as closed for open/closed
#: purposes (`## IL GATE ... DESIGNAZIONE`: "le otto righe sono corrette FATTO/CHIUSO").
CLOSED_STATES = frozenset({"FATTO", "INTEGRATA", "INTEGRATE", "CHIUSO", "CHIUSA"})
OPEN_STATES = frozenset(
    {"PRONTO", "IN CORSO", "QUARANTENA", "CONTESO", "NON_MISURATO", "SOSPESO"}
)
NOT_WORK_STATES = frozenset({"GUARDIA", "—", "–", "-", ""})

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


@dataclass(frozen=True)
class GateReport:
    verdict: Verdict
    findings: tuple[Finding, ...]
    nodes_examined: int
    carriers_seen: tuple[str, ...]
    claims: tuple[StateClaim, ...] = ()

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
    return ClosureClass.UNKNOWN


def _state_token_in(text: str) -> str | None:
    """Find a declared state word inside a free-form cell, longest first."""
    upper = text.upper()
    known = sorted(CLOSED_STATES | OPEN_STATES | {"GUARDIA"}, key=len, reverse=True)
    for word in known:
        if re.search(rf"\b{re.escape(word)}\b", upper):
            return word
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


# ---------------------------------------------------------------------------
# gate
# ---------------------------------------------------------------------------


def check_tree_coherence(
    doc_path: Path,
    *,
    reachability: CommitReachabilityPort,
    trunk_ref: str = DEFAULT_TRUNK_REF,
) -> GateReport:
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

    for node_id in sorted(claims_by_node):
        node_claims = claims_by_node[node_id]
        findings += _rule_carrier_contradiction(doc_path, node_id, node_claims)
        findings += _rule_quarantine_split(doc_path, node_id, node_claims)
        findings += _rule_closed_without_reference(doc_path, node_id, node_claims)
        findings += _rule_unknown_state(doc_path, node_id, node_claims)
        findings += _rule_sha_on_trunk(
            doc_path, node_id, node_claims, reachability, trunk_ref
        )

    findings += _rule_completion_word(doc_path, tree_nodes, claims_by_node)
    findings += _rule_lane_join_ambiguous(doc_path, lane_ambiguities)

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
    )


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
    args = parser.parse_args(argv)

    if not args.file.is_file():
        print(f"file not found: {args.file}", file=sys.stderr)
        return 2

    repo = args.repo or args.file.resolve().parent
    report = check_tree_coherence(
        args.file,
        reachability=build_reachability(repo),
        trunk_ref=args.trunk_ref,
    )

    if args.explain:
        _explain(report, args.explain, args.file)
        return 0

    print(f"VERDICT {report.verdict.value}")
    print(
        f"  {report.nodes_examined} nodes · carriers: "
        f"{', '.join(report.carriers_seen) or 'none'} · trunk `{args.trunk_ref}`"
    )
    for severity in (Severity.REJECT, Severity.UNVERIFIABLE, Severity.ADVISORY):
        group = report.by_severity(severity)
        if not group:
            continue
        print(f"\n--- {severity.value} ({len(group)}) ---")
        for finding in group:
            print(finding.render())
            print()
    return {Verdict.COHERENT: 0, Verdict.INCOHERENT: 1, Verdict.UNVERIFIABLE: 2}[
        report.verdict
    ]


if __name__ == "__main__":
    sys.exit(main())
