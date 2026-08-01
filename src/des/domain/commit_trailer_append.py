"""Shared append-a-mechanical-trailer decision (fix-commit-slice-trailer-contiguity).

Five independent call sites (``des commit-slice``'s ``Slice-Id:``,
``Reviewed-by:``, ``Co-Authored-By:`` and ``Gate-Scope:`` stamps, plus ``des
commit``'s ``Step-Id:`` stamp) each used to append their trailer with an
unconditional ``\\n\\n`` blank-line separator, regardless of what the message
already ended with. Chained in real order, every append after the first
inserted its OWN blank line ahead of an already-trailer-ending message, so
only the LAST-appended trailer ever formed a contiguous run -- the earlier
ones were invisible to ``git interpret-trailers --parse``, which recognises
only the trailing CONTIGUOUS block of ``Key: value`` lines.

This is pure-function domain logic -- a regex over a string, no filesystem,
subprocess, or CLI dependency -- so it lives in the domain layer, mirroring
``slice_id_trailer.py`` and ``attribution_trailer.py``.
"""

from __future__ import annotations

import re


#: A trailer-shaped line: `Key: value` where Key starts with a letter and
#: contains only letters/digits/hyphens. Deliberately loose (git's own
#: `interpret-trailers` is equally loose) -- a prose line that happens to
#: match (e.g. `Nota: qualcosa`) is indistinguishable from a real trailer by
#: construction; that is a declared, accepted heuristic limit, not a bug.
_TRAILER_LINE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]*:\s*.*$")


def append_mechanical_trailer_block(message: str, trailer_block: str) -> str:
    """Return *message* with *trailer_block* appended, merging onto an
    already-trailer-shaped tail instead of always inserting a blank line.

    Mirrors git's OWN trailer-block rule (empirically confirmed against the
    real `git interpret-trailers --parse` binary): a message's LAST paragraph
    (the contiguous non-blank lines at its end) is mergeable with a single
    newline only when BOTH hold --

      1. it is not the message's ONLY paragraph -- a blank line must already
         separate it from something above. A bare single-line/single-
         paragraph message (e.g. a subject like "feat: add a", which itself
         matches `Key: value` shape by conventional-commit coincidence) is
         NEVER treated as an existing trailer block by git, no matter its
         shape, because there is no established body/trailer split yet.
      2. every line of that last paragraph matches the trailer-line shape.

    When both hold, *trailer_block* joins with a SINGLE newline, extending
    the same contiguous trailer block a structural parser recognises.
    Otherwise it is separated by a blank line, exactly as before (the
    no-pre-existing-trailer case is unchanged).

    *trailer_block* may itself be more than one `Key: value` line (already
    joined by `\\n`) for call sites that stamp several trailers in one append.
    """
    stripped = message.rstrip("\n")
    lines = stripped.split("\n")
    end = len(lines)
    start = end
    while start > 0 and lines[start - 1].strip() != "":
        start -= 1
    has_prior_paragraph = start > 0
    last_paragraph_is_trailer_shaped = has_prior_paragraph and all(
        _TRAILER_LINE_RE.match(line) for line in lines[start:end]
    )
    separator = "\n" if last_paragraph_is_trailer_shaped else "\n\n"
    return f"{stripped}{separator}{trailer_block}"
