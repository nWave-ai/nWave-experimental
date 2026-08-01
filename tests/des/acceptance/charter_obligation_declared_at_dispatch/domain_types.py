"""Domain vocabulary for the charter-obligation ATs (Mandate 12).

Authored at DISTILL as a PLACEHOLDER, because at authoring time
`LaneProfile.charter_obligation` did not exist yet and there was nothing to
import. DELIVER slice-01 landed the production declaration on
`src/des/domain/expectation_charter_mapping.py` (feature-delta Reuse Analysis:
the single CREATE_NEW row lands THERE, no new `src/des/**` module), so the
placeholder declarations have MOVED and this module now IMPORTS them from
production -- it keeps no copy. A standalone declaration surviving here beside
the shipped counterpart would be a Mandate-12 violation, not a design choice.

What remains local is what production does NOT own: `LANE_OBLIGATIONS` (the
EXPECTED lane->obligation table, stated independently so the parametrized AT
is a specification rather than a tautology against `LANE_PROFILES`), the two
slice-02 event names, and the ledger reader + discriminator the ATs observe
through.

Stdlib (`json`, `pathlib`) plus the shipped vocabulary.
"""

from __future__ import annotations

import json
from pathlib import Path

from des.domain.expectation_charter_mapping import (
    CHARTER_OBLIGATION_DECLARED_EVENT,
    CHARTER_OBLIGATION_UNWRITABLE_EVENT,
    CharterObligation,
)


__all__ = [
    "ARMING_INDETERMINATE_EVENT",
    "CHARTER_OBLIGATION_EVENT",
    "LANE_OBLIGATIONS",
    "OBLIGATION_UNMET_EVENT",
    "UNWRITABLE_EVENT",
    "CharterObligation",
    "declared_obligation",
    "read_obligation_records",
]

#: The record type the dispatch appends to the EXISTING examine ledger
#: (feature-delta DDD-4). Keyed `(feature_id, slice_id)` -- the SAME key
#: `_latest_examine_verdict` already indexes on (`commit_slice.py:825-827`).
CHARTER_OBLIGATION_EVENT = CHARTER_OBLIGATION_DECLARED_EVENT

#: The LOUD stderr event when the ledger append fails (feature-delta
#: `[REF] Driving Ports`, row 1). The dispatch exit code is UNCHANGED: a
#: telemetry write must never take down the dispatch that is the operator's
#: only way forward.
UNWRITABLE_EVENT = CHARTER_OBLIGATION_UNWRITABLE_EVENT

#: The commit-time refusal when a `REQUIRED` obligation has no charter.
OBLIGATION_UNMET_EVENT = "CharterObligationUnmet"

#: The LOUD, NON-BLOCKING stderr warning for the third state (DDD-5).
ARMING_INDETERMINATE_EVENT = "ExamineArmingIndeterminate"

#: The lane -> obligation mapping the operator's `--lane` choice declares
#: (DDD-2), read off the already-existing `LANE_PROFILES` rows
#: (`src/des/domain/lane_profile.py:58`). `bugfix` already declares
#: `at_requirement=REQUIRED`; `prefactoring` and `charter` already declare
#: `EXEMPT`. The obligation is a FOURTH sibling field on the same rows (D-5),
#: not a parallel registry.
LANE_OBLIGATIONS: dict[str, CharterObligation] = {
    "bugfix": CharterObligation.REQUIRED,
    "prefactoring": CharterObligation.EXEMPT,
    "charter": CharterObligation.EXEMPT,
}


def read_obligation_records(ledger: Path) -> list[dict[str, object]]:
    """Every `CharterObligationDeclared` record on ``ledger``, in file order.

    Reuses the malformed-line tolerance the examine-ledger reader already
    establishes (`commit_slice.py:818-822` skips a `JSONDecodeError` line) --
    a partial line from a concurrent writer is skipped, never raised, so a
    concurrent-writer artefact can never masquerade as a missing declaration.
    """
    if not ledger.is_file():
        return []
    records: list[dict[str, object]] = []
    for line in ledger.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and record.get("event") == CHARTER_OBLIGATION_EVENT:
            records.append(record)
    return records


def declared_obligation(ledger: Path, slice_id: str) -> str | None:
    """The LATEST declared obligation for ``slice_id``, or ``None`` when the
    slice was NEVER DECLARED.

    THE DISCRIMINATOR. `None` is not a value of `CharterObligation` and must
    never be coerced into one: "never declared" is the absence of a record, and
    an absence read as a negative declaration is exactly the silent-wrong class
    this feature exists to kill. Latest-record-wins mirrors
    `_latest_examine_verdict`'s last-line-wins semantics on the same ledger.
    """
    latest: str | None = None
    for record in read_obligation_records(ledger):
        if record.get("slice_id") == slice_id:
            value = record.get("obligation")
            latest = str(value) if value is not None else None
    return latest


# ---------------------------------------------------------------------------
# The OPERATOR-VISIBLE surface -- a different proposition from the record
# ---------------------------------------------------------------------------
#
# The charter's Intent is "the system TELLS ME right there"; the ledger record
# is "the fact EXISTS on disk". Those are two propositions and only the second
# was ever asserted, which is how a 0-failed AT suite and a FAIL examine verdict
# were both true at once (session log, 2026-07-29: "I ran the dispatch nine
# different ways and never once saw the word 'charter' on my screen"). A ledger
# file the CLI never names IS the "buried" the charter's negative row forbids.
#
# The oracle below reads the OPERATOR-VISIBLE STREAM. It deliberately spans
# stdout AND stderr: that union is what appears on the operator's screen, and it
# is what the examiner actually looked at (she quoted the stderr-emitted
# `des.runtime.freshness.autoskipped` line in the same session). Asserting
# stdout ALONE would force prose into an envelope that downstream tooling
# consumes VERBATIM -- see the DISTILL note in the feature-delta; which of the
# two streams carries it is DELIVER's call, being told is not.


#: The word an operator scans for. Matching is case-insensitive.
CHARTER_WORD = "charter"


def operator_visible(stdout: str, stderr: str) -> str:
    """Everything the operator sees on screen from one invocation."""
    return f"{stdout}\n{stderr}"


def charter_lines(stdout: str, stderr: str) -> list[str]:
    """Every operator-visible line that names the charter question.

    A LINE-level oracle, not a bare substring over the whole output: it keeps
    the obligation word and the state token from being satisfied by two
    unrelated lines far apart (the accidental-match failure mode that already
    let one AT in this feature pass for the wrong reason).
    """
    return [
        line
        for line in operator_visible(stdout, stderr).splitlines()
        if CHARTER_WORD in line.lower()
    ]


def line_stating(stdout: str, stderr: str, *tokens: str) -> str | None:
    """The first charter-naming line that also carries EVERY token, or None.

    Token matching is case-insensitive so the assertion pins the STATE the
    operator is told, never a particular sentence the implementation is free to
    word as it likes.
    """
    for line in charter_lines(stdout, stderr):
        lowered = line.lower()
        if all(token.lower() in lowered for token in tokens):
            return line
    return None
