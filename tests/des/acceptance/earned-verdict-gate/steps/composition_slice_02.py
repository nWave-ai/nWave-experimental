"""Composition root for slice-02 (TestRunnerPort) of the earned-verdict gate.

Mandate-13 (driving-port-only) + Pillar 3: the SUT is exercised through the
PRODUCTION composition root -- the real test-runner CLI invoked as a
``python -m des.cli.run_tests`` subprocess. The TestRunnerPort / its pytest
adapter is NEVER imported and called directly; the only entry is the CLI driving
port. The CLI runs a real pytest target staged on a tmp path and emits one
``nwave.test_result.v1`` JSON (counts read from a structured JSON emission of
the run, NEVER scraped from the runner's stdout).

ALL business logic lives in the production adapter behind that CLI. This
module's service methods only (a) stage a real pytest target on a tmp path, (b)
invoke the CLI as a subprocess, and (c) parse + port-expose the emitted
envelope into a ``RunResult``. Step bodies in ``slice_02_steps.py`` delegate
here and never inline business logic (Mandate-12 criterion 3).

Layer 3 (subprocess CLI + JSON assertion): real I/O (a real subprocess, a real
pytest run, real JSON files on a tmp path), example-only -- no PBT machinery is
imported here (Mandate 9/11). The emitted run result's port-exposed fields
(``passed`` / ``failed`` / ``exit_code`` and, on the runner-absent path, the
ABSTAIN ``status`` / ``reason``) are the universe (Mandate 8).

R-1 ENVELOPE CHOICE (design note): ``nwave.test_result.v1`` has no
status/reason field, so "runner-absent" cannot be a malformed ``test_result.v1``
-- it is the gate-level ABSTAIN signal emitted IN PLACE of a run. This
composition reads BOTH possible emissions: a ``nwave.test_result.v1`` (the happy
RUN) and a ``nwave.earned_verdict.v1``-shaped ABSTAIN (status=ABSTAIN,
reason=runner-absent). The concrete envelope the CLI emits for runner-absent is
flagged for DESIGN confirmation in the feature-delta; this composition asserts
the OBSERVABLE contract (abstain present, no fabricated green) independent of
which envelope schema carries it.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types import TargetHealth, VerdictReason


# The frozen contract identifier for the RUN result. TestRunnerPort emits
# ``test_result.v1`` for a real run; the runner-absent fail-safe rides an
# ``earned_verdict.v1``-shaped ABSTAIN envelope (design-flagged) whose ``status``
# field this composition reads directly (no schema-const lookup needed).
TEST_RESULT_SCHEMA = "nwave.test_result.v1"

# The production driving port: the test-runner CLI module, invoked as a
# subprocess (``python -m``). This module does NOT exist yet -- DELIVER creates
# it. Until then the subprocess exits non-zero (ModuleNotFoundError), which is
# the RIGHT-reason RED: missing functionality at the driving port.
_CLI_MODULE = "des.cli.run_tests"

# A real pytest target body per staged TargetHealth. These are REAL test files
# the CLI runs -- the counts in the emitted envelope MUST come from running
# these, not from a template. ``all pass`` has two passing tests; ``has failure``
# has one passing + one failing (so failed>0 AND passed>0 -- a faithful mixed
# run). RUNNER_ABSENT stages no real target; the composition names an
# un-invokable runner so the CLI exercises the fail-safe path.
_TARGET_BODY: dict[str, str] = {
    TargetHealth.ALL_PASS.value: (
        "def test_one():\n    assert True\n\n\ndef test_two():\n    assert True\n"
    ),
    TargetHealth.HAS_FAILURE.value: (
        "def test_passes():\n    assert True\n\n\ndef test_fails():\n    assert False\n"
    ),
}

# A runner name that cannot be invoked -- exercises the R-1 fail-safe abstain.
_ABSENT_RUNNER = "no-such-runner"


@dataclass
class RunResult:
    """Observable outcome of one test-runner CLI invocation.

    Universe entries are port-exposed only (the emitted ``test_result.v1``
    counts, OR the ABSTAIN ``status`` / ``reason`` on the runner-absent path) --
    never internal adapter struct fields (Mandate 8). ``raw`` retains the full
    emitted envelope so a Then step can schema-check it against the frozen
    contract.
    """

    schema: str | None = None
    passed: int | None = None
    failed: int | None = None
    exit_code: int | None = None
    status: str | None = None
    reason: VerdictReason | None = None
    cli_exit_code: int | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class RunnerComposition:
    """Production composition root for the ``run_tests`` CLI (TestRunnerPort).

    Stages a real pytest target, invokes the real CLI subprocess, and parses the
    emitted envelope. The adapter's run logic is the single source of truth for
    the counts -- this composition never re-counts (no shadow oracle); it only
    stages a target and transports the emitted envelope.
    """

    result: RunResult = field(default_factory=RunResult)
    _workspace: Path | None = field(default=None, init=False)
    _target: TargetHealth | None = field(default=None, init=False)

    def given_target(self, target: TargetHealth) -> None:
        """Stage the kind of test target the runner will run."""
        self._target = target

    def run_target(self) -> RunResult:
        """Invoke the ``run_tests`` CLI over the staged target.

        Writes a real pytest target on a tmp path (for runnable targets), runs
        ``python -m des.cli.run_tests`` against it with the documented args, and
        parses the emitted envelope. For the runner-absent target it names an
        un-invokable runner so the CLI exercises the fail-safe path. The result
        is the CLI's emission -- the composition only stages + transports.
        """
        workspace = Path(tempfile.mkdtemp(prefix="run-tests-"))
        self._workspace = workspace
        out_path = workspace / "result.json"
        argv = self._build_argv(workspace, out_path)
        completed = subprocess.run(argv, capture_output=True, text=True)
        return self._result_from_emission(out_path, completed.returncode)

    def _build_argv(self, workspace: Path, out_path: Path) -> list[str]:
        """Compose the CLI argv for the staged target.

        Runnable targets get a real pytest file + the default runner; the
        runner-absent target names an un-invokable runner via ``--runner`` so the
        adapter's fail-safe abstain path is exercised at the driving port.
        """
        assert self._target is not None, "target not staged -- given_* missing"
        if self._target is TargetHealth.RUNNER_ABSENT:
            return [
                sys.executable,
                "-m",
                _CLI_MODULE,
                "--target",
                str(workspace),
                "--runner",
                _ABSENT_RUNNER,
                "--out",
                str(out_path),
            ]
        target_dir = workspace / "target"
        target_dir.mkdir(parents=True, exist_ok=True)
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
        """Parse the emitted envelope into a ``RunResult``.

        When the CLI does not exist yet (RED scaffold) the subprocess exits
        non-zero and writes no envelope; the result then carries only the CLI
        exit code, and the contract/count assertions in the Then steps fail for
        the RIGHT reason (missing functionality at the driving port). Reads both
        envelope shapes -- a ``test_result.v1`` RUN or an ABSTAIN envelope.
        """
        if not out_path.is_file():
            return RunResult(cli_exit_code=cli_exit_code)
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        reason_str = payload.get("reason")
        return RunResult(
            schema=payload.get("schema"),
            passed=payload.get("passed"),
            failed=payload.get("failed"),
            exit_code=payload.get("exit_code"),
            status=payload.get("status"),
            reason=VerdictReason(reason_str) if reason_str is not None else None,
            cli_exit_code=cli_exit_code,
            raw=payload,
        )

    def emitted_is_valid_test_result(self) -> bool:
        """Whether the emitted envelope conforms to ``nwave.test_result.v1``.

        Validates the frozen-contract shape of a RUN result: the ``schema``
        discriminator and the presence of the integer count fields the CORE
        reads. Port-exposed observable only -- reads the emitted JSON, never an
        adapter struct.
        """
        payload = self.result.raw
        if payload.get("schema") != TEST_RESULT_SCHEMA:
            return False
        return all(
            isinstance(payload.get(key), int)
            for key in ("exit_code", "collected", "passed", "failed")
        )

    def emitted_is_fail_safe_abstain(self) -> bool:
        """Whether the emitted envelope is a fail-safe ABSTAIN (not a RUN).

        The runner-absent path MUST NOT emit a ``test_result.v1`` RUN at all; it
        emits an ABSTAIN signal so the gate never trusts a run that never
        happened. Port-exposed observable only.
        """
        return self.result.status == "ABSTAIN"

    def no_passing_run_fabricated(self) -> bool:
        """Whether the runner-absent emission fabricated NO passing run.

        Theater the whole gate exists to prevent: a runner-absent emission that
        nonetheless reports ``passed>0`` would let a never-executed target read
        as green. This guard asserts the emission is NOT a passing
        ``test_result.v1``. Port-exposed observable only.
        """
        payload = self.result.raw
        if payload.get("schema") != TEST_RESULT_SCHEMA:
            return True
        passed = payload.get("passed")
        return not (isinstance(passed, int) and passed > 0)
