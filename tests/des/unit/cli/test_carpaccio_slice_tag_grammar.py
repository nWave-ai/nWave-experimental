"""Regression: the carpaccio slice-id VALIDATOR and the tag EXTRACTOR must accept
the SAME grammar (sister Tsunami Q-31, 2026-06-26).

A ``slice-05b`` id is validator-VALID (``_SLICE_ID_RE`` accepts the letter suffix),
but the old extractor ``@(slice-\\d+)\\b`` could not extract ``@slice-05b`` -- the
``\\b`` between ``\\d`` and a letter is no boundary, so the whole match failed -- and
the gate emitted a SILENT ``no-scenarios-for-slice`` on a valid id. The two
grammars must agree, or a valid slice id silently produces zero scenarios.
"""

from __future__ import annotations

import pytest

from des.cli.carpaccio_format import _SLICE_ID_RE, _SLICE_TAG_RE


@pytest.mark.parametrize(
    "slice_id", ["slice-01", "slice-12", "slice-100", "slice-05b", "slice-12a"]
)
def test_validator_and_extractor_agree_on_grammar(slice_id: str) -> None:
    # the validator accepts the id ...
    assert _SLICE_ID_RE.match(slice_id), f"{slice_id!r} should be a valid slice id"
    # ... and the extractor must extract that SAME id from a tag line.
    assert _SLICE_TAG_RE.findall(f"@{slice_id} @coupled") == [slice_id]


def test_letter_suffix_id_is_extractable_the_q31_case() -> None:
    # the exact Q-31 case: @slice-05b was silently un-extractable before the fix.
    assert _SLICE_TAG_RE.findall("@slice-05b") == ["slice-05b"]


def test_digit_only_id_unaffected() -> None:
    # backward-compat: the canonical digit-only id still extracts as before.
    assert _SLICE_TAG_RE.findall("@slice-07 carries scenarios") == ["slice-07"]
