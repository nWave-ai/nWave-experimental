#!/usr/bin/env python3
"""Generate a Jira-importable CSV mirror from the in-repo backlog SSOT.

One-way mirror: ``docs/product/backlog.md`` (the SSOT) -> a Jira CSV import file.
The backlog stays the single source of truth; Jira is a read-only visibility
mirror. Run on demand (or in CI) to refresh the export; never edit the CSV by
hand and never sync Jira -> backlog (that would create a second SSOT, the drift
this whole codebase fights).

Parsing contract (deliberately simple, stdlib-only, no PyYAML):
- Each ``### <ID> — <title>`` heading under a backlog section is one Story.
- The first ``**STATUS: ...**`` line after the heading yields Status + Priority
  (heuristic keyword match). A heading with no STATUS line -> Status "To Do".
- The body up to the next ``### `` heading is the Description (truncated).

Jira CSV columns: Issue Type, Summary, Description, Priority, Status, Labels.
Map the columns at Jira import time (Settings -> System -> External System Import).

Usage:
    python scripts/backlog_to_jira_csv.py            # -> docs/analysis/jira-mirror-backlog.csv
    python scripts/backlog_to_jira_csv.py --out PATH
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path


_REPO = Path(__file__).resolve().parents[1]
_BACKLOG = _REPO / "docs" / "product" / "backlog.md"
_DEFAULT_OUT = _REPO / "docs" / "analysis" / "jira-mirror-backlog.csv"

_HEADING = re.compile(
    r"^###\s+(?P<id>[A-Z0-9][A-Za-z0-9-]*)\s*[—–-]\s*(?P<title>.+?)\s*$"
)
# Title-first form (2026-07-05 re-layout): ``### <Human Title>   `F-ID` `` — the
# human title leads, the stable id trails in inline-code. Tried FIRST so the Jira
# Story summary is the human title (the board shows meaning, not the F-id jargon);
# the id-first ``_HEADING`` above stays as a fallback for any not-yet-flipped item.
_HEADING_TITLE_FIRST = re.compile(
    r"^###\s+(?P<title>.+?)\s+`(?P<id>[A-Za-z0-9][A-Za-z0-9-]*)`\s*$"
)
_STATUS_LINE = re.compile(r"\*\*STATUS:\s*(?P<status>.+?)\*\*", re.IGNORECASE)
_ITEM_ID = re.compile(r"^(F-|f-|fix-|BUG)", re.IGNORECASE)


# The backlog SECTION heading (## Critical / ## High / ## Medium / ## Low) is the
# AUTHORITATIVE priority -- the To Do column orders by it. Map section -> Jira priority.
_SECTION_PRIORITY = {
    "critical": "Highest",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "future": "Low",
}


def _priority(status_text: str, section: str = "") -> str:
    # Section wins (authoritative); the status-text keyword heuristic is the fallback
    # for items outside the 4 priority sections (Production Readiness, Release Pipeline).
    sec = section.strip().lower()
    for key, pri in _SECTION_PRIORITY.items():
        if sec.startswith(key):
            return pri
    t = status_text.lower()
    if "molto alta" in t or "asap" in t or "massima" in t or "critical" in t:
        return "Highest"
    if "alta" in t or "high" in t:
        return "High"
    if "media" in t or "medium" in t:
        return "Medium"
    if "low" in t or "bassa" in t:
        return "Low"
    return "Medium"


def _status(status_text: str) -> str:
    t = status_text.lower()
    if "in corso" in t or "in progress" in t or "in-flight" in t or "delivering" in t:
        return "In Progress"
    if "done" in t and "open" in t:  # partial: some sub-work done, rest open
        return "In Progress"
    if "done" in t and "open" not in t:
        return "Done"
    if "parcheggiat" in t or "parked" in t or "on hold" in t:
        return "On Hold"
    if "in review" in t or ("review" in t and "open" not in t):
        return "In Review"
    if "open" in t:
        return "To Do"
    return "To Do"


def parse(md: str) -> list[dict[str, str]]:
    lines = md.splitlines()
    items: list[dict[str, str]] = []
    i = 0
    n = len(lines)
    current_section = ""
    while i < n:
        # Track the current H2 priority section (## Critical / ## High / ## Medium /
        # ## Low / ## Future) -- the authoritative priority for each item beneath it.
        if lines[i].startswith("## "):
            current_section = lines[i][3:].strip()
            i += 1
            continue
        m = _HEADING_TITLE_FIRST.match(lines[i]) or _HEADING.match(lines[i])
        if not m:
            i += 1
            continue
        fid, title = m.group("id"), m.group("title").strip()
        # keep only real backlog work-items (features / fixes / bugs); drop
        # section sub-headings (SSOT, P1-P6, "Two-tier", "Walking", ...) that
        # are not trackable items.
        if not _ITEM_ID.match(fid):
            i += 1
            continue
        # collect body until next ### heading
        body: list[str] = []
        status_text = ""
        j = i + 1
        while (
            j < n and not lines[j].startswith("### ") and not lines[j].startswith("## ")
        ):
            if not status_text:
                sm = _STATUS_LINE.search(lines[j])
                if sm:
                    status_text = sm.group("status").strip()
            body.append(lines[j])
            j += 1
        desc = " ".join(b.strip() for b in body if b.strip())
        desc = re.sub(r"\s+", " ", desc)[:900]
        items.append(
            {
                "Issue Type": "Story",
                "Summary": title[:250],
                "Description": desc,
                "Priority": _priority(status_text, current_section),
                "Status": _status(status_text),
                "Labels": fid.lower(),
            }
        )
        i = j
    return items


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    ap.add_argument("--backlog", type=Path, default=_BACKLOG)
    args = ap.parse_args()
    if not args.backlog.is_file():
        print(f"backlog not found: {args.backlog}", file=sys.stderr)
        return 2
    items = parse(args.backlog.read_text(encoding="utf-8"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "Issue Type",
                "Summary",
                "Description",
                "Priority",
                "Status",
                "Labels",
            ],
        )
        w.writeheader()
        w.writerows(items)
    print(f"wrote {len(items)} backlog items -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
