"""StdoutOutput — the production OutputPort adapter writing to ``sys.stdout``.

Byte-identical to a bare ``print(line)``: emits the line followed by a newline to
the CURRENT ``sys.stdout`` (resolved at call time, so a ``contextlib.redirect_stdout``
in the caller is honoured). This is the default sink ``run_contract_gate.main``
injects when no ``OutputPort`` is supplied — so existing callers see byte-for-byte
unchanged terminal output (zero behaviour change via default-arg injection).
"""

from __future__ import annotations

import sys


class StdoutOutput:
    """Write each emitted line to ``sys.stdout`` (byte-identical to ``print``)."""

    def emit_line(self, line: str) -> None:
        """Emit ``line`` followed by a newline to the current ``sys.stdout``."""
        sys.stdout.write(f"{line}\n")


__all__ = ["StdoutOutput"]
