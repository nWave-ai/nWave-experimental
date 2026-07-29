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
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from git_commit_contents import (
    CommitContentsPort,
    UnavailableContents,
    build_contents,
)
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
    unfalsifiable: int = 0

    @property
    def evaluable(self) -> int:
        return self.carried + self.not_carried

    def render(self) -> str:
        return (
            f"  carry-check · {self.closures} attested closures · "
            f"{self.evaluable} decided ({self.carried} carry the claim, "
            f"{self.not_carried} do not) · {self.undecidable} undecidable · "
            f"{self.unfalsifiable} unfalsifiable (the note names no artifact)\n"
            "  cannot catch: a note that names an artifact the commit did touch but "
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


def _how_find_carrier(doc_path: Path, node_id: str) -> str:
    script = Path(__file__).resolve()
    try:
        rendered = script.relative_to(Path.cwd())
    except ValueError:
        rendered = script
    return f"python3 {rendered} --file {doc_path} --find-carrier {node_id}"


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
            coverage.carried += 1
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


# ---------------------------------------------------------------------------
# gate
# ---------------------------------------------------------------------------


#: The dependency graph lives in the consolidated register's ``dipende-da``
#: column -- the same source the board generator reads. Kept here rather than
#: imported so the gate stays a single file with Python as its only dependency.
_DECISIONS_REL = "2026-07-28-decisions-consolidated.md"
_DEP_ROW_RE = re.compile(r"^\| (D\d+) \|")
_DEP_ID_RE = re.compile(r"\bD\d+\b")


def read_dependency_edges(doc_path: Path) -> dict[str, set[str]]:
    """node id -> the set of node ids it WAITS FOR. Empty when unreadable."""
    register = doc_path.parent / _DECISIONS_REL
    try:
        text = register.read_text(encoding="utf-8")
    except OSError:
        return {}
    edges: dict[str, set[str]] = {}
    for line in text.split("\n"):
        if _DEP_ROW_RE.match(line) is None:
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) <= 7:
            continue
        node = _DEP_ROW_RE.match(line).group(1)  # type: ignore[union-attr]
        edges[node] = {d for d in _DEP_ID_RE.findall(cells[7]) if d != node}
    return edges


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
    edges = read_dependency_edges(doc_path)
    if not edges:
        return findings
    for node, klass in sorted(states.items()):
        if klass is not ClosureClass.CLOSED:
            continue
        base = re.sub(r"[ab]$", "", node)
        waited: set[str] = set()
        for dep in edges.get(base, set()):
            subs = [s for s in states if re.sub(r"[ab]$", "", s) == dep and s != dep]
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


def check_tree_coherence(
    doc_path: Path,
    *,
    reachability: CommitReachabilityPort,
    trunk_ref: str = DEFAULT_TRUNK_REF,
    contents: CommitContentsPort | None = None,
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
    node_states = {
        nid: (
            ClosureClass.CLOSED
            if any(c.closure is ClosureClass.CLOSED for c in cs)
            else ClosureClass.OPEN
        )
        for nid, cs in claims_by_node.items()
    }
    findings += check_closed_over_open_child(doc_path, node_states)

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
    report = check_tree_coherence(
        args.file,
        reachability=build_reachability(repo),
        trunk_ref=args.trunk_ref,
        contents=contents,
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
    return {Verdict.COHERENT: 0, Verdict.INCOHERENT: 1, Verdict.UNVERIFIABLE: 2}[
        report.verdict
    ]


if __name__ == "__main__":
    sys.exit(main())
