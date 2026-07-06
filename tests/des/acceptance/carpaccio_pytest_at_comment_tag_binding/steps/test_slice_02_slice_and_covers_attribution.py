"""Step definitions: a pytest AT file's head-comment names its slice and spec rows.

carpaccio-pytest-at-comment-tag-binding slice-02
(EXP-carpaccio-pytest-at-comment-tag-binding-2). Layer 3 composition-root
acceptance (Mandate 13); example-only, no PBT machinery (Mandate 9/11).

Active-RED contract: ``resolve_test_file_attribution`` is a ``__SCAFFOLD__``
raising ``AssertionError`` at HEAD (``src/des/application/feature_at_files.py``).
Module top imports ONLY the stable composition + domain types -- never the
absent resolver by name -- so collection succeeds; each scenario reds AT
RUNTIME inside ``composition.resolve_attribution()`` with a semantic
``AssertionError`` (MISSING_FUNCTIONALITY), never a collection/import error
(BROKEN).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import AttributionResult, FeatureTaggedTestFilesComposition


scenarios("../slice-02-slice-and-covers-attribution.feature")

_SUBJECT_RELATIVE_PATH = "tests/test_subject.py"


def _content_for_tag(tag: str) -> str:
    return f"# {tag}\ndef test_something():\n    assert True\n"


@pytest.fixture
def composition(tmp_path: Path) -> FeatureTaggedTestFilesComposition:
    """Production-wired composition root over a tmp_path scratch repository."""
    return FeatureTaggedTestFilesComposition(repo_dir=tmp_path / "repo")


@pytest.fixture
def attribution_box() -> dict[str, AttributionResult]:
    """Carrier for the resolver's observable attribution result."""
    return {}


# --- Given -------------------------------------------------------------------


@given(
    parsers.parse(
        'a scratch repository containing a pytest test file head-tagged "{tag}"'
    )
)
def given_tagged_file(
    tag: str,
    composition: FeatureTaggedTestFilesComposition,
) -> None:
    composition.write_test_file(_SUBJECT_RELATIVE_PATH, _content_for_tag(tag))


# --- When ----------------------------------------------------------------


@when("the maintainer resolves the test file's slice and spec-row attribution")
def when_resolve_attribution(
    composition: FeatureTaggedTestFilesComposition,
    attribution_box: dict[str, AttributionResult],
) -> None:
    attribution_box["result"] = composition.resolve_attribution(_SUBJECT_RELATIVE_PATH)


# --- Then ------------------------------------------------------------------


@then(parsers.parse('the resolved attribution names slice "{slice_id}"'))
def then_names_slice(
    attribution_box: dict[str, AttributionResult], slice_id: str
) -> None:
    result = attribution_box["result"]
    assert result.names_slice(slice_id), (
        f"expected the attribution to name slice {slice_id!r}, got {result!r}"
    )


@then(parsers.parse('the resolved attribution does not name slice "{slice_id}"'))
def then_not_names_slice(
    attribution_box: dict[str, AttributionResult], slice_id: str
) -> None:
    result = attribution_box["result"]
    assert not result.names_slice(slice_id), (
        f"unexpected cross-slice attribution to {slice_id!r} (no bleed allowed), "
        f"got {result!r}"
    )


@then(parsers.parse('the resolved attribution covers spec row "{row_id}"'))
def then_covers_row(attribution_box: dict[str, AttributionResult], row_id: str) -> None:
    result = attribution_box["result"]
    assert result.covers_row(row_id), (
        f"expected the attribution to cover spec row {row_id!r}, got {result!r}"
    )


@then("the resolved attribution reports no slice attribution")
def then_no_slice_attribution(
    attribution_box: dict[str, AttributionResult],
) -> None:
    result = attribution_box["result"]
    assert result.slice_id is None, (
        f"expected no slice attribution (guardrail: absence, never a raise), "
        f"got {result!r}"
    )


@then("the resolved attribution reports no covered spec rows")
def then_no_covered_rows(attribution_box: dict[str, AttributionResult]) -> None:
    result = attribution_box["result"]
    assert result.covers == (), f"expected no covered spec rows, got {result!r}"
