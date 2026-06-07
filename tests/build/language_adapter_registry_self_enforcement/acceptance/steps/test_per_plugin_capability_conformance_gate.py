"""Tier A step definitions — the per-plugin x per-capability conformance gate (slice-01).

CONTRACT_SHAPE: pure-function

language-adapter-registry-self-enforcement, slice-01 (DISTILL, per-slice JIT;
DDD-D3a plugin-axis ruling). The walking-skeleton vertical: the slice-12
``detect_real_adapter_capability_conformance`` detector GENERALIZED from 1-D to the
2-D per-plugin x per-capability cross-product.

Driving port: the pure ``detect_per_plugin_capability_conformance`` entrypoint
(``des.testarch.rules.registry_conformance``), reached through the
``PerPluginCapabilityConformanceService`` composition. Step bodies delegate to the
service and assert against port-exposed observables (the ``ConformanceOutcome`` enum,
the named ``(plugin, capability)`` offender); no business logic is inlined
(Mandate-12 criterion 3).

Recall/precision golden-fixture shape (DDD-D3a, mirroring slice-12):

  * RECALL scenario — drives the 2-D detector against the FROZEN unrealized-pair
    snapshot (which permanently carries a registered-but-unrealized pair). Asserts
    FLAGGED + the named planted offender. Green forever once the detector exists.
  * PRECISION (frozen) scenario — drives the detector against the FROZEN all-realized
    snapshot. Asserts CONFORMANT — the fail-closed precision bar.
  * PRECISION-LIVE scenario — drives the detector against the real ``PythonAstAdapter``
    method-surface injected as a single-element realized map. Asserts CONFORMANT. THIS
    is the scenario that flips RED->GREEN exactly when A_GREEN implements C1.

Layer ~2 (in-memory introspection of the testarch substrate, in-process) →
example-based, no PBT machinery (Mandate 9 v2: the only driven dependency is the
in-memory testarch package surface + frozen fixtures; the conformance fact is a
finite enumerable cross-check, not an unbounded domain). The conformance reads are
pure-function queries that mutate no state — the verdict is the port-exposed
observable, so the Then steps assert directly on it (no ``assert_state_delta``
universe to declare; nothing is mutated — Mandate-8 layer-1-3 universe-guard applies
to STATE-MUTATING steps only).

RED-for-right-reason (ADR-025 / Mandate-7): each When step drives the production
``detect_per_plugin_capability_conformance`` function, a RED scaffold raising
``AssertionError`` until A_GREEN implements it. All three scenarios RED now; the
recall + frozen-precision scenarios go GREEN when the detector is implemented; the
precision-live scenario goes GREEN at the same time (``PythonAstAdapter`` realizes all
9 required capabilities, so it is conformant once the cross-product logic exists). The
failures are semantic ``AssertionError`` from the missing detector body — NOT
collection / import / skip errors.

Honest tagging: @component (auto-``unit`` under ``tests/build/``), NEVER
@wiring_e2e/@subprocess.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from tests.build.language_adapter_registry_self_enforcement.acceptance.fixtures.per_plugin_capability.violation_unrealized_pair_snapshot import (
    PLANTED_UNREALIZED_CAPABILITY,
    PLANTED_UNREALIZED_PLUGIN_ID,
)
from tests.build.language_adapter_registry_self_enforcement.acceptance.steps.domain_types import (
    ConformanceOutcome,
)
from tests.build.language_adapter_registry_self_enforcement.acceptance.steps.per_plugin_capability_composition import (
    build_service,
)


scenarios("../per-plugin-capability-conformance-gate.feature")


# --- fixtures --------------------------------------------------------------


@pytest.fixture
def service():
    """Production composition root for the per-plugin capability conformance gate."""
    return build_service()


@pytest.fixture
def run_state() -> dict:
    """Mutable carrier for the conformance verdict across Given/When/Then."""
    return {}


# --- Given -----------------------------------------------------------------


@given("the generalized per-plugin capability conformance gate")
def given_the_gate(service, run_state):
    # Precondition only — the conformance service is the SUT entry. No expected
    # output is staged here (no Fixture Theater).
    run_state["service"] = service


# --- When ------------------------------------------------------------------


@when("the maintainer checks the frozen snapshot with an unrealized capability pair")
def when_check_unrealized_pair_snapshot(run_state):
    run_state["verdict"] = run_state[
        "service"
    ].conformance_of_unrealized_pair_snapshot()


@when("the maintainer checks the frozen snapshot where every plugin is fully realized")
def when_check_all_realized_snapshot(run_state):
    run_state["verdict"] = run_state["service"].conformance_of_all_realized_snapshot()


@when("the maintainer checks the injected reference adapter surface")
def when_check_injected_reference_adapter(run_state):
    run_state["verdict"] = run_state[
        "service"
    ].conformance_of_injected_reference_adapter()


# --- Then (recall) ---------------------------------------------------------


@then("the gate flags a plugin-capability gap in the snapshot")
def then_flags_plugin_capability_gap(run_state):
    outcome = run_state["service"].outcome_of(run_state["verdict"])
    assert outcome is ConformanceOutcome.FLAGGED


@then("the gate names the plugin and the capability the plugin does not realize")
def then_names_plugin_and_capability(run_state):
    named = {
        (violation.plugin_id, violation.capability)
        for violation in run_state["verdict"].violations
    }
    assert (PLANTED_UNREALIZED_PLUGIN_ID, PLANTED_UNREALIZED_CAPABILITY) in named


# --- Then (precision) ------------------------------------------------------


@then("the gate reports every plugin as realizing every registered capability")
def then_conformant(run_state):
    outcome = run_state["service"].outcome_of(run_state["verdict"])
    assert outcome is ConformanceOutcome.CONFORMANT
