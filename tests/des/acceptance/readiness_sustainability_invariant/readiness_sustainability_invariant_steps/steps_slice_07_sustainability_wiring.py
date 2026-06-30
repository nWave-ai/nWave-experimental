"""Step bindings -- the readiness SUSTAINABILITY invariant (invariant 7) wiring.

The wave-fires-the-gate oracle: the readiness gate
(`des verify-readiness-pre-dispatch`, wired into the atdd_pure flavor gate_stack
at dispatch.pre) gains a 7th invariant SUSTAINABILITY that calls
`validate_sustainability_content` on the feature-delta. A feature-delta whose
sustainability section is DECLARED-BUT-MISSING/malformed FAILS readiness; a
well-formed section clears that dimension.

Mandate-13 (S2 driving-port-only): imports ONLY the composition fixture +
`domain_types`. ZERO direct-domain imports. Driving port = the real
`des verify-readiness-pre-dispatch` CLI subprocess via `composition.verify()`.

Mandate-12 criterion 3: every step body is <=2 statements ending in a
`composition.<method>(...)` call / a single assertion; no control flow.

S1 step-text uniqueness: every literal here is sustainability/invariant-7-specific
and DISTINCT from the `readiness_reuse_invariant` package and the
sustainable-test-suite slice-01..05 literals. The When step speaks of "the
readiness gate at dispatch readiness" (not the reuse package's "before first
crafter dispatch", not slice-03's "the sustainability content check runs").
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from .domain_types import (
    SUSTAINABILITY_SHAPE_BY_PHRASE,
    InvariantStatus,
    ReadinessInvariantId,
    ReadinessVerdict,
)


# --- Given: arm a six-invariant-satisfying workspace, varying sustainability --


@given(
    parsers.parse(
        "a dispatch-ready feature whose feature-delta carries {sustainability_phrase}"
    )
)
def given_dispatch_ready_feature_with_sustainability(
    readiness_sustainability_composition, sustainability_phrase: str
) -> None:
    readiness_sustainability_composition.arm_feature_delta(
        SUSTAINABILITY_SHAPE_BY_PHRASE[sustainability_phrase]
    )


# --- When: drive the real readiness gate subprocess ------------------------


@when("the readiness gate runs at dispatch readiness")
def when_readiness_gate_runs_at_dispatch_readiness(
    readiness_sustainability_composition,
) -> None:
    readiness_sustainability_composition.verify()


# --- Then: observable verdict + 7th-invariant status -----------------------


@then("the readiness gate refuses the dispatch on the sustainability dimension")
def then_gate_refuses_on_sustainability(readiness_sustainability_composition) -> None:
    assert (
        readiness_sustainability_composition.last_verdict() is ReadinessVerdict.REFUSED
    )


@then("the sustainability readiness invariant is reported as failed")
def then_sustainability_invariant_failed(
    readiness_sustainability_composition,
) -> None:
    assert (
        readiness_sustainability_composition.sustainability_invariant_among_failures()
    )


@then("the sustainability readiness invariant is reported as satisfied")
def then_sustainability_invariant_satisfied(
    readiness_sustainability_composition,
) -> None:
    assert (
        readiness_sustainability_composition.last_invariant_status(
            ReadinessInvariantId.SUSTAINABILITY
        )
        is InvariantStatus.SATISFIED
    )


@then("the sustainability remediation names the Test Reuse & Consolidation section")
def then_sustainability_remediation_names_section(
    readiness_sustainability_composition,
) -> None:
    assert readiness_sustainability_composition.last_remediation_contains(
        ReadinessInvariantId.SUSTAINABILITY, "Test Reuse & Consolidation"
    )
