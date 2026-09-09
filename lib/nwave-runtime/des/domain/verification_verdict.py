"""What the judge said about one candidate, as a closed word the record carries.

A candidate that was CONSTRUCTED and verified natively is a fact whatever the
judge then said about it, so the verify record now carries both: the candidate,
and the word for the judgement over it.  Without the word the record could only
exist for an admitted candidate, and `des integrate` had to read the ABSENCE of
a record as «this candidate was never built» -- two different worlds under one
name, which is why a refused examination left the orchestrator with a NEXT line
naming a move the next step denied.

The vocabulary is closed and its members are ref-name safe, because the word is
part of the durable record's own name.
"""

from __future__ import annotations

from des.domain.delivery_disposition import Disposition


ADMITTED = "admitted"
NOT_ADMITTED = "not-admitted"
INDETERMINATE = "indeterminate"

VERDICTS = frozenset({ADMITTED, NOT_ADMITTED, INDETERMINATE})


def verdict_of(disposition: Disposition) -> str:
    """The word for one judged disposition.

    `Success` is the only admission.  `Indeterminate` keeps its own word rather
    than collapsing into a refusal, because «the judge could not tell» and «the
    judge said no» are different facts for the orchestrator that reads them.
    """
    if disposition is Disposition.Success:
        return ADMITTED
    if disposition is Disposition.Indeterminate:
        return INDETERMINATE
    return NOT_ADMITTED
