"""Composition root for the oss-earned-verdict-gate acceptance suite.

Mandate-13 (driving-port-only) + Pillar 3: the SUT is exercised through the
PRODUCTION composition root -- the real ``earned-verdict`` CLI invoked as a
``python -m des.cli.earned_verdict`` subprocess. The CORE is NEVER imported and
called directly (no ``from des.domain.earned_verdict import compute_verdict``);
the only entry is the CLI driving port. The CLI reads two
``nwave.test_result.v1`` JSON files (baseline + perturbed) plus the opaque
``--seam-id`` / ``--at-id``, and emits one ``nwave.earned_verdict.v1`` JSON.

ALL business logic lives in the production CORE behind that CLI. This module's
service methods only (a) stage the two RUN envelopes as on-disk JSON, (b)
invoke the CLI as a subprocess, and (c) parse + schema-validate the emitted
verdict envelope into a port-exposed ``VerdictResult``. Step bodies in
``common_steps.py`` delegate here and never inline business logic
(Mandate-12 criterion 3).

target-blind invariant: the staged RUN envelopes carry a ``runner`` field
(frozen on ``nwave.test_result.v1``) but the composition never asks the CORE to
branch on it -- the verdict is computed from counts + exit code alone. The
acceptance suite never names pytest/jest/etc in any *expected* CORE behaviour.

Layer 3 (subprocess CLI + JSON assertion): real I/O (a real subprocess, real
JSON files on a tmp path), example-only -- no PBT machinery is imported here
(Mandate 9/11). Traditional + state-delta assertions both permitted; the
emitted verdict's port-exposed fields (``status``, ``reason``, echoed
``seam_id`` / ``at_id``) are the universe.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types import (
    AtId,
    RunShape,
    SeamId,
    VerdictReason,
    VerdictStatus,
)


# The two frozen contract identifiers. The CORE consumes ``test_result.v1`` and
# emits ``earned_verdict.v1`` -- the composition pins both so a drift in either
# schema string surfaces as a failing assertion, not a silent pass.
TEST_RESULT_SCHEMA = "nwave.test_result.v1"
EARNED_VERDICT_SCHEMA = "nwave.earned_verdict.v1"

# The production driving port: the ``earned-verdict`` CLI module, invoked as a
# subprocess (``python -m``). This module does NOT exist yet -- DELIVER creates
# it. Until then the subprocess exits non-zero (ModuleNotFoundError), which is
# the RIGHT-reason RED: missing functionality at the driving port.
_CLI_MODULE = "des.cli.earned_verdict"

# A neutral opaque runner label. The CORE must NOT branch on this -- it is
# carried only because ``runner`` is a frozen field of ``test_result.v1``.
# Deliberately not a real-runner literal, to keep the target-blind contract
# legible: the CORE's behaviour is identical for any runner string.
_OPAQUE_RUNNER = "opaque-runner"


def _test_result_envelope(shape: RunShape, runner: str = _OPAQUE_RUNNER) -> dict:
    """Build a complete ``nwave.test_result.v1`` envelope from a ``RunShape``.

    Only ``passed`` / ``failed`` / ``exit_code`` carry the scenario's intent;
    the remaining frozen fields take neutral zero defaults. ``collected`` is
    derived as ``passed + failed`` so the envelope is internally coherent.
    """
    return {
        "schema": TEST_RESULT_SCHEMA,
        "runner": runner,
        "exit_code": shape.exit_code,
        "collected": shape.passed + shape.failed,
        "passed": shape.passed,
        "failed": shape.failed,
        "xfailed": 0,
        "xpassed": 0,
        "skipped": 0,
        "deselected": 0,
        "error": 0,
    }


@dataclass
class VerdictResult:
    """Observable outcome of one ``earned-verdict`` CLI invocation.

    Universe entries are port-exposed only (the emitted ``earned_verdict.v1``
    fields + the CLI exit code) -- never internal CORE struct fields
    (Mandate 8). ``raw`` retains the full emitted envelope so a Then step can
    schema-validate it against the frozen contract.
    """

    status: VerdictStatus | None = None
    reason: VerdictReason | None = None
    seam_id: str | None = None
    at_id: str | None = None
    exit_code: int | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class EarnedVerdictComposition:
    """Production composition root for the ``earned-verdict`` CLI (the CORE).

    Stages two RUN envelopes, invokes the real CLI subprocess, and parses the
    emitted VERDICT envelope. The CORE's deterministic rule is the single
    source of truth for the verdict -- this composition never re-computes it
    (no shadow oracle).
    """

    result: VerdictResult = field(default_factory=VerdictResult)
    _workspace: Path | None = field(default=None, init=False)
    _baseline: RunShape | None = field(default=None, init=False)
    _perturbed: RunShape | None = field(default=None, init=False)
    _seam_id: SeamId = field(default=SeamId("declared-dependency"), init=False)
    _at_id: AtId = field(default=AtId("node-under-test"), init=False)

    def given_baseline_run(self, shape: RunShape) -> None:
        """Stage the baseline ``test_result.v1`` (the run before perturbation)."""
        self._baseline = shape

    def given_perturbed_run(self, shape: RunShape) -> None:
        """Stage the perturbed ``test_result.v1`` (the run with the seam broken)."""
        self._perturbed = shape

    def compute_earned_verdict(self) -> VerdictResult:
        """Invoke the ``earned-verdict`` CLI over the two staged RUN envelopes.

        Writes baseline + perturbed as ``nwave.test_result.v1`` JSON files on a
        tmp path, runs ``python -m des.cli.earned_verdict`` with the documented
        args, and parses the emitted ``nwave.earned_verdict.v1`` JSON. The
        verdict is the CORE's -- the composition only transports envelopes.
        """
        workspace = Path(tempfile.mkdtemp(prefix="earned-verdict-"))
        self._workspace = workspace
        baseline_path = workspace / "baseline.test_result.json"
        perturbed_path = workspace / "perturbed.test_result.json"
        out_path = workspace / "verdict.earned_verdict.json"
        assert self._baseline is not None, "baseline run not staged -- given_* missing"
        assert self._perturbed is not None, (
            "perturbed run not staged -- given_* missing"
        )
        baseline_path.write_text(
            json.dumps(_test_result_envelope(self._baseline)), encoding="utf-8"
        )
        perturbed_path.write_text(
            json.dumps(_test_result_envelope(self._perturbed)), encoding="utf-8"
        )
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                _CLI_MODULE,
                "--baseline",
                str(baseline_path),
                "--perturbed",
                str(perturbed_path),
                "--seam-id",
                str(self._seam_id),
                "--at-id",
                str(self._at_id),
                "--out",
                str(out_path),
            ],
            capture_output=True,
            text=True,
        )
        return self._result_from_emission(out_path, completed.returncode)

    def _result_from_emission(self, out_path: Path, exit_code: int) -> VerdictResult:
        """Parse the emitted ``earned_verdict.v1`` JSON into a ``VerdictResult``.

        When the CLI does not exist yet (RED scaffold) the subprocess exits
        non-zero and writes no envelope; the result then carries only the
        exit code, and the schema/status assertions in the Then steps fail for
        the RIGHT reason (missing functionality at the driving port).
        """
        if not out_path.is_file():
            return VerdictResult(exit_code=exit_code)
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        status_str = payload.get("status")
        reason_str = payload.get("reason")
        return VerdictResult(
            status=VerdictStatus(status_str) if status_str is not None else None,
            reason=VerdictReason(reason_str) if reason_str is not None else None,
            seam_id=payload.get("seam_id"),
            at_id=payload.get("at_id"),
            exit_code=exit_code,
            raw=payload,
        )

    def emitted_envelope_is_valid_earned_verdict(self) -> bool:
        """Whether the emitted envelope conforms to ``nwave.earned_verdict.v1``.

        Validates the frozen-contract shape: the ``schema`` discriminator, the
        closed ``status`` + ``reason`` enums, the echoed ``seam_id`` / ``at_id``
        the CORE carried through, and the two embedded ``test_result.v1``
        sub-envelopes (baseline + perturbed). Port-exposed observable only --
        the validator reads the emitted JSON, never a CORE struct.
        """
        payload = self.result.raw
        if payload.get("schema") != EARNED_VERDICT_SCHEMA:
            return False
        if payload.get("status") not in {s.value for s in VerdictStatus}:
            return False
        if payload.get("reason") not in {r.value for r in VerdictReason}:
            return False
        for key in ("seam_id", "at_id", "baseline", "perturbed"):
            if key not in payload:
                return False
        for sub in (payload["baseline"], payload["perturbed"]):
            if not isinstance(sub, dict) or sub.get("schema") != TEST_RESULT_SCHEMA:
                return False
        return True

    def emitted_echo_matches_inputs(self) -> bool:
        """Whether the emitted ``seam_id`` / ``at_id`` ECHO the exact inputs.

        The frozen ``nwave.earned_verdict.v1`` contract names ``seam_id`` and
        ``at_id`` as carry-through fields: the CORE echoes verbatim the
        ``--seam-id`` / ``--at-id`` it was asked about. Presence alone is a
        theater hole -- a CORE that drops, swaps, or hard-codes the echo would
        still satisfy ``emitted_envelope_is_valid_earned_verdict``. This guard
        asserts FIDELITY: the emitted echo equals the exact opaque identifiers
        this composition passed to the CLI driving port (``self._seam_id`` /
        ``self._at_id``), so an echo that drops or swaps the carry-through reds
        the AT. Port-exposed observable only -- compares the emitted JSON
        against the composition's own staged inputs, never a CORE struct.
        """
        return self.result.seam_id == str(self._seam_id) and self.result.at_id == str(
            self._at_id
        )
