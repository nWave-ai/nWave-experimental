"""Provider translation is limited to the enforced outcome envelope."""

from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema
import pytest

from des.adapters.driven.task_invocation.model_envelope import (
    _acceptance_reviewer_schema,
    _schema_for,
    codex_schema_for,
    decode_model_run,
)
from des.ports.driven_ports.task_invocation_port import (
    CraftBlocker,
    DefectOwner,
    MalformedModelEnvelope,
    ModelOutcome,
)


def test_architect_outcome_keeps_opaque_diagnostic_and_typed_facts() -> None:
    diagnostic = "Updated the ADR; do not parse this sentence."

    run = decode_model_run(
        json.loads(
            json.dumps(
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": diagnostic,
                        "design_facts": {
                            "targets": [{"path": "src/x.py", "decision": "EXTEND"}],
                            "paradigm": "functional",
                            "decisions": ["opaque"],
                            "oracle": "tests/test_x.py",
                            "acceptance_supports": [],
                            "verification": [["pytest", "-q"]],
                            "oracle_verification_index": 0,
                            "authority_locator": "",
                            "architectural_tests": {
                                "applicability": "not_applicable",
                                "reason": "The fixture has no structural boundary change.",
                            },
                            "contract_tests": {
                                "applicability": "not_applicable",
                                "reason": "The fixture changes no shared contract.",
                            },
                            "prefactoring": {
                                "applicability": "not_applicable",
                                "reason": "The fixture requires no preservation move.",
                            },
                            "agreement_analysis": {
                                "applicability": "not_applicable",
                                "reason": "The fixture has no affected agreement.",
                            },
                            "reuse_analysis": {"candidates": []},
                            "impact_closure": {
                                "applicability": "not_applicable",
                                "reason": "The fixture reaches no public surface, consumer or build metadata.",
                            },
                        },
                    }
                }
            )
        )["structured_output"],
        role_id="nw-solution-architect",
    )

    assert run.outcome is ModelOutcome.Accepted
    assert run.diagnostic == diagnostic
    assert run.design_facts is not None


def test_architect_design_field_is_rejected_at_the_provider_boundary() -> None:
    envelope = json.dumps(
        {
            "structured_output": {
                "outcome": "accepted",
                "diagnostic": "opaque",
                "design": {"paradigm": "object_oriented"},
            }
        }
    )

    with pytest.raises(ValueError, match="ModelOutcomeMalformed"):
        decode_model_run(
            json.loads(envelope)["structured_output"], role_id="nw-solution-architect"
        )


@pytest.mark.parametrize(
    ("outcome", "diagnostic", "expected"),
    [
        ("accepted", "done", ModelOutcome.Accepted),
        ("rejected", "complete finding", ModelOutcome.Rejected),
        ("indeterminate", "unknown effect", ModelOutcome.Indeterminate),
    ],
)
def test_provider_result_translates_each_enforced_outcome(
    outcome: str, diagnostic: str, expected: ModelOutcome
) -> None:
    envelope = json.dumps(
        {
            "structured_output": {
                "outcome": outcome,
                "diagnostic": diagnostic,
            },
            "result": "duplicate serialization is ignored",
        }
    )
    run = decode_model_run(json.loads(envelope)["structured_output"])

    assert run.outcome is expected
    assert run.diagnostic == diagnostic


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"outcome": "accepted"},
        {"outcome": "PASS", "diagnostic": ""},
        {"outcome": "accepted", "diagnostic": "", "payload": None},
        "accepted",
    ],
)
def test_provider_refuses_result_outside_the_minimal_schema(payload: object) -> None:
    envelope = json.dumps({"structured_output": payload})

    with pytest.raises(ValueError, match="ModelOutcome"):
        decode_model_run(json.loads(envelope)["structured_output"])


def _product_owner_stdout(count: int) -> str:
    return json.dumps(
        {
            "structured_output": {
                "outcome": "accepted",
                "diagnostic": "",
                "values": [{"observation": f"v{index}"} for index in range(count)],
            }
        }
    )


def test_a_suffix_larger_than_the_declared_window_is_a_malformed_envelope() -> None:
    """The provider does not enforce cardinality, so the envelope law does."""
    with pytest.raises(MalformedModelEnvelope, match="ProductValuesOutsideWindow"):
        decode_model_run(
            json.loads(_product_owner_stdout(3))["structured_output"],
            role_id="nw-product-owner",
            max_product_values=2,
        )


def test_an_empty_suffix_inside_a_declared_window_is_consumed() -> None:
    """Zero is inside the window: the consumer, not the envelope, judges it.

    The envelope law owns cardinality against the declared window; whether an
    empty suffix leaves a value in the graph is the correction consumer's
    decision, and it refuses there with a product-side diagnostic.
    """
    run = decode_model_run(
        json.loads(_product_owner_stdout(0))["structured_output"],
        role_id="nw-product-owner",
        max_product_values=2,
    )

    assert run.product_values == ()


def test_a_suffix_inside_the_declared_window_is_consumed() -> None:
    run = decode_model_run(
        json.loads(_product_owner_stdout(2))["structured_output"],
        role_id="nw-product-owner",
        max_product_values=2,
    )

    assert [value.observation for value in run.product_values] == ["v0", "v1"]


def test_an_unbounded_product_owner_turn_admits_any_cardinality() -> None:
    run = decode_model_run(
        json.loads(_product_owner_stdout(5))["structured_output"],
        role_id="nw-product-owner",
    )

    assert len(run.product_values) == 5


def _recorded_architect_answer() -> dict:
    """The EXACT structured output the provider returned for turn 04 of run
    20260905T002110Z-3913588 -- `accepted`, with six prose sentences where
    `acceptance_supports` requires repository-relative file locators."""
    return json.loads(
        (Path(__file__).parent / "turn_04_architect_structured_output.json").read_text(
            encoding="utf-8"
        )
    )


_NO_IMPACT = {
    "applicability": "not_applicable",
    "reason": "The fixture reaches no public surface, consumer or build metadata.",
}


def _current_architect_answer() -> dict:
    """Synthetic current input; the historical provider receipt stays immutable."""
    answer = _recorded_architect_answer()
    for name, reason in (
        ("architectural_tests", "The example changes no structural boundary."),
        ("contract_tests", "The example changes no shared contract."),
        ("prefactoring", "No preservation move is required."),
        ("agreement_analysis", "No producer/consumer agreement changes."),
    ):
        answer["design_facts"][name] = {
            "applicability": "not_applicable",
            "reason": reason,
        }
    answer["design_facts"]["reuse_analysis"] = {"candidates": []}
    answer["design_facts"]["impact_closure"] = dict(_NO_IMPACT)
    return answer


def _architect_schema() -> dict:
    return json.loads(_schema_for("nw-solution-architect"))


def test_architect_schema_refuses_the_recorded_prose_acceptance_supports() -> None:
    """The measured defect, refused at the boundary that costs nothing.

    Before this schema carried the locator grammar, the provider ACCEPTED this
    exact answer: 184 paid seconds bought an envelope the runner then refused
    post hoc as `DesignFactsMalformed`.  The grammar now lives in the schema
    the provider enforces, so the same answer cannot be returned at all.
    """
    answer = _recorded_architect_answer()
    supports = answer["design_facts"]["acceptance_supports"]
    assert len(supports) == 6
    assert supports[0].startswith("USER OBSERVATION: ")

    errors = list(
        jsonschema.Draft202012Validator(_architect_schema()).iter_errors(answer)
    )

    paths = {tuple(error.absolute_path) for error in errors}
    assert {
        ("design_facts", "acceptance_supports", index) for index in range(6)
    } <= paths
    assert (
        "design_facts",
    ) in paths  # Historical facts lack the new explicit decisions.


def test_architect_schema_admits_locator_shaped_design_facts() -> None:
    answer = _current_architect_answer()
    answer["design_facts"]["acceptance_supports"] = [
        "src/des/adapters/driven/codefact/graphify_code_fact_adapter.py",
        "tests/des/unit/adapters/driven/codefact/test_graphify_code_fact_adapter.py",
    ]

    jsonschema.Draft202012Validator(_architect_schema()).validate(answer)


@pytest.mark.parametrize(
    ("mutation", "expected_path"),
    [
        ({"targets": []}, ("design_facts", "targets")),
        ({"decisions": []}, ("design_facts", "decisions")),
        ({"decisions": ["a", ""]}, ("design_facts", "decisions", 1)),
        ({"oracle": "../escape.py"}, ("design_facts", "oracle")),
        ({"verification": []}, ("design_facts", "verification")),
        ({"verification": [[]]}, ("design_facts", "verification", 0)),
        ({"verification": [["uv", ""]]}, ("design_facts", "verification", 0, 1)),
        (
            {"acceptance_supports": ["src/a.py", "src/a.py"]},
            ("design_facts", "acceptance_supports"),
        ),
    ],
)
def test_architect_schema_refuses_each_shape_the_guard_used_to_catch_alone(
    mutation: dict, expected_path: tuple
) -> None:
    """Every clause the post-hoc guard owned that JSON Schema can express.

    The provider validates each of these -- measured 2026-09-05 against the
    installed launcher, which refuses a StructuredOutput call naming the exact
    failing clause -- so the model is corrected inside its own turn.
    """
    answer = _current_architect_answer()
    answer["design_facts"]["acceptance_supports"] = ["src/support.py"]
    answer["design_facts"].update(mutation)

    errors = list(
        jsonschema.Draft202012Validator(_architect_schema()).iter_errors(answer)
    )

    assert expected_path in {tuple(error.absolute_path) for error in errors}


def _recorded_product_owner_turn() -> dict:
    """Turn 01 of run 20260905T062139Z-38400, verbatim.

    The schema the provider actually enforced that day, and the envelope it
    admitted: `rejected`, carrying three ordered, independently shippable
    values and a diagnostic explaining the decomposition.  The runner read the
    outcome, discarded the graph in silence and refused the Request.
    """
    return json.loads(
        (
            Path(__file__).parent / "turn_01_product_owner_structured_output.json"
        ).read_text(encoding="utf-8")
    )


def _product_owner_schema(window: int | None = None) -> dict:
    return json.loads(_schema_for("nw-product-owner", max_product_values=window))


def test_product_owner_schema_refuses_the_recorded_contradictory_envelope() -> None:
    """The same bytes, against the schema this adapter now declares."""
    envelope = _recorded_product_owner_turn()["structured_output"]

    errors = list(
        jsonschema.Draft202012Validator(_product_owner_schema()).iter_errors(envelope)
    )

    assert [tuple(error.absolute_path) for error in errors] == [("values",)]
    assert errors[0].validator == "maxItems"


@pytest.mark.parametrize("outcome", ["rejected", "indeterminate"])
def test_no_non_accepting_product_owner_outcome_may_carry_a_value(outcome: str) -> None:
    envelope = _recorded_product_owner_turn()["structured_output"]
    envelope["outcome"] = outcome

    errors = list(
        jsonschema.Draft202012Validator(_product_owner_schema()).iter_errors(envelope)
    )

    assert [tuple(error.absolute_path) for error in errors] == [("values",)]


def test_product_owner_schema_admits_the_same_graph_when_the_outcome_agrees() -> None:
    """The coherent envelope the run 21 turn was one field away from."""
    envelope = _recorded_product_owner_turn()["structured_output"]
    envelope["outcome"] = "accepted"

    jsonschema.Draft202012Validator(_product_owner_schema()).validate(envelope)


def test_product_owner_schema_admits_the_coherent_refusal() -> None:
    envelope = {"outcome": "rejected", "diagnostic": "one value only", "values": []}

    jsonschema.Draft202012Validator(_product_owner_schema()).validate(envelope)


def test_a_first_classification_that_accepts_must_carry_a_value() -> None:
    """No preserved prefix exists yet, so an accepted empty answer says nothing."""
    envelope = {"outcome": "accepted", "diagnostic": "single", "values": []}

    errors = list(
        jsonschema.Draft202012Validator(_product_owner_schema()).iter_errors(envelope)
    )

    assert [error.validator for error in errors] == ["minItems"]


def test_a_non_accepting_product_owner_turn_must_explain_itself() -> None:
    envelope = {"outcome": "rejected", "diagnostic": "", "values": []}

    errors = list(
        jsonschema.Draft202012Validator(_product_owner_schema()).iter_errors(envelope)
    )

    assert [tuple(error.absolute_path) for error in errors] == [("diagnostic",)]


def test_a_correction_that_accepts_may_answer_the_empty_replacement() -> None:
    """The window is an upper bound: an empty suffix says the prefix covers it.

    The accepting half of the law is deliberately absent from the bounded
    schema.  Declaring it would refuse a legitimate correction and, at a
    zero-width window, would make the schema unsatisfiable outright.
    """
    envelope = {"outcome": "accepted", "diagnostic": "prefix covers it", "values": []}

    jsonschema.Draft202012Validator(_product_owner_schema(0)).validate(envelope)
    jsonschema.Draft202012Validator(_product_owner_schema(3)).validate(envelope)


def test_a_correction_that_refuses_still_carries_no_value() -> None:
    envelope = _recorded_product_owner_turn()["structured_output"]

    errors = list(
        jsonschema.Draft202012Validator(_product_owner_schema(3)).iter_errors(envelope)
    )

    assert [tuple(error.absolute_path) for error in errors] == [("values",)]


@pytest.mark.parametrize("outcome", ["rejected", "indeterminate"])
def test_architect_schema_refuses_facts_on_a_non_accepting_outcome(
    outcome: str,
) -> None:
    """The state the runner used to catch post hoc as `DesignFactsMalformed`."""
    answer = _current_architect_answer()
    answer["design_facts"]["acceptance_supports"] = ["src/support.py"]
    answer["outcome"] = outcome

    errors = list(
        jsonschema.Draft202012Validator(_architect_schema()).iter_errors(answer)
    )

    assert ("design_facts",) in {tuple(error.absolute_path) for error in errors}


def test_architect_schema_admits_the_coherent_refusal() -> None:
    answer = {
        "outcome": "rejected",
        "diagnostic": "no reuse seam",
        "design_facts": None,
    }

    jsonschema.Draft202012Validator(_architect_schema()).validate(answer)


def test_architect_schema_refuses_a_null_payload_on_an_accepted_outcome() -> None:
    answer = {"outcome": "accepted", "diagnostic": "", "design_facts": None}

    errors = list(
        jsonschema.Draft202012Validator(_architect_schema()).iter_errors(answer)
    )

    assert ("design_facts",) in {tuple(error.absolute_path) for error in errors}


@pytest.mark.parametrize("outcome", ["rejected", "indeterminate"])
def test_a_replayed_contradictory_envelope_is_indeterminate_not_a_refusal(
    outcome: str,
) -> None:
    """The same law, for an envelope that never met the provider's validator.

    A replayed or hand-written envelope reaches `extract_model_run` directly.
    Reading its outcome and discarding its payload is the silent-wrong the
    schema now prevents at the producer; here the contradiction is named.
    """
    envelope = _recorded_product_owner_turn()["structured_output"]
    envelope["outcome"] = outcome

    with pytest.raises(MalformedModelEnvelope) as refused:
        decode_model_run(
            json.loads(json.dumps({"structured_output": envelope}))[
                "structured_output"
            ],
            role_id="nw-product-owner",
        )

    assert "EnvelopeOutcomeContradictsPayload" in str(refused.value)
    assert f"a {outcome} turn carried 3 product values" in str(refused.value)


def test_a_coherent_refusal_still_reaches_the_runner_as_a_refusal() -> None:
    run = decode_model_run(
        json.loads(
            json.dumps(
                {
                    "structured_output": {
                        "outcome": "rejected",
                        "diagnostic": "one value only",
                        "values": [],
                    }
                }
            )
        )["structured_output"],
        role_id="nw-product-owner",
    )

    assert run.outcome is ModelOutcome.Rejected and run.product_values == ()


#: Every role the runner dispatches that carries NO payload, and therefore owns
#: no other half of the envelope law.  Their whole answer is an outcome and a
#: diagnostic, so an empty diagnostic leaves nothing at all.
#:
#: The two crafters LEFT this list on 2026-09-06: a refusing craft turn now owes
#: the closed `blocked_by` word that routes its finding, so it carries a payload
#: and owns the other half of the law like every other payload role.
#:
#: The whole-diff reviewer left it the same day, for the same shape of reason.
#: ADR-DES-003 §5 retires the pre-craft oracle judge, which makes this reviewer
#: the oracle's only independent judge, so a finding it charges to the oracle
#: has to reach the oracle's author rather than the crafter -- and that routing
#: is a closed `defect_owner` word, which is a payload.
_PAYLOAD_FREE_ROLES = (
    "nw-acceptance-designer",
    "nw-user-examiner",
)
#: The two roles that implement one ready ordered batch, under one schema.
_CRAFTERS = ("nw-software-crafter", "nw-functional-software-crafter")


def _role_schema(role_id: str) -> dict:
    return json.loads(_schema_for(role_id))


@pytest.mark.parametrize("role_id", _PAYLOAD_FREE_ROLES)
@pytest.mark.parametrize("outcome", ["rejected", "indeterminate"])
def test_a_payload_free_role_cannot_refuse_without_explaining(
    role_id: str, outcome: str
) -> None:
    """The residual the review reproduced: a refusal that says nothing.

    The diagnostic is the ONLY thing these roles can pass on -- it travels
    verbatim as the terminal's WHY and again as its DIAGNOSTIC line -- so an
    empty one produced a blank WHY and a HOW pointing at a finding that was
    never there.
    """
    envelope = {"outcome": outcome, "diagnostic": ""}

    errors = list(
        jsonschema.Draft202012Validator(_role_schema(role_id)).iter_errors(envelope)
    )

    assert [tuple(error.absolute_path) for error in errors] == [("diagnostic",)]
    assert errors[0].validator == "minLength"


@pytest.mark.parametrize("role_id", _PAYLOAD_FREE_ROLES)
def test_a_payload_free_role_that_explains_itself_is_admitted(role_id: str) -> None:
    """The discriminant: the same envelope, one non-empty field."""
    envelope = {"outcome": "rejected", "diagnostic": "the diff proves no observation"}

    jsonschema.Draft202012Validator(_role_schema(role_id)).validate(envelope)


@pytest.mark.parametrize("role_id", _PAYLOAD_FREE_ROLES)
def test_an_accepting_payload_free_turn_is_left_unconstrained(role_id: str) -> None:
    """An accepted turn's diagnostic carries nothing the runner passes on.

    So the schema states nothing about it, and the law is an `if`/`then` with no
    `else`.  Constraining a branch that has no defect to prevent would be
    ceremony (GDP-10).
    """
    jsonschema.Draft202012Validator(_role_schema(role_id)).validate(
        {"outcome": "accepted", "diagnostic": ""}
    )


@pytest.mark.parametrize(
    "schema",
    [
        _role_schema("nw-acceptance-designer"),
        _role_schema("nw-software-crafter"),
        _product_owner_schema(),
        _product_owner_schema(3),
        _architect_schema(),
    ],
    ids=["payload-free", "crafter", "product-owner", "correction", "architect"],
)
def test_no_role_may_refuse_without_explaining_itself(schema: dict) -> None:
    """One law, every role: the census has no row left without this clause."""
    envelope: dict[str, object] = {"outcome": "rejected", "diagnostic": ""}
    if "values" in schema["properties"]:
        envelope["values"] = []
    if "design_facts" in schema["properties"]:
        envelope["design_facts"] = None
    if "blocked_by" in schema["properties"]:
        envelope["blocked_by"] = "product"

    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(envelope))

    assert ("diagnostic",) in {tuple(error.absolute_path) for error in errors}


#: The three words a blocked craft turn may answer, in the runner's own order.
_BLOCKERS = [blocker.value for blocker in CraftBlocker]


def _crafter_stdout(**payload: object) -> str:
    return json.dumps({"structured_output": payload})


@pytest.mark.parametrize("role_id", _CRAFTERS)
def test_both_crafters_answer_under_one_blocked_by_schema(role_id: str) -> None:
    """They differ only in paradigm, so a second schema would be a second truth."""
    schema = _role_schema(role_id)

    assert schema["properties"]["blocked_by"]["enum"] == [*_BLOCKERS, None]
    assert schema["required"] == ["outcome", "diagnostic", "blocked_by"]


@pytest.mark.parametrize("outcome", ["rejected", "indeterminate"])
def test_a_craft_turn_that_delivers_nothing_cannot_leave_its_batch_unrouted(
    outcome: str,
) -> None:
    """Runs 31, 32b and 33: a craft refusal with no owner has no route home."""
    envelope = {
        "outcome": outcome,
        "diagnostic": "the oracle is broken",
        "blocked_by": None,
    }

    errors = list(
        jsonschema.Draft202012Validator(
            _role_schema("nw-software-crafter")
        ).iter_errors(envelope)
    )

    assert {tuple(error.absolute_path) for error in errors} == {("blocked_by",)}


@pytest.mark.parametrize("blocker", _BLOCKERS)
def test_each_declared_blocker_is_an_admissible_refusal(blocker: str) -> None:
    jsonschema.Draft202012Validator(_role_schema("nw-software-crafter")).validate(
        {"outcome": "rejected", "diagnostic": "a finding", "blocked_by": blocker}
    )


def test_a_delivered_batch_is_blocked_by_nothing() -> None:
    """The envelope law on this role's payload: the word belongs to a refusal."""
    errors = list(
        jsonschema.Draft202012Validator(
            _role_schema("nw-software-crafter")
        ).iter_errors({"outcome": "accepted", "diagnostic": "", "blocked_by": "oracle"})
    )

    assert [tuple(error.absolute_path) for error in errors] == [("blocked_by",)]


def test_a_replayed_craft_refusal_naming_no_blocker_is_indeterminate() -> None:
    """The envelope law, re-stated for the envelopes that never met the schema."""
    with pytest.raises(MalformedModelEnvelope, match="CraftBlockerMissing"):
        decode_model_run(
            json.loads(
                _crafter_stdout(
                    outcome="rejected", diagnostic="a finding", blocked_by=None
                )
            )["structured_output"],
            role_id="nw-software-crafter",
        )


def test_a_replayed_accepted_craft_turn_carrying_a_blocker_is_indeterminate() -> None:
    with pytest.raises(
        MalformedModelEnvelope, match="EnvelopeOutcomeContradictsPayload"
    ):
        decode_model_run(
            json.loads(
                _crafter_stdout(outcome="accepted", diagnostic="", blocked_by="oracle")
            )["structured_output"],
            role_id="nw-software-crafter",
        )


def test_a_blocked_craft_turn_reaches_the_runner_as_typed_data() -> None:
    run = decode_model_run(
        json.loads(
            _crafter_stdout(
                outcome="rejected",
                diagnostic="the oracle compares two absolute paths",
                blocked_by="oracle",
            )
        )["structured_output"],
        role_id="nw-functional-software-crafter",
    )

    assert run.craft_blocker is CraftBlocker.Oracle


def test_a_delivered_craft_turn_reaches_the_runner_with_no_blocker() -> None:
    run = decode_model_run(
        json.loads(_crafter_stdout(outcome="accepted", diagnostic="", blocked_by=None))[
            "structured_output"
        ],
        role_id="nw-software-crafter",
    )

    assert run.outcome is ModelOutcome.Accepted and run.craft_blocker is None


#: The two values one Request's aggregate review may charge a defect to.
_REVIEWED = ("value one", "value two")
_REVIEWER = "nw-acceptance-designer-reviewer"


def _reviewer_stdout(**payload: object) -> str:
    return json.dumps({"structured_output": payload})


@pytest.mark.parametrize("outcome", ["rejected", "indeterminate"])
def test_a_non_accepting_review_cannot_leave_its_finding_unowned(
    outcome: str,
) -> None:
    """Run 28c's residual, stated to the provider instead of tested after it.

    The runner routes the one correction window on this word.  A refusal that
    names no owner is the envelope that sent a design defect to the acceptance
    designer, who owns no target and could not repair it.
    """
    envelope = {
        "outcome": outcome,
        "diagnostic": "value two omits a target its obligation rewrites",
        "defect_owner": None,
        "defect_value": "value two",
    }

    errors = list(
        jsonschema.Draft202012Validator(
            _acceptance_reviewer_schema(_REVIEWED)
        ).iter_errors(envelope)
    )

    assert {tuple(error.absolute_path) for error in errors} == {("defect_owner",)}


def test_a_review_may_charge_a_set_level_defect_to_no_single_value() -> None:
    """A duplicate stimulus across two oracles belongs to no one value."""
    jsonschema.Draft202012Validator(_acceptance_reviewer_schema(_REVIEWED)).validate(
        {
            "outcome": "rejected",
            "diagnostic": "two oracles assert the same stimulus",
            "defect_owner": "oracle",
            "defect_value": None,
        }
    )


def test_a_review_cannot_charge_a_value_this_request_does_not_contain() -> None:
    errors = list(
        jsonschema.Draft202012Validator(
            _acceptance_reviewer_schema(_REVIEWED)
        ).iter_errors(
            {
                "outcome": "rejected",
                "diagnostic": "a defect",
                "defect_owner": "design",
                "defect_value": "value nine",
            }
        )
    )

    assert [tuple(error.absolute_path) for error in errors] == [("defect_value",)]


def test_an_approving_review_owns_no_defect() -> None:
    """The envelope law on this role's payload: an approval carries no owner."""
    errors = list(
        jsonschema.Draft202012Validator(
            _acceptance_reviewer_schema(_REVIEWED)
        ).iter_errors(
            {
                "outcome": "accepted",
                "diagnostic": "",
                "defect_owner": "oracle",
                "defect_value": None,
            }
        )
    )

    assert [tuple(error.absolute_path) for error in errors] == [("defect_owner",)]


def test_a_replayed_review_naming_no_owner_is_indeterminate_not_a_refusal() -> None:
    """The envelope law, re-stated for the envelopes that never met the schema."""
    with pytest.raises(MalformedModelEnvelope, match="ReviewDefectOwnerMissing"):
        decode_model_run(
            json.loads(
                _reviewer_stdout(
                    outcome="rejected",
                    diagnostic="a defect",
                    defect_owner=None,
                    defect_value=None,
                )
            )["structured_output"],
            role_id=_REVIEWER,
            defect_values=_REVIEWED,
        )


def test_a_replayed_review_charging_an_unknown_value_is_indeterminate() -> None:
    with pytest.raises(MalformedModelEnvelope, match="ReviewDefectValueUnknown"):
        decode_model_run(
            json.loads(
                _reviewer_stdout(
                    outcome="rejected",
                    diagnostic="a defect",
                    defect_owner="design",
                    defect_value="value nine",
                )
            )["structured_output"],
            role_id=_REVIEWER,
            defect_values=_REVIEWED,
        )


def test_a_replayed_approval_carrying_an_owner_is_indeterminate() -> None:
    with pytest.raises(
        MalformedModelEnvelope, match="EnvelopeOutcomeContradictsPayload"
    ):
        decode_model_run(
            json.loads(
                _reviewer_stdout(
                    outcome="accepted",
                    diagnostic="",
                    defect_owner="oracle",
                    defect_value=None,
                )
            )["structured_output"],
            role_id=_REVIEWER,
            defect_values=_REVIEWED,
        )


def test_an_owned_review_finding_reaches_the_runner_as_typed_data() -> None:
    run = decode_model_run(
        json.loads(
            _reviewer_stdout(
                outcome="rejected",
                diagnostic="value two omits a target",
                defect_owner="design",
                defect_value="value two",
            )
        )["structured_output"],
        role_id=_REVIEWER,
        defect_values=_REVIEWED,
    )

    assert run.review_defect is not None
    assert run.review_defect.owner is DefectOwner.Design
    assert run.review_defect.value == "value two"


def test_an_approving_review_reaches_the_runner_with_no_defect() -> None:
    run = decode_model_run(
        json.loads(
            _reviewer_stdout(
                outcome="accepted",
                diagnostic="",
                defect_owner=None,
                defect_value=None,
            )
        )["structured_output"],
        role_id=_REVIEWER,
        defect_values=_REVIEWED,
    )

    assert run.outcome is ModelOutcome.Accepted and run.review_defect is None


#: The measured incident, verbatim: run 20260906T005839Z-648259, turn 06.  The
#: Product Owner correction window answered this envelope, the runner persisted
#: it, and the architect, the acceptance designer and its reviewer were paid
#: before the designer refused the byte -- about $1.2 and 12 minutes for a
#: one-character value the schema in force admitted for free.
_PLACEHOLDER_TURN_06 = {
    "outcome": "accepted",
    "diagnostic": "test",
    "values": [{"observation": "a"}],
}
#: The SHORTEST observation an ACCEPTED Product Owner turn actually produced --
#: the population the floor constrains, since only an accepting turn carries
#: values.  289 characters, run 20260905T235922Z-583383, verbatim.  The floor
#: sits more than seven times below it.
_SHORTEST_REAL_OBSERVATION = (
    "With a graphify-out/ index directory present, readable and current, and the "
    "graphify stub executable present on PATH recording that it was invoked, the "
    "graphify trace entry still reports event: answered exactly as before this "
    "change, with provider/confidence/payload sourced from graphify."
)
#: The shortest real ACCEPTED diagnostic, same population, run
#: 20260906T014933Z-735633.  41 characters: a 40-character floor on this field
#: would have refused it by one byte, which is why no floor is declared there.
_SHORTEST_REAL_DIAGNOSTIC = "single-value-accepted-as-walking-skeleton"


@pytest.mark.parametrize("window", [None, 2])
def test_the_recorded_placeholder_turn_is_unrepresentable(window: int | None) -> None:
    """Both Product Owner calls refuse turn 06's value, on the one field that cost."""
    errors = list(
        jsonschema.Draft202012Validator(_product_owner_schema(window)).iter_errors(
            _PLACEHOLDER_TURN_06
        )
    )

    assert [tuple(error.absolute_path) for error in errors] == [
        ("values", 0, "observation")
    ]
    assert errors[0].validator == "minLength"


@pytest.mark.parametrize("window", [None, 2])
def test_the_shortest_real_accepted_diagnostic_is_admitted(window: int | None) -> None:
    """The falsifier of the floor the review removed.

    A 40-character floor on the accepting diagnostic would refuse this real
    answer by one byte.  The diagnostic keeps the one-character floor every
    role owes and nothing more.
    """
    envelope = {
        "outcome": "accepted",
        "diagnostic": _SHORTEST_REAL_DIAGNOSTIC,
        "values": [{"observation": _SHORTEST_REAL_OBSERVATION}],
    }

    jsonschema.Draft202012Validator(_product_owner_schema(window)).validate(envelope)


def test_a_measured_real_answer_stays_well_inside_the_floor() -> None:
    """The discriminant: the same shape, the shortest observation ever recorded."""
    envelope = {
        "outcome": "accepted",
        "diagnostic": "one value",
        "values": [{"observation": _SHORTEST_REAL_OBSERVATION}],
    }

    jsonschema.Draft202012Validator(_product_owner_schema()).validate(envelope)
    jsonschema.Draft202012Validator(_product_owner_schema(2)).validate(envelope)


@pytest.mark.parametrize("window", [None, 2])
def test_an_accepting_product_owner_turn_still_explains_itself(
    window: int | None,
) -> None:
    """The one character every role owes, on the branch that carries values.

    The floor on `observation` says nothing about the diagnostic, and an
    accepted turn used to be able to answer with an empty one on both calls.
    """
    envelope = {
        "outcome": "accepted",
        "diagnostic": "",
        "values": [{"observation": _SHORTEST_REAL_OBSERVATION}],
    }

    errors = list(
        jsonschema.Draft202012Validator(_product_owner_schema(window)).iter_errors(
            envelope
        )
    )

    assert [tuple(error.absolute_path) for error in errors] == [("diagnostic",)]
    assert errors[0].validator == "minLength"


def test_a_refusal_still_needs_only_one_character_of_explanation() -> None:
    """The floor is the ACCEPTING half of the law and says nothing elsewhere.

    A refusal carries no value, so it has no observation to measure, and its
    diagnostic keeps the floor every role owes: non-empty.
    """
    envelope = {"outcome": "rejected", "diagnostic": "no", "values": []}

    jsonschema.Draft202012Validator(_product_owner_schema()).validate(envelope)
    jsonschema.Draft202012Validator(_product_owner_schema(2)).validate(envelope)


def _extract_envelope(role_id: str, structured: dict) -> object:
    """One provider document through the real reader, for one role."""
    return decode_model_run(
        json.loads(json.dumps({"structured_output": structured}))["structured_output"],
        role_id=role_id,
    )


#: The two roles that name whose defect they found (ADR-DES-003 §5, §6).
_DEFECT_NAMING_ROLES = (
    "nw-acceptance-designer-reviewer",
    "nw-software-crafter-reviewer",
)


@pytest.mark.parametrize("role_id", _DEFECT_NAMING_ROLES)
def test_an_accepting_review_needs_no_ownership_word(role_id: str) -> None:
    """The word routes a FINDING, and an accepted review has none.

    The schema's own `else` branch already forces both fields to null on an
    accepting envelope, so exactly one value is admissible there and demanding
    that the producer spell it buys nothing -- precautionary ceremony (GDP-10).

    MEASURED: making the whole-diff reviewer a defect-naming role broke the k4
    replay corpus, whose recorded turn 06 is an ACCEPTED review from before the
    word existed. Requiring presence there refused a historically valid answer
    for a field that could only ever have been null.
    """
    run = _extract_envelope(
        role_id, {"outcome": "accepted", "diagnostic": "the candidate is sound"}
    )
    assert run.outcome is ModelOutcome.Accepted
    assert run.review_defect is None


@pytest.mark.parametrize("role_id", _DEFECT_NAMING_ROLES)
@pytest.mark.parametrize("outcome", ["rejected", "indeterminate"])
def test_a_refusing_review_without_the_word_is_still_refused(
    role_id: str, outcome: str
) -> None:
    """The guarantee that matters is untouched: a finding must name its owner.

    This is the half the routing depends on -- without it the step would have to
    guess which role can answer -- and it stays strict.
    """
    with pytest.raises(MalformedModelEnvelope):
        _extract_envelope(
            role_id, {"outcome": outcome, "diagnostic": "it does not hold"}
        )


def _accepted_architect_answer() -> dict:
    answer = _current_architect_answer()
    answer["design_facts"]["acceptance_supports"] = ["src/support.py"]
    return answer


def _accepted_design_facts_schema(schema: dict) -> dict:
    branch = next(
        branch
        for branch in schema["properties"]["answer"]["anyOf"]
        if branch["properties"]["outcome"]["const"] == "accepted"
    )
    return branch["properties"]["design_facts"]


def test_adr_and_architect_handoff_are_optional_in_base_and_nullable_only_in_codex() -> (
    None
):
    base = _architect_schema()["properties"]["design_facts"]
    codex = _accepted_design_facts_schema(codex_schema_for("nw-solution-architect"))

    optional_fields = {"adr", "architect_handoff"}
    for name in optional_fields:
        assert name in base["properties"] and name not in base["required"]
        assert {"type": "null"} not in base["properties"][name].get("anyOf", [])
        assert name in codex["required"]
        assert codex["properties"][name]["anyOf"].count({"type": "null"}) == 1
    for name in set(codex["properties"]) - optional_fields:
        declared = codex["properties"][name]
        assert {"type": "null"} not in declared.get("anyOf", [])
        assert declared.get("type") != "null"

    answer = _accepted_architect_answer()
    jsonschema.Draft202012Validator(_architect_schema()).validate(answer)
    nullable = {
        "outcome": answer["outcome"],
        "diagnostic": answer["diagnostic"],
        "design_facts": {
            **answer["design_facts"],
            "adr": None,
            "architect_handoff": None,
        },
    }
    jsonschema.Draft202012Validator(codex_schema_for("nw-solution-architect")).validate(
        {"answer": nullable}
    )


def test_a_null_adr_decodes_exactly_as_an_absent_adr() -> None:
    absent = _accepted_architect_answer()
    assert "adr" not in absent["design_facts"]
    null = json.loads(json.dumps(absent))
    null["design_facts"]["adr"] = None

    decoded_absent = _extract_envelope("nw-solution-architect", absent)
    decoded_null = _extract_envelope("nw-solution-architect", null)

    assert decoded_null.design_facts.adr is None
    assert decoded_null.design_facts == decoded_absent.design_facts


@pytest.mark.parametrize("missing", ["reuse_analysis", "impact_closure"])
def test_an_architect_answer_omitting_a_required_decision_is_malformed(
    missing: str,
) -> None:
    answer = _accepted_architect_answer()
    del answer["design_facts"][missing]

    with pytest.raises(MalformedModelEnvelope):
        _extract_envelope("nw-solution-architect", answer)


def test_an_impact_closure_leaving_a_declared_consumer_undisposed_is_malformed() -> (
    None
):
    answer = _accepted_architect_answer()
    facts = answer["design_facts"]
    facts["agreement_analysis"] = {
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
    }
    facts["impact_closure"] = {
        "applicability": "applicable",
        "items": [
            {
                "kind": "runtime",
                "locator": target["path"],
                "decision": "CHANGED",
                "reason": "The target changes.",
            }
            for target in facts["targets"]
        ],
    }

    with pytest.raises(MalformedModelEnvelope, match=r"bin/main\.ml:1"):
        _extract_envelope("nw-solution-architect", answer)


def test_the_schema_requires_both_decisions_and_bounds_impact_locators() -> None:
    facts = _architect_schema()["properties"]["design_facts"]
    assert {"reuse_analysis", "impact_closure"} <= set(facts["required"])

    applicable = next(
        branch
        for branch in facts["properties"]["impact_closure"]["anyOf"]
        if branch["properties"]["applicability"]["const"] == "applicable"
    )
    pattern = re.compile(
        applicable["properties"]["items"]["items"]["properties"]["locator"]["pattern"]
    )
    assert pattern.search("src/a.b") and pattern.search("src/a.b:7")
    assert not pattern.search("../x")
