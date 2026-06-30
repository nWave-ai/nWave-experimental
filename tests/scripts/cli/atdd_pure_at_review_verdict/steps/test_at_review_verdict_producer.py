"""Step definitions: DISTILL records a keyless AT-review verdict.

ADR-029 D5 / slice-07 of the atdd-pure-roadmap-free-rollout.

Layer 3 (subprocess/FS acceptance). Example-only, no PBT machinery
(Mandate 9/11). Post-demotion the producer writes NO ``hmac_sha256`` field;
the tamper-outline rows (signed-field alterations) are superseded by the S2
keyless contract -- there is no signature to alter or verify.

The producer has a bounded-change contract: its only observable effect is one
new ATReviewVerdict line in the AT-completion ledger. The When-step asserts via
`assert_state_delta` over a port-exposed ledger universe (Mandate 8): the
verdict count changes as expected; the prior records are unchanged.

Step bodies delegate to `ATReviewVerdictComposition`; no inline business logic
(Mandate-12 criterion 3) -- each body is a typed lookup plus a composition call.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, set_to, unchanged

from .composition import ATReviewVerdictComposition
from .domain_types import (
    REVIEW_OUTCOME_BY_PHRASE,
    FeatureId,
)


scenarios("../at-review-verdict-producer.feature")


@pytest.fixture
def composition(tmp_path: Path) -> ATReviewVerdictComposition:
    """Production-wired composition root over a tmp_path repository."""
    return ATReviewVerdictComposition(repo_dir=tmp_path / "repo")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the recording result across When -> Then steps."""
    return {}


# --- Given -------------------------------------------------------------------


@given("an atdd_pure feature with an empty AT-completion ledger")
def given_feature_with_empty_ledger(composition: ATReviewVerdictComposition) -> None:
    composition.create_repo_with_empty_ledger(FeatureId("atdd-pure-demo"))
    composition.seed_unrelated_ledger_record()


@given("an acceptance-designer reviewer approved the entering slice's AT set")
def given_reviewer_approved(composition: ATReviewVerdictComposition) -> None:
    # Precondition only: the approval verdict is supplied to the When-step.
    assert composition.ledger_path.exists()


@given("an acceptance-designer reviewer asked the entering slice for revision")
def given_reviewer_needs_revision(composition: ATReviewVerdictComposition) -> None:
    assert composition.ledger_path.exists()


@given(parsers.parse("the entering slice has {count:d} reviewed acceptance tests"))
def given_reviewed_at_count(
    composition: ATReviewVerdictComposition, count: int
) -> None:
    composition.set_reviewed_at_count(count)


# --- When --------------------------------------------------------------------


@when("the designer records the AT-review verdict for the entering slice")
def when_record_approved(
    composition: ATReviewVerdictComposition,
    result_box: dict[str, object],
) -> None:
    before = composition.capture_universe()
    outcome = composition.record_verdict(
        REVIEW_OUTCOME_BY_PHRASE["approved the entering slice's AT set"]
    )
    after = composition.capture_universe()
    assert_state_delta(
        before=before,
        after=after,
        universe={"ledger.verdict_count", "ledger.prior_records"},
        expected={
            "ledger.verdict_count": set_to(1),
            "ledger.prior_records": unchanged(),
        },
    )
    result_box["outcome"] = outcome


@when("the designer completes the AT-review for the entering slice")
def when_complete_revision_review(
    composition: ATReviewVerdictComposition,
    result_box: dict[str, object],
) -> None:
    before = composition.capture_universe()
    outcome = composition.record_verdict(
        REVIEW_OUTCOME_BY_PHRASE["asked the entering slice for revision"]
    )
    after = composition.capture_universe()
    assert_state_delta(
        before=before,
        after=after,
        universe={"ledger.verdict_count", "ledger.prior_records"},
        expected={
            "ledger.verdict_count": unchanged(),
            "ledger.prior_records": unchanged(),
        },
    )
    result_box["outcome"] = outcome


@when("the designer records the AT-review verdict a second time for the slice")
def when_record_approved_again(
    composition: ATReviewVerdictComposition,
    result_box: dict[str, object],
) -> None:
    before = composition.capture_universe()
    outcome = composition.record_verdict(
        REVIEW_OUTCOME_BY_PHRASE["approved the entering slice's AT set"]
    )
    after = composition.capture_universe()
    assert_state_delta(
        before=before,
        after=after,
        universe={"ledger.verdict_count", "ledger.prior_records"},
        expected={
            "ledger.verdict_count": set_to(2),
            "ledger.prior_records": unchanged(),
        },
    )
    result_box["outcome"] = outcome


# --- Then --------------------------------------------------------------------


@then("the ledger gains one AT-review verdict for the entering slice")
def then_one_verdict(composition: ATReviewVerdictComposition) -> None:
    assert len(composition.verdicts_for_entering_slice()) == 1


@then("the recorded verdict carries no signature field")
def then_no_signature_field(composition: ATReviewVerdictComposition) -> None:
    assert not composition.latest_verdict_carries_signature_field()


@then("no earlier ledger record is altered")
def then_no_earlier_record_altered(composition: ATReviewVerdictComposition) -> None:
    prior = composition.non_verdict_records()
    assert prior == [{"event": "ATCompletion", "slice_id": "slice-06", "phase": "G"}]


@then("the ledger gains no AT-review verdict for the entering slice")
def then_no_verdict_recorded(
    composition: ATReviewVerdictComposition,
    result_box: dict[str, object],
) -> None:
    assert composition.verdicts_for_entering_slice() == []
    outcome = result_box["outcome"]
    assert outcome.record_written is False


@then(parsers.parse("the verdict lists {count:d} reviewed test identifiers"))
def then_verdict_lists_at_ids(
    composition: ATReviewVerdictComposition, count: int
) -> None:
    recorded_ids = composition.latest_verdict_field("at_ids")
    assert isinstance(recorded_ids, list)
    assert len(recorded_ids) == count


@then("the content fingerprint matches the reviewed acceptance tests")
def then_content_hash_matches_reviewed_bodies(
    composition: ATReviewVerdictComposition,
) -> None:
    recorded_hash = composition.latest_verdict_field("at_content_hash")
    assert recorded_hash == composition.reviewed_content_hash


@then("the ledger holds two AT-review verdicts for the entering slice")
def then_two_verdicts(composition: ATReviewVerdictComposition) -> None:
    assert len(composition.verdicts_for_entering_slice()) == 2


@then("the second recorded verdict is the one a later gate would trust")
def then_latest_verdict_is_the_second(
    composition: ATReviewVerdictComposition,
) -> None:
    verdicts = composition.verdicts_for_entering_slice()
    # The gate reads the LATEST verdict; assert the latest record's verdict
    # field matches the last written record.
    assert composition.latest_verdict_field("verdict") == verdicts[-1]["verdict"]
    # Post-demotion: no HMAC to verify; content seal (at_content_hash) is the
    # tamper-evidence. Assert the latest record carries the seal.
    assert bool(composition.latest_verdict_field("at_content_hash"))
