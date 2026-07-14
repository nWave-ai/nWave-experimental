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
import textwrap
from enum import Enum
from typing import IO


class Verdict(str, Enum):
    """The verdict surface every gate CLI emits -- one FACE per verdict.

    ``PASS`` → green ✅ prefix, exit code 0.
    ``FAIL`` → red ❌ prefix, exit code non-zero.
    ``DEGRADED`` → yellow ⚠️ prefix, exit code other (partial / soft refusal).
    ``NOT_APPLICABLE`` → grey ⚪ prefix, exit 0 -- nothing to check here, NOT
        blocking. Additive (fix-precommit-fabricates-vacuous-scaffold slice-01):
        it previously had to borrow ``PASS``'s green ✅ badge, so a developer
        skimming the terminal saw the SAME green check for "your acceptance
        tests ran and passed" and "there is no acceptance test on disk at all".
        A verdict wearing another verdict's badge is the same lie the gate's
        JSON verdict was fixed for -- one level up, on the FACE.
    ``INDETERMINATE`` → yellow ❓ prefix, exit code other -- the check could not
        RUN (unresolved runner / ambiguous feature). Distinct from ``DEGRADED``
        ("it ran, partially"): here nothing was evaluated, and the face must say
        so rather than imply a soft pass.

    The invariant: every verdict has its OWN visibly distinct face. None wears
    another's badge.
    """

    PASS = "PASS"
    FAIL = "FAIL"
    DEGRADED = "DEGRADED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    INDETERMINATE = "INDETERMINATE"


_ANSI_GREEN = "\x1b[32m"
_ANSI_RED = "\x1b[31m"
_ANSI_YELLOW = "\x1b[33m"
_ANSI_GREY = "\x1b[90m"
_ANSI_RESET = "\x1b[0m"


_COLOR_BY_VERDICT: dict[Verdict, str] = {
    Verdict.PASS: _ANSI_GREEN,
    Verdict.FAIL: _ANSI_RED,
    Verdict.DEGRADED: _ANSI_YELLOW,
    Verdict.NOT_APPLICABLE: _ANSI_GREY,
    Verdict.INDETERMINATE: _ANSI_YELLOW,
}


_PREFIX_BY_VERDICT: dict[Verdict, str] = {
    Verdict.PASS: "✅ PASS",
    Verdict.FAIL: "❌ FAIL",
    Verdict.DEGRADED: "⚠️ DEGRADED",
    Verdict.NOT_APPLICABLE: "⚪ NOT_APPLICABLE",
    Verdict.INDETERMINATE: "❓ INDETERMINATE",
}


# The detail block's geometry. A verdict's WHAT lives on the HEADLINE (one
# scannable line, next to its three siblings); its WHY/HOW live BENEATH it,
# label-aligned and wrapped. Nothing is ever dropped -- the standing rule is that
# every failure states WHAT failed, WHY, and HOW to fix it, directly, so nobody
# has to investigate. A 490-char run-on satisfies that rule on content and
# defeats it on legibility; the fix is to FORMAT the diagnostics, never to
# amputate them.
_DETAIL_INDENT = "     "
_DETAIL_LABEL_WIDTH = 5
_DETAIL_WRAP_WIDTH = 96


def _detail_lines(label: str, text: str) -> list[str]:
    """Render one labelled detail block: ``     WHY:  <wrapped, hanging-indent>``.

    The label is written once, on the first line; continuation lines align under
    the text column, so a multi-sentence WHY reads as one block rather than a
    ragged wall. Empty text yields no lines at all (never a bare dangling label).
    """
    body = text.strip()
    if not body:
        return []
    head = f"{_DETAIL_INDENT}{label + ':':<{_DETAIL_LABEL_WIDTH}} "
    hanging = " " * len(head)
    # `break_on_hyphens=False` / `break_long_words=False`: a remediation line is
    # meant to be COPY-PASTED. textwrap's defaults split on hyphens and inside
    # long tokens, so `re-run` renders as `re-` / `run` across two lines and a
    # command, flag, or path silently breaks in half. A HOW a developer cannot
    # copy correctly is not a HOW. Long tokens now overflow the width rather than
    # be corrupted -- legibility never outranks correctness.
    wrapped = textwrap.wrap(
        body,
        width=_DETAIL_WRAP_WIDTH,
        break_on_hyphens=False,
        break_long_words=False,
    ) or [body]
    return [f"{head}{wrapped[0]}"] + [f"{hanging}{line}" for line in wrapped[1:]]


def print_human_summary(
    verdict: Verdict,
    summary: str,
    file: IO[str] | None = None,
    why: str = "",
    how: str = "",
    command: str = "",
) -> None:
    """Emit a human-readable verdict, ANSI-colored when ``file`` is a TTY.

    Output shape: a HEADLINE — ``<prefix> — <summary>``, where ``<prefix>`` is
    one of ``✅ PASS`` / ``❌ FAIL`` / ``⚠️ DEGRADED`` / ``⚪ NOT_APPLICABLE`` /
    ``❓ INDETERMINATE`` — optionally followed by an indented detail block naming
    ``WHY`` the verdict was reached and ``HOW`` to act on it, and finally an
    optional ``command``. When ``file.isatty()`` returns True the prefix is
    wrapped in the verdict-matching ANSI CSI color escape; otherwise the line is
    plain text.

    ``command`` IS NOT PROSE, AND IS NEVER WRAPPED. It is emitted verbatim, alone
    on its own line, at column zero, with no indent, no label, no surrounding
    punctuation and no trailing character. This is the whole point of the
    parameter: a command embedded in a wrapped paragraph gets broken across lines
    with a hanging indent, and what the developer selects and pastes is a
    multi-line fragment with leading whitespace and a stray bracket — which
    ERRORS. Making the command *correct* is not enough; it must be *pasteable*.
    It may overflow the terminal width. That is correct and intended: a wrapped
    command is a broken command, and truncating one to fit is worse than a long
    line. Blank lines fence it off so a select-the-line gesture picks up exactly
    it and nothing else.

    ``why`` / ``how`` / ``command`` are OPTIONAL and default to empty, so every
    pre-existing call site renders byte-identically to before (headline only).
    They exist so a long diagnostic is FORMATTED rather than either (a) crammed
    into a 490-char headline that wraps across four terminal lines and destroys
    the at-a-glance scan, or (b) demoted to JSON-only, which would breach the
    standing rule that a failure explains itself on the surface a human reads.

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
    for detail in _detail_lines("WHY", why) + _detail_lines("HOW", how):
        print(detail, file=file)
    if command.strip():
        # Verbatim, alone, column zero, blank-line-fenced -- NOT through the
        # wrapper, and with nothing appended. Select-the-line and paste must
        # yield a command that runs.
        print("", file=file)
        print(command.strip(), file=file)
        print("", file=file)
