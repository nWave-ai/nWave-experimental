"""Phase-report CLI: operator-observable projection of the atdd_pure spine's
canonical delivery phase model.

Module-direct invocation via the runtime interpreter's ``-m`` switch on the
``des.cli.phases`` module (the composition root invokes it with the
``sys.executable`` absolute interpreter path, never the bare ``python``
console name — the import-safe form per F-DES-RUNTIME-INTERPRETER-BOUNDARY).

This is the real operator diagnostic that surfaces, in machine-readable form,
how many delivery phases the per-slice DELIVER carpaccio runs and which
transitions between them are legal (fix-atdd-pure-spine-phase-count-reduction
slice-01). The report is DERIVED from the live phase model
(`des.domain.atdd_pure_phases.CANONICAL_PHASES` + `CANONICAL_TRANSITIONS`), so
it cannot drift from what the spine actually runs (Mandate-13: the model is
observed through this port, never by reading its internals directly).

Emitted JSON shape (STDOUT only — the clean machine channel)::

    {
      "phases": ["A_GREEN", "C_REVIEWER_AUDIT", "D_REFACTOR_COMMIT"],
      "transitions": [["A_GREEN", "C_REVIEWER_AUDIT"], ...],
      "count": 3
    }
"""

from __future__ import annotations

import argparse
import json
import sys

from des.domain.atdd_pure_phases import (
    CANONICAL_PHASES,
    CANONICAL_TRANSITIONS,
    resolve_phase,
)


def _build_report() -> dict[str, object]:
    """Project the live canonical phase model into the report payload."""
    transitions = [
        [source, target]
        for source, targets in CANONICAL_TRANSITIONS.items()
        for target in sorted(targets)
    ]
    return {
        "phases": list(CANONICAL_PHASES),
        "transitions": transitions,
        "count": len(CANONICAL_PHASES),
    }


def _resolve(name: str) -> int:
    """Resolve a (possibly legacy) phase name and emit the typed outcome.

    THREE observable outcomes mirroring ``resolve_phase``:

    * a canonical/legacy name -> ``{"canonical": "<name>"}`` on stdout, exit 0;
    * the retired routing marker -> ``{"routing": true, "canonical": null}`` on
      stdout, exit 0 (the routing/seam outcome);
    * an unknown name -> a typed-error message on stderr, non-zero exit (never a
      silent map to a wrong phase).
    """
    resolution = resolve_phase(name)
    # Ask the outcome, never compare its enum member here: `is` on an enum
    # member is an identity check across a module boundary, the very coupling
    # this contract removed from the `except` it replaced.
    if resolution.is_unknown:
        sys.stderr.write(f"unknown phase name: {resolution.requested!r}\n")
        return 1
    if resolution.is_routing:
        json.dump({"routing": True, "canonical": None}, sys.stdout)
        sys.stdout.write("\n")
        return 0
    json.dump({"canonical": resolution.canonical}, sys.stdout)
    sys.stdout.write("\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="des.cli.phases",
        description="Report the atdd_pure spine's canonical delivery phase model.",
    )
    parser.add_argument(
        "--format",
        choices=["json"],
        default="json",
        help="Output format (only 'json' is supported).",
    )
    parser.add_argument(
        "--resolve",
        metavar="PHASE",
        default=None,
        help=(
            "Resolve a (possibly legacy) phase name to its canonical phase. "
            'Emits {"canonical": ...} (exit 0), {"routing": true} for the '
            "retired routing marker (exit 0), or a typed error (non-zero exit)."
        ),
    )
    args = parser.parse_args(argv)

    if args.resolve is not None:
        return _resolve(args.resolve)

    json.dump(_build_report(), sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
