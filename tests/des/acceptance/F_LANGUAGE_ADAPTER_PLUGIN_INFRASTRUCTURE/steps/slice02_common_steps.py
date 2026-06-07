"""Slice-02 step vocabulary for F-LANGUAGE-ADAPTER-PLUGIN-INFRASTRUCTURE.

Mandate-12 (SSOT via Types + Services + DSL): the slice's `.feature` file
binds to typed-parameter step templates. Each decorator below is parameterized
over a typed-enum lookup from ``slice02_domain_types.py`` -- the DSL emerges
from the typed concepts, not from one decorator per literal phrase.

Mandate-12 criterion 3: every step body is <=2 statements, ends in a single
``composition.<service>(...)`` call (or a typed-lookup + call), and contains
no control flow. Business logic lives in ``slice02_composition.py`` service
methods, never here.

Tier-2 S1 (step-text uniqueness within feature scope): every decorator
literal here is DISTINCT from any literal in ``common_steps.py`` (slice-01
shared vocabulary). The slice-02 phrases reference the "language-adapter
ABC" + "entry-point conformance" + "ABC contract member" -- nouns absent
from slice-01's catalog/doctor/discovery vocabulary. Scope-grepped at
authorship time to confirm zero collisions.

Mandate-13 (driving-port-only, CRITICAL P0): step bodies invoke composition
methods that subprocess to the production import boundary. ZERO direct
domain imports here -- the only imports are this slice's composition + types
modules, the pytest-bdd surface, and pytest itself.

Slice-02 binds the three ATs in ``slice-02-language-adapter-plugin-abc.feature``
to the production composition root via subprocess (Pillar 3 app-as-in-production).
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, then, when

from .slice02_composition import LanguageAdapterAbcComposition
from .slice02_domain_types import (
    ABC_CONTRACT_MEMBER_BY_PHRASE,
    ABC_INTROSPECTION_SHAPE_BY_PHRASE,
    ENTRY_POINT_CONFORMANCE_SHAPE_BY_PHRASE,
)


@pytest.fixture
def abc_composition() -> LanguageAdapterAbcComposition:
    """The production composition root for slice-02 ATs, fresh per scenario."""
    return LanguageAdapterAbcComposition()


# --- Given: ABC + conformance query staging ---------------------------------


@given("the language-adapter ABC substrate is queried via the installed package")
def given_abc_substrate_queried(
    abc_composition: LanguageAdapterAbcComposition,
) -> None:
    abc_composition.given_abc_substrate_query_staged()


@given(
    "the language-adapter entry-point discovery is exercised "
    "against the conformance fixture"
)
def given_conformance_fixture_exercised(
    abc_composition: LanguageAdapterAbcComposition,
) -> None:
    abc_composition.given_conformance_query_staged()


# --- When: production-subprocess invocation ---------------------------------


@when("the language-adapter ABC introspection runs")
def when_abc_introspection_runs(
    abc_composition: LanguageAdapterAbcComposition,
) -> None:
    abc_composition.when_abc_introspection_runs()


@when("the language-adapter entry-point conformance check runs")
def when_entry_point_conformance_runs(
    abc_composition: LanguageAdapterAbcComposition,
) -> None:
    abc_composition.when_entry_point_conformance_runs()


# --- Then: universe-bound assertions over port-exposed observables ----------


@then(
    parsers.parse("the language-adapter ABC introspection reports the class as {shape}")
)
def then_abc_introspection_shape(
    abc_composition: LanguageAdapterAbcComposition, shape: str
) -> None:
    abc_composition.then_abc_introspection_shape_is(
        ABC_INTROSPECTION_SHAPE_BY_PHRASE[shape]
    )


@then(
    parsers.parse(
        'the language-adapter ABC introspection reports the "{contract_member}" '
        "contract member as declared"
    )
)
def then_abc_member_declared(
    abc_composition: LanguageAdapterAbcComposition, contract_member: str
) -> None:
    abc_composition.then_abc_member_is_declared(
        ABC_CONTRACT_MEMBER_BY_PHRASE[contract_member]
    )


@then(parsers.parse("the language-adapter entry-point conformance reports {shape}"))
def then_conformance_shape(
    abc_composition: LanguageAdapterAbcComposition, shape: str
) -> None:
    abc_composition.then_conformance_envelope_shape_is(
        ENTRY_POINT_CONFORMANCE_SHAPE_BY_PHRASE[shape]
    )
