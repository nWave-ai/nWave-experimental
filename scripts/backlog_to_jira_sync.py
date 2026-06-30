#!/usr/bin/env python3
"""Direct one-way mirror: in-repo backlog SSOT -> a live Jira Cloud instance (REST API).

Idempotent upsert, re-runnable: each backlog item is matched in Jira by a unique
label ``mirror:<fid>``; found -> update summary+description, else -> create. The
backlog (``docs/product/backlog.md``) stays the single source of truth; Jira is a
read-only visibility mirror. NEVER sync Jira -> backlog (second-SSOT drift).

Stdlib only (urllib) per the Python-only dependency mandate -- no `requests`.

Credentials come from the environment (NEVER hard-code, never paste a token in
a chat transcript). Set them in a gitignored file and source it, e.g.:

    # ~/.nwave/jira-mirror.env   (chmod 600, gitignored)
    export JIRA_URL="https://YOURSITE.atlassian.net"
    export JIRA_EMAIL="you@example.com"
    export JIRA_API_TOKEN="<token from id.atlassian.com/manage-profile/security/api-tokens>"
    export JIRA_PROJECT_KEY="NW"

    source ~/.nwave/jira-mirror.env && uv run python scripts/backlog_to_jira_sync.py
    # add --dry-run to preview create/update actions without touching Jira.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from backlog_to_jira_csv import parse


_REPO = Path(__file__).resolve().parents[1]
_BACKLOG = _REPO / "docs" / "product" / "backlog.md"
_PRIORITY_MAP = {"Highest": "Highest", "High": "High", "Medium": "Medium"}
# backlog status (from backlog_to_jira_csv._status) -> WTBD workflow status name (Italian).
_STATUS_TO_JIRA = {
    "Done": "Completata",
    "On Hold": "Blocked",
    "In Review": "In revisione",
    "In Progress": "In corso",
    "To Do": "Da completare",
}


def _env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        sys.exit(f"missing env var {name} (source your gitignored jira-mirror.env)")
    return v


class Jira:
    def __init__(self, url: str, email: str, token: str, epic: str = "") -> None:
        self.base = url.rstrip("/")
        self.epic = epic
        cred = base64.b64encode(f"{email}:{token}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {cred}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _call(self, method: str, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            f"{self.base}{path}", data=data, headers=self.headers, method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            sys.exit(f"Jira {method} {path} -> {e.code}: {e.read().decode()[:400]}")

    def find_by_label(self, project: str, label: str) -> str | None:
        jql = f'project = "{project}" AND labels = "{label}"'
        r = self._call(
            "POST",
            "/rest/api/3/search/jql",
            {"jql": jql, "fields": ["key"], "maxResults": 1},
        )
        issues = r.get("issues", [])
        return issues[0]["key"] if issues else None

    def upsert(self, project: str, item: dict, label: str, dry: bool) -> str:
        adf = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": item["Description"] or "(no description)",
                        }
                    ],
                }
            ],
        }
        fields = {"summary": item["Summary"], "description": adf}
        if (
            self.epic
        ):  # parent the issue under the nWave-OSS epic so it shows as its child
            fields["parent"] = {"key": self.epic}
        existing = self.find_by_label(project, label)
        if existing:
            if dry:
                return f"UPDATE {existing} -> {item['Status']}"
            self._call("PUT", f"/rest/api/3/issue/{existing}", {"fields": fields})
            moved = self._sync_status(existing, item["Status"])
            return f"updated {existing} {moved}"
        if dry:
            return f"CREATE {label} -> {item['Status']}"
        fields |= {
            "project": {"key": project},
            "issuetype": {"name": "Story"},
            "labels": [label, "backlog-mirror"],
        }
        r = self._call("POST", "/rest/api/3/issue", {"fields": fields})
        key = r.get("key")
        moved = self._sync_status(key, item["Status"]) if key else ""
        return f"created {key} {moved}"

    def _sync_status(self, key: str, target_status: str) -> str:
        """Transition the issue to the backlog status (Jira create ignores status).

        Jira sets status only via a workflow transition, not the create/update field
        -- so a created issue always starts at the initial status. Map the backlog
        status to the WTBD workflow status name and fire the matching transition.
        """
        jira_name = _STATUS_TO_JIRA.get(target_status)
        if not jira_name or jira_name == "Da completare":  # already the initial status
            return ""
        r = self._call("GET", f"/rest/api/3/issue/{key}/transitions")
        for t in r.get("transitions", []):
            if (t.get("to") or {}).get("name") == jira_name:
                self._call(
                    "POST",
                    f"/rest/api/3/issue/{key}/transitions",
                    {"transition": {"id": t["id"]}},
                )
                return f"-> {jira_name}"
        return f"(no transition to {jira_name})"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--backlog", type=Path, default=_BACKLOG)
    args = ap.parse_args()

    items = parse(args.backlog.read_text(encoding="utf-8"))
    # Also mirror completed work from done.md (forced status Done -> Completata), so the
    # board shows the full picture (done + in-progress + to-do), not just open work.
    done_md = args.backlog.parent / "done.md"
    if done_md.is_file():
        done_items = parse(done_md.read_text(encoding="utf-8"))
        for it in done_items:
            it["Status"] = "Done"
        items += done_items
    if args.dry_run and not os.environ.get("JIRA_URL"):
        for it in items:
            label = f"mirror:{it['Labels']}"
            print(f"DRY {('CREATE' if True else '')} {label} :: {it['Summary'][:70]}")
        print(f"\n{len(items)} items (dry-run, no Jira env -> preview only)")
        return 0

    jira = Jira(
        _env("JIRA_URL"),
        _env("JIRA_EMAIL"),
        _env("JIRA_API_TOKEN"),
        epic=os.environ.get("JIRA_EPIC_KEY", "").strip(),
    )
    project = _env("JIRA_PROJECT_KEY")
    for it in items:
        label = f"mirror:{it['Labels']}"
        print(jira.upsert(project, it, label, args.dry_run))
    print(f"\n{len(items)} backlog items mirrored to {project}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
