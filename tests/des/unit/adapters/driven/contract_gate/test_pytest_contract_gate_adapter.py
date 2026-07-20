"""Regression: ``PythonContractGateAdapter.run_suite`` leverages parallelism.

RCA (2026-07-19, throughput regression ~10min -> 40min+): the registered
``ContractGatePort`` facet for tool-name ``"pytest"`` intercepts EVERY Python
repo's feature-end full-suite run -- including nwave-dev's own dogfood repo,
since it resolves to the SAME tool-name a customer target would. Its
``run_suite`` hardcoded a bare serial ``pytest -p no:cacheprovider`` invocation,
never consulting the SAME config-driven parallel-worker seam
(``run_contract_gate._parallel_pytest_args`` -- env ``NWAVE_GATE_JOBS`` >
``.nwave/config.yaml`` ``gate.jobs`` > ``auto``) the CLI's own
``_run_contract_suite`` fallback leg already used. Confirmed via
``/proc/<pid>/cmdline`` on the actually-running feature-end subprocess: no
``-n`` flag, no marker filter -- an exact match for this adapter's old argv.

The fix reuses that ONE seam rather than re-deriving parallelism twice, so
EVERY Python target this facet serves benefits generically (never an
nwave-dev-only carve-out).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from des.adapters.driven.contract_gate import pytest_contract_gate_adapter as pcga
from des.adapters.driven.contract_gate.pytest_contract_gate_adapter import (
    PythonContractGateAdapter,
)
from des.adapters.driven.runner import pytest_runner


class _RecordingCompletedProcess:
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode


def _capture_argv(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []

    def _fake_run(argv: list[str], **kwargs: Any) -> _RecordingCompletedProcess:
        calls.append(argv)
        return _RecordingCompletedProcess(returncode=0)

    # `run_suite` shells through the process-group-reaping helper
    # (`run_pytest_reaped`), resolved from the `pytest_runner` module at call
    # time; stub it there so the recorded argv is asserted without a real process.
    monkeypatch.setattr(pytest_runner, "run_pytest_reaped", _fake_run)
    monkeypatch.setattr(pcga, "python_for", lambda _cap, repo_root: "python3")
    return calls


def test_run_suite_includes_parallel_flags_when_xdist_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("NWAVE_GATE_JOBS", raising=False)
    from des.cli import run_contract_gate as rcg

    monkeypatch.setattr(rcg, "can_import", lambda _interp, _mod: True)
    calls = _capture_argv(monkeypatch)

    verdict = PythonContractGateAdapter().run_suite(tmp_path)

    assert verdict.passed is True
    assert len(calls) == 1
    argv = calls[0]
    assert "-n" in argv
    assert argv[argv.index("-n") + 1] == "auto"
    assert "--dist" in argv
    assert argv[argv.index("--dist") + 1] == "loadgroup"


def test_run_suite_never_adds_the_nwave_dev_marker_filter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A customer repo must never inherit nwave-dev's own dogfood marker."""
    from des.cli import run_contract_gate as rcg

    monkeypatch.setattr(rcg, "can_import", lambda _interp, _mod: True)
    calls = _capture_argv(monkeypatch)

    PythonContractGateAdapter().run_suite(tmp_path)

    # "-m" legitimately appears once as the "python -m pytest" module
    # invocation; it must NOT appear a second time as a marker-filter flag.
    argv = calls[0]
    assert argv.count("-m") == 1
    assert "unit or integration or acceptance" not in argv


def test_run_suite_degrades_serial_when_xdist_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from des.cli import run_contract_gate as rcg

    monkeypatch.setattr(rcg, "can_import", lambda _interp, _mod: False)
    calls = _capture_argv(monkeypatch)

    verdict = PythonContractGateAdapter().run_suite(tmp_path)

    assert verdict.passed is True
    assert "-n" not in calls[0]


def test_run_suite_operator_serial_override_still_honoured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NWAVE_GATE_JOBS", "serial")
    from des.cli import run_contract_gate as rcg

    monkeypatch.setattr(rcg, "can_import", lambda _interp, _mod: True)
    calls = _capture_argv(monkeypatch)

    PythonContractGateAdapter().run_suite(tmp_path)

    assert "-n" not in calls[0]


def test_run_suite_junit_xml_still_appended_after_parallel_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("NWAVE_GATE_JOBS", raising=False)
    from des.cli import run_contract_gate as rcg

    monkeypatch.setattr(rcg, "can_import", lambda _interp, _mod: True)
    calls = _capture_argv(monkeypatch)
    junit_path = tmp_path / "out.xml"

    PythonContractGateAdapter().run_suite(tmp_path, junit_xml_path=junit_path)

    assert calls[0][-1] == f"--junit-xml={junit_path}"
