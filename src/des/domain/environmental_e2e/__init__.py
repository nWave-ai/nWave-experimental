"""Environmental-e2e gate domain — token formatter + verdict-input-digest.

Feature `fix-oss-environmental-e2e-gate`. The domain types and pure functions
the L1.4 `verify_environmental_e2e` CLI composes — stdlib-only, no I/O.
"""

from __future__ import annotations

from des.domain.environmental_e2e.deferral_marker import (
    deferral_marker_path,
    write_deferral_marker,
)
from des.domain.environmental_e2e.done_gate import (
    DoneGateVerdict,
    evaluate_done_gate,
)
from des.domain.environmental_e2e.feature_delta_scanner import (
    has_environmental_e2e_block,
)
from des.domain.environmental_e2e.results_record import (
    ResultsRecord,
    serialize_results_record,
)
from des.domain.environmental_e2e.stdout_token import (
    GateExit,
    GateVerdict,
    StdoutToken,
    format_stdout_token,
)
from des.domain.environmental_e2e.verdict_input_digest import (
    VerdictInputBreakdown,
    compute_verdict_input_digest,
)


__all__ = [
    "DoneGateVerdict",
    "GateExit",
    "GateVerdict",
    "ResultsRecord",
    "StdoutToken",
    "VerdictInputBreakdown",
    "compute_verdict_input_digest",
    "deferral_marker_path",
    "evaluate_done_gate",
    "format_stdout_token",
    "has_environmental_e2e_block",
    "serialize_results_record",
    "write_deferral_marker",
]
