"""Active-RED public-contract properties for the slice-00 parity journey."""

from __future__ import annotations

from collections.abc import Mapping
from types import SimpleNamespace

import pytest

from .composition import CodexParityJourneyComposition, diagnostic_field, field
from .port_witnesses import FivePortWitnesses
from .test_slice_00_shared_port_contracts import _request


pytestmark = [pytest.mark.acceptance]


def test_slice_00_requested_codex_authority_never_falls_back_to_detected_claude() -> (
    None
):
    """Target selection is observed at the public journey boundary."""
    # covers: R-S00-14
    ports = FivePortWitnesses()
    request = _request()
    subject = request["subject"]
    assert isinstance(subject, dict)
    subject["requested_platform"] = "CODEX"
    selection = subject["target_selection"]
    assert isinstance(selection, dict)
    selection["detected_capabilities"] = ["claude-installed"]

    result = CodexParityJourneyComposition().run(
        request, external_ports=ports.external_ports()
    )

    assert field(result, "outcome") == "REFUSED", (
        "WHAT: a requested Codex journey fell back to Claude. "
        "WHY: detection can prove executability but cannot change user authority. "
        "HOW: return a typed target-unavailable refusal without starting the pair."
    )
    assert field(result, "stage_error") == "TARGET_UNAVAILABLE"
    assert all(diagnostic_field(result, name) for name in ("what", "why", "how"))
    assert ports.trace.events == []


@pytest.mark.negative_at
@pytest.mark.parametrize(
    ("kind", "required_payload"),
    [
        ("DOCUMENTED", {}),
        ("UNVERIFIED", {}),
        ("UNSUPPORTED", {}),
        ("DEGRADED", {"policy_id": "operator-accepted"}),
        (
            "INDETERMINATE",
            {
                "reason": "native witness unavailable",
                "remediation": "supply a capable host",
            },
        ),
        (
            "FAILED",
            {
                "reason": "witness contradicted contract",
                "remediation": "repair then reprobe",
            },
        ),
    ],
)
def test_slice_00_never_promotes_non_green_evidence_to_full_parity(
    kind: str, required_payload: Mapping[str, str]
) -> None:
    """Every non-green evidence state remains externally distinguishable."""
    # covers: R-S00-15
    ports = FivePortWitnesses()
    request = _request()
    request["expected_evidence"] = {"kind": kind, **required_payload}

    result = CodexParityJourneyComposition().run(
        request, external_ports=ports.external_ports()
    )

    assert field(result, "outcome") != "FULL_CODEX_PARITY", (
        "WHAT: non-green evidence was promoted to a full support claim. "
        "WHY: documented, degraded, unavailable, and failed observations are not proof. "
        "HOW: retain the original closed evidence disposition in the result and ledger."
    )
    evidence = field(result, "evidence")
    assert field(evidence, "state") == kind
    assert field(evidence, "contributes_to_full_parity") is False


def test_slice_00_refuses_cross_subject_evidence_and_does_not_append_it() -> None:
    """The ledger population is scoped to the journey subject, not a lane-local claim."""
    # covers: R-S00-16
    seeded_records = (
        SimpleNamespace(
            composition_id="other-composition",
            candidate_id="distribution-1+manifest-1+recipe-1",
            manifest_digest="manifest-1",
            item="role:specialist",
        ),
    )
    ports = FivePortWitnesses(
        ledger_failure="SUBJECT_MISMATCH",
        ledger_records=seeded_records,
    )
    request = _request()

    result = CodexParityJourneyComposition().run(
        request, external_ports=ports.external_ports()
    )

    assert field(result, "outcome") == "REFUSED", (
        "WHAT: cross-subject evidence entered the current aggregate. "
        "WHY: a witness proves only its immutable host/candidate/manifest tuple. "
        "HOW: reject the mismatch before any successful ledger append."
    )
    assert field(result, "stage_error") in {"SUBJECT_MISMATCH", "LEDGER_REJECTED"}
    assert "ledger.append" in ports.trace.events, (
        "WHAT: the atomic subject-validation boundary was bypassed. "
        "WHY: append owns validation and may refuse without committing. "
        "HOW: attempt the append once and preserve its typed SUBJECT_MISMATCH receipt."
    )
    assert (ports.ledger_records, ports.ledger_commits) == (seeded_records, []), (
        "WHAT: a refused cross-subject append changed the durable ledger population. "
        "WHY: an invocation is not a committed mutation. "
        "HOW: validate and append atomically, leaving every seeded record unchanged."
    )
