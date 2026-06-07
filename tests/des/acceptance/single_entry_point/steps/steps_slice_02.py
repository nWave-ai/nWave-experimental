"""Step methods for slice-02 — every subcommand reachable through the dispatcher.

Mandate-12 criterion 3: every step body has ≤ 2 statements, the last is a
delegation to `composition.<method>(...)`, no control flow in bodies. All
business logic lives in `composition.py`.

Pillar 1: step names speak the domain (operator, asks, runs, bundle scan).
NO technical jargon (no "subprocess", "argparse", "AST"). Technical detail
lives behind the composition methods.

Pillar 2: chained narrative — every scenario reuses the Background's
Given_the_nwave_runtime_is_installed from steps_slice_01. The When/Then
chain reads as a sequential operator story per subcommand.

Mandate 9 + 11: layer 3 subprocess + AST — example-only, NO PBT machinery.
Parametrize-collapse over SUBCOMMAND_TABLE: 16 subcommands × 2 outlines =
32 assertions through 2 scenarios.
"""

from __future__ import annotations

from pytest_bdd import parsers, then, when

from .composition import DesCliComposition, DesInvocation


# Feature binding lives in `../test_slice_02_all_subcommands_wired.py` — that
# binder calls `scenarios(...)` after the pytest config stack is active.


# ---- When ---------------------------------------------------------------


@when(
    parsers.parse('the operator asks the "{subcommand}" subcommand for its help'),
    target_fixture="invocation",
)
def when_the_operator_asks_the_subcommand_for_help(
    installed_runtime: DesCliComposition,
    subcommand: str,
) -> DesInvocation:
    return installed_runtime.run_subcommand_help(subcommand)


@when(
    parsers.parse(
        'the operator runs the "{subcommand}" subcommand with an unknown flag'
    ),
    target_fixture="invocation",
)
def when_the_operator_runs_the_subcommand_with_unknown_flag(
    installed_runtime: DesCliComposition,
    subcommand: str,
) -> DesInvocation:
    return installed_runtime.run_subcommand_with_unknown_flag(subcommand)


@when(
    "the bundle scan inspects the shipped des package",
    target_fixture="forbidden_imports",
)
def when_the_bundle_scan_inspects_the_shipped_des_package(
    installed_runtime: DesCliComposition,
) -> tuple[str, ...]:
    return installed_runtime.dispatcher_third_party_imports()


# ---- Then ---------------------------------------------------------------


@then("the subcommand exits successfully")
def then_the_subcommand_exits_successfully(invocation: DesInvocation) -> None:
    assert invocation.exit_code == 0, (
        f"subcommand --help exited {invocation.exit_code}. "
        f"stdout:\n{invocation.stdout}\nstderr:\n{invocation.stderr}"
    )


@then(parsers.parse('the help output names the "{subcommand}" prog name'))
def then_the_help_output_names_the_subcommand(
    invocation: DesInvocation,
    subcommand: str,
) -> None:
    assert subcommand in invocation.stdout, (
        f"des {subcommand} --help did not name the subcommand in its prog "
        f"line. stdout:\n{invocation.stdout}"
    )


@then(parsers.parse("the subcommand exits with the underlying argparse exit code 2"))
def then_the_subcommand_exits_argparse_exit_code_2(
    invocation: DesInvocation,
) -> None:
    assert invocation.exit_code == 2, (
        f"des <subcommand> --__nwave_unknown_flag exited "
        f"{invocation.exit_code} instead of 2. stderr:\n{invocation.stderr}"
    )


@then("the bundle scan reports no forbidden import was added by the dispatcher")
def then_the_bundle_scan_reports_no_forbidden_import(
    forbidden_imports: tuple[str, ...],
) -> None:
    assert forbidden_imports == (), (
        f"des dispatcher (src/des/cli/__main__.py) imports forbidden "
        f"third-party modules: {forbidden_imports}. The dispatcher MUST stay "
        f"stdlib-only at import time per DDD-2."
    )


@then("the existing forbidden-import set remains the contract surface")
def then_the_existing_forbidden_import_set_remains_the_contract_surface(
    forbidden_imports: tuple[str, ...],
) -> None:
    # Re-assert the empty-set invariant. AT-06 second clause is the
    # contract-shape:unbounded-preservation conjunct: the existing bundle-
    # scan contract (stdlib-only) is preserved by the dispatcher's addition.
    assert forbidden_imports == (), (
        f"bundle-scan contract regression: {forbidden_imports} appeared "
        f"after the dispatcher landed."
    )
