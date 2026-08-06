"""Subprocess composition root for the retained TestRunnerPort scenarios."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types import TargetHealth


TEST_RESULT_SCHEMA = "nwave.test_result.v1"
TEST_OBSERVATION_SCHEMA = "nwave.test_observation.v1"
_CLI_MODULE = "des.cli.run_tests"
_ABSENT_RUNNER = "no-such-runner"
_TARGET_BODY = {
    TargetHealth.ALL_PASS.value: "def test_one():\n    assert True\n\n\ndef test_two():\n    assert True\n",
    TargetHealth.HAS_FAILURE.value: "def test_passes():\n    assert True\n\n\ndef test_fails():\n    assert False\n",
}


@dataclass
class RunResult:
    """Observable output of one real test-runner CLI invocation."""

    schema: str | None = None
    passed: int | None = None
    failed: int | None = None
    exit_code: int | None = None
    observation: str | None = None
    reason: str | None = None
    cli_exit_code: int | None = None
    raw: dict[str, object] = field(default_factory=dict)


@dataclass
class RunnerComposition:
    """Stage a target and drive the public test-runner subprocess."""

    result: RunResult = field(default_factory=RunResult)
    _workspace: Path | None = field(default=None, init=False)
    _target: TargetHealth | None = field(default=None, init=False)

    def given_target(self, target: TargetHealth) -> None:
        self._target = target

    def run_target(self) -> RunResult:
        workspace = Path(tempfile.mkdtemp(prefix="run-tests-"))
        self._workspace = workspace
        out_path = workspace / "result.json"
        completed = subprocess.run(
            self._build_argv(workspace, out_path), capture_output=True, text=True
        )
        return self._result_from_emission(out_path, completed.returncode)

    def _build_argv(self, workspace: Path, out_path: Path) -> list[str]:
        assert self._target is not None, "target not staged -- given_* missing"
        common = [sys.executable, "-m", _CLI_MODULE, "--target", str(workspace)]
        if self._target is TargetHealth.RUNNER_ABSENT:
            return [*common, "--runner", _ABSENT_RUNNER, "--out", str(out_path)]
        target_dir = workspace / "target"
        target_dir.mkdir()
        (target_dir / "test_staged.py").write_text(
            _TARGET_BODY[self._target.value], encoding="utf-8"
        )
        return [
            sys.executable,
            "-m",
            _CLI_MODULE,
            "--target",
            str(target_dir),
            "--out",
            str(out_path),
        ]

    def _result_from_emission(self, out_path: Path, cli_exit_code: int) -> RunResult:
        if not out_path.is_file():
            return RunResult(cli_exit_code=cli_exit_code)
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        return RunResult(
            schema=payload.get("schema")
            if isinstance(payload.get("schema"), str)
            else None,
            passed=payload.get("passed")
            if isinstance(payload.get("passed"), int)
            else None,
            failed=payload.get("failed")
            if isinstance(payload.get("failed"), int)
            else None,
            exit_code=payload.get("exit_code")
            if isinstance(payload.get("exit_code"), int)
            else None,
            observation=payload.get("observation")
            if isinstance(payload.get("observation"), str)
            else None,
            reason=payload.get("reason")
            if isinstance(payload.get("reason"), str)
            else None,
            cli_exit_code=cli_exit_code,
            raw=payload,
        )

    def emitted_is_valid_test_result(self) -> bool:
        return self.result.schema == TEST_RESULT_SCHEMA and all(
            isinstance(self.result.raw.get(key), int)
            for key in ("exit_code", "collected", "passed", "failed")
        )

    def emitted_is_unobserved(self) -> bool:
        return (
            self.result.schema == TEST_OBSERVATION_SCHEMA
            and self.result.observation == "unobserved"
            and self.result.reason == "runner-absent"
        )

    def no_passing_run_fabricated(self) -> bool:
        return self.result.raw.get("schema") != TEST_RESULT_SCHEMA
