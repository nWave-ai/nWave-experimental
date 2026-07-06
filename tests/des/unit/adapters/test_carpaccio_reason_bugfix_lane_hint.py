"""FR-7 regression: gate rejection reasons self-describe the bugfix-lane escape.

When the carpaccio or readiness gate refuses a dispatch for a MISSING feature-delta
ceremony (a single-slice bugfix has no feature-delta by design), the human-facing
reason must surface the bugfix-lane escape + its exact marker format -- so a bugfix
does not thrash through the gate cascade discovering the lane by reading source.
The hint MUST be scoped: it appears only on the feature-delta ceremony failures,
never on a genuine non-ceremony gate refusal (a false hint would mis-guide).
"""

from __future__ import annotations

import json

from des.adapters.drivers.hooks.carpaccio_intercept import (
    _carpaccio_reason,
    _readiness_reason,
)


_MARKER = "DES-LANE: bugfix"
_JUSTIFICATION = "DES-LANE-JUSTIFICATION"


def test_carpaccio_slice_plan_missing_reason_surfaces_the_bugfix_lane() -> None:
    reason = _carpaccio_reason(
        json.dumps({"event": "SlicePlanSectionMissing", "error": "no feature-delta"})
    )
    assert _MARKER in reason, reason
    assert _JUSTIFICATION in reason, reason


def test_carpaccio_non_ceremony_reason_carries_no_bugfix_hint() -> None:
    # A genuine carpaccio failure (slice too large) is NOT a missing-feature-delta
    # ceremony -- the bugfix lane would not help, so the hint must NOT appear.
    reason = _carpaccio_reason(json.dumps({"event": "CARPACCIO_SLICE_TOO_LARGE"}))
    assert _MARKER not in reason, reason


def test_readiness_feature_delta_failure_surfaces_the_bugfix_lane() -> None:
    reason = _readiness_reason(
        json.dumps(
            {
                "event": "ReadinessRefused",
                "invariants": [
                    {
                        "id": "slice_plan_section",
                        "status": "failed",
                        "remediation": "add slice plan",
                    },
                    {
                        "id": "sustainability",
                        "status": "failed",
                        "remediation": "add sustainability section",
                    },
                ],
            }
        )
    )
    assert _MARKER in reason, reason
    assert _JUSTIFICATION in reason, reason


def test_readiness_non_ceremony_failure_carries_no_bugfix_hint() -> None:
    # A failure that is NOT a feature-delta ceremony invariant (e.g. the gate
    # could not run from a valid CWD) must not surface the bugfix-lane hint.
    reason = _readiness_reason(
        json.dumps(
            {
                "event": "ReadinessRefused",
                "invariants": [
                    {
                        "id": "gate_output_produceable",
                        "status": "failed",
                        "remediation": "run from valid cwd",
                    }
                ],
            }
        )
    )
    assert _MARKER not in reason, reason
