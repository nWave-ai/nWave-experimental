"""Public refusal, normalized ADR publication and opaque DESIGN reconstruction."""

import copy
import json

import pytest
from tests.common.in_process_cli import run_cli_in_process
from tests.des._helpers.host_facts import design_manifest
from tests.des.acceptance.design_document_construction.test_design_document_construction import (  # noqa: F401 - pytest fixture used by name
    HANDOVER,
    REPOSITORY_DESTINATION,
    UNRELATED_AUTHORITY_PREFIX,
    UNRELATED_AUTHORITY_SUFFIX,
    WIDGET_INPUT,
    _bootstrap_value,
    _design,
    _track_authority,
    design_repository,
    git,
)

from des.application.handover import Blocked, design_facts_defect, read_handover
from des.domain.design_document import FactCatalog, build_fact_catalog, normalized_wire
from des.ports.driven_ports.task_invocation_port import DesignFacts, PreNormalizedDesign


def _adr_input() -> dict:
    supplied = copy.deepcopy(WIDGET_INPUT)
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


def _adr_manifest() -> dict:
    supplied = _adr_input()
    return design_manifest(supplied, supplied["purpose"], 1)


@pytest.mark.parametrize("field", ["architectural_tests", "contract_tests"])
def test_invalid_declared_check_link_refuses_before_either_projection_moves(
    design_repository, tmp_path, field: str
) -> None:
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    authority = _track_authority(root, UNRELATED_AUTHORITY_PREFIX)
    authority_before = authority.read_bytes()
    handover_before = (root / HANDOVER).read_bytes()
    supplied = copy.deepcopy(WIDGET_INPUT)
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
        supplied["agreement_analysis"] = {
            "applicability": "applicable",
            "parties": [
                {
                    "contract": "Widget wire format",
                    "role": role,
                    "locator": locator,
                    "decision": "UNCHANGED_COMPATIBLE",
                    "reason": "The declared party retains the widget wire contract.",
                }
                for role, locator in (
                    ("producer", "src/widget.py:1"),
                    ("consumer", "tests/test_widget.py:1"),
                )
            ],
        }
        supplied["impact_closure"] = {
            "applicability": "applicable",
            "items": [
                {
                    "kind": kind,
                    "locator": locator,
                    "decision": "UNCHANGED_COMPATIBLE",
                    "reason": "The declared widget check reaches this existing owner.",
                }
                for kind, locator in (
                    ("runtime", "src/widget.py"),
                    ("consumer", "tests/test_widget.py:1"),
                )
            ],
        }
    supplied[field] = {"applicability": "applicable", "obligations": [obligation]}
    supplied = design_manifest(supplied, supplied["purpose"], 1)
    code, out, err = _design(root, environment, supplied)
    assert code != 0, out + err
    assert "verification_index" in out + err
    assert "InvalidDesignDocument" in out + err
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
    decision = "Use the existing color owner with explicit refusal for invalid colors."
    consequence = "Invalid colors refuse before any widget is created."
    supplied["facts"].extend(
        [
            {"id": "V1-adr-correction", "text": decision},
            {"id": "V1-adr-consequence", "text": consequence},
        ]
    )
    supplied["adr"]["decision"] = {"ref": "V1-adr-correction"}
    supplied["adr"]["consequences"] = [{"ref": "V1-adr-consequence"}]
    code, out, err = _design(root, environment, supplied, replace_current=True)
    assert code == 0, out + err
    after = authority.read_bytes()
    handover_after = (root / HANDOVER).read_bytes()
    assert after != before
    assert after.startswith(UNRELATED_AUTHORITY_PREFIX)
    assert after.endswith(UNRELATED_AUTHORITY_SUFFIX)
    restored = read_handover(handover_after)
    assert not isinstance(restored, Blocked)
    assert isinstance(restored.values[0].authority, DesignFacts)
    assert (
        normalized_wire(restored.values[0].authority.adr.decision)
        == supplied["adr"]["decision"]
    )
    assert (
        normalized_wire(restored.values[0].authority.adr.consequences)
        == supplied["adr"]["consequences"]
    )
    catalog = build_fact_catalog(restored.values[0].authority.facts)
    assert isinstance(catalog, FactCatalog), catalog
    assert catalog.resolve(restored.values[0].authority.adr.decision) == decision
    assert tuple(
        catalog.resolve(reference)
        for reference in restored.values[0].authority.adr.consequences
    ) == (consequence,)
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
    source = _adr_input()
    old_authority = {
        name: copy.deepcopy(source[name])
        for name in (
            "paradigm",
            "decisions",
            "oracle",
            "acceptance_supports",
            "verification",
            "oracle_verification_index",
            "public_oracle",
            "adr",
            "architectural_tests",
            "contract_tests",
            "prefactoring",
            "agreement_analysis",
            "reuse_analysis",
            "impact_closure",
        )
    }
    old_authority["targets"] = [
        {"path": target["path"], "decision": target["decision"]}
        for target in source["targets"]
    ]
    old_authority["obligations"] = copy.deepcopy(source["constraints"])
    old_authority["authority_locator"] = payload["values"][0]["authority"][
        "authority_locator"
    ]
    payload["values"][0]["authority"] = old_authority
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
    assert isinstance(parsed.values[0].authority, PreNormalizedDesign)
    assert parsed.values[0].authority.raw == old_authority
    diagnostic = design_facts_defect(parsed.values[0].authority)
    assert diagnostic is not None and "DesignFactsPreNormalized" in diagnostic
    assert "des design" in diagnostic and "--replace-current" in diagnostic
    authority_before = authority.read_bytes()
    refused_code, refused_out, refused_err = run_cli_in_process(
        [
            "handoff",
            "prompt",
            "--repo-root",
            str(root),
            "--role",
            "nw-software-crafter",
            "--value",
            "1",
            "--root-context",
            "README.md",
        ],
        cwd=root,
        env=environment,
        catch_all=True,
    )
    assert refused_code != 0, refused_out + refused_err
    assert "DesignFactsPreNormalized" in refused_out + refused_err
    assert "--replace-current" in refused_out + refused_err
    assert "native_input: " not in refused_out
    assert authority.read_bytes() == authority_before
    assert (root / HANDOVER).read_bytes() == legacy
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
    assert isinstance(parsed.values[0].authority, DesignFacts)
    assert design_facts_defect(parsed.values[0].authority) is None
    assert authority.read_bytes().startswith(UNRELATED_AUTHORITY_PREFIX)
    assert authority.read_bytes().endswith(UNRELATED_AUTHORITY_SUFFIX)
    code, out, err = _design(root, environment, supplied, replace_current=True)
    assert code == 0, out + err
    assert (root / HANDOVER).read_bytes() == recovered_raw
