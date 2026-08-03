"""Unit tests for the readiness-gate refusal surface (what/why/how propagation).

Regression pin for the opaque-rejection defect: when the
`verify-readiness-pre-dispatch` gate refuses a dispatch, the agent-facing
`InterceptDecision.reason` MUST carry, for every FAILED invariant, its ``id``
(WHAT) and its ``remediation`` (HOW) -- not the bare ``ReadinessRefused`` event
name. Before the fix `_carpaccio_reason` collapsed the rich JSON payload to
`payload.get("event")`, dropping the `invariants[].remediation` the gate already
computed, so the agent had to re-run the gate by hand to learn the next step
(violating the STANDING every-failure-explains rule).

Port-to-port: the driving port is `evaluate_atdd_pure_dispatch`; the injected
`readiness_runner` stands in for the real CLI subprocess, emitting the exact
JSON shape `des.cli.verify_readiness_pre_dispatch._emit_report` produces.
"""

from __future__ import annotations

import json
from pathlib import Path

from des.adapters.drivers.hooks.carpaccio_intercept import (
    _readiness_reason,
    evaluate_atdd_pure_dispatch,
)


_FEATURE_ID = "demo-feature"

_REUSE_REMEDIATION = (
    "Add a `## Reuse Analysis` section (DDD-8 / nw-design SKILL.md step 5)"
)
_SUSTAINABILITY_REMEDIATION = (
    "Add a well-formed `## Test Reuse & Consolidation Analysis` section"
)


def _atdd_pure_prompt(slice_id: str = "slice-01") -> str:
    return (
        "<!-- DES-VALIDATION : required -->\n"
        "<!-- DES-MODE : atdd_pure -->\n"
        "<!-- DES-PHASE : A_GREEN_ATS -->\n"
        f"<!-- DES-SLICE : {slice_id} -->\n"
        f"<!-- DES-PROJECT-ID : {_FEATURE_ID} -->\n"
    )


def _readiness_refused_payload() -> str:
    """The exact JSON shape `verify_readiness_pre_dispatch._emit_report` emits."""
    return json.dumps(
        {
            "event": "ReadinessRefused",
            "feature_id": _FEATURE_ID,
            "slice_id": "slice-01",
            "verdict": "refused",
            "invariants": [
                {
                    "id": "slice_plan_section",
                    "status": "satisfied",
                    "remediation": None,
                    "confidence": "",
                },
                {
                    "id": "reuse_first_or_design_skip",
                    "status": "failed",
                    "remediation": _REUSE_REMEDIATION,
                    "confidence": "",
                },
                {
                    "id": "sustainability",
                    "status": "failed",
                    "remediation": _SUSTAINABILITY_REMEDIATION,
                    "confidence": "",
                },
            ],
        }
    )


def test_readiness_refusal_reason_names_failed_invariants_and_remediations(
    tmp_path: Path,
) -> None:
    """A readiness refusal surfaces each failed invariant id + its remediation."""
    decision = evaluate_atdd_pure_dispatch(
        prompt=_atdd_pure_prompt("slice-01"),
        feature_id=_FEATURE_ID,
        project_root=tmp_path,
        carpaccio_runner=lambda _f, _s: (0, "{}"),
        readiness_runner=lambda _f, _s: (1, _readiness_refused_payload()),
    )

    assert decision.is_block
    assert decision.event == "ReadinessGateRejected"
    reason = decision.reason or ""
    # WHAT: each FAILED invariant id is named.
    assert "reuse_first_or_design_skip" in reason
    assert "sustainability" in reason
    # HOW: each failed invariant's remediation is propagated.
    assert _REUSE_REMEDIATION in reason
    assert _SUSTAINABILITY_REMEDIATION in reason
    # The satisfied invariant is NOT listed as a failure.
    assert "slice_plan_section" not in reason


def test_readiness_reason_lists_only_failed_invariants() -> None:
    """`_readiness_reason` enumerates failed invariants, skipping satisfied ones."""
    reason = _readiness_reason(_readiness_refused_payload())

    assert "2 invariant(s) failed" in reason
    assert "reuse_first_or_design_skip" in reason
    assert _REUSE_REMEDIATION in reason
    assert "slice_plan_section" not in reason


def test_readiness_reason_degrades_loud_on_unparseable_output() -> None:
    """Non-JSON gate output falls back to the carpaccio reason (never silent)."""
    assert _readiness_reason("not json at all") == "not json at all"


def test_readiness_reason_degrades_loud_when_no_invariants_key() -> None:
    """A payload without an `invariants` list falls back to the event name."""
    assert _readiness_reason('{"event": "ReadinessRefused"}') == "ReadinessRefused"


def test_readiness_reason_handles_failed_invariant_with_no_remediation() -> None:
    """A failed invariant missing its remediation is still named (degrade-LOUD).

    Uses `slice_plan_section` -- a surviving readiness invariant -- rather than
    the now-deleted `at_review_verdict` id (fix-readiness-carpaccio-disagree):
    that id can never again appear in a real readiness-gate payload, so
    asserting on it would exercise a state the system can no longer produce.
    """
    payload = json.dumps(
        {
            "event": "ReadinessRefused",
            "invariants": [
                {"id": "slice_plan_section", "status": "failed", "remediation": None},
            ],
        }
    )
    reason = _readiness_reason(payload)
    assert "slice_plan_section" in reason
    assert "(no remediation provided)" in reason
