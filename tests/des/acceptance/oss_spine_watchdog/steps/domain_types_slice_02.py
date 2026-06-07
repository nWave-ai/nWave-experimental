"""Domain types for oss-spine-watchdog slice-02 (bounded-block terminal N=3).

Mandate-12 criterion 1 (SSOT via Types + Services + DSL): every domain noun the
slice-02 .feature scenarios speak lives here as a typed enum or frozen dataclass.
Step methods + composition consume these typed parameters; raw `str` parameters
are avoided wherever a domain enum exists.

Slice-02 SUT = the G_COMMIT exit-gate SubagentStop intercept's BOUNDED-BLOCK
TERMINAL (DESIGN R-6, the block branch `subagent_stop_handler.py:672-678`). On a
returning atdd_pure crafter whose commit fails an exit gate, the handler emits a
`SliceCommitBlocked` + `{decision:block}` today UNCONDITIONALLY — which Claude Code
re-fires forever (no max-attempts: RCA #68, ledger seq 5,7-16 = 11 identical
blocks for one key). Slice-02: before re-emitting the block, count prior identical
`SliceCommitBlocked` records for `(slice_id, pinned_commit_sha)` from the ledger
(DISCUSS D-8); on the 3rd identical block emit a terminating INDETERMINATE
(non-block return: exit 0, NO `decision:block` body — DESIGN OQ-5 / D-3) instead.
A new SHA or a different block reason RESETS the count (DISCUSS D-4 — genuine
progress is never punished).

The driving port mirrors the shipped, proven G_COMMIT exit-gate sibling
(`tests/des/acceptance/atdd_pure_spine_hardening/steps/slice02_composition.py`):
the REAL `handle_subagent_stop` hook invoked over its JSON stdin protocol as a
subprocess (Mandate-13: driving-port-only, Layer-3/4 wiring; NO in-process
production import for the SUT). Prior `SliceCommitBlocked` records are seeded as
PRECONDITION substrate through the production `AtCompletionLedger` writer (the S2
tolerable-variant — seed precondition state via the real writer, same as the
slice-01 sibling), NEVER a direct-domain call.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "oss-spine-watchdog-demo").
FeatureId = NewType("FeatureId", str)

# A carpaccio slice identifier (e.g. "slice-NN").
SliceId = NewType("SliceId", str)


class BlockProgress(str, Enum):
    """How the block arriving at the handler relates to the seeded prior blocks.

    The N=3 bound (DISCUSS D-4) terminates ONLY on 3 IDENTICAL blocks for the same
    `(slice_id, pinned_commit_sha)`. This enum is the anti-vacuity discriminator —
    it names the three ways the arriving block relates to the 2 seeded prior
    identical blocks, so the AT can prove the terminal fires on IDENTICAL and
    RESETS on genuine progress.

    IDENTICAL  — the arriving block matches the seeded key exactly: same slice,
                 same pinned commit SHA, same block reason. It is the 3rd identical
                 block → the bounded-block terminal must fire (INDETERMINATE,
                 non-block return). This is AT-01, the leading outcome (journey
                 row 2: count ≤ 3 then a terminating INDETERMINATE).

    NEW_SHA    — the agent amended mid-loop, producing a NEW HEAD SHA. The
                 arriving block carries a DIFFERENT `pinned_commit_sha` → a fresh
                 count key starting at 0 → the handler must STILL `{decision:block}`
                 (count reset, NOT terminated). This is AT-02 — genuine progress
                 (a new commit) is not punished by the bound (DISCUSS D-4 guardrail).

    NEW_REASON — the same commit SHA but a DIFFERENT block reason (the prior 2
                 were E1 slice-commit-completeness failures; this one is an E2
                 contract-gate failure). A different reason is genuine movement
                 (the agent fixed E1, now E2 fails) → the count must RESET → still
                 `{decision:block}`. This is AT-03 — the reason axis of the reset
                 guardrail, distinct from the SHA axis (AT-02).
    """

    IDENTICAL = "identical to the prior blocks"
    NEW_SHA = "for a newly amended commit"
    NEW_REASON = "for a different gate failure"


class InterceptDecision(str, Enum):
    """What the G_COMMIT intercept decided — observable on the hook's stdout/exit.

    RE_FIRED is today's unconditional behaviour: the handler emits a
    `{"decision":"block"}` body on stdout (exit 0) → Claude Code re-fires the
    agent. For a NON-identical block (genuine progress) this is the CORRECT
    outcome (the agent should keep working on its new commit / new failure).

    TERMINATED is the slice-02 NEW behaviour (DESIGN OQ-5 / D-3): on the 3rd
    IDENTICAL block the handler emits a terminating INDETERMINATE — exit 0 with
    NO `{decision:block}` body — so the harness reaches a terminal Stop instead
    of re-firing forever, AND a loud diagnostic names the bounded-block reason.
    """

    RE_FIRED = "re-fires the agent"  # `{decision:block}` present on stdout
    TERMINATED = "terminates loud"  # no `decision:block`; INDETERMINATE


@dataclass(frozen=True)
class InterceptOutcome:
    """Observable outcome of ONE real G_COMMIT SubagentStop intercept invocation.

    The driving port is the real `handle_subagent_stop` hook subprocess (Layer-3/4
    wiring). The universe entries `assert_state_delta` tracks are built from THIS
    dataclass's port-exposed fields. Internal plumbing (Popen handle, env dict, the
    transcript JSONL bytes, the raw ledger file path) is NEVER in the universe
    (Mandate 8 — port-exposed observables only).

    - `blocked`         — True iff the hook stdout carried a `{"decision":"block"}`
                          body (the re-fire signal). False on a terminating
                          INDETERMINATE (the absence of a block decision is the
                          terminal, per DESIGN OQ-5).
    - `decision_event`  — the `event` field of the `{decision:block}` body when
                          blocked (`SliceCommitBlocked`), else None.
    - `diagnostic`      — the operator-facing diagnostic text the hook surfaced
                          (the block `reason` when re-fired, or the loud
                          INDETERMINATE warning when terminated). The bounded-block
                          terminal must NAME the bound in this text (DISCUSS KPI-2 /
                          the loud half of "loud → terminating").
    - `names_bound`     — True iff `diagnostic` names the bounded-block terminal
                          reason (a non-empty bound-naming token), proving the
                          terminal is LOUD about WHY it terminated — not a silent
                          allow.
    """

    blocked: bool
    decision_event: str | None
    diagnostic: str
    names_bound: bool


# --- Phrase -> typed-value lookup tables (Mandate-12 DSL emergence) -------

PROGRESS_BY_PHRASE: dict[str, BlockProgress] = {p.value: p for p in BlockProgress}


__all__ = [
    "PROGRESS_BY_PHRASE",
    "BlockProgress",
    "FeatureId",
    "InterceptDecision",
    "InterceptOutcome",
    "SliceId",
]
