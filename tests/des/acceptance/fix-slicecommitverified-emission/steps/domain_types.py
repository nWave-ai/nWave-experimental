"""Domain types for the fix-slicecommitverified-emission acceptance slice.

Mandate-12 criterion 1: every domain noun used in the Gherkin is expressed
once via the type system. The carpaccio entry-gate auto-backfill story has a
small, closed domain vocabulary -- a predecessor-slice ledger state, an
entry-gate verdict, and the typed feature/slice identifiers.

slice-01 of fix-slicecommitverified-emission: the auto-backfill happy path.
slice-02 of fix-slicecommitverified-emission: the auto-backfill fail-closed
rows -- the backfill must NOT false-allow on bad/missing E2-evidence
(``GateScopeSeed.ABSENT`` / ``GateScopeSeed.STALE`` / ``NOT_COMMITTED``).
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


FeatureId = NewType("FeatureId", str)
SliceId = NewType("SliceId", str)


class PredecessorLedgerState(Enum):
    """The ledger state of the entering slice's PREDECESSOR before the gate runs.

    The single domain noun the auto-backfill keys on: whether the predecessor
    slice has a real commit-on-disk and whether its ``SliceCommitVerified``
    record already exists.
    """

    # Commit on disk carrying the predecessor's Slice-Id, but NO
    # SliceCommitVerified ledger record -- the backfill precondition (the
    # `5e11c12b3` case).
    COMMITTED_BUT_UNRECORDED = "committed_but_unrecorded"
    # Commit on disk AND a SliceCommitVerified record already present -- the
    # idempotent case (gate must not re-backfill).
    COMMITTED_AND_RECORDED = "committed_and_recorded"
    # No commit on disk carrying the predecessor's Slice-Id at all -- the
    # backfill cannot run; genuine out-of-order (slice-02 fail-closed).
    NOT_COMMITTED = "not_committed"


class EntryGateVerdict(Enum):
    """The observable verdict the carpaccio entry gate returns for a dispatch."""

    ALLOWED = "allowed"
    BLOCKED = "blocked"


class GateScopeSeed(Enum):
    """How the predecessor commit's ``Gate-Scope:`` trailer is seeded.

    The resolved backfill contract (architect, E1-in-gate + E2-evidence-by-
    digest-VERIFICATION) makes the predecessor commit's ``Gate-Scope:`` trailer
    the E2 evidence the in-gate ``run_contract_gate --verify-gate-scope``
    recomputes against. slice-01 happy paths need the VERIFIABLE variant; the
    other two are slice-02 fail-closed-row prep (note-only here -- slice-02
    authors those scenarios; this enum makes the seed helper parameterizable).
    """

    # A real digest computed via `run_contract_gate --collect-only
    # --print-digest` against the seeded test repo -- matches what the in-gate
    # `--verify-gate-scope` recomputes (slice-01 happy path).
    VERIFIABLE = "verifiable"
    # No `Gate-Scope:` trailer at all -> in-gate verify returns
    # GateScopeUnverified(absent) -> backfill refuses (slice-02 fail-closed).
    ABSENT = "absent"
    # A syntactically-valid but stale 64-zero digest -> verify returns
    # GateScopeUnverified(mismatch) -> backfill refuses (slice-02 fail-closed).
    STALE = "stale"
