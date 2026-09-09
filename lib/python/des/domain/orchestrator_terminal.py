"""What one delivery terminal says to the ORCHESTRATOR that ran it.

A DES step is not run by a person repairing a checkout.  It is run by an LLM
orchestrator, and the only thing that reaches that reader is the terminal
block.  The role's own diagnostic travels in it, labelled and verbatim.  It is
SHOWN, never interpreted: nothing here parses it to choose a branch, because
the whole reason it is opaque evidence is that model-authored prose is not a
control-plane input.  The orchestrator reads it and decides.

WHAT USED TO LIVE HERE AND DOES NOT.  `orchestrator_line` composed the move a
WHOLE-Request run left open, from the disposition and from whether a durable
value graph survived that run -- two facts only the composed run held.  It went
with `des dispatch` (ADR-DES-003 Section 11: a property quantified over the
totality of a Request's run belongs to the composer).  A step's own
`ORCHESTRATOR` row is a DIFFERENT observation and has a different home: G5 of
Section 3 derives it from the primitive rows the step actually printed, in
`des.cli.step_terminal.orchestrator_line`, which is why the two were never
merged.
"""

from __future__ import annotations

import json


#: Beyond this many characters the diagnostic is cut and says so.  A role's
#: diagnostic is normally two or three sentences; a runaway one must not push
#: the WHAT, the WHY and the HOW out of a reader's window.
DIAGNOSTIC_CHARACTER_LIMIT = 4000

#: What the terminal says when no role turn ran at all -- a Request refused
#: before any model turn, for instance.  An absence stated, never a blank line
#: that reads like an empty answer.
NO_ROLE_TURN = "(no role turn ran)"


def diagnostic_line(diagnostic: str | None) -> str:
    """One machine-stable line carrying the last role turn's own words.

    The value is JSON-encoded rather than pasted raw.  A diagnostic is prose a
    model wrote, so it may contain newlines, and a terminal record that a caller
    reads line by line cannot have a field that silently becomes three lines.
    Encoding keeps the line one line AND keeps the text recoverable character
    for character, which rewriting the newlines away would not.
    """
    if diagnostic is None:
        return f"DIAGNOSTIC: {json.dumps(NO_ROLE_TURN)}"
    if len(diagnostic) > DIAGNOSTIC_CHARACTER_LIMIT:
        omitted = len(diagnostic) - DIAGNOSTIC_CHARACTER_LIMIT
        diagnostic = (
            diagnostic[:DIAGNOSTIC_CHARACTER_LIMIT]
            + f" [TRUNCATED: {omitted} more characters]"
        )
    return f"DIAGNOSTIC: {json.dumps(diagnostic, ensure_ascii=False)}"
