"""Render the Mikado tree as a DEPENDENCY tree, with every node's state.

One rendering, no prose. Leaves are the nodes that depend on nothing --
those are what you implement FIRST; a parent sits above the nodes it waits
for. That is the Mikado shape: you walk to the deepest leaf and work back up.

Two sources, joined:
  * `docs/mikado/2026-07-28-decisions-consolidated.md` -- the `dipende-da`
    column IS the dependency graph.
  * `docs/mikado/EXECUTION-SSOT-des-optimization.md` -- the per-node state
    table is the state.

Both are read, never restated, so the tree cannot drift from them. A node the
state table does not carry is rendered `?` rather than silently dropped:
absent state is a fact about the join, not a node that stopped existing.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Iterable


BEGIN = "<!-- MIKADO-BOARD:BEGIN -->"
END = "<!-- MIKADO-BOARD:END -->"

#: Node id anywhere in a `dipende-da` cell. Sub-slices (`D03a`) inherit the
#: base node's edges -- the graph is authored on base ids.
_DEP_RE = re.compile(r"\bD\d+\b")
_DECISION_ROW_RE = re.compile(r"^\| (D\d+) \|")
_STATE_ROW_RE = re.compile(r"^\| `([DV]\d+[ab]?)` \|")

#: State -> (glyph, rank). Rank orders siblings so what is workable floats up.
#: `FUSO IN <target>` is authored generically, not as one hard-coded target: the
#: glyph a fusion earns depends on the node it fused INTO, which `_glyph` resolves.
#: Words that CLOSE a node. Each also spawns a `<word>-SOSPESO` reading -- work
#: finished, closure suspended above an open node -- generated rather than typed so
#: the board can never know a closing word the suspended form forgot.
CLOSING_WORDS = ("FATTO", "CHIUSO", "CHIUSA", "MISURATO", "INTEGRATA", "INTEGRATE")
STATE_GLYPH = {
    **{f"{word}-SOSPESO": ("[s]", 2) for word in CLOSING_WORDS},
    "FATTO": ("[x]", 9),
    "CHIUSO": ("[-]", 9),
    "CHIUSA": ("[-]", 9),
    "MISURATO": ("[m]", 9),
    "INTEGRATA": ("[x]", 9),
    "INTEGRATE": ("[x]", 9),
    "FUSO IN": ("[>]", 9),
    "GUARDIA": ("[G]", 9),
    "AL LAVORO": ("[~]", 0),
    "PRONTO": ("[ ]", 1),
    "CONTESO": ("[!]", 2),
    "BLOCCATO-SERVE-DESIGN": ("[D]", 3),
    "QUARANTENA": ("[Q]", 4),
    "NON_MISURATO": ("[Q]", 4),
    "SOSPESO": ("[s]", 2),
    "RAMO": ("[+]", 6),
}
#: `[s]` -- work finished, closure suspended -- is deliberately NOT here. A
#: suspended closure that rendered as closed would be the same overstatement the
#: tree gate rejects, printed in a colour instead of a word.
CLOSED_GLYPHS = {"[x]", "[-]", "[m]", "[>]", "[G]"}
#: A fusion that resolved to its OPEN target: still a deferral, drawn as one.
_FUSED_OPEN = ("[>~]", 3)

#: Glyph -> CSS class, so colour carries the same meaning as in the document
#: rendering rather than a second, private vocabulary.
#: Longest title rendered inline on a tree row; the rest moves to detail.
_TITLE_MAX = 64

_CSS_CLASS = {
    "[x]": "done",
    "[-]": "done",
    "[m]": "done",
    "[>]": "done",
    "[G]": "guard",
    "[ ]": "ready",
    "[~]": "wip",
    "[!]": "cont",
    "[D]": "dsn",
    "[Q]": "quar",
    "[+]": "guard",
    "[?]": "guard",
    "[s]": "susp",
    "[>~]": "susp",
}

#: Defect-register states mapped onto the node-state vocabulary.
_DEFECT_STATE = {
    "RIPARATO": "FATTO",
    "IN CORSIA": "AL LAVORO",
    "APERTO": "PRONTO",
    "SERVE DESIGN": "BLOCCATO-SERVE-DESIGN",
}


#: `FUSO IN <target>` -- the node id whose state this fusion carries.
_FUSED_INTO = re.compile(r"^FUSO\s+IN\s+([A-Z]{1,2}\d{1,3}[A-Za-z]?)\b", re.IGNORECASE)
#: How deep a chain of fusions is walked before it is called a ring.
_FUSION_HOPS = 8


def _glyph(
    state: str, states: dict[str, tuple[str, str]] | None = None
) -> tuple[str, int]:
    """State -> (glyph, rank), matching the LONGEST state word first.

    Longest-first, not insertion order: `FATTO-SOSPESO` starts with `FATTO`, so a
    first-key-wins scan would have drawn a suspended closure as a finished one --
    the overstatement this vocabulary exists to prevent, reintroduced by dict order.

    A `FUSO IN X` state carries X's state rather than one of its own, so it is
    resolved against `states` when the caller has the map. Fused into an open node
    it has closed nothing and must not draw as closed; with no map, no chain end, or
    a ring, it stays open -- the safe direction.
    """
    fused = _FUSED_INTO.match(state.strip())
    if fused is not None:
        if states is None:
            return _FUSED_OPEN
        target, seen = fused.group(1).upper(), {""}
        for _ in range(_FUSION_HOPS):
            if target in seen or target not in states:
                return _FUSED_OPEN
            seen.add(target)
            hop = _FUSED_INTO.match(states[target][0].strip())
            if hop is None:
                inner, _rank = _glyph(states[target][0])
                return STATE_GLYPH["FUSO IN"] if inner in CLOSED_GLYPHS else _FUSED_OPEN
            target = hop.group(1).upper()
        return _FUSED_OPEN
    for key in sorted(STATE_GLYPH, key=len, reverse=True):
        if state.startswith(key):
            return STATE_GLYPH[key]
    return ("[?]", 5)


def read_states(path: Path) -> dict[str, tuple[str, str]]:
    """node id -> (state, title), from the per-node state table."""
    states: dict[str, tuple[str, str]] = {}
    for line in path.read_text(encoding="utf-8").split("\n"):
        match = _STATE_ROW_RE.match(line)
        if not match:
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) > 5:
            states[match.group(1)] = (cells[5], cells[2])
    return states


_DEFECT_ROW_RE = re.compile(r"^\| (F\d+) \| (.*?) \| (.*?) \| \*\*(.*?)\*\*")

#: A defect that BLOCKS a tree node hangs under it; the rest are leaves of
#: their own branch. Authored here because the register is prose, not a graph.
DEFECT_PARENT = {"F12": "V15"}

#: The branch a lane's work has to land on before the lane is finished.
_TRUNK = "feature/atdd-pure-staging"


def lane_node(
    branch: str, known_ids: Iterable[str]
) -> tuple[str | None, tuple[str, ...]]:
    """Which node a BRANCH DECLARES it works on -> (node, ambiguous group).

    The declaration is read out of the branch NAME -- `lane/d27-design` works
    D27, `lane/d25a-deadtests` works D25a -- and out of nothing else. That is
    the point: a derived reading cannot go stale, because renaming the branch
    moves the reading with it and deleting the branch deletes it.

    This replaced a hand-kept `LANE_NODES` dict, which did not merely risk rot
    but had already rotted through. `lane/codex-recover` carried four real
    unmerged commits of codex-host-parity work, so the liveness half of the
    probe fired correctly and forced D37/D38/D34/D35 to `AL LAVORO` -- four
    nodes whose topics that branch has never touched. Measured while repairing
    it, all 17 surviving entries were dead: not one named a branch that still
    had unmerged work, while two lanes that did -- `lane/d64-remeasure-and-
    reconcile` and `lane/d95-examine-gate` -- were invisible to it. Every live
    reading it produced was false and every true one was missing. D97's row
    already names it as the fourth state carrier, Python-resident and therefore
    invisible to the gate that guards the other three.

    Prose that MENTIONS a branch was weighed as a second carrier and refused:
    D92's row names `lane/codex-recover` as a branch to PROTECT from removal,
    and reading a mention as "this lane works this node" would rebuild the same
    bug on a different substrate. A mention is a DESIGNATION; a name that
    declares its node is the PROPERTY.

    Three outcomes, never two. A candidate resolving to exactly one real node is
    that node. A candidate whose base is shared by several suffixed nodes
    (`lane/d03` against D03a and D03b) comes back as the AMBIGUOUS group and
    overrides nothing -- picking one is how a board states a falsehood
    confidently. A name that is not node-shaped, or is shaped like an id no node
    carries (`bugfix/c1-...`, `spike/qw5-...`), declares no node at all: most
    branches are not lane work, and silence is the correct reading for them
    rather than a degradation.
    """
    # The coherence gate's own lane -> node join, borrowed whole: it already had
    # to answer this exact question for `## CORSIE` rows, ambiguity discipline
    # included (`lane-closure-join-ambiguous`). A second regex here would be a
    # second contract, free to drift from the one the gate enforces.
    sys.path.insert(0, str(Path(__file__).resolve().parent / "validation"))
    from validate_mikado_tree_coherence import (
        lane_id_candidate,
        resolve_node_reference,
    )

    candidate = lane_id_candidate(branch.rsplit("/", 1)[-1])
    if candidate is None:
        return None, ()
    # The gate's join works on uppercased ids; this document spells a sub-slice
    # with a lowercase suffix (`D03b`). Fold for the lookup, then hand back the
    # id as the document actually writes it -- a case-normalised near-miss would
    # match no row and silently override nothing.
    by_upper = {node.upper(): node for node in known_ids}
    resolved, group = resolve_node_reference(candidate, frozenset(by_upper))
    if resolved is not None:
        return by_upper[resolved], ()
    return None, tuple(by_upper[member] for member in group)


def live_nodes(
    repo: Path, known_ids: Iterable[str]
) -> tuple[set[str], list[tuple[str, tuple[str, ...]]]]:
    """(nodes a live lane works on, ambiguous joins) -- read entirely from git.

    A lane is LIVE when its worktree still exists AND its branch still carries
    work trunk does not have. BOTH halves are required, and for a long time only
    the first was checked. Worktree-exists alone is a DESIGNATION ("somebody
    opened a directory"), not the PROPERTY ("there is unlanded work here"): a
    lane that finished and was merged keeps its worktree until someone prunes
    it, so 17 of 18 branches then listed were fully merged (`ahead=0`) while
    this function still forced their nodes to `AL LAVORO`. That override WON
    over the register, which is how the board once rendered `D03b` as `AL
    LAVORO` on top of a row saying `BLOCCATO-SERVE-DESIGN`.

    WHICH node a live branch works on is `lane_node`'s question, and it is asked
    FIRST: the join is pure and cheap, the liveness probe is a git call per
    branch, and there is no reason to spend one on a branch that declares no
    node at all. The old order could not do this -- it started from the list of
    branches it already believed in, which is precisely what made it blind to
    every lane the list had never heard of.

    A branch that cannot be resolved is NOT silently treated as merged: an
    unreadable ref means "cannot tell", and the safe direction for a state
    override is to leave the register's own word standing.
    """
    import subprocess

    def _git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            # stdin closed and a wall-clock bound: a read-only probe must never
            # inherit a terminal or hang the render.
            stdin=subprocess.DEVNULL,
            timeout=10,
        )

    try:
        listing = _git("worktree", "list", "--porcelain").stdout
    except (OSError, subprocess.SubprocessError):
        return set(), []
    present = sorted(
        line.split("refs/heads/", 1)[1].strip()
        for line in listing.split("\n")
        if line.startswith("branch refs/heads/")
    )
    out: set[str] = set()
    ambiguous: list[tuple[str, tuple[str, ...]]] = []
    for branch in present:
        node, group = lane_node(branch, known_ids)
        if node is None and not group:
            continue
        try:
            ahead = _git("rev-list", "--count", f"{_TRUNK}..{branch}")
        except (OSError, subprocess.SubprocessError):
            continue
        # rc != 0 -> the ref or trunk did not resolve. Undecidable, so no
        # override: never invent "live", never invent "merged".
        if ahead.returncode != 0 or not ahead.stdout.strip().isdigit():
            continue
        if int(ahead.stdout.strip()) == 0:
            continue
        # Only a LIVE ambiguity is worth a word. A merged branch whose name
        # names no single node overrides nothing either way, and reporting it
        # would bury the one case a reader has to act on.
        if node is None:
            ambiguous.append((branch, group))
        else:
            out.add(node)
    return out, ambiguous


def read_defects(path: Path) -> dict[str, tuple[str, str, str]]:
    """defect id -> (state, title, parent-or-empty), from the defect register."""
    out: dict[str, tuple[str, str, str]] = {}
    for line in path.read_text(encoding="utf-8").split("\n"):
        match = _DEFECT_ROW_RE.match(line)
        if match:
            fid, title, _cls, state = match.groups()
            out[fid] = (state.strip(), title.strip(), DEFECT_PARENT.get(fid, ""))
    return out


def read_edges(path: Path) -> dict[str, set[str]]:
    """node id -> the set of nodes it WAITS FOR.

    Delegates to the coherence gate's reader, so the board and the gate cannot
    disagree about the graph they both render decisions from. That reader
    refuses to turn a `dipende-da` cell which says NONE, or which states the
    inverse relation, into edges: reading every `D\\d+` token in the cell as a
    dependency inverted 12 of 80 rows and closed phantom cycles that kept D27,
    D20, D44, D21 and D33 out of this very board.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent / "validation"))
    from validate_mikado_tree_coherence import read_dependency_register

    edges, _undecidable = read_dependency_register(path)
    return edges


#: The summary line, authored ONCE. The pattern that reads a PREVIOUS summary
#: back out of the document is DERIVED from this same template, so the renderer
#: and the parser cannot drift apart: reword the line and the parser follows by
#: construction. A hand-kept second copy of the pattern is exactly how a parser
#: ends up silently matching nothing while the renderer keeps working fine --
#: and a parser that matches nothing would report every render as a first one.
_SUMMARY_TEMPLATE = (
    "**{nodes} nodi · {closed} chiusi · {open} aperti, "
    "di cui {free} senza dipendenze aperte.**"
)
_SUMMARY_FIELDS = ("nodes", "closed", "open", "free")


def _summary_re() -> re.Pattern[str]:
    """The template with its count slots turned into capture groups."""
    pattern = re.escape(_SUMMARY_TEMPLATE)
    for field in _SUMMARY_FIELDS:
        pattern = pattern.replace(re.escape("{" + field + "}"), r"(\d+)")
    return re.compile(pattern)


_SUMMARY_RE = _summary_re()

#: Three readings of "what did the board say last time", never two.
PREV_PRESENT, PREV_ABSENT, PREV_UNREADABLE = "present", "absent", "unreadable"

#: What the delta sentence calls the clock, so a reader cannot take it for the
#: tree's last change: it is the moment this RENDER ran, nothing else.
_RENDER_PREFIX = "Reso (ora del RENDERING, non dell'ultima modifica all'albero)"
_COUNT_LABELS = ("nodi", "chiusi", "aperti", "schedulabili")

#: Populations the total has always MIXED. Applied as a PARTITION, never a
#: filter: every id lands in exactly one bucket, so the buckets sum to the total
#: by construction and an id class nobody has labelled yet surfaces as `altri`
#: instead of silently inflating `decisioni`. Rendered in this order, so the page
#: reads the same way run to run.
_SYNTHETIC_ROOT = "DIFETTI"
_POPULATION_ORDER = (
    "decisioni",
    "difetti, foglie che non bloccano l'albero",
    "radice sintetica, iniettata solo per disegnare l'albero",
    "altri, classe di id non etichettata",
)


def _population_of(node: str) -> str:
    """Which population an id belongs to.

    Keyed on the id NAMESPACE, which is what this document's ids actually mean --
    and the fallback bucket is why that is safe: an id shape this function does
    not know is NAMED as unlabelled rather than absorbed into a class it was
    never checked against.
    """
    if node == _SYNTHETIC_ROOT:
        return _POPULATION_ORDER[2]
    if re.fullmatch(r"F\d+", node):
        return _POPULATION_ORDER[1]
    if re.fullmatch(r"[DV]\d+[ab]?", node, flags=re.IGNORECASE):
        return _POPULATION_ORDER[0]
    return _POPULATION_ORDER[3]


def composition(states: dict[str, tuple[str, str]]) -> list[tuple[str, int]]:
    """The total, broken into the populations it mixes -- largest classes first.

    The board quoted one sum for months while that sum blended decision nodes,
    defect-register leaves the tree itself calls "foglie, non bloccano l'albero",
    and one synthetic root injected purely to draw the tree. A reader could not
    see the mix from the sum, which is the same defect as the missing delta: a
    number whose population is invisible.
    """
    tally: dict[str, int] = {}
    for node in states:
        label = _population_of(node)
        tally[label] = tally.get(label, 0) + 1
    return [(lab, tally[lab]) for lab in _POPULATION_ORDER if lab in tally]


def counts_of(
    states: dict[str, tuple[str, str]], deps: dict[str, set[str]]
) -> tuple[int, int, int, int]:
    """(nodi, chiusi, aperti, schedulabili) -- computed ONCE for BOTH surfaces.

    The markdown block and the HTML page must never disagree about the four
    numbers, and the only way to guarantee that is to have one computation rather
    than two that happen to match today. Before this existed the HTML carried
    three of the four (it silently dropped `schedulabili`), which is exactly the
    drift a shared computation makes impossible.
    """
    open_nodes = [
        n for n, (s, _) in states.items() if _glyph(s, states)[0] not in CLOSED_GLYPHS
    ]
    free = [
        n
        for n in open_nodes
        if not any(
            _glyph(states.get(d, ("?", ""))[0], states)[0] not in CLOSED_GLYPHS
            for d in deps.get(n, ())
        )
    ]
    return (len(states), len(states) - len(open_nodes), len(open_nodes), len(free))


def now_stamp() -> str:
    """The render clock, read ONCE per run so both surfaces carry one stamp."""
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d %H:%M")


def read_previous_summary(text: str) -> tuple[str, tuple[int, int, int, int] | None]:
    """What did the board say LAST time? -> (status, counts).

    The baseline is DERIVED from the very document this render is about to
    overwrite -- never kept in a state file. A stored count was measured in a
    past environment and cannot be trusted against the present one, and a
    counter nobody ever diffs against reality rots in silence; the document, by
    contrast, is read in the same process that recomputes the new numbers.

    Three outcomes, which is why this returns a STATUS rather than an Optional:
    a document with no previous line (`absent`) is a different fact from a
    previous line the parser cannot read (`unreadable`). Collapsing either onto
    zeros would print a delta of 0 -- a confident claim that nothing changed,
    made from no evidence at all. GDP-6: degrade LOUD, never silently-wrong.
    """
    if BEGIN not in text or END not in text:
        return PREV_ABSENT, None
    block = text.split(BEGIN, 1)[1].split(END, 1)[0]
    # The summary sits AFTER the tree's closing fence. Anchoring on that
    # structural landmark, rather than on the word "nodi", keeps a NODE TITLE
    # that happens to contain the word from being read as a summary line.
    tail = block.rsplit("```", 1)[-1] if "```" in block else block
    match = _SUMMARY_RE.search(tail)
    if match:
        nodes, closed, open_, free = (int(group) for group in match.groups())
        return PREV_PRESENT, (nodes, closed, open_, free)
    # Something occupies the summary's slot but does not parse -- say so.
    return (PREV_UNREADABLE, None) if tail.strip() else (PREV_ABSENT, None)


def _signed(delta: int) -> str:
    """`+2` / `0` / `-2` -- the sign is ALWAYS carried for a non-zero delta.

    Never absolute-valued and never rendered with a bare `+`: a DECREASE in
    `chiusi` is the single most informative reading this line carries, because
    it means a closure claim was WITHDRAWN rather than that work regressed.
    Hiding its direction would bury the one number a reader must not miss.
    """
    return f"{delta:+d}" if delta else "0"


def _delta_sentence(
    rendered_at: str,
    current: tuple[int, int, int, int],
    previous: tuple[str, tuple[int, int, int, int] | None],
) -> str:
    """When this ran, what it said before, what moved -- with NO markup.

    Markup-free on purpose: the markdown block italicises it and the HTML page
    escapes it into a paragraph, but the WORDS are authored here once. Two
    surfaces formatting one sentence cannot disagree about the delta; two
    surfaces each composing their own sentence would drift, and a delta that
    contradicts itself across surfaces is worse than one surface without a delta.
    """
    status, prev = previous
    head = f"{_RENDER_PREFIX} {rendered_at}"
    if status == PREV_UNREADABLE:
        return (
            f"{head} · precedente: ILLEGGIBILE — una riga di sintesi "
            "c'e', ma non e' interpretabile, quindi NESSUN delta e' calcolabile."
        )
    if prev is None:
        return (
            f"{head} · precedente: NESSUNO (primo rendering di questo "
            "blocco) — nessun delta calcolabile."
        )
    # `strict` on every pairing: a counts tuple that ever loses a field must
    # RAISE, not quietly render a line that is short one number.
    was = " · ".join(f"{v} {lab}" for v, lab in zip(prev, _COUNT_LABELS, strict=True))
    deltas = [now - before for now, before in zip(current, prev, strict=True)]
    moved = [
        f"{_signed(d)} {lab}" for d, lab in zip(deltas, _COUNT_LABELS, strict=True)
    ]
    if deltas[1] < 0:
        moved[1] += f" ({abs(deltas[1])} chiusure RITIRATE)"
    return f"{head} · precedente {was} → Δ {' · '.join(moved)}."


_ONDA_RE = re.compile(r"^### ONDA (\d+)")
_SHA_RE = re.compile(r"`([0-9a-f]{7,40})`")


def _extract_sha(text: str) -> str:
    """The first backtick-quoted hash in a closure-reference cell, if any."""
    match = _SHA_RE.search(text)
    return match.group(1) if match else ""


def read_node_meta(path: Path) -> dict[str, tuple[str, str, str]]:
    """node id -> (effort, wave, closure sha), read from the SAME per-node
    state table `read_states` reads. Effort and the closure reference sit in
    their own columns of that table; the wave is the nearest `### ONDA N`
    heading above the row -- it is not a column, it is the section a row
    lives in.
    """
    meta: dict[str, tuple[str, str, str]] = {}
    wave = ""
    for line in path.read_text(encoding="utf-8").split("\n"):
        onda = _ONDA_RE.match(line)
        if onda:
            wave = f"onda {onda.group(1)}"
            continue
        match = _STATE_ROW_RE.match(line)
        if not match:
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) > 9:
            meta[match.group(1)] = (cells[4], wave, _extract_sha(cells[9]))
    return meta


def build(
    states: dict[str, tuple[str, str]], edges: dict[str, set[str]]
) -> tuple[dict[str, set[str]], list[str]]:
    """Resolve sub-slices onto the graph and return (deps, roots)."""
    deps: dict[str, set[str]] = {}
    for node in states:
        base = re.sub(r"[ab]$", "", node, flags=re.IGNORECASE)
        resolved: set[str] = set()
        for dep in edges.get(base, set()):
            # A base id with sub-slices is waited for through its sub-slices.
            subs = [
                s
                for s in states
                if re.sub(r"[ab]$", "", s, flags=re.IGNORECASE) == dep and s != dep
            ]
            resolved.update(subs or ([dep] if dep in states else []))
        deps[node] = resolved - {node}
    waited_for = {d for ds in deps.values() for d in ds}
    roots = sorted(n for n in deps if n not in waited_for)
    return deps, roots


def render(
    states: dict[str, tuple[str, str]],
    deps: dict[str, set[str]],
    roots: list[str],
    rendered_at: str | None = None,
    previous: tuple[str, tuple[int, int, int, int] | None] | None = None,
) -> str:
    """The board block. `previous` is the reading this render replaces.

    Both extras default to the honest no-information case -- no previous reading
    at all -- so a caller that knows nothing about the document gets a line
    saying exactly that, never a fabricated zero delta.
    """
    rendered_at = rendered_at or now_stamp()
    previous = previous or (PREV_ABSENT, None)
    lines = [
        BEGIN,
        "## ▶ ALBERO MIKADO — dipendenze, stato di ogni nodo",
        "",
        "**GENERATO**: `uv run python scripts/mikado_board.py --write`.",
        "**Le FOGLIE non dipendono da nulla: si implementano per PRIME.**",
        "Un padre sta sopra i nodi che aspetta.",
        "",
        "`[ ]` pronto · `[~]` al lavoro · `[!]` serve una riga di Ale · "
        "`[D]` serve DESIGN · `[Q]` serve una misura · "
        "`[x]` fatto · `[-]` chiuso · `[m]` misurato · `[>]` fuso · `[?]` stato assente",
        "",
        "```",
    ]

    # A node is expanded ONCE, at its first occurrence. Every later appearance
    # is a one-line pointer -- a shared dependency is ONE node, not many, and
    # re-printing its subtree would both make the shape unreadable and
    # overstate how much work is left.
    expanded: set[str] = set()

    def walk(node: str, depth: int) -> None:
        state, title = states.get(node, ("?", ""))
        glyph, _ = _glyph(state, states)
        pad = "    " * depth
        if node in expanded:
            lines.append(f"{pad}{glyph} {node:5} \u2192 gia' mostrato sopra")
            return
        expanded.add(node)
        mark = "" if glyph in CLOSED_GLYPHS else f"  \u2190 {state}"
        lines.append(f"{pad}{glyph} {node:5} {title[:52]}{mark}".rstrip())
        children = sorted(
            deps.get(node, ()),
            key=lambda c: (_glyph(states.get(c, ("?", ""))[0], states)[1], c),
        )
        for child in children:
            walk(child, depth + 1)

    for root in sorted(
        roots, key=lambda r: (_glyph(states.get(r, ("?", ""))[0], states)[1], r)
    ):
        walk(root, 0)
    lines.append("```")

    # The SAME four numbers the summary has always carried, from the ONE
    # computation the HTML page also uses -- so the two surfaces cannot disagree.
    current = counts_of(states, deps)
    lines += [
        "",
        _SUMMARY_TEMPLATE.format(**dict(zip(_SUMMARY_FIELDS, current, strict=True))),
        f"*{_delta_sentence(rendered_at, current, previous)}*",
        END,
    ]
    return "\n".join(lines)


#: The stylesheet is IMPORTED from the document renderer, never copied. One
#: stylesheet for two projections of the same file: a copy would drift, and the
#: whole point is that a colour means the same thing in both views.
def _doc_css() -> str:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.render_doc_html import _CSS

    return _CSS


_PAGE = """<title>Albero Mikado \u2014 ottimizzazione DES</title>
<style>__CSS__
/* The one axis the document renderer has no reason to carry: a REPEATED node,
   rendered as a link back to the single expansion that owns the description. */
li.t-ref>.t-name{color:var(--muted);font-style:italic}
li.t-ref>a.t-id{text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:2px}
/* A node WITHOUT a description is a plain row, aligned with the ones that have
   a disclosure marker so the column of ids stays straight. */
.t-row{display:inline-block;padding:.16rem 0}
li.t-has-detail>details>summary::before{content:"\u203a";font-size:.85rem}
li.t-has-detail>details[open]>summary::before{content:"\u2304";font-size:.7rem}
.wrap{max-width:none}
/* --- hide-done toggle -------------------------------------------------
   A closed node's OWN row disappears; its children never do. `display:
   contents` drops only the <li>'s box, leaving its DOM children (a sibling
   <ul class="tree"> of open work, if any) rendered exactly where the parent
   used to be -- a re-parent upward with zero JS and zero restructuring. A
   `.t-ref` backlink has no children to preserve, so it just goes away. */
.toolbar{position:sticky;top:0;z-index:20;background:var(--paper);
  border-bottom:1px solid var(--rule);padding:.55rem 0;margin-bottom:.3rem}
.toolbar label{display:inline-flex;align-items:center;gap:.45rem;
  font-size:.85rem;color:var(--ink);cursor:pointer;user-select:none}
.toolbar input{width:1rem;height:1rem;accent-color:var(--accent);cursor:pointer}
body.hide-done li.t-closed{display:contents}
body.hide-done li.t-closed>.t-row,
body.hide-done li.t-closed>details{display:none}
body.hide-done li.t-ref.t-closed{display:none}
/* The render-time + previous-reading line. Same words as the markdown block,
   never a second phrasing of them. */
.t-delta{font-size:.85rem;color:var(--muted);margin:.1rem 0 .5rem}
.t-inflight{font-weight:700;color:#0284c7;border:1px solid #0284c7;border-radius:.25rem;padding:0 .3rem;margin-left:.3rem}
li.row-inflight,li.row-inflight>.t-row,li.row-inflight>details>summary,li.row-inflight .t-id,li.row-inflight .t-name{color:#0ea5e9!important}
</style>
<div class="wrap">
<div class="toolbar">
<label><input type="checkbox" id="hide-done-cb"
  onchange="document.body.classList.toggle('hide-done', this.checked)">
Nascondi i nodi chiusi</label>
</div>
<div class="provenance">
<span><strong>Proiezione, non sorgente.</strong> La verita\u2019 vive nel markdown versionato \u2014
<code>docs/mikado/EXECUTION-SSOT-des-optimization.md</code></span>
<span>Rigenera con <code>scripts/mikado_board.py --html</code>; non editare questa pagina.</span>
</div>
<h1>Albero Mikado \u2014 ottimizzazione DES</h1>
<p>__COUNTS__ &middot; le <strong>foglie</strong> non dipendono da nulla e si implementano per
<strong>prime</strong>; un padre sta sopra i nodi che aspetta. Apri un nodo per leggerne la
descrizione; un nodo ripetuto e\u2019 un collegamento all\u2019espansione che la porta.</p>
<p class="t-delta">__DELTA__</p>
<div class="treewrap">
<ul class="tree">
__ROWS__
</ul>
</div>
</div>
"""


#: A node row inside `## L'ALBERO`: leading whitespace, the node id, then a
#: pipe. Mirrors `_TREE_NODE_LINE` in validate_mikado_tree_coherence.py -- the
#: gate's `state-typed-outside-its-carrier` REJECT and this withdrawal tool
#: must agree on what counts as a node row, or the HOW that rule points at
#: would not actually silence the finding it names.
_NODE_ROW_LINE = re.compile(r"^\s+[A-Z]{1,2}\d{1,3}[a-z]?\s+\|")
#: An attribute tail glued onto a node/detail line: 2+ spaces then ": ".
#: Mirrors `_ATTRIBUTE_SPLIT` in validate_mikado_tree_coherence.py -- reused
#: as the same idea rather than a second regex that could drift from it.
_ALBERO_ATTRIBUTE_SPLIT = re.compile(r"(?=\s{2,}:\s)")

#: The `## L'ALBERO` heading this tool withdraws state from. Matched the same
#: way `_find_section` in validate_mikado_tree_coherence.py matches carriers
#: -- a case-insensitive prefix of the heading text -- so the two never
#: silently disagree about which section is the tree.
_TREE_SECTION_HEADING = "L'ALBERO"


def withdraw_tree_state(text: str) -> str:
    """Strip every pipe field after the title from an `## L'ALBERO` node row.

    State used to be typed a second time on every node row in this section,
    duplicating `## STATO NODO PER NODO` -- and it drifted from that table
    eight times across five classes without the coherence gate ever seeing it
    (see
    `state-typed-outside-its-carrier` in validate_mikado_tree_coherence.py).
    This walks ONLY the `## L'ALBERO` section and rewrites a node row from
    ``    D01 | Campo x | FATTO | XS | onda 1`` to ``    D01 | Campo x``,
    leaving everything else -- ring headings, the `GOAL |` line, `: key |
    value` detail lines, an attribute tail glued onto a node row, every other
    section (`## CORSIE`, `## STATO NODO PER NODO`, the board block) --
    byte-identical. IDEMPOTENT: a node row already carrying only id+title has
    nothing after its one pipe to drop, so a second run is a no-op.
    """
    lines = text.split("\n")
    out: list[str] = []
    in_tree = False
    for line in lines:
        if line.startswith("## "):
            in_tree = line[3:].strip().upper().startswith(_TREE_SECTION_HEADING.upper())
            out.append(line)
            continue
        out.append(_withdraw_node_row(line) if in_tree else line)
    return "\n".join(out)


def _withdraw_node_row(line: str) -> str:
    """Drop every pipe field after the title on one `## L'ALBERO` line.

    A glued attribute tail (`      : key | value`, `_ALBERO_ATTRIBUTE_SPLIT`'s
    lookahead never consumes it) rides through untouched: it is joined back
    onto the rewritten head verbatim, never re-parsed as part of the row.
    Only when there is NO tail is the rewritten head trailing-space-stripped:
    dropping the state/effort/wave fields leaves a trailing space before the
    pipe that used to separate title from state (`    D01 | Campo x `), and an
    end-of-line trailing space trips the repo's pre-commit whitespace check.
    A glued tail's own text starts right where the head ends, so THAT line
    never carries a trailing space to begin with -- stripping there would
    only ever be a no-op, so it is skipped rather than risk eating tail text.
    """
    segments = _ALBERO_ATTRIBUTE_SPLIT.split(line)
    head = segments[0]
    if not _NODE_ROW_LINE.match(head):
        return line
    parts = head.split("|")
    kept = head if len(parts) <= 2 else "|".join(parts[:2])
    if len(segments) == 1:
        kept = kept.rstrip()
    return "".join([kept, *segments[1:]])


_SLICE_PROGRESS_ROW = re.compile(
    r"^\| nodo `([DV]\d+[ab]?)` \| (.*?) \| (.*?) \| (.*?) \|$"
)


def read_slice_progress(path: Path) -> dict[str, list[tuple[str, str]]]:
    """node id -> its `## PROGRESSO PER FETTA` row (dove / fetta / evidenza).

    A SEPARATE section and format from `## L'ALBERO`'s `: key | value` sub-lines
    (`read_details`'s source) -- the free-text table where a node's live
    slice-in-flight detail actually lives. Read independently so the HTML
    surface can merge both into one node's expandable detail; neither format
    subsumes the other.
    """
    progress: dict[str, list[tuple[str, str]]] = {}
    for line in path.read_text(encoding="utf-8").split("\n"):
        row = _SLICE_PROGRESS_ROW.match(line.strip())
        if not row:
            continue
        node, dove, fetta, evidenza = (g.strip() for g in row.groups())
        progress.setdefault(node, []).extend(
            [("Dove", dove), ("Fetta", fetta), ("Evidenza", evidenza)]
        )
    return progress


_PROGRESS_FRACTION = re.compile(r"(\d+)\s*(?:di|su)\s*(\d+)")


def read_progress_fractions(path: Path) -> dict[str, str]:
    """node id -> a short 'N/M' read off its PROGRESSO PER FETTA `Fetta` cell.

    The cell is free prose ('fetta 03 di 4 in corso', '3 item su 4', 'non a
    fette -- 2 rami...') because the underlying units differ (slices, sites,
    items, branches) -- this extracts the first `<n> di|su <m>` numeral pair
    when the row happens to carry one, and is silently absent (no entry)
    otherwise rather than guessing a fraction out of prose that has none.
    """
    fractions: dict[str, str] = {}
    for node, rows in read_slice_progress(path).items():
        fetta = next((v for k, v in rows if k == "Fetta"), "")
        match = _PROGRESS_FRACTION.search(fetta)
        if match:
            fractions[node] = f"{int(match.group(1))}/{int(match.group(2))}"
    return fractions


def read_details(path: Path) -> dict[str, list[tuple[str, str]]]:
    """node id -> its `: key | value` sub-lines from L'ALBERO -- the description
    a reader wants when they click a node.

    Merges in `read_slice_progress` so a node with live slice-in-flight
    evidence shows it alongside its L'ALBERO description, not only in the
    markdown's separate `## PROGRESSO PER FETTA` prose section.
    """
    details: dict[str, list[tuple[str, str]]] = {}
    current: str | None = None
    for line in path.read_text(encoding="utf-8").split("\n"):
        head = re.match(r"    ([DV]\d+[ab]?) \| ", line)
        if head:
            current = head.group(1)
            details.setdefault(current, [])
            continue
        sub = re.match(r"      : ([^|]+?) \| (.*)$", line)
        if sub and current:
            details[current].append((sub.group(1).strip(), sub.group(2).strip()))
        elif line and not line.startswith("      ") and not line.startswith("    "):
            current = None
    for node, rows in read_slice_progress(path).items():
        details.setdefault(node, [])
        details[node] = rows + details[node]
    return details


def render_html(
    states: dict[str, tuple[str, str]],
    deps: dict[str, set[str]],
    roots: list[str],
    details: dict[str, list[tuple[str, str]]],
    meta: dict[str, tuple[str, str, str]] | None = None,
    rendered_at: str | None = None,
    previous: tuple[str, tuple[int, int, int, int] | None] | None = None,
    in_flight: set[str] | None = None,
    progress_fractions: dict[str, str] | None = None,
) -> str:
    """The document renderer\u2019s own tree markup, carrying THESE nodes in
    dependency order.

    `rendered_at` and `previous` are the SAME values the markdown block was
    rendered with, handed down from one read in `main()` -- not re-derived here.
    This page is the surface the work is actually read on, so it carries the
    render clock and the delta too; deriving them independently is how the two
    surfaces would come to disagree.

    `in_flight` (node ids with a `## PROGRESSO PER FETTA` row) drives a purely
    INFORMATIONAL "IN VOLO" badge alongside the STATO pill -- never a
    replacement for it. STATO stays exactly what `validate_mikado_tree_
    coherence.py`'s two gate-recognized carriers (CORSIE, STATO NODO PER NODO)
    say it is; a hand-stamped STATO change without a corroborating carrier is
    correctly rejected by that gate (reverted on D80 2026-07-31 for exactly
    this reason). This badge answers a DIFFERENT, narrower question -- "does a
    branch/slice-plan row explicitly declare working this node" -- from a
    source (`nodo `D80`` row headers) that is a declaration, not a mention, the
    same evidentiary bar `lane_node` already applies.
    """
    import html as _h

    meta = meta or {}
    in_flight = in_flight or set()
    progress_fractions = progress_fractions or {}
    out: list[str] = []
    expanded: set[str] = set()

    #: A title long enough to be a paragraph is unreadable as a tree row. Cut
    #: it at the first natural break and hand the FULL text to the expandable
    #: detail, so nothing is lost and the shape stays legible. Structural, so
    #: it applies to every node -- never a per-node hand-edit that would rot.
    def split_title(title: str) -> tuple[str, str]:
        clean = title.replace("**", "").strip()
        if len(clean) <= _TITLE_MAX:
            return clean, ""
        for sep in (" \u2014 ", ". ", " (", ": "):
            head = clean.split(sep)[0]
            if 12 <= len(head) <= _TITLE_MAX:
                return head, clean
        cut = clean[:_TITLE_MAX].rsplit(" ", 1)[0]
        return cut + "\u2026", clean

    def detail_dl(node: str, full_title: str = "") -> str:
        rows = list(details.get(node, []))
        if full_title:
            rows.insert(0, ("Cosa", full_title))
        if not rows:
            return ""
        cells = "".join(
            f"<dt>{_h.escape(k)}</dt><dd>{_h.escape(v)}</dd>" for k, v in rows
        )
        return f'<dl class="t-detail">{cells}</dl>'

    def walk(node: str) -> None:
        state, raw_title = states.get(node, ("?", ""))
        title, full_title = split_title(raw_title)
        glyph, _rank = _glyph(state, states)
        cls = _CSS_CLASS.get(glyph, "ready")
        row_cls = f"row-s-{cls}"
        # `t-closed` drives the hide-done toggle. It keys on the SAME glyph
        # membership test as the plain-text render() and the CLOSED_GLYPHS
        # contract -- never on `cls`/colour, which is a display choice and
        # would silently desync (e.g. GUARDIA is closed but coloured "guard",
        # not "done").
        closed_cls = " t-closed" if glyph in CLOSED_GLYPHS else ""
        inflight_cls = " row-inflight" if node in in_flight else ""
        idn = _h.escape(node)

        if node in expanded:
            out.append(
                f'<li class="t-ref {row_cls}{closed_cls}">'
                f'<a class="t-id" href="#n-{idn}">{idn}</a>'
                f'<span class="t-name">&#8593; gia&#39; mostrato sopra</span></li>'
            )
            return
        expanded.add(node)

        # State is ALWAYS a coloured pill -- the document view shows FATTO on
        # a done row exactly as it shows CONTESO on a live one; suppressing it
        # for closed nodes would hide the very state that earns the strike-
        # through. Effort / wave / closure-SHA are the same per-node columns
        # the document's own nwtree badges carry, just sourced from the state
        # table instead of the hand-authored block.
        badge = f'<span class="chip s-{cls}">{_h.escape(state)}</span>'
        if node in in_flight:
            frac = progress_fractions.get(node)
            label = f"IN VOLO — fetta {frac}" if frac else "IN VOLO"
            badge += f'<span class="t-badge t-inflight">{_h.escape(label)}</span>'
        effort, wave, sha = meta.get(node, ("", "", ""))
        for extra in (effort, wave):
            if extra:
                badge += f'<span class="t-badge">{_h.escape(extra)}</span>'
        if sha:
            badge += f'<span class="t-badge"><code>{_h.escape(sha)}</code></span>'
        head = (
            f'<span class="t-id">{idn}</span>'
            f'<span class="t-name">{_h.escape(title)}</span>{badge}'
        )
        children = sorted(
            deps.get(node, ()),
            key=lambda c: (_glyph(states.get(c, ("?", ""))[0], states)[1], c),
        )
        dl = detail_dl(node, full_title)

        # The description toggle and the child subtree are SIBLINGS, never
        # nested. Collapsing a description must never hide the nodes beneath
        # it: the shape of the work is always visible, the prose is a click.
        node_html = (
            f"<details><summary>{head}</summary>{dl}</details>"
            if dl
            else f'<span class="t-row">{head}</span>'
        )
        detail_cls = " t-has-detail" if dl else ""

        kids_html = ""
        if children:
            kids: list[str] = []
            for child in children:
                mark = len(out)
                walk(child)
                kids.extend(out[mark:])
                del out[mark:]
            kids_html = f'<ul class="tree">{"".join(kids)}</ul>'

        branch_cls = " t-branch" if children else ""
        out.append(
            f'<li class="{row_cls}{branch_cls}{detail_cls}{closed_cls}{inflight_cls}" id="n-{idn}">'
            f"{node_html}{kids_html}</li>"
        )

    for root in sorted(
        roots, key=lambda r: (_glyph(states.get(r, ("?", ""))[0], states)[1], r)
    ):
        walk(root)

    rendered_at = rendered_at or now_stamp()
    previous = previous or (PREV_ABSENT, None)
    nodes, closed, open_n, free = counts_of(states, deps)
    # The sum now SHOWS the populations it mixes, so `122 nodi` can no longer be
    # read as one homogeneous count of work.
    mix = " &middot; ".join(
        f"{n} {_h.escape(label)}" for label, n in composition(states)
    )
    counts = (
        f"{nodes} nodi ({mix}) &middot; {closed} chiusi &middot; {open_n} aperti "
        f"&middot; {free} senza dipendenze aperte"
    )
    return (
        _PAGE.replace("__CSS__", _doc_css())
        .replace("__ROWS__", "\n".join(out))
        .replace("__COUNTS__", counts)
        .replace(
            "__DELTA__",
            _h.escape(
                _delta_sentence(
                    rendered_at,
                    current=(nodes, closed, open_n, free),
                    previous=previous,
                )
            ),
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(prog="mikado_board")
    parser.add_argument(
        "--file", default="docs/mikado/EXECUTION-SSOT-des-optimization.md", type=Path
    )
    parser.add_argument(
        "--decisions",
        default="docs/mikado/2026-07-28-decisions-consolidated.md",
        type=Path,
    )
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--html", type=Path, default=None)
    parser.add_argument(
        "--withdraw-tree-state",
        action="store_true",
        help=(
            "rewrite '## L'ALBERO' node rows to id+title only, in place -- "
            "the producing tool for the coherence gate's "
            "state-typed-outside-its-carrier REJECT"
        ),
    )
    args = parser.parse_args()

    if args.withdraw_tree_state:
        text = args.file.read_text(encoding="utf-8")
        rewritten = withdraw_tree_state(text)
        if rewritten == text:
            print(f"{args.file} already carries no L'ALBERO state (no-op)")
            return 0
        args.file.write_text(rewritten, encoding="utf-8")
        print(f"withdrew L'ALBERO state in {args.file}")
        return 0

    states = read_states(args.file)
    deps, roots = build(states, read_edges(args.decisions))

    defects = read_defects(args.file)
    for fid, (state, title, parent) in defects.items():
        states[fid] = (_DEFECT_STATE.get(state, state), title)
        deps.setdefault(fid, set())
        if parent and parent in deps:
            deps[parent].add(fid)

    # ONE probe, applied ONCE and only after the defect rows are in `states` --
    # a branch may name an F-id as readily as a D-id, so an override applied
    # before them missed every defect node and had to be repeated verbatim
    # afterwards. The duplicate was pure cost (a git call per branch, twice) for
    # a result the second pass already subsumed. Passing `states` here is also
    # what keeps the join honest: the set of ids a branch may resolve against IS
    # the set of nodes the document carries, never a list kept beside it.
    #
    # A SUSPENDED closure is not overridable either, and `CLOSED_GLYPHS` alone
    # does not say so: `[s]` is deliberately outside that set (a suspended
    # closure must never render as closed), which left `AL LAVORO` free to
    # overwrite `FATTO-SOSPESO`/`CHIUSO-SOSPESO` and erase work that genuinely
    # happened -- the precise harm the `-SOSPESO` vocabulary was added to
    # prevent. The lane being live is a fact about the LANE; the work being
    # finished-and-suspended is a fact about the NODE, and it wins.
    unoverridable = CLOSED_GLYPHS | {"[s]"}
    working, ambiguous = live_nodes(args.file.resolve().parent.parent.parent, states)
    for node in working:
        if _glyph(states[node][0], states)[0] not in unoverridable:
            states[node] = ("AL LAVORO", states[node][1])
    # LOUD, never silent. A live branch whose name names a base several nodes
    # share is the one case the projection cannot decide, and a reader who never
    # hears about it has no way to learn the board is missing a live lane.
    for branch, group in ambiguous:
        print(
            f"AMBIGUO: il ramo vivo `{branch}` nomina una base condivisa da "
            f"{', '.join(group)} — nessuno dei due e' stato forzato a AL LAVORO. "
            f"COME: rinomina il ramo sul nodo esatto (es. `{group[0].lower()}`).",
            file=sys.stderr,
        )

    unparented = sorted(f for f, (_s, _t, p) in defects.items() if not p)
    if unparented:
        states["DIFETTI"] = (
            "RAMO",
            "difetti trovati eseguendo — foglie, non bloccano l'albero",
        )
        deps["DIFETTI"] = set(unparented)
        roots = [r for r in roots if r not in unparented] + ["DIFETTI"]

    # The baseline comes out of the document itself, read BEFORE the block is
    # replaced -- no state file to go stale, and no second source to disagree
    # with the numbers this same process is about to recompute.
    # ONE read of the baseline and ONE read of the clock per run, shared by BOTH
    # surfaces. The markdown block is the only durable record of a previous
    # reading, so the HTML page's baseline necessarily originates there -- but it
    # arrives via this single in-process value, never a second read of a second
    # artifact. Two reads would eventually disagree, and a delta that contradicts
    # itself across two surfaces is worse than one surface without a delta.
    text = args.file.read_text(encoding="utf-8")
    previous = read_previous_summary(text)
    rendered_at = now_stamp()
    board = render(states, deps, roots, rendered_at=rendered_at, previous=previous)

    if args.html is not None:
        args.html.write_text(
            render_html(
                states,
                deps,
                roots,
                read_details(args.file),
                read_node_meta(args.file),
                rendered_at=rendered_at,
                previous=previous,
                in_flight=set(read_slice_progress(args.file).keys()),
                progress_fractions=read_progress_fractions(args.file),
            ),
            encoding="utf-8",
        )
        print(f"html written to {args.html}")
        return 0

    if not args.write:
        print(board)
        return 0

    if BEGIN in text and END in text:
        head, rest = text.split(BEGIN, 1)
        _, tail = rest.split(END, 1)
        text = head + board + tail
    else:
        head, _, tail = text.partition("\n")
        text = f"{head}\n\n{board}\n{tail}"
    args.file.write_text(text, encoding="utf-8")
    print(f"tree written to {args.file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
