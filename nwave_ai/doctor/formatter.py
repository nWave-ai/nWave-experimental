"""Doctor formatter — converts CheckResult lists to human or JSON output.

Step 01-01: stubs returning empty string / empty JSON object.
Step 01-03: implement render_human (emoji-prefixed lines) and render_json (stable structure).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from nwave_ai.common.check_result import CheckResult


def render_human(results: list[CheckResult]) -> str:
    """Render check results as human-readable text.

    Passes render as "✅ <check_name>: <message>".
    Failures render as "⚠️  <check_name>: <message>" followed by indented remediation.
    Ends with a summary line: "N/M checks passed, F failed".

    Args:
        results: Ordered list of CheckResult objects from run_doctor().

    Returns:
        Multi-line string with emoji-prefixed pass/fail lines.
    """
    lines: list[str] = []
    passed_count = sum(1 for r in results if r.passed)
    failed_count = len(results) - passed_count

    for result in results:
        if result.passed:
            lines.append(f"✅ {result.check_name}: {result.message}")
        else:
            lines.append(f"⚠️  {result.check_name}: {result.message}")
            if result.remediation:
                for rem_line in result.remediation.splitlines():
                    lines.append(f"   {rem_line}")

    lines.append("")
    lines.append(f"{passed_count}/{len(results)} checks passed, {failed_count} failed")
    return "\n".join(lines)


def render_json(results: list[CheckResult]) -> str:
    """Render check results as a JSON string.

    Structure: {"checks": [{"name", "passed", "message", "remediation"}],
                "summary": {"total", "passed", "failed"}}.

    Args:
        results: Ordered list of CheckResult objects from run_doctor().

    Returns:
        JSON string with stable keys.
    """
    return json.dumps(
        {
            "checks": [
                {
                    "name": r.check_name,
                    "passed": r.passed,
                    "message": r.message,
                    "remediation": r.remediation,
                }
                for r in results
            ],
            "summary": {
                "total": len(results),
                "passed": sum(1 for r in results if r.passed),
                "failed": sum(1 for r in results if not r.passed),
            },
        },
        indent=2,
    )
