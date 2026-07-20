"""Domain types for autonomous-consolidation-and-bugfix-loops slice-01
(a stale-closed agent recovers its own verdict, charter
`a-stale-closed-agent-recovers-its-own-verdict.md`).

Mandate-12 criterion 1 (SSOT via Types + Services + DSL): every domain noun
the slice-01 ``.feature`` scenarios speak lives here as a typed enum or frozen
dataclass. Step methods + composition consume these typed parameters; raw
``str`` parameters are avoided wherever a domain enum exists.

Slice-01 EXTENDS the shipped `oss-spine-watchdog` stale-agent terminal check
(`subagent_stop_handler.py::_maybe_emit_stale_agent_closed`, D-5 reuse — see
that feature's slice-03 for the detection/closure this slice builds on). On
every `StaleAgentClosed` emission the spine must ALSO parse the closed
agent's OWN transcript for its last-stated verdict and write a PAIRED
recovery record to the AT-completion ledger in the SAME tick (D-1, D-8) — so
a `StaleAgentClosed` record is never orphaned.

── DISTILL-interim parsing contract (feature-delta Open Question 1, no DESIGN
wave ran for this feature — the Gotcha "DESIGN optional pushes decisions onto
DISTILL" applies; this is the concrete, testable resolution DELIVER must
implement) ──
A recovered verdict is a line matching ``VERDICT:\\s*(PASS|FAIL|BLOCKED)``
(case-insensitive) inside an ASSISTANT-role transcript message (never a
user-role message — mirrors the existing role-scoping precedent in
``_resolve_wave_only_context``, so a quoted/documented marker in user-injected
content is never mistaken for the agent's own statement). The recovery scans
EVERY assistant message (not only the last one — "buried under noise" must
still resolve) and keeps the LAST (most recent) matching marker — later
noise WITHOUT a marker never hides an earlier stated verdict. Absence of any
matching marker anywhere, an empty transcript, or a transcript whose
assistant-turn lines are unparseable JSON is UNRECOVERABLE — the recovery
record then honestly states "could not recover a verdict", NEVER a
fabricated guess (D-8 negative-oracle mandate).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "autonomous-consolidation-and-bugfix-loops-demo").
FeatureId = NewType("FeatureId", str)

# A carpaccio slice identifier (e.g. "slice-NN").
SliceId = NewType("SliceId", str)


class TranscriptVerdictCase(str, Enum):
    """The shape of the closed agent's OWN transcript the recovery scans.

    Each case selects the transcript-authoring recipe
    (`RecoveryFixture._write_transcript`) and the expected recovery outcome
    the ``Then`` step checks against — the transcript-state-space the charter's
    "What to explore" section names (clear PASS / clear FAIL / buried under
    noise / ambiguous / empty / corrupted).

    CLEAR_PASS / CLEAR_FAIL   — a single assistant message states
                                 ``VERDICT: PASS`` / ``VERDICT: FAIL`` before
                                 the agent goes quiet. The leading recoverable
                                 case (charter Positive-1).
    BURIED_UNDER_NOISE        — a verdict is stated early, then several MORE
                                 assistant turns (tool calls, retries) follow
                                 with NO marker — the real conclusion is
                                 "buried" under later noise (charter "What to
                                 explore"). The recovery must still find it.
    AMBIGUOUS                 — assistant messages exist (real prose) but NONE
                                 contain a recognizable verdict marker.
                                 Recovery must NOT guess.
    EMPTY                     — zero assistant messages at all (the agent went
                                 stale before producing any content).
    CORRUPTED                 — the assistant-turn transcript lines are
                                 unparseable JSON (a truncated/mangled write);
                                 the closing DES-marker line itself stays
                                 valid so the hook still routes into the
                                 stale check (only the CONTENT the recovery
                                 reads is corrupted, not the routing marker).
    """

    CLEAR_PASS = "clearly stated a PASS verdict before going quiet"
    CLEAR_FAIL = "clearly stated a FAIL verdict before going quiet"
    BURIED_UNDER_NOISE = "stated a verdict buried under later noise"
    AMBIGUOUS = "carries no recognizable verdict marker"
    EMPTY = "is empty"
    CORRUPTED = "is corrupted and unreadable"


class RecoveryVerdict(str, Enum):
    """A recovered verdict value the transcript-recovery scan can yield."""

    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class RecoveryOutcome:
    """Observable outcome of ONE real SubagentStop stale-close + recovery pass.

    The driving port is the real `handle_subagent_stop` hook (Layer-3/4
    wiring). Universe entries `assert_state_delta` tracks are built from
    THIS dataclass's port-exposed fields ONLY. Internal plumbing (Popen
    handle, env dict, the raw transcript JSONL bytes, the raw ledger file
    path) is NEVER in the universe (Mandate 8).

    - `closed`               — True iff the hook emitted the (shipped, D-5
                                reused) `StaleAgentClosed` terminal.
    - `paired_recovery`      — True iff EXACTLY one new recovery-attempted
                                record (`StaleAgentVerdictRecovered` XOR
                                `StaleAgentVerdictUnrecoverable`) was appended
                                in the SAME hook invocation the close happened
                                in — the D-8 no-orphan guarantee.
    - `recovered`            — True iff the paired record is the SUCCESS kind
                                (a verdict was actually recovered); False for
                                the honest-failure kind.
    - `recovered_verdict`    — the recovered verdict string when `recovered`
                                is True, else None. Never a guess.
    - `unrecoverable_reason` — the honest non-empty reason string when
                                `recovered` is False, else None.
    - `distinguishable`      — True iff the recovery record is marked
                                distinctly from an agent-reported `completed`
                                terminal (`source == "transcript-recovered"`,
                                never `SliceCommitVerified` /
                                `WorkflowPhaseCompletedGCommit`).
    - `durable_on_reread`    — True iff a FRESH ledger read (a new reader
                                instance, not the one that observed the
                                write) still sees the recovery record.
    - `new_record_count`     — the TOTAL number of ledger records newly
                                appended by this one hook invocation (any
                                event kind). Used by the re-arm scenario to
                                assert the ledger is byte-for-byte unchanged
                                on a second fire against an already-closed,
                                already-recovered agent — a precise
                                double-write guard the pairing fields alone
                                cannot express (a buggy double-write of BOTH
                                a StaleAgentClosed AND a recovery record
                                would still read `paired_recovery=True`).
    """

    closed: bool
    paired_recovery: bool
    recovered: bool
    recovered_verdict: str | None
    unrecoverable_reason: str | None
    distinguishable: bool
    durable_on_reread: bool
    new_record_count: int


# --- Phrase -> typed-value lookup table (Mandate-12 DSL emergence) --------

TRANSCRIPT_CASE_BY_PHRASE: dict[str, TranscriptVerdictCase] = {
    c.value: c for c in TranscriptVerdictCase
}


__all__ = [
    "TRANSCRIPT_CASE_BY_PHRASE",
    "FeatureId",
    "RecoveryOutcome",
    "RecoveryVerdict",
    "SliceId",
    "TranscriptVerdictCase",
]
