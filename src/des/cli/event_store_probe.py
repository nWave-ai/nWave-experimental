"""des event-store-probe -- the CLI driving surface for the unified event
store's Earned Trust startup probe (DD-14, unified-event-store slice-02).

Charter: docs/product/expectations/unified-event-store/
         as-a-store-operator-i-get-a-loud-startup-refusal-instead-of-a-silent-wrong-write-when-the.md
Feature-delta: docs/feature/unified-event-store/feature-delta.md

Runs `UnifiedEventStoreAdapter(project_root=<repo-root>).probe()` and
translates the outcome into terminal output + an exit code -- the composition
root's own "refuse to start on probe failure" contract (DD-14), made directly
observable so a store operator (or a `des doctor`-style precondition, or a
composition root's own startup path) can ask "is this telemetry substrate
usable?" without touching a file.

Exit-code contract:

    0 = probe succeeded (ProbeResult(ok=True, ...))
    1 = probe refused -- StoreProbeFailed, refusal names WHAT/WHY/HOW and the
        exact path attempted (always inside --repo-root; never the real
        installation's store)
    2 = malformed invocation (missing --repo-root)

RED at HEAD (unified-event-store slice-02, DISTILL scaffold): the adapter
this module drives (`UnifiedEventStoreAdapter`) is itself a RED scaffold --
`.probe()` raises a bare `AssertionError`, not `StoreProbeFailed`, so it is
NOT caught by the `except StoreProbeFailed` clause below and propagates out
of `main()` uncaught. This is the intended active-RED shape (Mandate 7): the
CLI plumbing is real, its sole callee is not, so every invocation fails for
the semantic reason "the probe is not implemented yet" (an AssertionError),
never an import/collection error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from des.adapters.driven.logging.unified_event_store_adapter import (
    UnifiedEventStoreAdapter,
)
from des.adapters.driven.output.stdout_output import StdoutOutput
from des.cli._repo_root_arg import add_repo_root_argument
from des.ports.driven_ports.probeable_port import StoreProbeFailed


if TYPE_CHECKING:
    from des.ports.driven_ports.output_port import OutputPort


def _emit(payload: dict[str, object], output: OutputPort) -> None:
    """Emit exactly one single-line JSON object through the injected sink."""
    output.emit_line(json.dumps(payload))


def main(argv: list[str] | None = None, output: OutputPort | None = None) -> int:
    """CLI entry point -- run the Earned Trust probe, report, exit accordingly.

    ``output`` defaults to :class:`StdoutOutput` (byte-identical to a bare
    ``print`` for every existing/real caller); an in-process acceptance test
    injects a :class:`CapturingOutput` fake instead (Mandate 13 L2 default --
    no interpreter fork needed to observe the terminal output).
    """
    parser = argparse.ArgumentParser(
        prog="des event-store-probe",
        description=(
            "Earned Trust startup probe for the unified event store (DD-14): "
            "exercises a canary write/flock/read/delete against the telemetry "
            "substrate under --repo-root and refuses LOUD (never exit 0) when "
            "it cannot honor its contract."
        ),
    )
    add_repo_root_argument(
        parser,
        "--repo-root",
        required=True,
        type=Path,
        help="The target repository root whose .nwave/telemetry/ substrate is probed.",
    )
    args = parser.parse_args(argv)
    sink = output if output is not None else StdoutOutput()

    adapter = UnifiedEventStoreAdapter(project_root=args.repo_root)
    try:
        result = adapter.probe()
    except StoreProbeFailed as exc:
        _emit(
            {
                "event": "EventStoreProbeRefused",
                "fault": exc.fault,
                "path": str(exc.path),
                "message": str(exc),
            },
            sink,
        )
        return 1

    _emit(
        {
            "event": "EventStoreProbeOk",
            "repo_root": str(args.repo_root),
            "detail": result.detail,
        },
        sink,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
