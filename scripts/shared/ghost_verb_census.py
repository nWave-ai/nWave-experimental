"""Census of `des <verb>` citations inside backtick code spans in `.md`
files that name a verb absent from the live `_REGISTRY` (F-INSTALL-REMOVAL-
TRANSPARENCY, follow-up: "the fix reproduces one level up the same defect it
repairs" -- Ale, 2026-08-24).

This is documentation staleness, not a CLI defect: a `.md` file citing a
verb that no longer exists cannot itself be wrong the way a code import is
wrong, so this module does NOT gate on the count being zero (hundreds of
existing occurrences would make a zero-tolerance gate red on day one and
get disarmed within a day -- exactly what a ratchet avoids). It only
computes the FACT -- which (file, verb) pairs are ghost citations right
now -- so a gate can ratchet against a checked-in baseline: fail on
citations NOT already in the baseline, never on the existing debt.

Extraction is deliberately confined to backtick-delimited spans, NOT a
word-boundary scan of raw prose. `defects.md`'s own
`shipped-prose-names-two-des-invocations-that-do-not-exist` entry already
diagnosed the wider failure mode by name: "un grep largo cattura frasi
come 'des across'" -- verified against this very tree, a raw `\bdes\\s+\\w+`
scan matches Italian/English prose that merely happens to contain the
standalone word "des" ("... risolve des al SUO source", "future tests
`des` across ...") with no command citation intended at all. Confining the
match to backtick spans avoids that class entirely: nobody wraps ordinary
prose in backticks. Within a span the verb need not be the first token
(`` `pipenv run des commit-slice --repo .` `` still names `commit-slice`),
but the span itself must be a real inline-code span -- prose mentioning a
verb outside backticks is not counted, matching that defect's own
prescription ("MAI il testo libero").
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


# Stage 1: every single-backtick inline code span (non-greedy, no embedded
# backtick or newline -- triple-backtick fences are a different construct
# and are intentionally out of scope here, consistent with the defect's own
# "backtick" framing).
_BACKTICK_SPAN = re.compile(r"`([^`\n]+)`")

# Stage 2: within a span, "des <verb>" anywhere (not required to be the
# first token), word-bounded.
_DES_VERB_IN_SPAN = re.compile(r"\bdes\s+([a-z][a-z0-9-]*)")


def extract_des_verb_citations(text: str) -> frozenset[str]:
    """Every distinct verb named as `des <verb>` inside a backtick code
    span within *text*. Duplicate-insensitive: a verb cited five times in
    one file counts once for that file (the ratchet's unit is "this file
    cites this ghost verb", not "this many times")."""
    verbs: set[str] = set()
    for span in _BACKTICK_SPAN.findall(text):
        verbs.update(_DES_VERB_IN_SPAN.findall(span))
    return frozenset(verbs)


def ghost_verbs(cited: Iterable[str], *, live: frozenset[str]) -> frozenset[str]:
    """Cited verbs absent from the live `_REGISTRY`.

    Deliberately independent of `_RETIRED`: a `.md` file instructing a
    reader to run `des commit-slice` is stale documentation regardless of
    whether the CLI now explains the miss nicely at the terminal -- the
    `_RETIRED` map fixes the RUNTIME symptom (F-INSTALL-REMOVAL-
    TRANSPARENCY deliverable 3), not the wrong instruction sitting in a
    guide. This is the measurement team-lead's own census used (a `.md`
    citing `commit-slice` counts as a ghost citation even though
    `commit-slice` is a declared `_RETIRED` entry)."""
    return frozenset(verb for verb in cited if verb not in live)


def census_ghost_citations(
    markdown_files: Iterable[Path],
    *,
    live: frozenset[str],
) -> dict[str, frozenset[str]]:
    """Ghost-verb citations per file, keyed by the path as given (callers
    pass repo-relative paths so the result is portable/comparable across
    machines). Files with no ghost citation are omitted from the result."""
    result: dict[str, frozenset[str]] = {}
    for path in markdown_files:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        cited = extract_des_verb_citations(text)
        if not cited:
            continue
        ghosts = ghost_verbs(cited, live=live)
        if ghosts:
            result[str(path)] = ghosts
    return result
