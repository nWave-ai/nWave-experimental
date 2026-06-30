"""OutputPort — the driven port for terminal output capture (in-process exemplar).

The WRITE-only capture-sink the in-process active-RED pattern composes (DESIGN §2):
a single ``emit_line`` write that the run-contract-gate entry routes its terminal
output through, so an acceptance test can drive ``main(argv)`` IN-PROCESS and capture
the emitted lines WITHOUT forking an interpreter.

Contract shape: bounded-change (DESIGN §2). The port exposes ONLY a write
(``emit_line``) — no read method (Principle 12: read/write split, an output sink only
writes). The production adapter (``StdoutOutput``) writes to ``sys.stdout``; the test
fake (``CapturingOutput``) records the lines for assertion.
"""

from __future__ import annotations

from typing import Protocol


class OutputPort(Protocol):
    """Write terminal output through an injectable sink — write-only (DESIGN §2).

    One method: :meth:`emit_line`. NO read method — an output sink only writes
    (the read/write split keeps the contract bounded-change). The production
    ``StdoutOutput`` writes to ``sys.stdout``; the ``CapturingOutput`` fake records
    lines so an in-process acceptance test can assert on the captured output.
    """

    def emit_line(self, line: str) -> None:
        """Emit one line of terminal output through the sink."""
        ...


__all__ = ["OutputPort"]
