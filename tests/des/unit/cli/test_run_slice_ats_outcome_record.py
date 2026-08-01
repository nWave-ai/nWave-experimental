"""slice-04 (gate-outcome-record-seam): `run-slice-ats` writes a per-run
outcome record.

DDD-5 named `run-slice-ats` a first-population target ("blocks every
commit"). Today it projects its verdict onto stdout JSON + the exit code
only -- it never calls `AtCompletionLedger.append_gate_event(...,
gate="run-slice-ats", outcome=<GateVerdict>)`.

`run_slice_ats.py` already resolves the in-flight feature id via
`active_feature_id(repo_root)` (the SSOT resolution helper living on
`AtCompletionLedger`'s own module) BEFORE the pytest-arm's AT discovery --
the singleton-shape ledger (`AtCompletionLedger(project_root=repo_root)`) is
the reuse target, threading that SAME resolved `feature_id` (`None` when
unresolvable, per the helper's own documented contract) into the new
`append_gate_event(..., feature_id=...)` call -- no second resolution
mechanism invented.

Two terminating paths exercised, reusing the established real-git-and-real-
pytest fixture (`_plant_slice_at`, mirrored from
`tests/bugs/des/test_run_slice_ats_fail_names_how.py` -- a genuinely
collectable `@<slice>` Gherkin scenario + pytest-bdd binding, so a RED
planted AT genuinely fails, never a fabricated pass):

  * a green planted AT -> exit 0 -> outcome=PASS.
  * a red planted AT -> exit 1 -> outcome=FAIL.

Driving surface (Mandate 16): the REAL `run_slice_ats.main()` CLI edge,
driven in-process via `run_cli_in_process` -- the SAME entry point the
commit-time slice-AT gate invokes.
"""

from __future__ import annotations

import os
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.run_slice_ats import main as _run_slice_ats_main
from des.domain.gate_outcome import GateVerdict
from tests.common.in_process_cli import run_cli_in_process
from tests.env_parity import seed_dev_checkout_marker


REPO_ROOT = Path(__file__).resolve().parents[4]

_GATE_NAME = "run-slice-ats"
_ENTERING_SLICE = "slice-outcome-record-fixture"


def _plant_slice_at(workspace: Path, *, green: bool) -> None:
    """A real, genuinely collectable `@<slice>` acceptance test.

    Identical fixture shape to
    `tests/bugs/des/test_run_slice_ats_fail_names_how.py::_plant_slice_at`
    (a proven, GREEN precedent) -- deliberately not imported cross-module
    (established per-file duplication convention in this test corpus, e.g.
    `_last_json_event`), reused here at the SAME literal shape.
    """
    (workspace / "pyproject.toml").write_text(
        "[project]\nname = 'run-slice-ats-outcome-fixture'\n", encoding="utf-8"
    )
    slug = _ENTERING_SLICE.replace("-", "_")
    slice_dir = workspace / "tests" / slug
    slice_dir.mkdir(parents=True, exist_ok=True)
    (slice_dir / "__init__.py").write_text("", encoding="utf-8")
    (slice_dir / f"{slug}.feature").write_text(
        f"@feature-run-slice-ats-outcome-fixture @{_ENTERING_SLICE}\n"
        "Feature: fixture slice for the run-slice-ats outcome record AT\n\n"
        f"  @{_ENTERING_SLICE}\n"
        "  Scenario: the fixture slice behaves\n"
        "    Given a fixture slice precondition\n"
        "    When the fixture slice acts\n"
        "    Then the fixture slice outcome holds\n",
        encoding="utf-8",
    )
    outcome = "0 == 0" if green else "0 == 1"
    (slice_dir / f"test_{slug}.py").write_text(
        "from pytest_bdd import given, when, then, scenarios\n\n"
        f'scenarios("{slug}.feature")\n\n\n'
        '@given("a fixture slice precondition")\n'
        "def _given():\n    pass\n\n\n"
        '@when("the fixture slice acts")\n'
        "def _when():\n    pass\n\n\n"
        '@then("the fixture slice outcome holds")\n'
        f"def _then():\n    assert {outcome}\n",
        encoding="utf-8",
    )


def _run_slice_ats(workspace: Path) -> int:
    """Drive the REAL `des run-slice-ats` CLI (`main()`) in-process."""
    prior_pythonpath = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = str(REPO_ROOT)
    try:
        exit_code, _stdout, _stderr = run_cli_in_process(
            ["--repo-root", str(workspace), "--entering-slice", _ENTERING_SLICE],
            cwd=workspace,
            main=_run_slice_ats_main,
        )
    finally:
        if prior_pythonpath is None:
            os.environ.pop("PYTHONPATH", None)
        else:
            os.environ["PYTHONPATH"] = prior_pythonpath
    return exit_code


def _outcome_records(repo_root: Path) -> list[dict[str, object]]:
    ledger = AtCompletionLedger(project_root=repo_root)
    return [
        record
        for record in ledger.read_records(event_type="GateOutcomeRecorded")
        if record.get("gate") == _GATE_NAME
    ]


# =============================================================================
# POSITIVE ATs -- active-RED today
# =============================================================================


def test_a_passing_slice_at_records_pass_outcome(tmp_path: Path) -> None:
    """A slice whose planted AT genuinely passes clears the gate (exit 0,
    unchanged) AND appends a GateOutcomeRecorded record with outcome=PASS."""
    workspace = tmp_path / "pass_repo"
    workspace.mkdir()
    seed_dev_checkout_marker(workspace)
    _plant_slice_at(workspace, green=True)

    exit_code = _run_slice_ats(workspace)

    assert exit_code == 0, (
        f"expected the green slice AT to clear (exit 0), got {exit_code}"
    )

    records = _outcome_records(workspace)
    assert len(records) == 1, (
        f"expected exactly one GateOutcomeRecorded record for {_GATE_NAME!r} "
        f"after a PASS run -- got {records!r}"
    )
    assert records[0].get("outcome") == GateVerdict.PASS.value, records[0]


def test_a_failing_slice_at_records_fail_outcome(tmp_path: Path) -> None:
    """A slice whose planted AT genuinely fails is still REJECTED (exit 1,
    unchanged -- floor intact) AND appends a GateOutcomeRecorded record with
    outcome=FAIL."""
    workspace = tmp_path / "fail_repo"
    workspace.mkdir()
    seed_dev_checkout_marker(workspace)
    _plant_slice_at(workspace, green=False)

    exit_code = _run_slice_ats(workspace)

    assert exit_code == 1, (
        f"expected the red slice AT to reject (exit 1), got {exit_code}"
    )

    records = _outcome_records(workspace)
    assert len(records) == 1, (
        f"expected exactly one GateOutcomeRecorded record for {_GATE_NAME!r} "
        f"after a FAIL run -- got {records!r}"
    )
    assert records[0].get("outcome") == GateVerdict.FAIL.value, records[0]
