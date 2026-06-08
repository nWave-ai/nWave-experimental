"""Domain types for the gate-trailer-read-git-port-extract slice-01 ATs.

Mandate-12 criterion 1: every domain noun used in the Gherkin is expressed once
here as a typed enum or NewType. Step bodies and the composition service consume
these typed parameters -- no raw `str` where a domain enum exists.

Bounded context: the deliver-integrity done-gate's commit-trailer read seam
(DESIGN DDD-G1..G4). The gate either CANNOT-EVALUATE the trailer history (git
absent / not a work-tree -> LOUD INDETERMINATE, exit 4) or RECONCILES it (the
history was read and every shipped slice has a ledger record -> exit 0).
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


class GitSubstrate(str, Enum):
    """The git readability of the synthetic deliver-project substrate.

    The done-gate's commit-trailer read seam consults git to collect the
    `Slice-Id:` trailers. Each substrate exercises one materially-distinct
    cannot-read / can-read decision-table row (DESIGN SUT verdict model C2/C6).

    NOT_A_WORK_TREE -- a real directory with the .nwave ledger substrate but NO
                       `.git` (never `git init`-ed). `git log` raises
                       `CalledProcessError` (fatal: not a git repository) -> the
                       seam MUST degrade LOUD to Indeterminate (exit 4), never
                       the silent `frozenset()` that reads as "nothing shipped".
    GIT_BINARY_ABSENT -- the same non-work-tree substrate, but the git binary is
                         masked off `PATH` for the subprocess. `git log` raises
                         `FileNotFoundError` -> the SAME LOUD Indeterminate
                         (exit 4). Proves the degrade is uniform across both
                         git-absence failure modes.
    REAL_WORK_TREE_WITH_SLICE -- a genuine `git init` work-tree carrying a commit
                         whose body has a `Slice-Id: slice-NN` trailer, plus a
                         matching ledger record. The history IS readable ->
                         the gate reconciles cleanly (exit 0). The non-vacuity
                         control: the refusal is bound to readability, not
                         vacuously always-on (KPI #2 guardrail).
    """

    NOT_A_WORK_TREE = "not_a_work_tree"
    GIT_BINARY_ABSENT = "git_binary_absent"
    REAL_WORK_TREE_WITH_SLICE = "real_work_tree_with_slice"


class GateVerdict(str, Enum):
    """The user-observable verdict of one des verify-integrity invocation.

    Maps onto the CLI exit-code contract (DESIGN: atdd_pure reuses 0/1; this
    feature ADDS the distinct cannot-evaluate exit 4 per D1, NEVER conflated
    with the exit-1 unreconciled verdict).

    CANNOT_EVALUATE -- exit 4 + the LOUD `health.gate.deliver-integrity.indeterminate`
                       event (`FeatureIndeterminate` single-line JSON). The
                       trailer history could not be READ.
    UNRECONCILED    -- exit 1 + the `FeatureUnreconciled` event. The history WAS
                       read but a shipped slice lacks a `SliceCommitVerified`
                       ledger record. Structurally distinct from CANNOT_EVALUATE
                       (DDD-G4: never conflate).
    RECONCILED      -- exit 0 + the `FeatureReconciled` event. The history was
                       read and every shipped slice has a ledger record.
    OTHER           -- any other exit code (0 with a non-reconciled trace, 2
                       usage). Captured so the silent-pass RED is observable as
                       a distinct, non-CANNOT_EVALUATE verdict.
    """

    CANNOT_EVALUATE = "cannot_evaluate"  # exit 4
    UNRECONCILED = "unreconciled"  # exit 1
    RECONCILED = "reconciled"  # exit 0 + FeatureReconciled
    OTHER = "other"


# The LOUD cannot-evaluate event name (DESIGN: the `health.gate.<role>.indeterminate`
# family established by committed_scope_port.py:46). Emitted on stdout as a
# single-line JSON `FeatureIndeterminate` payload when the trailer history is
# unreadable.
CANNOT_EVALUATE_EVENT = "health.gate.deliver-integrity.indeterminate"

# The single-line JSON event marker the cannot-evaluate verdict carries on stdout.
INDETERMINATE_JSON_EVENT = "FeatureIndeterminate"

# The exit code reserved for the distinct cannot-evaluate non-pass (D1; exit 4
# is NOT one of the verifier's existing 0/1/2 codes, so it is unambiguously
# distinct from the exit-1 FeatureUnreconciled).
CANNOT_EVALUATE_EXIT = 4

# A kebab-case feature identifier (e.g. "gate-trailer-read-demo").
FeatureId = NewType("FeatureId", str)


# Gherkin-phrase -> typed GitSubstrate lookup. Keeping this as a module-level
# dict lets each Given step body stay a single typed lookup + a single
# composition call (Mandate-12 criterion 3: no control flow in step bodies).
SUBSTRATE_BY_PHRASE: dict[str, GitSubstrate] = {
    "is not a git work-tree": GitSubstrate.NOT_A_WORK_TREE,
    "the git binary is unavailable": GitSubstrate.GIT_BINARY_ABSENT,
    "carrying a recorded shipped slice": GitSubstrate.REAL_WORK_TREE_WITH_SLICE,
}
