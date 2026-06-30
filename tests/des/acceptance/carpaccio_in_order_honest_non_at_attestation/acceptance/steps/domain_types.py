"""Domain types for the carpaccio-in-order-honest-non-at-attestation slice-01.

Mandate-12 criterion 1: every domain noun used in the slice-01 Gherkin is
expressed once here as a typed enum / NewType. Step bodies and the composition
service consume these typed parameters -- no raw ``str`` where a domain enum
exists.

Slice-01 (walking skeleton) vocabulary -- the honest prose-attestation chain:

  * ``SliceProseDelivered`` -- the NEW honest ledger record a prose slice mints
    from a doc-review APPROVED verdict (DDD-2). Attested but not AT-verified.
  * the in-order GATE OUTCOME -- whether the live carpaccio intercept ALLOWS the
    successor or BLOCKS it ``CarpaccioSliceOutOfOrder``.
  * the LEDGER-RECORD KIND distinction -- a prose-delivered record is NEVER a
    fabricated ``SliceCommitVerified`` (the honesty invariant).
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier.
FeatureId = NewType("FeatureId", str)

# A ``slice-NN`` slice identifier (e.g. "slice-02").
SliceId = NewType("SliceId", str)


class GateOutcome(str, Enum):
    """The observable decision of the live in-order carpaccio gate.

    PROCEEDS  -- the live ``evaluate_atdd_pure_dispatch`` hook did NOT raise a
                 ``CarpaccioSliceOutOfOrder`` block for the successor slice: the
                 predecessor's honest record satisfied the in-order predicate,
                 so the successor enters A_GREEN (US-02 observable value).
    WEDGED    -- the hook returned a ``CarpaccioSliceOutOfOrder`` block: the
                 predecessor carried no record the gate accepts (the today
                 behaviour the feature removes for an honest prose predecessor).
    """

    PROCEEDS = "proceeds"
    WEDGED = "wedged"


class LedgerRecordKind(str, Enum):
    """The honest record kind a delivered predecessor carries on the ledger.

    The kinds stay semantically DISTINCT (hard constraint): a prose slice is
    ``PROSE_DELIVERED`` (doc-review-attested), a non-Python-target degraded
    commit is ``INDETERMINATE`` (interpreter-unavailable), NEVER a fabricated
    ``VERIFIED``.

    PROSE_DELIVERED -- a ``SliceProseDelivered`` event (the prose honest record).
    INDETERMINATE   -- a ``SliceCommitIndeterminate`` event (the non-Python-target
                       degrade record, slice-02). Honest "unverified on this
                       machine", carries a free-text ``reason``.
    VERIFIED        -- a ``SliceCommitVerified`` event (the AT-PASS code-slice
                       record). A prose / degraded slice must NEVER carry this --
                       minting it would be theater.
    """

    PROSE_DELIVERED = "SliceProseDelivered"
    INDETERMINATE = "SliceCommitIndeterminate"
    VERIFIED = "SliceCommitVerified"


class CommitOutcome(str, Enum):
    """The observable outcome of a ``des commit-slice`` invocation (slice-02).

    LANDED  -- the predecessor commit was written to HEAD carrying its Slice-Id /
               Gate-Scope trailers, even though the committed-scope digest could
               not be established (the non-Python-target degrade still commits).
    REFUSED -- ``commit-slice`` rejected the input (malformed) and wrote nothing.
    """

    LANDED = "landed"
    REFUSED = "refused"


# The honest free-text degrade reason the ``commit-slice`` indeterminate mint
# carries (slice-02, DDD-6). NOT a closed enum on the production side -- this is
# the first value the AT pins; degrade-LOUD keeps the taxonomy open.
DEGRADE_REASON_INTERPRETER_UNAVAILABLE = "gate_scope_interpreter_unavailable"

# NOTE: the slice-03 DDD-7 prose-mint honesty-guardrail vocabulary
# (``MintOutcome`` + ``PROSE_MINT_REFUSED_EVENT``) was PARKED per ADR-FLOW-010
# (future-slice scaffolds absent). The guardrail is unbuilt and the prose-mint
# producer is not wired into the ``des`` dispatcher; its value is recorded in
# docs/product/backlog.md (F-CONSOLIDATION-DDD7-PROSE-MINT-HONESTY-GUARDRAIL)
# for canonical re-implementation when the prose-mint feature is wired.
