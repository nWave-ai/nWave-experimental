"""Step bindings for mode-registry-single-locus slice-01.

The SSOT-via-Types-Services-DSL mandate, criterion 3 — every step body has
<=2 statements, the final statement is `composition.<method>(...)`, no
control flow. The DSL emerges from typed phrase coercion via the
`domain_types_slice_01` lookup tables.

The Driving-Port-Only Boundary mandate — this module imports ONLY the
composition fixture (by pytest fixture name) + the typed vocabulary. Zero
production imports here; the single sanctioned driving-port import lives in
`composition_slice_01.py` (attestation in its module docstring).
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from .domain_types_slice_01 import DEFECT_BY_PHRASE, FLAVOR_BY_PHRASE, SkillName


# --- Background ------------------------------------------------------------


@given("the shipped mode registry declares the atdd_pure and classic flavors")
def given_shipped_registry(composition) -> None:
    composition.use_shipped_registry()


# --- Given: defective registry authoring (AT-03) ----------------------------


@given(parsers.parse("a mode registry whose crafter entry is {defect}"))
def given_defective_registry(composition, defect: str) -> None:
    composition.author_registry_with_crafter_defect(DEFECT_BY_PHRASE[defect])


# --- When: the dispatch asks the registry -----------------------------------


@when(
    parsers.parse(
        "the dispatch asks the registry for the crafter's conditional skills "
        'under the "{flavor}" flavor'
    )
)
def when_resolve_under_shipped_flavor(composition, flavor: str) -> None:
    composition.resolve_crafter_conditional_skills(FLAVOR_BY_PHRASE[flavor])


@when("the dispatch asks that registry for the crafter's conditional skills")
def when_resolve_under_authored_registry(composition) -> None:
    composition.resolve_crafter_conditional_skills_in_authored_registry()


# --- Then: directives and refusals ------------------------------------------


@then(parsers.parse('the crafter is directed to load exactly "{skill}"'))
def then_directed_exactly(composition, skill: str) -> None:
    composition.assert_directed_exactly(SkillName(skill))


@then("no other conditional skill is injected for the crafter")
def then_no_other_directive(composition) -> None:
    composition.assert_single_directive()


@then("the crafter is directed to load no conditional skills")
def then_directed_to_load_nothing(composition) -> None:
    composition.assert_directed_to_load_nothing()


@then("that empty answer is the registry's own declaration, not a fallback")
def then_answer_was_declared(composition) -> None:
    composition.assert_answer_was_declared()


@then("the request is refused as a declaration defect")
def then_refused_as_declaration_defect(composition) -> None:
    composition.assert_refused_as_declaration_defect()


@then("no conditional skills are improvised for the crafter")
def then_no_skills_improvised(composition) -> None:
    composition.assert_no_skills_improvised()
