"""Domain types for autonomous-consolidation-and-bugfix-loops slice-04
(trunk-health signals become queue items that never vanish, charter
`trunk-health-signals-become-queue-items-that-never-vanish.md`).

Mandate-12 criterion 1 (SSOT via Types + Services + DSL): every domain noun
the slice-04 ``.feature`` scenarios speak lives here as a typed enum or
frozen dataclass. Step methods + composition consume these typed parameters;
raw ``str`` parameters are avoided wherever a domain enum exists.

── REUSE, DON'T REBUILD (D-4/D-19 resolution) ──
``SignalType`` below is the ONLY net-new vocabulary this slice introduces.
Everything downstream of intake -- ``PipelineStage``, ``PipelineAction``,
``FULL_CHAIN_ORDER`` -- is the SAME vocabulary slice-03 already ships
(imported from ``domain_types_slice_03``, never re-declared). Full contract:
``src/des/cli/consolidation_signal_tick.py`` module docstring.

── The D-8/D-20 no-duplicate guard ──
A signal is "already queued" iff the ledger carries a
``PipelineStageStarted`` record for the deterministic ``defect_id`` derived
from ``(signal_type, signal_key)`` -- re-detecting it MUST NOT append a
second such record (idempotent recognition of the existing item, charter
Negative-2).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NewType


# A kebab-case signal-instance identifier (arbitrary per-scenario fixture
# key -- a branch name, a gate name, or "trunk" for drift -- not a real
# git/CI object).
SignalKey = NewType("SignalKey", str)

# A kebab-case feature identifier.
FeatureId = NewType("FeatureId", str)


class SignalType(str, Enum):
    """One of the four trunk-health signal classes the consolidation loop
    detects (feature-delta Slice Plan row slice-04, verbatim).

    Each value is BOTH the CLI's ``--signal-type`` wire value AND the
    Gherkin phrase the ``.feature`` file speaks -- Mandate-12 DSL emergence
    (one typed vocabulary, no separate business-phrase-to-enum table
    needed).
    """

    DRIFT = "drift"
    UNMERGED_WORK = "unmerged-work"
    STALE_BRANCH = "stale-branch"
    FAILING_GATE = "failing-gate"


# The four supported signal-type wire values -- used by the composition
# fixture to build an intentionally-unsupported value for AT-21 without
# hand-duplicating the enum's own member list.
SUPPORTED_SIGNAL_TYPE_VALUES: frozenset[str] = frozenset(
    member.value for member in SignalType
)


@dataclass(frozen=True)
class IntakeOutcome:
    """Observable outcome of a SEQUENCE of consolidation-signal-tick ticks
    (Layer 3/4).

    The driving port is the real ``des consolidation-signal-tick`` CLI entry
    (``des.cli.consolidation_signal_tick.main``), driven IN-PROCESS once per
    detected signal. Universe entries ``assert_state_delta`` tracks are
    built from THIS dataclass's port-exposed fields ONLY -- never a Popen
    handle, an argv list, the raw ledger file path, or the derived
    ``defect_id`` string itself (Mandate 8).

    - `queue_item_count`             -- distinct queue items observed,
                                         scoped either to ONE signal (AT-17,
                                         AT-20, AT-21 -- "does this signal
                                         have exactly one item, not zero and
                                         not two?") or to the WHOLE sample
                                         (AT-18, AT-22 -- "how many distinct
                                         items exist across every signal
                                         detected so far?"), per the
                                         composition method invoked.
    - `traceable_to_signal`          -- True iff exactly one queue item was
                                         found for the queried signal AND its
                                         ledger record names both the signal
                                         type and the signal key (charter
                                         Positive-1: "traceable back to the
                                         specific signal").
    - `full_chain_traceable`         -- True iff the ledger carries the full
                                         ordered chain RCA -> charter -> AT
                                         -> RED-seal -> GREEN -> examine ->
                                         commit-slice for the queued signal's
                                         item -- the SAME field name
                                         slice-03's ``PipelineOutcome`` uses,
                                         intentionally, signalling this is
                                         the identical shared-pipeline
                                         observable, not a lookalike (D-19).
    - `slice_commit_verified_present`-- True iff a `PipelineStageCompleted`
                                         record for `COMMIT_SLICE` (the
                                         `SliceCommitVerified`-class record)
                                         exists for that item.
    - `intake_rejected`              -- True iff an unsupported signal type
                                         was correctly REFUSED
                                         (`ConsolidationSignalIntakeRejected`
                                         appended) rather than silently
                                         dropped or silently queued anyway.
    - `rejection_reason_named`       -- True iff that rejection record
                                         carries a non-empty ``reason``.
    - `cli_exit_code`                -- the raw exit code the REAL
                                         ``des consolidation-signal-tick``
                                         CLI returned (EXAMINE fix, Vera
                                         FAIL: a rejection must be observable
                                         on the CLI-FACING surface itself,
                                         not merely the ledger -- a caller
                                         who never reads the ledger must
                                         still see it fail loudly, D-8). `0`
                                         when not captured by a CLI-invoking
                                         composition method (the ledger-only
                                         sampling methods leave this at its
                                         zero default).
    - `cli_output_names_unsupported_type` -- True iff the CLI's emitted
                                         stdout line names the literal
                                         unsupported ``signal_type`` value
                                         that was rejected (self-explaining
                                         WHAT).
    - `cli_output_names_supported_set`    -- True iff the CLI's emitted
                                         stdout line names EVERY member of
                                         `SUPPORTED_SIGNAL_TYPE_VALUES`
                                         (self-explaining HOW: what the
                                         caller should have sent instead).
    """

    queue_item_count: int
    traceable_to_signal: bool
    full_chain_traceable: bool
    slice_commit_verified_present: bool
    intake_rejected: bool
    rejection_reason_named: bool
    cli_exit_code: int = 0
    cli_output_names_unsupported_type: bool = False
    cli_output_names_supported_set: bool = False


__all__ = [
    "SUPPORTED_SIGNAL_TYPE_VALUES",
    "FeatureId",
    "IntakeOutcome",
    "SignalKey",
    "SignalType",
]
