"""A zero exit status with a JUnit report recording errors/failures must not
be GREEN.

CONCRETE HOST REPRODUCTION (des-fixes-sonnet-20260917 batch, 2026-09-17):
`DeliveryContinuationRunner._oracle_verdict(0, (1, 0, 1), False)` and
`_oracle_verdict(0, (1, 1, 0), False)` both returned `("green",
"junit-report")`. A native oracle whose process exits 0 while its own JUnit
report records a failed or errored test case is silently accepted as GREEN.

WHY: `_oracle_verdict`'s prior branch order checked `if not exit_status:
return "green", "junit-report"` BEFORE reading `counts` (tests, errors,
failures) at all. A clean process exit therefore always won the verdict,
even when the report the runner itself just measured disagreed with it.

HOW (the fix): read `counts` before trusting a zero exit. An error in the
report makes the verdict `broken` (an oracle whose own report says it never
reached its assertion, per the same "error report broken" convention already
applied on the nonzero-exit path). A failure with a zero exit is a genuine
contradiction between the two axes and is classified `indeterminate` /
`junit-report-contradicts-exit-status` -- the SAME conservative designation
the runner already gives the mirror contradiction (nonzero exit, clean
report) two lines below. Never `green` with a reported error or failure.

SCOPE: this file owns exactly the correction to `_oracle_verdict`. It does
not touch `_junit_counts`, `_executed_oracle_set`'s indeterminate-routing, or
report-count semantics beyond what the classifier already declares.
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from des.application.delivery_continuation import (
    AuthorityFacts,
    DeliveryContinuationRunner,
    DeliveryOutcome,
    Disposition,
)


# ---------------------------------------------------------------------------
# 1. Classifier-level cases: the exact two host reproductions plus their
#    nonzero-exit mirrors, and the existing valid controls that must not move.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("exit_status", "counts", "report_requested"),
    [
        (0, (1, 0, 1), False),  # exact host reproduction: 1 failure, exit 0
        (0, (1, 1, 0), False),  # exact host reproduction: 1 error, exit 0
        (0, (1, 0, 1), True),  # same contradiction, pytest-style report
        (0, (1, 1, 0), True),  # same contradiction, pytest-style report
    ],
)
def test_zero_exit_with_reported_failure_or_error_is_never_green(
    exit_status: int, counts: tuple[int, int, int], report_requested: bool
) -> None:
    verdict, axis = DeliveryContinuationRunner._oracle_verdict(
        exit_status, counts, report_requested
    )
    assert verdict != "green", (
        f"WHAT: _oracle_verdict({exit_status!r}, {counts!r}, "
        f"{report_requested!r}) returned verdict={verdict!r} axis={axis!r}\n"
        f"WHY: the report counts {counts} record a failure or error the exit "
        f"status alone cannot see; a zero exit must never outrank a report "
        f"that disagrees with it\n"
        f"HOW: read counts (errors, failures) before trusting a zero exit"
    )


def test_zero_exit_with_reported_error_is_broken() -> None:
    # errors -> broken is the SAME convention `_oracle_verdict` already
    # applies on its nonzero-exit path two branches below; a zero exit must
    # not exempt an errored report from that same designation.
    verdict, axis = DeliveryContinuationRunner._oracle_verdict(0, (1, 1, 0), False)
    assert (verdict, axis) == ("broken", "junit-report"), (verdict, axis)


def test_zero_exit_with_reported_failure_is_indeterminate_contradiction() -> None:
    # A failure with a clean exit is a genuine two-axis contradiction, so it
    # earns the SAME conservative designation the mirror contradiction
    # (nonzero exit, clean report) already earns just below in the method.
    verdict, axis = DeliveryContinuationRunner._oracle_verdict(0, (1, 0, 1), False)
    assert (verdict, axis) == (
        "indeterminate",
        "junit-report-contradicts-exit-status",
    ), (
        verdict,
        axis,
    )


# --- existing valid controls: this correction must not move any of these ---


def test_clean_zero_exit_with_clean_report_stays_green() -> None:
    verdict, axis = DeliveryContinuationRunner._oracle_verdict(0, (3, 0, 0), False)
    assert (verdict, axis) == ("green", "junit-report")


def test_nonzero_exit_with_reported_failure_stays_red() -> None:
    verdict, axis = DeliveryContinuationRunner._oracle_verdict(1, (3, 0, 1), True)
    assert (verdict, axis) == ("red", "junit-report")


def test_nonzero_exit_with_reported_error_stays_broken() -> None:
    verdict, axis = DeliveryContinuationRunner._oracle_verdict(1, (3, 1, 0), True)
    assert (verdict, axis) == ("broken", "junit-report")


def test_nonzero_exit_with_clean_report_stays_the_existing_contradiction() -> None:
    verdict, axis = DeliveryContinuationRunner._oracle_verdict(1, (3, 0, 0), True)
    assert (verdict, axis) == ("indeterminate", "junit-report-contradicts-exit-status")


def test_native_tool_success_exit_with_no_report_stays_green() -> None:
    verdict, axis = DeliveryContinuationRunner._oracle_verdict(0, None, False)
    assert (verdict, axis) == ("green", "exit-status-only")


def test_native_tool_nonzero_exit_with_no_report_stays_indeterminate() -> None:
    verdict, axis = DeliveryContinuationRunner._oracle_verdict(1, None, False)
    assert (verdict, axis) == ("indeterminate", "exit-status-only")


def test_missing_exit_status_stays_broken() -> None:
    verdict, axis = DeliveryContinuationRunner._oracle_verdict(None, None, False)
    assert (verdict, axis) == ("broken", "exit-status")


def test_requested_report_absent_stays_broken() -> None:
    verdict, axis = DeliveryContinuationRunner._oracle_verdict(0, None, True)
    assert (verdict, axis) == ("broken", "junit-report-absent")


def test_zero_executed_tests_with_zero_exit_is_unaffected_by_this_fix() -> None:
    # Zero executed tests (tests=0, errors=0, failures=0) is an EXISTING
    # semantic this correction does not touch or broaden: a report that
    # genuinely ran nothing, with a clean exit, still reads as `green` per
    # the pre-existing branch this fix does not reorder past the count check.
    verdict, axis = DeliveryContinuationRunner._oracle_verdict(0, (0, 0, 0), False)
    assert (verdict, axis) == ("green", "junit-report")


# ---------------------------------------------------------------------------
# 2. Service integration fixture reproduction through the real production
#    flow (`_executed_oracle_set`), with a genuine JUnit XML report on disk
#    and a genuine native (non-pytest) executable, exactly matching the host
#    reproduction's `report_requested=False` shape. This exercises the
#    private application service directly -- it is NOT a full CLI proof;
#    no `des` command line is invoked and no process boundary outside this
#    interpreter is crossed.
# ---------------------------------------------------------------------------


def _fake_native_oracle(root: Path) -> Path:
    """A tool that is NOT pytest, exits 0, yet writes a JUnit report with one
    failed test case to the `--junitxml=` path the runner places in
    `PYTEST_ADDOPTS` for exactly this purpose.

    This is not a pytest invocation (`invokes_pytest` sees no `pytest` token
    in its argv), so it exercises the SAME `report_requested=False` axis the
    two exact host reproductions above were measured on -- but through the
    real production service call (`_executed_oracle_set`), with a genuine
    file on disk, not only the classifier called directly. This is service
    integration, not a full CLI proof: no `des` executable is invoked.
    """
    script = root / "bin" / "fake-native-oracle"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        "#!/bin/sh\n"
        "report=$(printf '%s' \"$PYTEST_ADDOPTS\" | sed -n 's/.*--junitxml=\\([^ ]*\\).*/\\1/p')\n"
        "cat > \"$report\" <<'XML'\n"
        '<testsuite tests="1" errors="0" failures="1">'
        '<testcase classname="fake" name="reports_failure">'
        '<failure message="the assertion the oracle checks was not met" />'
        "</testcase></testsuite>\n"
        "XML\n"
        "exit 0\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


def test_native_oracle_with_zero_exit_and_reported_failure_is_not_green_via_service(
    tmp_path: Path,
) -> None:
    root = tmp_path / "subject"
    root.mkdir()
    fake_checker = _fake_native_oracle(root)

    oracle_locator = "tests/acceptance/fake_oracle.check"
    declared_argv = (str(fake_checker),)
    authority = AuthorityFacts(
        locator="docs/architecture.md#native oracle contradicts its own exit status",
        modified_authority_paths=(),
        target_decisions=(("src/answer.py", "CREATE_NEW"),),
        paradigm="object_oriented",
        decisions=(),
        obligations=(),
        acceptance_oracle_locator=oracle_locator,
        acceptance_paths=(oracle_locator,),
        native_verification_argvs=(declared_argv,),
        oracle_verification_index=0,
    )

    runner = DeliveryContinuationRunner()
    measured = runner._executed_oracle_set(root, [("the observation", authority)])

    # The corrected classifier makes this contradiction `indeterminate`
    # (never `green`), and `_executed_oracle_set` already routes an
    # `indeterminate` verdict on a non-`exit-status-only` axis straight to a
    # `Disposition.Indeterminate` outcome -- the SAME handling the mirror
    # contradiction (nonzero exit, clean report) already receives. Reaching
    # THAT outcome, rather than a silent `OracleExecution` with a `green`
    # row, is the service-integration proof the bug is fixed.
    assert isinstance(measured, DeliveryOutcome), (
        f"WHAT: through the _executed_oracle_set service call, a native oracle "
        f"that exited 0 while its own JUnit report recorded 1 failure "
        f"produced {measured!r} instead of an Indeterminate DeliveryOutcome\n"
        f"WHY: this reproduces the exact host bug -- a zero process exit "
        f"must never outrank a report the runner itself just measured\n"
        f"HOW: `_oracle_verdict` must read counts before trusting a zero exit"
    )
    assert measured.disposition == Disposition.Indeterminate, measured
    assert (
        measured.failure is not None
        and measured.failure.what == "OracleRedUnobservable"
    ), measured.failure
    assert measured.failure.why.startswith(oracle_locator), measured.failure
