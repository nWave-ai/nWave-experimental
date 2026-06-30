"""Step definitions: the AT-review verdict producer records keyless and is
discoverable through the des single entry point (oss-review-verdict-demotion, S2).

Decision SSOT: docs/analysis/oss-hmac-signing-demotion-2026-06-11.md.
Feature-delta S2 row + D-register + Hard contracts (a) key-absence-non-event,
(b) record-presence PASS leg.

Mandate 13: the driving ports are the production producer CLI
(``des.cli.at_review_verdict.main``) and the des dispatcher
(``des.cli.__main__.main`` with ``record-at-review-verdict``), invoked through
the ``ProducerComposition`` composition root via their argv ``main`` entries.
The round-trip witness drives the slice-01 keyless carpaccio gate
(``des.cli.carpaccio_slice_gate.main``) the same way. NO direct-domain import
of ``record_at_review_verdict`` or ``check_at_review``.

Layer 3 (subprocess/FS acceptance). Example-only, no PBT machinery (Mandate
9 v2 / 11): the only driven adapter is the real filesystem (tmp_path), so the
slice is @real-io and each S2 path is a named example, not a Hypothesis @given.

The producer has a bounded-change contract: its observable effect is one new
keyless ATReviewVerdict line appended to the ledger. The When-step asserts via
``assert_state_delta`` over a port-exposed ledger universe (Mandate 8): the
verdict count gains one, the recorded record's key-set is the keyless set (no
``hmac_sha256``), and no signing-key file appears.

Step bodies delegate to ``ProducerComposition``; no inline business logic
(Mandate-12 criterion 3) -- each body is a typed lookup plus a composition call.

RED contract (fail-for-right-reason): on the pre-demotion tree
``record_at_review_verdict`` writes ``hmac_sha256`` via
``require_signing_key`` -- which raises ``AssertionError`` when no key is
resolvable. All S2 scenarios run keyless, so the direct-producer scenarios
raise before writing a record (no verdict recorded -> "recorded" assertion
fails with AssertionError, missing functionality: the keyless write path), and
the dispatcher scenario hits an unregistered subcommand (argparse rejects the
``record-at-review-verdict`` choice -> no record -> AssertionError). Not test
bugs: every dependency resolves cleanly (Mandate 7: RED, not BROKEN). The
crafter greens them by dropping the ``hmac_sha256`` write + key import and
adding the ``record-at-review-verdict`` ``_REGISTRY`` row + mirror.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, set_to, unchanged

from .composition_slice_02 import GateRun, ProducerComposition, ProducerRun
from .domain_types_slice_02 import (
    ENTRY_POINT_BY_PHRASE,
    FeatureId,
)


scenarios("../slice-02-keyless-producer-and-registration.feature")


@pytest.fixture
def producer(tmp_path: Path) -> ProducerComposition:
    """Production-wired composition root over a tmp_path repository."""
    return ProducerComposition(repo_dir=tmp_path / "repo")


@pytest.fixture
def run_box() -> dict[str, object]:
    """Carrier for producer + gate runs across When -> Then steps."""
    return {}


# --- Given -------------------------------------------------------------------


@given(
    "an atdd_pure feature with an empty ledger and no reviewer signing key provisioned"
)
def given_keyless_feature(producer: ProducerComposition) -> None:
    producer.create_keyless_repo(FeatureId("oss-review-verdict-demotion"))


@given("the entering slice has an approved AT set ready to record")
def given_approved_at_set(producer: ProducerComposition) -> None:
    # Precondition only: the empty keyless repo from the Background already
    # carries the slice's .feature; the approval verdict is supplied to the
    # When-step. Assert the chained-narrative baseline holds.
    assert producer.ledger_path.exists()


# --- When --------------------------------------------------------------------


@when(
    parsers.parse("the reviewer records the approved verdict through {entry_phrase}"),
    target_fixture="record_result",
)
def when_record_verdict(
    producer: ProducerComposition,
    run_box: dict[str, object],
    entry_phrase: str,
) -> ProducerRun:
    before = producer.capture_universe()
    result = producer.record_approved_verdict(ENTRY_POINT_BY_PHRASE[entry_phrase])
    after = producer.capture_universe()
    assert_state_delta(
        before=before,
        after=after,
        universe={
            "ledger.verdict_count",
            "ledger.latest_record_has_signature",
            "signing_key.exists",
        },
        expected={
            # The keyless producer appends exactly one verdict for the slice...
            "ledger.verdict_count": set_to(1),
            # ...the appended record carries NO hmac_sha256 field...
            "ledger.latest_record_has_signature": set_to(False),
            # ...and no signing-key file ever materializes (key absence is a
            # non-event, never resolved). Universe-bound, port-exposed (Mandate
            # 8): the count, the signature-presence boolean, the key-file flag.
            "signing_key.exists": unchanged(),
        },
    )
    run_box["record_result"] = result
    return result


# --- Then --------------------------------------------------------------------


@then("the ledger gains one approved verdict for the entering slice")
def then_one_recorded_verdict(producer: ProducerComposition) -> None:
    assert producer.recorded_verdict_count() == 1


@then("the recorded verdict binds the reviewer identity and the content seal")
def then_record_binds_veto_fields(producer: ProducerComposition) -> None:
    assert producer.latest_record_binds_reviewer_and_seal()


@then("the recorded verdict carries no signature field")
def then_record_has_no_signature_field(producer: ProducerComposition) -> None:
    assert not producer.latest_record_carries_signature_field()


@then("no reviewer signing key was provisioned anywhere")
def then_no_key_provisioned(producer: ProducerComposition) -> None:
    assert producer.no_signing_key_provisioned()


@then("the slice-01 keyless gate clears the entering slice on the recorded verdict")
def then_gate_clears_round_trip(
    producer: ProducerComposition,
    run_box: dict[str, object],
) -> None:
    """Walking-skeleton round-trip: the producer wrote it, the keyless gate
    clears it. Drives the slice-01 gate via its argv main (no direct
    ``check_at_review`` call) and asserts the cleared verdict."""
    gate: GateRun = producer.run_consumer_gate()
    assert gate.cleared, gate.payload
