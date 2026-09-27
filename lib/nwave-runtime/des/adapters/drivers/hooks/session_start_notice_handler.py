"""SessionStart hook handler -- the route notice, read-only.

An agent beginning a session in an enabled nWave project must find, in its OWN
starting context, a short notice naming the available routes and what each one
leaves behind, without opening any project file.

READ-ONLY BY MANDATE. The historical DES-runtime SessionStart entry was retired
because it performed maintenance, which made opening a session mutate maintainer
state. This handler performs no maintenance, no ledger write, no update check,
no housekeeping and no filesystem mutation whatsoever: it reads one shipped
template and prints one JSON object.

ONE WORDING, ONE SOURCE. The notice text is the already-shipped
``nWave/templates/delivery-route-fragment.md`` -- the same bytes the installer
splices into the project's managed ``CLAUDE.md`` section. No second wording is
authored here, so the injected notice and the project's guidance file cannot
state different routes.

HOST CONTRACT. Standard output is EXACTLY ONE JSON object of the wrapped form
``{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext":
...}}``. The bare ``{"additionalContext": ...}`` form is not honored by current
Claude Code, and several independent ``print(json.dumps(...))`` calls in one
invocation produce output that is not valid JSON as a whole and silently drops
every contribution but the first -- so there is exactly one print here. No
``systemMessage`` key: the notice is for the agent's starting context, and a
user-visible banner at every session start is precisely the noise the earlier
retirement removed.

FAILURE ALGEBRA. Every branch is Refusal, and Refusal means NO stdout plus exit
0, because a SessionStart hook that blocks or crashes bricks a session. An
absent or ambiguous asset, an unreadable or undecodable file, an empty template
and a notice grown past its declared ceiling all yield the same observation:
nothing on stdout, one WHAT/WHY/HOW line on stderr, exit 0. Per-project scope is
not this module's concern -- the activation gate in ``hook_router`` already exits
0 before dispatch for a project that has not opted in.

A DECLARED, MEASURED SIZE. The notice is a standing tax on every session's
context, so its cost is reported as a measured fact on EVERY invocation, and the
text refuses to grow past a ceiling declared here and nowhere else. The report
rides on stderr because stdout is reserved for exactly one JSON object, and it
carries no ``systemMessage`` for the reason given above.

BYTES ARE PRIMITIVE, TOKENS ARE DERIVED. Bytes are the exact UTF-8 length of the
``additionalContext`` actually written to stdout. Tokens are ``ceil(bytes / 4)``
and are ALWAYS reported with that provenance named, because a SessionStart hook
must never touch the network and no tokenizer is reachable from it at runtime; a
number presented as a counted token would be a fabricated measurement. For this
text a real cl100k_base count is 239 tokens for 1179 bytes (4.93 B/token), so
``ceil(bytes / 4)`` over-states and can never under-report bloat.

ONE CEILING, TWO UNITS. Because tokens are a deterministic function of bytes, a
separate token ceiling would be the same rule stated twice.

DESCRIPTIVE, NEVER COMMANDING -- AND GUARDED HERE, AT RUNTIME. The published
managed section already has an install-time guard stating what commanding looks
like, as a closed forbidden set of phrases. That guard provably cannot see these
bytes: the notice is resolved AT RUNTIME from a tree that can legitimately drift
(see ``des.runtime.packaged_asset``), so an installed copy can command the agent
while the same project's published section stays clean and the older check says
PASS. The size ceiling cannot stand in for this one either -- commanding wording
is short. So the same closed set is declared here and decided over the exact
bytes this handler is about to write. The install-time guard is left untouched
and keeps governing the published section.

WHAT THIS GUARD MAY DECIDE. Substring membership in a DECLARED list, and
sentence-level co-occurrence, are primitive measurements over bytes: incomplete
at worst, never wrong. This handler never attempts to judge whether wording is
"commanding" in general -- that is a derived semantic claim and would be
software deciding on the model's behalf. Widening the set is a deliberate human
edit to the declaration below, never an inference at runtime.

THE POSITIVE HALF IS LOAD-BEARING. Forbidding commands is not enough: a notice
can command nothing and still quietly drop the fact that working directly stays
an available answer, which turns a description of three routes into a push
toward one. The notice must therefore carry at least one SENTENCE pairing the
direct route with a still-open token. Sentence-level, not whole-text: the words
"working directly" also open the third route entry, so their mere presence does
not discriminate.
"""

from __future__ import annotations

import json
import math
import re
import sys

from des.runtime.packaged_asset import resolve_packaged_asset


#: The shipped notice, authored once and spliced into every managed host file.
ROUTE_NOTICE_ASSET = "nWave/templates/delivery-route-fragment.md"

#: The single declaration of how much starting context the notice may spend.
#: MEASURED, not chosen: the shipped text is 1179 B, and the identical bytes are
#: spliced into a managed ``CLAUDE.md`` section capped at 4096 B, whose measured
#: headroom admits at most 1964 notice bytes. 1536 B therefore sits 357 B above
#: today's text and 428 B below that hard limit, so this ceiling can never be
#: satisfied while breaking the older section guard.
NOTICE_CEILING_BYTES = 1536

#: The same ceiling in the derived unit, so the two are one declaration.
NOTICE_CEILING_TOKENS = math.ceil(NOTICE_CEILING_BYTES / 4)

#: Tokens may only ever be presented as what they are.
TOKEN_PROVENANCE = (
    "derived as ceil(bytes/4), a conservative upper bound -- a session-start "
    "hook must never touch the network, so no tokenizer is reachable to count "
    "them"
)

#: The closed forbidden set, REUSED rather than redefined: these are the same
#: seven phrases the install-time section guard already decides over, at
#: tests/installer/acceptance/route_choice_block/public_oracle.py:72-80. They are
#: copied rather than shared because a production module cannot import an
#: acceptance oracle, and that oracle's own doctrine forbids it importing a
#: production symbol. MEMBERSHIP MUST STAY IDENTICAL to that list; comparison is
#: case-insensitive substring containment, exactly as it is there. Declaration
#: ORDER is meaningful: it is the order in which an offence is named.
COMMANDING_PHRASES = (
    "you must",
    "must route",
    "always route",
    "never bypass",
    "mandatory",
    "is required",
    "do not work directly",
)

#: The direct route, and the still-open tokens that keep it stated as an answer.
#: Also reused verbatim from the same install-time guard (its ``:117``).
DIRECT_ROUTE_TOKEN = "working directly"
STILL_OPEN_TOKENS = ("legitimate", "remains open")

#: Sentence boundaries, applied AFTER flattening the template's hard wraps.
#: MEASURED: the shipped text satisfies the positive predicate under both the
#: newline-preserving and the flattened split, so where the template happens to
#: wrap never decides the verdict.
SENTENCE_BOUNDARY = re.compile(r"[.;:!?]")

HOOK_EVENT_NAME = "SessionStart"


def _refuse(what: str, why: str, how: str) -> int:
    """Degrade loud on stderr, never on stdout, and never block the session."""
    print(f"WHAT: {what} WHY: {why} HOW: {how}", file=sys.stderr)
    return 0


def _read_route_notice() -> str | None:
    """The shipped route notice, or None when it cannot be read unambiguously."""
    resolution = resolve_packaged_asset(ROUTE_NOTICE_ASSET)
    if not resolution.is_usable or resolution.path is None:
        _refuse(
            f"the session-start route notice was not resolved ({resolution.detail}).",
            "the notice must come from exactly one shipped copy, never from a "
            "guess between a developer checkout and an installed tree.",
            "reinstall nWave so the shipped template resolves unambiguously.",
        )
        return None

    try:
        text = resolution.path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        _refuse(
            f"the session-start route notice at {resolution.path} could not be "
            f"read ({error}).",
            "an unreadable notice must not be replaced by an invented one.",
            "restore the shipped template, then start a new session.",
        )
        return None

    notice = text.strip()
    if not notice:
        _refuse(
            f"the session-start route notice at {resolution.path} is empty.",
            "an empty additionalContext would tell the agent nothing while "
            "looking like a delivered notice.",
            "restore the shipped template's content, then start a new session.",
        )
        return None
    return notice


def measure_notice(notice: str) -> tuple[int, int]:
    """The notice's cost in both units: measured bytes, derived token bound.

    Pure: a function of the text alone, so the reported number and the injected
    number cannot drift apart.
    """
    measured_bytes = len(notice.encode("utf-8"))
    return measured_bytes, math.ceil(measured_bytes / 4)


def _report(measured_bytes: int, derived_tokens: int) -> str:
    """The measurement, labelled so an operator and a check read one number."""
    return (
        f"bytes={measured_bytes} tokens={derived_tokens} ({TOKEN_PROVENANCE}); "
        f"permitted={NOTICE_CEILING_BYTES} "
        f"(a {NOTICE_CEILING_TOKENS} token upper bound)"
    )


def sentences_of(notice: str) -> tuple[str, ...]:
    """The notice cut into sentences, with the template's hard wraps flattened.

    Pure. Flattening first is what keeps the verdict independent of where the
    shipped template happens to wrap a line.
    """
    flattened = " ".join(notice.split())
    parts = (part.strip() for part in SENTENCE_BOUNDARY.split(flattened))
    return tuple(part for part in parts if part)


def first_commanding_phrase(notice: str) -> str | None:
    """The first DECLARED phrase the notice carries, in declaration order.

    Pure, and decidable: membership in a closed list, never a judgement about
    whether some wording reads as commanding. Returning the FIRST member in
    declaration order is what makes a notice violating several phrases yield one
    deterministic offence rather than a race.
    """
    folded = notice.lower()
    for phrase in COMMANDING_PHRASES:
        if phrase in folded:
            return phrase
    return None


def states_direct_route_remains_open(notice: str) -> bool:
    """Does some ONE sentence keep working directly stated as an answer?

    Pure. Sentence-level co-occurrence, because the words "working directly"
    also open the third route entry: whole-text presence would not discriminate.
    """
    for sentence in sentences_of(notice):
        folded = sentence.lower()
        if DIRECT_ROUTE_TOKEN in folded and any(
            token in folded for token in STILL_OPEN_TOKENS
        ):
            return True
    return False


def _descriptive_report(verdict: str) -> str:
    """State that the guard RAN, and over how much -- unfired is not evidence.

    Carries none of ``bytes=``, ``tokens=`` or ``permitted=``: the size
    observation reads each of those as a label occurring exactly once in this
    same stderr, so a second occurrence would break it.
    """
    return f"descriptive={verdict} phrases-checked={len(COMMANDING_PHRASES)}"


def handle_session_start() -> int:
    """Emit the route notice into the agent's starting context. Always exit 0."""
    notice = _read_route_notice()
    if notice is None:
        return 0

    measured_bytes, derived_tokens = measure_notice(notice)
    measurement = _report(measured_bytes, derived_tokens)
    if measured_bytes > NOTICE_CEILING_BYTES:
        # Oversize is the fifth member of the existing refusal family, not a
        # new algebra: no stdout, one WHAT/WHY/HOW line, exit 0.
        return _refuse(
            f"the session-start route notice measures {measurement}, so it "
            "exceeds its declared ceiling and was not injected.",
            "the notice is a standing tax on every session's starting context, "
            "and text that quietly outgrows its budget spends the agent's "
            "context on itself.",
            "shorten the shipped delivery-route notice back within the "
            "permitted size, or raise the declared ceiling deliberately.",
        )

    # The declared order: oversize (above), then commanding wording, then
    # missing legitimacy, then injection. A notice breaking several rules yields
    # exactly ONE refusal, naming the first offence in this order.
    commanding = first_commanding_phrase(notice)
    if commanding is not None:
        print(
            f"nWave session-start route notice: {measurement}; "
            f"{_descriptive_report('refused')}.",
            file=sys.stderr,
        )
        # The sixth member of the existing refusal family, not a new algebra.
        return _refuse(
            f"the session-start route notice commands the route: it carries the "
            f'phrase "{commanding}", so it was not injected.',
            "the notice must DESCRIBE the available routes and never command "
            "one, so that working directly remains an answer the agent can "
            "still give.",
            "restore the shipped delivery-route notice, or deliberately amend "
            "the declared set of forbidden phrases in the session-start notice "
            "handler.",
        )

    if not states_direct_route_remains_open(notice):
        print(
            f"nWave session-start route notice: {measurement}; "
            f"{_descriptive_report('refused')}.",
            file=sys.stderr,
        )
        # The seventh member of the same family, named by its missing property.
        return _refuse(
            "no sentence in the session-start route notice keeps working "
            "directly stated as a still-open answer, so it was not injected.",
            "a notice that names three routes but never says working directly "
            "remains available describes a choice while pushing one answer.",
            "restore the shipped delivery-route notice's sentence stating that "
            "working directly remains open as an answer.",
        )

    print(
        f"nWave session-start route notice: {measurement}; "
        f"{_descriptive_report('pass')}.",
        file=sys.stderr,
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": HOOK_EVENT_NAME,
                    "additionalContext": notice,
                }
            }
        )
    )
    return 0
