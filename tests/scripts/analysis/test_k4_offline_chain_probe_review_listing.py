"""`offline_chain_probe.parse_review_listing` refuses; it never skips.

The defect this file pins: `stage_score` read `REVIEW-THESE.txt` with
`text.split()`, whitespace-splitting the WHOLE file including the two lines of
instruction prose `blind_review.seal` writes at the top. The first "id" it tried
to score was the word `One`, and the chain died at `deliveries/One` with six
correct ids sitting three lines below. The seal was right; the reader was not.

The repair is NOT "skip the prose". A reader that silently drops what it does
not understand converts a drifted listing into a review of FEWER deliveries that
still reports PASS -- the same shape as an axis present with a null ratio passing
as green, which is the class this probe exists to catch. So every test below that
feeds a malformed file asserts a REFUSAL, never a quiet subset.
"""

from __future__ import annotations

import re

import pytest

from scripts.analysis import blind_review
from scripts.analysis.k4 import offline_chain_probe


def _sealed_listing(ids: list[str]) -> str:
    """Byte-for-byte the header `blind_review.seal` writes, so this fixture
    cannot pass while the real file fails."""
    return (
        "One delivery per line, in no meaningful order.\n"
        "Score each into a JSON object keyed by exactly these ids.\n\n"
        + "\n".join(ids)
        + "\n"
    )


def _real_ids(count: int) -> list[str]:
    """Ids from the real issuer, never hand-typed hex: if `opaque_id` ever
    changes shape, this test discovers it instead of asserting a stale one."""
    return [
        blind_review.opaque_id(f"session-{i}", "0123456789abcdef") for i in range(count)
    ]


def test_the_writers_own_output_parses_to_exactly_its_ids() -> None:
    ids = _real_ids(6)
    assert offline_chain_probe.parse_review_listing(_sealed_listing(ids)) == ids


def test_the_header_prose_is_never_returned_as_an_id() -> None:
    """The regression itself: `One`, `delivery`, `per` are not deliveries."""
    parsed = offline_chain_probe.parse_review_listing(_sealed_listing(_real_ids(2)))
    assert "One" not in parsed
    assert all(re.fullmatch(r"[0-9a-f]{12}", token) for token in parsed)


@pytest.mark.parametrize(
    ("name", "text"),
    [
        (
            "prose in the id block",
            "header\n\naaaaaaaaaaaa\nand one more thing\nbbbbbbbbbbbb\n",
        ),
        ("id-shaped token in the header", "aaaaaaaaaaaa\nheader\n\nbbbbbbbbbbbb\n"),
        ("uppercase hex", "header\n\nAAAAAAAAAAAA\n"),
        ("wrong length", "header\n\naaaaaaaaaaa\n"),
        ("a path instead of an id", "header\n\ndeliveries/aaaaaaaaaaaa\n"),
        ("duplicate id", "header\n\naaaaaaaaaaaa\naaaaaaaaaaaa\n"),
        ("no blank separator", "header\naaaaaaaaaaaa\n"),
        ("empty id block", "header\n\n"),
        ("empty file", ""),
    ],
)
def test_every_malformed_listing_is_refused_loudly(name: str, text: str) -> None:
    with pytest.raises(offline_chain_probe.ReviewListingError) as caught:
        offline_chain_probe.parse_review_listing(text)
    message = str(caught.value)
    assert "WHAT:" in message, name
    assert "WHY:" in message, name
    assert "HOW:" in message, name


def test_a_dropped_id_is_a_refusal_not_a_shorter_list() -> None:
    """The falsifier for the wrong repair. `skip what you do not understand`
    would return five ids here and report PASS; refusing is the whole point."""
    ids = _real_ids(6)
    corrupted = _sealed_listing(ids).replace(ids[3], "a delivery we lost", 1)
    with pytest.raises(offline_chain_probe.ReviewListingError) as caught:
        offline_chain_probe.parse_review_listing(corrupted)
    assert "a delivery we lost" in str(caught.value)
