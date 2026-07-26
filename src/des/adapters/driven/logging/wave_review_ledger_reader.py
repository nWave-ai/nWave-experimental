"""Ledger adapter for the per-wave review-verdict reader (DISCUSS/DESIGN/DEVOPS).

Implements the read-only review-verdict reader shape over the per-feature
AT-completion ledger family at
``{project_root}/.nwave/telemetry/atdd-pure/{feature_id}.jsonl`` (path resolved
through ``AtCompletionLedger`` -- one path SSOT). The read MECHANICS mirror
``carpaccio_slice_gate._latest_verdict_record``: a TOLERANT line scan (skip
blank / unparseable / non-dict lines) selecting the latest record of the wave's
event family for the feature, ``None`` when absent.

ONE reader for all three waves: the wave enters only as the ``WaveReviewSpec``
the instance carries -- the scan, the probe and the verdict are identical, and
were identical when they were three files.

Tolerant-by-design (DISTILL pin): a plain JSONL record line -- carrying no M7
``seq`` / ``record_hash`` -- is a conformant input for this READ-ONLY gate feed.
Pre-existing ``hmac_sha256`` fields on old records are tolerated-and-ignored
(D-tolerate-old, upgrade-compat). The probe is keyless.

degrade-LOUD (§17): an absent ledger / no matching record yields ``None`` so the
pure core decides INDETERMINATE -- NEVER a fabricated record.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from typing import TYPE_CHECKING

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.domain.review_verdict_gate import ReviewGateToken, ReviewVerdictGate
from des.ports.driven_ports.discuss_review_reader import DiscussReviewReader


if TYPE_CHECKING:
    from pathlib import Path

    from des.domain.wave_review_spec import WaveReviewSpec


def _ledger_path(project_root: Path, feature_id: str) -> Path:
    """Resolve the per-feature ledger path through the ledger path SSOT."""
    return AtCompletionLedger(feature_id, project_root).ledger_path()


class WaveReviewLedgerReader(DiscussReviewReader):
    """Reads the latest review verdict of ONE wave off the JSONL ledger.

    Satisfies the wave-neutral review-verdict reader shape (``latest`` +
    ``probe``) the ``DiscussReviewReader`` port declares -- the port signature
    was already wave-neutral, only the implementations were wave-named.
    """

    def __init__(self, spec: WaveReviewSpec) -> None:
        self._spec = spec

    def latest(self, project_root: Path, feature_id: str) -> dict[str, object] | None:
        """Tolerant scan: latest verdict record for the feature+wave, or None."""
        ledger = _ledger_path(project_root, feature_id)
        if not ledger.is_file():
            return None
        latest: dict[str, object] | None = None
        for line in ledger.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            if record.get("event") != self._spec.event:
                continue
            if record.get("feature_id") != feature_id:
                continue
            latest = record
        return latest

    def probe(self, project_root: Path) -> None:
        """Earned-trust probe (principle 13): keyless record-presence round-trip.

        Writes a keyless verdict record to a probe ledger, reads it back through
        :meth:`latest` and asserts the pure gate finds it PASS (record-present +
        artefact-current); then writes an absent-record ledger and asserts the
        gate returns INDETERMINATE("absent") -- NEVER PASS. A failed probe
        refuses startup.

        Post-demotion (oss-review-verdict-demotion S3): no signing key is used.
        The tamper-rejection probe (hmac-mismatch) is retired because there is
        no signature to tamper. The absent-record leg proves no-silent-pass.
        """
        probe_root = (
            project_root / ".nwave" / self._spec.probe_gate_dir / "_probe_review"
        )
        feature_id = "_probe"
        delta_hash = hashlib.sha256(b"# probe feature-delta\n").hexdigest()
        record: dict[str, object] = {
            "event": self._spec.event,
            "schema_version": "1.0.0",
            "feature_id": feature_id,
            "verdict": "approved",
            "reviewer_agent_id": "_probe-reviewer",
            "feature_delta_hash": delta_hash,
            "timestamp": "2026-01-01T00:00:00+00:00",
        }
        try:
            ledger = _ledger_path(probe_root, feature_id)
            ledger.parent.mkdir(parents=True, exist_ok=True)
            ledger.write_text(json.dumps(record) + "\n", encoding="utf-8")
            self._assert_roundtrip_passes(probe_root, feature_id, delta_hash)
            # Absent-record leg: overwrite with a non-matching record so latest()
            # returns None -> INDETERMINATE("absent"), proving no-silent-pass.
            ledger.write_text(
                json.dumps({"event": "PhaseBoundary", "phase": "A"}) + "\n",
                encoding="utf-8",
            )
            self._assert_absent_blocked(probe_root, feature_id, delta_hash)
        finally:
            shutil.rmtree(probe_root, ignore_errors=True)

    def _assert_roundtrip_passes(
        self, probe_root: Path, feature_id: str, delta_hash: str
    ) -> None:
        roundtrip = self.latest(probe_root, feature_id)
        result = ReviewVerdictGate.evaluate(roundtrip, delta_hash)
        if result.token is not ReviewGateToken.PASS:
            raise RuntimeError(
                f"health.startup.refused: {self._spec.wave}-review probe "
                f"round-trip did not PASS (token={result.token.value!r}, "
                f"detail={result.detail!r})"
            )

    def _assert_absent_blocked(
        self, probe_root: Path, feature_id: str, delta_hash: str
    ) -> None:
        absent = self.latest(probe_root, feature_id)
        result = ReviewVerdictGate.evaluate(absent, delta_hash)
        if (
            result.token is not ReviewGateToken.INDETERMINATE
            or result.detail != "absent"
        ):
            raise RuntimeError(
                f"health.startup.refused: {self._spec.wave}-review probe did not "
                "block on an absent record -- expected INDETERMINATE('absent'), "
                f"got (token={result.token.value!r}, detail={result.detail!r})"
            )
