# @feature-unified-event-store
"""Tests for `LegacyEnvelopeNormalizer` (unified-event-store slice-03, D80
Mikado node, `docs/mikado/EXECUTION-SSOT-des-optimization.md` line 2608).

Outcome anchor (feature-delta.md [REF] Slice Plan, slice-03): "As a
cross-cutting query caller, I get one merged view across legacy and unified
records with an honest could-not-verify count, never a silent undercount."
This file covers the LEGACY half of that merge -- DD-10's compatibility
overlay over the 3,415 frozen pre-cutover records.

CONTRACT_SHAPE: pure-function
Universe: `LegacyEnvelopeNormalizer.normalize()`'s return value (the overlay
fields it adds) and its non-mutation guarantee over the input mapping. The
module under test does no I/O -- every fixture here is a plain in-memory
dict, matching the measured legacy record shapes (feature-delta.md
"Event-kind inventory", dominant shape
`{event, feature_id, record_hash, seq, slice_id, timestamp}`, 33 distinct
key-shapes total) -- there is nothing to isolate on disk.

RED at HEAD: `LegacyEnvelopeNormalizer` is a DISTILL-authored scaffold
(`__SCAFFOLD__ = True`) whose `normalize()` raises a bare `AssertionError`.
Every test below targets the FINAL contract (DD-10's three-field overlay,
non-mutation, non-rewrite of record_hash/seq) -- none of it is
scaffold-aware -- so each fails TODAY because the scaffold's `AssertionError`
propagates out uncaught. DELIVER makes these green by implementing the real
behaviour; this file is never rewritten to do so.
"""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from des.domain.legacy_envelope_normalizer import LegacyEnvelopeNormalizer


# The dominant measured legacy shape (feature-delta.md "Event-kind
# inventory": 2,387 of 3,415 records carry exactly these six keys). Used as
# the canonical example fixture; PBT tests below vary the shape itself so the
# law is not pinned to this one example alone.
_DOMINANT_SHAPE_RECORD: dict[str, Any] = {
    "event": "SliceCommitVerified",
    "feature_id": "unified-event-store",
    "record_hash": "deadbeefcafef00d",
    "seq": 511,
    "slice_id": "slice-02",
    "timestamp": "2026-07-29T18:00:00Z",
}

# A minority measured legacy shape (e.g. a record with NO kind field at all --
# feature-delta.md notes "2 records carry no kind field at all"). Used to
# prove the overlay does not depend on `event` being present.
_NO_KIND_RECORD: dict[str, Any] = {
    "record_hash": "0011223344556677",
    "seq": 1,
}

# Arbitrary JSON-scalar values, for PBT over the space of legacy record
# shapes -- keeps the fixtures hermetic (in-memory dicts) while varying both
# the KEY SET and the VALUE TYPES a real legacy record might carry.
_JSON_SCALAR = st.one_of(
    st.text(max_size=20),
    st.integers(),
    st.booleans(),
    st.none(),
)
_LEGACY_RECORD_SHAPE = st.dictionaries(
    keys=st.text(
        alphabet=st.characters(
            whitelist_categories=("Ll", "Lu", "Nd"), max_codepoint=127
        ),
        min_size=1,
        max_size=15,
    ),
    values=_JSON_SCALAR,
    max_size=8,
)


class TestNormalizeAppliesTheThreeFieldOverlay:
    """DD-10: every legacy record normalizes to scope=feature,
    determination=measured, envelope_generation=legacy -- regardless of what
    other fields it carries."""

    def test_dominant_shape_record_gets_the_full_overlay(self):
        # covers: R18
        result = LegacyEnvelopeNormalizer.normalize(_DOMINANT_SHAPE_RECORD)

        assert result["scope"] == "feature"
        assert result["determination"] == "measured"
        assert result["envelope_generation"] == "legacy"

    def test_no_kind_field_record_still_gets_the_full_overlay(self):
        """A legacy record missing its `event`/kind field entirely (2 of
        3,415 measured records) must not be treated as a special case that
        skips the overlay -- the overlay is unconditional over ANY legacy
        record."""
        # covers: R18
        result = LegacyEnvelopeNormalizer.normalize(_NO_KIND_RECORD)

        assert result["scope"] == "feature"
        assert result["determination"] == "measured"
        assert result["envelope_generation"] == "legacy"

    def test_empty_record_still_gets_the_full_overlay(self):
        """The overlay is TOTAL -- even a degenerate empty legacy record
        (no keys at all) gets normalized rather than raising."""
        # covers: R18
        result = LegacyEnvelopeNormalizer.normalize({})

        assert result["scope"] == "feature"
        assert result["determination"] == "measured"
        assert result["envelope_generation"] == "legacy"

    @given(record=_LEGACY_RECORD_SHAPE)
    def test_normalize_is_total_over_any_legacy_record_shape(self, record):
        """CONTRACT_SHAPE: pure-function -- for ANY legacy record shape (33
        distinct key-shapes measured in production, feature-delta.md), the
        three-field overlay is applied unconditionally. Layer-1 domain pure
        function -> PBT full (Mandate 9), not example-pinned."""
        # covers: R18
        result = LegacyEnvelopeNormalizer.normalize(record)

        assert result["scope"] == "feature"
        assert result["determination"] == "measured"
        assert result["envelope_generation"] == "legacy"


class TestNormalizeNeverRewritesTheFrozenRecord:
    """DD-10: the compat-reader NEVER physically rewrites a legacy record --
    rewriting would recompute record_hash over _HASHED_FIELDS and destroy the
    existing tamper-evidence chain for every one of the 3,415 records. This
    is the node's binding constraint, not an implementation preference."""

    def test_record_hash_is_preserved_byte_identical(self):
        # covers: R19
        result = LegacyEnvelopeNormalizer.normalize(_DOMINANT_SHAPE_RECORD)

        assert result["record_hash"] == _DOMINANT_SHAPE_RECORD["record_hash"]

    def test_seq_is_preserved_unchanged(self):
        # covers: R19
        result = LegacyEnvelopeNormalizer.normalize(_DOMINANT_SHAPE_RECORD)

        assert result["seq"] == _DOMINANT_SHAPE_RECORD["seq"]

    def test_every_original_field_survives_unchanged_in_the_result(self):
        # covers: R19
        result = LegacyEnvelopeNormalizer.normalize(_DOMINANT_SHAPE_RECORD)

        for key, value in _DOMINANT_SHAPE_RECORD.items():
            assert result[key] == value, (
                f"original field {key!r} changed during normalize() -- "
                "legacy records are FROZEN (DD-10), the compat reader must "
                "never alter an original value"
            )

    def test_normalize_does_not_mutate_its_input_argument(self):
        """The compat reader reads a legacy record; it must never mutate the
        caller's dict in place -- a caller that iterates the same legacy
        corpus twice (e.g. re-running a query) must see the SAME input on
        the second pass."""
        # covers: R19
        original = dict(_DOMINANT_SHAPE_RECORD)
        before = dict(original)

        LegacyEnvelopeNormalizer.normalize(original)

        assert original == before, (
            "normalize() mutated its input argument in place -- legacy "
            f"records are FROZEN (DD-10); before={before!r} after={original!r}"
        )

    @given(record=_LEGACY_RECORD_SHAPE)
    def test_result_is_a_new_object_not_the_same_dict_instance(self, record):
        """A caller that holds the ORIGINAL legacy record (e.g. to compute
        its own record_hash independently) must never receive back the same
        mutable object the normalizer was given -- aliasing would let a
        downstream caller's later edit silently corrupt the legacy corpus."""
        # covers: R19
        result = LegacyEnvelopeNormalizer.normalize(record)

        assert result is not record


class TestNormalizeOverlayWinsOverAnyPreExistingConflictingValue:
    """Defensive law: a legacy record predates DD-5's scope discriminator
    entirely (Correction 1/DD-10), so it should never carry a conflicting
    scope/determination/envelope_generation value in production -- but the
    normalizer must never TRUST that assumption blindly. If a malformed or
    already-partially-migrated record arrives carrying a stray value under
    one of these three keys, the DD-10 overlay must win, never silently
    preserve the untrusted pre-existing value."""

    def test_overlay_wins_over_a_stray_pre_existing_scope_value(self):
        # covers: R18
        record = dict(_DOMINANT_SHAPE_RECORD, scope="nodes")  # untrusted typo

        result = LegacyEnvelopeNormalizer.normalize(record)

        assert result["scope"] == "feature"

    def test_overlay_wins_over_a_stray_pre_existing_determination_value(self):
        # covers: R18
        record = dict(_DOMINANT_SHAPE_RECORD, determination="could_not_verify")

        result = LegacyEnvelopeNormalizer.normalize(record)

        assert result["determination"] == "measured"

    def test_overlay_wins_over_a_stray_pre_existing_envelope_generation_value(self):
        # covers: R18
        record = dict(_DOMINANT_SHAPE_RECORD, envelope_generation="unified")

        result = LegacyEnvelopeNormalizer.normalize(record)

        assert result["envelope_generation"] == "legacy"


class TestNormalizeRefusesANonMappingInput:
    """`normalize()`'s declared parameter type is `Mapping[str, Any]` -- a
    caller passing something that is not mapping-shaped (e.g. a bare list, or
    None) gets a clear, typed refusal rather than an opaque `AttributeError`
    deep inside the overlay logic."""

    @pytest.mark.parametrize("not_a_mapping", [None, [], "a-string", 42])
    def test_a_non_mapping_argument_is_rejected_not_silently_accepted(
        self, not_a_mapping
    ):
        # covers: R18
        with pytest.raises((TypeError, AttributeError)):
            LegacyEnvelopeNormalizer.normalize(not_a_mapping)
