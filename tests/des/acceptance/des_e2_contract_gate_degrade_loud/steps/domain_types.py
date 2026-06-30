"""Domain types for the des-e2-contract-gate-degrade-loud acceptance slice.

Mandate-12 criterion 1: every domain noun used in the Gherkin is expressed
once via the type system. The interpreter-absence degrade-loud story has a
small, closed vocabulary -- the interpreter availability the E2 contract gate
resolves against, the gate outcome it degrades to, the ledger record the
verify-slice-commit producer mints, and the carpaccio entry verdict the
in-order guard returns.

slice-01 of fix-des-e2-contract-gate-degrade-loud: a single S-cohort slice
across three production surfaces (run_contract_gate degrade-loud,
verify_slice_commit record, carpaccio in-order guard accept) plus a Python
happy-path preservation guard.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


FeatureId = NewType("FeatureId", str)
SliceId = NewType("SliceId", str)


class InterpreterAvailability(Enum):
    """Whether the target machine resolves a pytest-capable interpreter.

    The single domain noun the E2 contract gate degrade-path keys on. The
    UNAVAILABLE variant is the non-Python-target case the feature unblocks:
    ``python_for("pytest")`` raises ``InterpreterUnavailable`` rather than
    returning a known-bad interpreter, and the gate must degrade LOUD to
    INDETERMINATE-and-proceed instead of hard-refusing (exit 2).
    """

    # A usable pytest-capable interpreter resolves -- the Python happy path
    # (AC-4 preservation: the gate runs and SliceCommitVerified is minted).
    AVAILABLE = "available"
    # No interpreter on the fallback ladder satisfies "pytest" --
    # ``InterpreterUnavailable`` is raised. The non-Python-target case
    # (AC-1/AC-2: degrade LOUD INDETERMINATE, never exit-2 hard-refuse).
    UNAVAILABLE = "unavailable"


class GateOutcome(Enum):
    """The observable outcome the E2 contract gate degrades to.

    INDETERMINATE is the honest "could not verify on this machine" the
    interpreter-absent path must emit (LOUD marker + non-refuse return),
    distinct from the exit-2 HARD_REFUSE status quo this feature replaces and
    from the PASS the Python happy path still earns.
    """

    # The gate emitted a LOUD INDETERMINATE event and PROCEEDED (return != 2).
    INDETERMINATE = "indeterminate"
    # The status-quo exit-2 hard refuse (`_emit_interpreter_unavailable`) --
    # the behaviour AC-1 forbids on interpreter-absence.
    HARD_REFUSE = "hard_refuse"
    # A usable interpreter + a passing gate (return 0) -- the preserved path.
    PASS = "pass"


class LedgerRecord(Enum):
    """The terminal AT-completion ledger record the verify-slice-commit mints.

    The honest-record domain noun: on an INDETERMINATE E2 the producer appends
    ``SliceCommitIndeterminate`` (never a fabricated ``SliceCommitVerified``);
    on a passing Python gate it still mints ``SliceCommitVerified``.
    """

    # Honest "unverified on this machine" -- the new record AC-2 asserts.
    SLICE_COMMIT_INDETERMINATE = "SliceCommitIndeterminate"
    # The genuine pass record -- AC-2 asserts its ABSENCE; AC-4 asserts its
    # PRESENCE (INDETERMINATE is never coerced to PASS, PASS never downgraded).
    SLICE_COMMIT_VERIFIED = "SliceCommitVerified"


class EntryGateVerdict(Enum):
    """The observable verdict the carpaccio in-order guard returns for a dispatch.

    AC-3: with a ``SliceCommitIndeterminate`` predecessor seeded, the U1
    carpaccio intercept must ALLOW the successor slice's entry (treat the
    INDETERMINATE predecessor as satisfying in-order), not BLOCK it
    ``CarpaccioSliceOutOfOrder``.
    """

    ALLOWED = "allowed"
    BLOCKED = "blocked"
