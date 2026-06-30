"""Composition root for the oss-review-verdict-demotion S4 acceptance slice.

Mandate 13 (Driving-Port-Only Boundary) + Mandate-12 (Pillar 3). Wires the
PRODUCTION feature-end signer through ONE driving surface:

  * the REAL ``des feature-end sign`` subcommand, invoked end-to-end over the
    ``des.cli.__main__`` dispatcher as a subprocess (Layer 3 subprocess, the SAME
    driving surface as the oss-feature-end-emit-cli slice-02 producer). The
    composition NEVER imports ``sign_feature_end_review`` / its ``main`` and calls
    it at the step boundary; the only entry is the real subprocess through the
    dispatcher, exactly as an operator (or the eventual SubagentStop hook shim)
    invokes it.

OBSERVABLE READ-BACK (substrate verification, NOT a second SUT)
--------------------------------------------------------------
The produced ``verdict_hash`` is read off the command's stdout, then RECOMPUTED
independently and KEYLESSLY via the ``des.domain.at_review_signing`` SSOT's
keyless content-seal helper -- ``sha256(canonical_signed_json(record,
SIGNED_FIELDS))`` -- to assert the produced hash is a GENUINE deterministic
content hash over the real deep-review verdict input, not a minted constant and
not the pre-demotion keyed HMAC. This is allowed (Mandate 13): the recompute
verifies the observable SUBSTRATE the ``des emit-feature-end --verdict-hash``
consumer later reads; it is the anti-theater proof, not the SUT. ``canonical_
signed_json`` is the KEYLESS canonicalizer the demotion RETAINS (only the keyed
``compute_verdict_hmac`` / ``load_signing_key`` callers are removed) -- the same
helper the post-demotion production signer reuses.

The end-to-end loop is also closed: the produced content hash is fed straight
into the real ``des emit-feature-end --record FeatureEndReviewVerdict
--verdict-hash <hex>`` consumer through the same dispatcher, proving the keyless
content hash is accepted unchanged (the emitter never HMAC-verified -- it only
requires the hash to be PRESENT, and the ledger's ``_is_hex64`` validation
accepts any 64-char hex, which a content SHA-256 satisfies).

KEYLESS BY CONSTRUCTION
-----------------------
NO reviewer signing key is provisioned for any S4 state. The signing-key env var
is SCRUBBED around every subprocess run and no key file is written, so the
command runs entirely keyless -- the S4 contract is "the content binds the hash,
the named-reviewer-and-known-verdict checks bind the honesty, and the key is
gone". The only driven adapter is the real filesystem (tmp_path) -> @real-io;
example-only, no PBT machinery (Mandate 9 v2 / 11).

S4 RED note (fail-for-right-reason): on the pre-demotion tree (tip 0d8a76a91)
``sign_feature_end_review`` loads a signing key and HMACs the verdict, and
REFUSES (lines 108-114) when the key is unresolvable. The S4 fixtures provision
NO key, so the happy-path scenarios hit the key-unresolvable refusal (no hash
where a content hash is expected) and the keyless-content-hash genuineness check
cannot match (an HMAC under a present key would not equal the keyless content
hash either). Each failure is a semantic ``AssertionError`` at the Then step
after the real command ran -- never an ImportError / FIXTURE_BROKEN /
SETUP_FAILURE. No ``@skip``. The crafter greens them by removing the
``load_signing_key`` call + the key-unresolvable refusal and producing
``sha256(canonical_signed_json(signed_region, SIGNED_FIELDS))``, keeping the
non-empty-reviewer + known-verdict refusals verbatim.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from des.domain.at_review_signing import (
    SIGNED_FIELDS,
    canonical_signed_json,
)
from tests.common.in_process_cli import run_cli_in_process
from tests.env_parity import seed_dev_checkout_marker

from .domain_types_slice_04 import (
    ContentHash,
    DeepReviewRecord,
    DeepReviewVerdict,
    FeatureId,
    ReviewerAgentId,
    SealOutcome,
)


_FEATURE_ID = FeatureId("oss-feature-end-demo")
_REVIEWER_AGENT = ReviewerAgentId("nw-software-crafter-reviewer")

# Signing-key env / file -- referenced ONLY to guarantee they stay ABSENT. S4
# never provisions a key; the env var is scrubbed for every subprocess run.
_SIGNING_KEY_ENV = "NWAVE_REVIEWER_SIGNING_KEY"
_SIGNING_KEY_FILE = ".nwave/secrets/reviewer-signing.key"

# The signed-region constants binding a deep-review verdict onto the seven
# at_review_signing SIGNED_FIELDS -- the SAME mapping the production signer uses.
# The keyless content-hash oracle reproduces these byte-for-byte; a divergence
# breaks the equality check, which is the anti-theater guard working.
_SCHEMA_VERSION = "1.0.0"
_SLICE_ID = "feature-end"
_TIMESTAMP = "feature-end-review"


@dataclass
class SealResult:
    """The observable result of one `des feature-end sign` invocation.

    Universe entries are port-exposed only (Mandate 8): the command outcome
    (succeeded / refused, derived from the exit code) and the produced content
    hash read off stdout -- never an internal use-case struct. ``stdout`` /
    ``stderr`` are kept for diagnostic surfacing in the Then assertions.
    """

    outcome: SealOutcome
    exit_code: int
    produced_hash: str | None
    stdout: str
    stderr: str


@dataclass
class EmitResult:
    """The observable result of feeding a content hash to the slice-01 emitter."""

    outcome: SealOutcome
    exit_code: int


class FeatureEndSealComposition:
    """Production-wired composition root for the keyless feature-end-seal slice.

    The driving port is the real `des feature-end sign` subcommand invoked over
    the `des` dispatcher as a subprocess; the observable surface is the command
    exit code and the `verdict_hash` it prints. The hash is verified genuine by
    an INDEPENDENT KEYLESS recompute via the at_review_signing content-seal
    helper, and end-to-end-accepted by feeding it to the real slice-01
    `emit-feature-end` consumer. NO signing key is ever provisioned.
    """

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        self._feature_id = _FEATURE_ID
        # Env-parity (F21/RCA-#68): the `des` subprocess runs with
        # cwd=project_root (the per-test tmp workspace). Mark it a developer
        # checkout so the runtime-freshness gate AUTOSKIPS instead of the
        # customer-install REFUSAL (exit 78). The honest fix, NOT a
        # NWAVE_FRESHNESS=skip mask. See tests/env_parity.py.
        seed_dev_checkout_marker(self._project_root)

    # --- paths ---------------------------------------------------------------

    @property
    def _signing_key_path(self) -> Path:
        return self._project_root / _SIGNING_KEY_FILE

    # --- the real deep-review verdict (the signer's required input) ----------

    def deep_review_verdict_with(self, verdict: DeepReviewVerdict) -> DeepReviewRecord:
        """A real deep-review verdict carrying a chosen decision (APPROVED/REJECTED)."""
        return DeepReviewRecord(
            feature_id=self._feature_id,
            reviewer_agent_id=_REVIEWER_AGENT,
            verdict=verdict,
            findings=("no blocking findings",),
        )

    # --- driving-port invocation (the SUT) -----------------------------------

    def seal(self, verdict: DeepReviewRecord) -> SealResult:
        """Invoke the REAL `des feature-end sign` over the dispatcher, KEYLESS.

        Supplies the real deep-review verdict (agent + verdict + findings); the
        post-demotion signer content-hashes it via the at_review_signing keyless
        helper and prints the produced `verdict_hash`. No signing key is
        provisioned and the env var is scrubbed -- key absence must be a
        non-event.
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
        return self._run_seal(argv)

    def emit_with_content_hash(self, content_hash: ContentHash) -> EmitResult:
        """Feed a content hash to the REAL slice-01 `des emit-feature-end` consumer.

        Closes the end-to-end loop: the keyless content hash is accepted by the
        slice-01 consumer (`--record FeatureEndReviewVerdict --verdict-hash`),
        proving the demotion's output is consumed unchanged through the single
        `des` entry point.
        """
        argv = [
            "emit-feature-end",
            "--repo",
            str(self._project_root),
            "--feature-id",
            str(self._feature_id),
            "--record",
            "FeatureEndReviewVerdict",
            "--verdict-hash",
            str(content_hash),
        ]
        completed = self._dispatch(argv)
        outcome = (
            SealOutcome.SUCCEEDED if completed.returncode == 0 else SealOutcome.REFUSED
        )
        return EmitResult(outcome=outcome, exit_code=completed.returncode)

    def seal_then_emit_round_trips(self, verdict: DeepReviewRecord) -> bool:
        """Whether sealing a real verdict then emitting its content hash both succeed.

        Encapsulated here so the Then step body stays a single delegate + assert
        (Mandate-12 criterion 3).
        """
        sealed = self.seal(verdict)
        if sealed.outcome is not SealOutcome.SUCCEEDED or sealed.produced_hash is None:
            return False
        emit = self.emit_with_content_hash(ContentHash(sealed.produced_hash))
        return emit.outcome is SealOutcome.SUCCEEDED

    # --- observable read-back (substrate verification, NOT the SUT) ----------

    def expected_content_hash_for(self, verdict: DeepReviewRecord) -> str:
        """The KEYLESS content hash the signer MUST have produced over this verdict.

        Recomputed INDEPENDENTLY via the at_review_signing SSOT's keyless
        content-seal helper -- ``sha256(canonical_signed_json(record,
        SIGNED_FIELDS))`` over the SAME seven-field signed region. Asserting the
        produced hash equals THIS value proves the signer hashed the real input
        deterministically (no key), never minted a constant and never emitted the
        pre-demotion keyed HMAC. ``canonical_signed_json`` is the keyless helper
        the demotion retains -- the SAME canonicalization the production signer
        reuses.
        """
        record = _signed_region(verdict)
        return hashlib.sha256(canonical_signed_json(record, SIGNED_FIELDS)).hexdigest()

    @staticmethod
    def is_content_hash_shape(produced_hash: str | None) -> bool:
        """Whether a produced hash has the deterministic SHA-256 hex shape.

        64 lowercase hex chars -- byte-identical SHAPE to the pre-demotion HMAC,
        so the emitter + the ledger's ``_is_hex64`` validation accept it
        unchanged. The recompute-equality check is the primary genuineness proof;
        this is the shape sanity check.
        """
        if produced_hash is None:
            return False
        return len(produced_hash) == 64 and all(
            c in "0123456789abcdef" for c in produced_hash
        )

    def no_signing_key_was_read(self) -> bool:
        """True iff no signing key file exists and the env var is unset.

        The observable backing the demotion's key-absence-is-a-non-event
        contract: the command produced its result with NO key present, so no key
        could have been read.
        """
        return (
            not self._signing_key_path.exists()
            and os.environ.get(_SIGNING_KEY_ENV) is None
        )

    # --- subprocess plumbing -------------------------------------------------

    def _run_seal(self, argv: list[str]) -> SealResult:
        completed = self._dispatch(argv)
        outcome = (
            SealOutcome.SUCCEEDED if completed.returncode == 0 else SealOutcome.REFUSED
        )
        produced = (
            _extract_produced_hash(completed.stdout)
            if completed.returncode == 0
            else None
        )
        return SealResult(
            outcome=outcome,
            exit_code=completed.returncode,
            produced_hash=produced,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def _dispatch(self, argv: list[str]) -> subprocess.CompletedProcess[str]:
        """Dispatch `des <argv>` through the real `des.cli.__main__` entry point.

        Driven IN-PROCESS via the shared ``run_cli_in_process`` driver (default
        EDGE = ``des.cli.__main__.main``), chdir'd to the project root and
        restored. Runs entirely KEYLESS: the signing-key env var is scrubbed
        IN-PROCESS around the call (restored in ``finally``) and no key file is
        written, exercising the demotion's key-absence contract. The result is
        wrapped in a ``CompletedProcess`` so the existing call sites
        (``.returncode`` / ``.stdout`` / ``.stderr``) are unchanged.
        """
        prior_env = dict(os.environ)
        os.environ.pop(_SIGNING_KEY_ENV, None)
        try:
            exit_code, stdout, stderr = run_cli_in_process(
                argv, cwd=str(self._project_root)
            )
        finally:
            os.environ.clear()
            os.environ.update(prior_env)
        return subprocess.CompletedProcess(
            args=argv, returncode=exit_code, stdout=stdout, stderr=stderr
        )


def _signed_region(verdict: DeepReviewRecord) -> dict[str, object]:
    """The seven-SIGNED_FIELDS record the signer content-hashes for a verdict.

    Reuses the at_review_signing SSOT field names. The mapping from a deep-review
    verdict onto the seven fields is the signing use-case's contract -- the test
    recomputes against the SAME mapping so the equality check is meaningful. The
    crafter's post-demotion use-case MUST build the identical signed region; a
    divergence reds the genuineness assertion, which is the anti-theater guard
    working.
    """
    return {
        "schema_version": _SCHEMA_VERSION,
        "slice_id": _SLICE_ID,
        "verdict": verdict.verdict.value,
        "reviewer_agent_id": str(verdict.reviewer_agent_id),
        "at_ids": [],
        "at_content_hash": str(verdict.feature_id),
        "timestamp": _TIMESTAMP,
    }


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
    "FeatureEndSealComposition",
    "SealResult",
]
