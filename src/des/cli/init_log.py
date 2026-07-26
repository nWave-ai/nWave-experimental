"""Legacy execution-log boundary for migration and read-only replay.

Usage:
    des init-log \\
      --project-dir docs/feature/my-feature/deliver \\
      --feature-id my-feature

The sole active workflow is atdd_pure and it is execution-log-free.  This
command therefore never creates a live execution log; historical logs remain
available only to the explicit migration/replay path.

Exit codes:
    1 = Refusal or validation error; no live execution log is created
    2 = Usage error (argparse default for missing/invalid arguments)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Workflow-mode resolution moved to the application layer (AD-05 layering fix):
# pure config-file reads belong above the CLI, not in this driving-port module.
# Re-exported here so existing `des.cli.init_log` importers resolve unchanged.
from des.application.workflow_mode import (
    WorkflowModeSelection,
    resolve_workflow_selection,
)


def resolve_dispatch_mode(
    project_dir: Path,
    *,
    audit_log: list[str] | None = None,
) -> WorkflowModeSelection:
    """Legacy resolver name retained only as a read-only refusal boundary."""
    del audit_log
    return resolve_workflow_selection(project_dir)


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for init_log CLI."""
    parser = argparse.ArgumentParser(
        prog="des init-log",
        description="Refuse live execution-log initialization; atdd_pure is ledger-backed.",
    )
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Path to the project directory where execution-log.json will be created",
    )
    parser.add_argument(
        "--feature-id",
        required=True,
        help="Feature identifier (kebab-case, e.g., my-feature)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the init_log CLI tool.

    Args:
        argv: Command-line arguments. Uses sys.argv[1:] if None.

    Returns:
        Exit code: 0=success, 1=validation error, 2=usage error.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    project_dir = Path(args.project_dir)

    # Validate project directory exists
    if not project_dir.is_dir():
        print(f"Error: Project directory does not exist: {project_dir}")
        return 1

    selection = resolve_workflow_selection(project_dir)
    if not selection.selected:
        print(
            f"Error: {selection.outcome}; {selection.reason_code or 'MODE_REPAIR_REQUIRED'}; "
            f"{selection.diagnostic}",
            file=sys.stderr,
        )
        return 1

    print(
        "Error: atdd_pure is execution-log-free; historical logs are read-only "
        "through explicit migration or replay.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
