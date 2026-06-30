"""Composition root for slice-02 -- the `des feature-end sign` CLI.

slice-02 of oss-feature-end-emit-cli (DDD-7 RATIFIED 2026-06-03).

Mandate-13 (driving-port-only) + Pillar 3: the SUT is exercised through the
PRODUCTION single entry point -- the real `des feature-end sign` subcommand
invoked end-to-end over the `des.cli.__main__` dispatcher as a subprocess
(Layer 3 subprocess, the SAME driving surface as slice-01's `des
emit-feature-end` and as `des verify-slice-commit`). The composition NEVER
imports the signing use-case's `main` / the sign function and calls it at the
step boundary; the only entry is the real subprocess through the dispatcher,
exactly as an operator (or the eventual SubagentStop hook shim) invokes it.

OBSERVABLE READ-BACK (substrate verification, NOT a second SUT)
--------------------------------------------------------------
The produced `verdict_hash` is read off the command's stdout; the command
exit code and the `SignRefused` payload determine whether the signer refused.

KEYLESS BY CONSTRUCTION (OSS demotion, oss-review-verdict-demotion S4)
----------------------------------------------------------------------
No reviewer signing key is provisioned. The signing-key env var is SCRUBBED
for every subprocess run. A sign request with NO real verdict is REFUSED;
key absence is a non-event for real-verdict inputs.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process
from tests.env_parity import seed_dev_checkout_marker

from .domain_types import FeatureEndRecord
from .domain_types_slice_02 import (
    DeepReviewRecord,
    DeepReviewVerdict,
    FeatureId,
    MalformedVerdictKind,
    ReviewerAgentId,
    SignOutcome,
    VerdictHash,
)


_FEATURE_ID = FeatureId("oss-feature-end-demo")

# The canonical real deep-review verdict the happy-path scenarios sign: a real
# reviewer agent, an APPROVED decision, real findings.
_REVIEWER_AGENT = ReviewerAgentId("nw-software-crafter-reviewer")


@dataclass
class SignResult:
    """The observable result of one `des feature-end sign` invocation.

    Universe entries are port-exposed only (Mandate 8): the command outcome
    (succeeded / refused, derived from the exit code), the produced
    `verdict_hash` read off stdout, and whether the refusal came from the
    SIGNER's own anti-theater check (`refused_by_signer`) versus a dispatcher
    miss -- never an internal use-case struct.

    `refused_by_signer` is the discriminator that makes the refusal scenarios
    RED-for-the-right-reason: today `des feature-end sign` is an unknown
    subcommand, so the dispatcher exits non-zero WITHOUT emitting the signer's
    structured refusal payload -- the refusal assertions must reject that
    vacuous path and only pass once the real signer exists and refuses with its
    own `SignRefused` marker (the same shape slice-01's `EmitRefused` carries).
    """

    outcome: SignOutcome
    exit_code: int
    produced_hash: str | None
    refused_by_signer: bool
    stdout: str
    stderr: str


@dataclass
class EmitResult:
    """The observable result of feeding a hash to the slice-01 consumer."""

    outcome: SignOutcome
    exit_code: int


class FeatureEndSignComposition:
    """Production-wired composition root for the `des feature-end sign` slice.

    The driving port is the real `des feature-end sign` subcommand invoked over
    the `des` dispatcher as a subprocess; the observable surface is the command
    exit code and the `verdict_hash` it prints. The command runs KEYLESS -- the
    signing-key env var is always scrubbed.
    """

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        self._feature_id = _FEATURE_ID
        # Env-parity (F21/RCA-#68): the `des` subprocess runs with
        # cwd=project_root (the per-test tmp workspace). Mark it a developer
        # checkout so the runtime-freshness gate AUTOSKIPS instead of the
        # customer-install REFUSAL (exit 78). Same honest fix as slice-01 --
        # NOT a NWAVE_FRESHNESS=skip mask. See tests/env_parity.py.
        seed_dev_checkout_marker(self._project_root)

    # --- the real deep-review verdict (the signer's required input) ----------

    @property
    def real_deep_review_verdict(self) -> DeepReviewRecord:
        """The canonical REAL deep-review verdict the happy path signs."""
        return DeepReviewRecord(
            feature_id=self._feature_id,
            reviewer_agent_id=_REVIEWER_AGENT,
            verdict=DeepReviewVerdict.APPROVED,
            findings=("no blocking findings", "coverage complete"),
        )

    def deep_review_verdict_with(self, verdict: DeepReviewVerdict) -> DeepReviewRecord:
        """A real deep-review verdict carrying a chosen decision (APPROVED/REJECTED)."""
        return DeepReviewRecord(
            feature_id=self._feature_id,
            reviewer_agent_id=_REVIEWER_AGENT,
            verdict=verdict,
            findings=("no blocking findings",),
        )

    # --- driving-port invocation (the SUT) -----------------------------------

    def sign(self, verdict: DeepReviewRecord) -> SignResult:
        """Invoke the REAL `des feature-end sign` subcommand over the dispatcher.

        Supplies the real deep-review verdict (agent + verdict + findings); the
        keyless signer content-hashes it and prints the produced `verdict_hash`.
        No signing key is provisioned -- key absence is a non-event.
        """
        argv = [
            "feature-end",
            "sign",
            "--repo",
            str(self._project_root),
            "--feature-id",
            str(verdict.feature_id),
            "--reviewer-agent-id",
            str(verdict.reviewer_agent_id),
            "--verdict",
            verdict.verdict.value,
        ]
        for finding in verdict.findings:
            argv += ["--finding", finding]
        return self._run_sign(argv)

    def sign_malformed(self, kind: MalformedVerdictKind) -> SignResult:
        """Invoke `des feature-end sign` with a non-real verdict input (refusal path).

        Each `MalformedVerdictKind` violates the real-verdict precondition the
        anti-theater invariant requires (empty agent / unknown verdict / missing
        verdict / no record). The signer must REFUSE and produce NO hash.
        """
        base = [
            "feature-end",
            "sign",
            "--repo",
            str(self._project_root),
            "--feature-id",
            str(self._feature_id),
        ]
        if kind is MalformedVerdictKind.NO_RECORD:
            argv = base  # no agent, no verdict at all
        elif kind is MalformedVerdictKind.MISSING_VERDICT:
            argv = base + ["--reviewer-agent-id", str(_REVIEWER_AGENT)]
        elif kind is MalformedVerdictKind.EMPTY_AGENT:
            argv = base + [
                "--reviewer-agent-id",
                "   ",
                "--verdict",
                DeepReviewVerdict.APPROVED.value,
            ]
        elif kind is MalformedVerdictKind.UNKNOWN_VERDICT:
            argv = base + [
                "--reviewer-agent-id",
                str(_REVIEWER_AGENT),
                "--verdict",
                "MAYBE",
            ]
        else:  # pragma: no cover - exhaustive enum
            raise AssertionError(f"unhandled malformed kind: {kind}")
        return self._run_sign(argv)

    def emit_with_signed_hash(self, signed_hash: VerdictHash) -> EmitResult:
        """Feed a hash to the REAL slice-01 `des emit-feature-end` consumer.

        Closes the end-to-end loop: the signer's output is accepted by the
        slice-01 consumer (`--record FeatureEndReviewVerdict --verdict-hash`),
        proving the two slices compose through the single `des` entry point.
        """
        argv = [
            "emit-feature-end",
            "--repo",
            str(self._project_root),
            "--feature-id",
            str(self._feature_id),
            "--record",
            FeatureEndRecord.DEEP_REVIEW_VERDICT.value,
            "--verdict-hash",
            str(signed_hash),
        ]
        completed = self._dispatch(argv)
        outcome = (
            SignOutcome.SUCCEEDED if completed.returncode == 0 else SignOutcome.REFUSED
        )
        return EmitResult(outcome=outcome, exit_code=completed.returncode)

    def sign_then_emit_round_trips(self) -> bool:
        """Whether signing a real verdict then emitting its hash both succeed.

        The back-compat round-trip (DDD-7): the consolidated `des feature-end
        sign` produces a content hash AND the consolidated/preserved `des
        emit-feature-end` consumer accepts it -- proving the two verbs compose
        under the single entry point. Encapsulated here so the step body stays a
        single delegate + assert (Mandate-12 criterion 3).
        """
        signed = self.sign(self.real_deep_review_verdict)
        if signed.outcome is not SignOutcome.SUCCEEDED or signed.produced_hash is None:
            return False
        emit = self.emit_with_signed_hash(VerdictHash(signed.produced_hash))
        return emit.outcome is SignOutcome.SUCCEEDED

    def is_feature_end_namespace_reachable(self) -> bool:
        """Whether `des feature-end --help` resolves the consolidated namespace.

        Single-entry-point / 1:1 mirror probe (DDD-7, AD-26): the consolidated
        `des feature-end` surface is dispatchable through the one `des` entry
        point. Reachable iff the help invocation exits zero and advertises the
        `sign` verb.
        """
        completed = self._dispatch(["feature-end", "--help"])
        return completed.returncode == 0 and "sign" in completed.stdout

    # --- subprocess plumbing -------------------------------------------------

    def _run_sign(self, argv: list[str]) -> SignResult:
        completed = self._dispatch(argv)
        outcome = (
            SignOutcome.SUCCEEDED if completed.returncode == 0 else SignOutcome.REFUSED
        )
        produced = (
            _extract_produced_hash(completed.stdout)
            if completed.returncode == 0
            else None
        )
        return SignResult(
            outcome=outcome,
            exit_code=completed.returncode,
            produced_hash=produced,
            refused_by_signer=_carries_signer_refusal(
                completed.stdout, completed.stderr
            ),
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def _dispatch(self, argv: list[str]) -> subprocess.CompletedProcess[str]:
        """Dispatch `des <argv>` through the real `des.cli.__main__` entry point."""
        # Keyless post-demotion (oss-review-verdict-demotion S4): scrub any
        # ambient signing key so the signer runs entirely keyless. Restored in
        # `finally` -- shared-process safe.
        prior_key = os.environ.pop("NWAVE_REVIEWER_SIGNING_KEY", None)
        try:
            exit_code, stdout, stderr = run_cli_in_process(
                list(argv), cwd=str(self._project_root)
            )
        finally:
            if prior_key is not None:
                os.environ["NWAVE_REVIEWER_SIGNING_KEY"] = prior_key
        return subprocess.CompletedProcess(argv, exit_code, stdout, stderr)


def _carries_signer_refusal(stdout: str, stderr: str) -> bool:
    """Whether the refusal came from the SIGNER's own anti-theater check.

    The production signer emits a structured `{"event": "SignRefused", ...}`
    payload on every refusal (the same shape slice-01's `EmitRefused` carries) --
    a real input-check refusal, NOT a dispatcher miss. An unknown-subcommand
    dispatcher error (today's RED state) emits NO such payload, so this returns
    False and the refusal scenarios stay RED until the real signer exists and
    refuses with its own marker. This is the discriminator that closes the
    vacuous-refusal trap (the same trap slice-01's conftest documented for AT-3).
    """
    for stream in (stdout, stderr):
        for line in stream.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("event") == "SignRefused":
                return True
    return False


def _extract_produced_hash(stdout: str) -> str | None:
    """Pull the produced `verdict_hash` off the signer's machine-readable stdout."""
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "verdict_hash" in payload:
            return str(payload["verdict_hash"])
    return None


__all__ = [
    "EmitResult",
    "FeatureEndSignComposition",
    "SignResult",
]
