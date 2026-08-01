# @feature-unified-event-store
"""Tests for `ReductionKeyDeduper` + `Aggregate` (unified-event-store
slice-03, D80 Mikado node,
`docs/mikado/EXECUTION-SSOT-des-optimization.md` line 2608).

Outcome anchor (feature-delta.md [REF] Slice Plan, slice-03): "As a
cross-cutting query caller, I get one merged view across legacy and unified
records with an honest could-not-verify count, never a silent undercount."
This file covers the DERIVED/aggregate half of that merge (DD-7, DD-8, DD-9)
plus the slice's CUTOVER CRITERION composing both halves (last test class).

CONTRACT_SHAPE: pure-function
Universe: `ReductionKeyDeduper.dedupe()`'s return value -- an `Aggregate`
whose `measured_count`/`could_not_verify_count`/`could_not_verify_reasons`
are asserted for shape (DD-9 arity: never a bare int) and for the DD-7/DD-8
reduction laws. The module under test does no I/O -- every fixture here is a
plain in-memory list of dicts, matching the measured DERIVED record shape
(feature-delta.md DD-7: `reduction_key`/`reduction_seq`/
`reduced_through_request`/`reducer_version`, plus `agent_id`) -- there is
nothing to isolate on disk.

RED at HEAD: `ReductionKeyDeduper` is a DISTILL-authored scaffold
(`__SCAFFOLD__ = True`) whose `dedupe()` raises a bare `AssertionError`.
Every test below targets the FINAL contract -- none of it is
scaffold-aware -- so each fails TODAY because the scaffold's `AssertionError`
propagates out uncaught. DELIVER makes these green by implementing the real
behaviour; this file is never rewritten to do so.
"""

from __future__ import annotations

from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from des.domain.event_store_aggregate import Aggregate, ReductionKeyDeduper
from des.domain.legacy_envelope_normalizer import LegacyEnvelopeNormalizer


def _derived_record(
    *,
    reduction_key: str,
    reduction_seq: int,
    agent_id: str | None = "agent-1",
    event: str = "SomeDerivedEvent",
) -> dict[str, Any]:
    """A minimal, measured-DERIVED-shape fixture record (DD-7 fields)."""
    return {
        "event": event,
        "reduction_key": reduction_key,
        "reduction_seq": reduction_seq,
        "reduced_through_request": "req-1",
        "reducer_version": "v1",
        "agent_id": agent_id,
    }


class TestAggregateIsNeverABareInt:
    """DD-9: the aggregate result structurally carries could_not_verify_count
    -- a caller cannot obtain a bare total. Pinned on the TYPE shape, not
    merely on one example value, so an implementation returning a bare int
    (or a dict missing the field) cannot pass by accident."""

    def test_dedupe_of_empty_input_returns_an_aggregate_not_a_bare_value(self):
        # covers: R22
        result = ReductionKeyDeduper.dedupe([])

        assert isinstance(result, Aggregate)
        assert result.measured_count == 0
        assert result.could_not_verify_count == 0
        assert result.could_not_verify_reasons == []

    def test_aggregate_has_all_three_required_attributes(self):
        # covers: R22
        result = ReductionKeyDeduper.dedupe(
            [_derived_record(reduction_key="k1", reduction_seq=1)]
        )

        # Structural presence, not merely a lucky value -- a caller reading
        # any of these three off an Aggregate instance must never raise
        # AttributeError, whatever the reduction outcome was.
        assert hasattr(result, "measured_count")
        assert hasattr(result, "could_not_verify_count")
        assert hasattr(result, "could_not_verify_reasons")
        assert isinstance(result.could_not_verify_reasons, list)

    @given(
        records=st.lists(
            st.builds(
                _derived_record,
                reduction_key=st.text(min_size=1, max_size=5),
                reduction_seq=st.integers(min_value=0, max_value=100),
                agent_id=st.one_of(st.none(), st.text(min_size=1, max_size=5)),
            ),
            max_size=10,
        )
    )
    def test_could_not_verify_count_always_equals_reasons_length(self, records):
        """CONTRACT_SHAPE: pure-function -- the DD-9 arity invariant holds
        for ANY input, not just the hand-picked examples above. Layer-1
        domain pure function -> PBT full (Mandate 9), not example-pinned."""
        # covers: R22
        result = ReductionKeyDeduper.dedupe(records)

        assert result.could_not_verify_count == len(result.could_not_verify_reasons)


class TestNullAgentIdIsDedupIneligible:
    """DD-8: reduction_key requires a non-null agent_id. A null-agent_id
    record is dedup-ineligible: never MAX'd away (i.e. never silently
    discarded as if it had competed and lost), always could_not_verify."""

    def test_single_null_agent_id_record_is_could_not_verify_not_measured(self):
        # covers: R21
        record = _derived_record(reduction_key="k1", reduction_seq=1, agent_id=None)

        result = ReductionKeyDeduper.dedupe([record])

        assert result.measured_count == 0
        assert result.could_not_verify_count == 1

    def test_null_agent_id_record_is_could_not_verify_even_with_the_highest_seq(self):
        """The defining negative case: a null-agent_id record carrying the
        NUMERICALLY HIGHEST reduction_seq in its group must still be
        could_not_verify, never silently promoted to the MAX-winner just
        because its seq value would have won a naive numeric comparison."""
        # covers: R21
        eligible = _derived_record(
            reduction_key="k1", reduction_seq=1, agent_id="agent-1"
        )
        null_agent_but_highest_seq = _derived_record(
            reduction_key="k1", reduction_seq=999, agent_id=None
        )

        result = ReductionKeyDeduper.dedupe([eligible, null_agent_but_highest_seq])

        assert result.measured_count == 1, (
            "the one eligible record must still be counted measured -- the "
            "null-agent_id record must never suppress it"
        )
        assert result.could_not_verify_count == 1

    def test_two_null_agent_id_records_sharing_a_key_are_both_could_not_verify(self):
        """Sibling-branch pin: null-agent_id records are NEVER grouped by
        reduction_key for MAX purposes -- two of them sharing the same key
        must both independently count as could_not_verify, never collapse
        into a single could_not_verify entry the way a mistaken
        group-then-count implementation might."""
        # covers: R21
        first = _derived_record(reduction_key="k1", reduction_seq=1, agent_id=None)
        second = _derived_record(reduction_key="k1", reduction_seq=2, agent_id=None)

        result = ReductionKeyDeduper.dedupe([first, second])

        assert result.measured_count == 0
        assert result.could_not_verify_count == 2

    @given(reduction_seq=st.integers(min_value=0, max_value=10_000))
    def test_null_agent_id_is_could_not_verify_for_any_reduction_seq_value(
        self, reduction_seq
    ):
        """CONTRACT_SHAPE: pure-function -- DD-8 ineligibility holds for
        EVERY possible reduction_seq value, not one hand-picked number."""
        # covers: R21
        record = _derived_record(
            reduction_key="k1", reduction_seq=reduction_seq, agent_id=None
        )

        result = ReductionKeyDeduper.dedupe([record])

        assert result.measured_count == 0
        assert result.could_not_verify_count == 1


class TestMaxReductionSeqPerKeyWins:
    """DD-7: the read rule is MAX(reduction_seq) per reduction_key -- the
    single highest-seq record in a group is the surviving measured fact;
    older duplicates are silently superseded (NOT could_not_verify -- that
    is a distinct failure class from dedup-ineligibility)."""

    def test_two_eligible_records_sharing_a_key_collapse_to_one_measured(self):
        # covers: R20
        older = _derived_record(reduction_key="k1", reduction_seq=1)
        newer = _derived_record(reduction_key="k1", reduction_seq=2)

        result = ReductionKeyDeduper.dedupe([older, newer])

        assert result.measured_count == 1, (
            "two derived records sharing one reduction_key must collapse to "
            "exactly ONE measured fact (the higher-seq winner) -- got "
            f"measured_count={result.measured_count!r}"
        )
        assert result.could_not_verify_count == 0, (
            "a superseded (lower-seq) duplicate is NOT could_not_verify -- "
            "supersession and dedup-ineligibility are distinct failure "
            f"classes; got could_not_verify_count={result.could_not_verify_count!r}"
        )

    def test_records_under_distinct_keys_are_each_independently_measured(self):
        """Sibling-branch pin: distinct reduction_keys must NOT be
        conflated into one group -- each key's winner counts separately."""
        # covers: R20
        first_key = _derived_record(reduction_key="k1", reduction_seq=1)
        second_key = _derived_record(reduction_key="k2", reduction_seq=1)

        result = ReductionKeyDeduper.dedupe([first_key, second_key])

        assert result.measured_count == 2
        assert result.could_not_verify_count == 0

    def test_input_order_does_not_affect_which_seq_wins(self):
        """The MAX rule must be order-independent -- feeding the same group
        in ascending vs descending seq order must pick the SAME winner."""
        # covers: R20
        older = _derived_record(reduction_key="k1", reduction_seq=1)
        newer = _derived_record(reduction_key="k1", reduction_seq=2)

        ascending = ReductionKeyDeduper.dedupe([older, newer])
        descending = ReductionKeyDeduper.dedupe([newer, older])

        assert ascending.measured_count == descending.measured_count == 1
        assert (
            ascending.could_not_verify_count == descending.could_not_verify_count == 0
        )

    @given(
        seqs=st.lists(st.integers(min_value=0, max_value=1_000), min_size=1, max_size=8)
    )
    def test_one_key_with_n_eligible_records_always_yields_exactly_one_measured(
        self, seqs
    ):
        """CONTRACT_SHAPE: pure-function -- for ANY non-empty group of
        eligible records sharing one key (however many, whatever their seq
        values, EXCEPT the tied-max case covered separately below), exactly
        one measured fact survives. Excludes ties by construction (distinct
        seqs) so this law is isolated from TestAmbiguousMaxIsCouldNotVerify's
        law -- the two are different rules, tested separately."""
        # covers: R20
        distinct_seqs = sorted(set(seqs))
        records = [
            _derived_record(reduction_key="k1", reduction_seq=seq)
            for seq in distinct_seqs
        ]

        result = ReductionKeyDeduper.dedupe(records)

        assert result.measured_count == 1
        assert result.could_not_verify_count == 0


class TestAmbiguousMaxIsCouldNotVerify:
    """Two eligible records sharing one reduction_key AND the same maximum
    reduction_seq is an ambiguity DD-7's rule does not resolve on its own --
    the same "never silently collapse an unproven identity" law DD-8 states
    for null agent_id, applied to a genuine tie. Silently picking one would
    reproduce exactly the collapse class DD-8 exists to prevent."""

    def test_tied_max_reduction_seq_in_one_group_is_could_not_verify(self):
        # covers: R23
        first = _derived_record(reduction_key="k1", reduction_seq=5, agent_id="agent-1")
        second = _derived_record(
            reduction_key="k1", reduction_seq=5, agent_id="agent-2"
        )

        result = ReductionKeyDeduper.dedupe([first, second])

        assert result.measured_count == 0, (
            "an ambiguous tied-max group must NOT silently promote either "
            "record to measured"
        )
        assert result.could_not_verify_count == 1, (
            "a tied-max group is one ambiguity, reported once -- got "
            f"could_not_verify_count={result.could_not_verify_count!r}"
        )

    def test_a_non_tied_record_in_a_different_key_is_unaffected_by_a_tie_elsewhere(
        self,
    ):
        """Sibling-branch pin: an ambiguity in one reduction_key's group
        must not suppress or contaminate a clean, unambiguous winner under a
        DIFFERENT key."""
        # covers: R23, R20
        tied_a = _derived_record(
            reduction_key="k1", reduction_seq=5, agent_id="agent-1"
        )
        tied_b = _derived_record(
            reduction_key="k1", reduction_seq=5, agent_id="agent-2"
        )
        clean = _derived_record(reduction_key="k2", reduction_seq=1, agent_id="agent-3")

        result = ReductionKeyDeduper.dedupe([tied_a, tied_b, clean])

        assert result.measured_count == 1
        assert result.could_not_verify_count == 1


class TestCutoverCriterionMergesLegacyAndDerivedIntoOneResult:
    """Staging Plan slice-03 cutover criterion, verbatim: "a query over a
    fixture mixing legacy and new-envelope rows returns one merged,
    correctly-tagged result." Composes BOTH slice-03 components directly
    (LegacyEnvelopeNormalizer for the legacy half, ReductionKeyDeduper for
    the derived half) -- the wiring of this composition into
    UnifiedEventStoreAdapter.read() is DELIVER's job for this slice; this
    test proves the two pure functions compose to the correct merged answer
    at the domain layer, which is the property the cutover criterion names."""

    def test_a_fixture_mixing_legacy_and_derived_rows_yields_one_correct_aggregate(
        self,
    ):
        # covers: R24
        legacy_rows = [
            {
                "event": "SliceCommitVerified",
                "feature_id": "unified-event-store",
                "record_hash": "hash-1",
                "seq": 1,
            },
            {
                "event": "ATReviewVerdict",
                "feature_id": "unified-event-store",
                "record_hash": "hash-2",
                "seq": 2,
            },
        ]
        derived_rows = [
            _derived_record(reduction_key="d1", reduction_seq=1),
            _derived_record(reduction_key="d1", reduction_seq=2),  # supersedes above
            _derived_record(reduction_key="d2", reduction_seq=1, agent_id=None),
        ]

        normalized_legacy = [
            LegacyEnvelopeNormalizer.normalize(row) for row in legacy_rows
        ]
        derived_aggregate = ReductionKeyDeduper.dedupe(derived_rows)

        # The merged view: every normalized legacy row is independently
        # measured (legacy records predate reduction_key entirely -- DD-7
        # does not apply to them), plus whatever the derived-side aggregate
        # measured/could-not-verified.
        merged_measured_count = (
            len(normalized_legacy) + derived_aggregate.measured_count
        )
        merged_could_not_verify_count = derived_aggregate.could_not_verify_count

        assert all(row["envelope_generation"] == "legacy" for row in normalized_legacy)
        assert all(row["determination"] == "measured" for row in normalized_legacy)
        assert merged_measured_count == 3, (
            "expected 2 normalized legacy rows + 1 surviving derived winner "
            f"(k1 max-seq) -- got {merged_measured_count!r}"
        )
        assert merged_could_not_verify_count == 1, (
            "expected exactly the 1 null-agent_id derived row -- got "
            f"{merged_could_not_verify_count!r}"
        )

    def test_legacy_only_fixture_never_contributes_a_could_not_verify_row(self):
        """Sibling-branch pin: a fixture with ONLY legacy rows (no derived
        rows at all) must yield could_not_verify_count == 0 -- legacy rows
        have no reduction_key/agent_id concept, so DD-8 ineligibility can
        never apply to them."""
        # covers: R24
        legacy_rows = [
            {"event": "CarpaccioGateCleared", "record_hash": "hash-3", "seq": 3}
        ]

        normalized_legacy = [
            LegacyEnvelopeNormalizer.normalize(row) for row in legacy_rows
        ]
        derived_aggregate = ReductionKeyDeduper.dedupe([])

        assert len(normalized_legacy) == 1
        assert derived_aggregate.measured_count == 0
        assert derived_aggregate.could_not_verify_count == 0
