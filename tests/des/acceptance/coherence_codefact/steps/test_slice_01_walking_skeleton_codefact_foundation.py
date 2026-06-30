"""pytest-bdd binding for the f-coherence-and-attestation slice-01 scenarios.

Driving surface (Mandate-13 driving-port-only, Layer 3 composition): the REAL
CodeFactPort / TextSearchAdapter / slice-01 code-fact gate / byte-lock guard via
the production composition root. Step bodies delegate to the composition root
(composition_coherence_codefact.py); no business logic in step bodies
(Mandate-12). The ``<capability>`` parameter is parsed once into the typed
``CapabilityId`` enum, so ONE scenario shape ranges over the 5 LOCKED stable-core
capabilities.

active-RED scaffold (atdd_pure -- NOT @skip): every scenario is RED until DELIVER
lands the slice-01 seams (the port + the floor adapter + the code-fact gate + the
byte-lock guard + the locked-vocabulary fixture). Each scenario fails with a
semantic AssertionError naming the missing seam, never a collection / import /
setup error.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_coherence_codefact import CoherenceCodeFactComposition
from .domain_types_coherence_codefact import CapabilityId, GuardProbe, WiringCase


scenarios("../slice-01-walking-skeleton-codefact-foundation.feature")


# Capability wire-token (kebab-lowercase, LOCKED) -> typed enum.
_CAPABILITY_BY_TOKEN = {c.value: c for c in CapabilityId}


@pytest.fixture
def codefact() -> CoherenceCodeFactComposition:
    return CoherenceCodeFactComposition()


# --- Given -----------------------------------------------------------------


@given(
    parsers.parse("a code-fact gate requires the stable-core capability {capability}")
)
def given_capability_required(
    codefact: CoherenceCodeFactComposition, capability: str
) -> None:
    codefact.given_capability_required(_CAPABILITY_BY_TOKEN[capability])


@given("a net-new symbol with no production call-site")
def given_never_wired_symbol(codefact: CoherenceCodeFactComposition) -> None:
    codefact.given_wiring_case(WiringCase.NEVER_WIRED)


@given("the published-language byte-lock guard")
def given_byte_lock_guard(codefact: CoherenceCodeFactComposition) -> None:
    codefact.given_guard_probe(GuardProbe.PRISTINE)


# --- When ------------------------------------------------------------------


@when("the substrate is asked for the fact through the CodeFactPort")
def when_substrate_asked(
    codefact: CoherenceCodeFactComposition, tmp_path: Path
) -> None:
    codefact.when_floor_answers_via_port(tmp_path)


@when("a code-fact gate re-derives whether it is never-wired through the port")
def when_gate_rederives_never_wired(
    codefact: CoherenceCodeFactComposition, tmp_path: Path
) -> None:
    codefact.when_gate_rederives_never_wired(tmp_path)


@when("the guard runs against the pristine locked vocabulary")
def when_guard_runs_pristine(
    codefact: CoherenceCodeFactComposition, tmp_path: Path
) -> None:
    codefact.given_guard_probe(GuardProbe.PRISTINE)
    codefact.when_byte_lock_guard_runs(tmp_path)


@when("the guard runs against a planted-drift vocabulary variant")
def when_guard_runs_drifted(
    codefact: CoherenceCodeFactComposition, tmp_path: Path
) -> None:
    codefact.given_guard_probe(GuardProbe.DRIFTED)
    codefact.when_byte_lock_guard_runs(tmp_path)


# --- Then ------------------------------------------------------------------


@then("a usable answer comes back")
def then_usable_answer(codefact: CoherenceCodeFactComposition) -> None:
    codefact.then_a_usable_answer_came_back()


@then("the answer carries provider and confidence provenance")
def then_provenance_tagged(codefact: CoherenceCodeFactComposition) -> None:
    codefact.then_provenance_is_tagged()


@then("the provider token is one of the locked cross-tier values")
def then_provider_locked(codefact: CoherenceCodeFactComposition) -> None:
    codefact.then_provider_token_is_locked()


@then("the confidence token is one of the locked cross-tier values")
def then_confidence_locked(codefact: CoherenceCodeFactComposition) -> None:
    codefact.then_confidence_token_is_locked()


@then("the answer is tagged as the text-search floor at noisy confidence")
def then_floor_noisy(codefact: CoherenceCodeFactComposition) -> None:
    codefact.then_provider_is_text_search_floor()


@then("the never-wired answer carries a locked reason code")
def then_never_wired_reason_locked(
    codefact: CoherenceCodeFactComposition,
) -> None:
    codefact.then_never_wired_reason_is_locked()


@then("the byte-lock guard passes")
def then_guard_passes(codefact: CoherenceCodeFactComposition) -> None:
    codefact.then_pristine_fixture_passes()


@then("the byte-lock guard goes red")
def then_guard_red(codefact: CoherenceCodeFactComposition) -> None:
    codefact.then_planted_drift_makes_guard_red()
