"""pytest-bdd binding for f-attest-bundled-slice slice-01 scenarios.

Driving surface (Mandate-13 driving-port-only, Layer 3 subprocess): the REAL
``des`` dispatcher via the production CLI dispatcher; for the shared-core
scenarios, the production modules imported in a child interpreter and reverify's
existing acceptance suite re-run as a child pytest. Step bodies delegate to the
composition root (``composition_slice_01_scaffold.py``); no business logic in
step bodies (Mandate-12 criterion 3). The ``<outcome>`` token is parsed into the
typed ``AttestExit`` enum, so the step template ranges over the typed domain
vocabulary (DSL emergence, not decorator proliferation).

Active-RED scaffold (atdd_pure -- NOT @skip): RED until DELIVER ships the
``_reverify_core`` extraction + registers the ``attest-bundled-slice`` row +
ships ``src/des/cli/attest_bundled_slice.py`` with ``--reason required=True``. At
HEAD the unregistered subcommand yields ``invalid choice`` (exit 2) and the
shared-core module is absent; the observable effect never happens, so each Then
fails with a semantic AssertionError, never a collection / import error.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_01_scaffold import AttestScaffoldComposition
from .domain_types_attest_bundled_slice import AttestExit


scenarios("../slice-01-shared-core-and-cli-scaffold.feature")


@pytest.fixture
def attest() -> AttestScaffoldComposition:
    return AttestScaffoldComposition()


# --- Given -----------------------------------------------------------------


@given("the maintainer omits the mandatory reason on the attestation")
def given_reason_omitted(attest: AttestScaffoldComposition) -> None:
    attest.given_reason_omitted()


# --- When ------------------------------------------------------------------


@when("the maintainer runs the bundled-slice attestation command")
def when_operator_runs_attest(attest: AttestScaffoldComposition) -> None:
    attest.when_operator_runs_attest()


@when("the maintainer imports the shared reverify core")
def when_the_shared_core_is_imported(attest: AttestScaffoldComposition) -> None:
    attest.when_the_shared_core_is_imported()


@when("the maintainer re-runs reverify's existing acceptance suite")
def when_the_reverify_suite_is_rerun(attest: AttestScaffoldComposition) -> None:
    attest.when_the_reverify_suite_is_rerun()


# --- Then ------------------------------------------------------------------


@then("the dispatcher recognizes the bundled-slice attestation subcommand")
def then_subcommand_recognized(attest: AttestScaffoldComposition) -> None:
    attest.then_attest_subcommand_is_recognized()


@then(parsers.parse("the attestation command exits with the {outcome} outcome"))
def then_attest_exits(attest: AttestScaffoldComposition, outcome: str) -> None:
    attest.then_attest_exits_with(AttestExit[outcome])


@then("the usage error names the mandatory reason argument")
def then_usage_error_names_reason(attest: AttestScaffoldComposition) -> None:
    attest.then_usage_error_names_the_reason()


@then("the shared core exposes every reused reverify helper to both commands")
def then_shared_core_exposes_symbols(attest: AttestScaffoldComposition) -> None:
    attest.then_shared_core_exposes_reused_symbols()


@then("reverify's existing acceptance suite stays green after the core extraction")
def then_reverify_behaviour_preserved(attest: AttestScaffoldComposition) -> None:
    attest.then_reverify_behaviour_is_preserved()
