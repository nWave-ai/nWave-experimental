"""RED->GREEN for techdebt row
``five-of-seven-polyglot-runners-shell-out-with-no-timeout-bound``.

Of the seven language runner adapters, only ``pytest_runner`` and
``cargo_runner`` bound their ``subprocess.run`` call with
``timeout=run_timeout_seconds()`` and translate ``subprocess.TimeoutExpired``
into a named ``RunnerAdapterUnavailable`` (INDETERMINATE, GDP-6 degrade-LOUD).
The other five -- go, java, kotlin, vitest, csharp -- called ``subprocess.run``
with no ``timeout=`` at all, so a hung target-language test run blocks the
calling DES gate/service forever instead of degrading LOUD.

This test drives each of the five ``run_*_scope`` functions with
``subprocess.run`` mocked to raise ``subprocess.TimeoutExpired`` and asserts
the SAME contract cargo_runner already honors: the timeout is caught and
re-raised as ``RunnerAdapterUnavailable`` naming the timeout, never left to
propagate as a bare ``TimeoutExpired`` (which would hang the caller's own
except-clause expectations) or -- worse -- left unbound so the subprocess call
itself never returns.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from des.adapters.driven.runner.tool_discovery import ToolResolution
from des.ports.test_runner_port import RunnerAdapter, RunnerAdapterUnavailable


_CASES = [
    (
        "des.adapters.driven.runner.go_runner",
        "run_go_scope",
        "go-test",
        "/usr/bin/go",
    ),
    (
        "des.adapters.driven.runner.java_runner",
        "run_java_scope",
        "java-test",
        "/usr/bin/mvn",
    ),
    (
        "des.adapters.driven.runner.kotlin_runner",
        "run_kotlin_scope",
        "kotlin-test",
        "/usr/bin/gradlew",
    ),
    (
        "des.adapters.driven.runner.vitest_runner",
        "run_vitest_scope",
        "vitest",
        "/usr/bin/vitest",
    ),
    (
        "des.adapters.driven.runner.csharp_runner",
        "run_csharp_scope",
        "csharp-test",
        "/usr/bin/dotnet",
    ),
]


@pytest.mark.parametrize("module_path, func_name, adapter_name, tool_path", _CASES)
def test_hung_subprocess_degrades_to_named_indeterminate(
    module_path: str, func_name: str, adapter_name: str, tool_path: str, tmp_path: Path
) -> None:
    import importlib

    module = importlib.import_module(module_path)
    run_scope = getattr(module, func_name)
    adapter = RunnerAdapter(name=adapter_name)

    with (
        patch.object(
            module,
            "resolve_tool",
            return_value=ToolResolution(rung="on-path", path=tool_path),
        ),
        patch.object(
            module,
            "subprocess",
        ) as mock_subprocess,
    ):
        mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired
        mock_subprocess.run.side_effect = subprocess.TimeoutExpired(
            cmd=[tool_path], timeout=2700
        )

        with pytest.raises(RunnerAdapterUnavailable) as exc_info:
            run_scope(adapter, tmp_path, (tool_path.rsplit("/", 1)[-1], "test"))

    assert "did not complete within" in str(exc_info.value)
    assert "NWAVE_GATE_RUN_TIMEOUT" in str(exc_info.value)
