"""Criterion 3: run_contract_gate surfaces InterpreterUnavailable as exit 2.

F-21 boundary contract. `run_contract_gate` resolves its nested pytest
interpreter through `des.runtime.interpreter.python_for("pytest")`. When no
candidate on the fallback ladder is pytest-capable, `python_for` raises
`InterpreterUnavailable` rather than spawning a known-bad interpreter.

The gate must convert that raise into a structured, machine-readable
`InterpreterUnavailable` event on stdout plus exit code 2 -- never let a
pytest-collection traceback escape. Each role (run / digest / verify) must
fail the same diagnosable way.
"""

from __future__ import annotations

import json

import pytest

from des.cli import run_contract_gate
from des.runtime.interpreter import InterpreterUnavailable


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
    converted to a structured malformed-input payload at the gate.
    """
    probed = ["/usr/bin/python3", "/opt/venv/bin/python"]

    def boom(capability):  # type: ignore[no-untyped-def]
        raise InterpreterUnavailable(capability, probed)

    monkeypatch.setattr(run_contract_gate, "python_for", boom)

    exit_code = run_contract_gate.main(argv)
    stdout = capsys.readouterr().out

    assert exit_code == 2
    event = _last_json_event(stdout)
    assert event["event"] == "InterpreterUnavailable"
    assert event["capability"] == "pytest"
    assert event["probed"] == probed
    assert "pytest" in event["error"]
