"""pytest-bdd binding + step vocabulary for slice-03-seam-injection-port.

Mandate-12 (SSOT via Types + Services + DSL): step decorators are parameterized
templates over typed-enum parameters (from ``domain_types.py``). Mandate-12
criterion 3: every step body is <=2 statements, ends in a single
``composition.<service>(...)`` call (or a typed-lookup + call), no control flow.
Business logic lives in the production port behind the ``inject_seam`` CLI; the
composition transports results; this module only names domain facts and
delegates.

S1 (step-text uniqueness): every literal step string here is distinct from
slice-01 + slice-02 vocabulary -- no ``@then`` shadowing across the feature dir.
The slice-03 ``the injection abstain reason is "{reason}"`` is deliberately
distinct from slice-02's ``the abstain reason is "{reason}"`` (same template
string would collide in the pytest-bdd global registry). The fixture name
``injection_composition`` is also distinct from the other slices' roots.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_03 import SeamInjectionComposition
from .domain_types import INJECTION_OUTCOME_BY_PHRASE, REASON_BY_PHRASE


scenarios("../slice-03-seam-injection-port.feature")


@pytest.fixture
def injection_composition() -> Iterator[SeamInjectionComposition]:
    """The production seam-injection composition root, fresh per scenario.

    Teardown removes the mkdtemp workspace the composition stages during the
    CLI subprocess call, so the suite leaves no ``/tmp`` residue.
    """
    comp = SeamInjectionComposition()
    yield comp
    if comp._workspace is not None:
        shutil.rmtree(comp._workspace, ignore_errors=True)


# --- Given: stage the generated scaffold + its named seams --------------------


@given("a generated scaffold exposing a nameable seam")
def given_nameable_seam(injection_composition: SeamInjectionComposition) -> None:
    injection_composition.given_scaffold_with_nameable_seam()


@given("the seam initially resolves to the real implementation")
def given_seam_initially_real(
    injection_composition: SeamInjectionComposition,
) -> None:
    injection_composition.given_scaffold_with_nameable_seam()


@given("a generated scaffold with no seam matching the requested name")
def given_unnameable_seam(injection_composition: SeamInjectionComposition) -> None:
    injection_composition.given_scaffold_without_matching_seam()


# --- When: perturb the seam through the injection port -------------------------


@when("the seam-injection port perturbs that seam")
def when_perturb_seam(injection_composition: SeamInjectionComposition) -> None:
    injection_composition.result = injection_composition.perturb_seam()


# --- Then: assert on the post-injection seam resolution + abstain signal -------


@then(parsers.parse('the perturbation outcome is "{outcome}"'))
def then_perturbation_outcome(
    injection_composition: SeamInjectionComposition, outcome: str
) -> None:
    assert injection_composition.result.outcome == INJECTION_OUTCOME_BY_PHRASE[outcome]


@then("the seam now resolves to the fault implementation")
def then_seam_resolves_fault(
    injection_composition: SeamInjectionComposition,
) -> None:
    assert injection_composition.seam_resolves_to_fault() is True


@then("the seam no longer resolves to the real implementation")
def then_seam_not_real(injection_composition: SeamInjectionComposition) -> None:
    assert injection_composition.seam_resolves_to_real() is False


@then(parsers.parse('the injection abstain reason is "{reason}"'))
def then_injection_abstain_reason(
    injection_composition: SeamInjectionComposition, reason: str
) -> None:
    assert injection_composition.result.reason == REASON_BY_PHRASE[reason]


@then("the real dependency is left untouched")
def then_real_untouched(injection_composition: SeamInjectionComposition) -> None:
    assert injection_composition.real_dependency_left_untouched() is True
