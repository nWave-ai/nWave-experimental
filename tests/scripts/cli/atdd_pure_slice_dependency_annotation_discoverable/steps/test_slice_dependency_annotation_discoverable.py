"""Step definitions: the dependency token is discoverable at the point of
authoring a Slice Plan.

`docs/feature/parallel-by-default-slice-plan/feature-delta.md` slice-02.

No production driving port exists for "is this documented" (same posture as
AT-d in ``tests/des/unit/cli/test_carpaccio_ceiling_15_and_coupled_affordance.py``
for the sibling ``@coupled`` affordance) -- step bodies delegate to
``SliceDependencyDiscoverabilityComposition``, which reads the real
authoring-surface files (or a fabricated fixture, for the negative
scenarios) and extracts the section-scoped vocabulary text; no inline
business logic in step bodies (Mandate-12 criterion 3).
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import (
    SectionRead,
    SliceDependencyDiscoverabilityComposition,
    documents_all,
    documents_dependency_token,
    states_default_flip,
)
from .domain_types import AUTHORING_SURFACE_BY_PHRASE, FabricatedFixture


scenarios("../slice-dependency-annotation-discoverable.feature")


@pytest.fixture
def composition() -> SliceDependencyDiscoverabilityComposition:
    return SliceDependencyDiscoverabilityComposition()


@pytest.fixture
def read_box() -> dict[str, SectionRead]:
    return {}


# --- Given -------------------------------------------------------------


@given(parsers.parse("the {surface} authoring surface"))
def given_authoring_surface(
    composition: SliceDependencyDiscoverabilityComposition,
    read_box: dict[str, SectionRead],
    surface: str,
) -> None:
    read = composition.read_surface(AUTHORING_SURFACE_BY_PHRASE[surface])
    if not read.surface_present:
        pytest.skip(
            f"no local nWave install for {surface!r} -- fresh clone/CI, not "
            "this scenario's defect to report"
        )
    read_box["read"] = read


@given("a fabricated surface with the token pasted into an unrelated appendix")
def given_fabricated_outside_section(
    composition: SliceDependencyDiscoverabilityComposition,
    read_box: dict[str, SectionRead],
) -> None:
    read_box["read"] = composition.read_fabricated(
        FabricatedFixture.TOKEN_OUTSIDE_SECTION
    )


@given("a fabricated surface that names the token without stating the default flip")
def given_fabricated_bare_token(
    composition: SliceDependencyDiscoverabilityComposition,
    read_box: dict[str, SectionRead],
) -> None:
    read_box["read"] = composition.read_fabricated(FabricatedFixture.BARE_TOKEN_NO_FLIP)


@given(
    "a fabricated surface that documents the new token but drops an "
    "existing annotation token"
)
def given_fabricated_drops_existing(
    composition: SliceDependencyDiscoverabilityComposition,
    read_box: dict[str, SectionRead],
) -> None:
    read_box["read"] = composition.read_fabricated(
        FabricatedFixture.DROPS_EXISTING_TOKEN
    )


# --- When ------------------------------------------------------------------


@when("a PO reads that surface's annotation-vocabulary section")
def when_read_section(read_box: dict[str, SectionRead]) -> None:
    # The Given step already extracted the section; When is kept as a
    # narrative capture point for the reused Given/When/Then vocabulary
    # (Pillar 2) and asserts the precondition it depends on.
    assert "read" in read_box, "no surface was read"


# --- Then --------------------------------------------------------------------


@then("the section documents the depends-on slice-id token")
def then_documents_token(read_box: dict[str, SectionRead]) -> None:
    read = read_box["read"]
    assert documents_dependency_token(read.section_text), (
        "expected the `depends-on {slice-id}` token in the extracted "
        f"section; got:\n{read.section_text}"
    )


@then("the section does not document the depends-on slice-id token")
def then_does_not_document_token(read_box: dict[str, SectionRead]) -> None:
    read = read_box["read"]
    assert not documents_dependency_token(read.section_text), (
        "the token was pasted outside the target section -- it must not be "
        f"recognized as documented; got:\n{read.section_text}"
    )


@then("the section states the flipped default in plain language")
def then_states_flip(read_box: dict[str, SectionRead]) -> None:
    read = read_box["read"]
    assert states_default_flip(read.section_text), (
        "expected silence-means-parallel-safe language in the extracted "
        f"section; got:\n{read.section_text}"
    )


@then("the section does not state the flipped default in plain language")
def then_does_not_state_flip(read_box: dict[str, SectionRead]) -> None:
    read = read_box["read"]
    assert not states_default_flip(read.section_text), (
        "a bare token mention must not count as stating the default flip; "
        f"got:\n{read.section_text}"
    )


@then("the section still documents its pre-existing annotation tokens")
def then_documents_existing_tokens(read_box: dict[str, SectionRead]) -> None:
    read = read_box["read"]
    assert documents_all(read.section_text, read.existing_tokens), (
        f"lost one or more pre-existing annotation tokens "
        f"{read.existing_tokens!r} -- this slice must extend the "
        f"vocabulary, never displace an entry; got:\n{read.section_text}"
    )


@then("the section no longer documents its pre-existing annotation tokens")
def then_regression_lost_existing_tokens(read_box: dict[str, SectionRead]) -> None:
    read = read_box["read"]
    assert not documents_all(read.section_text, read.existing_tokens), (
        "test setup invariant broken: the fabricated fixture must actually "
        f"drop a pre-existing token, or this negative AT is vacuous; "
        f"got:\n{read.section_text}"
    )
