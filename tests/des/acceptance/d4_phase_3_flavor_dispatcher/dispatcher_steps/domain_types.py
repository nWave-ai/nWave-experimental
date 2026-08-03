"""Domain types for D4 Phase 3 slice-01 flavor-dispatcher acceptance tests.

Mandate-12 criterion 1 (SSOT + Zero Duplication via Types + Services + DSL).
Every domain noun used in the Gherkin is expressed once here as a typed enum
or NewType. Step bodies and the FlavorDispatcherComposition service consume
these typed parameters — no raw `str` where a domain enum exists.

The slice ships the workflow flavor dispatcher pure function:

  dispatch_lifecycle_event(event_id, flavor_id, context, *,
                            flavors_dir, gate_invoker) -> CompositionResult

The dispatcher reads a flavor YAML file, looks up the lifecycle event's
gate composition, invokes each gate via the injected Port, and aggregates
results per the per-gate `on_failure` policy.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A flavor identifier as it appears in the `flavor_id` YAML field
# (e.g. "atdd_pure", "classic", "demo_single").
FlavorId = NewType("FlavorId", str)


# A gate identifier as it appears in the catalog `gate_id` field
# (e.g. "health-check", "carpaccio-slice-gate").
GateId = NewType("GateId", str)


# An abstract lifecycle event name from `nWave/data/host-bridge-events.yaml`
# closed vocabulary (e.g. "dispatch.pre", "session.init", "subagent.stop").
LifecycleEventName = NewType("LifecycleEventName", str)


class OnFailurePolicy(str, Enum):
    """The per-gate failure-handling policy declared in a flavor composition.

    BLOCK -- halt composition on first failure, propagate block decision to host.
    WARN  -- continue composition, annotate the failing gate's result with a
             warning, complete every remaining gate.
    LOG   -- continue silently, record event for audit, no annotation.
    """

    BLOCK = "block"
    WARN = "warn"
    LOG = "log"


class GateOutcome(str, Enum):
    """The success-or-failure outcome of a single gate invocation.

    SUCCESS -- gate cleared (exit_code == 0).
    FAILURE -- gate rejected (exit_code != 0).
    """

    SUCCESS = "success"
    FAILURE = "failure"


# --- slice-02 (carpaccio_intercept refactor) ------------------------------
#
# The slice-02 ATs pin the public `InterceptDecision` contract returned by
# `evaluate_atdd_pure_dispatch()` — the same function pre- and post-refactor.
# Three observable verdict shapes correspond to the three M3 classification
# outcomes (`absent` -> passthrough, `defective` -> block, `valid` -> allow
# subject to M8 + carpaccio gate).


class InterceptVerdict(str, Enum):
    """The public InterceptDecision shape — one of three terminal verdicts.

    PASSTHROUGH -- not an atdd_pure dispatch; the classic path is unchanged.
    ALLOW       -- a recognised atdd_pure dispatch the U1 gate cleared.
    BLOCK       -- a recognised atdd_pure dispatch the U1 gate rejected.
    """

    PASSTHROUGH = "passthrough"
    ALLOW = "allow"
    BLOCK = "block"


VERDICT_BY_PHRASE: dict[str, InterceptVerdict] = {
    "allow": InterceptVerdict.ALLOW,
    "block": InterceptVerdict.BLOCK,
    "passthrough": InterceptVerdict.PASSTHROUGH,
}


# --- slice-03 (D1 readiness pre-dispatch gate) ----------------------------
#
# The slice-03 ATs pin the public ReadinessReport contract returned by
# `des verify-readiness-pre-dispatch`. The gate verifies the five
# cascading first-dispatch invariants catalogued in friction #57 and
# emits one combined diagnostic naming every failed invariant.


class ReadinessVerdict(str, Enum):
    """The public readiness gate verdict -- one of two terminal shapes.

    CLEARED -- every first-dispatch invariant satisfied; dispatch proceeds.
    REFUSED -- at least one first-dispatch invariant failed; diagnostic lists every failure.
    """

    CLEARED = "cleared"
    REFUSED = "refused"


class InvariantStatus(str, Enum):
    """The status of a single first-dispatch invariant within the readiness diagnostic.

    SATISFIED -- the invariant holds for this workspace.
    FAILED    -- the invariant does not hold; remediation accompanies the entry.
    """

    SATISFIED = "satisfied"
    FAILED = "failed"


class FirstDispatchInvariantId(str, Enum):
    """The four first-dispatch invariants the readiness gate verifies (this
    AT scope's slice; the live gate carries more -- see
    `verify_readiness_pre_dispatch._ALL_INVARIANTS`).

    Each invariant corresponds to one cascading friction empirically observed
    during first-dispatch of a NEW feature (friction #57 enumeration).

    NOTE (fix-readiness-carpaccio-disagree): this enum used to also carry an
    `AT_REVIEW_VERDICT = "at_review_verdict"` member -- unused by any step in
    this AT scope (grep-confirmed), removed alongside the gate's own deletion
    of that invariant.
    """

    SLICE_PLAN_SECTION = "slice_plan_section"
    SCENARIO_SLICE_TAGS = "scenario_slice_tags"
    GATE_OUTPUT_PRODUCEABLE = "gate_output_produceable"
    PRE_COMMIT_SCOPE = "pre_commit_scope"


# Maps the operator-facing Gherkin invariant name to its typed identifier.
# Keeping it module-scoped lets step bodies stay one typed lookup + one
# composition call (Mandate-12 criterion 3).
INVARIANT_BY_PHRASE: dict[str, FirstDispatchInvariantId] = {
    "slice plan": FirstDispatchInvariantId.SLICE_PLAN_SECTION,
}


READINESS_VERDICT_BY_PHRASE: dict[str, ReadinessVerdict] = {
    "clears": ReadinessVerdict.CLEARED,
    "refuses": ReadinessVerdict.REFUSED,
}


# --- slice-04 (LogPersistencePort + adapters) -----------------------------
#
# The slice-04 ATs pin the public LogPersistencePort contract — every gate
# emits a typed `GateLogEvent` envelope through `port.emit(event)`; the
# adapter resolves the destination from config per INV-3 (gate is
# path-blind) + INV-9 (config-as-driver). Three observable adapter shapes
# correspond to the three shipped adapter classes:
#   * JsonlLogAdapter   -- two-tier filesystem persistence (per-feature +
#                          common-log fanout); fail-OPEN on OSError.
#   * StdoutLogAdapter  -- JSON-line emit on a writable text stream.
#   * SilentLogAdapter  -- no-op + optional in-memory capture for tests.


class LogAdapterKind(str, Enum):
    """The shipped LogPersistencePort adapter classes for slice-04 ATs.

    JSONL   -- two-tier filesystem JSONL with optional fanout to common log.
    STDOUT  -- single text-stream JSON-line emit (operator debug + CI sinks).
    SILENT  -- no-op + optional in-memory capture for test fixtures.
    """

    JSONL = "jsonl"
    STDOUT = "stdout"
    SILENT = "silent"


# A GateLogEvent's `event_id` field — a closed namespace string per
# `nWave/data/log-persistence-defaults.yaml` `event_namespaces` list, e.g.
# "gate.carpaccio.slice-cleared", "gate.contract.tree-cleared".
GateEventId = NewType("GateEventId", str)


# Gherkin-phrase -> typed-value lookups. Keeping these as module-level dicts
# lets each step body stay a single typed lookup + a single composition call
# (Mandate-12 criterion 3: no control flow in step bodies).

ON_FAILURE_BY_PHRASE: dict[str, OnFailurePolicy] = {
    "block": OnFailurePolicy.BLOCK,
    "warn": OnFailurePolicy.WARN,
    "log": OnFailurePolicy.LOG,
}

OUTCOME_BY_PHRASE: dict[str, GateOutcome] = {
    "successful": GateOutcome.SUCCESS,
    "failing": GateOutcome.FAILURE,
}

COUNT_BY_PHRASE: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
}


# --- slice-05 (multi-gate dispatch.pre wire) ------------------------------
#
# Mandate-12 criterion 1 (SSOT + Zero Duplication via Types + Services + DSL,
# refined 2026-05-18): gate-id and event-name literals used by the slice-05
# multi-gate composition are promoted from raw `str` to closed enums. The
# enums:
#   * Pin the closed vocabulary of dispatch.pre gate identifiers + block
#     event names at one source.
#   * Let composition methods consume typed parameters
#     (Mandate-12 criterion 2 -- the per-gate runner registry stores
#     `GateIdOnDispatchPre` keys, not raw `str`; the invocation-log
#     observable returns `list[GateIdOnDispatchPre]`, not `list[str]`).
#   * Keep step-body Gherkin literals readable (Pillar 1 -- the operator
#     reads "verify-readiness-pre-dispatch then carpaccio-slice-gate", not
#     "GateIdOnDispatchPre.VERIFY_READINESS_PRE_DISPATCH then ...") while
#     resolving the literal through the enum at the composition boundary.


class GateIdOnDispatchPre(str, Enum):
    """The closed vocabulary of gate ids the atdd_pure dispatch.pre wires.

    VERIFY_READINESS_PRE_DISPATCH -- slice-03 first-dispatch invariants gate.
    CARPACCIO_SLICE_GATE          -- slice-02 carpaccio order/scope gate.
    """

    VERIFY_READINESS_PRE_DISPATCH = "verify-readiness-pre-dispatch"
    CARPACCIO_SLICE_GATE = "carpaccio-slice-gate"


class BlockEventName(str, Enum):
    """The closed vocabulary of block-event names a multi-gate dispatch emits.

    READINESS_GATE_REJECTED -- verify-readiness-pre-dispatch on_failure=block.
    CARPACCIO_GATE_REJECTED -- carpaccio-slice-gate on_failure=block.
    """

    READINESS_GATE_REJECTED = "ReadinessGateRejected"
    CARPACCIO_GATE_REJECTED = "CarpaccioGateRejected"
