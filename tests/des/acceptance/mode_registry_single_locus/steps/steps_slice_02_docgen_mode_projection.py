"""Step bindings for mode-registry-single-locus slice-02.

The SSOT-via-Types-Services-DSL mandate, criterion 3 — every step body has
<=2 statements, the final statement is `projection_composition.<method>(...)`,
no control flow. The DSL emerges from typed phrase coercion via the
`domain_types_slice_02` lookup tables.

The Driving-Port-Only Boundary mandate — this module imports ONLY the
composition fixture (by pytest fixture name) + the typed vocabulary. Zero
production imports here; the single sanctioned driving-port import lives in
`composition_slice_02.py` (attestation in its module docstring).

S1 step-text uniqueness: every literal below is phrased for the slice-02
projection journey and collides with no slice-01 literal (slice-01 speaks of
"the dispatch asks the registry"; slice-02 speaks of "the projection" and
"the staleness check").
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from .domain_types_slice_02 import DRIFT_BY_PHRASE


# --- Background ---------------------------------------------------------------


@given("a working copy of the shipped crafter spec, deliver guide, and mode registry")
def given_working_copy(projection_composition) -> None:
    projection_composition.build_working_copy()


@given("the working registry declares the mode descriptors authored for this test")
def given_authored_descriptors(projection_composition) -> None:
    projection_composition.author_mode_descriptors()


# --- Given: registry edits + projection baseline -------------------------------


@given(
    "the working registry is edited to direct the crafter to a different "
    "conditional skill"
)
def given_registry_edited(projection_composition) -> None:
    projection_composition.edit_registry_to_direct_crafter_elsewhere()


@given("the working copy has been freshly projected and accepted")
def given_freshly_projected_and_accepted(projection_composition) -> None:
    projection_composition.freshly_project_and_accept()


@given(parsers.parse("{drift} behind the projection's back"))
def given_drift_applied(projection_composition, drift: str) -> None:
    projection_composition.apply_drift(DRIFT_BY_PHRASE[drift])


# --- When: drive the real docgen entry point -----------------------------------


@when("the projection re-renders the working copy")
def when_projection_rerenders(projection_composition) -> None:
    projection_composition.project_working_copy()


@when("the staleness check inspects the working copy")
def when_staleness_check_runs(projection_composition) -> None:
    projection_composition.run_staleness_check()


# --- Then: projection outcomes --------------------------------------------------


@then("the re-render completes without refusal")
def then_render_completed(projection_composition) -> None:
    projection_composition.assert_render_completed()


@then(
    "the crafter spec's generated skill-load region directs exactly what the "
    "registry resolution seam answers"
)
def then_crafter_region_follows_registry(projection_composition) -> None:
    projection_composition.assert_crafter_region_follows_registry()


@then(
    "no hand-written copy of the retired conditional-skill row survives in "
    "the crafter spec"
)
def then_inline_row_retired(projection_composition) -> None:
    projection_composition.assert_inline_row_retired()


@then("the crafter spec outside its generated region is untouched")
def then_crafter_outside_untouched(projection_composition) -> None:
    projection_composition.assert_crafter_outside_region_untouched()


@then(
    "the deliver guide's generated mode-descriptor region carries the "
    "registry's descriptor for every declared mode"
)
def then_deliver_region_carries_descriptors(projection_composition) -> None:
    projection_composition.assert_deliver_region_carries_all_descriptors()


@then(
    "the deliver guide's generated mode-descriptor region carries the "
    "registry's deliver phase shape"
)
def then_deliver_region_carries_phase_shape(projection_composition) -> None:
    projection_composition.assert_deliver_region_carries_phase_shape()


@then("the deliver guide outside its generated region is untouched")
def then_deliver_outside_untouched(projection_composition) -> None:
    projection_composition.assert_deliver_outside_region_untouched()


# --- Then: staleness-check outcomes ----------------------------------------------


@then("the staleness check refuses the working copy, naming the stale crafter spec")
def then_refused_naming_crafter_spec(projection_composition) -> None:
    projection_composition.assert_refused_naming_crafter_spec()


@then("the very same working copy was accepted before the drift")
def then_accepted_before_drift(projection_composition) -> None:
    projection_composition.assert_accepted_before_drift()


@then("the staleness check itself rewrites nothing")
def then_check_rewrites_nothing(projection_composition) -> None:
    projection_composition.assert_check_rewrites_nothing()
