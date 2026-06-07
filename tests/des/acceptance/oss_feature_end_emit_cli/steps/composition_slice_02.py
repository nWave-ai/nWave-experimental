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
The produced `verdict_hash` is read off the command's stdout, then RECOMPUTED
independently via the `des.domain.at_review_signing` SSOT
(`compute_verdict_hmac(record, key)` over `canonical_at_review_json(record)`)
to assert the produced hash is a GENUINE HMAC over the real deep-review verdict
input -- not a minted constant. This is allowed (Mandate-13): the recompute
verifies the observable SUBSTRATE the slice-01 consumer (`des emit-feature-end
--verdict-hash`) will later read; it is the anti-theater proof, not the SUT.

The end-to-end loop is also closed: the produced hash is fed straight into the
real `des emit-feature-end --record FeatureEndReviewVerdict --verdict-hash
<hex>` slice-01 consumer through the same dispatcher, proving the signer's
output is accepted by the consumer (the two slices compose).

There are no test doubles for the driving surface: the git working tree, the
signing key (env `NWAVE_REVIEWER_SIGNING_KEY`), and the AT-completion ledger
are real -- a layer-3 `@real-io` surface (Mandate 9/11: example only, no PBT
machinery). The only thing the test sets/clears is the signing-key env var
(an external/non-deterministic port per the Architecture of Reference -- a
controlled fake-or-real secret, captured so a `Then` can observe the refusal).
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from des.domain.at_review_signing import (
    compute_verdict_hmac,
)
from tests.env_parity import seed_dev_checkout_marker

from .domain_types import FeatureEndRecord
from .domain_types_slice_02 import (
    DeepReviewRecord,
    DeepReviewVerdict,
    FeatureId,
    MalformedVerdictKind,
    ReviewerAgentId,
    SigningKeyState,
    SignOutcome,
    VerdictHash,
)


# The absolute repo-`src/` path, derived from THIS file's location rather than a
# cwd-relative `Path("src")` -- the `des` CLI subprocess is launched with
# `cwd=project_root` (the per-test tmp workspace), so a cwd-relative PYTHONPATH
# would resolve under the tmp tree and fail to import `des`. THIS file lives at
# tests/des/acceptance/oss_feature_end_emit_cli/steps/composition_slice_02.py ->
# 5 parents up is the repo root.
_REPO_SRC = Path(__file__).resolve().parents[5] / "src"

_FEATURE_ID = FeatureId("oss-feature-end-demo")

# A deterministic reviewer signing key for the test environment. The signer
# resolves it from `NWAVE_REVIEWER_SIGNING_KEY` (the `at_review_signing` env
# precedence); the test recomputes the HMAC with the SAME bytes to assert the
# produced hash is genuine. This is the controlled external-secret port -- not a
# minted hash, a real key the real HMAC is computed under.
_SIGNING_KEY = "test-reviewer-signing-key-slice-02"

# The canonical real deep-review verdict the happy-path scenarios sign: a real
# reviewer agent, an APPROVED decision, real findings. The SIGNED region reuses
# the at_review_signing SSOT's seven SIGNED_FIELDS -- the signer HMACs exactly
# these, and the test recomputes the SAME canonical JSON to verify genuineness.
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
    """The observable result of feeding a signed hash to the slice-01 consumer."""

    outcome: SignOutcome
    exit_code: int


class FeatureEndSignComposition:
    """Production-wired composition root for the `des feature-end sign` slice.

    The driving port is the real `des feature-end sign` subcommand invoked over
    the `des` dispatcher as a subprocess; the observable surface is the command
    exit code and the signed `verdict_hash` it prints. The hash is verified
    genuine by an INDEPENDENT recompute via the at_review_signing SSOT, and
    end-to-end-accepted by feeding it to the real slice-01 `emit-feature-end`
    consumer.
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

    def sign(
        self,
        verdict: DeepReviewRecord,
        *,
        key_state: SigningKeyState = SigningKeyState.PRESENT,
    ) -> SignResult:
        """Invoke the REAL `des feature-end sign` subcommand over the dispatcher.

        Supplies the real deep-review verdict (agent + verdict + findings); the
        signer HMACs it via the at_review_signing SSOT and prints the produced
        `verdict_hash`. `key_state` controls whether the signing-key env var is
        present (the missing-key loud-refusal path).
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
        return self._run_sign(argv, key_state=key_state)

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
        return self._run_sign(argv, key_state=SigningKeyState.PRESENT)

    def emit_with_signed_hash(self, signed_hash: VerdictHash) -> EmitResult:
        """Feed a signed hash to the REAL slice-01 `des emit-feature-end` consumer.

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
        completed = self._dispatch(argv, key_state=SigningKeyState.PRESENT)
        outcome = (
            SignOutcome.SUCCEEDED if completed.returncode == 0 else SignOutcome.REFUSED
        )
        return EmitResult(outcome=outcome, exit_code=completed.returncode)

    def sign_then_emit_round_trips(self) -> bool:
        """Whether signing a real verdict then emitting its hash both succeed.

        The back-compat round-trip (DDD-7): the consolidated `des feature-end
        sign` produces a genuine hash AND the consolidated/preserved `des
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
        completed = self._dispatch(
            ["feature-end", "--help"], key_state=SigningKeyState.PRESENT
        )
        return completed.returncode == 0 and "sign" in completed.stdout

    # --- observable read-back (substrate verification, NOT the SUT) ----------

    def expected_signature_for(self, verdict: DeepReviewRecord) -> str:
        """The HMAC the signer MUST have produced over this real verdict.

        Recomputed INDEPENDENTLY via the at_review_signing SSOT -- the same
        `compute_verdict_hmac` over `canonical_at_review_json` the production
        signer reuses. Asserting the produced hash equals THIS value proves the
        signer signed the real input (genuine HMAC), never minted a constant.
        The signed region is the seven SIGNED_FIELDS the SSOT defines.
        """
        record = _signed_region(verdict)
        return compute_verdict_hmac(record, _SIGNING_KEY.encode("utf-8"))

    @staticmethod
    def is_genuine_hmac_shape(produced_hash: str | None) -> bool:
        """Whether a produced hash has the genuine HMAC-SHA256 hex shape.

        64 lowercase hex chars. A guard against a minted placeholder slipping
        through with the wrong shape (the recompute-equality check is the
        primary genuineness proof; this is the shape sanity check).
        """
        if produced_hash is None:
            return False
        return len(produced_hash) == 64 and all(
            c in "0123456789abcdef" for c in produced_hash
        )

    # --- subprocess plumbing -------------------------------------------------

    def _run_sign(self, argv: list[str], *, key_state: SigningKeyState) -> SignResult:
        completed = self._dispatch(argv, key_state=key_state)
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

    def _dispatch(
        self, argv: list[str], *, key_state: SigningKeyState
    ) -> subprocess.CompletedProcess[str]:
        """Dispatch `des <argv>` through the real `des.cli.__main__` entry point."""
        return subprocess.run(
            [sys.executable, "-m", "des.cli.__main__", *argv],
            capture_output=True,
            text=True,
            cwd=str(self._project_root),
            env=_subprocess_env(key_state),
        )


def _signed_region(verdict: DeepReviewRecord) -> dict[str, object]:
    """The seven-SIGNED_FIELDS record the signer HMACs for a deep-review verdict.

    Reuses the at_review_signing SSOT field names. The mapping from a deep-review
    verdict onto the seven fields is the signing use-case's contract -- the test
    recomputes against the SAME mapping so the equality check is meaningful. (The
    crafter's production use-case MUST build the identical signed region; a
    divergence reds AT-1, which is the anti-theater guard working.)
    """
    return {
        "schema_version": "1.0.0",
        "slice_id": "feature-end",
        "verdict": verdict.verdict.value,
        "reviewer_agent_id": str(verdict.reviewer_agent_id),
        "at_ids": [],
        "at_content_hash": str(verdict.feature_id),
        "timestamp": "feature-end-review",
    }


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
    import json

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
    import json

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


def _subprocess_env(key_state: SigningKeyState) -> dict[str, str]:
    env = dict(os.environ)
    # ABSOLUTE repo-`src/` path so the subprocess can import `des` from a tmp cwd.
    env["PYTHONPATH"] = str(_REPO_SRC)
    if key_state is SigningKeyState.PRESENT:
        env["NWAVE_REVIEWER_SIGNING_KEY"] = _SIGNING_KEY
    else:
        env.pop("NWAVE_REVIEWER_SIGNING_KEY", None)
    return env


__all__ = [
    "EmitResult",
    "FeatureEndSignComposition",
    "SignResult",
]
