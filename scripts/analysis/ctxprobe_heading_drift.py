#!/usr/bin/env python3
"""Cross-tree heading-drift detector: the control that sees BOTH copies.

WHY IT MUST RUN AT SESSION TIME. The two copies of nWave's guidance live in
different trees: the project CLAUDE.md is in the repo, the global one is under
the active Claude profile. No CI job, pre-commit hook or `des` gate can see
the second. A session hook can see both -- verified, not assumed:
  * CLAUDE_CONFIG_DIR is present in the hook environment and names the active
    profile, so the global file resolves as $CLAUDE_CONFIG_DIR/CLAUDE.md;
  * the project root is cwd, the same resolution load_project_context.py uses.

WHAT IT DECIDES ON. NOT "the files differ" -- they SHOULD differ; a third of
the global file is genuinely profile-scope and has nothing to do with any
project. The falsifiable property is narrower:

    two sections with the SAME HEADING and DIFFERENT BODIES

WHAT IT DOES WHEN IT FIRES. It cannot repair: one side lives outside the repo
and belongs to a human. So it NAMES. Staleness is only ever claimed on a
mechanically decidable signal -- one body's non-empty lines being a strict
subset of the other, i.e. absorbed. Everything else is INDETERMINATE with both
bodies shown.

DESIGNED AGAINST THE DANGEROUS ERROR. A false positive here tells someone a
norm is obsolete when it is not. That is worse than today's silence. So the
detector prefers NOT DECIDING to deciding wrong: it never guesses which copy
is older from mtime, size, or wording, and INDETERMINATE is a first-class
outcome that reaches the aggregate rather than being rounded to PASS or FAIL.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


HEADING = re.compile(r"^(#{1,3} .+)$", re.M)
SCHEMA_VERSION = 1


def split_sections(text: str) -> dict[str, str]:
    parts = HEADING.split(text)
    out: dict[str, str] = {}
    for i in range(1, len(parts), 2):
        head = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        # a repeated heading in one file is itself a defect; keep the first and
        # let the duplicate surface rather than silently overwriting
        out.setdefault(head, body)
    return out


def norm_lines(body: str) -> list[str]:
    return [ln.strip() for ln in body.splitlines() if ln.strip()]


def resolve_global() -> tuple[Path | None, str]:
    cfg = os.environ.get("CLAUDE_CONFIG_DIR")
    if cfg:
        p = Path(cfg) / "CLAUDE.md"
        if p.is_file():
            return p, "CLAUDE_CONFIG_DIR"
    p = Path.home() / ".claude" / "CLAUDE.md"
    if p.is_file():
        return p, "~/.claude fallback"
    return None, "not found"


def compare(global_path: Path, project_path: Path) -> dict:
    """Returns a verdict record. Never raises; unreadable input -> could_not_verify."""
    rec: dict = {
        "schema_version": SCHEMA_VERSION,
        "kind": "heading_drift",
        "global_path": str(global_path),
        "project_path": str(project_path),
        "drifted": [],
        "measured_count": 0,
        "could_not_verify_count": 0,
        "could_not_verify_reasons": [],
    }
    try:
        g = split_sections(global_path.read_text(encoding="utf-8", errors="replace"))
        p = split_sections(project_path.read_text(encoding="utf-8", errors="replace"))
    except OSError as exc:
        rec["could_not_verify_count"] = 1
        rec["could_not_verify_reasons"].append(f"unreadable: {exc}")
        return rec

    shared = sorted(set(g) & set(p))
    rec["shared_headings"] = len(shared)
    rec["global_only"] = len(set(g) - set(p))
    rec["project_only"] = len(set(p) - set(g))

    for h in shared:
        gb, pb = g[h].strip(), p[h].strip()
        if gb == pb:
            continue
        gl, pl = norm_lines(gb), norm_lines(pb)
        only_g = [ln for ln in gl if ln not in pl]
        only_p = [ln for ln in pl if ln not in gl]

        # The ONLY mechanically decidable staleness signal: strict subset.
        if not only_g and only_p:
            finding, det = "global_absorbed_into_project", "measured"
        elif not only_p and only_g:
            finding, det = "project_absorbed_into_global", "measured"
        else:
            finding, det = "bodies_diverge", "could_not_verify"

        item = {
            "heading": h,
            "finding": finding,
            "determination": det,
            "global_bytes": len(gb),
            "project_bytes": len(pb),
            "lines_only_in_global": only_g[:20],
            "lines_only_in_project": only_p[:20],
        }
        if det == "could_not_verify":
            item["could_not_verify_reason"] = (
                "each copy carries lines the other lacks; which is older is not "
                "mechanically decidable and is NOT guessed"
            )
            rec["could_not_verify_count"] += 1
            rec["could_not_verify_reasons"].append(h)
        else:
            rec["measured_count"] += 1
        rec["drifted"].append(item)
    return rec


def render(rec: dict) -> str:
    n = len(rec["drifted"])
    if not n and not rec["could_not_verify_reasons"]:
        return ""
    out = [
        f"HEADING DRIFT: {n} heading(s) exist in BOTH guidance files with different bodies.",
        f"  global : {rec['global_path']}",
        f"  project: {rec['project_path']}",
        f"  measured {rec['measured_count']} | could-not-verify {rec['could_not_verify_count']}",
        "",
    ]
    for d in rec["drifted"]:
        out.append(f"  [{d['determination'].upper()}] {d['heading']}")
        out.append(
            f"      finding: {d['finding']}  "
            f"(global {d['global_bytes']:,} B, project {d['project_bytes']:,} B)"
        )
        if d["finding"] == "global_absorbed_into_project":
            out.append(
                "      the global copy is a strict SUBSET -> it is the older copy"
            )
        elif d["finding"] == "project_absorbed_into_global":
            out.append(
                "      the project copy is a strict SUBSET -> it is the older copy"
            )
        else:
            out.append(
                "      WHICH IS OLDER IS NOT DECIDABLE HERE -- both bodies differ"
            )
            for ln in d["lines_only_in_global"][:3]:
                out.append(f"        only in GLOBAL : {ln[:110]}")
            for ln in d["lines_only_in_project"][:3]:
                out.append(f"        only in PROJECT: {ln[:110]}")
    out.append("")
    out.append("  This control cannot repair: one copy lives outside the repo and")
    out.append("  belongs to a human. It names the divergence; a human decides.")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    gp = pp = None
    if len(argv) >= 2:
        gp, pp = Path(argv[0]), Path(argv[1])
        src = "explicit args"
    else:
        gp, src = resolve_global()
        pp = Path.cwd() / "CLAUDE.md"
    if gp is None or not gp.is_file():
        print(
            json.dumps(
                {
                    "determination": "could_not_verify",
                    "reason": f"global CLAUDE.md unresolved ({src})",
                }
            ),
            file=sys.stderr,
        )
        return 0  # never block a session
    if not pp.is_file():
        return 0  # not in a project that has one; nothing to compare
    rec = compare(gp, pp)
    text = render(rec)
    if os.environ.get("DRIFT_JSON"):
        print(json.dumps(rec, indent=2, ensure_ascii=False))
    elif text:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
