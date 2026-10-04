"""Public refusal, ADR publication and historical DESIGN reconstruction contracts."""

import copy
import json

import pytest
from tests.des.acceptance.design_document_construction.test_design_document_construction import (  # noqa: F401 - pytest fixture used by name
    HANDOVER,
    MANIFEST,
    REPOSITORY_DESTINATION,
    UNRELATED_AUTHORITY_PREFIX,
    UNRELATED_AUTHORITY_SUFFIX,
    _bootstrap_value,
    _design,
    _track_authority,
    design_repository,
    git,
)

from des.application.handover import Blocked, design_facts_defect, read_handover
from des.ports.driven_ports.task_invocation_port import LegacyDesignFacts


def _adr_manifest() -> dict:
    supplied = copy.deepcopy(MANIFEST)
    supplied["adr"] = {
        "applicability": "applicable",
        "context": "Widget already owns color; callers depend on its default.",
        "decision": "Extend the existing color owner instead of adding a parallel owner.",
        "alternatives": [
            "A second configuration owner would duplicate the default rule."
        ],
        "consequences": [
            "Existing callers retain the default; selected color extends the same owner."
        ],
        "status": "accepted",
    }
    return supplied


@pytest.mark.parametrize("field", ["architectural_tests", "contract_tests"])
def test_invalid_declared_check_link_refuses_before_either_projection_moves(
    design_repository, tmp_path, field: str
) -> None:
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    authority = _track_authority(root, UNRELATED_AUTHORITY_PREFIX)
    authority_before = authority.read_bytes()
    handover_before = (root / HANDOVER).read_bytes()
    supplied = copy.deepcopy(MANIFEST)
    obligation = {
        "obligation": "A declared native check must remain part of verification.",
        "oracle": "tests/test_widget.py",
        "verification_index": 5,
    }
    if field == "contract_tests":
        obligation.update(
            contract="Widget wire format",
            producer="src/widget.py:1",
            consumer="tests/test_widget.py:1",
            observation="A consumer reads the selected color unchanged.",
        )
    supplied[field] = {"applicability": "applicable", "obligations": [obligation]}
    code, out, err = _design(root, environment, supplied)
    assert code != 0, out + err
    assert authority.read_bytes() == authority_before
    assert (root / HANDOVER).read_bytes() == handover_before


def test_adr_replacement_is_idempotent_and_preserves_foreign_sections(
    design_repository, tmp_path
) -> None:
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    _track_authority(root, UNRELATED_AUTHORITY_PREFIX)
    supplied = _adr_manifest()
    code, out, err = _design(root, environment, supplied)
    assert code == 0, out + err
    authority = root / REPOSITORY_DESTINATION
    authority.write_bytes(authority.read_bytes() + UNRELATED_AUTHORITY_SUFFIX)
    git(root, "add", str(REPOSITORY_DESTINATION))
    git(root, "commit", "-qm", "retain a foreign authority section")
    before = authority.read_bytes()
    supplied["adr"]["decision"] = (
        "Use the existing color owner with explicit refusal for invalid colors."
    )
    supplied["adr"]["consequences"] = [
        "Invalid colors refuse before any widget is created."
    ]
    code, out, err = _design(root, environment, supplied, replace_current=True)
    assert code == 0, out + err
    after = authority.read_bytes()
    handover_after = (root / HANDOVER).read_bytes()
    assert after != before
    assert after.startswith(UNRELATED_AUTHORITY_PREFIX)
    assert after.endswith(UNRELATED_AUTHORITY_SUFFIX)
    restored = read_handover(handover_after)
    assert not isinstance(restored, Blocked)
    assert restored.values[0].authority.adr.decision == supplied["adr"]["decision"]
    code, out, err = _design(root, environment, supplied, replace_current=True)
    assert code == 0, out + err
    assert authority.read_bytes() == after
    assert (root / HANDOVER).read_bytes() == handover_after


def test_explicit_constructor_reconstructs_unassessed_history_without_losing_graph(
    design_repository, tmp_path
) -> None:
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path, "widget color", "unrelated lookup")
    _track_authority(root, UNRELATED_AUTHORITY_PREFIX)
    supplied = _adr_manifest()
    code, out, err = _design(root, environment, supplied)
    assert code == 0, out + err
    authority = root / REPOSITORY_DESTINATION
    authority.write_bytes(authority.read_bytes() + UNRELATED_AUTHORITY_SUFFIX)
    git(root, "add", str(REPOSITORY_DESTINATION))
    git(root, "commit", "-qm", "retain a foreign authority section")
    payload = json.loads((root / HANDOVER).read_bytes())
    unrelated = copy.deepcopy(payload["values"][1])
    graph = [(item["observation"], item["dependencies"]) for item in payload["values"]]
    for name in (
        "architectural_tests",
        "contract_tests",
        "prefactoring",
        "agreement_analysis",
        "reuse_analysis",
        "impact_closure",
    ):
        del payload["values"][0]["authority"][name]
    legacy = json.dumps(payload, separators=(",", ":")).encode()
    (root / HANDOVER).write_bytes(legacy)
    parsed = read_handover(legacy)
    assert not isinstance(parsed, Blocked)
    assert isinstance(parsed.values[0].authority, LegacyDesignFacts)
    assert "unassessed" in design_facts_defect(parsed.values[0].authority)
    code, out, err = _design(root, environment, supplied, replace_current=True)
    assert code == 0, out + err
    recovered_raw = (root / HANDOVER).read_bytes()
    recovered = json.loads(recovered_raw)
    assert recovered["values"][1] == unrelated
    assert [
        (item["observation"], item["dependencies"]) for item in recovered["values"]
    ] == graph
    assert recovered["request"] == payload["request"]
    parsed = read_handover(recovered_raw)
    assert not isinstance(parsed, Blocked)
    assert not isinstance(parsed.values[0].authority, LegacyDesignFacts)
    assert design_facts_defect(parsed.values[0].authority) is None
    assert authority.read_bytes().startswith(UNRELATED_AUTHORITY_PREFIX)
    assert authority.read_bytes().endswith(UNRELATED_AUTHORITY_SUFFIX)
    code, out, err = _design(root, environment, supplied, replace_current=True)
    assert code == 0, out + err
    assert (root / HANDOVER).read_bytes() == recovered_raw
