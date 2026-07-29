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
from pathlib import Path


BEGIN = "<!-- MIKADO-BOARD:BEGIN -->"
END = "<!-- MIKADO-BOARD:END -->"

#: Node id anywhere in a `dipende-da` cell. Sub-slices (`D03a`) inherit the
#: base node's edges -- the graph is authored on base ids.
_DEP_RE = re.compile(r"\bD\d+\b")
_DECISION_ROW_RE = re.compile(r"^\| (D\d+) \|")
_STATE_ROW_RE = re.compile(r"^\| `([DV]\d+[ab]?)` \|")

#: State -> (glyph, rank). Rank orders siblings so what is workable floats up.
STATE_GLYPH = {
    "FATTO": ("[x]", 9),
    "CHIUSO": ("[-]", 9),
    "MISURATO": ("[m]", 9),
    "FUSO IN D03b": ("[>]", 9),
    "GUARDIA": ("[G]", 9),
    "AL LAVORO": ("[~]", 0),
    "PRONTO": ("[ ]", 1),
    "CONTESO": ("[!]", 2),
    "BLOCCATO-SERVE-DESIGN": ("[D]", 3),
    "QUARANTENA": ("[Q]", 4),
    "NON_MISURATO": ("[Q]", 4),
    "RAMO": ("[+]", 6),
}
CLOSED_GLYPHS = {"[x]", "[-]", "[m]", "[>]", "[G]"}

#: Glyph -> CSS class, so colour carries the same meaning as in the document
#: rendering rather than a second, private vocabulary.
_CSS_CLASS = {
    "[x]": "done", "[-]": "done", "[m]": "done", "[>]": "done", "[G]": "guard",
    "[ ]": "ready", "[~]": "wip", "[!]": "cont", "[D]": "dsn", "[Q]": "quar",
    "[+]": "guard", "[?]": "guard",
}

#: Defect-register states mapped onto the node-state vocabulary.
_DEFECT_STATE = {
    "RIPARATO": "FATTO",
    "IN CORSIA": "AL LAVORO",
    "APERTO": "PRONTO",
    "SERVE DESIGN": "BLOCCATO-SERVE-DESIGN",
}


def _glyph(state: str) -> tuple[str, int]:
    for key, value in STATE_GLYPH.items():
        if state.startswith(key):
            return value
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

#: Branch of a LIVE lane -> the node ids it is working on. Authored, because a
#: lane's branch name is not a node id and guessing the link would be exactly
#: the designation-not-property mistake this tree keeps repairing. A lane whose
#: worktree still exists and whose branch is not merged into trunk is live.
LANE_NODES = {
    "lane/at-discovery-ssot": ("V15", "F12"),
    "lane/codex-recover": ("D37", "D38", "D34", "D35"),
    "lane/ws-na-reconciliation": ("F13",),
    "lane/d27-design": ("D27",),
    "lane/d15-design": ("D15", "D03b"),
    "lane/d12-design": ("D12",),
    "lane/review-producer-wiring": ("F14",),
    "lane/d03b": ("D03b",),
}


def live_nodes(repo: Path) -> set[str]:
    """Node ids a live lane is working on right now.

    A lane is LIVE when its worktree still exists -- read from git's own
    worktree list, never from a hand-kept list that would go stale the moment
    a lane finishes.
    """
    import subprocess

    try:
        listing = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=repo,
            capture_output=True,
            text=True,
            # stdin closed and a wall-clock bound: a read-only probe must never
            # inherit a terminal or hang the render.
            stdin=subprocess.DEVNULL,
            timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return set()
    present = {
        line.split("refs/heads/", 1)[1].strip()
        for line in listing.split("\n")
        if line.startswith("branch refs/heads/")
    }
    out: set[str] = set()
    for branch, nodes in LANE_NODES.items():
        if branch in present:
            out.update(nodes)
    return out


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
    """node id -> the set of nodes it WAITS FOR."""
    edges: dict[str, set[str]] = {}
    for line in path.read_text(encoding="utf-8").split("\n"):
        match = _DECISION_ROW_RE.match(line)
        if not match:
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) <= 7:
            continue
        node = match.group(1)
        deps = {d for d in _DEP_RE.findall(cells[7]) if d != node}
        edges[node] = deps
    return edges


def build(
    states: dict[str, tuple[str, str]], edges: dict[str, set[str]]
) -> tuple[dict[str, set[str]], list[str]]:
    """Resolve sub-slices onto the graph and return (deps, roots)."""
    deps: dict[str, set[str]] = {}
    for node in states:
        base = re.sub(r"[ab]$", "", node)
        resolved: set[str] = set()
        for dep in edges.get(base, set()):
            # A base id with sub-slices is waited for through its sub-slices.
            subs = [s for s in states if re.sub(r"[ab]$", "", s) == dep and s != dep]
            resolved.update(subs or ([dep] if dep in states else []))
        deps[node] = resolved - {node}
    waited_for = {d for ds in deps.values() for d in ds}
    roots = sorted(n for n in deps if n not in waited_for)
    return deps, roots


def render(
    states: dict[str, tuple[str, str]], deps: dict[str, set[str]], roots: list[str]
) -> str:
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
        glyph, _ = _glyph(state)
        pad = "    " * depth
        if node in expanded:
            lines.append(f"{pad}{glyph} {node:5} \u2192 gia' mostrato sopra")
            return
        expanded.add(node)
        mark = "" if glyph in CLOSED_GLYPHS else f"  \u2190 {state}"
        lines.append(f"{pad}{glyph} {node:5} {title[:52]}{mark}")
        children = sorted(
            deps.get(node, ()),
            key=lambda c: (_glyph(states.get(c, ("?", ""))[0])[1], c),
        )
        for child in children:
            walk(child, depth + 1)

    for root in sorted(
        roots, key=lambda r: (_glyph(states.get(r, ("?", ""))[0])[1], r)
    ):
        walk(root, 0)
    lines.append("```")

    open_nodes = [
        n for n, (s, _) in states.items() if _glyph(s)[0] not in CLOSED_GLYPHS
    ]
    free = [
        n
        for n in open_nodes
        if not any(
            _glyph(states.get(d, ("?", ""))[0])[0] not in CLOSED_GLYPHS
            for d in deps.get(n, ())
        )
    ]
    lines += [
        "",
        f"**{len(states)} nodi · {len(states) - len(open_nodes)} chiusi · "
        f"{len(open_nodes)} aperti, di cui {len(free)} senza dipendenze aperte.**",
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
</style>
<div class="wrap">
<div class="provenance">
<span><strong>Proiezione, non sorgente.</strong> La verita\u2019 vive nel markdown versionato \u2014
<code>docs/mikado/EXECUTION-SSOT-des-optimization.md</code></span>
<span>Rigenera con <code>scripts/mikado_board.py --html</code>; non editare questa pagina.</span>
</div>
<h1>Albero Mikado \u2014 ottimizzazione DES</h1>
<p>__COUNTS__ &middot; le <strong>foglie</strong> non dipendono da nulla e si implementano per
<strong>prime</strong>; un padre sta sopra i nodi che aspetta. Apri un nodo per leggerne la
descrizione; un nodo ripetuto e\u2019 un collegamento all\u2019espansione che la porta.</p>
<div class="treewrap">
<ul class="tree">
__ROWS__
</ul>
</div>
</div>
"""


def read_details(path: Path) -> dict[str, list[tuple[str, str]]]:
    """node id -> its `: key | value` sub-lines from L'ALBERO -- the description
    a reader wants when they click a node."""
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
    return details


def render_html(
    states: dict[str, tuple[str, str]],
    deps: dict[str, set[str]],
    roots: list[str],
    details: dict[str, list[tuple[str, str]]],
) -> str:
    """The document renderer\u2019s own tree markup, carrying THESE nodes in
    dependency order."""
    import html as _h

    out: list[str] = []
    expanded: set[str] = set()

    def detail_dl(node: str) -> str:
        rows = details.get(node, [])
        if not rows:
            return ""
        cells = "".join(
            f"<dt>{_h.escape(k)}</dt><dd>{_h.escape(v)}</dd>" for k, v in rows
        )
        return f'<dl class="t-detail">{cells}</dl>'

    def walk(node: str) -> None:
        state, title = states.get(node, ("?", ""))
        glyph, _rank = _glyph(state)
        row_cls = f"row-s-{_CSS_CLASS.get(glyph, 'ready')}"
        idn = _h.escape(node)

        if node in expanded:
            out.append(
                f'<li class="t-ref {row_cls}">'
                f'<a class="t-id" href="#n-{idn}">{idn}</a>'
                f'<span class="t-name">&#8593; gia&#39; mostrato sopra</span></li>'
            )
            return
        expanded.add(node)

        badge = (
            ""
            if glyph in CLOSED_GLYPHS
            else f'<span class="t-badge">{_h.escape(state)}</span>'
        )
        head = (
            f'<span class="t-id">{idn}</span>'
            f'<span class="t-name">{_h.escape(title)}</span>{badge}'
        )
        children = sorted(
            deps.get(node, ()),
            key=lambda c: (_glyph(states.get(c, ("?", ""))[0])[1], c),
        )
        dl = detail_dl(node)

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
            f'<li class="{row_cls}{branch_cls}{detail_cls}" id="n-{idn}">'
            f"{node_html}{kids_html}</li>"
        )

    for root in sorted(
        roots, key=lambda r: (_glyph(states.get(r, ("?", ""))[0])[1], r)
    ):
        walk(root)

    open_n = [n for n, (s_, _t) in states.items() if _glyph(s_)[0] not in CLOSED_GLYPHS]
    counts = (
        f"{len(states)} nodi &middot; {len(states) - len(open_n)} chiusi "
        f"&middot; {len(open_n)} aperti"
    )
    return (
        _PAGE.replace("__CSS__", _doc_css())
        .replace("__ROWS__", "\n".join(out))
        .replace("__COUNTS__", counts)
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
    args = parser.parse_args()

    states = read_states(args.file)
    deps, roots = build(states, read_edges(args.decisions))

    for node in live_nodes(args.file.resolve().parent.parent.parent):
        if node in states and _glyph(states[node][0])[0] not in CLOSED_GLYPHS:
            states[node] = ("AL LAVORO", states[node][1])

    defects = read_defects(args.file)
    for fid, (state, title, parent) in defects.items():
        states[fid] = (_DEFECT_STATE.get(state, state), title)
        deps.setdefault(fid, set())
        if parent and parent in deps:
            deps[parent].add(fid)
    for node in live_nodes(args.file.resolve().parent.parent.parent):
        if node in states and _glyph(states[node][0])[0] not in CLOSED_GLYPHS:
            states[node] = ("AL LAVORO", states[node][1])

    unparented = sorted(f for f, (_s, _t, p) in defects.items() if not p)
    if unparented:
        states["DIFETTI"] = ("RAMO", "difetti trovati eseguendo — foglie, non bloccano l'albero")
        deps["DIFETTI"] = set(unparented)
        roots = [r for r in roots if r not in unparented] + ["DIFETTI"]
    board = render(states, deps, roots)

    if args.html is not None:
        args.html.write_text(
            render_html(states, deps, roots, read_details(args.file)), encoding="utf-8"
        )
        print(f"html written to {args.html}")
        return 0

    if not args.write:
        print(board)
        return 0

    text = args.file.read_text(encoding="utf-8")
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
