"""pytest-bdd binding for csharp-test-runner-adapter slice-01 scenarios.

Driving surface (Mandate-13 driving-port-only, Layer 3 subprocess): the REAL
production slice-01 SUTs (the C# run-facet ``run_csharp_scope``, the
AT-discovery facet ``discover_csharp_ats``, and the routing registry
``resolve()``) imported + invoked in a child interpreter over a GENUINE
controlled filesystem + FAKE-``dotnet`` executable. Step bodies delegate to the
composition root (``composition_slice_01_csharp_runner.py``); no business logic
in step bodies (Mandate-12 criterion 3).

ZERO ``des.adapters.*`` import in THIS process: the SUT is only imported in the
child interpreter (inside the composition root's ``python -c`` probe), never
here.

Active-RED scaffold (atdd_pure -- NOT @skip): AC-1..5 RED until DELIVER ships
``csharp_runner.py``. At HEAD the module is absent, so the child probe import
raises ModuleNotFoundError THERE (rc != 0, no marker); the observable effect
never happens, so each Then fails with a semantic AssertionError, never a
collection / import error. AC-6 (the resolve() glob-routing rows) is
LIVE-GREEN at HEAD -- it is authored directly by this feature, never gated
behind csharp_runner.py.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_01_csharp_runner import (
    _TWO_AT_CSHARP_EXPECTED_IDS,
    CSharpRunnerComposition,
)
from .domain_types_csharp_runner import DotnetExitScenario, ManifestKind, RunnerVerdict


scenarios("../slice-01-csharp-runner.feature")


@pytest.fixture
def csharp() -> CSharpRunnerComposition:
    return CSharpRunnerComposition()


# --- Given -------------------------------------------------------------------


@given("a C# target whose dotnet test exits zero with all tests passing")
def given_csharp_green(csharp: CSharpRunnerComposition) -> None:
    csharp.given_target_with_fake_dotnet(DotnetExitScenario.GREEN)


@given("a C# target whose dotnet test exits non-zero after executing tests")
def given_csharp_red(csharp: CSharpRunnerComposition) -> None:
    csharp.given_target_with_fake_dotnet(DotnetExitScenario.RED)


@given("a C# target whose dotnet is absent from PATH and every known location")
def given_csharp_dotnet_absent(csharp: CSharpRunnerComposition) -> None:
    csharp.given_target_with_dotnet_absent_everywhere()


@given("a C# regression file declaring two [Fact] test methods")
def given_csharp_regression_two_tests(csharp: CSharpRunnerComposition) -> None:
    csharp.given_csharp_regression_file_with_two_tests()


@given("a C# regression file declaring zero [Fact] test methods")
def given_csharp_regression_zero_tests(csharp: CSharpRunnerComposition) -> None:
    csharp.given_csharp_regression_file_with_zero_tests()


@given(parsers.parse("a target carrying only a {manifest} manifest"))
def given_dotnet_manifest_only_target(
    csharp: CSharpRunnerComposition, manifest: str
) -> None:
    csharp.given_target_with_only_manifest(ManifestKind(manifest))


# --- When ----------------------------------------------------------------


@when("the C# run-facet runs the declared command")
def when_csharp_run_facet_runs(csharp: CSharpRunnerComposition) -> None:
    csharp.when_the_run_facet_runs_the_command()


@when("the C# AT-discovery facet discovers the file's acceptance tests")
def when_csharp_at_discovery_runs(csharp: CSharpRunnerComposition) -> None:
    csharp.when_the_at_discovery_facet_discovers_ats()


@when("the target's test runner is resolved")
def when_target_runner_resolved(csharp: CSharpRunnerComposition) -> None:
    csharp.when_the_target_runner_is_resolved()


# --- Then ------------------------------------------------------------------


@then(parsers.parse("the run verdict is {verdict}"))
def then_csharp_run_verdict_is(csharp: CSharpRunnerComposition, verdict: str) -> None:
    csharp.then_the_verdict_is(RunnerVerdict(verdict))


@then("the indeterminate result names the remediation")
def then_csharp_indeterminate_names_remediation(
    csharp: CSharpRunnerComposition,
) -> None:
    csharp.then_the_indeterminate_names_the_remediation()


@then("the discovered AT identities match the declared [Fact] methods")
def then_csharp_discovered_ids_match(csharp: CSharpRunnerComposition) -> None:
    csharp.then_the_discovered_at_ids_match(_TWO_AT_CSHARP_EXPECTED_IDS)


@then("the discovery result carries a content seal over the regression file's bytes")
def then_csharp_discovery_content_seal(csharp: CSharpRunnerComposition) -> None:
    csharp.then_the_discovery_carries_a_content_seal()


@then("the discovery degrades to a loud indeterminate naming the malformed file")
def then_csharp_discovery_degrades_loud(csharp: CSharpRunnerComposition) -> None:
    csharp.then_the_discovery_degrades_loud_naming_the_malformed_file()


@then(parsers.parse("the resolved runner is {runner}"))
def then_csharp_resolved_runner_is(
    csharp: CSharpRunnerComposition, runner: str
) -> None:
    csharp.then_the_resolved_runner_is(runner)
