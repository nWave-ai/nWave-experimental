"""CI gate: query GitHub Check Runs API and return CI status.

Exit codes: 0=green, 1=failed, 2=pending, 3=none, 4=API error.
"""

from __future__ import annotations

import httpx


def evaluate_check_runs(
    response_data: dict,
    sha: str,
    self_workflow: str | None = None,
) -> dict:
    """Evaluate GitHub check-runs response and return CI gate result."""
    check_runs = response_data.get("check_runs", [])
    short_sha = sha[:7]

    if self_workflow:
        check_runs = [cr for cr in check_runs if cr["name"] != self_workflow]

    details = [
        {"name": cr["name"], "status": cr["status"], "conclusion": cr.get("conclusion")}
        for cr in check_runs
    ]

    if not check_runs:
        return {
            "status": "none",
            "exit_code": 3,
            "message": f"No CI run found for {short_sha}. Push to trigger CI first.",
            "details": details,
        }

    # Check for any failures first
    failed = [cr["name"] for cr in check_runs if cr.get("conclusion") == "failure"]
    if failed:
        names = ", ".join(failed)
        return {
            "status": "failed",
            "exit_code": 1,
            "message": f"CI failed on {short_sha}: {names}",
            "details": details,
        }

    # Check for any pending/in-progress
    pending = [cr for cr in check_runs if cr["status"] != "completed"]
    if pending:
        return {
            "status": "pending",
            "exit_code": 2,
            "message": f"CI still running on {short_sha}, retry later",
            "details": details,
        }

    # All completed and successful
    count = len(check_runs)
    return {
        "status": "green",
        "exit_code": 0,
        "message": f"All {count} check-runs passed on {short_sha}",
        "details": details,
    }


def fetch_check_runs(repo: str, sha: str, token: str) -> dict:
    """Fetch check-runs from GitHub API."""
    url = f"https://api.github.com/repos/{repo}/commits/{sha}/check-runs"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    try:
        response = httpx.get(url, headers=headers, timeout=30)
    except httpx.ConnectTimeout:
        return {
            "exit_code": 4,
            "status": "error",
            "message": "GitHub API connection timed out.",
        }

    if response.status_code == 401:
        return {
            "exit_code": 4,
            "status": "error",
            "message": "GitHub API returned 401. Check GH_TOKEN permissions.",
        }

    if response.status_code != 200:
        return {
            "exit_code": 4,
            "status": "error",
            "message": f"GitHub API returned {response.status_code}.",
        }

    return response.json()
