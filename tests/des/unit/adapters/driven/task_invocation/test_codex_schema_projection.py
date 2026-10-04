"""Native Codex grammar retains role outcome/payload coherence without execution."""

import copy

import jsonschema
import pytest

from des.adapters.driven.task_invocation.model_envelope import (
    codex_schema_for,
    decode_model_run,
)
from des.ports.driven_ports.task_invocation_port import MalformedModelEnvelope


def test_codex_review_schema_binds_defects_to_the_selected_values():
    role = "nw-software-crafter-reviewer"
    value = "The operator sees the completed transfer."
    validator = jsonschema.Draft202012Validator(
        codex_schema_for(role, defect_values=(value,))
    )
    accepted = {
        "outcome": "accepted",
        "diagnostic": "",
        "defect_owner": None,
        "defect_value": None,
    }
    rejected = {
        "outcome": "rejected",
        "diagnostic": "Transfer result is absent.",
        "defect_owner": "implementation",
        "defect_value": value,
    }
    for answer in (accepted, rejected):
        validator.validate({"answer": answer})
        run = decode_model_run(answer, role_id=role, defect_values=(value,))
        assert run.outcome.value == answer["outcome"]
    invalid = (
        dict(accepted, defect_owner="implementation"),
        dict(rejected, defect_value="An unselected value."),
    )
    for answer in invalid:
        with pytest.raises(jsonschema.ValidationError):
            validator.validate({"answer": answer})
        with pytest.raises(MalformedModelEnvelope):
            decode_model_run(answer, role_id=role, defect_values=(value,))
    # Nonblank rejection diagnostics are enforced by native structured output;
    # the legacy semantic decoder validates the string type, not its length.
    with pytest.raises(jsonschema.ValidationError):
        validator.validate({"answer": dict(rejected, diagnostic="")})


def test_codex_recovery_schema_preserves_complete_document_and_task_boundary():
    role = "nw-acceptance-designer"
    task = "selected-revision-recovery"
    validator = jsonschema.Draft202012Validator(
        codex_schema_for(role, semantic_task=task)
    )
    answer = {
        "outcome": "accepted",
        "diagnostic": "The complete selected revision is realigned.",
        "distill_document": {
            "schema_version": 2,
            "values": [
                {
                    "observation": "A user sees the revised public behavior.",
                    "acceptance_obligations": [
                        {
                            "id": "revision-current",
                            "stimulus": "Use the revised public operation.",
                            "expected": "The selected revision is observable.",
                        }
                    ],
                    "oracle": "tests/acceptance/test_revision.py::test_current",
                    "acceptance_supports": ["tests/support/revision_driver.py"],
                    "verification": [
                        ["python", "-m", "pytest", "tests/acceptance/test_revision.py"]
                    ],
                    "oracle_verification_index": 0,
                }
            ],
        },
    }
    validator.validate({"answer": answer})
    run = decode_model_run(answer, role_id=role, semantic_task=task)
    assert (
        run.distill_document.values[0].oracle
        == "tests/acceptance/test_revision.py::test_current"
    )
    incomplete = copy.deepcopy(answer)
    del incomplete["distill_document"]["values"][0]["oracle_verification_index"]
    for invalid in (incomplete, dict(answer, outcome="rejected")):
        with pytest.raises(jsonschema.ValidationError):
            validator.validate({"answer": invalid})
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(codex_schema_for(role)).validate(
            {"answer": answer}
        )
    with pytest.raises(MalformedModelEnvelope):
        decode_model_run(answer, role_id=role)
