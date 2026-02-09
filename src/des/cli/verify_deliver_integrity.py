"""CLI: Verify deliver integrity before finalize.

Usage:
    python -m des.cli.verify_deliver_integrity docs/feature/{project-id}/

Reads roadmap.yaml and execution-log.yaml from the project directory,
cross-references step IDs against execution-log entries, and reports
violations (steps without DES traces or with incomplete TDD phases).

Exit codes:
    0 = All steps verified
    1 = Integrity violations found
    2 = Usage error
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from des.domain.deliver_integrity_verifier import DeliverIntegrityVerifier
from des.domain.tdd_schema import get_tdd_schema


def _parse_execution_log(exec_log: dict) -> dict[str, list[str]]:
    """Parse execution-log.yaml events into step_id -> list[phase_name] mapping.

    Event format: "step_id|phase_name|status|outcome|timestamp"
    """
    entries: dict[str, list[str]] = {}
    for event in exec_log.get("events", []):
        if not isinstance(event, str):
            continue
        parts = event.split("|")
        if len(parts) >= 2:
            step_id = parts[0]
            phase_name = parts[1]
            entries.setdefault(step_id, []).append(phase_name)
    return entries


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python -m des.cli.verify_deliver_integrity <project-dir>")
        return 2

    project_dir = Path(sys.argv[1])

    roadmap_path = project_dir / "roadmap.yaml"
    exec_log_path = project_dir / "execution-log.yaml"

    if not roadmap_path.exists():
        print(f"Error: roadmap.yaml not found at {roadmap_path}")
        return 2

    if not exec_log_path.exists():
        print(f"Error: execution-log.yaml not found at {exec_log_path}")
        return 2

    roadmap = yaml.safe_load(roadmap_path.read_text())
    exec_log = yaml.safe_load(exec_log_path.read_text())

    step_ids = [s["step_id"] for s in roadmap.get("steps", [])]
    entries = _parse_execution_log(exec_log)

    schema = get_tdd_schema()
    verifier = DeliverIntegrityVerifier(required_phases=list(schema.tdd_phases))
    result = verifier.verify(step_ids, entries)

    if result.is_valid:
        print(f"All {result.steps_verified} steps have complete DES traces")
        return 0
    else:
        print(f"INTEGRITY VIOLATIONS: {result.reason}")
        for v in result.violations:
            print(
                f"  - {v.step_id}: {v.phase_count}/7 phases, "
                f"missing: {v.missing_phases}"
            )
        return 1


if __name__ == "__main__":
    sys.exit(main())
