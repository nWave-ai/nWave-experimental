"""Entry-gate domain -- classifies the observable-net verdict an item's own
dispatched agent emits, before the item is ever allowed to merge blind.

CREATE_NEW (des-refactor-fixer-swarm slice-04, feature-delta Reuse Analysis
row ``EntryGateVerdict`` / ``classify_entry_gate``). Design container:
"entrygate: Classifies the observable-net verdict from the agent's own
emitted envelope; Mikado-escalation handling" (feature-delta C4 Container).

D9 (feature-delta DDD list): Mikado is escalation-ONLY, never the default --
a flat queue per item unless an item's own agent emits ``MIKADO_ESCALATION``.
D10 informs the SAME closed-enum-over-powerset shape this module borrows
(pattern-reuse only, not a Reuse Analysis EXTEND row) from
``des.domain.environmental_e2e.done_gate.evaluate_done_gate`` -- a read-only
consumed dependency per the feature-delta's own note.

Wired into ``RefactorDrainService.drain_one`` (A_GREEN, slice-04): the
agent's own ``AgentInvocationResult.stdout`` is routed through
``classify_entry_gate`` BEFORE the green-to-green/merge step. The slice-04
acceptance tests (``tests/des/refactor/test_slice_04_entry_gate.py``) drive
the REAL ``drain_one`` entry point and assert the observable merge/pile-file
effect this wiring produces.
"""

from __future__ import annotations

import re
from enum import Enum


class EntryGateVerdict(str, Enum):
    """The 5-way CLOSED set of entry-gate verdicts an item's own dispatched
    agent may emit in its own output (feature-delta Reuse Analysis row).

    Only ``REFACTOR_SAFE`` and ``MECHANICAL_RENAME_EXEMPT`` permit the
    existing green-to-green + merge path (slice-01) to proceed.
    ``CHARACTERIZE_FIRST`` and ``ABSTAINED`` refuse to merge blind (Value
    statement #4). ``MIKADO_ESCALATION`` refuses to merge AND is annotated
    ``escalated`` in ``techdebt.md`` for human follow-up (D9, AT-8) --
    never moved to ``paidtechdebt.md``.
    """

    REFACTOR_SAFE = "REFACTOR_SAFE"
    CHARACTERIZE_FIRST = "CHARACTERIZE_FIRST"
    ABSTAINED = "ABSTAINED"
    MECHANICAL_RENAME_EXEMPT = "MECHANICAL_RENAME_EXEMPT"
    MIKADO_ESCALATION = "MIKADO_ESCALATION"


#: The named merge-refusal reason (feature-delta AT-7, verbatim) when the
#: agent's own output carries no recognized :class:`EntryGateVerdict` token
#: -- never a silent merge.
ENTRY_GATE_VERDICT_MISSING = "EntryGateVerdictMissing"

#: The only two verdicts that let an item through to merge
#: (``RefactorDrainService._entry_gate_refusal``). A merge-permitting verdict
#: is granted ONLY by an unambiguous bare-line attestation (the first pass in
#: ``classify_entry_gate`` below) -- NEVER by a loose substring match over
#: prose, because prose is exactly where a fixer explains why it will NOT
#: certify (e.g. "I cannot certify this as REFACTOR_SAFE"). Widening this back
#: to a substring match re-opens the arming defect this set exists to close.
MERGE_PERMITTING_VERDICTS = frozenset(
    {EntryGateVerdict.REFACTOR_SAFE, EntryGateVerdict.MECHANICAL_RENAME_EXEMPT}
)


def classify_entry_gate(agent_output: str) -> EntryGateVerdict | None:
    """Parse the agent's own emitted verdict token out of ``agent_output``.

    Returns the recognized :class:`EntryGateVerdict`, or ``None`` when no
    recognized token is present anywhere in ``agent_output`` -- the caller
    (``RefactorDrainService.drain_one``, A_GREEN) maps ``None`` to the named
    ``ENTRY_GATE_VERDICT_MISSING`` merge-refusal outcome (AT-7), never a
    silent merge against a vacuous or unclassified green.

    Two passes, in order:

    1. **Bare-line attestation** -- a line whose ENTIRE stripped content is
       exactly one token's value. This is the only path that may yield a
       merge-permitting verdict (``REFACTOR_SAFE`` /
       ``MECHANICAL_RENAME_EXEMPT``): an unambiguous, standalone line is the
       single most reliable shape of "I certify this".
    2. **Prose fallback, declining tokens only** -- when no bare line exists,
       a loose substring match is still useful for the tokens that only ever
       REFUSE to merge (``CHARACTERIZE_FIRST`` / ``ABSTAINED`` /
       ``MIKADO_ESCALATION``): mis-detecting a refusal as a *different*
       refusal never merges unreviewed work. The merge-permitting tokens are
       deliberately excluded from this pass -- an LLM explaining why it will
       NOT certify is the single most likely shape of a real refusal, and
       that explanation routinely NAMES the token it is declining.
    """
    for raw_line in agent_output.splitlines():
        stripped = raw_line.strip()
        for verdict in EntryGateVerdict:
            if stripped == verdict.value:
                return verdict
    for verdict in EntryGateVerdict:
        if verdict in MERGE_PERMITTING_VERDICTS:
            continue
        if re.search(rf"\b{re.escape(verdict.value)}\b", agent_output):
            return verdict
    return None
