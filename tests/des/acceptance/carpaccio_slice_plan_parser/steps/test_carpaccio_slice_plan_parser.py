"""Step definitions: one tolerant slice-plan parser shared by entry gate + hook.

C10 of consolidation-for-wider-beta-testing. Layer 3 (FS / module-port
acceptance). Example-only, no PBT machinery (Mandate 9/11).

The two real parsers are driven through their public entry points over hermetic
feature-delta texts crafted under pytest ``tmp_path`` -- never this repo's own
deltas. No personal-hook home-directory path is read (the hermeticity guard at
tests/meta/test_acceptance_hermeticity.py).

Step bodies delegate to ``ParserComposition``; no inline parse logic
(Mandate-15 criterion 3) -- each body is a typed lookup plus a composition call.

Regression contract: AC-1/2/3 FAIL at HEAD and PASS once C10's tolerant
``parse_slice_plan_rows`` lands and both paths delegate to it:
  AC-1 -- the CLI entry-gate parser raises ``MalformedInput`` "must have 5
          columns" on the 3-column plan while the hook parser accepts it; the
          two disagree -> the equality assertion reds for the RIGHT reason.
  AC-2 -- the escaped ``\\|`` is split as a column boundary -> the value cell is
          truncated / the row miscounted.
  AC-3 -- the H3 heading yields a missing slice-plan section.
AC-4 is a live-green preservation guard: the 5-column H2 plan the shipped deltas
use already parses; the fix must keep it parsing the same slice-ids.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import ParserComposition, ParseResult
from .domain_types import FeatureId, ParseOutcome, ParserUnderTest, SliceId


scenarios("../slice-01-carpaccio-slice-plan-parser.feature")


_FEATURE_ID = FeatureId("carpaccio-parser-demo")


# A 3-column slice plan (Slice | Value statement | Status) under an H2 heading.
# The CLI entry-gate parser rejects this at HEAD (requires exactly 5 columns);
# the hook parser accepts it (len(cells) >= 3) -- the divergence AC-1 pins.
_DELTA_3COL = """\
# Feature Delta: carpaccio parser demo

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status |
|-------|-----------------|--------|
| slice-01 | The first slice ships an observable user outcome end to end. | pending |
| slice-02 | The second slice extends the first with the next observable outcome. | pending |
"""


# A slice plan whose value cell carries a GFM-escaped pipe (`\\|`). At HEAD the
# raw-`|` split treats the escape as a column boundary -> the row is miscounted
# and the value truncated. The gold sample uses a multi-clause value statement
# so the escaped pipe sits mid-cell where a naive split visibly corrupts it.
_DELTA_ESCAPED_PIPE = """\
# Feature Delta: carpaccio parser demo

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|-------|-----------------|--------|------------|---------------|
| slice-01 | The slice supports the on-call \\| off-call routing toggle as one observable outcome. | pending | | Single slice. |
"""


# A 3-column slice plan under an H3 heading. At HEAD both parsers key on an
# H2-only heading regex -> the section is reported missing.
_DELTA_H3_HEADING = """\
# Feature Delta: carpaccio parser demo

### Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status |
|-------|-----------------|--------|
| slice-01 | The first slice ships an observable user outcome end to end. | pending |
| slice-02 | The second slice extends the first with the next observable outcome. | pending |
"""


# A 5-column slice plan under an H2 heading -- the format the shipped
# feature-deltas use. The CLI entry-gate parser already parses this at HEAD;
# AC-4 pins that the consolidation keeps it parsing the same slice-ids.
_DELTA_5COL = """\
# Feature Delta: carpaccio parser demo

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|-------|-----------------|--------|------------|---------------|
| slice-01 | The first slice ships an observable user outcome end to end. | pending | | First slice. |
| slice-02 | The second slice extends the first with the next observable outcome. | pending | | Second slice. |
"""


_PARSER_BY_PHRASE = {
    "carpaccio entry-gate parser": ParserUnderTest.ENTRY_GATE,
    "subagent-stop hook parser": ParserUnderTest.EXIT_HOOK,
}


def _slice_id_set(phrase: str) -> tuple[SliceId, ...]:
    return tuple(SliceId(token.strip()) for token in phrase.split(","))


@pytest.fixture
def composition(tmp_path: Path) -> ParserComposition:
    """Production-wired composition root over a tmp_path repository."""
    return ParserComposition(repo_dir=tmp_path / "repo")


@pytest.fixture
def results() -> dict[ParserUnderTest, ParseResult]:
    """Carrier for each driven parser's observable result."""
    return {}


# --- Given -------------------------------------------------------------------


@given(
    'a feature-delta whose slice plan is a 3-column table with columns "Slice", '
    '"Value statement" and "Status"'
)
def given_3col_delta(composition: ParserComposition) -> None:
    composition.write_feature_delta(_FEATURE_ID, _DELTA_3COL)


@given(
    "a feature-delta whose slice plan has a value cell containing a GFM-escaped pipe"
)
def given_escaped_pipe_delta(composition: ParserComposition) -> None:
    composition.write_feature_delta(_FEATURE_ID, _DELTA_ESCAPED_PIPE)


@given('a feature-delta whose slice plan sits under a level-3 "Slice Plan" heading')
def given_h3_delta(composition: ParserComposition) -> None:
    composition.write_feature_delta(_FEATURE_ID, _DELTA_H3_HEADING)


@given(
    "a feature-delta whose slice plan is a 5-column table under a level-2 "
    '"Slice Plan" heading'
)
def given_5col_delta(composition: ParserComposition) -> None:
    composition.write_feature_delta(_FEATURE_ID, _DELTA_5COL)


@given(parsers.parse('the plan declares slices "{slice_a}" and "{slice_b}"'))
def given_declares_two_slices(slice_a: str, slice_b: str) -> None:
    # Documents the precondition declared in the gold-sample delta text above;
    # the rows are already written by the delta-authoring Given. No mutation.
    assert {slice_a, slice_b} == {"slice-01", "slice-02"}


@given(
    parsers.parse(
        'the plan declares slice "{slice_id}" with a value statement that '
        "mentions a piped alternative"
    )
)
def given_declares_one_piped_slice(slice_id: str) -> None:
    assert slice_id == "slice-01"


# --- When --------------------------------------------------------------------


@when(
    "the carpaccio entry-gate parser and the subagent-stop hook parser each read the plan"
)
def when_both_parsers_read(
    composition: ParserComposition,
    results: dict[ParserUnderTest, ParseResult],
) -> None:
    results[ParserUnderTest.ENTRY_GATE] = composition.parse_with(
        ParserUnderTest.ENTRY_GATE
    )
    results[ParserUnderTest.EXIT_HOOK] = composition.parse_with(
        ParserUnderTest.EXIT_HOOK
    )


@when("the shared slice-plan parser reads the plan")
def when_shared_parser_reads(
    composition: ParserComposition,
    results: dict[ParserUnderTest, ParseResult],
) -> None:
    # The shared tolerant parser is the one both paths delegate to; we observe it
    # through the carpaccio entry-gate public entry point (the strict surface at
    # HEAD), which the fix routes through the tolerant parser.
    results[ParserUnderTest.ENTRY_GATE] = composition.parse_with(
        ParserUnderTest.ENTRY_GATE
    )


@when("the carpaccio entry-gate parser reads the plan")
def when_entry_gate_reads(
    composition: ParserComposition,
    results: dict[ParserUnderTest, ParseResult],
) -> None:
    results[ParserUnderTest.ENTRY_GATE] = composition.parse_with(
        ParserUnderTest.ENTRY_GATE
    )


# --- Then --------------------------------------------------------------------


@then(parsers.parse('both parsers extract the slice-id set "{slice_set}"'))
def then_both_extract_set(
    results: dict[ParserUnderTest, ParseResult], slice_set: str
) -> None:
    expected = _slice_id_set(slice_set)
    entry = results[ParserUnderTest.ENTRY_GATE]
    hook = results[ParserUnderTest.EXIT_HOOK]
    assert entry.slice_ids == expected, (
        "entry-gate parser must extract "
        f"{expected!r}, got outcome={entry.outcome.value} ids={entry.slice_ids!r}"
    )
    assert hook.slice_ids == expected, (
        "hook parser must extract "
        f"{expected!r}, got outcome={hook.outcome.value} ids={hook.slice_ids!r}"
    )
    assert entry.slice_ids == hook.slice_ids, (
        "the entry gate and the hook must agree on the SAME slice-id set "
        f"(entry={entry.slice_ids!r} hook={hook.slice_ids!r})"
    )


@then("neither parser rejects the 3-column plan")
def then_neither_rejects(results: dict[ParserUnderTest, ParseResult]) -> None:
    for parser, result in results.items():
        assert result.outcome is ParseOutcome.PARSED, (
            f"{parser.value} must parse the 3-column plan, got {result.outcome.value}"
        )


@then(
    parsers.parse(
        'the parser extracts slice-id "{slice_id}" with its full value statement'
    )
)
def then_extracts_full_value(
    results: dict[ParserUnderTest, ParseResult], slice_id: str
) -> None:
    entry = results[ParserUnderTest.ENTRY_GATE]
    sid = SliceId(slice_id)
    assert entry.outcome is ParseOutcome.PARSED, (
        f"the parser must parse the escaped-pipe plan, got {entry.outcome.value}"
    )
    assert sid in entry.slice_ids, f"slice-id {slice_id!r} must be extracted"
    value = entry.value_for.get(sid, "")
    assert "on-call" in value and "off-call" in value, (
        "the full value statement (both sides of the escaped pipe) must survive; "
        f"got value={value!r}"
    )


@then("the escaped pipe is treated as literal text, not a column boundary")
def then_escaped_pipe_literal(
    results: dict[ParserUnderTest, ParseResult],
) -> None:
    entry = results[ParserUnderTest.ENTRY_GATE]
    value = entry.value_for.get(SliceId("slice-01"), "")
    assert "|" in value, (
        "the escaped pipe must reappear as a literal '|' in the value cell, "
        f"not consumed as a column boundary; got value={value!r}"
    )


@then(parsers.parse('the parser extracts the slice-id set "{slice_set}"'))
def then_parser_extracts_set(
    results: dict[ParserUnderTest, ParseResult], slice_set: str
) -> None:
    entry = results[ParserUnderTest.ENTRY_GATE]
    expected = _slice_id_set(slice_set)
    assert entry.slice_ids == expected, (
        f"the parser must extract {expected!r}, "
        f"got outcome={entry.outcome.value} ids={entry.slice_ids!r}"
    )


@then("the parser does not report the slice-plan section as missing")
def then_not_section_missing(
    results: dict[ParserUnderTest, ParseResult],
) -> None:
    entry = results[ParserUnderTest.ENTRY_GATE]
    assert entry.outcome is not ParseOutcome.SECTION_MISSING, (
        "the parser must find the slice-plan section under the level-3 heading, "
        "not report it missing"
    )
