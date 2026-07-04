"""P0.3 negative-AT mandate gate — the observed proofs, pinned as regression.

These tests ARE the evolution-plan P0.3 done-currency, made permanent: the
gate was proven by execution against a planted defect of its target class
(a critical scenario covered only by presence-only ATs — the GS-8 /
lyra-tsunami-4x class where "asserts the right output appears" passed every
code-reading review while nothing asserted the wrong output is NOT
produced), a compliant case, the Gherkin arm, the honest-N/A case, and the
degrade-LOUD case. Deleting the gate's logic turns these RED.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli.verify_negative_at import main


_PRESENCE_ONLY_PY = """\
import pytest


@pytest.mark.critical
def test_booking_confirmation_is_created():
    result = {"confirmation": "abc"}
    assert result["confirmation"] is not None


@pytest.mark.critical
def test_charge_record_exists_after_booking():
    charges = [{"id": 1}]
    assert len(charges) >= 1
"""

_NEGATIVE_BY_NAME_PY = """\

def test_unrelated_input_does_not_trigger_a_second_charge():
    charges = [{"id": 1}]
    assert len(charges) == 1
"""

_PRESENCE_ONLY_FEATURE = """\
Feature: Booking atomicity

  @critical
  Scenario: Successful booking creates exactly one charge
    Given a seat is available
    When the user books it
    Then a charge record exists
"""

_NEGATIVE_SCENARIO = """\

  @negative
  Scenario: A failed payment never produces a charge
    Given a seat is available
    When the payment is declined
    Then no charge record exists
"""


def _first_event(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    out: dict[str, object] = json.loads(capsys.readouterr().out.splitlines()[0])
    return out


def test_presence_only_critical_pytest_file_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """NEGATIVE proof: @critical happy-path ATs with zero negative ATs -> RED.

    The GS-8 class: every assertion says the expected output appears; none
    says the wrong output is NOT produced. The gate must exit 1 and NAME the
    offending scope with what/why/how.
    """
    test_file = tmp_path / "test_booking_atomicity.py"
    test_file.write_text(_PRESENCE_ONLY_PY)

    assert main(["--test-file", str(test_file)]) == 1
    event = _first_event(capsys)
    assert event["event"] == "NegativeAtRefused"
    assert all(k in event for k in ("what", "why", "how"))
    scopes = event["scopes"]
    assert isinstance(scopes, list)
    assert str(test_file) in str(scopes[0]["file"])


def test_name_convention_negative_at_satisfies_the_scope(tmp_path: Path) -> None:
    """POSITIVE proof: adding a `_does_not_`-named AT makes the scope pass."""
    test_file = tmp_path / "test_booking_atomicity.py"
    test_file.write_text(_PRESENCE_ONLY_PY + _NEGATIVE_BY_NAME_PY)

    assert main(["--test-file", str(test_file)]) == 0


def test_negative_at_marker_satisfies_the_scope(tmp_path: Path) -> None:
    """POSITIVE proof (marker arm): @pytest.mark.negative_at also counts."""
    test_file = tmp_path / "test_booking_atomicity.py"
    test_file.write_text(
        _PRESENCE_ONLY_PY
        + "\n\n@pytest.mark.negative_at\ndef test_wrong_seat_charge():\n"
        "    assert True\n"
    )

    assert main(["--test-file", str(test_file)]) == 0


def test_gherkin_critical_without_negative_scenario_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Gherkin arm, NEGATIVE proof: @critical scenario, no @negative -> RED."""
    feature = tmp_path / "booking.feature"
    feature.write_text(_PRESENCE_ONLY_FEATURE)

    assert main(["--test-file", str(feature)]) == 1
    event = _first_event(capsys)
    assert event["event"] == "NegativeAtRefused"


def test_gherkin_negative_scenario_satisfies_the_scope(tmp_path: Path) -> None:
    """Gherkin arm, POSITIVE proof: adding a @negative scenario -> exit 0."""
    feature = tmp_path / "booking.feature"
    feature.write_text(_PRESENCE_ONLY_FEATURE + _NEGATIVE_SCENARIO)

    assert main(["--test-file", str(feature)]) == 0


def test_no_critical_scopes_is_honest_not_applicable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """N/A proof: no @critical marks, no --all-critical -> exit 0, N/A event.

    Criticality is never fabricated — an unmarked suite is honestly N/A.
    """
    test_file = tmp_path / "test_plain.py"
    test_file.write_text("def test_happy_path():\n    assert 1 + 1 == 2\n")

    assert main(["--test-file", str(test_file)]) == 0
    assert _first_event(capsys)["event"] == "NegativeAtNotApplicable"


def test_all_critical_arms_the_mandate_on_unmarked_files(tmp_path: Path) -> None:
    """--all-critical proof: the caller declares the whole file critical."""
    test_file = tmp_path / "test_plain.py"
    test_file.write_text("def test_happy_path():\n    assert 1 + 1 == 2\n")

    assert main(["--test-file", str(test_file), "--all-critical"]) == 1


def test_missing_file_degrades_loud_indeterminate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """DEGRADE proof: missing input -> exit 2 with what/why/how, never a pass."""
    assert main(["--test-file", str(tmp_path / "nope.py")]) == 2
    event = _first_event(capsys)
    assert event["event"] == "NegativeAtIndeterminate"
    assert all(k in event for k in ("what", "why", "how"))


def test_test_dir_scans_py_and_feature_files(tmp_path: Path) -> None:
    """--test-dir proof: discovery covers both arms; one bad scope -> RED."""
    (tmp_path / "test_ok.py").write_text(_PRESENCE_ONLY_PY + _NEGATIVE_BY_NAME_PY)
    (tmp_path / "booking.feature").write_text(_PRESENCE_ONLY_FEATURE)

    assert main(["--test-dir", str(tmp_path)]) == 1
