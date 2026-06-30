"""DISCUSS PO-review verdict driven port (slice-07b, nwave-flow-v2-enforcement).

A read-only capability port (principle 12) the DISCUSS gate-OUT review branch
consumes. Returns the latest ``DiscussReviewVerdict`` ledger record for the
feature as a raw dict, or ``None`` when no such record exists, so the pure
``DiscussReviewGate.evaluate`` core decides INDETERMINATE (degrade-LOUD, §17
no-silent-pass) on absence.

Asymmetric authority (§22.0): the gate VETOES; it never writes a verdict, so
this port exposes ONLY a read. The PRODUCER half is the separate signed CLI
``des record-discuss-review`` (O-4).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


class DiscussReviewReader(ABC):
    """Driven, read-only port over the DISCUSS review verdict ledger."""

    @abstractmethod
    def latest(self, project_root: Path, feature_id: str) -> dict[str, object] | None:
        """Return the latest ``DiscussReviewVerdict`` record, or ``None``.

        Mirrors ``carpaccio_slice_gate._latest_verdict_record``: a tolerant
        line scan over the per-feature AT-completion ledger family
        (``.nwave/telemetry/atdd-pure/{feature_id}.jsonl``) selecting the
        latest ``DiscussReviewVerdict`` record for ``feature_id``. Absent
        ledger / no matching record -> ``None`` (NOT raise -- the pure core
        maps ``None`` to INDETERMINATE, degrade-LOUD). The record is returned
        RAW; verification (schema, artefact currency) is the pure gate's job,
        never the reader's.
        """
        ...
