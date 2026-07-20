"""Domain types for fix-atdd-pure-spine-dogfood-defects (Mandate-12 criterion 1).

Three atdd_pure-spine defects, three slices:

  slice-00 -- the contract test suite collects clean (all collection errors fixed).
  slice-01 -- the E2 contract gate verifies a real, non-empty test scope.
  slice-02 -- a feature-end-cycle dispatch is accepted by the U0 marker contract.

Every domain noun used in the Gherkin is expressed once here as a typed enum or
NewType. Step bodies and the composition service consume these typed parameters
-- no raw `str` where a domain enum exists.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A SHA-256 hex digest as printed by `run_contract_gate --print-digest`.
Digest = NewType("Digest", str)

# The sha256("") sentinel -- the vacuous digest defect 3 produces.
EMPTY_DIGEST = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


class CollectVerdict(str, Enum):
    """The user-observable outcome of a contract-suite collection probe.

    slice-00 drives the contract tree into one of these states; the walking
    skeleton asserts CLEAN (zero collection errors).
    """

    CLEAN = "clean"  # 0 collection errors -- the tree collects clean
    HAS_ERRORS = "has_errors"  # >=1 collection error -- pytest exits 2


class CollectScope(str, Enum):
    """The shape of the test scope a `--collect-only` digest run observes.

    slice-01's fail-closed guard partitions every collection outcome into one
    of these four classes -- an enumerable, closed condition universe.
    """

    REAL_NON_EMPTY = "real_non_empty"  # the suite collects N>0 node-ids cleanly
    COLLECTION_ERROR = "collection_error"  # pytest exits non-(0,5): collection failed
    ZERO_NODES_EXIT_ZERO = "zero_nodes_exit_zero"  # exit 0 but zero node-ids parsed
    GENUINELY_EMPTY = "genuinely_empty"  # exit 5 -- no tests collected, legitimately


class GuardOutcome(str, Enum):
    """How `run_contract_gate` resolves a `--collect-only` digest request.

    Exit-code-EXACT (BLOCKER 1): DoD-2 mandates the fail-closed path raise
    `_CollectionError` -> exit 2 specifically. UNEXPECTED captures any OTHER
    non-zero exit (exit 1 `GateScopeUnverified`, exit 3/5, argparse error,
    uncaught exception) so a wrong failure mode is caught, never silently
    absorbed into FAILED_CLOSED.
    """

    DIGEST_PRINTED = "digest_printed"  # exit 0 -- a digest of the collected scope
    FAILED_CLOSED = "failed_closed"  # exit 2 -- MalformedInput, guard fired closed
    UNEXPECTED = "unexpected"  # any other non-zero -- a WRONG failure mode


class DispatchPhase(str, Enum):
    """The atdd_pure phase a crafter dispatch carries (ATDDPurePhase member).

    slice-02 drives both per-slice phases and feature-end-cycle phases.
    """

    A_GREEN_ATS = "A_GREEN_ATS"  # a per-slice phase
    D_DISTILL = "D_DISTILL"  # a feature-end-cycle phase
    F_FINAL_REVIEW = "F_FINAL_REVIEW"  # a feature-end-cycle phase
    G_COMMIT = "G_COMMIT"  # the per-slice terminal phase (ADR-028 D6 runs it 3x)


# The closed set of feature-end-cycle phases. G_COMMIT is excluded -- it is the
# per-slice terminal phase, run once per slice, so its coherent scope is a
# `slice-NN` value, not `feature-end`. E_BATCH_REFACTOR was retired
# (commit 1ca40aedc, Ale-ratified, 2026-07-19) and replaced here by D_DISTILL,
# a currently-valid member of the production `FEATURE_END_PHASES` SSOT
# (`src/des/domain/atdd_pure_phases.py`).
FEATURE_END_PHASES = frozenset(
    {
        DispatchPhase.D_DISTILL,
        DispatchPhase.F_FINAL_REVIEW,
    }
)


class DispatchScope(str, Enum):
    """The scope value a DES-SLICE marker carries (Option A closed union).

    `slice-NN` for a per-slice dispatch, the literal `feature-end` for a
    feature-end-cycle dispatch, or a malformed token that the anchored grammar
    rejects.
    """

    SLICE_01 = "slice-01"  # a well-formed per-slice scope
    SLICE_12 = "slice-12"  # a well-formed per-slice scope
    FEATURE_END = "feature-end"  # the feature-end-cycle scope literal (Option A)
    MALFORMED_NODASH = "slice1"  # malformed -- no dash, anchor fails
    MALFORMED_TAIL = "slice-3-->"  # malformed -- garbled tail, anchor fails


class DispatchRecognition(str, Enum):
    """The recognition verdict `classify_atdd_pure_dispatch` returns."""

    VALID = "valid"  # mode + phase + a coherent (phase, scope) pair
    DEFECTIVE = "defective"  # a marker absent / malformed / an incoherent pair
    ABSENT = "absent"  # no atdd_pure mode marker -- a classic dispatch
