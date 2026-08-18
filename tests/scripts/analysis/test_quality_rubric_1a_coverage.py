"""The K4 rubric must answer to the ratified quality definition, not to its own
inertia.

`docs/product/architecture/ADR-SSOT-002-canonical-delivery-model.md` Section 1a
is the single enumerated, per-item-cited quality definition ("the roadmap points
here instead of restating it"). Before this test existed, the K4 paired-quality
rubric's twelve criteria predated Section 1a, lived only as prose in
`docs/analysis/2026-08-06-k4-lane-c-output-contract.md`, and were never checked
against it -- five Section 1a items (semantic PBT, algebra-driven design,
residuality, certainty-by-construction, no-DRY/SSOT-violation) had no rubric
criterion at all, and nothing said so.

This is that standing check, pinned RED against the old shape:
`scripts/analysis/k4/quality_rubric.py` did not exist, so every assertion below
fails on import alone. GREEN requires the module to name, for every one of
Section 1a's 13 items, either a criterion that cites it or an entry in
`DELEGATED_1A` naming the instrument that measures it instead -- never silence.

Run: uv run pytest -q tests/scripts/analysis/test_quality_rubric_1a_coverage.py
"""

from __future__ import annotations

from scripts.analysis.k4 import quality_rubric as qr


def test_every_section_1a_item_is_covered_or_delegated():
    uncovered = qr.uncovered_1a_items()
    assert uncovered == set(), (
        f"Section 1a items with no citing criterion and no DELEGATED_1A entry: "
        f"{sorted(uncovered)}"
    )


def test_section_1a_items_are_the_thirteen_ratified_items():
    assert set(qr.SECTION_1A_ITEMS) == set(range(1, 14))


def test_every_criterion_key_is_contiguous_from_one():
    assert [c.key for c in qr.CRITERIA] == [
        str(n) for n in range(1, len(qr.CRITERIA) + 1)
    ]
    assert frozenset(c.key for c in qr.CRITERIA) == qr.CRITERIA_KEYS


def test_every_criterion_section_1a_reference_is_a_real_item():
    for c in qr.CRITERIA:
        for n in c.section_1a:
            assert n in qr.SECTION_1A_ITEMS, f"criterion {c.key} cites unknown item {n}"


def test_every_delegated_item_names_a_nonempty_instrument():
    for item, instrument in qr.DELEGATED_1A.items():
        assert item in qr.SECTION_1A_ITEMS
        assert isinstance(instrument, str) and instrument.strip()


def test_five_gap_items_found_before_the_fix_are_now_criterion_covered():
    """Items 5-9 had zero rubric criteria before this fix -- pin them covered
    by an actual criterion, not merely delegated, since a source-blind reader
    CAN judge them from the delivery diff."""
    cited = {n for c in qr.CRITERIA for n in c.section_1a}
    for item in (5, 6, 7, 8, 9):
        assert item in cited, f"Section 1a item {item} still has no citing criterion"


def test_blind_review_criteria_keys_are_wired_to_the_rubric_module():
    """`blind_review.py` must not hardcode its own idea of the key set --
    otherwise this module and the verdict-shape validator can drift again."""
    from scripts.analysis import blind_review as br

    assert br._CRITERIA_KEYS == qr.CRITERIA_KEYS


def test_no_criterion_leaks_nwave_or_adr_vocabulary_to_the_reviewer():
    """A source-blind reviewer sees only `dimension` and `question` -- the
    fields that end up in a reviewer prompt. Section 1a anchors are code
    metadata (`section_1a`, `notes`) and must never leak into that text: a
    verdict conditioned on "Section 1a item 10" or "DELEGATED_1A" is no
    longer shape-blind, whatever the label on the field that carries it.

    Pinned RED against 46009810d, where criterion 2's `question` named
    "Section 1a item 10" and criterion 18's named "DELEGATED_1A" outright.
    """
    leaks = qr.leaked_reviewer_vocabulary()
    assert leaks == [], f"reviewer-facing text leaks nWave/ADR vocabulary: {leaks}"


def test_every_section_1a_item_is_cited_by_at_most_one_criterion():
    """Equal weight by default: a Section 1a item cited by two scored
    criteria counts twice toward the aggregate total while every
    single-cited item counts once -- weight inflation, not a stated
    rationale. Pinned RED against 46009810d, where item 4 was cited by both
    `tests_as_specification` and `test_implementation_coupling`, and item 13
    by both `craftsmanship` and `living_documentation`.
    """
    counts = qr.citation_counts()
    over_weighted = {n: c for n, c in counts.items() if c > 1}
    assert over_weighted == {}, (
        f"Section 1a items cited by more than one criterion (weight > 1): "
        f"{over_weighted}"
    )


def test_delegated_10_and_13_are_honest_about_what_k4_actually_runs():
    """`DELEGATED_1A` naming an instrument that no K4 script actually
    invokes is not a delegation, it is a decoration. Items 10 and 13 named
    `nw-solution-architect-reviewer` and a `defects.md`/`techdebt.md`
    baseline comparison, neither of which any `scripts/analysis/k4/*.py`
    module runs at scoring time -- pinned RED against 46009810d. GREEN
    requires either an instrument this repo can show actually running in a
    K4 campaign, or an explicit "NOT MEASURED in K4" admission.
    """
    for item in (10, 13):
        instrument = qr.DELEGATED_1A[item]
        assert (
            "not measured in k4" in instrument.lower()
            or "run_acceptance.py" in instrument
        )
