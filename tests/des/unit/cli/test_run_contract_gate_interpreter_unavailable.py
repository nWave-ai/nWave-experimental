"""Criterion 3: run_contract_gate surfaces InterpreterUnavailable as exit 2.

F-21 boundary contract. `run_contract_gate` resolves its nested pytest
interpreter through the pytest run-facet boundary
`des.adapters.driven.runner.pytest_runner.pytest_interpreter()` (which calls
`des.runtime.interpreter.python_for("pytest")`) -- the gate no longer calls
`python_for` inline (gate-layer-test-runner-genericity slice-01: the
python-hardcode lives behind the runner-adapter boundary, never in gate logic).
When no candidate on the fallback ladder is pytest-capable, `python_for` raises
`InterpreterUnavailable` rather than spawning a known-bad interpreter.

The gate must convert that raise into a structured, machine-readable
`InterpreterUnavailable` event on stdout plus exit code 2 -- never let a
pytest-collection traceback escape. Each role (run / digest / verify) must
fail the same diagnosable way.

Two seams resolve the interpreter for the two roles this test covers, and
BOTH must be patched:

* the "digest" role (`--collect-only --print-digest`) falls back to
  `_collect_scope` -> `pytest_interpreter()`, which calls
  `des.adapters.driven.runner.pytest_runner.python_for("pytest")` -- the
  pytest run-facet boundary.
* the "run-suite" role (default mode) routes FIRST through
  `_maybe_route_through_registered_contract_gate`, which resolves the
  registered `PythonContractGateAdapter` (nwave_lang_python's pytest
  `ContractGatePort` facet) and calls its `run_suite`/`collect_scope`, which
  import `python_for` DIRECTLY from `des.runtime.interpreter` -- a SEPARATE
  name binding in
  `des.adapters.driven.contract_gate.pytest_contract_gate_adapter` that the
  `pytest_runner` patch does not reach.

Patching only `pytest_runner.python_for` (as this test previously did)
leaves the run-suite role's registered-adapter path unpatched: `python_for`
resolves a real interpreter, and `PythonContractGateAdapter.run_suite`
spawns a REAL nested whole-tree `pytest` subprocess against the live repo
from inside this unit test -- hanging to the pytest-timeout ceiling instead
of exercising the InterpreterUnavailable contract this test exists to prove.
"""

from __future__ import annotations

import json
import subprocess
import time

import pytest

from des.adapters.driven.contract_gate import pytest_contract_gate_adapter
from des.adapters.driven.runner import pytest_runner
from des.cli import run_contract_gate
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
    converted to a structured malformed-input payload at the gate. Both the
    digest-leg seam (`pytest_runner.python_for`) and the run-suite-leg
    registered-adapter seam (`pytest_contract_gate_adapter.python_for`) are
    patched, so whichever internal route `main()` takes for a given `argv`,
    it observes the SAME simulated interpreter refusal.
    """
    probed = ["/usr/bin/python3", "/opt/venv/bin/python"]

    def boom(capability):  # type: ignore[no-untyped-def]
        raise InterpreterUnavailable(capability, probed)

    monkeypatch.setattr(pytest_runner, "python_for", boom)
    monkeypatch.setattr(pytest_contract_gate_adapter, "python_for", boom)

    # Anti-recurrence guard: if a future refactor introduces yet another
    # `python_for` name binding neither patch reaches, fail FAST and
    # self-explain rather than hang running a real nested whole-tree suite.
    real_subprocess_run = subprocess.run

    def _guard_no_nested_pytest_spawn(*args, **kwargs):  # type: ignore[no-untyped-def]
        command = args[0] if args else kwargs.get("args")
        if command and any("pytest" in str(part) for part in command):
            raise AssertionError(
                "this unit test must never spawn a nested pytest suite -- "
                "a seam bypassed both `python_for` patches and reached a "
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
