"""Domain types for oss-spine-watchdog slice-03 (stale-agent timeout, #68 P2-E).

Mandate-12 criterion 1 (SSOT via Types + Services + DSL): every domain noun the
slice-03 .feature scenarios speak lives here as a typed enum or frozen dataclass.
Step methods + composition consume these typed parameters; raw `str` parameters
are avoided wherever a domain enum exists.

Slice-03 SUT = the SubagentStop hook's stale-agent terminal-state check (DESIGN
OQ-4 / R-7). On a returning atdd_pure agent, the hook computes the wall-clock gap
between the agent's LAST PROGRESS SIGNAL (the AT-completion ledger's most-recent
record `timestamp` for this agent's `(feature_id, slice_id)`) and NOW. If the gap
EXCEEDS the threshold (DESIGN OQ-4: read from R1's `.nwave/config.yaml`
control-plane, DEFAULT 20 minutes) AND no `completed`/`blocked` terminal record
exists for `(feature_id, slice_id)`, the hook emits `StaleAgentClosed` — a
TERMINATING INDETERMINATE: exit 0, NO `{decision:block}` body (DESIGN OQ-5 / D-3),
a loud `sys.__stderr__` warning naming the staleness, and a durable
`StaleAgentClosed` ledger record. The progress signal is the existing ledger
record `timestamp` (`at_completion_ledger.py:703`) — reuse-first, no new
persistence (mirrors D-8).

NO orchestrator poll loop, NO sequencer, NO daemon (DESIGN OQ-4 / D-2). The check
is evaluated WHEN the SubagentStop hook fires — the only event the OSS hooks-only
architecture gives. It is a single conditional inside the existing hook handler
that reads two timestamps and the ledger.

The driving port mirrors the shipped, proven slice-02 sibling
(`composition_slice_02.py`) and the spine-hardening sibling: the REAL
`handle_subagent_stop` hook invoked over its JSON stdin protocol as a subprocess
(Mandate-13: driving-port-only, Layer-3/4 wiring; NO in-process production import
for the SUT). The agent's last-progress ledger record is seeded as PRECONDITION
substrate through the production `AtCompletionLedger` writer carrying an EXPLICIT
`timestamp` (honoured per the F-13 producer-timestamp contract,
`at_completion_ledger.py:665`) — so the stale gap is deterministic WITHOUT a real
wall-clock sleep. This is the S2 tolerable-variant: seed precondition state via
the real writer, NEVER a direct-domain call.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "oss-spine-watchdog-demo").
FeatureId = NewType("FeatureId", str)

# A carpaccio slice identifier (e.g. "slice-NN").
SliceId = NewType("SliceId", str)


class ProgressAge(str, Enum):
    """How old the agent's last progress signal is relative to the threshold.

    The stale terminal (DESIGN OQ-4) fires ONLY when the gap between the agent's
    last progress signal and NOW EXCEEDS the threshold AND no terminal record
    exists. This enum is the threshold-comparison discriminator — it names the
    two relationships between the last-progress timestamp and the threshold, so
    the AT can prove the terminal fires on a STALE gap and is WITHHELD on a fresh
    gap (never punishing a working agent).

    STALE  — the agent's last progress is OLDER than the threshold (e.g. seeded
             25 minutes ago against a 20-minute threshold). The gap EXCEEDS the
             threshold → the stale terminal must fire (StaleAgentClosed, a
             non-block INDETERMINATE). This is AT-01, the leading outcome.

    FRESH  — the agent's last progress is RECENT, WITHIN the threshold (e.g.
             seeded 2 minutes ago against a 20-minute threshold). The gap is
             below the threshold → the hook must NOT close the agent (normal
             return). This is AT-02 — fresh progress is never punished (the
             DESIGN OQ-4 / G-3 guardrail: the watchdog MUST NOT close a
             legitimately-working agent).
    """

    STALE = "older than the threshold"
    FRESH = "recent"


class TerminalPresence(str, Enum):
    """Whether a `completed`/`blocked` terminal record already exists for the key.

    The stale terminal precondition (DESIGN OQ-4): the hook closes a stale agent
    ONLY when NO terminal record exists for `(feature_id, slice_id)`. An agent
    that already reached a terminal state must NOT be re-closed.

    ABSENT — no `completed`/`blocked`/`StaleAgentClosed` terminal record exists
             for the key. Combined with a STALE gap → the stale terminal fires
             (AT-01).

    PRESENT — a `SliceCommitVerified` (completed) / `SliceCommitBlockedTerminal`
              (blocked) terminal already exists for the key. The terminal record
              is seeded with a STALE timestamp (the SAME 25-min age as the progress
              record), so the most-recent ledger record is ALSO past the threshold
              — the gap is stale either way. The ONLY thing withholding the close
              is therefore the no-existing-terminal PRECONDITION, not a fresh gap:
              the hook must NOT emit StaleAgentClosed (don't close an
              already-terminal agent) EVEN THOUGH its progress gap exceeds the
              threshold. This is AT-03 — the no-double-close precondition axis,
              distinct from AT-02's fresh-gap axis (a precondition-blind gap-only
              closer RED-fails AT-03 precisely because the gap here is stale).
    """

    ABSENT = "no terminal yet"
    PRESENT = "already terminal"


class StaleDecision(str, Enum):
    """What the stale check decided — observable on the hook's stdout/exit.

    NOT_CLOSED is the path where the hook leaves the agent alone: either the gap
    is within the threshold (fresh progress) or a terminal already exists. The
    hook returns normally (no StaleAgentClosed record, no terminating
    INDETERMINATE naming staleness). For a working / already-terminal agent this
    is the CORRECT outcome.

    CLOSED is the slice-03 NEW behaviour (DESIGN OQ-4 / OQ-5 / D-3): on a STALE
    gap with NO existing terminal, the hook emits StaleAgentClosed — a
    terminating INDETERMINATE (exit 0, NO `{decision:block}` body) — so the agent
    reaches a terminal Stop instead of hanging forever, AND a loud diagnostic
    names the staleness, AND a durable `StaleAgentClosed` ledger record lands.
    """

    NOT_CLOSED = "is left alone"  # no StaleAgentClosed; normal return
    CLOSED = "is closed loud"  # StaleAgentClosed; INDETERMINATE


@dataclass(frozen=True)
class StaleCheckOutcome:
    """Observable outcome of ONE real SubagentStop stale-check invocation.

    The driving port is the real `handle_subagent_stop` hook subprocess
    (Layer-3/4 wiring). The universe entries `assert_state_delta` tracks are built
    from THIS dataclass's port-exposed fields. Internal plumbing (Popen handle,
    env dict, the transcript JSONL bytes, the raw ledger file path) is NEVER in
    the universe (Mandate 8 — port-exposed observables only).

    - `closed`             — True iff the hook emitted a `StaleAgentClosed`
                             terminal for this agent (the durable ledger record
                             was written AND the loud INDETERMINATE was surfaced).
                             False on a normal return (the agent was left alone).
    - `blocked`            — True iff the hook stdout carried a `{decision:block}`
                             body. The stale terminal is NON-block (DESIGN OQ-5),
                             so a CLOSED outcome is NOT blocked. A normal return
                             on the generic atdd_pure path is also not blocked
                             (the SubagentStop service allows). Tracked so the AT
                             can prove the terminal is the ABSENCE of a block, not
                             a new block flavour.
    - `names_staleness`    — True iff the operator-facing diagnostic NAMES why the
                             agent was closed (a non-empty staleness-naming token),
                             proving the terminal is LOUD about the staleness — not
                             a silent allow. The loud half of "loud → terminating".
    - `terminal_recorded`  — True iff a durable `StaleAgentClosed` record was
                             appended to the AT-completion ledger for this key
                             (the durable half of "loud" — readable post-mortem by
                             a not-watching operator, DEVOPS cross-env invariant 2).
    """

    closed: bool
    blocked: bool
    names_staleness: bool
    terminal_recorded: bool


# --- Phrase -> typed-value lookup tables (Mandate-12 DSL emergence) -------

PROGRESS_AGE_BY_PHRASE: dict[str, ProgressAge] = {a.value: a for a in ProgressAge}
TERMINAL_PRESENCE_BY_PHRASE: dict[str, TerminalPresence] = {
    t.value: t for t in TerminalPresence
}


__all__ = [
    "PROGRESS_AGE_BY_PHRASE",
    "TERMINAL_PRESENCE_BY_PHRASE",
    "FeatureId",
    "ProgressAge",
    "SliceId",
    "StaleCheckOutcome",
    "StaleDecision",
    "TerminalPresence",
]
