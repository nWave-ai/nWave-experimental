import json
from dataclasses import replace

import pytest

from des.application.handover import (
    Blocked,
    HandoverValue,
    _canonical_bytes,
    design_facts_defect,
    read_handover,
)
from des.domain.design_document import (
    DesignDocument,
    DesignDocumentInvalid,
    DesignFactsSection,
    design_decisions_defect,
)
from des.ports.driven_ports.task_invocation_port import (
    ApplicableImpactClosure,
    ApplicablePrefactoring,
    ImpactItem,
    LegacyDesignFacts,
    NotApplicable,
    ReuseAnalysis,
    ReuseCandidate,
    UnassessedDesignDecision,
)


def manifest() -> dict:
    not_applicable = {
        "applicability": "not_applicable",
        "reason": "No dependency boundary changes.",
    }
    return {
        "schema_version": 1,
        "authority": {"heading": "Native reservation contract"},
        "purpose": "Preserve reservation observations across native consumers.",
        "constraints": ["Cancelled reservations cannot be consumed."],
        "targets": [
            {
                "path": "lib/reservations.ml",
                "decision": "EXTEND",
                "reason": "Existing owner.",
            }
        ],
        "paradigm": "functional",
        "decisions": ["Keep the reservation owner and migrate the CLI consumer."],
        "reuse_analysis": {"candidates": []},
        "impact_closure": {
            "applicability": "applicable",
            "items": [
                {
                    "kind": "runtime",
                    "locator": "lib/reservations.ml",
                    "decision": "CHANGED",
                    "reason": "Why.",
                },
                {
                    "kind": "consumer",
                    "locator": "bin/main.ml:1",
                    "decision": "UNCHANGED_COMPATIBLE",
                    "reason": "Why.",
                },
            ],
        },
        "prefactoring": {
            "applicability": "applicable",
            "existing_oracle": "test/preservation.ml",
            "move": "Extract reservation decoding without changing behavior.",
            "preserved_observation": "Existing reservation identifiers remain stable.",
            "verification": [["dune", "exec", "test/preservation.exe"]],
            "acceptance_supports": ["test/support.ml"],
        },
        "agreement_analysis": {
            "applicability": "applicable",
            "parties": [
                {
                    "contract": "Reservation wire format",
                    "role": "producer",
                    "locator": "lib/reservations.ml:1",
                    "decision": "MIGRATED",
                    "reason": "Writes the format.",
                },
                {
                    "contract": "Reservation wire format",
                    "role": "consumer",
                    "locator": "bin/main.ml:1",
                    "decision": "UNCHANGED_COMPATIBLE",
                    "reason": "Reads the same tagged format.",
                },
            ],
        },
        "architectural_tests": {
            "applicability": "applicable",
            "obligations": [
                {
                    "obligation": "The domain cannot depend on CLI effects.",
                    "oracle": "test/dependencies.ml",
                    "verification_index": 1,
                }
            ],
        },
        "contract_tests": {
            "applicability": "applicable",
            "obligations": [
                {
                    "obligation": "The CLI rejects cancelled reservation payloads.",
                    "contract": "Reservation wire format",
                    "producer": "lib/reservations.ml:1",
                    "consumer": "bin/main.ml:1",
                    "observation": "Cancelled input returns the declared business refusal.",
                    "oracle": "test/contracts.ml::cancelled",
                    "verification_index": 1,
                }
            ],
        },
        "adr": {
            "applicability": "applicable",
            "context": "A CLI consumer reads the reservation format.",
            "decision": "Keep one tagged reservation format.",
            "alternatives": ["A second independently decoded format was rejected."],
            "consequences": ["Both parties use the same cancelled-state meaning."],
            "status": "accepted",
        },
        "boundaries": dict(not_applicable),
        "public_oracle": {
            "observation": "Cancellation cannot reactivate a reservation.",
            "stimulus": "Cancel then consume.",
            "expected": "The consume attempt is refused.",
            "falsifier": "The consume attempt succeeds.",
        },
        "oracle": "test/reservations.ml",
        "acceptance_supports": [],
        "verification": [
            ["dune", "exec", "test/reservations.exe"],
            ["dune", "runtest", "test"],
        ],
        "oracle_verification_index": 0,
    }


@pytest.mark.parametrize(
    "field",
    [
        "architectural_tests",
        "contract_tests",
        "prefactoring",
        "agreement_analysis",
        "impact_closure",
    ],
)
def test_new_design_refuses_omission_instead_of_assuming_not_applicable(
    field: str,
) -> None:
    supplied = manifest()
    del supplied[field]
    with pytest.raises(DesignDocumentInvalid):
        DesignDocument.from_json(json.dumps(supplied))


@pytest.mark.parametrize("field", ["architectural_tests", "contract_tests"])
def test_deliberate_non_applicability_requires_a_real_reason(field: str) -> None:
    supplied = manifest()
    supplied[field] = {"applicability": "not_applicable", "reason": "  "}
    with pytest.raises(DesignDocumentInvalid):
        DesignDocument.from_json(json.dumps(supplied))
    supplied[field]["reason"] = (
        "This local change touches no applicable boundary or agreement."
    )
    facts = DesignDocument.from_json(json.dumps(supplied)).facts
    assert isinstance(getattr(facts, field), NotApplicable)


@pytest.mark.parametrize("field", ["architectural_tests", "contract_tests"])
def test_applicable_check_cannot_lose_its_obligation_or_declared_command(
    field: str,
) -> None:
    supplied = manifest()
    supplied[field]["obligations"] = []
    with pytest.raises(DesignDocumentInvalid):
        DesignDocument.from_json(json.dumps(supplied))
    supplied = manifest()
    supplied[field]["obligations"][0]["verification_index"] = 2
    with pytest.raises(DesignDocumentInvalid, match="declared verification command"):
        DesignDocument.from_json(json.dumps(supplied))


@pytest.mark.parametrize("party", ["producer", "consumer"])
def test_contract_check_must_link_the_agreed_party_not_a_different_contract(
    party: str,
) -> None:
    supplied = manifest()
    supplied["contract_tests"]["obligations"][0][party] = "lib/unrelated.ml:1"
    with pytest.raises(DesignDocumentInvalid, match="agreement party"):
        DesignDocument.from_json(json.dumps(supplied))


@pytest.mark.parametrize("decision", ["EXTEND", "CREATE_NEW"])
def test_a_craft_target_is_never_also_an_acceptance_support(decision: str) -> None:
    supplied = manifest()
    supplied["targets"][0]["decision"] = decision
    supplied["acceptance_supports"] = ["test/fixture.ml", "lib/reservations.ml"]
    with pytest.raises(DesignDocumentInvalid, match=r"lib/reservations\.ml") as refused:
        DesignDocument.from_json(json.dumps(supplied))
    assert "test/fixture.ml" not in str(refused.value)
    supplied["acceptance_supports"] = ["test/fixture.ml"]
    DesignDocument.from_json(json.dumps(supplied))


def test_native_assurance_and_preservation_selection_survive_handover_restart() -> None:
    document = DesignDocument.from_json(json.dumps(manifest()))
    bound = document.facts_at("docs/decisions.md#Native reservation contract")
    payload = _canonical_bytes(
        "Preserve reservations", (HandoverValue("Reservation cancellation", (), bound),)
    )
    restored = read_handover(payload)
    assert not isinstance(restored, Blocked)
    facts = restored.values[0].authority
    assert facts == bound
    broken = replace(facts, verification=(facts.verification[0],))
    assert "declared verification command" in design_facts_defect(broken)
    assert isinstance(facts.prefactoring, ApplicablePrefactoring)
    assert facts.prefactoring.verification != facts.verification
    changed = manifest()
    changed["prefactoring"]["verification"] = [["dune", "exec", "test/other.exe"]]
    assert (
        DesignDocument.from_json(json.dumps(changed)).semantic_sha256
        != document.semantic_sha256
    )


def test_legacy_absence_is_readable_history_not_approved_non_applicability() -> None:
    bound = DesignDocument.from_json(json.dumps(manifest())).facts_at(
        "docs/decisions.md#Native reservation contract"
    )
    payload = json.loads(
        _canonical_bytes(
            "Preserve reservations", (HandoverValue("Cancellation", (), bound),)
        )
    )
    for name in (
        "architectural_tests",
        "contract_tests",
        "prefactoring",
        "agreement_analysis",
        "reuse_analysis",
        "impact_closure",
    ):
        del payload["values"][0]["authority"][name]
    raw = json.dumps(payload, separators=(",", ":")).encode()
    restored = read_handover(raw)
    assert not isinstance(restored, Blocked)
    facts = restored.values[0].authority
    assert isinstance(facts, LegacyDesignFacts)
    assert isinstance(facts.architectural_tests, UnassessedDesignDecision)
    assert "unassessed" in design_facts_defect(facts)
    reencoded = json.loads(_canonical_bytes(restored.request, restored.values))
    assert reencoded == payload


@pytest.mark.parametrize(
    "locator",
    [
        "docs/brief.md",
        "docs/brief.md#",
        "docs/brief.md#   ",
        "docs/brief.md### Native",
        "docs/brief.md#Native\ncontract",
    ],
)
def test_a_locator_naming_no_renderable_section_is_refused_not_guessed(
    locator: str,
) -> None:
    facts = DesignDocument.from_json(json.dumps(manifest())).facts
    assert DesignFactsSection.for_locator(locator, facts) is None


def _closed(items: list[dict]) -> dict:
    return {"applicability": "applicable", "items": items}


def _item(kind: str, locator: str, decision: str = "CHANGED") -> dict:
    return {"kind": kind, "locator": locator, "decision": decision, "reason": "Why."}


def test_input_description_documents_impact_closure() -> None:
    assert "impact_closure" in DesignDocument.input_description()


def test_unclosed_impact_closure_names_every_missing_locator_in_one_refusal() -> None:
    supplied = manifest()
    supplied["targets"].append(
        {"path": "lib/extra.ml", "decision": "CREATE_NEW", "reason": "New."}
    )
    supplied["impact_closure"] = _closed([_item("runtime", "lib/reservations.ml")])
    with pytest.raises(DesignDocumentInvalid) as refused:
        DesignDocument.from_json(json.dumps(supplied))
    message = str(refused.value)
    assert "bin/main.ml:1" in message
    assert "lib/extra.ml" in message


def test_not_applicable_closure_is_refused_when_a_consumer_is_declared() -> None:
    supplied = manifest()
    supplied["impact_closure"] = {
        "applicability": "not_applicable",
        "reason": "Nothing else is reached.",
    }
    with pytest.raises(DesignDocumentInvalid, match=r"bin/main\.ml:1"):
        DesignDocument.from_json(json.dumps(supplied))


def test_closed_manifest_constructs_and_carries_reuse_and_impact_everywhere() -> None:
    supplied = manifest()
    supplied["reuse_analysis"] = {
        "candidates": [
            {
                "symbol": "Reservations",
                "locator": "lib/reservations.ml:3",
                "decision": "EXTEND",
                "reason": "Existing owner.",
            }
        ]
    }
    document = DesignDocument.from_json(json.dumps(supplied))
    assert document.facts.reuse_analysis == ReuseAnalysis(
        (
            ReuseCandidate(
                "Reservations", "lib/reservations.ml:3", "EXTEND", "Existing owner."
            ),
        )
    )
    assert document.facts.impact_closure == ApplicableImpactClosure(
        (
            ImpactItem("runtime", "lib/reservations.ml", "CHANGED", "Why."),
            ImpactItem("consumer", "bin/main.ml:1", "UNCHANGED_COMPATIBLE", "Why."),
        )
    )
    projected = json.loads(document.facts_json())
    assert "reuse_analysis" in projected
    assert "impact_closure" in projected
    assert "Impact closure" in document.markdown()


def test_changing_one_impact_decision_changes_the_semantic_digest() -> None:
    base = DesignDocument.from_json(json.dumps(manifest()))
    changed = manifest()
    changed["impact_closure"]["items"][0]["decision"] = "MIGRATED"
    assert (
        DesignDocument.from_json(json.dumps(changed)).semantic_sha256
        != base.semantic_sha256
    )


def test_facts_section_renders_reuse_and_impact_closure() -> None:
    facts = DesignDocument.from_json(json.dumps(manifest())).facts
    rendered = DesignFactsSection("Native reservation contract", facts).markdown()
    assert "Reuse analysis" in rendered
    assert "Impact closure" in rendered
    assert "bin/main.ml:1" in rendered


def test_non_source_targets_are_closed_by_role_kinds_not_language_names() -> None:
    supplied = manifest()
    extras = [
        ("dune-project", "build_metadata"),
        ("reservations.opam", "manifest"),
        ("reservations.opam.locked", "lock"),
    ]
    items = list(supplied["impact_closure"]["items"])
    for path, kind in extras:
        supplied["targets"].append(
            {"path": path, "decision": "EXTEND", "reason": "Metadata."}
        )
        items.append(_item(kind, path))
    supplied["impact_closure"] = _closed(items)
    facts = DesignDocument.from_json(json.dumps(supplied)).facts
    assert {item.kind for item in facts.impact_closure.items} >= {
        "build_metadata",
        "manifest",
        "lock",
    }
    items[-1] = _item("ocaml_lockfile", "reservations.opam.locked")
    supplied["impact_closure"] = _closed(items)
    with pytest.raises(DesignDocumentInvalid):
        DesignDocument.from_json(json.dumps(supplied))


def _defects(supplied: dict) -> tuple[str, ...]:
    with pytest.raises(DesignDocumentInvalid) as refused:
        DesignDocument.from_json(json.dumps(supplied))
    return refused.value.defects


def _naming(defects: tuple[str, ...], pointer: str) -> list[str]:
    return [defect for defect in defects if defect.startswith(pointer)]


def test_two_independent_field_defects_are_refused_together() -> None:
    supplied = manifest()
    supplied["purpose"] = "  "
    supplied["targets"][0]["path"] = "/tmp/reservations.ml"

    defects = _defects(supplied)

    assert len(defects) == 2, defects
    assert _naming(defects, "manifest.purpose"), defects
    assert _naming(defects, "manifest.targets[0].path"), defects


def test_a_field_defect_and_a_cross_field_defect_are_refused_together() -> None:
    supplied = manifest()
    supplied["purpose"] = "  "
    supplied["oracle_verification_index"] = 2

    defects = _defects(supplied)

    assert len(defects) == 2, defects
    assert _naming(defects, "manifest.purpose"), defects
    assert _naming(defects, "manifest.oracle_verification_index"), defects
    # A cross-field rule over a refused field does not run: the refused
    # verification is the one defect, not also every index pointing into it.
    supplied = manifest()
    supplied["verification"] = "dune runtest"
    supplied["oracle_verification_index"] = 5
    (only,) = _defects(supplied)
    assert only.startswith("manifest.verification "), only


def test_every_violated_design_decision_rule_is_refused_together() -> None:
    supplied = manifest()
    supplied["architectural_tests"]["obligations"][0]["verification_index"] = 2
    supplied["prefactoring"]["acceptance_supports"] = ["test/preservation.ml"]

    defects = _defects(supplied)

    assert len(defects) == 2, defects
    assert _naming(defects, "architectural_tests.verification_index"), defects
    assert _naming(defects, "prefactoring.acceptance_supports"), defects
    facts = DesignDocument.from_json(json.dumps(manifest())).facts
    obligation = facts.architectural_tests.obligations[0]
    persisted = replace(
        facts,
        architectural_tests=replace(
            facts.architectural_tests,
            obligations=(replace(obligation, verification_index=2),),
        ),
        prefactoring=replace(
            facts.prefactoring, acceptance_supports=("test/preservation.ml",)
        ),
    )
    defect = design_decisions_defect(persisted)
    assert defect is not None
    assert "architectural_tests.verification_index" in defect, defect
    assert "prefactoring.acceptance_supports" in defect, defect


def test_an_unlinked_contract_party_names_the_parties_the_agreement_declares() -> None:
    supplied = manifest()
    supplied["contract_tests"]["obligations"][0]["producer"] = "lib/unrelated.ml:1"

    (producer,) = _defects(supplied)

    assert producer.startswith("contract_tests.producer"), producer
    assert "lib/reservations.ml:1" in producer, producer
    # The contract named with a different spelling than the agreement's.
    supplied = manifest()
    supplied["contract_tests"]["obligations"][0]["contract"] = (
        "Reservations wire format"
    )

    producer, consumer = _defects(supplied)

    assert "lib/reservations.ml:1" in producer, producer
    assert "Reservation wire format" in producer, producer
    assert "bin/main.ml:1" in consumer, consumer
