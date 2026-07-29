"""pytest-bdd binding for cpp-test-runner-adapter slice-01 scenarios.

Driving surface (Mandate-13 driving-port-only, Layer 3 subprocess): the REAL
production slice-01 SUTs (the C++ run-facet ``run_cpp_scope`` and the
AT-discovery facet ``discover_cpp_ats``) imported + invoked in a child
interpreter over a GENUINE controlled filesystem + FAKE-``make`` executable (for
the run-facet scenarios) or the REAL polyglot pilot fixture files (for the
AT-discovery scenarios). Step bodies delegate to the composition root
(``composition_slice_01_cpp_runner.py``); no business logic in step bodies
(Mandate-12 criterion 3).

ZERO ``des.adapters.*`` import in THIS process: the SUT is only imported in the
child interpreter (inside the composition root's ``python -c`` probe), never
here.

Active-RED scaffold (atdd_pure -- NOT @skip): RED until DELIVER ships
``cpp_runner.py``. At HEAD the module is absent, so the child probe import
raises ModuleNotFoundError THERE (rc != 0, no marker); the observable effect
never happens, so each Then fails with a semantic AssertionError, never a
collection / import error.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_01_cpp_runner import (
    _TWO_TEST_EXPECTED_IDS,
    CppRunnerComposition,
)
from .domain_types_cpp_runner import MakeExitScenario, RunnerVerdict


scenarios("../slice-01-cpp-runner.feature")


@pytest.fixture
def cpp() -> CppRunnerComposition:
    return CppRunnerComposition()


# --- Given -------------------------------------------------------------------


@given("a C++ target whose make test exits zero with all tests passing")
def given_cpp_green(cpp: CppRunnerComposition) -> None:
    cpp.given_target_with_fake_make(MakeExitScenario.GREEN)


@given("a C++ target whose make test exits non-zero after executing tests")
def given_cpp_red(cpp: CppRunnerComposition) -> None:
    cpp.given_target_with_fake_make(MakeExitScenario.RED)


@given("a C++ target whose make is absent from PATH and every known location")
def given_cpp_make_absent(cpp: CppRunnerComposition) -> None:
    cpp.given_target_with_make_absent_everywhere()


@given("the real polyglot pilot regression file declaring two TEST cases")
def given_cpp_pilot_two_tests(cpp: CppRunnerComposition) -> None:
    cpp.given_real_pilot_file_with_two_tests()


@given("the real polyglot pilot regression file declaring zero TEST cases")
def given_cpp_pilot_zero_tests(cpp: CppRunnerComposition) -> None:
    cpp.given_real_pilot_file_with_zero_tests()


# --- When ----------------------------------------------------------------


@when("the C++ run-facet runs the declared command")
def when_cpp_run_facet_runs(cpp: CppRunnerComposition) -> None:
    cpp.when_the_run_facet_runs_the_command()


@when("the C++ AT-discovery facet discovers the file's acceptance tests")
def when_cpp_at_discovery_runs(cpp: CppRunnerComposition) -> None:
    cpp.when_the_at_discovery_facet_discovers_ats()


# --- Then ------------------------------------------------------------------


@then(parsers.parse("the run verdict is {verdict}"))
def then_cpp_run_verdict_is(cpp: CppRunnerComposition, verdict: str) -> None:
    cpp.then_the_verdict_is(RunnerVerdict(verdict))


@then("the indeterminate result names the remediation")
def then_cpp_indeterminate_names_remediation(cpp: CppRunnerComposition) -> None:
    cpp.then_the_indeterminate_names_the_remediation()


@then("the discovered AT identities match the declared TEST cases")
def then_cpp_discovered_ids_match(cpp: CppRunnerComposition) -> None:
    cpp.then_the_discovered_at_ids_match(_TWO_TEST_EXPECTED_IDS)


@then("the discovery result carries a content seal over the regression file's bytes")
def then_cpp_discovery_content_seal(cpp: CppRunnerComposition) -> None:
    cpp.then_the_discovery_carries_a_content_seal()


@then("the discovery degrades to a loud indeterminate naming the malformed file")
def then_cpp_discovery_degrades_loud(cpp: CppRunnerComposition) -> None:
    cpp.then_the_discovery_degrades_loud_naming_the_malformed_file()
