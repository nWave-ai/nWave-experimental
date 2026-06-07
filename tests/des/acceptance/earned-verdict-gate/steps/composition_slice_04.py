"""Composition root for slice-04 (commit gate + self-test) of the earned-verdict gate.

Mandate-13 (driving-port-only) + Pillar 3, Layer 4 wiring_e2e: the SUT is
exercised through the REAL installed PreToolUse hook invoked as a subprocess over
its JSON stdin protocol with a ``git commit`` tool event. The hook is NEVER
imported and called in-process for AT-1; it is driven exactly as Claude Code
drives it (``python -c "from <handler> import handle_pre_tool_use; ..."`` reading
a JSON event on stdin), mirroring the established g-commit-exit-gate precedent
(tests/des/acceptance/atdd_pure_spine_hardening/steps/slice02_composition.py).

ALL business logic lives in the production commit-gate hook branch + the
slice-01/02/03 ports behind it. This module's service methods only (a) stage a
slice + its ATs, (b) invoke the real hook subprocess with a ``git commit``
event, and (c) parse + port-expose the hook's decision body. Step bodies in
``slice_04_steps.py`` delegate here and never inline business logic
(Mandate-12 criterion 3).

DEPENDENCY (FLAGGED): the gate cannot perturb-and-re-run without slice-02
(TestRunnerPort) + slice-03 (SeamInjectionPort). These ATs are scaffolded
@skip @pending; today they RED because the commit-gate hook branch / self-test
entry do not exist (driving-port-absent RED -- the correct RED for an unbuilt
capstone). The exact handler module + self-test entry are DELIVER's choice once
DESIGN confirms the commit-gate wiring; the placeholders below name the
OBSERVABLE contract (deny on theater, self-test verdict flips RED), not the
wiring.

Layer 4: real hook subprocess, real I/O, example-only (Mandate 9/11).
Traditional assertions are permitted at this layer (the Mandate 8 universe-guard
is a layer-1..3 requirement); the hook's decision body + exit code are the
observable surface.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types import CommitGateDecision, SliceHealth, VerdictStatus


# The production PreToolUse hook handler the commit gate lives in. The
# earned-verdict commit gate is a NEW PreToolUse branch firing on a Bash
# ``git commit`` -- DELIVER creates it (in pre_tool_use_handler or a dedicated
# handler). Until then the subprocess emits no deny body, which is the
# RIGHT-reason RED: missing functionality at the driving port. The exact module
# is DESIGN-confirmed in DELIVER; this is the established handler entry point.
_HANDLER_MODULE = "des.adapters.drivers.hooks.pre_tool_use_handler"

# The gate's self-test entry (AT-2). The gate perturbs its OWN verdict CORE and
# demands its verdict flips RED. Per GAP-3(b) resolution (DESIGN, feature-delta)
# this is a dedicated ``python -m des.cli.earned_verdict_self_test`` subcommand
# that is independently driving-port-testable as a Layer-3/4 subprocess and
# reuses the established ``python -m`` invocation (mirrors run_tests/inject_seam).
_SELF_TEST_MODULE = "des.cli.earned_verdict_self_test"

# The CORE's OWN declared seam (GAP-3b). The CORE ships a ``nwave.seam_manifest.v1``
# naming ``verdict-core`` -> real=the real ``compute_verdict``, fault=a
# deliberately-broken ``compute_verdict`` stand-in. The self-test perturbs THIS
# seam (the uniform ``NWAVE_PERTURB`` selector, frozen contract) to prove the
# gate is causally bound to its own perturbation, not hard-wiring RED.
_CORE_SEAM = "verdict-core"


def _commit_event(slice_health: SliceHealth) -> str:
    """Build the PreToolUse ``git commit`` hook event JSON for a staged slice.

    The earned-verdict commit gate fires on a Bash ``git commit``. The slice's
    honesty is carried on the commit command so the gate knows which slice's ATs
    to perturb. The exact marker contract is DELIVER's to define; this stages a
    representative ``git commit`` event whose slice carries the staged health.
    """
    return json.dumps(
        {
            "tool_name": "Bash",
            "tool_input": {
                "command": f"git commit -m 'slice ({slice_health.value})'",
            },
        }
    )


@dataclass
class CommitGateResult:
    """Observable outcome of one commit-gate hook invocation.

    The hook's decision body (allow / deny-block) + exit code are the observable
    surface. ``self_test_status`` carries the gate's own verdict on the
    self-test path. ``raw`` retains the parsed decision body.
    """

    decision: CommitGateDecision | None = None
    self_test_status: VerdictStatus | None = None
    reason_text: str | None = None
    exit_code: int | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class CommitGateComposition:
    """Production composition root for the earned-verdict PreToolUse commit gate.

    Stages a slice + its ATs, invokes the REAL PreToolUse hook subprocess with a
    ``git commit`` event, and parses the hook's decision body. The gate's
    perturb-and-re-run logic (slice-01/02/03 behind it) is the single source of
    truth for the decision -- this composition never re-computes it (no shadow
    oracle); it stages a slice + transports the decision.
    """

    result: CommitGateResult = field(default_factory=CommitGateResult)
    control_status: VerdictStatus | None = field(default=None, init=False)
    _slice_health: SliceHealth = field(default=SliceHealth.ALL_EARNED, init=False)
    _self_test_core_perturbed: bool = field(default=False, init=False)

    def given_slice(self, slice_health: SliceHealth) -> None:
        """Stage a slice whose acceptance tests carry the given honesty."""
        self._slice_health = slice_health

    def given_core_perturbed(self) -> None:
        """Stage the self-test: the gate's own verdict CORE is perturbed."""
        self._self_test_core_perturbed = True

    def attempt_commit(self) -> CommitGateResult:
        """Invoke the REAL PreToolUse hook over a ``git commit`` event.

        Runs the production hook exactly as Claude Code does -- a subprocess
        reading the JSON event on stdin -- and parses the decision body. The
        decision is the gate's; the composition only stages + transports.
        """
        runner = (
            "import sys; "
            f"from {_HANDLER_MODULE} import handle_pre_tool_use; "
            "sys.exit(handle_pre_tool_use())"
        )
        completed = subprocess.run(
            [sys.executable, "-c", runner],
            input=_commit_event(self._slice_health),
            capture_output=True,
            text=True,
            cwd=str(Path.cwd()),
        )
        return self._decision_from_output(completed.stdout, completed.returncode)

    def run_self_test(self) -> CommitGateResult:
        """Run the gate's self-test over its perturbed verdict CORE (AT-2).

        GAP-3(b) keystone (closes MAJOR-1): the perturbation MUST reach the
        subprocess for the flip to be GENUINE rather than hard-wired RED. When
        ``_self_test_core_perturbed`` is set, the self-test is invoked with
        ``--perturb-core <core-seam>`` on argv AND ``NWAVE_PERTURB=<core-seam>``
        in the subprocess env (the uniform frozen selector). The self-test then
        perturbs the CORE's OWN ``verdict-core`` seam, re-runs the CORE's AT
        suite, and -- because a broken CORE no longer flips its verdicts --
        emits ``status:RED`` and denies its own commit.
        """
        return self._invoke_self_test(perturb=self._self_test_core_perturbed)

    def run_self_test_control(self) -> None:
        """Run the un-perturbed self-test control leg (AT-2 differential).

        GAP-3(b) anti-theater proof: the differential ``(perturbed -> RED) and
        (baseline -> GREEN)`` is the honesty proof. A gate that emitted RED
        regardless of perturbation would FAIL this control (it would emit RED
        un-perturbed too). This control leg makes the flip a WITNESSED two-run
        guarantee inside AT-2, closing the hard-coded-RED hole inside the AT.
        Stores the control verdict on ``control_status`` for the Then step.
        """
        self.control_status = self._invoke_self_test(perturb=False).self_test_status

    def _invoke_self_test(self, perturb: bool) -> CommitGateResult:
        """Invoke the self-test driving port as a subprocess (perturbed or control).

        Single source of the ``python -m des.cli.earned_verdict_self_test``
        invocation. The ``perturb`` flag carries the ``--perturb-core`` argv +
        ``NWAVE_PERTURB`` env through to the subprocess so the perturbation is a
        REAL selection against the CORE's own seam, never a dropped flag.
        """
        argv = [sys.executable, "-m", _SELF_TEST_MODULE]
        env = dict(os.environ)
        if perturb:
            argv += ["--perturb-core", _CORE_SEAM]
            env["NWAVE_PERTURB"] = _CORE_SEAM
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            cwd=str(Path.cwd()),
            env=env,
        )
        return self._self_test_from_output(completed.stdout, completed.returncode)

    def _decision_from_output(self, stdout: str, exit_code: int) -> CommitGateResult:
        """Parse the hook's decision body into a ``CommitGateResult``.

        When the commit-gate hook branch does not exist yet (RED scaffold) the
        hook emits no deny body; the result then carries only the exit code, and
        the decision Then steps fail for the RIGHT reason (missing functionality
        at the driving port).
        """
        body = self._parse_body(stdout)
        denied = body.get("decision") == "block" or (
            body.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"
        )
        return CommitGateResult(
            decision=CommitGateDecision.DENIED
            if denied
            else (CommitGateDecision.ALLOWED if body else None),
            reason_text=body.get("reason"),
            exit_code=exit_code,
            raw=body,
        )

    def _self_test_from_output(self, stdout: str, exit_code: int) -> CommitGateResult:
        """Parse the self-test emission into a ``CommitGateResult``."""
        body = self._parse_body(stdout)
        status_str = body.get("status")
        denied = body.get("decision") == "block" or status_str == "RED"
        return CommitGateResult(
            self_test_status=VerdictStatus(status_str)
            if status_str is not None
            else None,
            decision=CommitGateDecision.DENIED if denied else None,
            exit_code=exit_code,
            raw=body,
        )

    @staticmethod
    def _parse_body(stdout: str) -> dict:
        """Parse the last JSON object the hook printed to stdout (or {})."""
        for line in reversed(stdout.strip().splitlines()):
            stripped = line.strip()
            if stripped.startswith("{"):
                return json.loads(stripped)
        return {}

    def reports_theater_reason(self) -> bool:
        """Whether the deny reason names the theater test (AT-1).

        Port-exposed observable: the deny body's reason mentions theater so the
        operator knows WHY the commit was denied, not just THAT it was.
        """
        return bool(self.result.reason_text) and "theater" in (
            self.result.reason_text or ""
        )
