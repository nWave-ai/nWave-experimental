"""Shared step vocabulary for the wire-p0-gates-at-feature-end suite.

Mandate-12 (SSOT via Types + Services + DSL): the three slices' `.feature`
files share ONE step vocabulary for the When/Then verbs (all three drive the
identical ``run_feature_end_cycle`` surface and assert the identical
``CycleRefusal`` observable); only the Given fixture-staging step differs per
gate, one dedicated ``@given`` per slice (each stages a materially different
disk fixture -- a git repo, a Cobertura XML, a README -- so a single
parameterized template would hide, not clarify, the domain difference).

Mandate-12 criterion 3: every step body is <=2 statements and ends in a
single ``composition.<service>(...)`` call; no control flow. Business logic
lives in ``composition.py``.

Each slice's ``test_slice_NN_*.py`` binding file imports ``*`` from this
module and calls ``scenarios(...)`` on its own ``.feature`` file --
pytest-bdd resolves every step from this shared module (Mandate 10
shared-vocabulary contract).
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, then, when

from .composition import FeatureEndP0GateComposition
from .domain_types import GATE_NAME_BY_PHRASE


@pytest.fixture
def composition(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> FeatureEndP0GateComposition:
    """The production composition root, fresh per scenario."""
    return FeatureEndP0GateComposition(tmp_path=tmp_path, monkeypatch=monkeypatch)


# --- Given: per-gate fixture staging (one per slice) --------------------------


@given("a feature whose committed tree fails a fresh-clone build")
def given_fresh_clone_broken_build(composition: FeatureEndP0GateComposition) -> None:
    composition.given_fresh_clone_broken_build()


@given("a feature that ships a production file with zero recorded executions")
def given_never_executed_production_file(
    composition: FeatureEndP0GateComposition,
) -> None:
    composition.given_never_executed_production_file()


@given("a feature whose shipped docs claim a script and a file that do not exist")
def given_docs_overstating_absent_code(
    composition: FeatureEndP0GateComposition,
) -> None:
    composition.given_docs_overstating_absent_code()


# --- When: production-code invocation (shared across all three slices) -------


@when("the nWave maintainer runs the feature-end cycle")
def when_feature_end_cycle_runs(composition: FeatureEndP0GateComposition) -> None:
    composition.when_feature_end_cycle_runs()


# --- Then: universe-bound assertions over the port-exposed observable -------


@then("the feature-end cycle refuses to sign the feature as done")
def then_cycle_is_refused(composition: FeatureEndP0GateComposition) -> None:
    composition.then_cycle_is_refused()


@then(parsers.parse("the refusal names the {gate_name} gate"))
def then_refusal_names_gate(
    composition: FeatureEndP0GateComposition, gate_name: str
) -> None:
    composition.then_refusal_names_gate(GATE_NAME_BY_PHRASE[gate_name].value)


@then("no feature-end verdict is recorded")
def then_no_feature_end_verdict_recorded(
    composition: FeatureEndP0GateComposition,
) -> None:
    composition.then_no_feature_end_verdict_recorded()


@then("the feature-end cycle signs the feature as done")
def then_cycle_signs_as_done(composition: FeatureEndP0GateComposition) -> None:
    composition.then_cycle_signs_as_done()


@then("the doc-coherence findings are recorded as a warning naming the violation")
def then_doc_coherence_warning_recorded(
    composition: FeatureEndP0GateComposition,
) -> None:
    composition.then_doc_coherence_warning_recorded()


@then("the warning is never recorded as doc-coherence verified clean")
def then_warning_never_reads_as_verified_clean(
    composition: FeatureEndP0GateComposition,
) -> None:
    composition.then_warning_never_reads_as_verified_clean()
