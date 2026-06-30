"""Step bindings for mode-registry-single-locus slice-05.

The SSOT-via-Types-Services-DSL mandate, criterion 3 — every step body has
<=2 statements, the final statement is `guardrail_composition.<method>(...)`,
no control flow. The DSL emerges from typed phrase coercion via the
`domain_types_slice_05` lookup tables (`GATE_BY_PHRASE`,
`REGISTRY_DEFECT_BY_PHRASE`).

The Driving-Port-Only Boundary mandate — this module imports ONLY the
composition fixture (by pytest fixture name) + the typed vocabulary. Every
gate is driven by subprocess through its real entry in
`composition_slice_05.py`; there is ZERO production import anywhere in the
slice-05 step surface (S2 PASS).

S1 step-text uniqueness: every literal below is phrased for the slice-05
guardrail journey and collides with no slice-01/02/03/04 literal — slice-01
speaks of "the dispatch asks the registry"; slice-02 of "the projection
re-renders the working copy" / "the staleness check"; slice-03 of "the
command guides"; slice-04 of "the bulk migration" / "the sweep" / "the
prose-watchers"; slice-05 speaks of "the guardrail", "a mechanical mode gate",
"the offending defect", and "wired".
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from .domain_types_slice_05 import GATE_BY_PHRASE, REGISTRY_DEFECT_BY_PHRASE


# --- Background -----------------------------------------------------------------


@given("a working copy of the mode registry, its asset families, and the gate catalog")
def given_guardrail_working_copy(guardrail_composition) -> None:
    guardrail_composition.build_working_copy()


# --- Given: which gate + the planted defect -------------------------------------


@given(parsers.parse("{gate_phrase} stands watch over the working copy"))
def given_gate_selected(guardrail_composition, gate_phrase: str) -> None:
    guardrail_composition.select_gate(GATE_BY_PHRASE[gate_phrase])


@given("the guardrail has already accepted the clean working copy as a baseline")
def given_clean_baseline(guardrail_composition) -> None:
    guardrail_composition.establish_clean_baseline()


@given("a mode literal is re-stated by hand outside any generated region or marker")
def given_naked_literal_planted(guardrail_composition) -> None:
    guardrail_composition.plant_naked_mode_literal()


@given(parsers.parse("the working registry is half-declared so that {defect_phrase}"))
def given_registry_defect_introduced(guardrail_composition, defect_phrase: str) -> None:
    guardrail_composition.introduce_registry_defect(
        REGISTRY_DEFECT_BY_PHRASE[defect_phrase]
    )


@given("the registry's declared delivery phase shape drifts from the running system")
def given_phase_shape_drift(guardrail_composition) -> None:
    guardrail_composition.introduce_phase_shape_drift()


# --- When: drive the guardrail through its real entry ---------------------------


@when("the guardrail inspects the clean working copy")
def when_guardrail_inspects_clean(guardrail_composition) -> None:
    guardrail_composition.run_gate_against_clean_copy()


@when("the guardrail inspects the working copy carrying the defect")
def when_guardrail_inspects_defective(guardrail_composition) -> None:
    guardrail_composition.run_gate_against_defective_copy()


# --- Then: teeth + preservation + wiring witness --------------------------------


@then("the guardrail refuses the working copy, naming the offending defect")
def then_guardrail_refuses_naming_defect(guardrail_composition) -> None:
    guardrail_composition.assert_gate_refuses_naming_defect()


@then("the guardrail accepts the clean working copy")
def then_guardrail_accepts_clean(guardrail_composition) -> None:
    guardrail_composition.assert_gate_accepts_clean_copy()


@then("the guardrail accepted the clean working copy before the defect")
def then_guardrail_accepted_baseline(guardrail_composition) -> None:
    guardrail_composition.assert_accepted_clean_baseline_before_defect()


@then("the guardrail itself rewrites nothing")
def then_guardrail_rewrites_nothing(guardrail_composition) -> None:
    guardrail_composition.assert_gate_rewrites_nothing()


@then("the guardrail is wired as a reachable gate the catalog declares")
def then_guardrail_wired(guardrail_composition) -> None:
    guardrail_composition.assert_gate_wired_to_dispatcher_and_catalog()
