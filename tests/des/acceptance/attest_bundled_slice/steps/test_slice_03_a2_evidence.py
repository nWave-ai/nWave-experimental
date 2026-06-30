"""pytest-bdd binding for f-attest-bundled-slice slice-03 scenarios (the A2 contract).

Driving surface (Mandate-13 driving-port-only, Layer 3 subprocess): the REAL
``des attest-bundled-slice`` subcommand via the production dispatcher, invoked
against a crafted TEMP git repo. Step bodies delegate to the composition root
(``composition_slice_03_a2_evidence.py``); no business logic in step bodies
(Mandate-12 criterion 3). The Given binds a fixture name to the typed
``A2Fixture`` enum (DSL emergence over typed domain vocabulary, not decorator
proliferation).

Active-RED scaffold (atdd_pure -- NOT @skip): RED until slice-03 DELIVER replaces
the inherited strict P2/P4 in ``attest_bundled_slice.main()`` with the A2
evidence check (A2.a real-AT presence + A2.b two-branch trailer presence + the
NEW ``_has_step_id_line`` helper + A2.c no-``@skip``/``@xfail`` scan). At HEAD
main() composes the shared ``_preconditions`` (P1->P2->P3->P4->P5->P6) then emits
``BundledSliceAttestPreconditionsCleared`` (exit 0). Each Then turns a captured
subprocess observable into a semantic AssertionError, never a collection / import
error. The composition imports ZERO ``des.adapters.*`` (slice-02 RC-2 / F-005).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_03_a2_evidence import A2EvidenceComposition
from .domain_types_attest_bundled_slice import A2Fixture


scenarios("../slice-03-a2-bundle-evidence.feature")


@pytest.fixture
def attest(tmp_path: Path) -> A2EvidenceComposition:
    return A2EvidenceComposition(tmp_path)


# --- Given (one per slice-03 A2 fixture) ------------------------------------


@given(
    "a bundle commit that names the slice in its trailer but carries no "
    "acceptance test for it"
)
def given_no_slice_at(attest: A2EvidenceComposition) -> None:
    attest.given_fixture(A2Fixture.NO_SLICE_AT)


@given(
    "a bundle commit that carries the slice's acceptance test but neither a "
    "slice nor a step trailer"
)
def given_no_trailer(attest: A2EvidenceComposition) -> None:
    attest.given_fixture(A2Fixture.NO_TRAILER)


@given(
    "a bundle commit trailered only with a feature-level step that names no "
    "slice but carries the slice's acceptance test"
)
def given_step_id_only(attest: A2EvidenceComposition) -> None:
    attest.given_fixture(A2Fixture.STEP_ID_ONLY)


@given(
    "a bundle commit trailing a different slice but carrying this slice's "
    "acceptance test"
)
def given_different_slice_trailer(attest: A2EvidenceComposition) -> None:
    attest.given_fixture(A2Fixture.DIFFERENT_SLICE_TRAILER)


@given("a bundle commit whose slice acceptance test carries a deferred scenario")
def given_xfail_scenario(attest: A2EvidenceComposition) -> None:
    attest.given_fixture(A2Fixture.XFAIL_SCENARIO)


# --- When -------------------------------------------------------------------


@when("the maintainer attests the bundled slice")
def when_operator_attests(attest: A2EvidenceComposition) -> None:
    attest.when_operator_attests_the_bundled_slice()


# --- Then -------------------------------------------------------------------


@then(
    "the attestation is refused because the slice's real acceptance evidence is absent"
)
def then_refused_absent_at(attest: A2EvidenceComposition) -> None:
    attest.then_attest_refuses_on_absent_at()


@then(
    "the attestation is refused because the commit carries no recognised "
    "carpaccio or wave trailer"
)
def then_refused_absent_trailer(attest: A2EvidenceComposition) -> None:
    attest.then_attest_refuses_on_absent_trailer()


@then(
    "the attestation is not refused on the trailer ground because the step "
    "trailer is recognised"
)
def then_not_refused_on_trailer(attest: A2EvidenceComposition) -> None:
    attest.then_attest_not_refused_on_the_trailer_ground()


@then(
    "the attestation is not refused on the trailer ground because a recognised "
    "slice trailer is present"
)
def then_not_refused_on_present_slice_trailer(
    attest: A2EvidenceComposition,
) -> None:
    attest.then_attest_not_refused_on_a_present_slice_trailer()


@then(
    "the attestation is refused because a deferred scenario is not genuinely exercised"
)
def then_refused_deferred_scenario(attest: A2EvidenceComposition) -> None:
    attest.then_attest_refuses_on_deferred_scenario()
