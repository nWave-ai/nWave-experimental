"""Regression: verify-integrity exempts attested PROSE slices from the
truncated-feature check.

The adversarial swarm (2026-06-29) exposed a verify-integrity FALSE-POSITIVE: a
prose slice (Decision-4 NON-code, "NO ATs authored for prose") was flagged
`FeatureSlicePlanPending`/TRUNCATED because it has no `.feature` file, theater-
rejecting an honestly-delivered prose slice. Delivery of a prose slice is
attested by a `SliceProseDelivered` ledger record (`attested: true`), the
un-gameable spine-emitted analogue of `.feature`-presence for code slices.
"""

import json
from pathlib import Path

from des.cli.verify_deliver_integrity import _prose_delivered_slices


def _write_ledger(tmp_path: Path, feature_id: str, records: list[dict]) -> None:
    ledger = tmp_path / ".nwave" / "telemetry" / "atdd-pure" / f"{feature_id}.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
    )


def test_attested_prose_slice_is_recognised_as_delivered(tmp_path: Path) -> None:
    _write_ledger(
        tmp_path,
        "feat",
        [
            {"event": "SliceProseDelivered", "slice_id": "slice-02", "attested": True},
            {"event": "SliceCommitVerified", "slice_id": "slice-01"},
        ],
    )
    assert _prose_delivered_slices(tmp_path, "feat") == frozenset({"slice-02"})


def test_unattested_prose_record_is_not_a_delivery(tmp_path: Path) -> None:
    # attested:false must NOT count -- only a real attested record exempts.
    _write_ledger(
        tmp_path,
        "feat",
        [{"event": "SliceProseDelivered", "slice_id": "slice-02", "attested": False}],
    )
    assert _prose_delivered_slices(tmp_path, "feat") == frozenset()


def test_absent_ledger_yields_empty(tmp_path: Path) -> None:
    assert _prose_delivered_slices(tmp_path, "no-such-feature") == frozenset()
