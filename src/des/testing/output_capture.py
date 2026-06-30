"""CapturingOutput — the test-fake OutputPort that records emitted lines.

The capture-sink counterpart of ``StdoutOutput``: instead of writing to
``sys.stdout`` it records each emitted line, so an in-process acceptance test can
drive ``run_contract_gate.main(argv, output=CapturingOutput())`` and assert on the
captured output WITHOUT forking an interpreter (DESIGN §2).

Lives under ``src/des/testing/`` (NOT ``tests/``) so production code that wires this
fake never imports from the test tree (F-D-09 clean).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CapturingOutput:
    """Record each emitted line for in-process assertion (OutputPort fake)."""

    lines: list[str] = field(default_factory=list)

    def emit_line(self, line: str) -> None:
        """Record ``line`` instead of writing it to a terminal."""
        self.lines.append(line)

    def captured_text(self) -> str:
        """Return the recorded lines joined by newlines."""
        return "\n".join(self.lines)


__all__ = ["CapturingOutput"]
