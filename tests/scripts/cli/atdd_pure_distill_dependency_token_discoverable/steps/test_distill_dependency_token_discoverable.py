"""Step definitions: the dependency token is discoverable from the DISTILL
authoring surface (the ``nw-distill`` skill family), pointing at nw-discuss's
vocabulary reference rather than restating it.

`docs/feature/parallel-by-default-distill-slicing/feature-delta.md` slice-02.

No production driving port exists for "is this documented" (same posture as the
row-1 sibling suite
``tests/scripts/cli/atdd_pure_slice_dependency_annotation_discoverable/`` and as
AT-d in ``tests/des/unit/cli/test_carpaccio_ceiling_15_and_coupled_affordance.py``
for the ``@coupled`` affordance) -- step bodies delegate to
``DistillDependencyDiscoverabilityComposition``, which reads the real family
files (or a fabricated fixture, for the negative scenarios) and extracts the
token-locus text; no inline business logic in step bodies (Mandate-12
criterion 3).
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import (
    DistillDependencyDiscoverabilityComposition,
    FamilyRead,
    demands_justification_on_empty,
    documents_dependency_token,
    reads_silence_as_serial,
    references_discuss_vocabulary,
    states_default_flip,
)
from .domain_types import FAMILY_TREE_BY_PHRASE, FabricatedFamily


scenarios("../distill-dependency-token-discoverable.feature")


@pytest.fixture
def composition() -> DistillDependencyDiscoverabilityComposition:
    return DistillDependencyDiscoverabilityComposition()


@pytest.fixture
def read_box() -> dict[str, FamilyRead]:
    return {}


# --- Given -------------------------------------------------------------------


@given(parsers.parse("the {tree} nw-distill skill family"))
def given_family_tree(
    composition: DistillDependencyDiscoverabilityComposition,
    read_box: dict[str, FamilyRead],
    tree: str,
) -> None:
    read = composition.read_family(FAMILY_TREE_BY_PHRASE[tree])
    if not read.tree_present:
        pytest.skip(
            f"no local nWave install for {tree!r} -- fresh clone / CI, not "
            "this scenario's defect to report"
        )
    read_box["read"] = read


@given("a fabricated family that restates the rule but omits the nw-discuss pointer")
def given_fabricated_restated(
    composition: DistillDependencyDiscoverabilityComposition,
    read_box: dict[str, FamilyRead],
) -> None:
    read_box["read"] = composition.read_fabricated(
        FabricatedFamily.RESTATED_NO_CROSSLINK
    )


@given("a fabricated family that names the token but never states the default flip")
def given_fabricated_bare_token(
    composition: DistillDependencyDiscoverabilityComposition,
    read_box: dict[str, FamilyRead],
) -> None:
    read_box["read"] = composition.read_fabricated(FabricatedFamily.BARE_TOKEN_NO_FLIP)


@given("a fabricated family that makes an empty annotation owe a justification")
def given_fabricated_empty_owes(
    composition: DistillDependencyDiscoverabilityComposition,
    read_box: dict[str, FamilyRead],
) -> None:
    read_box["read"] = composition.read_fabricated(
        FabricatedFamily.EMPTY_NEEDS_JUSTIFICATION
    )


@given("a fabricated family that reads silence as assume-serial")
def given_fabricated_assume_serial(
    composition: DistillDependencyDiscoverabilityComposition,
    read_box: dict[str, FamilyRead],
) -> None:
    read_box["read"] = composition.read_fabricated(FabricatedFamily.ASSUME_SERIAL)


# --- When --------------------------------------------------------------------


@when("an acceptance-designer reads the family for the dependency-token vocabulary")
def when_read_family(read_box: dict[str, FamilyRead]) -> None:
    # The Given step already read the family; When is the narrative capture
    # point for the reused Given/When/Then vocabulary (Pillar 2) and asserts
    # the precondition it depends on.
    assert "read" in read_box, "no family was read"


# --- Then --------------------------------------------------------------------


@then("the family documents the depends-on slice-id token")
def then_documents_token(read_box: dict[str, FamilyRead]) -> None:
    read = read_box["read"]
    assert documents_dependency_token(read.family_text), (
        "expected the `depends-on {slice-id}` token somewhere in the "
        "nw-distill skill family; the family currently has zero mentions -- "
        "an acceptance-designer originating a Slice Plan in DISTILL cannot "
        "discover the vocabulary from his own trigger-loaded skill surface"
    )


@then("the token locus states the flipped default in plain language")
def then_locus_states_flip(read_box: dict[str, FamilyRead]) -> None:
    read = read_box["read"]
    assert states_default_flip(read.locus_text), (
        "expected the flipped default (silence = parallel-safe) stated in "
        "plain language NEAR the token; got locus:\n"
        f"{read.locus_text!r}"
    )


@then(
    "the token locus points at nw-discuss's Slice Plan annotation vocabulary reference"
)
def then_locus_points_at_discuss(read_box: dict[str, FamilyRead]) -> None:
    read = read_box["read"]
    assert references_discuss_vocabulary(read.locus_text), (
        "expected the locus to POINT at nw-discuss's `Slice Plan annotation "
        "vocabulary` reference (D-4 SSOT/DRY) -- naming both `nw-discuss` and "
        "that section near the token, not a second independently-worded copy; "
        f"got locus:\n{read.locus_text!r}"
    )


@then(
    "the token locus does not point at nw-discuss's Slice Plan annotation vocabulary reference"
)
def then_locus_does_not_point_at_discuss(read_box: dict[str, FamilyRead]) -> None:
    read = read_box["read"]
    assert not references_discuss_vocabulary(read.locus_text), (
        "a restated copy that omits the nw-discuss pointer must NOT be "
        "recognized as a valid cross-link -- it is the copy that drifts; got "
        f"locus:\n{read.locus_text!r}"
    )


@then("the token locus does not state the flipped default in plain language")
def then_locus_does_not_state_flip(read_box: dict[str, FamilyRead]) -> None:
    read = read_box["read"]
    assert not states_default_flip(read.locus_text), (
        "a bare token mention must NOT count as stating the default flip; got "
        f"locus:\n{read.locus_text!r}"
    )


@then("the family never tells an empty annotation it owes a justification")
def then_family_never_empty_owes(read_box: dict[str, FamilyRead]) -> None:
    read = read_box["read"]
    assert not demands_justification_on_empty(read.family_text), (
        "a nw-distill family file makes an empty Annotation OWE a Justification "
        "-- that resurrects the pre-row-1 default this feature exists to retire "
        "(charter obs 3)"
    )


@then("the family never reads silence as assume-serial")
def then_family_never_assume_serial(read_box: dict[str, FamilyRead]) -> None:
    read = read_box["read"]
    assert not reads_silence_as_serial(read.family_text), (
        "a nw-distill family file reads silence as 'assume serial' -- the exact "
        "guess row 1 exists to retire (charter obs 3)"
    )


@then("the family tells an empty annotation it owes a justification")
def then_family_empty_owes(read_box: dict[str, FamilyRead]) -> None:
    read = read_box["read"]
    assert demands_justification_on_empty(read.family_text), (
        "test-setup invariant broken: the fabricated fixture must actually make "
        "an empty annotation owe a justification, or this negative AT is vacuous"
    )


@then("the family reads silence as assume-serial")
def then_family_assume_serial(read_box: dict[str, FamilyRead]) -> None:
    read = read_box["read"]
    assert reads_silence_as_serial(read.family_text), (
        "test-setup invariant broken: the fabricated fixture must actually read "
        "silence as assume-serial, or this negative AT is vacuous"
    )
