"""Domain types for oss-spine-watchdog slice-06 (timeout-block countability).

Mandate-12 criterion 1 (SSOT via Types + Services + DSL): every domain noun the
slice-06 .feature scenarios speak lives here as a typed enum or frozen dataclass.
Step methods + composition consume these typed parameters; raw `str` parameters
are avoided wherever a domain enum exists.

Slice-06 closes residue R-69-F (the timeout-countability gap), surfaced by the
feature-end deep review (`a01511d9`). The defect lives in the G_COMMIT exit-gate
handler's `except subprocess.TimeoutExpired` path
(`subagent_stop_handler.py:1047-1052`):

    except subprocess.TimeoutExpired as exc:
        _emit_g_commit_ledger_event(resolved, "SliceCommitBlocked")   # FIELDLESS
        return _emit_atdd_pure_block(..., "GateInvocationTimeout")

The NORMAL block path (`:1036-1041`) emits `SliceCommitBlocked` WITH
`pinned_commit_sha=pinned_sha` + `block_reason=failed`, so the bounded-block count
(`count_slice_commit_blocked`, which keys on `(slice_id, pinned_commit_sha,
block_reason)`) can match identical-key priors and terminate at N=3. The TIMEOUT
path emits a FIELDLESS `SliceCommitBlocked` — no `pinned_commit_sha`, no
`block_reason` — so `count_slice_commit_blocked` can NEVER match it. A
gate-subprocess-TIMEOUT-driven re-fire loop on the SAME commit is therefore
UNCOUNTABLE → the N=3 bound (slice-02) is DEFEATED for timeout-originated blocks
(backstopped only by slice-03's coarse stale-timeout).

Slice-06 GREEN target (DISCUSS Slice Plan slice-06 / EXTEND): thread
`pinned_commit_sha=pinned_sha` (already resolved before the gate call at `:933`) +
`block_reason="gate-timeout"` into the timeout-except emit — so identical timeout
blocks on the same `(slice_id, pinned_sha, "gate-timeout")` key count toward N=3
and the bounded-block terminal fires on the 3rd, exactly like an ordinary block.

── DRIVING PORT (Mandate-13, invariant 1+2): real hook subprocess ──
Slice-06 drives the REAL `handle_subagent_stop` G_COMMIT exit-gate hook over its
JSON stdin protocol AS A SUBPROCESS — exactly as the shipped, proven slice-02
(`composition_slice_02.py`) + slice-05 (`composition_slice_05.py`) siblings drive
it — against a real git repo under tmp_path, with the gate subprocess forced to
TIME OUT via the production timeout-fault seam (`NWAVE_U2_FORCE_GATE_TIMEOUT=1`,
the GREEN-added sibling of the existing `NWAVE_U2_FORCE_HANDLER_FAULT` test seam at
`:917`). This produces a REAL `subprocess.TimeoutExpired` deterministically and
fast — NOT a 120s sleep (a real-timeout test would be too slow; the seam is the
realistic fast injection point the composition machinery supports). The OBSERVABLE
is the durable terminal record + non-block return of the REAL gate, NEVER a direct
`from des...subagent_stop_handler import _handle_g_commit_exit_gate` invocation.
`AtCompletionLedger` is imported ONLY to SEED the 2 prior `(slice, sha,
"gate-timeout")` blocks + RE-READ the durable terminal record (the S2
tolerable-variant — seed/observe through the production writer/reader), NEVER the
SUT.

── THE ANTI-VACUITY DISCRIMINATOR (the divergence pair) ──
  THIRD_IDENTICAL_TIMEOUT — 2 prior `(slice, sha, "gate-timeout")` blocks are
    seeded, then the gate is forced to time out a 3rd time on the SAME key. The
    incoming timeout block is the 3rd identical block → the bounded-block terminal
    must fire (a durable `SliceCommitBlockedTerminal` + non-block return). RED
    today: the timeout emit is FIELDLESS → the 2 seeded fielded priors + the
    fieldless 3rd never reach count==N-1 on a MATCHING key → no terminal →
    `terminated` is False / `blocked` is True. GREEN once the timeout emit threads
    `pinned_commit_sha` + `block_reason="gate-timeout"`.

  FIRST_TIMEOUT_NO_PRIORS — a SINGLE timeout block with NO priors seeded. The
    bounded-block count is 0 (< N-1=2) → the gate takes the ORDINARY block path
    (a `{decision:block}` re-fire), it does NOT terminate. GREEN today and MUST
    STAY GREEN: a gate that terminated EVERY timeout regardless of count would
    wrongly terminate this first, single timeout. The discriminator pins that the
    terminal fires on the Nth IDENTICAL timeout, nothing else.

A fix that NEVER counts the timeout block (today's fieldless emit) fails AT-01 (no
terminal at the 3rd). A fix that ALWAYS terminated a timeout (count-blind) fails
AT-02 (the first single timeout is wrongly terminated). The two cases bracket the
contract: the terminal is keyed on the Nth identical `(slice, sha, "gate-timeout")`
block, exactly like an ordinary block.

── Mechanical assertion (Mandate-13 invariant 5) ──
Python + git + filesystem only (the hook resolves a real repo + seeds/reads a real
ledger JSONL + the forced TimeoutExpired exercises the real except branch),
cross-OS. The terminal is exit 0 with NO `{decision:block}` body (DESIGN OQ-5 /
DV-5: loud via stderr + durable ledger record, NEVER a non-zero exit). The
durable-record observable is a re-read count delta over the GENUINE-terminal event
set (EXCLUDING the non-terminal `SliceCommitBlocked` re-fire record) — a
port-exposed observable, never an internal field.

Layer 3/4 (real git repo + real ledger JSONL + forced-timeout real hook subprocess
against tmp_path): example-only (Mandate 9 v2 — @real-io because the driven set
includes a real filesystem adapter + a real git subprocess + a real hook
subprocess → NOT PBT; Mandate 11 — sad paths enumerated explicitly). No PBT
machinery imported.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "oss-spine-watchdog-demo").
FeatureId = NewType("FeatureId", str)

# A carpaccio slice identifier (e.g. "slice-NN").
SliceId = NewType("SliceId", str)


class TimeoutBlockHistory(str, Enum):
    """How many prior identical timeout blocks precede the arriving timeout.

    The N=3 bound (DISCUSS D-4) terminates ONLY on 3 IDENTICAL blocks for the same
    `(slice_id, pinned_commit_sha, block_reason)`. For a TIMEOUT-originated block
    the reason is `"gate-timeout"`. This enum is the anti-vacuity discriminator —
    it names the two timeout-history topologies the AT builds to prove the timeout
    block is now COUNTABLE (terminates at the 3rd) yet does NOT over-fire on the
    first.

    THIRD_IDENTICAL_TIMEOUT — 2 prior `(slice, sha, "gate-timeout")` blocks are
        seeded; the gate is then forced to time out a 3rd time on the SAME key. It
        is the 3rd identical timeout block → the bounded-block terminal must fire
        (a durable `SliceCommitBlockedTerminal` + a non-block return). This is
        AT-01, the leading outcome (KPI-2: terminate within N=3 — now for timeouts
        too). RED today (the fieldless timeout emit is uncountable → no terminal).

    FIRST_TIMEOUT_NO_PRIORS — no priors seeded; the gate is forced to time out
        once. The bounded-block count is 0 (< N-1=2) → the gate takes the ORDINARY
        block path (a `{decision:block}` re-fire), NOT a terminal. This is AT-02 —
        the anti-vacuity pin: a count-blind fix that terminated EVERY timeout would
        wrongly terminate this first single timeout. GREEN today and MUST STAY
        GREEN.
    """

    THIRD_IDENTICAL_TIMEOUT = "two prior timeout blocks for the slice and commit"
    FIRST_TIMEOUT_NO_PRIORS = "no prior timeout block for the slice and commit"


@dataclass(frozen=True)
class GateOutcome:
    """Observable outcome of ONE real forced-timeout G_COMMIT exit-gate invocation.

    The driving port is the real `handle_subagent_stop` G_COMMIT exit-gate hook
    subprocess (Layer-3/4 wiring), with the gate subprocess forced to time out. The
    universe entries `assert_state_delta` tracks are built from THIS dataclass's
    port-exposed fields. Internal plumbing (Popen handle, env dict, the transcript
    JSONL bytes, the raw ledger file path) is NEVER in the universe (Mandate 8 —
    port-exposed observables only).

    - `terminated` — True iff a NEW durable GENUINE-terminal record (the
                     bounded-block terminal routed through the slice-04 shared
                     `_emit_terminating_indeterminate`, event
                     `SliceCommitBlockedTerminal`) was appended to the
                     AT-completion ledger between the before-snapshot and the
                     after-snapshot (a re-read count delta over the genuine-terminal
                     event set, EXCLUDING the non-terminal `SliceCommitBlocked`
                     re-fire record). The durable half of "loud → terminating",
                     readable post-mortem by a not-watching operator. This is the
                     R-69-F pin: RED today for THIRD_IDENTICAL_TIMEOUT (the timeout
                     emit is fieldless → the count never matches the seeded priors →
                     no terminal → delta 0), GREEN once the timeout emit threads
                     `pinned_commit_sha` + `block_reason="gate-timeout"`.
    - `blocked`    — True iff the hook stdout carried a `{decision:block}` body. The
                     bounded-block terminal is NON-block (DESIGN OQ-5 / DV-5), so a
                     terminated outcome is NOT blocked — the harness reaches a Stop
                     rather than re-firing. RED today for THIRD_IDENTICAL_TIMEOUT
                     (`blocked` is True — the uncountable timeout re-blocks). For
                     FIRST_TIMEOUT_NO_PRIORS `blocked` is True BOTH today and
                     post-GREEN (the first single timeout takes the ordinary block
                     path — the discriminator pins the gate does NOT terminate a
                     first timeout).
    """

    terminated: bool
    blocked: bool


# --- Phrase -> typed-value lookup tables (Mandate-12 DSL emergence) -------

TIMEOUT_HISTORY_BY_PHRASE: dict[str, TimeoutBlockHistory] = {
    k.value: k for k in TimeoutBlockHistory
}


__all__ = [
    "TIMEOUT_HISTORY_BY_PHRASE",
    "FeatureId",
    "GateOutcome",
    "SliceId",
    "TimeoutBlockHistory",
]
