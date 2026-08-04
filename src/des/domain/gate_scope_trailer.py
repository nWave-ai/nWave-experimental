"""Pure parsing of the ``Gate-Scope:`` commit-message trailer.

The single SSOT for the placeholder digest and the STRICT trailer grammar
`des commit-slice` stamps and later amends. This is pure-function domain
logic -- a regex over a string plus a constant, no filesystem, subprocess, or
CLI dependency -- so it lives in the domain layer.

Previously ``commit_slice.py``, ``run_contract_gate.py``, and
``verify_slice_commit_completeness.py`` each independently redeclared
``_PLACEHOLDER_DIGEST`` / ``_ALL_ZERO_GATE_SCOPE_DIGEST`` and their own
``Gate-Scope:`` regex, citing an import cycle toward ``commit_slice`` as the
reason. That justification does not apply to a domain module: nothing here
imports FROM any CLI module, so all three sites import from here instead of
redeclaring (AD-05 -- domain logic must never live in the drivers layer).

The three-way duplication was not merely repetitive -- it was a LATENT BUG.
``commit_slice._GATE_SCOPE_LINE_RE`` used a LOOSE grammar
(``r"^Gate-Scope:.*$"``, any payload) for its writer-side ``.sub()`` amend,
while ``run_contract_gate._GATE_SCOPE_TRAILER_RE`` used a STRICT grammar
(64 lowercase hex only) for its reader-side pre-flight guard. A
caller-supplied ``--message`` embedding a non-hex ``Gate-Scope: pending``
line slipped past the STRICT guard, then the LOOSE ``.sub(..., count=1)``
rewrote that fake line instead of the mechanically appended placeholder,
leaving the all-zero placeholder as the shipped commit's FINAL trailer --
a well-formed-looking commit that attests nothing. Unifying on ONE STRICT
regex for both read and write closes the grammar mismatch.
"""

from __future__ import annotations

import re


#: The placeholder digest ``des commit-slice`` stamps on the FIRST
#: (pre-amend) commit. 64 zero-hex characters match the ``Gate-Scope:``
#: trailer's own well-formed shape (``GATE_SCOPE_TRAILER_RE``'s
#: ``[0-9a-f]{64}`` group matches it cleanly) yet unmistakably attest
#: nothing real. Replaced in a later step by the real committed-scope
#: digest of the resulting HEAD.
PLACEHOLDER_GATE_SCOPE_DIGEST = "0" * 64

#: A ``Gate-Scope:`` commit trailer in the STRICT form: a full-line trailer
#: whose payload is exactly 64 lowercase hex characters. Compiled with
#: ``re.MULTILINE`` so ONE pattern serves both:
#:
#:  * a per-line parse -- ``.match(line.strip())`` (``^``/``$`` degrade to
#:    plain start/end-of-string on an already-stripped single line, so
#:    ``re.MULTILINE`` is a no-op there); and
#:  * an in-place ``.sub()`` rewrite over the FULL multi-line commit
#:    message.
#:
#: The trailing whitespace class is deliberately ``[^\S\n]*`` (horizontal
#: whitespace only), NOT ``\s*``. Under ``re.MULTILINE``, ``$`` matches just
#: before ANY ``\n`` (not only end-of-string) -- a greedy ``\s*`` will
#: consume past the line's own terminator into a following blank line's
#: newline before backtracking to satisfy ``$``, silently swallowing that
#: blank line during a ``.sub()`` rewrite. ``[^\S\n]*`` cannot cross a
#: ``\n``, so it is byte-equivalent to ``\s*`` for the already-stripped
#: per-line match path (no newline can appear inside a stripped single
#: line) while staying safe for the multiline rewrite path.
GATE_SCOPE_TRAILER_RE = re.compile(
    r"^Gate-Scope:[^\S\n]*([0-9a-f]{64})[^\S\n]*$", re.MULTILINE
)

#: PERMISSIVE detection: any line that literally STARTS with the
#: ``Gate-Scope:`` token, in ANY position, with ANY payload shape (hex or
#: not). Deliberately independent of ``GATE_SCOPE_TRAILER_RE`` -- that regex
#: (and the STRICT, position-scoped ``extract_gate_scope`` built on it)
#: answers "which digest attests THIS shipped commit?", a READER question
#: that must stay strict. This predicate answers a DIFFERENT, WRITER-side
#: question -- "does this caller-supplied message already look like it is
#: trying to carry a Gate-Scope: trailer?" -- which must stay permissive: a
#: caller could smuggle a non-hex or non-trailing line that the strict
#: reader would silently ignore, so the guard cannot reuse the strict
#: predicate without going blind to exactly those shapes (Defect C,
#: fix-gate-scope-constants-dedup).
_GATE_SCOPE_PREFIXED_LINE_RE = re.compile(r"^Gate-Scope:", re.MULTILINE)


def has_gate_scope_prefixed_line(message: str) -> bool:
    """True if ANY line in ``message`` starts with the ``Gate-Scope:`` token.

    Position- and payload-agnostic by design (see ``_GATE_SCOPE_PREFIXED_LINE_RE``
    above) -- a mid-body line, a non-hex payload, or a well-formed trailing
    trailer all count. A mid-SENTENCE mention (the token not at the start of
    a line) does NOT count -- a commit message has every right to talk ABOUT
    the mechanism.
    """
    return _GATE_SCOPE_PREFIXED_LINE_RE.search(message) is not None
