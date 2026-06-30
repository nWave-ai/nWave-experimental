"""Step bindings for mode-registry-single-locus slice-03.

The SSOT-via-Types-Services-DSL mandate, criterion 3 — every step body has
<=2 statements, the final statement is `frontmatter_composition.<method>(...)`,
no control flow. The DSL emerges from typed phrase coercion via the
`domain_types_slice_03` lookup tables.

The Driving-Port-Only Boundary mandate — this module imports ONLY the
composition fixture (by pytest fixture name) + the typed vocabulary. Zero
production imports anywhere in slice-03; docgen is driven by subprocess in
`composition_slice_03.py` and the expected-side oracle is an independent
YAML parse (attestation in its module docstring).

S1 step-text uniqueness: every literal below is phrased for the slice-03
command-guide journey and collides with no slice-01/slice-02 literal
(slice-01 speaks of "the dispatch asks the registry"; slice-02 of "the
projection re-renders the working copy"; slice-03 of "the command guides"
and "the catalog").
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from .domain_types_slice_03 import DESYNC_BY_PHRASE


# --- Background ---------------------------------------------------------------


@given("a working copy of the shipped command guides and the framework catalog")
def given_command_guides_working_copy(frontmatter_composition) -> None:
    frontmatter_composition.build_working_copy()


# --- Given: catalog edits + projection baseline ---------------------------------


@given("the catalog's description for the execute command is edited")
def given_catalog_execute_description_edited(frontmatter_composition) -> None:
    frontmatter_composition.edit_catalog_description_for_execute()


@given("the catalog's argument hint for the distill command is edited")
def given_catalog_distill_hint_edited(frontmatter_composition) -> None:
    frontmatter_composition.edit_catalog_hint_for_distill()


@given("the command guides have been freshly projected and accepted")
def given_guides_freshly_projected_and_accepted(frontmatter_composition) -> None:
    frontmatter_composition.freshly_project_and_accept()


@given(parsers.parse("{desync} behind the command guides' back"))
def given_desync_applied(frontmatter_composition, desync: str) -> None:
    frontmatter_composition.apply_desync(DESYNC_BY_PHRASE[desync])


# --- When: drive the real docgen entry point ------------------------------------


@when("the command guides are re-projected from the catalog")
def when_guides_reprojected(frontmatter_composition) -> None:
    frontmatter_composition.project_command_guides()


@when("the command guides are projected once more")
def when_guides_projected_once_more(frontmatter_composition) -> None:
    frontmatter_composition.project_command_guides()


@when("the staleness check inspects the command guides")
def when_staleness_check_inspects_guides(frontmatter_composition) -> None:
    frontmatter_composition.run_staleness_check()


# --- Then: projection outcomes ----------------------------------------------------


@then("the catalog projection completes without refusal")
def then_catalog_projection_completed(frontmatter_composition) -> None:
    frontmatter_composition.assert_projection_completed()


@then("the execute guide's description is exactly what the edited catalog declares")
def then_execute_description_follows_catalog(frontmatter_composition) -> None:
    frontmatter_composition.assert_execute_description_follows_catalog()


@then("the distill guide's argument hint is exactly what the edited catalog declares")
def then_distill_hint_follows_catalog(frontmatter_composition) -> None:
    frontmatter_composition.assert_distill_hint_follows_catalog()


@then("nothing else about the command guides or the catalog changes")
def then_bounded_change_only(frontmatter_composition) -> None:
    frontmatter_composition.assert_bounded_change_only()


# --- Then: staleness-check outcomes ------------------------------------------------


@then("the staleness check refuses the command guides, naming the stale execute guide")
def then_refused_naming_execute_guide(frontmatter_composition) -> None:
    frontmatter_composition.assert_refused_naming_execute_guide()


@then("the very same command guides were accepted before the desync")
def then_accepted_before_desync(frontmatter_composition) -> None:
    frontmatter_composition.assert_accepted_before_desync()


@then("the staleness check leaves every command guide untouched")
def then_check_left_guides_untouched(frontmatter_composition) -> None:
    frontmatter_composition.assert_check_left_guides_untouched()


# --- Then: byte-match degradation pin (AT-03) ---------------------------------------


@then("the freshly projected command guides were accepted by the staleness check")
def then_fresh_projection_was_accepted(frontmatter_composition) -> None:
    frontmatter_composition.assert_fresh_projection_was_accepted()


@then(
    "every command guide the catalog declares agrees with the catalog on "
    "description and argument hint"
)
def then_every_declared_guide_agrees(frontmatter_composition) -> None:
    frontmatter_composition.assert_every_declared_guide_agrees_with_catalog()


@then("the second projection changes not a single command guide")
def then_second_projection_changed_nothing(frontmatter_composition) -> None:
    frontmatter_composition.assert_second_projection_changed_nothing()
