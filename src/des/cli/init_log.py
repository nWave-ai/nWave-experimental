"""CLI: Initialize execution-log.json for a deliver session.

Usage:
    des init-log \\
      --project-dir docs/feature/my-feature/deliver \\
      --feature-id my-feature

Creates: {"schema_version": "5.0", "feature_id": "my-feature", "events": []}

Workflow-mode awareness (ADR-028 D4.1):
    The execution log belongs to the classic, roadmap-based DELIVER spine.
    The atdd_pure spine is roadmap-free and execution-log-free, so when the
    project's `.nwave/config.yaml` declares `workflow.mode: atdd_pure`,
    the init-log subcommand refuses to create the log and exits non-zero.
    Any other mode -- `classic`, an absent key, or an absent config file --
    is treated as classic and behaves exactly as before (zero regression).

Exit codes:
    0 = Success, file created
    1 = Validation error (file already exists, directory missing) or
        atdd_pure refusal (the execution log must not exist in that mode)
    2 = Usage error (argparse default for missing/invalid arguments)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Workflow-mode resolution moved to the application layer (AD-05 layering fix):
# pure config-file reads belong above the CLI, not in this driving-port module.
# Re-exported here so existing `des.cli.init_log` importers resolve unchanged.
from des.application.workflow_mode import (
    ATDD_PURE_MODE,
    CLASSIC_MODE,
    _read_workflow_mode,
    resolve_workflow_mode,
)


# The loud per-dispatch advisory emitted when a DELIVER dispatch resolves to the
# deprecated `classic` spine (classic-spine-decommission slice-13, release N of
# the staged ADR-032 cutover). Release N deprecates `classic`; it does NOT
# remove it -- the DELETE sweep is the N+1 sibling epic.
# The customer-facing migration note shipped with release N (M8). The
# deprecation advisory points here so an operator who sees the advisory has a
# single, discoverable place documenting the conversion procedure and the N+1
# removal timeline.
CLASSIC_SPINE_MIGRATION_NOTE = "docs/guides/classic-spine-migration.md"

CLASSIC_SPINE_DEPRECATED_ADVISORY = (
    "ClassicSpineDeprecated: workflow.mode is 'classic' -- the classic "
    "roadmap-based DELIVER spine is DEPRECATED (ADR-032 staged cutover, "
    "release N). It still resolves and runs as a fallback, but atdd_pure is "
    "now the default spine. Migrate this project to workflow.mode: atdd_pure; "
    "the classic spine is removed in the next release. See the migration "
    f"guide: {CLASSIC_SPINE_MIGRATION_NOTE}."
)


def resolve_dispatch_mode(
    project_dir: Path,
    *,
    audit_log: list[str] | None = None,
) -> str:
    """Resolve the DELIVER-dispatch `workflow.mode` for a project (slice-13).

    This is the release-N DELIVER-dispatch resolver of the staged ADR-032
    cutover. It differs from `_resolve_workflow_mode` in exactly one bounded
    way: an *absent* `workflow.mode` resolves to ``atdd_pure`` (the new
    default), not ``classic``. Explicit modes are honoured unchanged.

    When the project explicitly configures `workflow.mode: classic`, the
    deprecated classic spine still resolves and runs (fallback floor intact),
    but a loud `ClassicSpineDeprecated` advisory is emitted to stderr and, when
    `audit_log` is supplied, appended to it as one advisory record. The
    resolution result is unchanged by the advisory (bounded-change contract).

    The absent-key default is now the SSOT `resolve_workflow_mode` answer
    (`atdd_pure`, DDD-7); this function adds only the explicit-classic
    deprecation advisory on top of that one resolution. It uses the raw
    `_read_workflow_mode` to distinguish an *explicit* classic (advisory fired)
    from the absent-key default (no advisory) -- the advisory must not fire on
    an unconfigured project, whose canonical answer is atdd_pure.
    """
    mode = _read_workflow_mode(project_dir)
    if mode is None:
        return ATDD_PURE_MODE
    if mode == CLASSIC_MODE:
        print(CLASSIC_SPINE_DEPRECATED_ADVISORY, file=sys.stderr)
        if audit_log is not None:
            audit_log.append(CLASSIC_SPINE_DEPRECATED_ADVISORY)
    return mode


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for init_log CLI."""
    parser = argparse.ArgumentParser(
        prog="des init-log",
        description="Initialize execution-log.json for a deliver session.",
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

    # Refuse under the atdd_pure spine: it is roadmap-free and
    # execution-log-free (ADR-028 D4.1). No log is created.
    if resolve_workflow_mode(project_dir) == ATDD_PURE_MODE:
        print(
            "Error: workflow.mode is atdd_pure -- the ATDD-pure spine is "
            "roadmap-free and execution-log-free (ADR-028 D4.1).\n"
            "       No execution-log.json is created. The atdd_pure DELIVER "
            "spine tracks progress via the AT-completion ledger instead.\n"
            "       To create an execution log, set workflow.mode to classic "
            "in .nwave/config.yaml.",
            file=sys.stderr,
        )
        return 1

    log_path = project_dir / "execution-log.json"

    # Fail if file already exists
    if log_path.exists():
        print(f"Error: execution-log.json already exists at {log_path}")
        return 1

    # Create execution log with the ADR-025 v5.0 (3-phase canon) schema, so new
    # DELIVER logs default to RED/GREEN/COMMIT (issue #65). Legacy v4 logs stay
    # valid for audit-log replay via per-log dispatch.
    log_data = {
        "schema_version": "5.0",
        "feature_id": args.feature_id,
        "events": [],
    }
    log_path.write_text(json.dumps(log_data, indent=2))

    print(f"Created execution-log.json at {log_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
