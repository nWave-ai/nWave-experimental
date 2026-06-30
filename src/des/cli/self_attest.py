"""des self-attest -- the thin CLI driver over the self-attest verdict classifier.

Feature: f-coherence-and-attestation slice-06 (the gate-stack WIRING slice). The
dual-source self-attest verdict layer (slice-04, ``des.domain.self_attest.classify``)
ships as pure domain with no CLI surface; this module is the operator-visible
``des self-attest`` subcommand that REACHES it. It is a THIN driver: it reads a
dual-source verdict record (a JSON file carrying the mechanical-gate verdict, the
LLM-reviewer verdict, a reference to the mechanical evidence, and a watchdog/timeout
signal), delegates to the UNCHANGED ``classify``, and prints the resulting §17
``GateVerdict`` token (ADR-GV-001, the FIVE verdicts -- consumed unchanged, no sixth)
as a JSON line on stdout.

NO domain logic lives here -- a machine YES never authorizes, a bare-LLM say-so
floors to UNVERIFIED, a divergence / watchdog degrades LOUD to INDETERMINATE: every
one of those decisions is made by ``classify`` and merely surfaced here.

Contract::

  des self-attest --record <path/to/verdict_record.json>

The record is a flat JSON object::

  {
    "mechanical_verdict": "pass" | "fail" | ... | null,
    "llm_verdict": "pass" | ... | null,
    "mechanical_evidence_ref": "<ref>" | null,
    "watchdog_timed_out": true | false
  }

Emits one JSON line ``{"verdict": <token>, "reason": <str>}`` on stdout; exit 0 (the
verdict, not the process code, carries the outcome -- asymmetric authority).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from des.domain.self_attest import classify


def main(argv: list[str] | None = None) -> int:
    """Classify a dual-source verdict record → print the §17 verdict token.

    Reads the ``--record`` JSON, delegates to the unchanged
    ``des.domain.self_attest.classify``, and prints
    ``{"verdict": <token>, "reason": <str>}`` on stdout. Exit 0 -- the verdict
    (not the exit code) carries the self-attest outcome.
    """
    args = _build_parser().parse_args(argv)
    record = _read_record(args.record)
    outcome = classify(
        mechanical_verdict=record.get("mechanical_verdict"),
        llm_verdict=record.get("llm_verdict"),
        mechanical_evidence_ref=record.get("mechanical_evidence_ref"),
        watchdog_timed_out=bool(record.get("watchdog_timed_out", False)),
    )
    print(json.dumps({"verdict": outcome.verdict.value, "reason": outcome.reason}))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des self-attest",
        description=(
            "Classify a dual-source verdict record onto the §17 GateVerdict SSOT: a "
            "machine YES never authorizes (bare-LLM -> UNVERIFIED, divergence / "
            "watchdog -> INDETERMINATE, mechanically-grounded agreement -> PASS)."
        ),
    )
    parser.add_argument(
        "--record",
        required=True,
        type=Path,
        help=(
            "Path to the dual-source verdict record (a JSON object with "
            "mechanical_verdict, llm_verdict, mechanical_evidence_ref, "
            "watchdog_timed_out)."
        ),
    )
    return parser


def _read_record(record_path: Path) -> dict[str, object]:
    """Read the dual-source verdict record JSON object from ``record_path``."""
    return json.loads(record_path.read_text(encoding="utf-8"))


if __name__ == "__main__":  # pragma: no cover - subprocess entry point
    sys.exit(main())
