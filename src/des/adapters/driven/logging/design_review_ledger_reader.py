"""Ledger adapter for the DESIGN review verdict reader (f-design-devops-review-gate).

Implements the read-only review-verdict reader shape over the per-feature
AT-completion ledger family at
``{project_root}/.nwave/telemetry/atdd-pure/{feature_id}.jsonl`` (path resolved
through ``AtCompletionLedger`` -- one path SSOT). The thin DESIGN-scoped sibling
of ``DiscussReviewLedgerReader`` (DDD-8): same tolerant line scan + keyless
probe, keyed to the ``DesignReviewVerdict`` event.

Tolerant-by-design: a plain JSONL record line -- carrying no M7 ``seq`` /
``record_hash`` -- is a conformant input for this READ-ONLY gate feed.
Pre-existing ``hmac_sha256`` fields on old records are tolerated-and-ignored
(D-tolerate-old, upgrade-compat).

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


# The DESIGN review verdict event name -- the record-family discriminant the
# reader selects on (sibling of DISCUSS_REVIEW_EVENT for the DESIGN wave).
DESIGN_REVIEW_EVENT = "DesignReviewVerdict"


def _ledger_path(project_root: Path, feature_id: str) -> Path:
    """Resolve the per-feature ledger path through the ledger path SSOT."""
    return AtCompletionLedger(feature_id, project_root).ledger_path()


class DesignReviewLedgerReader(DiscussReviewReader):
    """Reads the latest DESIGN review verdict off the JSONL ledger.

    Satisfies the wave-neutral review-verdict reader shape
    (``latest`` + ``probe``) the existing ``DiscussReviewReader`` port declares;
    no port churn (the signature is already wave-neutral).
    """

    def latest(self, project_root: Path, feature_id: str) -> dict[str, object] | None:
        """Tolerant scan: latest ``DesignReviewVerdict`` for the feature, or None."""
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
            if record.get("event") != DESIGN_REVIEW_EVENT:
                continue
            if record.get("feature_id") != feature_id:
                continue
            latest = record
        return latest

    def probe(self, project_root: Path) -> None:
        """Earned-trust probe (principle 13): keyless record-presence round-trip.

        Writes a keyless ``DesignReviewVerdict`` to a probe ledger, reads it back
        through :meth:`latest` and asserts the pure gate finds it PASS
        (record-present + artefact-current); then writes an absent-record ledger
        and asserts the gate returns INDETERMINATE("absent") -- NEVER PASS. A
        failed probe refuses startup.
        """
        probe_root = project_root / ".nwave" / "design-gate" / "_probe_review"
        feature_id = "_probe"
        delta_hash = hashlib.sha256(b"# probe feature-delta\n").hexdigest()
        record: dict[str, object] = {
            "event": DESIGN_REVIEW_EVENT,
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
                "health.startup.refused: design-review probe round-trip did "
                f"not PASS (token={result.token.value!r}, "
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
                "health.startup.refused: design-review probe did not block "
                "on an absent record -- expected INDETERMINATE('absent'), got "
                f"(token={result.token.value!r}, detail={result.detail!r})"
            )
