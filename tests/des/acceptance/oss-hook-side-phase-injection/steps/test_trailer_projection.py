"""Step definitions for slice-03 -- mechanical HMAC trailer projection.

slice-03 of oss-hook-side-phase-injection (the DISTILL-wave hook keystone, D1).

Step bodies are delegate-only (Mandate-12 criterion 3): each is a single typed
lookup into the ``slice03_domain_types`` phrase tables plus one composition call.
All projection + verification logic lives in the production
``derive_review_trailer`` + ``verify_commit_trailers`` CLIs; the composition root
only wires the real CLI subprocesses and reads back the observable stdout / exit
code (plus the precondition ledger seed through the shipped producer + reader).

S1 (step-text uniqueness) note: every literal step string in this module is
distinct from the slice-01 ``test_g_distill_exit_gate.py`` and slice-02
``test_distill_dispatch_and_deliver_exit_symmetry.py`` literals in the same
feature directory. The slice-03 vocabulary is deliberately worded around the
"reviewer attribution" / "delivery verifier" domain nouns so no
``(step_type, literal)`` key is double-registered across the three step files.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .slice03_composition import (
    DeriveOutcome,
    RoundTripOutcome,
    TrailerProjectionComposition,
)
from .slice03_domain_types import (
    FAULT_BY_PHRASE,
    RoundTripVerdict,
    TrailerProjection,
)


scenarios("../trailer-projection.feature")


# --- fixtures -----------------------------------------------------------------


@pytest.fixture
def trailer_projection(tmp_path: Path) -> TrailerProjectionComposition:
    return TrailerProjectionComposition(tmp_path)


@pytest.fixture
def derive_holder() -> dict[str, DeriveOutcome]:
    return {}


@pytest.fixture
def round_trip_holder() -> dict[str, RoundTripOutcome]:
    return {}


# --- shared precondition (AT-1 / AT-2 / AT-3) --------------------------------


@given("a signed acceptance-test review for a slice is recorded in the ledger")
def _given_signed_review_recorded(
    trailer_projection: TrailerProjectionComposition,
) -> None:
    trailer_projection.seed_signed_verdict()


# --- AT-1: derive the trailer pair -------------------------------------------


@when("the orchestrator derives the reviewer attribution for that slice")
def _when_orchestrator_derives_attribution(
    trailer_projection: TrailerProjectionComposition,
    derive_holder: dict[str, DeriveOutcome],
) -> None:
    derive_holder["result"] = trailer_projection.run_derive_cli()


@then("a reviewer attribution line is projected for that review")
def _then_attribution_line_projected(
    derive_holder: dict[str, DeriveOutcome],
) -> None:
    result = derive_holder["result"]
    assert result.projection == TrailerProjection.PAIR_EMITTED
    assert result.reviewed_by_line is not None


@then("a matching verdict payload line is projected alongside it")
def _then_payload_line_projected(
    derive_holder: dict[str, DeriveOutcome],
) -> None:
    assert derive_holder["result"].verdict_payload_line is not None


@then("the derivation succeeds with exit code zero")
def _then_derivation_exit_zero(
    derive_holder: dict[str, DeriveOutcome],
) -> None:
    assert derive_holder["result"].exit_code == 0


# --- AT-2: derive->verify clean round-trip -----------------------------------


@given("the orchestrator has derived the reviewer attribution for that slice")
def _given_attribution_derived(
    trailer_projection: TrailerProjectionComposition,
) -> None:
    trailer_projection.run_derive_cli()


@when("the derived attribution is embedded in a slice commit and checked at delivery")
def _when_attribution_checked_at_delivery(
    trailer_projection: TrailerProjectionComposition,
    round_trip_holder: dict[str, RoundTripOutcome],
) -> None:
    round_trip_holder["result"] = trailer_projection.run_round_trip()


@then("the delivery verifier accepts the attribution as authentic")
def _then_verifier_accepts_authentic(
    round_trip_holder: dict[str, RoundTripOutcome],
) -> None:
    assert round_trip_holder["result"].verdict == RoundTripVerdict.VERIFIES


@then("the verifier reports success with exit code zero")
def _then_verifier_success_exit_zero(
    round_trip_holder: dict[str, RoundTripOutcome],
) -> None:
    assert round_trip_holder["result"].verify_exit_code == 0


# --- AT-3: fault-injected round-trip (closed error set) ----------------------


@when(
    parsers.parse("the derived attribution is embedded in a slice commit but {fault}")
)
def _when_attribution_embedded_with_fault(
    trailer_projection: TrailerProjectionComposition,
    round_trip_holder: dict[str, RoundTripOutcome],
    fault: str,
) -> None:
    round_trip_holder["result"] = trailer_projection.run_round_trip(
        FAULT_BY_PHRASE[fault]
    )


@then(parsers.parse("the delivery verifier refuses the attribution as {outcome}"))
def _then_verifier_refuses(
    round_trip_holder: dict[str, RoundTripOutcome], outcome: str
) -> None:
    # The Gherkin fault phrase is carried on the When; the outcome phrase here is
    # narrative -- the mechanical assertion is the closed error set verified on
    # the exit-code step below. We assert only that the verifier did NOT verify.
    assert round_trip_holder["result"].verdict != RoundTripVerdict.VERIFIES


@then(parsers.parse("the verifier reports the refusal with exit code {code:d}"))
def _then_verifier_refusal_exit_code(
    round_trip_holder: dict[str, RoundTripOutcome], code: int
) -> None:
    assert round_trip_holder["result"].verify_exit_code == code
