"""Regression: ``des verify-red-green --record-red`` on a NON-Python repo (no
recognized Python manifest, no ``--run-cmd``) must declare an honest
INCAPACITY, never a false "zero test cases collected".

RCA (src/des/cli/verify_red_green.py, ``_default_run_cmd`` ~L97-116): on a
target with NO ``uv.lock``/``poetry.lock``/``Pipfile`` the private Python-only
manifest chain falls through, open-ended, to the module-level
``_DEFAULT_RUN_CMD`` (``python -m pytest``) -- even on a Cargo/Rust repo. On a
Cargo target it then runs ``pytest tests/x.rs``; pytest rejects the ``.rs``
file at glob-match (a genuine collection mismatch) but STILL writes a valid,
EMPTY JUnit XML. ``_run_and_collect`` never checks the subprocess return code
(L152-159), so the empty XML parses into ``outcomes == {}`` and the tool emits
``_indeterminate("zero test cases collected", ...)`` (DES_EXIT=2) -- "your
tests witness nothing" (a measure NEVER made), not "I cannot run this project
layout" (a declared incapacity the tool should own as its OWN gap).

Second defect (same evidence trail): the "zero test cases collected"
``_indeterminate`` call (``_run_and_collect``, the ``if not outcomes:``
branch) never states WHICH ``cmd`` it ran, though ``cmd`` is already in local
scope at that point (built a few lines above to invoke the subprocess) --
GDP-3 (self-explaining WHAT/WHY/HOW) demands the actual command appear in the
payload, not just prose.

THE FIX under test (pinned by these scenarios, NOT implemented here --
DISTILL authors the test, DELIVER implements against it): ``_default_run_cmd``
must delegate to the EXISTING per-language registry
``des.ports.test_runner_port.resolve(repo)`` instead of its private
Python-only chain. On a layout that registry does NOT map to a
verify-red-green-known pytest-style run-cmd template (Cargo/Rust included --
``resolve()`` DOES recognize ``Cargo.toml`` -> runner ``cargo-test``, but
verify-red-green has no concrete cargo run-cmd template), the tool REFUSES
loud instead of silently reaching pytest: it names the incapacity, points at
``--run-cmd`` as the escape hatch, and surfaces the command it ran/would-run.
A genuinely-empty RECOGNIZED-Python suite must keep reporting "zero test
cases collected" unchanged (the incapacity path must not swallow a real
empty-suite measurement) -- the two verdicts must stay mechanically
distinguishable (never the same exit code + same "what").

Hermetic, real-CLI, no stub of the runner resolution: every scenario builds a
REAL on-disk fixture repo under ``tmp_path`` and drives the REAL
``des verify-red-green`` CLI via ``tests.common.in_process_cli.run_cli_in_process``
(the in-process analogue of
``python -m des.cli.__main__ verify-red-green ...``) -- ``resolve()`` inspects
the REAL filesystem of each fixture, nothing is monkeypatched.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.common.in_process_cli import run_cli_in_process


# ---------------------------------------------------------------------------
# Fixture repo builders -- each is a REAL on-disk repo, no recognized
# Python-package manifest shared across builders unless explicitly stated.
# ---------------------------------------------------------------------------


def _cargo_repo(tmp_path: Path) -> tuple[Path, str]:
    """A genuine Rust/Cargo repo -- Cargo.toml + a failing #[test], NO .py
    file anywhere, NO uv.lock/poetry.lock/Pipfile/pyproject.toml/pytest.ini."""
    (tmp_path / "Cargo.toml").write_text(
        '[package]\nname = "sample"\nversion = "0.1.0"\nedition = "2021"\n'
    )
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "it.rs").write_text(
        "#[test]\nfn it_fails() {\n    assert_eq!(1, 2);\n}\n"
    )
    return tmp_path, "tests/it.rs"


def _recognized_python_repo(tmp_path: Path, *, test_filename: str, body: str) -> Path:
    """A recognized Python layout resolvable to the ``pytest`` runner via
    ``pytest.ini`` (single-lockfile-equivalent fast path in
    ``test_runner_port.resolve`` -- deliberately WITHOUT uv.lock/poetry.lock/
    Pipfile, so the derived default run-cmd is the plain
    ``sys.executable -m pytest`` form on BOTH the old and the fixed code --
    a hermetic, no-external-tool-required real subprocess run)."""
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    (tmp_path / test_filename).write_text(body)
    return tmp_path


def _real_failing_python_repo(tmp_path: Path) -> Path:
    return _recognized_python_repo(
        tmp_path,
        test_filename="test_x.py",
        body="def test_regression():\n    assert 1 == 2\n",
    )


def _genuinely_empty_python_repo(tmp_path: Path) -> Path:
    return _recognized_python_repo(
        tmp_path,
        test_filename="test_empty.py",
        body="# no test_* functions in this file at all\n",
    )


def _copier_run_cmd(tmp_path: Path, xml: str, *, marker: str) -> str:
    """A ``--run-cmd`` that copies canned JUnit XML to ``{junit_out}`` -- no
    real Rust/pytest toolchain required. ``marker`` is a unique token baked
    into the script's own path so a test can prove the CUSTOM command (not a
    silent internal guess) is the one that actually ran."""
    xml_src = tmp_path / f"canned_{marker}.xml"
    xml_src.write_text(xml)
    copier = tmp_path / f"copier_{marker}.py"
    copier.write_text("import shutil, sys\nshutil.copy(sys.argv[1], sys.argv[2])\n")
    return f"{sys.executable} {copier} {xml_src} {{junit_out}}"


def _run_record_red(
    repo: Path, test_file: str, *, run_cmd: str | None = None
) -> tuple[int, str]:
    """Drive the REAL ``des verify-red-green --record-red`` in-process
    through the production dispatcher edge; return (exit_code, stdout)."""
    argv = [
        "verify-red-green",
        "--repo",
        str(repo),
        "--test-file",
        test_file,
        "--record-red",
    ]
    if run_cmd is not None:
        argv += ["--run-cmd", run_cmd]
    exit_code, stdout, stderr = run_cli_in_process(argv, cwd=repo)
    assert stdout, f"no stdout captured -- stderr={stderr!r}"
    return exit_code, stdout


def _json_events(stdout: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            events.append(json.loads(stripped))
        except json.JSONDecodeError:
            continue
    return events


def _last_json_event(stdout: str) -> dict[str, Any]:
    events = _json_events(stdout)
    assert events, f"no JSON event line found in stdout: {stdout!r}"
    return events[-1]


# ---------------------------------------------------------------------------
# Scenario 1 (POSITIVE, the bug -- RED today): unsupported (non-Python)
# layout must REFUSE loud, never claim "zero test cases collected".
# ---------------------------------------------------------------------------


def test_unsupported_cargo_layout_refuses_loud_never_zero_collected(
    tmp_path: Path,
) -> None:
    repo, test_file = _cargo_repo(tmp_path)

    exit_code, stdout = _run_record_red(repo, test_file)

    # Today: exit_code == 2, event RedGreenIndeterminate, what == "zero test
    # cases collected" -- the exact false-empty this bug reports. All three
    # assertions below are the diagnosed-defect pins.
    assert "zero test cases collected" not in stdout, (
        "an unsupported (non-Python) project layout must NEVER be reported "
        f"as an empty test suite -- des never even ran the developer's "
        f"tests. Got: {stdout!r}"
    )
    assert exit_code == 1, (
        "an unsupported project layout is a declared REFUSAL (des knows "
        "exactly what happened: it doesn't have a run-cmd template for this "
        "layout), distinct in both exit code and meaning from the "
        f"INDETERMINATE 'zero test cases collected' verdict (exit 2). Got "
        f"exit_code={exit_code}, stdout={stdout!r}"
    )
    haystack = stdout.lower()
    assert "--run-cmd" in stdout, (
        "the refusal must name --run-cmd as the escape hatch (GDP-3/GDP-4 -- "
        f"the HOW routes to the producing affordance). Got: {stdout!r}"
    )
    assert any(token in haystack for token in ("cargo", ".rs", "rust")), (
        "the refusal must NAME the unsupported layout it detected (the "
        f"resolved runner / manifest), not a generic error. Got: {stdout!r}"
    )
    payload = _last_json_event(stdout)
    assert "cmd" in payload, (
        "the refusal payload must surface the command it ran or would have "
        f"run (GDP-3 -- cmd is available, not just prose HOW). Got: {payload!r}"
    )
    assert payload["cmd"], f"'cmd' must be non-empty. Got: {payload!r}"


# ---------------------------------------------------------------------------
# Scenario 2 (NEGATIVE control -- must stay green): a genuinely-empty
# RECOGNIZED-Python suite keeps reporting "zero test cases collected" --
# the incapacity path must not swallow an honest empty measurement.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_genuinely_empty_python_suite_still_reports_zero_collected(
    tmp_path: Path,
) -> None:
    repo = _genuinely_empty_python_repo(tmp_path)

    exit_code, stdout = _run_record_red(repo, "test_empty.py")

    assert exit_code == 2, (
        f"a real pytest run that genuinely collects zero tests stays "
        f"INDETERMINATE (exit 2), unchanged by the incapacity fix. Got "
        f"exit_code={exit_code}, stdout={stdout!r}"
    )
    payload = _last_json_event(stdout)
    assert payload.get("event") == "RedGreenIndeterminate"
    assert payload.get("what") == "zero test cases collected", (
        "the incapacity fix must be scoped to unsupported layouts only -- a "
        f"recognized-Python empty suite keeps this exact verdict. Got: "
        f"{payload!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 3 (NEGATIVE control -- must stay green): a recognized Python
# layout resolves + runs pytest exactly as before, no regression.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_recognized_python_layout_default_derivation_unaffected(
    tmp_path: Path,
) -> None:
    repo = _real_failing_python_repo(tmp_path)

    exit_code, stdout = _run_record_red(repo, "test_x.py")

    assert exit_code == 0, (
        f"a recognized Python layout with a genuinely-failing test must "
        f"still RED-seal exactly as before the fix. Got exit_code="
        f"{exit_code}, stdout={stdout!r}"
    )
    payload = _last_json_event(stdout)
    assert payload.get("event") == "RedObserved"
    assert payload.get("failing"), f"expected a failing test recorded: {payload!r}"
    assert "zero test cases collected" not in stdout
    assert "--run-cmd" not in stdout, (
        "the incapacity advisory must not leak onto a normal, working "
        f"recognized-Python RED path. Got: {stdout!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 4 (control + new GDP-3 pin, RED today on the cmd-visibility
# assertion): an explicit --run-cmd on the unsupported layout is honored
# verbatim, and the reported result names the cmd that actually ran.
# ---------------------------------------------------------------------------


def test_explicit_run_cmd_overrides_incapacity_and_names_cmd_used(
    tmp_path: Path,
) -> None:
    repo, test_file = _cargo_repo(tmp_path)
    xml_one_fail = (
        '<testsuite><testcase classname="it" name="it_fails">'
        '<failure message="red"/></testcase></testsuite>'
    )
    run_cmd = _copier_run_cmd(tmp_path, xml_one_fail, marker="cargo_override")

    exit_code, stdout = _run_record_red(repo, test_file, run_cmd=run_cmd)

    assert exit_code == 0, (
        "an explicit --run-cmd must be honored even on an otherwise "
        f"unsupported layout -- the user has already told des what to run, "
        f"so no incapacity refusal should fire. Got exit_code={exit_code}, "
        f"stdout={stdout!r}"
    )
    assert "zero test cases collected" not in stdout
    assert "the unsupported" not in stdout.lower()
    payload = _last_json_event(stdout)
    assert payload.get("event") == "RedObserved"
    assert payload.get("failing") == ["it::it_fails"]
    assert "cargo_override" in stdout, (
        "the reported result must name the cmd that actually ran (the "
        "user's explicit --run-cmd), not stay silent about which command "
        f"was used. Got: {stdout!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 5 (POSITIVE, the second defect -- RED today): the "zero test
# cases collected" Indeterminate payload must surface the actual cmd it ran
# (cmd is already in local scope at that point in _run_and_collect), not
# just a prose HOW that omits it.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("build_repo", "test_filename"),
    [
        pytest.param(_genuinely_empty_python_repo, "test_empty.py", id="empty-python"),
    ],
)
def test_zero_collected_indeterminate_payload_names_the_cmd_it_ran(
    tmp_path: Path, build_repo, test_filename: str
) -> None:
    repo = build_repo(tmp_path)

    exit_code, stdout = _run_record_red(repo, test_filename)

    assert exit_code == 2
    payload = _last_json_event(stdout)
    assert payload.get("what") == "zero test cases collected"
    assert "cmd" in payload, (
        "the zero-collected INDETERMINATE payload must name the actual "
        "command it ran -- `cmd` is already in local scope where "
        "_indeterminate(what='zero test cases collected', ...) is raised "
        f"(GDP-3: self-explaining, not just prose HOW). Got: {payload!r}"
    )
    assert payload["cmd"], f"'cmd' must be non-empty. Got: {payload!r}"
    assert "pytest" in json.dumps(payload["cmd"]), (
        f"the surfaced cmd must reflect the pytest invocation that actually "
        f"ran against this recognized-Python repo. Got: {payload!r}"
    )
