"""Pure attribution-trailer append decision (fix-attribution-trailer-never-applied).

`des commit` and `des commit-slice` run `git commit` inside a Python
subprocess the PreToolUse Bash rewriter (`trailer_rewriter.py`) never
observes, so the dual-trailer mechanism there never fires on the spine's own
producing tools. This module is the producing-tool-side counterpart (GDP-4):
given an already-composed commit message and an already-resolved boolean
decision, it returns the message to commit. No I/O, no config reads, no git --
those live in the application seam that calls this function.

Reuses the SENTINEL idempotency key from `trailer_rewriter` so a message that
already carries the nWave trailer -- whether typed by the model in
`--message` or injected earlier by the Bash PreToolUse rewriter -- is never
doubled (property 1, ADR-CA-006 idempotency discipline).
"""

from __future__ import annotations

from des.domain.commit_attribution.trailer_rewriter import SENTINEL
from des.domain.commit_trailer_append import append_mechanical_trailer_block


# Re-exported under this module's own name so a caller reading only this file
# never needs to know the sentinel is shared with the Bash-rewrite mechanism.
ATTRIBUTION_TRAILER = SENTINEL


def apply_attribution_trailer(message: str, *, enabled: bool) -> str:
    """Return *message* with the nWave attribution trailer appended when due.

    ``enabled=False`` -> *message* returned byte-identical (off means off,
    property 2). ``enabled=True`` and the sentinel already present ANYWHERE in
    *message* -> byte-identical (idempotent by sentinel, property 1) --
    covers both a model-typed trailer in the authored message and one already
    injected by the Bash PreToolUse rewriter on a `-m` path. ``enabled=True``
    and the sentinel absent -> the trailer is appended as a new trailing
    paragraph (merged onto an existing contiguous trailer block, or blank-line
    separated when there is none -- see `append_mechanical_trailer_block`);
    the subject, body, and every other pre-existing trailer are preserved
    verbatim ahead of it.
    """
    if not enabled:
        return message
    if ATTRIBUTION_TRAILER in message:
        return message
    return append_mechanical_trailer_block(message, ATTRIBUTION_TRAILER)
