"""Criterion 3: run_contract_gate surfaces InterpreterUnavailable as exit 2.

`run_contract_gate` resolves its nested pytest interpreter through the shared
bounded test-execution helper, which calls
`des.runtime.interpreter.python_for("pytest")`.
When no candidate on the fallback ladder is pytest-capable, `python_for` raises
`InterpreterUnavailable` rather than spawning a known-bad interpreter.

The gate must convert that raise into a structured, machine-readable
`InterpreterUnavailable` event on stdout plus exit code 2 -- never let a
pytest-collection traceback escape. Each role (run / digest / verify) must
fail the same diagnosable way.

The same direct pytest boundary resolves the interpreter for both roles:

* the "digest" role (`--collect-only --print-digest`) falls back to
  `_collect_scope` -> `pytest_interpreter()`.
* the "run-suite" role (default mode) uses the same direct fallback.
"""

from __future__ import annotations

import json
import subprocess
import time

import pytest

from des.cli import run_contract_gate
from des.runtime import test_execution
from des.runtime.interpreter import InterpreterUnavailable


_MAX_WALL_CLOCK_SECONDS = 30


def _last_json_event(stdout: str) -> dict:
    """Parse the final single-line JSON object emitted on stdout."""
    json_lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    return json.loads(json_lines[-1])


@pytest.mark.parametrize(
    "argv",
    [
        pytest.param(["--repo", "."], id="run-suite"),
        pytest.param(["--repo", ".", "--collect-only", "--print-digest"], id="digest"),
    ],
)
def test_interpreter_unavailable_surfaces_as_exit_2_structured_payload(
    monkeypatch: pytest.MonkeyPatch, capsys, argv: list[str]
) -> None:
    """A raised InterpreterUnavailable becomes exit 2 + an InterpreterUnavailable event.

    No pytest-collection traceback escapes -- the boundary refusal is
    converted to a structured malformed-input payload at the gate. Whichever
    role `main()` takes for a given `argv`, it observes the same refusal.
    """
    probed = ["/usr/bin/python3", "/opt/venv/bin/python"]

    def boom(capability, repo_root=None):  # type: ignore[no-untyped-def]
        raise InterpreterUnavailable(capability, probed)

    monkeypatch.setattr(test_execution, "python_for", boom)

    # Anti-recurrence guard: if a future refactor bypasses this boundary, fail FAST and
    # self-explain rather than hang running a real nested whole-tree suite.
    real_subprocess_run = subprocess.run

    def _guard_no_nested_pytest_spawn(*args, **kwargs):  # type: ignore[no-untyped-def]
        command = args[0] if args else kwargs.get("args")
        if command and any("pytest" in str(part) for part in command):
            raise AssertionError(
                "this unit test must never spawn a nested pytest suite -- "
                "a seam bypassed the `python_for` patch and reached a "
                f"real subprocess spawn: command={command!r}"
            )
        return real_subprocess_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", _guard_no_nested_pytest_spawn)

    start = time.monotonic()
    exit_code = run_contract_gate.main(argv)
    elapsed = time.monotonic() - start
    stdout = capsys.readouterr().out

    assert elapsed < _MAX_WALL_CLOCK_SECONDS, (
        f"gate took {elapsed:.1f}s -- must fail fast on InterpreterUnavailable, "
        "never spawn/hang running a real nested suite"
    )
    assert exit_code == 2
    event = _last_json_event(stdout)
    assert event["event"] == "InterpreterUnavailable"
    assert event["capability"] == "pytest"
    assert event["probed"] == probed
    assert "pytest" in event["error"]
