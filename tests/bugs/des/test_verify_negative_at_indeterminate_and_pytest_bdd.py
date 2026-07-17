"""Regression -- ``des verify-negative-at`` self-contradictory verdict on
pytest-bdd-declared scopes (two coupled root causes).

RCA: docs/feature/fix-verify-negative-at-indeterminate/deliver/rca.md.
Charter: docs/product/expectations/fix-verify-negative-at-indeterminate/
developer-gets-a-truthful-verdict-on-pytest-bdd-negative-ats.md.

ROOT CAUSE A (GDP-6): the "no scannable AT surface" cause routes through
``_refuse()``/exit 1 even though the module's own contract already reserves
``_EXIT_INDETERMINATE = 2`` for exactly "cannot analyze" -- a
self-contradictory verdict ("this is NOT a weak-AT problem" then a red
REFUSED). Fix: no-scannable -> exit 2 (INDETERMINATE), never exit 1.

ROOT CAUSE B (resolution gap): ``_scan_pytest_file`` only collects
``test*``-named ``FunctionDef`` nodes -- it has no path to follow a
``pytest_bdd.scenarios("x.feature")`` call to the companion ``.feature``,
even though ``_scan_feature_file`` (the parser that DOES find the negative
AT) already lives in the same module. A pytest-bdd step-shim (a ``.py`` file
with ``scenarios(...)`` and zero ``def test_`` -- the normal, correct
pytest-bdd shape) is today scored REFUSED when pointed at the shim/dir, but
PASS when pointed at the sibling ``.feature`` directly. Fix: teach
``_scan_pytest_file`` to detect ``scenarios(<literal>)``, resolve the path
relative to the shim's own directory, and delegate to ``_scan_feature_file``.

Driving surface (Mandate-13/16 driving-port-only, Layer 3 in-process
default): the REAL ``des verify-negative-at`` CLI entry (``main()``),
captured via ``capsys`` -- the established idiom for this exact gate in this
exact directory (``tests/bugs/des/test_verify_negative_at_two_causes.py``,
``tests/des/unit/cli/test_verify_negative_at.py``). All fixtures are built
hermetically under ``tmp_path``; no repo file is mutated.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli.verify_negative_at import main


# ---------------------------------------------------------------------------
# Fixture content
# ---------------------------------------------------------------------------

# A correct pytest-bdd companion .feature: one scenario whose name signals a
# negative assertion ("does not create" -> the "not " token) -- the wrong
# outcome (a widget order) is asserted NOT to be produced.
_WIDGET_PURCHASE_FEATURE = """\
Feature: Widget purchase

  Scenario: A declined payment does not create a widget order
    Given a widget order form is open
    When the customer submits payment that is declined
    Then no widget order is created
"""

# A correct pytest-bdd step-shim: `scenarios(...)` binding + @given/@when/@then
# step definitions, and DELIBERATELY zero `def test_` functions -- exactly
# the idiom pytest-bdd requires and that this repo already uses repo-wide
# (e.g. tests/installer/acceptance/*/steps/test_*.py).
_WIDGET_PURCHASE_STEPS_PY = """\
from pytest_bdd import given, scenarios, then, when

scenarios("../widget_purchase.feature")


@given("a widget order form is open")
def _order_form_open():
    pass


@when("the customer submits payment that is declined")
def _submit_declined_payment():
    pass


@then("no widget order is created")
def _no_widget_order_created():
    pass
"""

# Genuine weak AT: real, scannable `def test_` functions, but NONE of them
# is negative (presence-only -- every assertion says the expected output
# appears). Must keep refusing (exit 1) both before and after the fix.
_WEAK_AT_PY = """\
def test_widget_order_confirmation_is_created():
    result = {"confirmation": "abc123"}
    assert result["confirmation"] is not None
"""

# Same scope, PLUS a genuine negative-named AT -- must keep passing (exit 0)
# both before and after the fix.
_WEAK_AT_WITH_NEGATIVE_PY = _WEAK_AT_PY + (
    "\n\n"
    "def test_unrelated_input_does_not_trigger_a_second_confirmation():\n"
    "    confirmations = [{'id': 1}]\n"
    "    assert len(confirmations) == 1\n"
)

# Genuinely zero-scannable: no `def test_`, no `fn`/`func`/`function` decl,
# no pytest-bdd `scenarios(...)` call -- nothing to scan at all. Mirrors the
# #29 fixture (`_ZERO_SCANNABLE_PROSE`), whose exit code is the exact axis
# Root Cause A changes: 1 (today, wrong) -> 2 (fixed, honest INDETERMINATE).
_ZERO_SCANNABLE_PROSE = """\
Widget purchase runbook

This document describes the manual QA checklist for widget purchases.
There is no automated test coverage in this directory -- see the wiki.
"""

# A syntactically valid Python file discoverable via --test-dir (matches the
# `test_*.py` glob) that is ALSO genuinely zero-scannable: step-style helper
# functions with no `def test_` prefix and no `scenarios(...)` call. Proves
# Root Cause A's fix is not accidentally piggybacking on Root Cause B's
# `scenarios(...)` detection -- a real, structural absence of an AT surface.
_ZERO_SCANNABLE_PY = """\
def _order_form_open():
    pass


def _submit_declined_payment():
    pass
"""


def _events(capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    """Every JSON payload line ``main()`` emitted since the last read."""
    out = capsys.readouterr().out
    return [json.loads(line) for line in out.splitlines() if line.startswith("{")]


def _first_event(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    return _events(capsys)[0]


def _build_pytest_bdd_scope(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A correct pytest-bdd scope: <root>/widget_purchase.feature +
    <root>/steps/test_widget_purchase_steps.py (scenarios() resolved
    relative to the SHIM's own directory, one level up -- the real repo-wide
    dual-file idiom). Returns (root_dir, feature_file, shim_file)."""
    root = tmp_path / "widget-purchase-at"
    steps_dir = root / "steps"
    steps_dir.mkdir(parents=True)
    feature_file = root / "widget_purchase.feature"
    feature_file.write_text(_WIDGET_PURCHASE_FEATURE)
    shim_file = steps_dir / "test_widget_purchase_steps.py"
    shim_file.write_text(_WIDGET_PURCHASE_STEPS_PY)
    return root, feature_file, shim_file


# ---------------------------------------------------------------------------
# ROOT CAUSE B -- pytest-bdd `scenarios(...)` resolution
# ---------------------------------------------------------------------------


def test_direct_feature_file_passes_as_the_baseline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CONTROL (must be green today and after the fix): pointed straight at
    the `.feature` file, the negative scenario is found and the scope
    passes. This is the result the pytest-bdd shim/directory invocations
    below must MATCH once Root Cause B is fixed."""
    _root, feature_file, _shim = _build_pytest_bdd_scope(tmp_path)

    exit_code = main(["--test-file", str(feature_file), "--all-critical"])

    assert exit_code == 0
    event = _first_event(capsys)
    assert event["event"] == "NegativeAtVerified"


@pytest.mark.parametrize("point_at", ["shim_file", "root_dir"])
def test_pytest_bdd_shim_resolves_the_companion_feature_and_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], point_at: str
) -> None:
    """BUG observable (Root Cause B), RED today: a pytest-bdd step-shim
    `.py` (zero `def test_`, a `scenarios("../widget_purchase.feature")`
    call) must resolve to its companion `.feature`'s negative scenario and
    PASS (exit 0) -- whether pointed at directly (`--test-file <shim>.py`)
    or via its containing directory (`--test-dir <root>`) -- matching the
    direct-`.feature` control above.

    Today: the shim scans to ZERO cases (no `def test_` is collectable),
    so it is scored "no scannable AT surface" and the run REFUSES (exit 1)
    even though the real negative AT is one hop away via `scenarios(...)`.
    """
    root, _feature_file, shim_file = _build_pytest_bdd_scope(tmp_path)

    if point_at == "shim_file":
        argv = ["--test-file", str(shim_file), "--all-critical"]
    else:
        argv = ["--test-dir", str(root), "--all-critical"]

    exit_code = main(argv)

    assert exit_code == 0, (
        "a correct pytest-bdd step-shim (scenarios(...) + zero def test_) "
        f"must resolve its companion .feature and PASS -- got exit "
        f"{exit_code}: {_first_event(capsys)}"
    )
    event = _first_event(capsys)
    assert event["event"] == "NegativeAtVerified"
    assert event.get("negative_ats_found", 0) >= 1


# ---------------------------------------------------------------------------
# ROOT CAUSE A -- exit-code mapping for "no scannable AT surface"
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("build_argv", "case_id"),
    [
        (
            lambda tmp_path: (
                [
                    "--test-file",
                    str(_write(tmp_path, "runbook.md", _ZERO_SCANNABLE_PROSE)),
                    "--all-critical",
                ]
            ),
            "prose-file",
        ),
        (
            lambda tmp_path: (
                [
                    "--test-dir",
                    str(
                        _mkdir_with(
                            tmp_path,
                            "no-surface-dir",
                            "test_helpers.py",
                            _ZERO_SCANNABLE_PY,
                        )
                    ),
                    "--all-critical",
                ]
            ),
            "python-file-via-dir",
        ),
    ],
)
def test_zero_scannable_scope_is_indeterminate_not_refused(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    build_argv,
    case_id: str,
) -> None:
    """BUG observable (Root Cause A), RED today: a scope with genuinely
    ZERO scannable AT tokens (no `def test_`, no `fn`/`func`/`function`, no
    pytest-bdd `scenarios(...)`) must exit 2 (`_EXIT_INDETERMINATE`, this
    module's OWN pre-existing "cannot analyze" contract) -- NOT exit 1
    (`_EXIT_REFUSED`). The gate's own message already says "this is NOT a
    weak-AT problem"; the exit code must stop contradicting it.

    Today: routes through `_refuse()` -> exit 1, same red REFUSED verdict a
    genuine weak-AT scope gets.
    """
    argv = build_argv(tmp_path)

    exit_code = main(argv)

    assert exit_code == 2, (
        f"[{case_id}] a genuinely zero-scannable scope must exit 2 "
        f"(INDETERMINATE), never exit 1 (REFUSED) -- got {exit_code}"
    )
    event = _first_event(capsys)
    assert event["event"] == "NegativeAtIndeterminate", (
        f"[{case_id}] expected the INDETERMINATE verdict event, got: {event}"
    )
    assert event["event"] != "NegativeAtRefused"


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content)
    return path


def _mkdir_with(tmp_path: Path, dirname: str, filename: str, content: str) -> Path:
    d = tmp_path / dirname
    d.mkdir(parents=True, exist_ok=True)
    (d / filename).write_text(content)
    return d


# ---------------------------------------------------------------------------
# Three-way verdict distinctness (charter oracle) + negative-AT pins
# ---------------------------------------------------------------------------


def test_three_way_verdict_is_distinct_pass_weak_refuse_indeterminate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Charter oracle: across the three seeds, verdict word + exit code must
    take exactly THREE DISTINCT forms -- PASS (0), a weak-AT refusal (1),
    and an incapacity/indeterminate outcome (2). RED today: the weak-AT
    refusal and the indeterminate scope both surface as exit 1 /
    `NegativeAtRefused` -- "I looked and it's weak" and "I could not look"
    collapse onto the same verdict.
    """
    pass_file = _write(tmp_path, "test_pass.py", _WEAK_AT_WITH_NEGATIVE_PY)
    weak_file = _write(tmp_path, "test_weak.py", _WEAK_AT_PY)
    indeterminate_file = _write(tmp_path, "prose.md", _ZERO_SCANNABLE_PROSE)

    pass_exit = main(["--test-file", str(pass_file), "--all-critical"])
    pass_event = _first_event(capsys)

    weak_exit = main(["--test-file", str(weak_file), "--all-critical"])
    weak_event = _first_event(capsys)

    indeterminate_exit = main(
        ["--test-file", str(indeterminate_file), "--all-critical"]
    )
    indeterminate_event = _first_event(capsys)

    exit_codes = {pass_exit, weak_exit, indeterminate_exit}
    assert exit_codes == {0, 1, 2}, (
        "the three seeds must produce three DISTINCT exit codes -- got "
        f"pass={pass_exit} weak={weak_exit} indeterminate={indeterminate_exit}"
    )

    event_names = {
        pass_event["event"],
        weak_event["event"],
        indeterminate_event["event"],
    }
    assert len(event_names) == 3, (
        "the three seeds must produce three DISTINCT verdict words -- got "
        f"{event_names}"
    )
    assert weak_event["event"] == "NegativeAtRefused"
    assert indeterminate_event["event"] == "NegativeAtIndeterminate"
    assert indeterminate_event["event"] != weak_event["event"], (
        "'I looked and it's weak' and 'I could not look' must never "
        "collapse onto the same verdict word"
    )


def test_genuine_weak_at_still_refuses(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """REGRESSION PIN (must stay GREEN before and after the fix): a scope
    with real, scannable `def test_` functions and ZERO negative assertion
    still refuses -- exit 1, `NegativeAtRefused`. Neither root-cause fix may
    launder a genuine weak-AT problem into a soft pass or an INDETERMINATE
    shrug."""
    test_file = _write(tmp_path, "test_weak_pin.py", _WEAK_AT_PY)

    exit_code = main(["--test-file", str(test_file), "--all-critical"])

    assert exit_code == 1
    assert _first_event(capsys)["event"] == "NegativeAtRefused"


def test_real_negative_at_still_passes(tmp_path: Path) -> None:
    """REGRESSION PIN (must stay GREEN before and after the fix): a scope
    carrying a genuine negative-named AT still passes -- with or without
    `--all-critical`."""
    test_file = _write(tmp_path, "test_negative_pin.py", _WEAK_AT_WITH_NEGATIVE_PY)

    assert main(["--test-file", str(test_file), "--all-critical"]) == 0
    assert main(["--test-file", str(test_file)]) == 0
