"""CLI: Append a phase entry to execution-log.yaml with a real UTC timestamp.

Usage:
    PYTHONPATH=src python -m des.cli.log_phase \\
      --project-dir docs/feature/build-pipeline-elimination \\
      --step-id 02-03 \\
      --phase GREEN \\
      --status EXECUTED \\
      --data PASS

stdout (agent sees real timestamp):
    02-03|GREEN|EXECUTED|PASS|2026-02-10T20:28:18Z

Exit codes:
    0 = Success, entry appended
    1 = Validation error (invalid phase, invalid skip prefix, missing log file)
    2 = Usage error (argparse default for missing/invalid arguments)
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from des.domain.tdd_schema import get_tdd_schema


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for log_phase CLI."""
    parser = argparse.ArgumentParser(
        prog="des.cli.log_phase",
        description="Append a phase entry to execution-log.yaml with a real UTC timestamp.",
    )
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Path to the project directory containing execution-log.yaml",
    )
    parser.add_argument(
        "--step-id",
        required=True,
        help="Step identifier (e.g., 02-03)",
    )
    parser.add_argument(
        "--phase",
        required=True,
        help="TDD phase name (e.g., GREEN, PREPARE)",
    )
    parser.add_argument(
        "--status",
        required=True,
        choices=["EXECUTED", "SKIPPED"],
        help="Phase execution status",
    )
    parser.add_argument(
        "--data",
        required=True,
        help="Outcome data (e.g., PASS, FAIL, or skip reason with prefix)",
    )
    parser.add_argument(
        "--turns-used",
        type=int,
        default=None,
        help="Optional: number of turns consumed during this step",
    )
    parser.add_argument(
        "--tokens-used",
        type=int,
        default=None,
        help="Optional: number of tokens consumed during this step",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the log_phase CLI tool.

    Args:
        argv: Command-line arguments. Uses sys.argv[1:] if None.

    Returns:
        Exit code: 0=success, 1=validation error, 2=usage error.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    schema = get_tdd_schema()

    # Validate phase name against schema
    if args.phase not in schema.tdd_phases:
        print(
            f"Error: Invalid phase '{args.phase}'. "
            f"Valid phases: {', '.join(schema.tdd_phases)}"
        )
        return 1

    # Validate skip prefix for SKIPPED status
    if args.status == "SKIPPED":
        all_skip_prefixes = schema.valid_skip_prefixes + schema.blocking_skip_prefixes
        has_valid_prefix = any(
            args.data.startswith(prefix) for prefix in all_skip_prefixes
        )
        if not has_valid_prefix:
            print(
                f"Error: SKIPPED status requires a valid skip prefix. "
                f"Valid prefixes: {', '.join(all_skip_prefixes)}"
            )
            return 1

    # Check execution-log.yaml exists
    project_dir = Path(args.project_dir)
    log_path = project_dir / "execution-log.yaml"
    if not log_path.exists():
        print(f"Error: execution-log.yaml not found at {log_path}")
        return 1

    # Generate real UTC timestamp
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Build entry string
    entry = f"{args.step_id}|{args.phase}|{args.status}|{args.data}|{timestamp}"
    if args.turns_used is not None and args.tokens_used is not None:
        entry = f"{entry}|{args.turns_used}|{args.tokens_used}"

    # YAML read-modify-write
    log_data = yaml.safe_load(log_path.read_text())
    if log_data is None:
        log_data = {}
    if "events" not in log_data:
        log_data["events"] = []
    log_data["events"].append(entry)
    log_path.write_text(yaml.dump(log_data, default_flow_style=False))

    # Print entry to stdout
    print(entry)

    return 0


if __name__ == "__main__":
    sys.exit(main())
