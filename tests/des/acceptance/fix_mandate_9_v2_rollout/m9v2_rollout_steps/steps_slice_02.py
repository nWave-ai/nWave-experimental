"""Step bindings for fix-mandate-9-v2-rollout slice-02 acceptance tests.

Mandate-12 criterion 3 — every step body has <=2 statements, the final
statement is `composition.<method>(...)`. NO control flow (`if`/`for`/
`while`/`try`) in step bodies. DSL emerges from typed parameter coercion
via `parsers.parse` + `domain_types` enum / NewType lookups.

Mandate-13 — driving-port-only. Step modules import ONLY the composition
root (via fixture) + `domain_types`. ZERO `from des.<domain|application|
adapters>.<x> import <internal>` direct-domain imports. The composition
in conftest.py reads production skill/agent .md files via
`pathlib.Path.read_text(...)` — the filesystem is the driving surface for
documentation-contract behavioural surfaces (slice-02 SUT = production
.md document bodies).
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then


# --- Background ------------------------------------------------------------
# Same Background step text as slice-01; pytest-bdd binds per test-module so
# the binding is redeclared here for the slice-02 entry test. Step body is
# the canonical composition-fixture availability assertion (Mandate-13 +
# Mandate-12 criterion 3 — one statement, no control flow).


@given("the mandate 9 v2 rollout composition is available")
def given_composition_available(composition) -> None:
    assert composition is not None


# --- Surface (4): nw-distill skill document -------------------------------


@given("the nw-distill skill document is loaded")
def given_load_distill_skill(composition) -> None:
    composition.load_distill_skill_doc()


@then(parsers.parse('the distill skill carries the section heading "{heading}"'))
def then_distill_section_heading(composition, heading: str) -> None:
    assert composition.distill_skill_carries_section_heading(heading)


@then(parsers.parse('the distill skill enumerates the property "{property_name}"'))
def then_distill_enumerates_property(composition, property_name: str) -> None:
    assert composition.distill_skill_enumerates_property(property_name)


@then(
    parsers.parse(
        'the distill skill declares the per-property verdict vocabulary "{token}"'
    )
)
def then_distill_declares_verdict_vocabulary(composition, token: str) -> None:
    assert composition.distill_skill_declares_verdict_vocabulary(token)


# --- Surface (5): nw-acceptance-designer-reviewer agent document ---------


@given("the acceptance designer reviewer agent document is loaded")
def given_load_reviewer_agent(composition) -> None:
    composition.load_reviewer_agent_doc()


@then(parsers.parse('the reviewer agent declares the critique vector "{vector_name}"'))
def then_reviewer_declares_critique_vector(composition, vector_name: str) -> None:
    assert composition.reviewer_agent_declares_critique_vector(vector_name)


@then(
    parsers.parse(
        'the reviewer agent enumerates the mechanical checklist step "{phrase}"'
    )
)
def then_reviewer_enumerates_checklist_step(composition, phrase: str) -> None:
    assert composition.reviewer_agent_enumerates_checklist_step(phrase)


# --- Surface (6): nw-tdd-methodology skill document ----------------------


@given("the nw-tdd-methodology skill document is loaded")
def given_load_tdd_methodology(composition) -> None:
    composition.load_tdd_methodology_doc()


@then(
    parsers.parse('the tdd methodology skill carries the section heading "{heading}"')
)
def then_tdd_section_heading(composition, heading: str) -> None:
    assert composition.tdd_methodology_carries_section_heading(heading)


@then(parsers.parse('the tdd methodology skill mentions the red phase mode "{mode}"'))
def then_tdd_mentions_red_phase_mode(composition, mode: str) -> None:
    assert composition.tdd_methodology_mentions_red_phase_mode(mode)


@then(
    parsers.parse(
        'the tdd methodology skill distinguishes red phase semantics by mentioning "{token}"'
    )
)
def then_tdd_distinguishes_red_phase(composition, token: str) -> None:
    assert composition.tdd_methodology_distinguishes_red_phase_by(token)
