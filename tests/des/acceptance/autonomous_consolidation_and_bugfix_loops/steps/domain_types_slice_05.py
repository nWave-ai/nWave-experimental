"""Domain types for autonomous-consolidation-and-bugfix-loops slice-05
(a session starting fires every pending autonomous-loop tick, fail-open --
resolves feature-delta Open Question OQ-3 / DA-13).

Mandate-12 criterion 1 (SSOT via Types + Services + DSL): every domain noun
the slice-05 ``.feature`` scenarios speak lives here as a typed enum or
frozen dataclass.

── THE GAP THIS SLICE CLOSES (OQ-3 / DA-13) ──
Slices 02-04 shipped three correct, ledger-safe driving ports
(``des work-exhausted-tick`` / ``des bugfix-pipeline-tick`` /
``des consolidation-signal-tick``) with ZERO production callers -- nothing in
the codebase autonomously ticks them. Ale ratified closing this gap by wiring
them into the SessionStart hook's ``handle_session_start()`` (mirrors slice-01's
already-shipped SubagentStop pattern, ``_maybe_emit_stale_agent_closed`` --
extend an EXISTING lifecycle-hook trigger, never a new in-process daemon --
the ``background-loops-hybrid-c`` ``iv-3`` no-daemon invariant this feature
sits on the same lifecycle surface as).

── DISTILL-INTERIM WIRING CONTRACT (no DESIGN wave resolved the per-tick
parameter-sourcing question -- the row 7b Gotcha applies again) ──
Real state-detection (which queue-state, which defect transition, which
trunk-health signal) is OUT OF SCOPE for this driving port -- the SAME
carve-out slice-04 already established for signal detection ("scanning the
real git/CI state ... is Vera's EXAMINE job, not this AT's job"). Instead,
SessionStart reads an EXPLICIT, ALREADY-DETECTED tick REQUEST per domain from
an optional, minimal per-project JSON file directly under ``{cwd}/.nwave/``:

  * ``loop-tick-work-exhausted.json``    -> ``des.domain.work_exhausted_ladder``
  * ``loop-tick-bugfix-pipeline.json``   -> ``des.domain.bugfix_pipeline``
  * ``loop-tick-consolidation-signal.json`` -> ``des.domain.consolidation_queue_intake``

A file's ABSENCE means "nothing pending for this domain this session" -- a
safe no-op, never an error (mirrors the queue model's own ``malformed ==
exhausted-safe`` discipline: an unknown/no-signal state degrades to inaction,
never a hang). A file's PRESENCE names a request DELIVER dispatches DIRECTLY
into the domain seam (never the CLI's argv layer -- SessionStart already has
the parsed values, so the domain function is called in-process with ``now``
supplied by SessionStart itself). Each of the three ticks is wrapped in its
OWN top-level ``try/except Exception: pass`` (the EXACT fail-open contract
every existing SessionStart trigger already follows) -- an exception in ONE
tick never propagates and never blocks the OTHER two ticks or any
pre-existing SessionStart trigger; ``handle_session_start()`` always returns
0.

── D-8 EXTENDED: A FAILED TICK ATTEMPT IS STILL OBSERVABLE (never swallowed) ──
Two distinct degrade classes, DELIVER-pinned:

  1. **Known feature, bad request** (the request JSON parses and names a
     non-empty ``feature_id``, but a domain-required field is missing) -- the
     tick CAN target a ledger, so the failed attempt is LEDGER-ATTESTED: a
     new ``WorkExhaustedTickAttemptFailed`` / ``BugfixPipelineTickAttemptFailed``
     / ``ConsolidationSignalTickAttemptFailed`` record is appended (reusing
     the ALREADY-GENERIC ``append_work_exhausted_event`` /
     ``append_bugfix_pipeline_event`` write surfaces -- D-8/DA-6 reuse, no new
     port method), carrying a non-empty ``reason`` naming the missing field.
  2. **No derivable feature_id** (unparseable JSON, or the request is missing
     ``feature_id`` itself) -- there is no feature ledger to target, so the
     tick fails open via a labeled ``[nwave] ... error (fail-open): ...``
     stderr diagnostic ONLY (the SAME idiom ``_adopt_prior_use_if_warranted``
     / ``_apply_pending_update_if_any`` already use) -- no ledger write is
     attempted. Both an unparseable-JSON request and a request missing
     ``feature_id`` route through this SAME code path to the SAME outcome;
     this slice's AT exercises the missing-``feature_id`` case as the
     representative example (not enumerated twice -- same law, same code
     path).

── HOOK-POINT COEXISTENCE (OQ-4, cross-feature collision guard) ──
`background-loops-hybrid-c` (DESIGN ratified, commit 390a08e07, NOT yet
DELIVERed) has reserved a DIFFERENT extension point in the SAME
`session_start_handler.py::handle_session_start()` -- a function named
`_stabilize_tick`, intended to run FIRST, before the background tick,
tree-clean-gated, serialized under its own land-flock. `_stabilize_tick`
does NOT exist on trunk as of this slice's authoring (confirmed by repo-wide
search). This slice's DELIVER-pinned wrapper functions are DELIBERATELY
named and shaped to never collide with it:

  * ``_maybe_tick_work_exhausted`` / ``_maybe_tick_bugfix_pipeline`` /
    ``_maybe_tick_consolidation_intake`` -- three DISTINCT names, none of
    them ``_stabilize_tick``, none of them claiming to be "first" or
    otherwise structurally ordered relative to it.
  * Each is its OWN independent ``try/except`` block appended to
    `handle_session_start()`, the SAME additive pattern the EXISTING
    triggers already use (`_adopt_prior_use_if_warranted`,
    `_apply_pending_update_if_any`, the housekeeping/update-check blocks) --
    no shared state with, no read of, no write to anything
    `_stabilize_tick` (present or future) touches.
  * Ordering relative to a not-yet-built `_stabilize_tick` is UNDEFINED and
    UNIMPORTANT by design -- both are independent, side-effect-isolated
    fail-open blocks in the same function body; landing either one before
    or after the other changes nothing observable for the OTHER feature's
    behavior.

Both can co-exist on the SessionStart hook; slice-05 names its trigger
functions distinctly precisely so `background-loops-hybrid-c`'s eventual
DELIVER (whichever feature lands second) reads this choice instead of
colliding blind -- the SAME coexistence discipline that feature's own DESIGN
already applies to a different probe-name collision. See feature-delta.md
OQ-4 disposition for the cross-feature record.

Reference: docs/feature/autonomous-consolidation-and-bugfix-loops/
           feature-delta.md, ``## Wave: DESIGN / [REF] Open Questions`` OQ-3
           and OQ-4, and slice-05 (``## Wave: DISTILL / [REF] Wave-Decision
           Reconciliation``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, NewType


# A kebab-case feature identifier (e.g. "loops-slice05-demo-work-exhausted").
FeatureId = NewType("FeatureId", str)


class LoopTickDomain(str, Enum):
    """The three domains slice-05 wires into `handle_session_start()`.

    Each carries its own request filename (DELIVER-pinned, `.nwave/`-rooted)
    and its own ledger event-name pair (ticked-successfully is proven by
    slices 02-04's own event vocabulary; the tick-ATTEMPT-failed name is the
    ONE net-new event kind per domain this slice introduces, D-8).
    """

    WORK_EXHAUSTED = "work-exhausted"
    BUGFIX_PIPELINE = "bugfix-pipeline"
    CONSOLIDATION_SIGNAL = "consolidation-signal"


# The DELIVER-pinned request filename per domain -- update here (and in the
# scaffold's own docstring, mirroring slices 02-04's convention) if DELIVER
# picks a different name.
LOOP_TICK_REQUEST_FILENAME: dict[LoopTickDomain, str] = {
    LoopTickDomain.WORK_EXHAUSTED: "loop-tick-work-exhausted.json",
    LoopTickDomain.BUGFIX_PIPELINE: "loop-tick-bugfix-pipeline.json",
    LoopTickDomain.CONSOLIDATION_SIGNAL: "loop-tick-consolidation-signal.json",
}

# The DELIVER-pinned tick-attempt-failed event name per domain (D-8, the one
# net-new event kind per domain -- reuses the already-generic
# append_work_exhausted_event / append_bugfix_pipeline_event write surfaces).
TICK_ATTEMPT_FAILED_EVENT: dict[LoopTickDomain, str] = {
    LoopTickDomain.WORK_EXHAUSTED: "WorkExhaustedTickAttemptFailed",
    LoopTickDomain.BUGFIX_PIPELINE: "BugfixPipelineTickAttemptFailed",
    LoopTickDomain.CONSOLIDATION_SIGNAL: "ConsolidationSignalTickAttemptFailed",
}

# The domain-ticked-successfully sentinel event name per domain -- the
# SINGLE new record a fresh, valid request produces (asserted for "ticked
# exactly once"). Reuses slices 02-04's own shipped event vocabulary --
# nothing new is minted for the success path.
TICK_SUCCESS_EVENT: dict[LoopTickDomain, str] = {
    LoopTickDomain.WORK_EXHAUSTED: "WorkExhaustedWindowOpened",
    LoopTickDomain.BUGFIX_PIPELINE: "PipelineStageStarted",
    LoopTickDomain.CONSOLIDATION_SIGNAL: "PipelineStageStarted",
}


@dataclass(frozen=True)
class PendingLoopTick:
    """A single pending, ALREADY-DETECTED loop-tick request this AT seeds.

    ``payload`` carries exactly the fields the domain's request file would
    hold; ``drop_field`` names a required field to OMIT (the malformed-
    known-feature case, D-8 class 1) -- ``None`` means "write the payload as
    given" (the well-formed case). ``feature_id`` is threaded separately so
    the fixture can seed/read a per-domain ledger namespace even when the
    payload itself is deliberately missing it (D-8 class 2, no derivable
    feature_id).
    """

    domain: LoopTickDomain
    feature_id: FeatureId | None
    payload: dict[str, Any] = field(default_factory=dict)
    drop_field: str | None = None

    def request_json(self) -> dict[str, Any]:
        """The JSON object this fixture writes to the request file.

        ``feature_id`` is folded in (unless deliberately omitted -- the
        no-derivable-feature_id case, D-8 class 2) and ``drop_field``, when
        set, removes that key from the final payload (D-8 class 1).
        """
        body = dict(self.payload)
        if self.feature_id is not None:
            body["feature_id"] = str(self.feature_id)
        if self.drop_field is not None:
            body.pop(self.drop_field, None)
        return body


FEATURE_ID_BY_DOMAIN: dict[LoopTickDomain, FeatureId] = {
    LoopTickDomain.WORK_EXHAUSTED: FeatureId("loops-slice05-demo-work-exhausted"),
    LoopTickDomain.BUGFIX_PIPELINE: FeatureId("loops-slice05-demo-bugfix-pipeline"),
    LoopTickDomain.CONSOLIDATION_SIGNAL: FeatureId(
        "loops-slice05-demo-consolidation-signal"
    ),
}

# The default WELL-FORMED payload per domain -- each shaped to produce
# EXACTLY ONE new success record when ticked against a fresh ledger.
_DEFAULT_PAYLOAD: dict[LoopTickDomain, dict[str, Any]] = {
    LoopTickDomain.WORK_EXHAUSTED: {"queue_state": "empty"},
    LoopTickDomain.BUGFIX_PIPELINE: {
        "defect_id": "slice05-demo-defect",
        "action": "stage-started",
        "stage": "rca",
    },
    LoopTickDomain.CONSOLIDATION_SIGNAL: {
        "signal_type": "drift",
        "signal_key": "slice05-demo-branch",
    },
}

# The field to drop for the "malformed known-feature request" class (D-8
# class 1) -- bugfix-pipeline's `action` is required with no default in
# `des.domain.bugfix_pipeline.evaluate_and_record`.
_MALFORMED_DROP_FIELD: dict[LoopTickDomain, str] = {
    LoopTickDomain.BUGFIX_PIPELINE: "action",
}


def well_formed_tick(domain: LoopTickDomain) -> PendingLoopTick:
    """A default, well-formed pending tick for `domain`."""
    return PendingLoopTick(
        domain=domain,
        feature_id=FEATURE_ID_BY_DOMAIN[domain],
        payload=dict(_DEFAULT_PAYLOAD[domain]),
    )


def malformed_known_feature_tick(domain: LoopTickDomain) -> PendingLoopTick:
    """A pending tick naming a KNOWN feature_id but missing a required field."""
    return PendingLoopTick(
        domain=domain,
        feature_id=FEATURE_ID_BY_DOMAIN[domain],
        payload=dict(_DEFAULT_PAYLOAD[domain]),
        drop_field=_MALFORMED_DROP_FIELD[domain],
    )


def nameless_tick(domain: LoopTickDomain) -> PendingLoopTick:
    """A pending tick with NO derivable feature_id (D-8 class 2)."""
    return PendingLoopTick(
        domain=domain,
        feature_id=None,
        payload=dict(_DEFAULT_PAYLOAD[domain]),
    )


@dataclass(frozen=True)
class LoopTickWiringOutcome:
    """Observable outcome of ONE real `handle_session_start()` invocation.

    The driving port is the real SessionStart hook (Layer-3/4 wiring, mirrors
    slice-01's `RecoveryOutcome`). Universe entries `assert_state_delta`
    tracks are built from THIS dataclass's port-exposed fields ONLY --
    internal plumbing (the raw JSON request bytes, the raw ledger file path,
    stdout/stderr capture buffers) is NEVER in the universe (Mandate 8).

    - `exit_code`              -- the hook's own return value; 0 always
                                   (fail-open, unconditional per every
                                   existing SessionStart trigger).
    - `ticked`                 -- per-domain: True iff that domain's SINGLE
                                   expected success record newly appeared.
    - `attempt_failed`         -- per-domain: True iff that domain's
                                   tick-ATTEMPT-failed record newly appeared
                                   (D-8 class 1 -- known feature, bad field).
    - `stderr_mentions_domain` -- per-domain: True iff a labeled
                                   `[nwave] ... error (fail-open)` diagnostic
                                   naming that domain's request appears on
                                   stderr (D-8 class 2 -- no derivable
                                   feature_id, no ledger to target).
    """

    exit_code: int
    ticked: dict[LoopTickDomain, bool]
    attempt_failed: dict[LoopTickDomain, bool]
    stderr_mentions_domain: dict[LoopTickDomain, bool]

    def ticked_exactly(self, *domains: LoopTickDomain) -> bool:
        """True iff EXACTLY `domains` ticked and no OTHER domain ticked."""
        wanted = frozenset(domains)
        return all(self.ticked[d] == (d in wanted) for d in LoopTickDomain)


__all__ = [
    "FEATURE_ID_BY_DOMAIN",
    "LOOP_TICK_REQUEST_FILENAME",
    "TICK_ATTEMPT_FAILED_EVENT",
    "TICK_SUCCESS_EVENT",
    "FeatureId",
    "LoopTickDomain",
    "LoopTickWiringOutcome",
    "PendingLoopTick",
    "malformed_known_feature_tick",
    "nameless_tick",
    "well_formed_tick",
]
