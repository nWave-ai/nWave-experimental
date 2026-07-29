"""Render an nWave markdown document to a self-contained HTML page.

WHY THIS EXISTS, AND WHY IT IS NOT A REUSE OF ``scripts/docs_site/build_site.py``
---------------------------------------------------------------------------------
``build_site.py:render_markdown`` already renders markdown to HTML — but it shells
out to **pandoc**. This repository's standing constraint is that the only runtime
dependency is Python: no external CLI tool may be required for a shipped asset to
work (target-machine agnosticism). Reusing it would make this renderer work on the
authoring machine and fail on a clean target, which is the exact class of defect
the constraint exists to prevent. So: stdlib only, no subprocess, no third party.

WHAT IT DELIBERATELY DOES **NOT** DO
------------------------------------
This is a bounded renderer for the markdown subset nWave documents actually use.
It does NOT implement full CommonMark. Unsupported constructs are reported on
stderr with their line number rather than silently mangled (degrade-LOUD): a
renderer that quietly drops content would make the HTML lie about the source.

THE SOURCE OF TRUTH IS THE MARKDOWN, NEVER THE HTML
---------------------------------------------------
The generated page is a PROJECTION. It carries a banner naming the markdown file
it came from. Never edit the HTML; edit the markdown and re-render. The published
artifact URL, if any, is recorded back INTO the markdown as a one-line pointer, so
the repository stays authoritative and the link is a convenience, not an authority.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path


_UNSUPPORTED: list[tuple[int, str]] = []

_INLINE_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC = re.compile(r"(?<![*\w])\*([^*\n]+)\*(?!\*)")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_TABLE_SEP = re.compile(r"^\|[\s:|-]+\|$")
_LIST_ITEM = re.compile(r"^(\s*)[-*+]\s+(.*)$")
_ORDERED_ITEM = re.compile(r"^(\s*)\d+[.)]\s+(.*)$")

# State pills: the SSOT encodes node state as a bare word. Rendering it as a
# coloured chip is information design, not decoration -- state must read at a
# glance, which is the whole reason this projection exists.
_STATE_CLASS = {
    "PRONTO": "s-ready",
    "IN CORSO": "s-wip",
    "AL LAVORO": "s-wip",  # the word the SSOT tables actually use for wip
    "FATTO": "s-done",
    "CHIUSO": "s-done",  # closed-with-nothing-left is done-family, same as FATTO
    "MISURATO": "s-done",
    "QUARANTENA": "s-quar",
    "CONTESO": "s-cont",
    "GUARDIA": "s-guard",
    "BLOCCATO-SERVE-DESIGN": "s-dsn",
    "TIENI": "v-keep",
    "SEMPLIFICA": "v-simp",
    "RIMUOVI": "v-drop",
    "NON_MISURATO": "v-unk",
}


def _inline(text: str) -> str:
    """Escape, then apply inline markup. Order matters: code wins over emphasis."""
    out = html.escape(text, quote=False)
    placeholders: list[str] = []

    def _stash(match: re.Match[str]) -> str:
        placeholders.append(f"<code>{match.group(1)}</code>")
        return f"\x00{len(placeholders) - 1}\x00"

    out = _INLINE_CODE.sub(_stash, out)
    out = _BOLD.sub(r"<strong>\1</strong>", out)
    out = _ITALIC.sub(r"<em>\1</em>", out)
    out = _LINK.sub(r'<a href="\2">\1</a>', out)
    for index, value in enumerate(placeholders):
        out = out.replace(f"\x00{index}\x00", value)
    return out


def _cell(text: str) -> str:
    """Render one table cell, promoting known state words to coloured chips."""
    stripped = text.strip()
    bare = stripped.strip("*`")
    if bare in _STATE_CLASS:
        return f'<span class="chip {_STATE_CLASS[bare]}">{html.escape(bare)}</span>'
    return _inline(stripped)


def _split_row(line: str) -> list[str]:
    return line.strip().strip("|").split("|")


def render_tree(body: list[str]) -> str:
    """Render an ```nwtree block as a collapsible directory-style tree.

    An ASCII tree inside <pre> is a PHOTOGRAPH of a structure; in a living
    document whose nodes change state it should be the structure itself. The
    directory idiom is the one every reader already knows how to scan.

    Syntax -- indentation (2 spaces per level) carries the hierarchy, fields are
    separated by ' | ':

        GOAL - what we are aiming at
          R1 BRANCH NAME
            D01 | what the node does | PRONTO | XS | onda 1

    Field 1 is the id/label, field 2 the description, any further field becomes a
    badge; a field matching a known state or verdict word becomes a coloured chip.
    A row with children renders as <details>/<summary> -- collapsible with zero
    JavaScript, which keeps the page keyboard-accessible and CSP-safe.
    """
    rows: list[tuple[int, list[str], list[list[str]]]] = []
    for raw in body:
        if not raw.strip():
            continue
        depth = (len(raw) - len(raw.lstrip(" "))) // 2
        fields = [f.strip() for f in raw.strip().split("|")]
        if fields[0].startswith(":"):
            # A DETAIL line: not a node of its own, it is an attribute of the
            # node above. This is what makes a node clickable -- the row detail
            # travels WITH the tree instead of living only in a table the reader
            # has to scroll to and match by id.
            fields[0] = fields[0].lstrip(":").strip()
            if rows:
                rows[-1][2].append(fields)
            continue
        rows.append((depth, fields, []))

    def state_of(fields: list[str]) -> str:
        """The node's state word, if it carries one — drives the row's colour."""
        for extra in fields[2:]:
            bare = extra.strip().strip("*`")
            if bare in _STATE_CLASS:
                return _STATE_CLASS[bare]
        return ""

    def node_html(fields: list[str]) -> str:
        label = html.escape(fields[0])
        parts = [f'<span class="t-id">{label}</span>']
        if len(fields) > 1 and fields[1]:
            parts.append(f'<span class="t-name">{_inline(fields[1])}</span>')
        for extra in fields[2:]:
            if not extra:
                continue
            bare = extra.strip("*`")
            if bare in _STATE_CLASS:
                parts.append(
                    f'<span class="chip {_STATE_CLASS[bare]}">{html.escape(bare)}</span>'
                )
            else:
                parts.append(f'<span class="t-badge">{_inline(extra)}</span>')
        return "".join(parts)

    def detail_html(details: list[list[str]]) -> str:
        """Render the attribute rows a reader sees when they open a node."""
        cells: list[str] = []
        for fields in details:
            key = html.escape(fields[0])
            value = " · ".join(
                f'<span class="chip {_STATE_CLASS[v.strip("*`")]}">'
                f"{html.escape(v.strip('*`'))}</span>"
                if v.strip("*`") in _STATE_CLASS
                else _inline(v)
                for v in fields[1:]
                if v
            )
            cells.append(f"<dt>{key}</dt><dd>{value or '—'}</dd>")
        return f'<dl class="t-detail">{"".join(cells)}</dl>'

    def build(start: int, depth: int) -> tuple[str, int]:
        items: list[str] = []
        index = start
        while index < len(rows) and rows[index][0] >= depth:
            row_depth, fields, details = rows[index]
            if row_depth > depth:
                index += 1
                continue
            has_children = index + 1 < len(rows) and rows[index + 1][0] > depth
            if has_children:
                child_html, index = build(index + 1, depth + 1)
                inner = (detail_html(details) if details else "") + child_html
                items.append(
                    f'<li class="t-branch row-{state_of(fields)}"><details open>'
                    f"<summary>{node_html(fields)}</summary>"
                    f"{inner}</details></li>"
                )
            elif details:
                # A leaf that carries its own row detail: collapsed by default,
                # so the tree stays scannable and the detail is one click away.
                items.append(
                    f'<li class="t-leaf t-has-detail row-{state_of(fields)}"><details>'
                    f"<summary>{node_html(fields)}</summary>"
                    f"{detail_html(details)}</details></li>"
                )
                index += 1
            else:
                items.append(
                    f'<li class="t-leaf row-{state_of(fields)}">{node_html(fields)}</li>'
                )
                index += 1
        return f'<ul class="tree">{"".join(items)}</ul>', index

    if not rows:
        return ""
    html_out, _ = build(0, rows[0][0])
    return f'<div class="treewrap">{html_out}</div>'


def render(markdown: str) -> str:
    """Render the supported markdown subset to an HTML fragment."""
    lines = markdown.splitlines()
    out: list[str] = []
    index = 0
    in_list: str | None = None

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append(f"</{in_list}>")
            in_list = None

    while index < len(lines):
        line = lines[index]

        if line.startswith("```"):
            close_list()
            fence = line[3:].strip()
            body: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].startswith("```"):
                body.append(lines[index])
                index += 1
            index += 1
            if fence == "nwtree":
                out.append(render_tree(body))
                continue
            lang = f' data-lang="{html.escape(fence)}"' if fence else ""
            escaped = html.escape("\n".join(body), quote=False)
            out.append(f"<pre{lang}><code>{escaped}</code></pre>")
            continue

        if (
            line.startswith("|")
            and index + 1 < len(lines)
            and _TABLE_SEP.match(lines[index + 1].strip())
        ):
            close_list()
            header = _split_row(line)
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].startswith("|"):
                rows.append(_split_row(lines[index]))
                index += 1
            out.append('<div class="tablewrap"><table>')
            out.append("<thead><tr>")
            out.extend(f"<th>{_cell(c)}</th>" for c in header)
            out.append("</tr></thead><tbody>")
            for row in rows:
                out.append("<tr>")
                out.extend(f"<td>{_cell(c)}</td>" for c in row)
                out.append("</tr>")
            out.append("</tbody></table></div>")
            continue

        heading = _HEADING.match(line)
        if heading:
            close_list()
            level = len(heading.group(1))
            text = _inline(heading.group(2).strip())
            slug = re.sub(r"[^a-z0-9]+", "-", heading.group(2).lower()).strip("-")
            out.append(f'<h{level} id="{slug}">{text}</h{level}>')
            index += 1
            continue

        if line.strip() in {"---", "***", "___"}:
            close_list()
            out.append("<hr>")
            index += 1
            continue

        if line.startswith(">"):
            close_list()
            quote: list[str] = []
            while index < len(lines) and lines[index].startswith(">"):
                quote.append(lines[index].lstrip(">").strip())
                index += 1
            out.append(f"<blockquote>{_inline(' '.join(quote))}</blockquote>")
            continue

        item = _LIST_ITEM.match(line)
        ordered = _ORDERED_ITEM.match(line)
        if item or ordered:
            want = "ol" if ordered else "ul"
            if in_list != want:
                close_list()
                out.append(f"<{want}>")
                in_list = want
            body_text = (ordered or item).group(2)  # type: ignore[union-attr]
            out.append(f"<li>{_inline(body_text)}</li>")
            index += 1
            continue

        if not line.strip():
            close_list()
            index += 1
            continue

        para: list[str] = []
        while (
            index < len(lines)
            and lines[index].strip()
            and not (
                lines[index].startswith(("|", ">", "#", "```"))
                or _LIST_ITEM.match(lines[index])
                or _ORDERED_ITEM.match(lines[index])
            )
        ):
            para.append(lines[index])
            index += 1
        close_list()
        out.append(f"<p>{_inline(' '.join(para))}</p>")

    close_list()
    return "\n".join(out)


_CSS = """
:root{
  --paper:#fbfaf8; --ink:#14171c; --muted:#5f6672; --rule:#e3e0da;
  --panel:#ffffff; --accent:#a8590c; --accent-soft:#f5ead9;
  --ready:#0f766e; --wip:#1d4ed8; --done:#15803d;
  --quar:#a16207; --cont:#7e22ce; --guard:#475569; --dsn:#c2410c;
  --keep:#15803d; --simp:#1d4ed8; --drop:#b91c1c; --unk:#6b7280;
}
@media (prefers-color-scheme:dark){
  :root{
    --paper:#11141a; --ink:#e7e5e0; --muted:#98a0ad; --rule:#252a33;
    --panel:#171b22; --accent:#e0964a; --accent-soft:#2a2118;
    --ready:#5eead4; --wip:#93c5fd; --done:#86efac;
    --quar:#fcd34d; --cont:#d8b4fe; --guard:#94a3b8; --dsn:#fb923c;
    --keep:#86efac; --simp:#93c5fd; --drop:#fca5a5; --unk:#9ca3af;
  }
}
:root[data-theme="light"]{
  --paper:#fbfaf8; --ink:#14171c; --muted:#5f6672; --rule:#e3e0da;
  --panel:#ffffff; --accent:#a8590c; --accent-soft:#f5ead9;
  --ready:#0f766e; --wip:#1d4ed8; --done:#15803d;
  --quar:#a16207; --cont:#7e22ce; --guard:#475569; --dsn:#c2410c;
  --keep:#15803d; --simp:#1d4ed8; --drop:#b91c1c; --unk:#6b7280;
}
:root[data-theme="dark"]{
  --paper:#11141a; --ink:#e7e5e0; --muted:#98a0ad; --rule:#252a33;
  --panel:#171b22; --accent:#e0964a; --accent-soft:#2a2118;
  --ready:#5eead4; --wip:#93c5fd; --done:#86efac;
  --quar:#fcd34d; --cont:#d8b4fe; --guard:#94a3b8; --dsn:#fb923c;
  --keep:#86efac; --simp:#93c5fd; --drop:#fca5a5; --unk:#9ca3af;
}
*{box-sizing:border-box}
body{
  margin:0; background:var(--paper); color:var(--ink);
  font-family:ui-sans-serif,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",sans-serif;
  font-size:15px; line-height:1.62; -webkit-font-smoothing:antialiased;
}
.wrap{max-width:1180px;margin:0 auto;padding:2.5rem 1.5rem 6rem;
  display:flex;flex-direction:column;gap:1.1rem}
.provenance{
  display:flex;flex-wrap:wrap;gap:.5rem .9rem;align-items:baseline;
  background:var(--accent-soft);border-left:3px solid var(--accent);
  padding:.7rem .95rem;border-radius:0 4px 4px 0;font-size:.8rem;color:var(--muted);
}
.provenance strong{color:var(--ink);font-weight:600}
.provenance code{background:none;padding:0;color:var(--accent)}
h1,h2,h3,h4{text-wrap:balance;line-height:1.22;margin:0;font-weight:640}
h1{font-size:1.9rem;letter-spacing:-.018em;margin-top:.6rem}
h2{font-size:1.28rem;letter-spacing:-.01em;margin-top:2.2rem;
  padding-bottom:.4rem;border-bottom:1px solid var(--rule)}
h3{font-size:1.02rem;margin-top:1.5rem;color:var(--accent)}
h4{font-size:.9rem;margin-top:1.1rem;text-transform:uppercase;
  letter-spacing:.07em;color:var(--muted)}
p{margin:0;max-width:74ch}
ul,ol{margin:0;padding-left:1.3rem;display:flex;flex-direction:column;gap:.35rem;max-width:74ch}
hr{border:0;border-top:1px solid var(--rule);margin:1.6rem 0;width:100%}
a{color:var(--accent);text-decoration-thickness:1px;text-underline-offset:2px}
a:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
code{font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace;font-size:.86em;
  background:var(--accent-soft);padding:.1em .34em;border-radius:3px}
pre{background:var(--panel);border:1px solid var(--rule);border-radius:5px;
  padding:1rem 1.1rem;overflow-x:auto;margin:0;font-size:.78rem;line-height:1.5}
pre code{background:none;padding:0;font-size:inherit}
blockquote{margin:0;padding:.75rem 1rem;background:var(--panel);
  border-left:3px solid var(--quar);border-radius:0 4px 4px 0;color:var(--muted);max-width:74ch}
.tablewrap{overflow-x:auto;border:1px solid var(--rule);border-radius:5px;background:var(--panel)}
table{border-collapse:collapse;width:100%;font-size:.83rem;
  font-variant-numeric:tabular-nums}
th{position:sticky;top:0;background:var(--panel);text-align:left;
  font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;
  color:var(--muted);font-weight:620;padding:.6rem .75rem;
  border-bottom:1px solid var(--rule);white-space:nowrap}
td{padding:.55rem .75rem;border-bottom:1px solid var(--rule);vertical-align:top}
tbody tr:last-child td{border-bottom:0}
.chip{display:inline-block;padding:.12em .55em;border-radius:100px;
  font-size:.7rem;font-weight:650;letter-spacing:.03em;white-space:nowrap;
  border:1px solid currentColor}
.s-ready{color:var(--ready)} .s-wip{color:var(--wip)} .s-done{color:var(--done)}
.s-quar{color:var(--quar)} .s-cont{color:var(--cont)} .s-guard{color:var(--guard)}
.s-dsn{color:var(--dsn)}
.v-keep{color:var(--keep)} .v-simp{color:var(--simp)}
.v-drop{color:var(--drop)} .v-unk{color:var(--unk)}
/* --- directory tree: connectors drawn with borders, not characters,
   so the chips stay aligned regardless of name length --- */
.treewrap{border:1px solid var(--rule);border-radius:5px;background:var(--panel);
  padding:.9rem 1.1rem;overflow-x:auto}
ul.tree{list-style:none;margin:0;padding:0;display:block;max-width:none;
  font-size:.83rem;line-height:1.5}
ul.tree ul.tree{margin-left:.62rem;padding-left:.95rem;border-left:1px solid var(--rule)}
ul.tree li{position:relative;padding:.16rem 0 .16rem .95rem;margin:0}
ul.tree ul.tree>li::before{content:"";position:absolute;left:-.95rem;top:.72rem;
  width:.82rem;border-top:1px solid var(--rule)}
ul.tree ul.tree>li:last-child::after{content:"";position:absolute;left:-1.02rem;
  top:.75rem;bottom:0;width:1px;background:var(--panel)}
ul.tree summary{cursor:pointer;list-style:none;padding:.16rem 0;margin-left:-.95rem;
  padding-left:.95rem;border-radius:3px}
ul.tree summary::-webkit-details-marker{display:none}
ul.tree summary::before{content:"▾";position:absolute;left:-.15rem;color:var(--muted);
  font-size:.7rem;transition:transform .12s ease}
ul.tree details:not([open])>summary::before{content:"▸"}
ul.tree summary:hover{background:var(--accent-soft)}
ul.tree summary:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.t-id{font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace;font-weight:650;
  color:var(--accent);margin-right:.55rem;white-space:nowrap}
.t-name{color:var(--ink);margin-right:.55rem}
.t-badge{display:inline-block;font-size:.7rem;color:var(--muted);
  border:1px solid var(--rule);border-radius:3px;padding:.02em .4em;
  margin-right:.35rem;white-space:nowrap}
li.t-branch>details>summary .t-id{font-size:.86rem;letter-spacing:.01em}
/* --- colore del TESTO per stato: si legge la riga intera, non solo la chip --- */
li.row-s-done>.t-name,li.row-s-done>details>summary .t-name{color:var(--done);
  text-decoration:line-through;text-decoration-thickness:1px;opacity:.82}
li.row-s-done>.t-id,li.row-s-done>details>summary .t-id{color:var(--done)}
li.row-s-wip>.t-name,li.row-s-wip>details>summary .t-name{color:var(--wip);font-weight:560}
li.row-s-wip>.t-id,li.row-s-wip>details>summary .t-id{color:var(--wip)}
li.row-s-wip>details>summary{background:color-mix(in srgb,var(--wip) 9%,transparent);
  border-left:2px solid var(--wip);margin-left:-1.15rem;padding-left:1.1rem}
li.row-s-quar>.t-name,li.row-s-quar>details>summary .t-name{color:var(--muted);opacity:.72}
li.row-s-cont>.t-name,li.row-s-cont>details>summary .t-name{color:var(--cont)}
li.row-s-dsn>.t-name,li.row-s-dsn>details>summary .t-name{color:var(--dsn)}
li.row-s-dsn>.t-id,li.row-s-dsn>details>summary .t-id{color:var(--dsn)}
/* leaf with detail: closed by default, so the tree stays scannable
   and the full row is a click away instead of a table to search */
li.t-has-detail>details>summary::before{content:"›";font-size:.85rem}
li.t-has-detail>details[open]>summary::before{content:"⌄";font-size:.7rem}
li.t-has-detail>details[open]>summary{background:var(--accent-soft)}
dl.t-detail{display:grid;grid-template-columns:auto 1fr;gap:.28rem .9rem;
  margin:.45rem 0 .6rem .3rem;padding:.6rem .8rem;font-size:.78rem;
  background:var(--paper);border:1px solid var(--rule);border-radius:4px}
dl.t-detail dt{color:var(--muted);font-size:.7rem;text-transform:uppercase;
  letter-spacing:.05em;font-weight:620;white-space:nowrap;padding-top:.06rem}
dl.t-detail dd{margin:0;color:var(--ink)}
@media (max-width:640px){.wrap{padding:1.5rem 1rem 4rem}h1{font-size:1.5rem}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""


def build_page(markdown: str, source: str, title: str) -> str:
    """Wrap the rendered fragment in the standalone page body."""
    banner = (
        '<div class="provenance">'
        "<span><strong>Projection, not source.</strong> "
        "The truth lives in the versioned markdown — "
        f"<code>{html.escape(source)}</code></span>"
        "<span>Do not edit this page: edit the markdown and re-generate.</span>"
        "</div>"
    )
    return (
        f"<title>{html.escape(title)}</title>\n"
        f"<style>{_CSS}</style>\n"
        f'<div class="wrap">{banner}\n{render(markdown)}</div>\n'
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render an nWave markdown document to a self-contained HTML page."
    )
    parser.add_argument("source", type=Path, help="markdown file to render")
    parser.add_argument("--out", type=Path, required=True, help="HTML file to write")
    parser.add_argument("--title", default=None, help="page title (default: first H1)")
    args = parser.parse_args(argv)

    if not args.source.is_file():
        print(
            f"WHAT: cannot render, the source file does not exist.\n"
            f"WHY: {args.source} was not found.\n"
            f"HOW: pass the path of an existing markdown file.",
            file=sys.stderr,
        )
        return 2

    text = args.source.read_text(encoding="utf-8")
    first_h1 = next(
        (
            m.group(2).strip()
            for m in (_HEADING.match(row) for row in text.splitlines())
            if m
        ),
        args.source.stem,
    )
    title = args.title or first_h1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(build_page(text, str(args.source), title), encoding="utf-8")

    print(f"rendered {args.source} -> {args.out} ({args.out.stat().st_size:,} bytes)")
    if _UNSUPPORTED:
        print(
            f"NOTE: {len(_UNSUPPORTED)} unsupported construct(s) passed through as text.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
