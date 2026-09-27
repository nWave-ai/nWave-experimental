"""Implementation findings must not be mislabeled as architecture rework."""

import json

import pytest

from des.adapters.driven.task_invocation.model_envelope import (
    _schema_for,
    decode_model_run,
)
from des.ports.driven_ports.task_invocation_port import MalformedModelEnvelope


def refusal():
    return {
        "outcome": "rejected",
        "diagnostic": "Receipt duplicates the existing tax rule; repair receipt code.",
        "defect_owner": "implementation",
        "defect_value": None,
    }


def test_whole_candidate_reviewer_can_report_implementation_owner():
    schema = json.loads(_schema_for("nw-software-crafter-reviewer"))
    assert "implementation" in schema["then"]["properties"]["defect_owner"]["enum"]
    result = decode_model_run(refusal(), role_id="nw-software-crafter-reviewer")
    assert result.review_defect.owner.value == "implementation"


def test_acceptance_reviewer_cannot_charge_a_not_yet_authored_implementation():
    schema = json.loads(_schema_for("nw-acceptance-designer-reviewer"))
    assert "implementation" not in schema["then"]["properties"]["defect_owner"]["enum"]
    with pytest.raises(MalformedModelEnvelope, match="ReviewDefectOwner"):
        decode_model_run(refusal(), role_id="nw-acceptance-designer-reviewer")


def test_accepted_review_cannot_carry_implementation_defect():
    payload = refusal() | {"outcome": "accepted"}
    with pytest.raises(
        MalformedModelEnvelope, match="EnvelopeOutcomeContradictsPayload"
    ):
        decode_model_run(payload, role_id="nw-software-crafter-reviewer")
