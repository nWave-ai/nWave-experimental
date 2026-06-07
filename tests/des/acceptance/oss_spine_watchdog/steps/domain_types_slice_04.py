"""Domain types for oss-spine-watchdog slice-04 (terminal-coherence feature-end-fix).

Mandate-12 criterion 1 (SSOT via Types + Services + DSL): every domain noun the
slice-04 .feature scenarios speak lives here as a typed enum or frozen dataclass.
Step methods + composition consume these typed parameters; raw `str` parameters
are avoided wherever a domain enum exists.

Slice-04 = the cross-slice terminal wire-format coherence fix the deep feature-end
review (`a360758f`, 2026-06-05) REJECTED the coherent feature on. The 3 prior
slices each ship correctly individually, but the DDD-5 terminating-INDETERMINATE
wire-format (non-block + loud stderr + DURABLE ledger record) was realized
INCONSISTENTLY across the 3 terminals. Slice-04 EXTRACTs one shared
`_emit_terminating_indeterminate(event, reason)` (durable ledger record + loud
stderr + DV-2 audit KPI event) so every terminal honours DDD-5, closing:

  * BLOCKER-2 (R-69-A) — the slice-02 bounded-block terminal
    (`_emit_bounded_block_terminal`, `subagent_stop_handler.py:518-541`) is
    stderr-ONLY: it prints to `sys.__stderr__` and `return 0` with NO
    `_append_record`. So `grep SliceCommitBlockedTerminal src/` = 0 — the durable
    record DDD-5/DV-1 require is NEVER written, and KPI-2 ("the 3rd block paired
    with a terminal record") is UNMEASURABLE as shipped. The GREEN retrofit routes
    the bounded-block terminal through the shared helper so it writes a durable
    `SliceCommitBlockedTerminal` record.

  * BLOCKER-3 (R-69-B) — the slice-03 stale-check no-double-close precondition keys
    on `_EXISTING_TERMINAL_EVENTS = {SliceCommitVerified, SliceCommitBlocked}`
    (`subagent_stop_handler.py:692`). `SliceCommitBlocked` is the NON-terminal
    re-fire record (2 precede every bounded-block), NOT a genuine terminal. So a
    bounded-block-terminated agent leaves historical `SliceCommitBlocked` records;
    a LATER cross-invocation stale check reads one, treats it as a terminal, and
    LEAVES A GENUINELY-STUCK AGENT ALONE (a false-negative — the exact silent-hang
    the feature exists to kill). The GREEN re-keys `_EXISTING_TERMINAL_EVENTS` onto
    GENUINE terminals `{SliceCommitVerified, SliceCommitBlockedTerminal,
    StaleAgentClosed}` — dropping the non-terminal `SliceCommitBlocked`.

── DRIVING PORT (Mandate-13, invariant 1+2): real hook subprocess ──
The driving port mirrors the shipped, proven slice-02 + slice-03 siblings: the REAL
`handle_subagent_stop` SubagentStop hook invoked over its JSON stdin protocol AS A
SUBPROCESS (Mandate-13: driving-port-only, Layer-3/4 wiring; NO in-process
production import of the SUT at the test boundary). `AtCompletionLedger` is imported
ONLY to SEED precondition records (the S2 tolerable-variant — seed precondition
state through the production writer); it is substrate, NEVER the SUT.

  * AT-01 drives the G_COMMIT exit-gate bounded-block terminal (mirror
    composition_slice_02.py `_fire_hook`): seed 2 prior identical
    `SliceCommitBlocked` for `(slice, pinned_sha)`, fire the hook once → that
    single invocation IS the 3rd identical block → the bounded-block terminal must
    fire. The OBSERVABLE is the DURABLE RECORD: a re-read count delta on
    `SliceCommitBlockedTerminal` (mirror composition_slice_03.py
    `_read_stale_closed_count`). RED today: the terminal writes NO record → delta 0.

  * AT-02 drives the stale-check (mirror composition_slice_03.py): for the
    NON-TERMINAL block-record case, seed a historical `SliceCommitBlocked` (a
    re-fire record, NOT a terminal) + a STALE last-progress, fire → the agent must
    be CLOSED (`StaleAgentClosed`), because a regular `SliceCommitBlocked` is NOT a
    genuine terminal. RED today: the current `_EXISTING_TERMINAL_EVENTS` includes
    `SliceCommitBlocked` → the stale-check sees the historical block as a terminal →
    does NOT close → the stuck agent is wrongly left alone. PAIRED (anti-vacuity)
    with the GENUINE-TERMINAL case: seed a `SliceCommitVerified` (a real completed
    terminal) + a STALE last-progress, fire → the agent must NOT be closed (the
    no-double-close precondition is PRESERVED post-GREEN). A re-key that simply
    dropped the precondition would red the genuine-terminal pin.

── Mechanical assertion (Mandate-13 invariant 5) ──
Python + git + filesystem only (the hook resolves a real repo + reads/writes a real
ledger JSONL, as in production), cross-OS. The terminal is exit 0 with NO
`{decision:block}` body (DESIGN OQ-5 / DEVOPS: loud via stderr + ledger record,
NEVER a non-zero exit). The DURABLE-RECORD observable (AT-01) is a re-read count
delta on the ledger — a port-exposed observable, never an internal field.

Layer 3/4 (real git repo + real ledger JSONL + real hook subprocess against
tmp_path): example-only (Mandate 9 v2 — @real-io because the driven set includes a
real filesystem adapter + a real git subprocess + a real hook subprocess → NOT PBT;
Mandate 11 — sad paths enumerated explicitly). No PBT machinery imported.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "oss-spine-watchdog-demo").
FeatureId = NewType("FeatureId", str)

# A carpaccio slice identifier (e.g. "slice-NN").
SliceId = NewType("SliceId", str)


class PriorTerminalKind(str, Enum):
    """Which kind of prior ledger record precedes a STALE returning agent (AT-02).

    The slice-04 BLOCKER-3 fix re-keys the stale-check no-double-close precondition
    onto GENUINE terminals only. This enum names the two ledger histories the AT
    seeds to prove the re-key — both with a STALE last-progress gap, so the ONLY
    discriminator is whether the prior record is a GENUINE terminal:

    NON_TERMINAL_BLOCK — the agent's history holds a regular `SliceCommitBlocked`
        re-fire record (the kind a bounded-block-terminated agent leaves behind:
        2 precede every bounded-block). It is NOT a terminal. With a STALE gap and
        no genuine terminal, the stale check MUST CLOSE the agent (`StaleAgentClosed`)
        — a regular block must not be mistaken for a terminal. This is the
        BLOCKER-3 pin: RED today, because the current `_EXISTING_TERMINAL_EVENTS`
        includes `SliceCommitBlocked`, so the stale check wrongly treats the
        historical block as a terminal and LEAVES THE STUCK AGENT ALONE.

    GENUINE_TERMINAL — the agent's history holds a `SliceCommitVerified` (a real
        completed terminal). With a STALE gap, the stale check MUST NOT close it
        (the no-double-close precondition — an already-finished agent is never
        re-closed). This is the anti-vacuity pin: GREEN today and MUST STAY GREEN
        post-GREEN — a re-key that simply dropped the precondition (always-close on
        a stale gap) would wrongly close here.
    """

    NON_TERMINAL_BLOCK = "a re-fire block on record"
    GENUINE_TERMINAL = "a completed terminal on record"


@dataclass(frozen=True)
class BoundedTerminalOutcome:
    """Observable outcome of ONE real bounded-block terminal hook invocation (AT-01).

    The driving port is the real `handle_subagent_stop` G_COMMIT exit-gate hook
    subprocess (Layer-3/4 wiring). The universe entries `assert_state_delta` tracks
    are built from THIS dataclass's port-exposed fields. Internal plumbing (Popen
    handle, env dict, the transcript JSONL bytes, the raw ledger file path) is NEVER
    in the universe (Mandate 8 — port-exposed observables only).

    - `terminal_recorded` — True iff a NEW durable `SliceCommitBlockedTerminal`
                            record was appended to the AT-completion ledger for this
                            `(slice, pinned_commit_sha)` between the before-snapshot
                            and the after-snapshot (a re-read count delta — the
                            durable half of "loud", readable post-mortem by a
                            not-watching operator, DDD-5/DV-1, KPI-2). This is the
                            BLOCKER-2 pin: RED today (the stderr-only terminal writes
                            NO record → delta 0), GREEN once the bounded-block
                            terminal routes through the shared
                            `_emit_terminating_indeterminate` that writes the durable
                            record (R-69-A).
    - `blocked`           — True iff the hook stdout carried a `{decision:block}`
                            body. The bounded-block terminal is NON-block (DESIGN
                            OQ-5), so the terminated outcome is NOT blocked. Tracked
                            so the AT can prove the durable record accompanies a
                            genuine terminal (a non-block return), not a re-fire.
    """

    terminal_recorded: bool
    blocked: bool


@dataclass(frozen=True)
class CrossInvocationOutcome:
    """Observable outcome of ONE real cross-invocation stale-check hook (AT-02).

    The driving port is the real `handle_subagent_stop` stale-check hook subprocess
    (Layer-3/4 wiring), fired against a returning agent whose history holds a prior
    ledger record (a non-terminal block OR a genuine terminal — `PriorTerminalKind`)
    and whose last progress is STALE. The universe entries are built from THIS
    dataclass's port-exposed fields; internal plumbing is NEVER in the universe
    (Mandate 8).

    - `closed`  — True iff the hook emitted a `StaleAgentClosed` terminal for this
                  agent (a NEW durable `StaleAgentClosed` record was appended — a
                  re-read count delta). For NON_TERMINAL_BLOCK this MUST be True
                  (the historical block is not a terminal, so the stuck agent is
                  closed — the BLOCKER-3 pin, RED today). For GENUINE_TERMINAL this
                  MUST be False (the no-double-close precondition — the anti-vacuity
                  pin, GREEN today, must stay GREEN).
    - `blocked` — True iff the hook stdout carried a `{decision:block}` body. The
                  stale terminal is NON-block (DESIGN OQ-5); a normal return on the
                  generic atdd_pure path is also not blocked. Tracked so the AT can
                  prove the close is the ABSENCE of a block.
    """

    closed: bool
    blocked: bool


# --- Phrase -> typed-value lookup tables (Mandate-12 DSL emergence) -------

PRIOR_TERMINAL_KIND_BY_PHRASE: dict[str, PriorTerminalKind] = {
    k.value: k for k in PriorTerminalKind
}


__all__ = [
    "PRIOR_TERMINAL_KIND_BY_PHRASE",
    "BoundedTerminalOutcome",
    "CrossInvocationOutcome",
    "FeatureId",
    "PriorTerminalKind",
    "SliceId",
]
