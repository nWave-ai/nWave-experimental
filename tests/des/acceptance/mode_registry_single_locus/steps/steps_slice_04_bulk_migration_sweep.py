"""Step bindings for mode-registry-single-locus slice-04.

The SSOT-via-Types-Services-DSL mandate, criterion 3 — every step body has
<=2 statements, the final statement is `bulk_composition.<method>(...)`,
no control flow. The DSL emerges from typed phrase coercion via the
`domain_types_slice_04` lookup tables.

The Driving-Port-Only Boundary mandate — this module imports ONLY the
composition fixture (by pytest fixture name) + the typed vocabulary. docgen
is driven by subprocess in `composition_slice_04.py`; the only production
import lives there (the slice-01 seam, attestation in its module docstring).

S1 step-text uniqueness: every literal below is phrased for the slice-04
bulk-migration journey and collides with no slice-01/02/03 literal
(slice-01 speaks of "the dispatch asks the registry"; slice-02 of "the
projection re-renders the working copy" and "the staleness check inspects
the working copy"; slice-03 of "the command guides" and "the catalog";
slice-04 of "the bulk migration", "the migrated families", "the sweep",
and "the prose-watchers").
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from .domain_types_slice_04 import (
    AGENT_SPEC_BY_PHRASE,
    GUARDED_ASSET_BY_PHRASE,
    RENDER_CASE_BY_PHRASE,
    WATCHER_BY_PHRASE,
)


# --- Background -----------------------------------------------------------------


@given("a working copy of every shipped mode-aware asset family and the mode registry")
def given_bulk_working_copy(bulk_composition) -> None:
    bulk_composition.build_bulk_working_copy()


# --- Given: registry authoring + projection baseline + drift ----------------------


@given(parsers.parse("the working registry is edited to declare {render_case}"))
def given_render_case_declared(bulk_composition, render_case: str) -> None:
    bulk_composition.declare_render_case(RENDER_CASE_BY_PHRASE[render_case])


@given("the migrated families have been freshly re-rendered and accepted")
def given_families_rendered_and_accepted(bulk_composition) -> None:
    bulk_composition.freshly_render_and_accept()


@given(
    parsers.parse(
        "the {guarded_asset}'s generated region is hand-edited "
        "behind the bulk migration's back"
    )
)
def given_guarded_region_hand_edited(bulk_composition, guarded_asset: str) -> None:
    bulk_composition.hand_edit_guarded_region(GUARDED_ASSET_BY_PHRASE[guarded_asset])


# --- When: drive the real docgen entry point / the sweep ---------------------------


@when("the bulk migration re-renders every migrated asset")
def when_bulk_migration_rerenders(bulk_composition) -> None:
    bulk_composition.render_bulk_working_copy()


@when("the sweep audits every migrated asset family for hand-written mode statements")
def when_sweep_audits_families(bulk_composition) -> None:
    bulk_composition.run_naked_literal_sweep()


@when("the staleness check audits the migrated families")
def when_staleness_check_audits_families(bulk_composition) -> None:
    bulk_composition.run_bulk_staleness_check()


# --- Then: AT-01 rendering outcomes --------------------------------------------------


@then("the bulk re-render completes without refusal")
def then_bulk_rerender_completed(bulk_composition) -> None:
    bulk_composition.assert_bulk_render_completed()


@then(
    parsers.parse(
        "the {agent} spec's generated skill-load region declares "
        "exactly what the registry resolution seam answers"
    )
)
def then_agent_region_matches_seam(bulk_composition, agent: str) -> None:
    bulk_composition.assert_agent_region_matches_seam(AGENT_SPEC_BY_PHRASE[agent])


@then(parsers.parse("the {agent} spec outside its generated region is untouched"))
def then_agent_outside_region_untouched(bulk_composition, agent: str) -> None:
    bulk_composition.assert_agent_outside_region_untouched(AGENT_SPEC_BY_PHRASE[agent])


# --- Then: AT-02 sweep outcomes -------------------------------------------------------


@then(
    "no hand-written mode statement survives outside a generated region "
    "or a marked reference"
)
def then_no_naked_literal_survives(bulk_composition) -> None:
    bulk_composition.assert_no_naked_literal_survives()


@then("the sweep itself rewrites nothing")
def then_sweep_rewrites_nothing(bulk_composition) -> None:
    bulk_composition.assert_sweep_rewrites_nothing()


# --- Then: AT-03 watcher-ledger outcomes -----------------------------------------------


@then(parsers.parse("the {watcher} is gone from the test tree"))
def then_watcher_gone(bulk_composition, watcher: str) -> None:
    bulk_composition.assert_watcher_deleted(WATCHER_BY_PHRASE[watcher])


@then("the prose-watchers ruled keepers still stand watch")
def then_keeper_watchers_still_present(bulk_composition) -> None:
    bulk_composition.assert_keeper_watchers_still_present()


@then(
    parsers.parse(
        "the staleness check refuses the migrated families, naming the {guarded_asset}"
    )
)
def then_refused_naming_guarded_asset(bulk_composition, guarded_asset: str) -> None:
    bulk_composition.assert_refused_naming_guarded_asset(
        GUARDED_ASSET_BY_PHRASE[guarded_asset]
    )


@then("the migrated families were accepted before the hand-edit")
def then_accepted_before_hand_edit(bulk_composition) -> None:
    bulk_composition.assert_accepted_before_hand_edit()
