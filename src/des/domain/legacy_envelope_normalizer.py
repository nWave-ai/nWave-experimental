"""LegacyEnvelopeNormalizer -- DD-10 compatibility reader over the 3,415
frozen pre-cutover records (unified-event-store slice-03).

`normalize()` is implemented (DELIVER slice-03): pure and total, it never
raises for a well-formed Mapping and never mutates its input.

Design contract (feature-delta.md DD-10 + [REF] Architecture & Contract
Tests, `test_legacy_envelope_normalizer.py`): the 3,415 measured pre-cutover
records (33 distinct key-shapes, dominant shape
`{event, feature_id, record_hash, seq, slice_id, timestamp}`) are FROZEN --
they are read through this normalizer, never physically rewritten, because
rewriting would recompute `record_hash` over `_HASHED_FIELDS` and destroy the
existing tamper-evidence chain for every one of those records.

`normalize()` is a PURE, TOTAL function: for ANY legacy record shape it
returns a NEW dict overlaying exactly three compatibility fields --
`scope="feature"`, `determination="measured"`, `envelope_generation="legacy"`
-- while leaving every original key (including `record_hash` and `seq`)
byte-identical. It never mutates its input. A legacy record predates DD-5's
`scope` discriminator entirely, so this overlay always applies; it is not a
merge negotiation with a pre-existing value.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


__all__ = ["LegacyEnvelopeNormalizer"]


class LegacyEnvelopeNormalizer:
    """Pure, side-effect-free compatibility overlay for frozen legacy records.

    No constructor state -- every method is a pure function of its argument,
    so a caller may use the class as a plain namespace (`normalize` is a
    `staticmethod`) or instantiate it; both work identically because there is
    no instance state to diverge.
    """

    @staticmethod
    def normalize(raw_record: Mapping[str, Any]) -> dict[str, Any]:
        """Return a NEW dict: `raw_record`'s fields, plus the DD-10 overlay."""
        if not isinstance(raw_record, Mapping):
            raise TypeError(
                f"LegacyEnvelopeNormalizer.normalize() requires a Mapping, "
                f"got {type(raw_record).__name__!r}"
            )
        return {
            **raw_record,
            "scope": "feature",
            "determination": "measured",
            "envelope_generation": "legacy",
        }
