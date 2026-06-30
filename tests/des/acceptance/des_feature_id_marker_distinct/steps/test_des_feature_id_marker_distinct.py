"""Step definitions: the carpaccio feature-id is its own DES-FEATURE-ID marker (C5, AD-61).

Binds the slice-01 ``.feature`` scenarios to the production-wired
``FeatureIdResolutionComposition``. Layer 1-3 acceptance.

Paradigm (Mandate 9/11): example-only, no PBT machinery. The four ACs form a
finite, enumerable closed set of identity arrangements (feature-id only /
both-markers / project-id only), so a small set of explicit examples is the
correct paradigm; sad paths (the missing-feature-id RED path) are enumerated
explicitly, never PBT-generated.

Mandate-8 (state-delta): AC-4 asserts the project_id role is UNCHANGED by adding
a feature-id marker -- a preservation observation. It asserts via
``assert_state_delta`` over a port-exposed Universe (the two parsed identity
fields) that project_id is preserved at "proj-Y" while feature_id is the only
field that may change. AC-1 / AC-2 / AC-3 assert single resolved-value outcomes
directly (the observable is one identity string).

Step bodies delegate to the composition (Mandate-12 criterion 3): each body is a
typed lookup plus a single composition call, no inline business logic / control
flow.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import FeatureIdResolutionComposition, ParseObservation


scenarios("../slice-01-des-feature-id-marker-distinct.feature")


@pytest.fixture
def composition() -> FeatureIdResolutionComposition:
    """Production-wired composition root driving the REAL parser + carpaccio resolution."""
    return FeatureIdResolutionComposition()


# --- Given -------------------------------------------------------------------


@given(
    parsers.parse(
        'a dispatch prompt carrying the distinct feature-id marker "{feature_id}"'
    )
)
def given_feature_id_only(
    composition: FeatureIdResolutionComposition, feature_id: str
) -> None:
    composition.given_markers(feature_id=feature_id)


@given(
    parsers.parse(
        'a carpaccio dispatch prompt carrying both a feature-id marker "{feature_id}" '
        'and a project-id marker "{project_id}"'
    )
)
def given_both_markers_carpaccio(
    composition: FeatureIdResolutionComposition, feature_id: str, project_id: str
) -> None:
    composition.given_markers(feature_id=feature_id, project_id=project_id)


@given(
    parsers.parse(
        'a carpaccio dispatch prompt carrying only a project-id marker "{project_id}"'
    )
)
def given_project_id_only_carpaccio(
    composition: FeatureIdResolutionComposition, project_id: str
) -> None:
    composition.given_markers(project_id=project_id)


@given(
    parsers.parse(
        'a dispatch prompt carrying both a feature-id marker "{feature_id}" '
        'and a project-id marker "{project_id}"'
    )
)
def given_both_markers_parse(
    composition: FeatureIdResolutionComposition, feature_id: str, project_id: str
) -> None:
    composition.given_markers(feature_id=feature_id, project_id=project_id)


# --- When --------------------------------------------------------------------


@when("the DES marker parser parses the dispatch prompt", target_fixture="parse_obs")
def when_parse(composition: FeatureIdResolutionComposition) -> ParseObservation:
    return composition.parse_dispatch()


@when(
    "the carpaccio dispatch resolution runs over the dispatch prompt",
    target_fixture="resolved_feature_id",
)
def when_resolve(
    composition: FeatureIdResolutionComposition,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> str:
    return composition.resolve_carpaccio_feature_id(monkeypatch, tmp_path)


# --- Then --------------------------------------------------------------------


@then(parsers.parse('the parsed feature id is "{expected}"'))
def then_parsed_feature_id(parse_obs: ParseObservation, expected: str) -> None:
    assert parse_obs.feature_id == expected, (
        f"expected parsed feature_id == {expected!r}, got {parse_obs.feature_id!r} "
        "(active-RED at HEAD: DesMarkers has no DES-FEATURE-ID pattern/field yet)"
    )


@then(parsers.parse('the resolved carpaccio feature id is "{expected}"'))
def then_resolved_feature_id(resolved_feature_id: str, expected: str) -> None:
    assert resolved_feature_id == expected, (
        f"expected the carpaccio resolution to resolve feature-id == {expected!r}, "
        f"got {resolved_feature_id!r} (active-RED at HEAD: the resolution overloads "
        "markers.project_id instead of preferring markers.feature_id)"
    )


@then(parsers.parse('the parsed project id is "{expected}"'))
def then_parsed_project_id(
    composition: FeatureIdResolutionComposition, expected: str
) -> None:
    # Mandate-8: a preservation assertion over a port-exposed Universe. The
    # perturbation is adding a DES-FEATURE-ID marker; project_id is unchanged()
    # across that delta and remains the expected value.
    from tests.common.state_delta import assert_state_delta, unchanged

    before, after = composition.project_id_preservation_delta()
    assert before["project_id"] == expected, (
        f"the project-id-only baseline must parse project_id == {expected!r}, "
        f"got {before['project_id']!r}"
    )
    assert_state_delta(
        before=before,
        after=after,
        universe={"project_id"},
        expected={"project_id": unchanged()},
    )
