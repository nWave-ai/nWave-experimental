"""pytest-bdd binding for wire-multilang-run-facets slice-01 scenarios.

Driving surface (Mandate-13 driving-port-only, Layer 3 subprocess): the REAL PRODUCTION
REGISTRY DISPATCH (``seed_runner_registry()`` + ``RunnerAdapter(token).run(...)`` over
``GLOBAL_REGISTRY.lookup``) driven in a child interpreter over a hermetic target + a FAKE
runner on a controlled PATH. Step bodies delegate to the composition root
(``composition_slice_01_wire_multilang.py``); no business logic in step bodies (Mandate-12
criterion 3). The dispatch-outcome token is parsed into the typed ``DispatchOutcome`` enum,
so the assertion ranges over the typed domain vocabulary (DSL emergence).

CRITICAL -- the production dispatch, NOT the bypass: this harness NEVER imports
``run_go_scope`` / ``run_vitest_scope`` directly. The run-facet is reached ONLY through the
registry lookup the production code uses. The C13/C14 ATs the adversarial swarm (2026-06-24)
flagged imported the run-facet directly in a child -- proving the isolated function while
bypassing the registry. These ATs drive ``seed_runner_registry()`` + ``RunnerAdapter.run``,
so they prove the WIRING, not just the function.

ZERO ``des.adapters.*`` / ``des.ports.*`` import in THIS process: the SUT is only ever
imported in the child interpreter (inside the composition root's ``python -c`` probe).

Active-RED scaffold (atdd_pure -- NOT @skip): RED until DELIVER registers the run-facets in
``seed_runner_registry``. At HEAD the go-test / vitest tokens are unregistered, so the
production dispatch raises ``RunnerAdapterUnavailable`` (OUTCOME:UNWIRED); each AC-1/AC-2
Then fires a semantic AssertionError, never a collection / import error. AC-3 (preservation)
is live-green: pytest + cargo-test are already registered.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_01_wire_multilang import WireMultilangComposition
from .domain_types_wire_multilang import DispatchOutcome, TargetLanguage


scenarios("../slice-01-wire-multilang-run-facets.feature")


@pytest.fixture
def wire() -> WireMultilangComposition:
    return WireMultilangComposition()


# --- Given -----------------------------------------------------------------


@given("a hermetic Go target with a fake go on PATH")
def given_go_target(wire: WireMultilangComposition) -> None:
    wire.given_target_with_fake_runner(TargetLanguage.GO)


@given("a hermetic JS/TS target with a fake vitest on PATH")
def given_vitest_target(wire: WireMultilangComposition) -> None:
    wire.given_target_with_fake_runner(TargetLanguage.VITEST)


@given("the runner registry is seeded")
def given_registry_seeded(wire: WireMultilangComposition) -> None:
    wire.given_the_registry_is_seeded()


# --- When ------------------------------------------------------------------


@when("the production dispatch runs through the runner registry")
def when_production_dispatch_runs(wire: WireMultilangComposition) -> None:
    wire.when_the_production_dispatch_runs()


@when("the existing runner tokens are looked up")
def when_existing_tokens_looked_up(wire: WireMultilangComposition) -> None:
    wire.when_the_registry_is_seeded()


# --- Then ------------------------------------------------------------------


@then("the dispatch outcome is wired")
def then_dispatch_outcome_wired(wire: WireMultilangComposition) -> None:
    wire.then_the_dispatch_outcome_is(DispatchOutcome.WIRED)


@then("the existing runners still resolve")
def then_existing_runners_resolve(wire: WireMultilangComposition) -> None:
    wire.then_the_existing_runners_still_resolve()
