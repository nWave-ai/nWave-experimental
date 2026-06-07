"""Domain types for des-spine-control-plane-ssot slice-04 (gate-composition SSOT).

Mandate-12 criterion 1 (SSOT via Types + Services + DSL): every domain noun the
slice-04 .feature scenarios speak lives here as a typed enum or frozen dataclass.
Step methods + composition consume these typed parameters; raw `str` parameters
are avoided wherever a domain enum exists.

Slice-04 SUT = the spine's `subagent.stop` lifecycle-event driving port — the
REAL `des ... subagent-stop` hook entry (`claude_code_hook_adapter subagent-stop`)
invoked exactly as Claude Code invokes it when a dispatched atdd_pure crafter
returns. The slice-04 BEHAVIOR is the gate-composition SSOT consolidation
(DESIGN facet-1, DDD-1): today the gate that fires at `subagent.stop` is hand-
wired (the if-ladder in `subagent_stop_handler.py:1356` + the hardcoded
`_REQUIRED_FEATURE_END_RECORDS` frozenset at `:820`); after slice-04 it is the
gate the flavor YAML declares for that boundary — `gates_fired_at(E) ==
yaml_composition(flavor, E)` (DESIGN Aggregate `LifecycleComposition` invariant).

The disease (grep-evidenced, witnessed at DISTILL HEAD):

  * `nWave/flavors/atdd_pure.yaml:36-87` declares ALL FOUR lifecycle events —
    `dispatch.pre`, `subagent.stop`, `commit.pre`, `session.init`.
  * Only `dispatch.pre` is routed through the YAML-driven `flavor_dispatcher`
    (`carpaccio_intercept.py:522`, `_DISPATCH_PRE_EVENT_ID`).
  * `subagent.stop` is DEAD YAML: its behavior is a hand-wired if-ladder
    (`subagent_stop_handler.py:1356-1370`) + a hardcoded feature-end
    required-records frozenset (`_REQUIRED_FEATURE_END_RECORDS`, `:820-829`,
    six literal record names hand-edited across five prior features — the exact
    "edit-in-N-places" fixture-fanout the SSOT mandate bans).

The OBSERVABLE contract the ATs drive at the `subagent.stop` boundary (witnessed
RED today via the real hook subprocess): on a feature-end return (F_FINAL_REVIEW,
all planned slices shipped, feature-end cycle records absent) the hook emits a
`{"decision": "block", "event": "FeatureEndCycleIncomplete", "missing": [...]}`
JSON decision whose `missing` list is the required-records profile NOT YET in
the ledger. Today that profile is the hardcoded frozenset; after slice-04 it is
the flavor YAML's `subagent.stop` required-records profile.

The discriminator seam (slice-04 wires it; RED today because it does not exist):
`NWAVE_FLAVORS_DIR` — an env override pointing the gate-composition dispatcher at
a flavor directory. It is the seam that makes the flavor YAML the overridable
SSOT for the `subagent.stop` composition. Today the hook reads NO flavor dir for
`subagent.stop` (the if-ladder ignores it), so setting `NWAVE_FLAVORS_DIR` has
zero effect → the discriminator ATs (AT-01/AT-02) RED-fail.

DESIGN Aggregate `LifecycleComposition` (DDD-1) decides the invariant ONCE
upstream — `gates_fired_at(E) == yaml_composition(flavor, E)` for all four E. The
AT does not re-litigate it; it pins it as the observable contract at the
`subagent.stop` boundary, where the required-records profile is the YAML-sourced
composition field that the frozenset hardcodes today.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# The structured `event` value the feature-end gate emits in its `block`
# decision when the required-records profile is not yet satisfied by the ledger
# (`subagent_stop_handler._handle_feature_end_gate` -> `_emit_atdd_pure_block`,
# event `FeatureEndCycleIncomplete`). The AT recognises the feature-end boundary
# verdict by this event + its `missing` list, never by an internal call.
FEATURE_END_BLOCK_EVENT = "FeatureEndCycleIncomplete"

# The `decision` key value for a block (the atdd_pure block contract surfaced on
# stdout as one JSON line). A non-block feature-end return carries no block JSON.
BLOCK_DECISION = "block"

# The six required-records names the HARDCODED frozenset demands today
# (`_REQUIRED_FEATURE_END_RECORDS`, `subagent_stop_handler.py:820-829`). This is
# the behavior-preservation baseline AT-03 pins: with the PRODUCTION flavor (no
# override) the boundary must keep naming exactly these six in `missing`. After
# slice-04 these become the flavor YAML's `subagent.stop` required-records
# profile — same six, now YAML-sourced (representation 3 → 1).
PRODUCTION_REQUIRED_RECORDS = frozenset(
    {
        "CoverageMapVerifiedAtDeliverExit",
        "CoverageMapVerifiedAtDistillExit",
        "EBatchRefactorCompleted",
        "EnvironmentalE2eGateRan",
        "FeatureEndReviewVerdict",
        "WalkingSkeletonGateRan",
    }
)

# A sentinel required-record name that is NOT in the production frozenset. A
# test flavor declaring it in its `subagent.stop` required-records profile must
# (post-slice-04) make the boundary block naming THIS record in `missing` —
# proving the profile is read from the YAML composition, not the frozenset.
# Today the frozenset is the SSOT and never names a sentinel → AT-02 RED.
SENTINEL_REQUIRED_RECORD = "SliceFourYamlSourcedSentinelRecord"


class FlavorComposition(str, Enum):
    """How the `subagent.stop` feature-end required-records profile is declared.

    The seam the gate-composition SSOT cure reads. Each member maps (in the
    composition fixture) to a flavor directory the `NWAVE_FLAVORS_DIR` override
    points at — or, for PRODUCTION, to NO override (the shipped
    `nWave/flavors/atdd_pure.yaml`).

    * PRODUCTION — no `NWAVE_FLAVORS_DIR` override; the real shipped flavor YAML
      governs. The required-records profile equals the production six. This is
      the behavior-preservation case (AT-03): identical observable verdict
      before and after the routing, proving the consolidation is invariant-
      preserving (DEVOPS slice-04 deploy gate / regression pin).
    * EMPTY_REQUIRED_RECORDS — a test flavor whose `subagent.stop` feature-end
      composition demands NO required records. Post-slice-04 the boundary must
      NOT block on missing-records (the hardcoded frozenset no longer governs);
      it proceeds past the required-records check. The load-bearing
      YAML-driven-ness discriminator (AT-01) — today the frozenset blocks
      regardless of the flavor → RED.
    * SENTINEL_REQUIRED_RECORD — a test flavor adding ONE sentinel required
      record absent from the production frozenset. Post-slice-04 the boundary
      must block naming the sentinel in `missing` — proving the profile is read
      from the YAML, not the frozenset (AT-02). Today the sentinel never appears
      → RED.

    The `.value` strings are the human-readable Gherkin phrases the step
    decorators parse (DSL emergence over a typed enum — Mandate-12).
    """

    PRODUCTION = "the shipped gate composition"
    EMPTY_REQUIRED_RECORDS = (
        "a gate composition that demands no feature-end records at the "
        "subagent-stop boundary"
    )
    SENTINEL_REQUIRED_RECORD = (
        "a gate composition that adds one extra feature-end record at the "
        "subagent-stop boundary"
    )


class BoundaryOutcome(str, Enum):
    """How the `subagent.stop` boundary resolves the feature-end return — observable.

    Derived from the real hook subprocess's stdout block JSON (+ exit code). The
    slice-04 invariant is that this outcome reflects the FLAVOR YAML composition
    for the `subagent.stop` boundary, not the hand-wired frozenset.

    * BLOCKED_MISSING_RECORDS — the boundary emitted a `block` decision with
      event `FeatureEndCycleIncomplete` + a `missing` records list. The
      required-records profile is the discriminator: which records appear in
      `missing` tells whether the profile is YAML-sourced (the sentinel appears
      / the empty profile yields no records) or frozenset-sourced (always the
      six).
    * PROCEEDED_PAST_RECORDS — the boundary did NOT block on missing records:
      either no block JSON at all, or a block from a LATER gate (the integrity
      gate) that is NOT the missing-records block. Observable as the ABSENCE of
      a `FeatureEndCycleIncomplete` event. This is the EMPTY_REQUIRED_RECORDS
      post-slice-04 state (AT-01).
    * UNEXPECTED — any other shape, so a verdict never passes for the wrong reason.
    """

    BLOCKED_MISSING_RECORDS = "blocked: feature-end records missing"
    PROCEEDED_PAST_RECORDS = "proceeded past the required-records check"
    UNEXPECTED = "unexpected"


@dataclass(frozen=True)
class FeatureEndProject:
    """A handle on a synthetic atdd_pure project a feature-end return runs against.

    Wraps a tmp_path-scoped project: a `.nwave/config.yaml` declaring atdd_pure,
    a feature-delta carrying a one-row `[REF] Slice Plan` whose only slice is
    `shipped` (so the feature-end gate sees "all planned slices shipped" via the
    markdown fallback), and NO AT-completion ledger (so the feature-end cycle
    records are ABSENT — the missing-records branch is reachable). The
    `flavor_composition` records which `subagent.stop` required-records profile
    governs (production frozenset today; YAML-sourced after slice-04).
    """

    project_dir: str  # the repo root the hook resolves context + artifacts from
    feature_id: str
    transcript_path: str  # the synthetic F_FINAL_REVIEW feature-end transcript
    flavor_composition: FlavorComposition
    flavors_dir: str | None  # the NWAVE_FLAVORS_DIR override path, or None (production)


@dataclass(frozen=True)
class BoundaryRun:
    """Observable outcome of one real `subagent.stop` hook fire (feature-end return).

    Universe entries `assert_state_delta` tracks are built from THIS dataclass's
    port-exposed fields: `outcome`, `missing_records`, `block_event`. Internal
    plumbing (Popen handle, env dict, raw stream bytes, the parsed JSON object)
    is NEVER in the universe (Mandate 8 — port-exposed observables only). The
    `missing_records` frozenset is the boundary's emitted `missing` list (the
    required-records-profile observable that discriminates YAML-sourced from
    frozenset-sourced).
    """

    exit_code: int
    stdout: str
    stderr: str
    outcome: BoundaryOutcome
    block_event: str | None  # the structured `event` of the block, or None
    missing_records: frozenset[str]  # the emitted `missing` set (empty when none)


# --- Phrase -> typed-value lookup tables (Mandate-12 DSL emergence) -------

FLAVOR_COMPOSITION_BY_PHRASE: dict[str, FlavorComposition] = {
    c.value: c for c in FlavorComposition
}


__all__ = [
    "BLOCK_DECISION",
    "FEATURE_END_BLOCK_EVENT",
    "FLAVOR_COMPOSITION_BY_PHRASE",
    "PRODUCTION_REQUIRED_RECORDS",
    "SENTINEL_REQUIRED_RECORD",
    "BoundaryOutcome",
    "BoundaryRun",
    "FeatureEndProject",
    "FlavorComposition",
]
