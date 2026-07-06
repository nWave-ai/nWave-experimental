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
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from backlog_to_jira_csv import parse


_REPO = Path(__file__).resolve().parents[1]
_BACKLOG = _REPO / "docs" / "product" / "backlog.md"
_PRIORITY_MAP = {"Highest": "Highest", "High": "High", "Medium": "Medium", "Low": "Low"}
# backlog status (from backlog_to_jira_csv._status) -> WTBD workflow status name (Italian).
_STATUS_TO_JIRA = {
    "Done": "Completata",
    "On Hold": "Blocked",
    "In Review": "In revisione",
    "In Progress": "In corso",
    "To Do": "Da completare",
}

#: A Slice-Plan table data row: ``| slice-NN | value statement | ...``.
_SLICE_ROW_RE = re.compile(r"^\|\s*(slice-\d+)\s*\|\s*([^|]+?)\s*\|")


def _slice_plan(fid: str) -> list[tuple[str, str]]:
    """Parse a feature's Slice Plan into ``(slice_id, value_statement)`` rows so
    each slice can mirror as a Sub-task. Scoped to the ``[REF] Slice Plan``
    section (slice-ids in DoD/Test-Reuse tables are NOT miscounted). Empty list
    when the feature has no ``docs/feature/{fid}/feature-delta.md`` -- degrade-safe.
    """
    fd = _REPO / "docs" / "feature" / fid / "feature-delta.md"
    if not fd.is_file():
        return []
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    in_plan = False
    for line in fd.read_text(encoding="utf-8").splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#") and "Slice Plan" in line:
            in_plan = True
            continue
        if in_plan and stripped.startswith("## ") and "Slice Plan" not in line:
            break  # reached the next section
        if not in_plan:
            continue
        m = _SLICE_ROW_RE.match(line.strip())
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            rows.append((m.group(1), m.group(2).strip()[:180]))
    return rows


def _done_slices(fid: str) -> set[str]:
    """Slice-ids attested ``SliceCommitVerified`` in the AT-completion ledger --
    the substance of 'this slice is done'. Empty set when no ledger exists."""
    led = _REPO / ".nwave" / "telemetry" / "atdd-pure" / f"{fid}.jsonl"
    if not led.is_file():
        return set()
    done: set[str] = set()
    for raw in led.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw.startswith("{"):
            continue
        try:
            d = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if d.get("event") == "SliceCommitVerified":
            # the ledger records the singular ``slice_id``; the CLI STDOUT event
            # uses the plural ``slice_ids`` list -- accept BOTH.
            if d.get("slice_id"):
                done.add(d["slice_id"])
            for s in d.get("slice_ids", []):
                done.add(s)
    return done


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
            if e.code == 401:
                sys.exit(
                    "Jira auth FAILED (401): the API token is invalid or expired.\n"
                    "  WHY: an unauthenticated request is treated as ANONYMOUS -- "
                    "searches return EMPTY, so every backlog item would look like a "
                    "CREATE and mass-duplicate. Refusing to run.\n"
                    "  FIX: regenerate a token at "
                    "https://id.atlassian.com/manage-profile/security/api-tokens "
                    "-- set the expiry to the MAX (up to 1 year) so this does not "
                    "recur -- then update JIRA_API_TOKEN in ~/.nwave/jira-mirror.env "
                    "and re-run."
                )
            sys.exit(f"Jira {method} {path} -> {e.code}: {e.read().decode()[:400]}")

    def verify_auth(self) -> None:
        """Fail LOUD if the token does not authenticate -- NEVER run anonymously.

        An unauthenticated Jira search returns an EMPTY result set (not a 401),
        which makes `find_by_label` return None for every item, so the upsert
        classifies EVERY backlog item as a CREATE and mass-duplicates the board.
        This preflight forces the 401 surface (via `/myself`) before any write.
        """
        me = self._call("GET", "/rest/api/3/myself")
        who = me.get("emailAddress") or me.get("displayName") or "?"
        print(f"authenticated as {who}")

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
        # Set the Jira priority from the backlog section (was never set -> everything
        # showed default priority in Jira, so To Do could not be urgency-ordered).
        jira_priority = _PRIORITY_MAP.get(item.get("Priority", ""), "Medium")
        fields["priority"] = {"name": jira_priority}
        if (
            self.epic
        ):  # parent the issue under the nWave-OSS epic so it shows as its child
            fields["parent"] = {"key": self.epic}
        existing = self.find_by_label(project, label)
        if existing:
            if dry:
                print(f"UPDATE {existing} -> {item['Status']}")
                return existing
            self._call("PUT", f"/rest/api/3/issue/{existing}", {"fields": fields})
            moved = self._sync_status(existing, item["Status"])
            print(f"updated {existing} {moved}")
            return existing
        if dry:
            print(f"CREATE {label} -> {item['Status']}")
            return (
                None  # no key exists yet in dry mode -- subtasks previewed unparented
            )
        fields |= {
            "project": {"key": project},
            "issuetype": {"name": "Story"},
            "labels": [label, "backlog-mirror"],
        }
        r = self._call("POST", "/rest/api/3/issue", {"fields": fields})
        key = r.get("key")
        moved = self._sync_status(key, item["Status"]) if key else ""
        print(f"created {key} {moved}")
        return key

    def subtask_type_id(self, project: str) -> str | None:
        """Discover the project's Sub-task issue-type id at runtime (never
        hard-code -- the name is locale-dependent, e.g. 'Sottotask'). Returns
        None if the project has no subtask type (slices then skip, degrade-safe).
        """
        r = self._call("GET", f"/rest/api/3/issue/createmeta/{project}/issuetypes")
        for it in r.get("issueTypes", r.get("values", [])):
            if it.get("subtask"):
                return str(it["id"])
        return None

    def upsert_subtask(
        self,
        project: str,
        parent_key: str,
        label: str,
        summary: str,
        status: str,
        subtask_type_id: str,
        dry: bool,
    ) -> None:
        """Mirror ONE slice as a Sub-task under its feature's Story. Matched by
        the unique ``mirror:<fid>:<slice-id>`` label (idempotent upsert)."""
        existing = self.find_by_label(project, label)
        if existing:
            if dry:
                print(f"  UPDATE-SUB {existing} -> {status}")
                return
            self._call(
                "PUT", f"/rest/api/3/issue/{existing}", {"fields": {"summary": summary}}
            )
            self._sync_status(existing, status)
            print(f"  updated-sub {existing} -> {status}")
            return
        if dry:
            print(f"  CREATE-SUB {label} -> {status}")
            return
        fields = {
            "project": {"key": project},
            "parent": {"key": parent_key},
            "issuetype": {"id": subtask_type_id},
            "summary": summary[:250],
            "labels": [label, "backlog-mirror-slice"],
        }
        r = self._call("POST", "/rest/api/3/issue", {"fields": fields})
        key = r.get("key")
        if key:
            self._sync_status(key, status)
        print(f"  created-sub {key} -> {status}")

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

    def rerank_by_priority(self, project: str) -> None:
        """Rank every Story in ``project`` by priority (Highest->Low) so the board
        columns -- the To Do column especially -- read most-urgent-first. Jira orders
        a column by Lexorank, NOT the priority field, so setting the field alone does
        not reorder the board; this pass sets the rank. Stable within a priority (keeps
        the existing backlog order). Batches of 50 after a moving anchor."""
        order = {"Highest": 0, "High": 1, "Medium": 2, "Low": 3, "Lowest": 4}
        rows: list[tuple[str, str]] = []
        token: str | None = None
        while True:
            body: dict = {
                "jql": f'project = "{project}" AND issuetype = Story ORDER BY Rank ASC',
                "fields": ["priority"],
                "maxResults": 100,
            }
            if token:
                body["nextPageToken"] = token
            r = self._call("POST", "/rest/api/3/search/jql", body)
            for it in r.get("issues", []):
                pr = (it["fields"].get("priority") or {}).get("name", "Medium")
                rows.append((it["key"], pr))
            token = r.get("nextPageToken")
            if not token:
                break
        rows.sort(
            key=lambda kp: order.get(kp[1], 2)
        )  # stable: keeps within-priority order
        keys = [k for k, _ in rows]
        if len(keys) < 2:
            return
        anchor, i = keys[0], 1
        while i < len(keys):
            batch = keys[i : i + 50]
            self._call(
                "PUT",
                "/rest/agile/1.0/issue/rank",
                {"issues": batch, "rankAfterIssue": anchor},
            )
            anchor = batch[-1]
            i += 50
        print(f"reranked {len(keys)} stories by priority (most-urgent first)")


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
    # Order by urgency (Highest -> Low) so the create/upsert order -- and thus the
    # To Do column rank for newly-created issues -- runs most-urgent-first. Stable
    # sort keeps within-priority backlog order. (Existing issues keep their rank on
    # update; a board "sort To Do by Priority" or an explicit rank pass reorders those.)
    _rank = {"Highest": 0, "High": 1, "Medium": 2, "Low": 3}
    items.sort(key=lambda it: _rank.get(it.get("Priority", "Medium"), 2))
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
    jira.verify_auth()  # fail LOUD on a dead token -- never run anonymously
    subtask_type = jira.subtask_type_id(project)
    for it in items:
        fid = it["Labels"]
        story_key = jira.upsert(project, it, f"mirror:{fid}", args.dry_run)
        # Mirror each slice of an in-flight feature as a Sub-task so the board
        # shows slice-level progress ("a che punto siamo"). Done iff the ledger
        # attests SliceCommitVerified; every other slice is To Do.
        slices = _slice_plan(fid)
        if not slices:
            continue
        done = _done_slices(fid)
        for sid, val in slices:
            status = "Done" if sid in done else "To Do"
            if story_key and subtask_type:
                jira.upsert_subtask(
                    project,
                    story_key,
                    f"mirror:{fid}:{sid}",
                    f"{sid}: {val}",
                    status,
                    subtask_type,
                    args.dry_run,
                )
            else:
                print(
                    f"  (skipped SUB {fid}:{sid} -> {status}: no parent/subtask-type)"
                )
    if not args.dry_run:
        jira.rerank_by_priority(project)  # To Do column reads most-urgent-first
    print(f"\n{len(items)} backlog items mirrored to {project}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
