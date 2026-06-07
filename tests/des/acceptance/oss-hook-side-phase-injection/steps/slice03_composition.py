"""Composition root for slice-03 -- mechanical HMAC trailer projection.

slice-03 of oss-hook-side-phase-injection (the DISTILL-wave hook keystone, D1).

Mandate-13 (driving-port-only) + Pillar 3: every SUT is exercised through a
PRODUCTION CLI invoked end-to-end as a subprocess (Layer 3, the direct mirror of
the shipped slice-01/02 ATs' hook subprocess pattern):

  * AT-1 drives the real ``scripts/cli/derive_review_trailer.py`` CLI as a
    subprocess. The observable surface is the CLI's stdout (the
    ``Reviewed-by:`` + ``Verdict-Payload:`` line pair) and its exit code. The
    derive CLI reads a signed ``ATReviewVerdict`` ledger record and projects the
    verifier's 4-field canonical verdict.
  * AT-2 chains AT-1's derived pair into the real ``des.cli.verify_commit_trailers``
    CLI as a subprocess (the derive->verify round-trip). The observable surface is
    the verifier's exit code (0 = the pair verifies).
  * AT-3 drives the same round-trip with a fault injected (key mismatch /
    extra-field / unpaired trailer). The observable surface is the verifier's
    exit code (4 = hash mismatch, 6 = malformed/unpaired) -- never a silent pass.

The composition NEVER imports the derive CLI's projection logic and calls it at
the step boundary; the only entry is the real CLI subprocess. The production
``AtCompletionLedger`` writer is used ONLY to SEED the signed verdict record the
CLI reads (the precondition SUBSTRATE, not the SUT) -- the adjudicated-legitimate
carve-out, exactly as in slice-01/02. The signed record is produced through the
shipped ``at_review_verdict.record_at_review_verdict`` PRODUCER so the unsigned
``findings_summary`` lands on the record's unsigned region exactly as in
production.

The only test doubles are the absent ones: there are none. The git repo, the
ledger JSONL, the signing key, the derive CLI subprocess and the verify CLI
subprocess are all real I/O -- a layer-3 ``@real-io`` surface (Mandate 9/11:
example only, no PBT machinery).

HARD INVARIANT (NOT a hook): the derive CLI only READS + PROJECTS. No assertion
claims it mutated the ledger or dispatched an agent -- it cannot. The
single-serializer invariant (derive + verify share
``verify_commit_trailers.canonical_verdict_json``) is exercised by AT-2's
round-trip: a GREEN round-trip is structurally impossible under any field-set
drift.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

from .slice03_domain_types import (
    FeatureId,
    RoundTripVerdict,
    TrailerFault,
    TrailerProjection,
)


_FEATURE_ID = FeatureId("atdd-pure-demo")
_SLICE_ID = "slice-01"
_REVIEWER_AGENT_ID = "nw-acceptance-designer-reviewer"
_DERIVE_CLI_MODULE = "scripts.cli.derive_review_trailer"
_VERIFY_CLI_MODULE = "des.cli.verify_commit_trailers"

# The signing key the derive side uses (the file fallback both the producer and
# the verifier honour). AT-3 KEY_MISMATCH hands the verifier a DIFFERENT key.
_SIGNING_KEY = "slice-03-acceptance-signing-key"
_WRONG_KEY = "slice-03-WRONG-signing-key"

_REVIEWED_BY_RE = re.compile(r"^Reviewed-by:\s*([^:\s]+):([0-9a-fA-F]{64})\s*$")
_VERDICT_PAYLOAD_RE = re.compile(r"^Verdict-Payload:\s*(\{.*\})\s*$")


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return completed.stdout


def _subprocess_env(repo: Path, signing_key: str) -> dict[str, str]:
    import os

    env = dict(os.environ)
    # The derive CLI imports des.cli.verify_commit_trailers + scripts.cli; both
    # roots must resolve. The repo root carries scripts/; src/ carries des/.
    env["PYTHONPATH"] = f"{Path('src').resolve()}:{Path.cwd()}"
    env["NWAVE_REVIEWER_SIGNING_KEY"] = signing_key
    env["NWAVE_REPO_ROOT"] = str(repo)
    return env


@dataclass
class DeriveOutcome:
    """The observable result of a ``derive_review_trailer`` CLI invocation.

    Universe entries are port-exposed only (Mandate 8): the projection shape
    (pair emitted / absent), the parsed agent + hmac, the parsed payload JSON,
    and the CLI exit code -- never an internal CLI struct field.
    """

    projection: TrailerProjection
    reviewed_by_line: str | None
    verdict_payload_line: str | None
    agent_id: str | None
    hmac_hex: str | None
    payload_obj: dict | None
    exit_code: int


@dataclass
class RoundTripOutcome:
    """The observable result of a derive->verify round-trip.

    Universe entries are port-exposed only (Mandate 8): the round-trip verdict
    and the verifier's exit code -- never an internal struct field.
    """

    verdict: RoundTripVerdict
    verify_exit_code: int


class TrailerProjectionComposition:
    """Production-wired composition root for the derive CLI + round-trip.

    The driving ports are the real ``derive_review_trailer`` CLI (projection)
    and the real ``verify_commit_trailers`` CLI (round-trip verification), each
    invoked as a subprocess. The observable surface is each CLI's stdout and
    exit code.
    """

    def __init__(self, repo: Path) -> None:
        self._repo = repo
        self._feature_id = _FEATURE_ID
        self._slice_id = _SLICE_ID
        self._derive: DeriveOutcome | None = None

    # --- precondition: seed the signed verdict record -----------------------

    def seed_signed_verdict(self) -> None:
        """Append a signed ``ATReviewVerdict`` through the SHIPPED producer.

        Uses ``at_review_verdict.record_at_review_verdict`` (the slice-07
        producer) so the record's signed region (``verdict``, ``timestamp``,
        ``reviewer_agent_id``) and unsigned region (``findings_summary``) land
        exactly as in production -- the substrate the derive CLI reads. This is
        the adjudicated precondition-seed carve-out (NOT the SUT).
        """
        import os

        from des.cli.at_review_verdict import record_at_review_verdict

        saved = os.environ.get("NWAVE_REVIEWER_SIGNING_KEY")
        os.environ["NWAVE_REVIEWER_SIGNING_KEY"] = _SIGNING_KEY
        try:
            record_at_review_verdict(
                repo_root=self._repo,
                feature_id=str(self._feature_id),
                slice_id=self._slice_id,
                verdict="APPROVED",
                reviewer_agent_id=_REVIEWER_AGENT_ID,
                at_ids=["AT-1", "AT-2", "AT-3"],
                at_content_hash="deadbeef",
                timestamp="2026-05-29T12:00:00Z",
                findings_summary=["no blockers", "one low note"],
            )
        finally:
            if saved is None:
                os.environ.pop("NWAVE_REVIEWER_SIGNING_KEY", None)
            else:
                os.environ["NWAVE_REVIEWER_SIGNING_KEY"] = saved

    def signed_verdict_is_present(self) -> bool:
        """Read back the seeded record through the production ledger reader."""
        ledger = AtCompletionLedger(str(self._feature_id), self._repo)
        records = ledger.read_records(event_type="ATReviewVerdict")
        return any(r.get("slice_id") == self._slice_id for r in records)

    # --- AT-1: derive the trailer pair --------------------------------------

    def run_derive_cli(self) -> DeriveOutcome:
        """Invoke the REAL ``derive_review_trailer`` CLI as a subprocess."""
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                _DERIVE_CLI_MODULE,
                "--feature-id",
                str(self._feature_id),
                "--slice-id",
                self._slice_id,
                "--repo-root",
                str(self._repo),
            ],
            capture_output=True,
            text=True,
            cwd=str(Path.cwd()),
            env=_subprocess_env(self._repo, _SIGNING_KEY),
        )
        self._derive = self._interpret_derive(completed)
        return self._derive

    def _interpret_derive(
        self, completed: subprocess.CompletedProcess
    ) -> DeriveOutcome:
        reviewed_by: str | None = None
        verdict_payload: str | None = None
        agent_id: str | None = None
        hmac_hex: str | None = None
        payload_obj: dict | None = None
        for line in completed.stdout.splitlines():
            stripped = line.strip()
            rb = _REVIEWED_BY_RE.match(stripped)
            if rb is not None:
                reviewed_by = stripped
                agent_id = rb.group(1)
                hmac_hex = rb.group(2)
                continue
            vp = _VERDICT_PAYLOAD_RE.match(stripped)
            if vp is not None:
                verdict_payload = stripped
                try:
                    payload_obj = json.loads(vp.group(1))
                except json.JSONDecodeError:
                    payload_obj = None
        projection = (
            TrailerProjection.PAIR_EMITTED
            if reviewed_by is not None and verdict_payload is not None
            else TrailerProjection.ABSENT
        )
        return DeriveOutcome(
            projection=projection,
            reviewed_by_line=reviewed_by,
            verdict_payload_line=verdict_payload,
            agent_id=agent_id,
            hmac_hex=hmac_hex,
            payload_obj=payload_obj,
            exit_code=completed.returncode,
        )

    # --- AT-2 / AT-3: derive->verify round-trip -----------------------------

    def run_round_trip(self, fault: TrailerFault | None = None) -> RoundTripOutcome:
        """Embed the derived pair in a commit and run the verifier subprocess.

        ``fault`` injects one of the AT-3 negative shapes; ``None`` is the AT-2
        clean round-trip. The verifier is the REAL ``verify_commit_trailers`` CLI
        run against a real git commit whose message carries the embedded pair.
        """
        if self._derive is None:
            self.run_derive_cli()
        assert self._derive is not None
        self._init_repo_if_needed()
        verify_key = _WRONG_KEY if fault is TrailerFault.KEY_MISMATCH else _SIGNING_KEY
        message = self._compose_commit_message(self._derive, fault)
        self._commit_with_message(message)
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                _VERIFY_CLI_MODULE,
                "--commit",
                "HEAD",
                "--strict",
            ],
            capture_output=True,
            text=True,
            cwd=str(self._repo),
            env=_subprocess_env(self._repo, verify_key),
        )
        return RoundTripOutcome(
            verdict=self._verdict_for_exit(completed.returncode),
            verify_exit_code=completed.returncode,
        )

    def _compose_commit_message(
        self, derive: DeriveOutcome, fault: TrailerFault | None
    ) -> str:
        body = "feat: deliver slice work\n\n"
        reviewed_by = derive.reviewed_by_line or ""
        verdict_payload = derive.verdict_payload_line or ""
        if fault is TrailerFault.UNPAIRED_TRAILER:
            # A Reviewed-by line with NO matching Verdict-Payload (count mismatch).
            return body + reviewed_by + "\n"
        if fault is TrailerFault.EXTRA_FIELD:
            # Mutate the embedded payload to carry an extra field the verifier's
            # 4-field serializer rejects on recompute (field-set divergence).
            mutated = dict(derive.payload_obj or {})
            mutated["injected_extra"] = "drift"
            verdict_payload = "Verdict-Payload: " + json.dumps(
                mutated, sort_keys=True, separators=(",", ":")
            )
        return body + reviewed_by + "\n" + verdict_payload + "\n"

    def _init_repo_if_needed(self) -> None:
        if (self._repo / ".git").is_dir():
            return
        _git(self._repo, "init")
        _git(self._repo, "config", "user.email", "t@t.com")
        _git(self._repo, "config", "user.name", "T")
        (self._repo / "README.md").write_text("seed\n", encoding="utf-8")
        _git(self._repo, "add", "README.md")
        _git(self._repo, "commit", "-m", "chore: seed")

    def _commit_with_message(self, message: str) -> None:
        marker = self._repo / "slice03_work.txt"
        marker.write_text("work\n", encoding="utf-8")
        _git(self._repo, "add", "slice03_work.txt")
        _git(self._repo, "commit", "-m", message)

    @staticmethod
    def _verdict_for_exit(exit_code: int) -> RoundTripVerdict:
        if exit_code == 0:
            return RoundTripVerdict.VERIFIES
        if exit_code == 6:
            return RoundTripVerdict.MALFORMED_PAIR
        return RoundTripVerdict.HASH_MISMATCH


__all__ = [
    "DeriveOutcome",
    "RoundTripOutcome",
    "TrailerProjectionComposition",
]
