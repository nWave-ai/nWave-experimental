"""KPI measurement script for nWave contributor attribution adoption.

Queries GitHub Search API for Co-Authored-By commits and PyPI API
for download stats. Outputs markdown report with adoption metrics.

Stdlib only (urllib). No new dependencies.
"""

import json
import sys
import urllib.request
from datetime import datetime, timezone


_GITHUB_SEARCH_URL = "https://api.github.com/search/commits?q=Co-Authored-By:nWave"
_PYPI_STATS_URL = "https://pypistats.org/api/packages/nwave-ai/recent"


def _fetch_url(url: str) -> bytes:
    """Fetch URL content, returning bytes."""
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github.cloak-preview+json",
            "User-Agent": "nWave-adoption-metrics/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()


def _fetch_github_commits() -> dict:
    """Query GitHub Search API for Co-Authored-By commits."""
    try:
        data = _fetch_url(_GITHUB_SEARCH_URL)
        return json.loads(data)
    except Exception:
        return {"total_count": 0, "items": []}


def _fetch_pypi_downloads() -> dict:
    """Query PyPI API for nwave-ai download stats."""
    try:
        data = _fetch_url(_PYPI_STATS_URL)
        return json.loads(data)
    except Exception:
        return {"data": {"last_day": 0, "last_week": 0, "last_month": 0}}


def calculate_adoption_metrics(commit_count: int, monthly_downloads: int) -> dict:
    """Calculate adoption metrics from raw counts.

    Args:
        commit_count: Number of commits with Co-Authored-By trailer.
        monthly_downloads: Monthly PyPI download count.

    Returns:
        Dict with commit_count, monthly_downloads, adoption_ratio.
    """
    if monthly_downloads > 0:
        adoption_ratio = round(commit_count / monthly_downloads, 4)
    else:
        adoption_ratio = 0.0

    return {
        "commit_count": commit_count,
        "monthly_downloads": monthly_downloads,
        "adoption_ratio": adoption_ratio,
    }


def generate_report() -> str:
    """Generate a markdown adoption report from API data.

    Returns:
        Markdown-formatted report string.
    """
    github_data = _fetch_github_commits()
    pypi_data = _fetch_pypi_downloads()

    commit_count = github_data.get("total_count", 0)
    downloads = pypi_data.get("data", {})
    monthly_downloads = downloads.get("last_month", 0)
    weekly_downloads = downloads.get("last_week", 0)
    daily_downloads = downloads.get("last_day", 0)

    metrics = calculate_adoption_metrics(commit_count, monthly_downloads)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    report = f"""# nWave Adoption Report

Generated: {now}

## Attribution Commits

| Metric | Value |
|--------|-------|
| Total commits with Co-Authored-By | {commit_count} |

## PyPI Downloads (nwave-ai)

| Period | Downloads |
|--------|-----------|
| Last day | {daily_downloads} |
| Last week | {weekly_downloads} |
| Last month | {monthly_downloads} |

## Adoption Metrics

| Metric | Value |
|--------|-------|
| Adoption ratio (commits/downloads) | {metrics["adoption_ratio"]} |
"""
    return report


def main() -> int:
    """CLI entry point for measure_adoption.py."""
    output_format = "markdown"

    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--output" and i < len(sys.argv) - 1:
            output_format = sys.argv[i + 1]

    if output_format != "markdown":
        print(f"Unsupported output format: {output_format}", file=sys.stderr)
        return 1

    report = generate_report()
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
