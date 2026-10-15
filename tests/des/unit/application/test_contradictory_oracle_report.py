"""Captured native/report assertions must not be overruled by process exit alone."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from des.application.delivery_continuation import (
    DeliveryContinuationRunner,
    DeliveryOutcome,
    Disposition,
)
from des.domain.oracle_observation import (
    ObservationUnavailable,
    OracleObservation,
    OracleObservationKind,
    observation_from_counts,
)
from tests.des.unit.application.test_authored_oracle_is_executed_red import (
    execution_authority,
    oracle_manifest,
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
        exit_status,
        observation_from_counts(counts[0], counts[2], counts[1], source="junit-report"),
        completed=True,
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
    verdict, axis = DeliveryContinuationRunner._oracle_verdict(
        0, observation_from_counts(1, 0, 1, source="junit-report"), completed=True
    )
    assert (verdict, axis) == ("broken", "junit-report"), (verdict, axis)


def test_zero_exit_with_reported_failure_is_indeterminate_contradiction() -> None:
    # A failure with a clean exit is a genuine two-axis contradiction, so it
    # earns the SAME conservative designation the mirror contradiction
    # (nonzero exit, clean report) already earns just below in the method.
    verdict, axis = DeliveryContinuationRunner._oracle_verdict(
        0, observation_from_counts(1, 1, 0, source="junit-report"), completed=True
    )
    assert (verdict, axis) == (
        "indeterminate",
        "junit-report-contradicts-exit-status",
    ), (
        verdict,
        axis,
    )


# --- existing valid controls: this correction must not move any of these ---


@pytest.mark.parametrize("source", ["native-observation", "junit-report"])
def test_clean_zero_exit_with_positive_observation_stays_green(source: str) -> None:
    verdict, axis = DeliveryContinuationRunner._oracle_verdict(
        0, observation_from_counts(3, 0, 0, source=source), completed=True
    )
    assert (verdict, axis) == ("green", source)


def test_nonzero_exit_with_reported_failure_stays_red() -> None:
    verdict, axis = DeliveryContinuationRunner._oracle_verdict(
        1, observation_from_counts(3, 1, 0, source="junit-report"), completed=True
    )
    assert (verdict, axis) == ("red", "junit-report")


def test_nonzero_exit_with_reported_error_stays_broken() -> None:
    verdict, axis = DeliveryContinuationRunner._oracle_verdict(
        1, observation_from_counts(3, 0, 1, source="junit-report"), completed=True
    )
    assert (verdict, axis) == ("broken", "junit-report")


def test_nonzero_exit_with_clean_report_stays_the_existing_contradiction() -> None:
    verdict, axis = DeliveryContinuationRunner._oracle_verdict(
        1, observation_from_counts(3, 0, 0, source="junit-report"), completed=True
    )
    assert (verdict, axis) == ("indeterminate", "junit-report-contradicts-exit-status")


def test_native_tool_success_exit_without_observation_is_indeterminate() -> None:
    verdict, axis = DeliveryContinuationRunner._oracle_verdict(
        0,
        OracleObservation(OracleObservationKind.Missing, "native-observation"),
        completed=True,
    )
    assert (verdict, axis) == ("indeterminate", "native-observation-no-observation")


def test_native_tool_nonzero_exit_with_no_report_stays_indeterminate() -> None:
    verdict, axis = DeliveryContinuationRunner._oracle_verdict(
        1,
        OracleObservation(OracleObservationKind.Missing, "native-observation"),
        completed=True,
    )
    assert (verdict, axis) == ("indeterminate", "exit-status-only")


def test_missing_exit_status_stays_broken() -> None:
    verdict, axis = DeliveryContinuationRunner._oracle_verdict(
        None,
        OracleObservation(OracleObservationKind.Missing, "native-observation"),
        completed=False,
    )
    assert (verdict, axis) == ("broken", "exit-status")


def test_requested_report_absent_stays_broken() -> None:
    verdict, axis = DeliveryContinuationRunner._oracle_verdict(
        0,
        ObservationUnavailable("junit-report-absent", "requested report absent"),
        completed=True,
    )
    assert (verdict, axis) == ("broken", "junit-report-absent")


@pytest.mark.parametrize("source", ["native-observation", "junit-report"])
def test_zero_completed_observations_with_zero_exit_is_indeterminate(
    source: str,
) -> None:
    verdict, axis = DeliveryContinuationRunner._oracle_verdict(
        0, observation_from_counts(0, 0, 0, source=source), completed=True
    )
    assert (verdict, axis) == ("indeterminate", f"{source}-no-observation")


# ---------------------------------------------------------------------------
# 2. Service integration fixture reproduction through the real production
#    flow (`_executed_oracle_set`), with a genuine JUnit XML report on disk
#    requested explicitly in a native (non-pytest) executable's declared argv.
#    The process really executes; no mock supplies the report or exit status.
# ---------------------------------------------------------------------------


def _fake_native_oracle(root: Path, exit_status: int, produces_report: bool) -> Path:
    """A native checker writes only to its explicitly declared report output."""
    script = root / "bin" / "fake-native-oracle"
    script.parent.mkdir(parents=True, exist_ok=True)
    report_body = (
        "report=${1#--junitxml=}\n"
        "cat > \"$report\" <<'XML'\n"
        '<testsuite tests="1" errors="0" failures="1">'
        '<testcase classname="fake" name="reports_failure">'
        '<failure message="the assertion the oracle checks was not met" />'
        "</testcase></testsuite>\n"
        "XML\n"
    )
    script.write_text(
        "#!/bin/sh\n"
        + (report_body if produces_report else "")
        + f"exit {exit_status}\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


@pytest.mark.parametrize(
    ("exit_status", "produces_report", "expected"),
    [
        (0, True, ("indeterminate", "junit-report-contradicts-exit-status")),
        (101, True, ("red", "junit-report")),
        (0, False, ("indeterminate", "junit-report-invalid")),
    ],
)
def test_native_oracle_judges_its_explicit_report_without_pytest_exit_conventions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exit_status: int,
    produces_report: bool,
    expected: tuple[str, str],
) -> None:
    verdict, axis = expected
    root = tmp_path / "subject"
    root.mkdir()
    monkeypatch.delenv("PYTHONPATH", raising=False)
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    fake_checker = _fake_native_oracle(root, exit_status, produces_report)
    report = root / "native-report.xml"
    # A report from an earlier execution cannot stand in for this observation.
    report.write_text('<testsuite tests="1" errors="0" failures="1"/>')

    oracle_locator = "tests/acceptance/fake_oracle.check"
    declared_argv = (str(fake_checker), "--junitxml=native-report.xml")
    authority = execution_authority(
        root,
        oracle_manifest(
            "Native oracle contradicts its own exit status.",
            oracle=oracle_locator,
            targets=(("src/answer.py", "CREATE_NEW"),),
            verification=(declared_argv,),
        ),
    )

    runner = DeliveryContinuationRunner()
    measured = runner._executed_oracle_set(root, [("the observation", authority)])

    records = list((root / ".nwave/des/logs/native").glob("oracle-*.json"))
    retained = json.loads(records[0].read_text())[0]
    assert retained["argv"] == list(declared_argv)
    assert retained["exit"] == exit_status
    assert all(
        retained["declared_environment"].get(name) == os.environ.get(name)
        for name in ("PYTEST_ADDOPTS", "PYTHONPATH")
    )
    assert not isinstance(measured, DeliveryOutcome), measured
    assert measured.measured[0]["verdict"] == verdict
    assert measured.measured[0]["axis"] == axis
    assert measured.measured[0]["counts"] == ((1, 0, 1) if produces_report else None)
    if verdict == "indeterminate":
        assert measured.refusal is not None
        outcome = measured.refusal.terminal
        assert outcome.disposition is Disposition.Indeterminate
        assert outcome.failure.what == "OracleRedUnobservable"
        assert outcome.failure.why.startswith(oracle_locator)
    else:
        assert (measured.refusal is not None) is (verdict == "broken")
