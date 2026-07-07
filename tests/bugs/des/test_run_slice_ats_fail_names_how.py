"""Regression (GDP-3/GDP-4): `des run-slice-ats`'s ``FAIL`` verdict must carry
a ``how`` field naming the concrete remediation, not ONLY
``{event, entering_slice, verdict, runner, reason, ran_node_ids,
ran_whole_tree, out_of_slice_ran}`` with ``reason: ""`` (WHAT, no HOW).

Charter: ``docs/product/expectations/fix-run-slice-ats-fail-names-how/
the-fail-verdict-names-how-to-green-the-slice-ats.md``.

Found in ``src/des/cli/run_slice_ats.py``:
  * ``_emit_verdict`` (~:87) -- builds the JSON payload; carries no ``how`` key.
  * ``main`` (~:235) -- the FAIL branch (``run_verdict.passed`` False) calls
    ``_emit_verdict`` with no ``how=`` argument at all.

The fix direction (charter, NOT implemented here): the FAIL verdict's ``how``
names the remediation -- green the failing slice acceptance test(s) (fix the
implementation until they pass), then re-run ``des run-slice-ats``.

CRITICAL CONSTRAINT (preserved, do NOT change): the check stays intact -- a
slice whose acceptance test genuinely fails is STILL rejected (exit 1). The
PASS path (exit 0) stays clean -- no ``how``.

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process default):
the REAL ``des.cli.run_slice_ats.main()`` CLI driver, driven in-process via
``run_cli_in_process`` (no interpreter fork for the CLI edge itself) -- the
SAME entry point the commit-time slice-AT gate invokes. No direct import of
``_emit_verdict`` / ``main``'s internals -- only the CLI edge.

Fixture shape mirrored from the proven, GREEN precedent
``tests/des/acceptance/f_spine_runs_tests_not_git_hooks/steps/composition.py``
(``SliceRunComposition``): a hermetic tmp workspace recognized as a pytest
target (``pyproject.toml``), with a real, genuinely collectable ``@<slice>``
``.feature`` + pytest-bdd binding planted under ``tests/<slug>/`` -- green
(``assert 0 == 0``) or RED (``assert 0 == 1``). The executor's own RUN facet
shells a REAL child ``pytest`` over that scoped node-id set, so a RED planted
AT genuinely FAILS (never a fabricated / collect-only pass).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from des.cli.run_slice_ats import main as _run_slice_ats_main
from tests.common.in_process_cli import run_cli_in_process
from tests.env_parity import seed_dev_checkout_marker


REPO_ROOT = Path(__file__).resolve().parents[3]

_ENTERING_SLICE = "slice-run-fail-how-fixture"


def _plant_slice_at(workspace: Path, *, green: bool) -> None:
    """Plant a REAL, genuinely collectable ``@<slice>`` acceptance test.

    A pytest project (``pyproject.toml``) carrying a real Gherkin scenario
    tagged ``@feature-... @<entering_slice>`` and a pytest-bdd binding whose
    ``then`` step asserts a true (green) or false (RED) behavior -- the
    executor's RUN facet shells a real child ``pytest`` over this, so a RED
    planted AT genuinely FAILS (not a collect-only pass).
    """
    (workspace / "pyproject.toml").write_text(
        "[project]\nname = 'run-slice-ats-how-fixture'\n", encoding="utf-8"
    )
    slug = _ENTERING_SLICE.replace("-", "_")
    slice_dir = workspace / "tests" / slug
    slice_dir.mkdir(parents=True, exist_ok=True)
    (slice_dir / "__init__.py").write_text("", encoding="utf-8")
    (slice_dir / f"{slug}.feature").write_text(
        f"@feature-run-slice-ats-how-fixture @{_ENTERING_SLICE}\n"
        "Feature: fixture slice for the run-slice-ats FAIL-names-how AT\n\n"
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


def _run_slice_ats(workspace: Path) -> tuple[int, dict[str, object]]:
    """Drive the REAL ``des run-slice-ats`` CLI (``main()``) in-process.

    Mirrors ``SliceRunComposition._run_executor``: PYTHONPATH is set to
    ``REPO_ROOT`` (save/restore) so the executor's own child-worker pytest
    spawn resolves ``des`` identically to the proven precedent.
    """
    prior_pythonpath = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = str(REPO_ROOT)
    try:
        exit_code, stdout, stderr = run_cli_in_process(
            ["--repo-root", str(workspace), "--entering-slice", _ENTERING_SLICE],
            cwd=workspace,
            main=_run_slice_ats_main,
        )
    finally:
        if prior_pythonpath is None:
            os.environ.pop("PYTHONPATH", None)
        else:
            os.environ["PYTHONPATH"] = prior_pythonpath
    combined = stdout + stderr
    payload: dict[str, object] = {}
    for line in combined.splitlines():
        stripped = line.strip()
        if stripped.startswith("{") and "verdict" in stripped:
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                continue
    assert payload, f"expected a verdict JSON line on stdout/stderr; got: {combined!r}"
    return exit_code, payload


# ===========================================================================
# POSITIVE AT -- active-RED today
# ===========================================================================


def test_fail_verdict_names_a_how_to_green_the_slice_ats(tmp_path: Path) -> None:
    """A slice whose acceptance test genuinely fails is REJECTED (floor
    intact -- exit 1, ``verdict='FAIL'``) -- already true today. The payload
    must ALSO carry a ``how`` field naming the concrete remediation -- green
    the failing slice acceptance test(s), then re-run ``des run-slice-ats`` --
    this is MISSING today (RED for the right reason: a semantic AssertionError
    on the absent ``how``, not a crash or collection error).
    """
    workspace = tmp_path / "fail_repo"
    workspace.mkdir()
    seed_dev_checkout_marker(workspace)
    _plant_slice_at(workspace, green=False)

    exit_code, payload = _run_slice_ats(workspace)

    # Floor intact -- already passing today, must stay true after the fix.
    assert exit_code == 1, (
        "a slice whose acceptance test genuinely fails must still be "
        f"REJECTED (exit 1) -- got exit_code={exit_code}; payload={payload!r}"
    )
    assert payload.get("verdict") == "FAIL", payload

    # HOW -- MISSING today. run_slice_ats.py's FAIL branch calls
    # `_emit_verdict` with no `how=` argument; `_emit_verdict` builds no `how`
    # key at all.
    how = payload.get("how")
    assert how, (
        "the FAIL verdict must carry a `how` field naming the concrete "
        "remediation -- green the failing slice acceptance test(s), then "
        f"re-run `des run-slice-ats` -- payload carries no `how`: {payload!r}"
    )
    assert isinstance(how, str), f"expected `how` to be a str, got {how!r}"
    how_lower = how.lower()
    assert "run-slice-ats" in how_lower, (
        "the `how` for a FAIL verdict must name re-running `des "
        f"run-slice-ats` -- got how={how!r}"
    )
    assert any(word in how_lower for word in ("green", "fix", "pass")), (
        "the `how` for a FAIL verdict must name greening/fixing the failing "
        f"slice acceptance test(s) as the remediation -- got how={how!r}"
    )


# ===========================================================================
# NEGATIVE AT -- control, green today AND after the fix
# ===========================================================================


@pytest.mark.negative_at
def test_pass_verdict_never_carries_a_how(tmp_path: Path) -> None:
    """A slice whose acceptance test passes clears the gate (``verdict='PASS'``,
    exit 0) with NO spurious ``how`` in the payload -- the ``how`` remediation
    belongs only to the reject path, never leaking into a passing verdict.
    Must stay green both BEFORE and AFTER the fix.
    """
    workspace = tmp_path / "pass_repo"
    workspace.mkdir()
    seed_dev_checkout_marker(workspace)
    _plant_slice_at(workspace, green=True)

    exit_code, payload = _run_slice_ats(workspace)

    assert exit_code == 0, (
        "a slice whose acceptance test passes must clear (exit 0) -- got "
        f"exit_code={exit_code}; payload={payload!r}"
    )
    assert payload.get("verdict") == "PASS", payload
    assert "how" not in payload, (
        f"a PASS verdict must never carry a spurious `how` field: {payload!r}"
    )
