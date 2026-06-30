"""Human-readable verdict surface — one line, optional ANSI color, on stderr.

F-D1-HUMAN-READABLE-GATE-SURFACES slice-01 walking-skeleton helper. Every
gate CLI emits BOTH a single-line JSON event (machine-readable contract,
unchanged byte-content) AND a short colored human-readable summary line on
stderr (operator-facing surface). This module is the SSOT for both surfaces.

WHY-NEW-FILE: src/des/cli/human_surface.py
  CLOSEST-EXISTING: src/des/cli/run_contract_gate.py
  EXTENSION-COST: every gate CLI under src/des/cli/ would re-implement the
    same Verdict enum + ANSI escapes + TTY detection — DDD-1 SSOT violation.
  PARALLEL-RATIONALE: shared cross-CLI helper has a different lifecycle from
    any one gate (slice-02/03/04 extend the surface to 8 more CLIs by
    importing this module; inlining into run_contract_gate would force every
    sibling CLI to import from a peer gate, not a shared helper).

Hook-only architecturally — standalone module, NO sequencer / NO engine
coupling (Ale 2026-05-24 nwave-dev topology). stdlib only.
"""

from __future__ import annotations

import sys
from enum import Enum
from typing import IO


class Verdict(str, Enum):
    """The three-state verdict surface every gate CLI emits.

    ``PASS`` → green ✅ prefix, exit code 0.
    ``FAIL`` → red ❌ prefix, exit code non-zero.
    ``DEGRADED`` → yellow ⚠️ prefix, exit code other (partial / soft refusal).
    """

    PASS = "PASS"
    FAIL = "FAIL"
    DEGRADED = "DEGRADED"


_ANSI_GREEN = "\x1b[32m"
_ANSI_RED = "\x1b[31m"
_ANSI_YELLOW = "\x1b[33m"
_ANSI_RESET = "\x1b[0m"


_COLOR_BY_VERDICT: dict[Verdict, str] = {
    Verdict.PASS: _ANSI_GREEN,
    Verdict.FAIL: _ANSI_RED,
    Verdict.DEGRADED: _ANSI_YELLOW,
}


_PREFIX_BY_VERDICT: dict[Verdict, str] = {
    Verdict.PASS: "✅ PASS",
    Verdict.FAIL: "❌ FAIL",
    Verdict.DEGRADED: "⚠️ DEGRADED",
}


def print_human_summary(
    verdict: Verdict,
    summary: str,
    file: IO[str] | None = None,
) -> None:
    """Emit one human-readable verdict line, ANSI-colored when ``file`` is a TTY.

    Output shape: ``<prefix> — <summary>`` where ``<prefix>`` is one of
    ``✅ PASS`` / ``❌ FAIL`` / ⚠️ DEGRADED``. When ``file.isatty()`` returns
    True the prefix is wrapped in the verdict-matching ANSI CSI color escape;
    otherwise the line is plain text.

    ``file`` LATE-BINDS ``sys.stderr``: the default is ``None`` and the live
    ``sys.stderr`` is resolved HERE, at CALL-time, not captured at DEF-time.
    Production behaviour is identical (the same stream the def-time default
    pointed at), but an in-process ``contextlib.redirect_stderr`` patched AFTER
    this module is imported now wraps THIS call — so a test can capture the loud
    advisory diagnostic in-process instead of forking a subprocess.
    """
    if file is None:
        file = sys.stderr
    prefix = _PREFIX_BY_VERDICT[verdict]
    if file.isatty():
        color = _COLOR_BY_VERDICT[verdict]
        line = f"{color}{prefix}{_ANSI_RESET} — {summary}"
    else:
        line = f"{prefix} — {summary}"
    print(line, file=file)
