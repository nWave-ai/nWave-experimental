"""L1.4 results-JSON `schema_version 2.0` record — pure serializer, no I/O.

The L1.4 `--mode run` writes this record; `--mode verify-merge-ready` reads it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from des.domain.environmental_e2e.stdout_token import GateVerdict
    from des.domain.environmental_e2e.verdict_input_digest import VerdictInputBreakdown


_SCHEMA_VERSION = "2.0"


@dataclass(frozen=True)
class ResultsRecord:
    """L1.4 results-JSON value object, schema_version 2.0."""

    feature_id: str
    verdict_input_digest: str
    verdict_input_breakdown: VerdictInputBreakdown
    verdict: GateVerdict
    collected: int
    reruns: int
    rerun_results: tuple[str, ...]
    xfail_marker_present: bool
    e2e_path: str
    built_at: str
    cli_version: str


def serialize_results_record(record: ResultsRecord) -> str:
    """Return the JSON-text rendering of `record` as the L1.4 schema 2.0 shape."""
    payload: dict[str, object] = {
        "schema_version": _SCHEMA_VERSION,
        "feature_id": record.feature_id,
        "verdict_input_digest": record.verdict_input_digest,
        "verdict_input_breakdown": {
            "wheel": record.verdict_input_breakdown.wheel,
            "e2e_files": record.verdict_input_breakdown.e2e_files,
            "ci_job_closure": record.verdict_input_breakdown.ci_job_closure,
        },
        "verdict": record.verdict.value,
        "collected": record.collected,
        "reruns": record.reruns,
        "rerun_results": list(record.rerun_results),
        "xfail_marker_present": record.xfail_marker_present,
        "e2e_path": record.e2e_path,
        "built_at": record.built_at,
        "cli_version": record.cli_version,
    }
    return json.dumps(payload, indent=2, sort_keys=True)


__all__ = ["ResultsRecord", "serialize_results_record"]
