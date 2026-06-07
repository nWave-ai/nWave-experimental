#!/usr/bin/env python3
"""Validate OpenCode platform contracts against empirical specifications.

Checks that nWave templates (DES plugin, hooks plugin) conform to the
OpenCode plugin API as documented in @opencode-ai/plugin v1.2.27+.

Each validator returns a list of Finding objects. Zero findings = compliant.

Usage:
    python scripts/validation/validate_platform_contracts.py
    python scripts/validation/validate_platform_contracts.py --project-root /path/to/repo

Exit codes:
    0 = all checks pass
    1 = errors found
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    """A single contract violation found during validation."""

    anomaly_id: str
    severity: str  # "error" | "warning"
    file: str
    message: str


# ---------------------------------------------------------------------------
# DES template validation
# ---------------------------------------------------------------------------

# Contract rules derived from OpenCode plugin API (v1.2.27+)
# Each rule checks one aspect of the template against the empirical spec.

_IMPORT_PATTERN = re.compile(
    r'import\s+type\s*\{\s*Plugin\s*\}\s*from\s*["\']@opencode-ai/plugin["\']'
)

_BAD_IMPORT_PATTERN = re.compile(
    r'import\s+type\s*\{[^}]*PluginContext[^}]*\}\s*from\s*["\']opencode["\']'
)

_IS_SUBAGENT_PATTERN = re.compile(r"\bis_subagent\b")

_TOOL_EXECUTE_BEFORE_HANDLER = re.compile(
    r'"tool\.execute\.before"\s*:\s*async\s*\((.+?)\)\s*=>',
    re.DOTALL,
)


def _has_two_parameters(handler_params: str) -> bool:
    """Check if handler parameter list contains exactly two parameters.

    Handles complex type annotations with nested braces and angle brackets
    (e.g., Record<string, unknown>) by tracking nesting depth when
    scanning for parameter-separating commas.
    """
    depth = 0
    comma_count = 0
    for char in handler_params:
        if char in ("{", "<"):
            depth += 1
        elif char in ("}", ">"):
            depth -= 1
        elif char == "," and depth == 0:
            comma_count += 1
    return comma_count == 1


def validate_des_template(template_content: str) -> list[Finding]:
    """Validate DES plugin template against OpenCode plugin API contracts.

    Args:
        template_content: The full text of opencode-des-plugin.ts.template.

    Returns:
        List of findings. Empty list means the template is compliant.
    """
    findings: list[Finding] = []
    template_file = "opencode-des-plugin.ts.template"

    # ANOMALY-3: Import must be Plugin from '@opencode-ai/plugin'
    if not _IMPORT_PATTERN.search(template_content):
        if _BAD_IMPORT_PATTERN.search(template_content):
            findings.append(
                Finding(
                    anomaly_id="ANOMALY-3",
                    severity="error",
                    file=template_file,
                    message=(
                        "Import uses 'PluginContext' from 'opencode'. "
                        "Must import 'Plugin' from '@opencode-ai/plugin'."
                    ),
                )
            )
        else:
            findings.append(
                Finding(
                    anomaly_id="ANOMALY-3",
                    severity="error",
                    file=template_file,
                    message=(
                        "Missing correct import. "
                        "Must import 'Plugin' from '@opencode-ai/plugin'."
                    ),
                )
            )

    # ANOMALY-4: No is_subagent references anywhere
    is_subagent_matches = _IS_SUBAGENT_PATTERN.findall(template_content)
    if is_subagent_matches:
        findings.append(
            Finding(
                anomaly_id="ANOMALY-4",
                severity="error",
                file=template_file,
                message=(
                    f"Found {len(is_subagent_matches)} reference(s) to 'is_subagent'. "
                    "OpenCode plugin API has no sub-agent concept."
                ),
            )
        )

    # ANOMALY-5: tool.execute.before must use two-parameter (input, output) signature
    handler_match = _TOOL_EXECUTE_BEFORE_HANDLER.search(template_content)
    if handler_match:
        params_text = handler_match.group(1)
        if not _has_two_parameters(params_text):
            findings.append(
                Finding(
                    anomaly_id="ANOMALY-5",
                    severity="error",
                    file=template_file,
                    message=(
                        "tool.execute.before uses single-parameter signature. "
                        "Must use two-parameter (input, output) signature."
                    ),
                )
            )
    else:
        findings.append(
            Finding(
                anomaly_id="ANOMALY-5",
                severity="error",
                file=template_file,
                message=(
                    "tool.execute.before handler not found. "
                    "Must use two-parameter (input, output) signature."
                ),
            )
        )

    return findings


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate OpenCode platform contracts."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(),
        help="Project root directory (default: current directory)",
    )
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    all_findings: list[Finding] = []

    # Validate DES template
    des_template = (
        project_root / "nWave" / "templates" / "opencode-des-plugin.ts.template"
    )
    if des_template.is_file():
        content = des_template.read_text(encoding="utf-8")
        findings = validate_des_template(content)
        all_findings.extend(findings)
    else:
        print(f"WARNING: DES template not found at {des_template}")

    # Report
    if all_findings:
        for finding in all_findings:
            print(
                f"  [{finding.severity.upper()}] {finding.anomaly_id} "
                f"{finding.file}: {finding.message}"
            )
        error_count = sum(1 for f in all_findings if f.severity == "error")
        warning_count = len(all_findings) - error_count
        print(f"\nFAILED: {error_count} error(s), {warning_count} warning(s)")
        return 1

    print("PASSED: All platform contracts compliant")
    return 0


if __name__ == "__main__":
    sys.exit(main())
