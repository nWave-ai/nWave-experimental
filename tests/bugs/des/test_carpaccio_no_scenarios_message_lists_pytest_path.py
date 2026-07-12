"""Regression (GDP-2/GDP-3): the ``no-scenarios-for-slice`` rejection must
name BOTH accepted AT-authoring paths, not only the Gherkin one.

Found in ``src/des/cli/carpaccio_format.py`` ``_no_scenarios_rejection(repo,
feature_id, slice_id)`` (lines ~1059-1097): the ``error`` string and
``instruction`` field describe ONLY the Gherkin remediation path -- literally
"To fix: add/author a '.feature' file carrying the file-level tag
'@feature-<id>' with a scenario tagged @<slice>". The carpaccio slice gate
ALSO accepts a second, co-equal, supported entry path -- the pytest-
regression mechanical-seal route (``--at-kind pytest-regression
--regression-test-file <f>``), documented in ``check_carpaccio`` and exercised
by ``tests/des/unit/cli/test_carpaccio_mechanical_seal.py``. An operator whose
AT is a pytest file hits this rejection and is steered into a needless
Gherkin workaround, because the message never mentions the path they are
actually meant to take. This violates GDP-2 (inline affordance -- surface ALL
accepted paths at the point of rejection) + GDP-3 (complete what/why/how).

Driving surface: calls ``_no_scenarios_rejection`` directly (the real
emission function -- not a re-derivation), inspects the returned
``GateError.payload`` dict. Author-only regression test; the fix (extending
``error``/``instruction``/``how`` to name the pytest-regression path while
KEEPING the existing Gherkin wording) is left to the crafter.
"""

from __future__ import annotations

from pathlib import Path

from des.cli.carpaccio_format import GateError, _no_scenarios_rejection


_FEATURE_ID = "no-scenarios-message-fixture"
_SLICE_ID = "slice-01"


def _rejection_text(payload: dict[str, object]) -> str:
    """Concatenate every operator-facing string field on the payload --
    ``error`` + ``instruction`` + an optional ``how`` -- so the assertions
    below are agnostic to WHICH field the fix ultimately extends."""
    parts = [
        str(payload.get("error", "")),
        str(payload.get("instruction", "")),
        str(payload.get("how", "")),
    ]
    return "\n".join(parts)


def test_no_scenarios_rejection_names_the_pytest_regression_entry_path(
    tmp_path: Path,
) -> None:
    """POSITIVE AT (active-RED today): the rejection built for a genuinely
    absent '.feature' file must ALSO tell the operator about the
    pytest-regression mechanical-seal route -- naming both the mode flag
    (``pytest-regression``) and the file flag (``--regression-test-file``).
    Today the payload only ever names the Gherkin '.feature' path, so this
    assertion fails on the CURRENT code for a real semantic reason (the
    missing substrings), not a crash.
    """
    repo = tmp_path / "repo"
    repo.mkdir()

    error = _no_scenarios_rejection(repo, _FEATURE_ID, _SLICE_ID)

    assert isinstance(error, GateError)
    text = _rejection_text(error.payload)

    assert "pytest-regression" in text, (
        "the no-scenarios-for-slice rejection must name the pytest-regression "
        f"AT-kind as an accepted entry path -- got: {text!r}"
    )
    assert "--regression-test-file" in text, (
        "the no-scenarios-for-slice rejection must name the "
        "--regression-test-file flag so an operator with a pytest AT knows "
        f"how to point the gate at it -- got: {text!r}"
    )


def test_no_scenarios_rejection_does_not_drop_the_gherkin_path(
    tmp_path: Path,
) -> None:
    """NEGATIVE AT (control -- green today, must stay green after the fix):
    the fix must ADD the pytest-regression path, never REPLACE the existing
    Gherkin one. The rejection must still mention a '.feature' file and the
    file-level '@feature-<id>' tag it searched for."""
    repo = tmp_path / "repo"
    repo.mkdir()

    error = _no_scenarios_rejection(repo, _FEATURE_ID, _SLICE_ID)

    assert isinstance(error, GateError)
    text = _rejection_text(error.payload)

    assert ".feature" in text, (
        f"the Gherkin remediation path must remain in the message -- got: {text!r}"
    )
    assert f"@feature-{_FEATURE_ID}" in text, (
        "the file-level tag the gate searched for must remain named in the "
        f"message -- got: {text!r}"
    )
