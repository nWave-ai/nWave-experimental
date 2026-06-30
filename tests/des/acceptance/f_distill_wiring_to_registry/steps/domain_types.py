"""Typed domain vocabulary for the f-distill-wiring-to-registry slice-01 ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the slice-01
Gherkin names is expressed once here as a typed enum / frozen dataclass, so the
composition methods consume typed parameters (no raw ``str`` where an enum
exists). The DSL emerges from these typed concepts -- the scenarios range over
the four DISTILL-OUT gate ids + the wired-module set + the false-credit case,
not over decorator proliferation.

These types are TEST-LOCAL (they never import production code) -- the ATs drive
the SUT only through composition-root driving ports (Mandate-13): the REAL spine
``wave_gate_stack_dispatch.resolve_stack`` and the REAL GOAL-CONTRACT scorecard
module ``scripts/flow_v2_closure_scorecard.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------------------
# The four DISTILL gate-out gate ids, in DECLARED ORDER (DDD-1). The slice-01
# guarantee is that ``resolve_stack("distill","gate-out")`` carries EXACTLY this
# sequence -- ``self-attest`` + ``verify-test-runner`` are LIVE-resolved, no
# longer catalogued-but-dormant. The tokens are the 1:1 dispatcher/catalog ids.
# ---------------------------------------------------------------------------


class DistillGateOut(Enum):
    """A gate id on the DISTILL gate-out stack (the registry is the SOLE source).

    CHECK_SLICE_AT_COMPLETENESS -- the AT-completeness check (block; already wired).
    GATE_DESIGN_AT_COHERENCE    -- the design<->AT coherence gate (warn; already
                                   wired, renamed from gate-g by f-code-design DDD-5).
    SELF_ATTEST                 -- the verdict-validity layer (warn; THIS feature
                                   wires it LIVE into the registry, DDD-1/DDD-2).
    VERIFY_TEST_RUNNER          -- the TestRunnerPort CLI (warn; THIS feature wires
                                   it LIVE into the registry, DDD-1/DDD-2).
    """

    CHECK_SLICE_AT_COMPLETENESS = "check-slice-at-completeness"
    GATE_DESIGN_AT_COHERENCE = "gate-design-at-coherence"
    SELF_ATTEST = "self-attest"
    VERIFY_TEST_RUNNER = "verify-test-runner"


# The DISTILL-OUT gate-id sequence in DECLARED ORDER (DDD-1). CT-1 asserts the
# resolved stack equals exactly this ordered list; CT-2 asserts the on_failure
# semantics of the two NEW rows (both ``warn`` -- the no-objection boundary).
DISTILL_GATE_OUT_DECLARED_ORDER: tuple[str, ...] = (
    DistillGateOut.CHECK_SLICE_AT_COMPLETENESS.value,
    DistillGateOut.GATE_DESIGN_AT_COHERENCE.value,
    DistillGateOut.SELF_ATTEST.value,
    DistillGateOut.VERIFY_TEST_RUNNER.value,
)

# The two NEW rows this feature wires + their don't-break-spine on_failure
# semantics (DDD-2: both ``warn`` -- a record-/runner-absent DISTILL return is
# never vetoed). CT-2 ranges over this map.
NEW_ROW_ON_FAILURE: dict[str, str] = {
    DistillGateOut.SELF_ATTEST.value: "warn",
    DistillGateOut.VERIFY_TEST_RUNNER.value: "warn",
}


# ---------------------------------------------------------------------------
# The wired-module class the scorecard tightening governs (DDD-7). CT-4 asserts
# f-coherence's three modules all live-resolve; CT-5 is the regression-pin: a
# synthetic gate-stack-class id present ONLY as a flavor string is NOT wired.
# ---------------------------------------------------------------------------


class WiredModule(Enum):
    """A f-coherence-and-attestation ``wired_module`` (the GOAL-CONTRACT key).

    The post-rename live keys (DDD-5): ``gate-design-at-coherence`` (was the stale
    ``gate-g``), ``self-attest``, ``test-runner`` (maps to subcommand
    ``verify-test-runner``). After DELIVER, ``_module_wired`` returns True for each
    iff the subcommand is registered AND its gate_id LIVE-resolves in the DISTILL
    gate-out registry (the tightening, DDD-7) -- not merely a flavor-string match.
    """

    GATE_DESIGN_AT_COHERENCE = "gate-design-at-coherence"
    SELF_ATTEST = "self-attest"
    TEST_RUNNER = "test-runner"


# f-coherence-and-attestation's three wired_modules, post-rename (DDD-5). CT-4
# asserts every one evaluates ``_module_wired == True`` against the LIVE state.
COHERENCE_WIRED_MODULES: tuple[str, ...] = tuple(m.value for m in WiredModule)


# The CT-5 regression-pin witness: a gate id that is registered as a real ``des``
# subcommand AND whose name appears in a WIRING_FILES surface -- here a HOOK,
# ``scripts/hooks/run_wave_contract_coherence.py`` (NOT the flavor) -- yet is NOT a
# member of the DISTILL gate-out stack (it belongs to a DIFFERENT wave) and therefore
# NEVER live-resolves there. ``verify-wave-contract-coherence`` is exactly that stable
# witness (verified live: registered + hook-stringed in WIRING_FILES + ABSENT from
# resolve_stack("distill","gate-out")).
#
# Under the OLD ``_term_wired`` check (regex over WIRING_FILES = flavors + hooks) the
# witness is false-credited wired True for the DISTILL boundary (the regex matches the
# hook string AND ignores the wave/boundary -- the demonstrated defect). Under the
# tightened ``_live_resolved("distill","gate-out", <witness>)`` (DDD-7) it must be
# wired False -- it does not live-resolve in that boundary. The witness is a
# DIFFERENT-wave gate, so it never live-resolves for DISTILL even after DELIVER wires
# self-attest + verify-test-runner: the pin is STABLE GREEN post-DELIVER, never a
# pin that flips back RED. (Name is historical: the witness is hook-stringed, not
# flavor-stringed -- the false-credit class is identical: a WIRING_FILES string match.)
FLAVOR_ONLY_WITNESS_GATE_ID = "verify-wave-contract-coherence"


@dataclass(frozen=True)
class StackObservable:
    """The observable slice of a ``resolve_stack`` run the ATs assert on.

    Port-exposed names only (Mandate-8 universe): the ORDERED gate-id sequence the
    spine resolves, and the per-row ``on_failure`` for the two new rows. NEVER an
    internal resolver field.
    """

    gate_ids_in_order: tuple[str, ...]
    on_failure_by_gate: dict[str, str]


# ---------------------------------------------------------------------------
# slice-02 (DDD-9): the dead flavor ``wave_gate_stacks`` $defs is REMOVED from
# the SHIPPED flavor SCHEMA ``nWave/flavors/_schema.yaml`` -- completing the
# MOVE so the registry (``nWave/waves/*.yaml``) is the SOLE gate-stack source and
# no dead flavor schema property survives. This is the SCHEMA-level twin of
# slice-01 CT-3 (which removed the dormant block from a flavor INSTANCE): once no
# instance carries the block, the schema property that allowed it is dead and
# must go too. CS-1 asserts ``properties.wave_gate_stacks`` is ABSENT from the
# shipped schema.
# ---------------------------------------------------------------------------


# The schema property whose ABSENCE is f-distill slice-02's OWN deliverable: the
# dead flavor gate-stack $defs the MOVE-not-COPY leaves behind. CS-1 asserts it is
# gone from ``nWave/flavors/_schema.yaml`` ``properties``.
DEAD_SCHEMA_PROPERTY = "wave_gate_stacks"


@dataclass(frozen=True)
class SchemaPropertyObservable:
    """The observable slice of a flavor-schema read (slice-02 CS-1).

    Port-exposed: whether the shipped flavor SCHEMA still declares the dead
    ``wave_gate_stacks`` property. The AT reads this from the shipped artifact
    (``nWave/flavors/_schema.yaml``) as DATA -- never an internal field.
    """

    schema_carries_dead_property: bool


@dataclass(frozen=True)
class WiredModuleObservable:
    """The observable slice of a scorecard ``_module_wired`` evaluation (CT-4/CT-5).

    Port-exposed: whether the GOAL-CONTRACT scorecard counts the module wired. The
    ATs read this through the REAL scorecard module's driving surface, never an
    internal scorecard field.
    """

    module: str
    wired: bool | None
