"""slice-05 step definitions — PER-TEST .nwave STATE ISOLATION (parallelism restoration).

Driving surfaces (Mandate-13):
  * WALKING SKELETON / NO-MASK: a hermetic `pytest -p xdist -n 2` subprocess over a
    generated fixture test-set (the subprocess is the SUT; no production module imported
    at the step boundary).
  * ISOLATION-OBSERVABLE / STALE-FLOOR / FALLBACK: the per-test `.nwave`-root RESOLVER
    entry point (`des.domain.nwave_root.resolve_nwave_root`).

Each step body delegates to the `NwaveIsolationDriver` composition (Mandate-12: ≤2
statements, no inline logic, no control flow).

Active-RED: at HEAD the resolver is a RED scaffold (`resolve_nwave_root()` raises
AssertionError) and the autouse per-test isolation fixture does not exist, so the
resolver-driven scenarios raise a clean AssertionError when they invoke the resolver and
the subprocess scenarios observe cross-test-interference where the WITH-isolation
contract demands all-isolated-green (MISSING_FUNCTIONALITY) — not an ImportError. DELIVER
makes these GREEN by landing the DES_PROJECT_DIR-preferring resolver + the autouse
isolation fixture; it does NOT unskip anything.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .slice_05_composition import NwaveIsolationDriver
from .slice_05_domain_types import IsolationVerdict, ParallelOutcome


scenarios("../slice-05-per-test-nwave-isolation.feature")


@pytest.fixture
def isolation_driver() -> NwaveIsolationDriver:
    return NwaveIsolationDriver()


# -- Given ------------------------------------------------------------------


@given("a parallel fixture suite that writes .nwave state under the isolation harness")
def given_suite_with_isolation(
    isolation_driver: NwaveIsolationDriver, tmp_path: Path
) -> None:
    isolation_driver.given_parallel_fixture_set_with_isolation(tmp_path)


@given(
    "a parallel fixture suite that writes .nwave state with the isolation harness disabled"
)
def given_suite_without_isolation(
    isolation_driver: NwaveIsolationDriver, tmp_path: Path
) -> None:
    isolation_driver.given_parallel_fixture_set_without_isolation(tmp_path)


@given("two tests run under the per-test .nwave isolation harness")
def given_two_tests_under_harness(
    isolation_driver: NwaveIsolationDriver, tmp_path: Path
) -> None:
    isolation_driver.given_two_tests_under_the_isolation_harness(tmp_path)


@given("a stale wave-active floor is left in the shared repo at session start")
def given_stale_floor(isolation_driver: NwaveIsolationDriver, tmp_path: Path) -> None:
    isolation_driver.given_a_stale_wave_floor_in_the_shared_repo(tmp_path)


@given("a test runs with no per-test .nwave override configured")
def given_no_override(isolation_driver: NwaveIsolationDriver, tmp_path: Path) -> None:
    isolation_driver.given_no_per_test_override_configured(tmp_path)


# -- When -------------------------------------------------------------------


@when("the parallel fixture suite runs under two workers")
def when_parallel_suite_runs(isolation_driver: NwaveIsolationDriver) -> None:
    isolation_driver.when_the_parallel_suite_runs()


@when("the resolver is asked for each test's .nwave root")
def when_resolver_asked_each(isolation_driver: NwaveIsolationDriver) -> None:
    isolation_driver.when_the_resolver_is_asked_for_each_tests_root()


@when("the resolver runs inside an isolated per-test root")
def when_resolver_in_isolated(isolation_driver: NwaveIsolationDriver) -> None:
    isolation_driver.when_the_resolver_runs_in_the_isolated_test()


@when("the resolver is asked for the .nwave root with no override")
def when_resolver_no_override(isolation_driver: NwaveIsolationDriver) -> None:
    isolation_driver.when_the_resolver_is_asked_with_no_override()


# -- Then -------------------------------------------------------------------


@then("every fixture test that writes .nwave state passes under the parallel workers")
def then_all_isolated_green(isolation_driver: NwaveIsolationDriver) -> None:
    isolation_driver.then_parallel_outcome_is(ParallelOutcome.ALL_ISOLATED_GREEN)


@then("a fixture test reports cross-worker .nwave state interference")
def then_cross_test_interference(isolation_driver: NwaveIsolationDriver) -> None:
    isolation_driver.then_parallel_outcome_is(ParallelOutcome.CROSS_TEST_INTERFERENCE)


@then(
    "the two tests resolve distinct per-test .nwave roots away from the shared repo cwd"
)
def then_per_test_isolated(isolation_driver: NwaveIsolationDriver) -> None:
    isolation_driver.then_isolation_verdict_is(IsolationVerdict.PER_TEST_ISOLATED)


@then("the isolated test's resolved .nwave root is free of the stale wave floor")
def then_stale_floor_no_leak(isolation_driver: NwaveIsolationDriver) -> None:
    isolation_driver.then_the_stale_floor_does_not_leak()


@then("the resolved .nwave root is the shared repo cwd root")
def then_shared_cwd_root(isolation_driver: NwaveIsolationDriver) -> None:
    isolation_driver.then_isolation_verdict_is(IsolationVerdict.SHARED_CWD_ROOT)
