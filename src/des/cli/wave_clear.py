"""des wave-clear -- the sanctioned operator command for clearing a wave floor.

Feature: fix-wave-bypass-recovery-truthful slice-02 (JOB-019, OB-B=B1). A
maintainer/LLM-operator facing a STALE inferred wave floor must clear it through
ONE sanctioned, loud, auditable command instead of hand-editing
``.nwave/wave-active/active.json``. The clear reuses the shipped
``WaveActiveWriter.clear`` via ``WaveActivationService.clear_floor`` (D11: the CLI
is that seam's first consumer).

Contract (the DESIGN ``des wave-clear`` CLI exit-code / floor-state table):

  des wave-clear --reason "<why>" --project-root PATH

  * floor present (a record) -> removed, exit 0 (CLEARED), loud + audited; the
    next legitimate dispatch no longer sees WAVE_MARKER_BYPASS.
  * --reason absent           -> argparse usage error exit 2, floor untouched,
    no audit (``required=True`` -- the human, not the tool, authorizes the clear).
  * floor absent              -> no-op SUCCESS exit 0 (NOOP_SUCCESS), idempotent,
    STILL audited.
  * floor corrupt/unreadable  -> INDETERMINATE degrade-LOUD exit 1, audited,
    NEVER a fabricated success.

Every non-usage run appends a ``wave.floor.clear*`` audit record (one JSONL line)
under ``--project-root`` so the authorized clear is recorded (who + why).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from des.adapters.driven.filesystem.wave_active_filesystem_store import (
    WaveActiveFilesystemStore,
)
from des.application.wave_activation_service import (
    ClearFloorOutcome,
    WaveActivationService,
)


# Exit codes the operator sees (the DESIGN contract table). CLEARED and
# NOOP_SUCCESS are both 0; INDETERMINATE is 1; a missing --reason is the argparse
# usage error (2), produced by argparse itself, never reached here.
_EXIT_BY_OUTCOME: dict[ClearFloorOutcome, int] = {
    ClearFloorOutcome.CLEARED: 0,
    ClearFloorOutcome.NOOP_SUCCESS: 0,
    ClearFloorOutcome.INDETERMINATE: 1,
}

# The audit event-type literal per outcome (all carry the ``wave.floor.clear``
# stem so the run is discoverable as a wave-floor clear event).
_EVENT_BY_OUTCOME: dict[ClearFloorOutcome, str] = {
    ClearFloorOutcome.CLEARED: "wave.floor.cleared",
    ClearFloorOutcome.NOOP_SUCCESS: "wave.floor.clear.noop",
    ClearFloorOutcome.INDETERMINATE: "wave.floor.clear.indeterminate",
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des wave-clear",
        description=(
            "Clear the wave-active floor through the sanctioned, audited command "
            "(never hand-edit active.json)."
        ),
    )
    parser.add_argument(
        "--reason",
        required=True,
        help=(
            "Why the floor is being cleared (the human GO token the audit record "
            "captures). REQUIRED -- the human, not the tool, authorizes the clear."
        ),
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="The project root holding the wave-active floor + the audit log.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Clear the wave-active floor; return the operator-visible exit code.

    A missing ``--reason`` exits 2 via argparse (the floor is never touched, no
    audit record). Otherwise the clear runs through the real service over the
    pinned floor under ``--project-root`` and every outcome writes an audit record.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    project_root: Path = args.project_root
    store = WaveActiveFilesystemStore()
    service = WaveActivationService(reader=store, writer=store)

    outcome = service.clear_floor(project_root)
    _write_audit_record(project_root, outcome, args.reason)
    _emit(outcome)
    return _EXIT_BY_OUTCOME[outcome]


def _emit(outcome: ClearFloorOutcome) -> None:
    """Print a loud, human-readable line so the clear is never silent."""
    messages = {
        ClearFloorOutcome.CLEARED: "wave-clear: CLEARED -- stale wave floor removed.",
        ClearFloorOutcome.NOOP_SUCCESS: (
            "wave-clear: NOOP_SUCCESS -- no wave floor present (idempotent no-op)."
        ),
        ClearFloorOutcome.INDETERMINATE: (
            "wave-clear: INDETERMINATE -- the wave floor is corrupt/unreadable; "
            "refusing to fabricate success (degrade-LOUD)."
        ),
    }
    stream = sys.stderr if outcome is ClearFloorOutcome.INDETERMINATE else sys.stdout
    print(messages[outcome], file=stream)


def _write_audit_record(
    project_root: Path, outcome: ClearFloorOutcome, reason: str
) -> None:
    """Append one ``wave.floor.clear*`` JSONL audit record under ``--project-root``.

    Written to ``{project_root}/.nwave/des/logs/wave-clear-<date>.jsonl`` -- a
    ``.jsonl`` file under the project root (append-only, loud + auditable), so the
    authorized clear is recorded with who/why on EVERY run (clear / no-op /
    indeterminate).
    """
    log_dir = project_root / ".nwave" / "des" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = log_dir / f"wave-clear-{today}.jsonl"

    entry = {
        "event": _EVENT_BY_OUTCOME[outcome],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "outcome": outcome.value,
        "reason": reason,
    }
    line = json.dumps(entry, separators=(",", ":"), sort_keys=True)
    with open(log_file, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
