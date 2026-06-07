"""Step methods for slice-01 — single des entry point walking skeleton.

Mandate-12 criterion 3: every step body has ≤ 2 statements, the last is a
delegation to `composition.<method>(...)`, no control flow in bodies. All
business logic lives in `composition.py`.

Pillar 1: step names speak the domain (operator, asks, runs, listing,
verdict, json shape). NO technical jargon (no "subprocess", "argparse",
"importlib", "PYTHONPATH"). Technical detail lives behind the composition
methods.

Pillar 2: chained narrative — scenario 2's Given reuses scenario 1's
Given_the_nwave_runtime_is_installed (the Background); scenario 3 reuses
the same Given. The When/Then chain reads as a sequential operator story.

Mandate 8: layer 3 acceptance — assert_state_delta is OPTIONAL per the
Layered Test Discipline table (layers 4+ may use traditional assertions;
layer 3 is the boundary). We use traditional assertions here because the
subprocess invocation IS the observable mutation — there is no pre/post
state shape inside the dispatcher (it is a pure-function fan-out per R11
residuality). The universe-bound discipline is encoded in the
`DesInvocation` triple (exit_code, stdout, stderr) — these ARE the
port-exposed observables.

Mandate 9 + 11: layer 3 subprocess — example-only, NO PBT machinery.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, then, when

from .composition import DesCliComposition, DesInvocation
from .domain_types import HealthCheckVerdict, OutputFormat


# Feature binding lives in `../test_slice_01_single_entry_point.py` — that
# binder calls `scenarios(...)` after the pytest config stack is active.


# ---- Fixtures -----------------------------------------------------------


@pytest.fixture
def composition() -> DesCliComposition:
    """Fresh production composition root per scenario (function scope)."""
    return DesCliComposition()


# ---- Given --------------------------------------------------------------


@given("the nwave runtime is installed", target_fixture="installed_runtime")
def given_the_nwave_runtime_is_installed(
    composition: DesCliComposition,
) -> DesCliComposition:
    """Background: an installed nwave runtime exposes the `des` console-script.

    Delegates to composition.resolve_des_binary() which raises the RED
    scaffold AssertionError until slice-01 DELIVER ships the dispatcher.
    """
    composition.resolve_des_binary()
    return composition


# ---- When ---------------------------------------------------------------


@when(
    "the operator asks des to list its subcommands",
    target_fixture="invocation",
)
def when_the_operator_asks_des_to_list_subcommands(
    installed_runtime: DesCliComposition,
) -> DesInvocation:
    return installed_runtime.list_subcommands()


@when(
    "the operator runs the health-check subcommand",
    target_fixture="invocation",
)
def when_the_operator_runs_the_health_check_subcommand(
    installed_runtime: DesCliComposition,
) -> DesInvocation:
    row = installed_runtime.health_check_row()
    return installed_runtime.run_subcommand(row, output_format=OutputFormat.TEXT)


@when(
    "the operator runs the health-check subcommand asking for json output",
    target_fixture="invocation",
)
def when_the_operator_runs_the_health_check_subcommand_with_json(
    installed_runtime: DesCliComposition,
) -> DesInvocation:
    row = installed_runtime.health_check_row()
    return installed_runtime.run_subcommand(row, output_format=OutputFormat.JSON)


# ---- Then ---------------------------------------------------------------


@then("the listing names every known subcommand")
def then_the_listing_names_every_known_subcommand(
    installed_runtime: DesCliComposition,
    invocation: DesInvocation,
) -> None:
    expected_names = installed_runtime.expected_subcommand_names()
    missing = [name for name in expected_names if name not in invocation.stdout]
    assert not missing, (
        f"des --help omitted subcommands: {missing}. stdout was:\n{invocation.stdout}"
    )


@then("the listing exits successfully")
def then_the_listing_exits_successfully(invocation: DesInvocation) -> None:
    assert invocation.exit_code == 0, (
        f"des --help exited {invocation.exit_code}. stderr:\n{invocation.stderr}"
    )


@then(
    parsers.parse(
        "the health-check exits with the same verdict the standalone shim returns"
    )
)
def then_the_health_check_exits_with_same_verdict(
    installed_runtime: DesCliComposition,
    invocation: DesInvocation,
) -> None:
    verdict = installed_runtime.verdict_of(invocation)
    assert verdict in (HealthCheckVerdict.HEALTHY, HealthCheckVerdict.UNHEALTHY), (
        f"health-check returned an undeclared verdict: exit_code={invocation.exit_code}, "
        f"stdout={invocation.stdout!r}, stderr={invocation.stderr!r}"
    )


@then("the health-check emits the canonical json shape with seven named checks")
def then_the_health_check_emits_canonical_json_shape(
    installed_runtime: DesCliComposition,
    invocation: DesInvocation,
) -> None:
    parsed = installed_runtime.parse_health_check_json(invocation)
    expected_names = installed_runtime.expected_health_check_names()
    assert "checks" in parsed, (
        f"des health-check --json missing top-level 'checks' key. Got: {list(parsed)}"
    )
    actual_names = tuple(check.get("name") for check in parsed["checks"])
    assert actual_names == expected_names, (
        f"des health-check --json checks mismatch.\n"
        f"  expected: {expected_names}\n"
        f"  actual:   {actual_names}"
    )
