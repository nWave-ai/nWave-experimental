"""Domain types for slice-03 -- the M7 integrity-checked AT-completion ledger.

slice-03 of F-DES-ATDD-PURE-HOOK-GATES (U3 / Mikado T-F). Every domain noun in
the Gherkin is expressed once here as a typed enum or NewType; step bodies and
the composition service consume these typed parameters (Mandate-12 criterion 1).

The slice builds the ledger substrate the U1 carpaccio-order check and the U4
feature-end gate consume: an append-only JSONL ledger
(`.nwave/telemetry/atdd-pure/{feature_id}.jsonl`) where every record carries a
gap-free monotonic `seq` + a `record_hash`, appended under `fcntl.flock`, with a
fail-closed integrity read contract.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "atdd-pure-demo").
FeatureId = NewType("FeatureId", str)

# A carpaccio slice identifier (e.g. "slice-03").
SliceId = NewType("SliceId", str)


class GateEvent(str, Enum):
    """The M4 gate-boundary audit events the U1/U2 hooks emit into the ledger.

    Exactly one carpaccio event (CARPACCIO_GATE_CLEARED | CARPACCIO_GATE_REJECTED)
    is emitted per atdd_pure dispatch U1 intercepts -- the dispatch-count
    reconciliation signal. SLICE_COMMIT_VERIFIED is the terminal record U4 reads
    to derive "all slices shipped".
    """

    CARPACCIO_GATE_CLEARED = "CarpaccioGateCleared"
    CARPACCIO_GATE_REJECTED = "CarpaccioGateRejected"
    SLICE_COMMIT_VERIFIED = "SliceCommitVerified"
    SLICE_COMMIT_BLOCKED = "SliceCommitBlocked"


class LedgerCorruption(str, Enum):
    """The integrity-violation universe the M7 fail-closed read contract covers.

    NONE        -- a well-formed ledger; the read succeeds.
    MALFORMED   -- a non-JSON / non-object line somewhere in the ledger.
    TRUNCATED   -- a short / partial final line (a killed append, S17).
    HASH_MISMATCH -- a record whose `record_hash` does not match its fields
                     (a hand-edit, S21).
    SEQ_GAP     -- a gap in the monotonic per-feature `seq` sequence (a deleted
                   or reordered record, S21).
    """

    NONE = "none"
    MALFORMED = "malformed"
    TRUNCATED = "truncated"
    HASH_MISMATCH = "hash-mismatch"
    SEQ_GAP = "seq-gap"


class ReadVerdict(str, Enum):
    """The user-observable verdict of an integrity-checked ledger read.

    OK      -- the ledger passed its integrity contract; records returned.
    BLOCKED -- a `LedgerIntegrityViolation` was raised; the reader fails closed
               rather than returning a silent undercount.
    """

    OK = "ok"
    BLOCKED = "blocked"


class WritabilityState(str, Enum):
    """The M11 ledger-directory provisioning state.

    PROVISIONABLE -- the ledger directory is absent but creatable; the writer
                     provisions it with `mkdir(parents=True, exist_ok=True)` and
                     the append succeeds.
    UNWRITABLE    -- the append itself raises `OSError`; the writer surfaces a
                     `LedgerSubstrateUnavailable` block (EAFP, no TOCTOU probe).
    """

    PROVISIONABLE = "provisionable"
    UNWRITABLE = "unwritable"


# Gherkin-phrase -> typed-value lookups (Mandate-12 criterion 3: no control
# flow in step bodies -- each body is a single typed lookup + composition call).

CORRUPTION_BY_PHRASE: dict[str, LedgerCorruption] = {
    "well-formed": LedgerCorruption.NONE,
    "a malformed line": LedgerCorruption.MALFORMED,
    "a truncated final line": LedgerCorruption.TRUNCATED,
    "a tampered record hash": LedgerCorruption.HASH_MISMATCH,
    "a gap in the sequence": LedgerCorruption.SEQ_GAP,
}

VERDICT_BY_PHRASE: dict[str, ReadVerdict] = {
    "succeeds": ReadVerdict.OK,
    "is blocked": ReadVerdict.BLOCKED,
}

GATE_EVENT_BY_PHRASE: dict[str, GateEvent] = {
    "a cleared carpaccio gate": GateEvent.CARPACCIO_GATE_CLEARED,
    "a rejected carpaccio gate": GateEvent.CARPACCIO_GATE_REJECTED,
    "a verified slice commit": GateEvent.SLICE_COMMIT_VERIFIED,
    "a blocked slice commit": GateEvent.SLICE_COMMIT_BLOCKED,
}
