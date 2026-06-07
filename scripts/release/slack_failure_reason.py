"""Determine failure reason for release pipeline Slack notifications.

Analyzes job results in pipeline order and returns a human-readable
reason for the first failure encountered. Used by all three release
workflows (dev, RC, stable) to produce consistent Slack messages.

CLI:
    python slack_failure_reason.py --jobs JSON --ci-gate-status STATUS

Output:
    JSON object: {"reason": "..."}

Exit codes:
    0 = success
"""

from __future__ import annotations

import argparse
import json


_CI_GATE_REASONS: dict[str, str] = {
    "pending": "CI pipeline is still running. Retry after it completes.",
    "failed": "CI pipeline failed on this commit. Fix CI first.",
    "none": "No CI run found for this commit. Push to trigger CI.",
}

_JOB_REASONS: dict[str, str] = {
    "validate-source": "Source tag validation failed. Check that the tag exists.",
    "ci-gate": "",  # handled separately via _CI_GATE_REASONS
    "version-calc": "Version calculation failed.",
    "build": "Distribution build failed.",
    "build-plugin": "Plugin build failed.",
    "version-bump": "Version bump on nwave-dev failed.",
    "tag-release": "Tag or release creation failed.",
    "pypi-publish": "PyPI publish failed.",
    "sync-beta": "Beta repo sync failed.",
    "sync-public": "Public repo sync failed.",
    "marker-tag": "Marker tag creation failed.",
}


def determine_reason(jobs: list[dict[str, str]], ci_gate_status: str) -> str:
    """Return human-readable failure reason from the first failing job."""
    for job in jobs:
        name = job["name"]
        result = job["result"]
        if result in ("success", "skipped"):
            continue

        if name == "ci-gate":
            return _CI_GATE_REASONS.get(
                ci_gate_status,
                f"CI gate blocked the release (status: {ci_gate_status or 'unknown'}).",
            )

        reason = _JOB_REASONS.get(name)
        if reason:
            return reason
        return f"{name} failed."

    return "Unknown failure. Check the workflow run for details."


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Determine release pipeline failure reason for Slack."
    )
    parser.add_argument(
        "--jobs",
        required=True,
        help='JSON array of {"name": "...", "result": "..."} in pipeline order',
    )
    parser.add_argument(
        "--ci-gate-status",
        default="",
        help="CI gate status output (pending/failed/none/green)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    jobs = json.loads(args.jobs)
    reason = determine_reason(jobs, args.ci_gate_status)
    print(json.dumps({"reason": reason}))


if __name__ == "__main__":
    main()
