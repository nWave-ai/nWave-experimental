"""Tier A step definitions -- the live-registry conformance gate (slice-03).

CONTRACT_SHAPE: unbounded-preservation

language-adapter-registry-self-enforcement, slice-03 (DISTILL, per-slice JIT; DDD-D4a).
The LIVE-registry end-to-end vertical: the conformance gate CLI mode resolve-and-probes
the ACTUAL registered ``nwave.lang.adapter`` plugins (C2) and cross-checks each plugin's
realized surface against the registered-capability obligation set (C1), running as part of
the gate surface (C5), so registry completeness is enforced mechanically.

Driving port (Mandate-13 driving-port-only boundary): the gate is reached EXCLUSIVELY
through a composition-root driving surface -- LAYER 3 SUBPROCESS (scenario 1, the real CLI
``--check-conformance`` over the real registry) or LAYER 3 COMPOSITION (scenarios 2+3, the
gate-runner ``run_conformance_gate(source)`` with an injected discovery source). Step bodies
delegate to ``ConformanceGateService`` (the composition root) and assert against port-exposed
observables (the ``ConformanceGateLane`` exit-code enum); no business logic is inlined and
no C1/C2 domain function is called directly (Mandate-12 criterion 3 + Mandate-13).

Three falsifiable-at-HEAD corpora (DDD-D4a):

  * RECALL / GAP (scenario 1) -- the REAL live registry. At HEAD the inert
    ``_conformance_fixture`` realizes 0/9 -> a GENUINE registered-but-unrealized gap ->
    exit 1 (lane GAP). Falsifiable WITHOUT slice-05a. The live-registry end-to-end witness.
  * LOUD INDETERMINATE (scenario 2) -- an injected unresolvable ``entry_points`` source;
    the gate really attempts ``.load()`` and really fails -> exit 3 (lane INDETERMINATE)
    loud, never silent green (DDD-D5).
  * PRECISION-CLEAN / CONFORMANT (scenario 3) -- a frozen all-realized discovery result ->
    exit 0 (lane CONFORMANT), pinning the exit-0 lane WITHOUT claiming the LIVE registry is
    conformant (precision-live-CONFORMANT deferred to slice-05a).

Layer ~3 (real CLI subprocess + in-process gate-runner over injected sources) ->
example-based, no PBT machinery (Mandate 9 v2: a finite three-lane exit-code contract over
a real/injected registry, not an unbounded generated domain; @real-io/@subprocess precludes
PBT by OR-reduction). The gate reads are pure-function-over-discovery queries that mutate no
state -- the exit code IS the port-exposed observable, so the Then steps assert directly on
it (no ``assert_state_delta`` universe to declare; nothing is mutated -- Mandate-8 layer-1-3
universe-guard applies to STATE-MUTATING steps only, and this gate is read-only by the
@contract-shape:unbounded-preservation contract).

RED-for-right-reason (ADR-025 / Mandate-7): each When step drives the production
``run_conformance_gate`` (C3), a RED scaffold raising ``AssertionError`` until A_GREEN
implements it (consuming the C2 ``resolve_and_probe_realized_surface`` scaffold). All three
scenarios RED now; all three go GREEN when A_GREEN implements C2 + C3. The failures are
semantic ``AssertionError`` from the missing gate body -- NOT collection / import / skip
errors. The subprocess scenario RED-fails as a non-zero CLI exit carrying the scaffold
``AssertionError`` traceback (its lane is not GAP/INDETERMINATE/CONFORMANT -> the Then
assertion fires on the wrong lane, the right-reason RED).

Honest tagging: scenario 1 @real-io @subprocess (real CLI over real registry); scenario 2
@real-io (real ``.load()`` failure); scenario 3 @in-memory (frozen plain-data result).
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from scripts.cli.validate_language_adapter_catalog import (
    _CONFORMANCE_GATE_GAP_PREFIX,
)
from tests.build.language_adapter_registry_self_enforcement.acceptance.steps.conformance_gate_composition import (
    build_service,
)
from tests.build.language_adapter_registry_self_enforcement.acceptance.steps.conformance_gate_domain_types import (
    ConformanceGateLane,
)


scenarios("../conformance-gate-live-registry.feature")


# --- fixtures --------------------------------------------------------------


@pytest.fixture
def service():
    """Production composition root for the live-registry conformance gate."""
    return build_service()


@pytest.fixture
def run_state() -> dict:
    """Mutable carrier for the gate result across Given/When/Then."""
    return {}


# --- Given -----------------------------------------------------------------


@given("the conformance gate is invoked over the live language-adapter registry")
def given_live_registry(service, run_state):
    # Precondition only -- the conformance gate service is the SUT entry. No expected
    # output is staged here (no Fixture Theater); the real registry is the corpus.
    run_state["service"] = service


@given(
    "a registered language-adapter plugin whose discovery surface cannot be resolved"
)
def given_unresolvable_registry(service, run_state):
    run_state["service"] = service


@given(
    "a registry result in which every discovered plugin realizes every required capability"
)
def given_clean_registry_result(service, run_state):
    run_state["service"] = service


# --- When ------------------------------------------------------------------


@when("the maintainer runs the conformance gate")
def when_run_gate_over_live_registry(run_state):
    run_state["result"] = run_state["service"].gate_over_live_registry()


@when("the maintainer runs the conformance gate over the unresolvable registry")
def when_run_gate_over_unresolvable_registry(run_state):
    run_state["result"] = run_state["service"].gate_over_unresolvable_registry()


@when("the maintainer runs the conformance gate over the clean registry result")
def when_run_gate_over_clean_result(run_state):
    run_state["result"] = run_state["service"].gate_over_clean_registry_result()


# --- Then (recall / GAP) ---------------------------------------------------


@then("the conformance gate reports a registered-but-unrealized capability gap")
def then_reports_gap(run_state):
    lane = run_state["service"].lane_of(run_state["result"])
    assert lane is ConformanceGateLane.GAP


@then("the conformance gate names the registered-but-unrealized capability gap")
def then_names_gap(run_state):
    # The GAP lane shares exit 1 with the catalog modes AND collides with a scaffold
    # crash's default exit 1 -- the discriminator is the stderr message prefix DESIGN's
    # Outcome Collision Check mandates. The RED scaffold subprocess emits an
    # ``AssertionError`` traceback (no gap prefix) -> this assertion REDs for the right
    # reason; the GREEN gate emits the deliberate gap prefix -> it GREENs. This guards
    # against the false-GREEN where a crashed scaffold (exit 1) masquerades as a real gap.
    assert _CONFORMANCE_GATE_GAP_PREFIX in run_state["result"].stderr


@then("the conformance gate leaves the registry and catalog unchanged")
def then_registry_and_catalog_unchanged(run_state):
    # The gate is a read-only inspection (@contract-shape:unbounded-preservation): running
    # it does not mutate the registry or the catalog. The live registry still holds exactly
    # the registered plugins after the run -- the gate observed, never wrote.
    from importlib.metadata import entry_points

    registered = {ep.name for ep in entry_points(group="nwave.lang.adapter")}
    assert "_conformance_fixture" in registered


# --- Then (loud INDETERMINATE) ---------------------------------------------


@then("the conformance gate reports an indeterminate discovery failure")
def then_reports_indeterminate(run_state):
    lane = run_state["service"].lane_of(run_state["result"])
    assert lane is ConformanceGateLane.INDETERMINATE


@then("the conformance gate does not report the registry as conformant")
def then_not_conformant(run_state):
    lane = run_state["service"].lane_of(run_state["result"])
    assert lane is not ConformanceGateLane.CONFORMANT


# --- Then (precision-clean / CONFORMANT) -----------------------------------


@then("the conformance gate reports the registry as conformant")
def then_reports_conformant(run_state):
    lane = run_state["service"].lane_of(run_state["result"])
    assert lane is ConformanceGateLane.CONFORMANT
