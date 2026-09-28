"""Provider-neutral semantic model envelope.

Providers project this module's schemas into their own constrained grammar and
pass only a typed terminal object to :func:`decode_model_run`.  Provider stdout
is provenance/accounting, never semantic model output.
"""

from __future__ import annotations

import json
from typing import Any

from des.domain.architecture_brief_resolver import (
    DESIGN_ORACLE_LOCATOR_PATTERN,
    REPOSITORY_RELATIVE_WHOLE_FILE_PATTERN,
    is_design_oracle_locator,
    is_repository_relative_whole_file_locator,
)
from des.domain.design_authority_locator import (
    UNSAFE_LOCATOR_REFUSAL,
    is_design_authority_locator,
)
from des.domain.distill_document import DistillDocument, DistillDocumentInvalid
from des.ports.driven_ports.task_invocation_port import (
    MINIMUM_OBSERVATION_CHARACTERS,
    CraftBlocker,
    DefectOwner,
    DesignFacts,
    DesignTarget,
    ExpectationCharterAnswer,
    MalformedModelEnvelope,
    ModelAccounting,
    ModelOutcome,
    ModelRun,
    ProductValue,
    ReviewDefect,
)


#: The one semantic task this decoder branches on for the shared Product Owner
#: role, distinct from the ordinary decomposition/correction envelope.
_EXPECTATION_CHARTER_TASK = "expectation-charter"


_PRODUCT_OWNER = "nw-product-owner"
_SOLUTION_ARCHITECT = "nw-solution-architect"
_ACCEPTANCE_DESIGNER = "nw-acceptance-designer"
_ACCEPTANCE_REVIEWER = "nw-acceptance-designer-reviewer"

#: The whole-diff reviewer owes the same ownership word. ADR-DES-003 §5 retires
#: the pre-craft oracle judge, so this role is now the ONLY independent judge of
#: the oracle -- it sees oracle and implementation together, which §4a item 4
#: already made its job -- and §6 hands it the measured radius so it can say
#: whether the oracle covers the surfaces the candidate touched. A finding of
#: that shape belongs to the ORACLE, not to the crafter, and without the word
#: the step would have to guess which role can answer it.
_WHOLE_DIFF_REVIEWER = "nw-software-crafter-reviewer"

#: The two roles that name whose defect they found.
_DEFECT_NAMING = frozenset({_ACCEPTANCE_REVIEWER, _WHOLE_DIFF_REVIEWER})
#: The two roles that implement one ready ordered batch.  They differ only
#: in paradigm, so they answer under ONE schema and are named together
#: everywhere the envelope law is stated.
_CRAFTERS = frozenset({"nw-software-crafter", "nw-functional-software-crafter"})


def _base_role_id(role_id: str) -> str:
    """Return the published role identity behind an optional competence key.

    ``role#competence`` selects a configured runtime.  It does not create a
    second specialist or a second semantic envelope.  The provider adapters
    must therefore use the base role for every role-shaped schema and decoder
    decision, while the qualified id remains available to the runtime and turn
    record.
    """
    return role_id.partition("#")[0]


def is_crafter_role(role_id: str) -> bool:
    """Whether this role owns one implementation batch.

    This is the one role classification shared by the semantic envelope and
    native producer capture.  A recorder must never grow a second, drifting
    spelling of the crafter set.
    """
    return _base_role_id(role_id) in _CRAFTERS


_ACCEPTING: dict[str, Any] = {
    "properties": {"outcome": {"type": "string", "const": ModelOutcome.Accepted.value}},
    "required": ["outcome"],
}
_NOT_ACCEPTING: dict[str, Any] = {
    "properties": {
        "outcome": {
            "enum": [
                ModelOutcome.Rejected.value,
                ModelOutcome.Indeterminate.value,
            ]
        }
    },
    "required": ["outcome"],
}
#: One spelling of "this turn actually said something", used by every role.
_NON_EMPTY_DIAGNOSTIC: dict[str, Any] = {"type": "string", "minLength": 1}
#: The half of the envelope law that EVERY role owes, payload or not: a turn
#: that does not accept must say why.  Its `diagnostic` is the ONLY thing the
#: runner can pass on -- it travels verbatim as the terminal's WHY and again as
#: its DIAGNOSTIC line -- so an empty one produces a refusal that explains
#: nothing and a HOW pointing at a finding that is not there.  Reproduced
#: 2026-09-05 in review: `WHY:` blank, `DIAGNOSTIC: ""`, and a HOW naming a
#: nonexistent finding.  The six roles that carry no payload own no other half
#: of the law, which is exactly why this one had to reach them.
_MUST_EXPLAIN_ITSELF: dict[str, Any] = {
    "properties": {"diagnostic": _NON_EMPTY_DIAGNOSTIC}
}
_OUTCOME_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "outcome": {
            "type": "string",
            "enum": [outcome.value for outcome in ModelOutcome],
        },
        "diagnostic": {"type": "string"},
    },
    "required": ["outcome", "diagnostic"],
    "additionalProperties": False,
    # An `if`/`then` with no `else`: the accepting branch of a payload-free role
    # is unconstrained, so there is nothing to state there and stating something
    # anyway would be ceremony.  Measured 2026-09-05, this exact shape: asked to
    # answer `rejected` with an empty diagnostic, the provider refused the
    # StructuredOutput call with `is_error: true` and "must NOT have fewer than
    # 1 characters (got 0), root: must match the 'then' schema".  A model that
    # insists on the forbidden shape ends the turn with no structured output at
    # all, which the runner already reports as indeterminate -- an honest
    # non-answer where a lying refusal used to be admitted.
    "if": _NOT_ACCEPTING,
    "then": _MUST_EXPLAIN_ITSELF,
}
#: What an ACCEPTED Product Owner turn owes on the payload side, stated to the
#: provider instead of discovered after four paid turns.  Measured 2026-09-06,
#: run 20260906T005839Z-648259 turn 06: the correction window answered
#: `{"outcome":"accepted","diagnostic":"test","values":[{"observation":"a"}]}`,
#: the runner persisted the single character, and the architect, the acceptance
#: designer, its reviewer and a second designer were paid -- about $1.2 and
#: twelve minutes -- before the designer refused "the observation field is the
#: literal placeholder string 'a'".  The schema in force that day declared only
#: `type: string`, so "a" was a VALID answer and nothing inside the turn could
#: correct it.  With the floor declared, the same answer is refused inside the
#: model's own turn: the provider returns `is_error` and retries, exactly as it
#: does for `pattern`, `minItems` and `maxItems` (all three measured on this
#: boundary), so a placeholder never becomes a persisted value (GDP-0, GDP-1,
#: GDP-5).  The number is measured on accepted turns -- the shortest real one
#: states 289 characters -- and lives in the port with its evidence.
#:
#: The turn's `diagnostic` is NOT constrained beyond the one character every
#: role owes.  It was, briefly, and the review measured why that was wrong: the
#: shortest real accepted diagnostic is 41 characters, so the same floor there
#: would have refused a real answer by one byte.  The observation is the byte
#: the incident cost money on, and it is the only one this states.
_SUBSTANTIVE_OBSERVATION: dict[str, Any] = {
    "type": "string",
    "minLength": MINIMUM_OBSERVATION_CHARACTERS,
}

#: THE ENVELOPE'S OWN COHERENCE, stated to the provider rather than tested
#: after the paid turn.  An outcome and the payload that outcome licenses are
#: two halves of ONE semantic answer, so an envelope carrying a refusal AND a
#: full payload is not a defensible answer the runner must interpret -- it is a
#: state the producer must be unable to build (GDP-0).  The decision stays the
#: model's; only its FORM is constrained (`boundary:software-measures-model-
#: decides`).
#:
#: The boundary admits exactly one shape for that law.  Measured 2026-09-05
#: against the installed launcher: a schema carrying `allOf` (and by the same
#: message `anyOf` or `oneOf`) at the top level is refused by the API before any
#: model turn exists -- HTTP 400, "input_schema does not support oneOf, allOf,
#: or anyOf at the top level" -- while a top-level `if`/`then`/`else` is
#: accepted AND enforced: asked in one turn for `rejected` with three values,
#: the provider answered the StructuredOutput call with `is_error: true` and
#: "Output does not match required schema: /values: must NOT have more than 0
#: items (got 3), root: must match the 'else' schema", and the same model
#: then returned `rejected` with an empty list.  The identical prompt and schema
#: MINUS the conditional returned `rejected` with three values, which is the
#: discriminant: the conditional, not the model's mood, produces the coherence.
_PRODUCT_VALUES: dict[str, Any] = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "observation": _SUBSTANTIVE_OBSERVATION,
        },
        "required": ["observation"],
        "additionalProperties": False,
    },
}
#: What a non-accepting Product Owner turn is: the refusal IS the answer, so it
#: carries no value and its `diagnostic` is the only thing the runner can pass
#: on -- an empty one would make the terminal explain nothing.
_NO_PRODUCT_VALUES: dict[str, Any] = {
    "properties": {
        "values": {"type": "array", "maxItems": 0},
        "diagnostic": _NON_EMPTY_DIAGNOSTIC,
    }
}


def _product_owner_schema(window: int | None = None) -> dict[str, Any]:
    """The Product Owner schema for a first classification or a correction.

    ``window`` is the inclusive upper bound on the replacement suffix for ONE
    correction call, or ``None`` for the unbounded first classification.  It
    belongs to the transition, not to the role, which is why it is a parameter
    and not part of the role-static constant.

    The two calls do not share the accepting half of the law.  A FIRST
    classification that accepts must decompose into at least one value: no
    preserved prefix exists to fall back on, so an accepted empty answer would
    say nothing at all.  A CORRECTION that accepts may legitimately answer the
    empty suffix -- the statement that the already-prepared prefix covers the
    whole Request -- so no lower bound is declared there and declaring one would
    make the schema unsatisfiable for a zero-width window.  The non-accepting
    half is the same in both: a refusal carries no values.

    ``maxItems`` WAS believed to be advisory.  It is not.  Probe, 2026-09-05,
    reproducible in one command and reproduced independently in review: a schema
    whose only constraint is ``maxItems: 2``, asked for five items, is refused
    with ``is_error: true`` and ``must NOT have more than 2 items (got 5)``,
    exactly as ``pattern`` and ``minItems`` are.  :func:`extract_model_run`
    keeps refusing an over-window answer anyway, because the window is a fact
    about the TRANSITION and a replayed or hand-written envelope reaches that
    function without ever having passed the provider's validator.
    """
    schema: dict[str, Any] = {
        **_OUTCOME_SCHEMA,
        "properties": {
            **_OUTCOME_SCHEMA["properties"],
            "values": (
                _PRODUCT_VALUES
                if window is None
                else {**_PRODUCT_VALUES, "maxItems": window}
            ),
        },
        "required": ["outcome", "diagnostic", "values"],
    }
    # The accepting branch owes the one character every role owes: `values`
    # carries the observation, and the diagnostic is what a turn says about the
    # decomposition it just made.  Nothing above the floor is asked of it -- the
    # shortest real accepted diagnostic is 41 characters, so a wider floor here
    # would refuse a real answer.
    if window is None:
        schema["if"] = _ACCEPTING
        schema["then"] = {
            "properties": {
                "values": {"type": "array", "minItems": 1},
                "diagnostic": _NON_EMPTY_DIAGNOSTIC,
            }
        }
        schema["else"] = _NO_PRODUCT_VALUES
    else:
        schema["if"] = _NOT_ACCEPTING
        schema["then"] = _NO_PRODUCT_VALUES
        schema["else"] = _MUST_EXPLAIN_ITSELF
    return schema


_PRODUCT_OWNER_SCHEMA: dict[str, Any] = _product_owner_schema()
#: A repository-relative whole-file locator, in the ONE grammar
#: :mod:`des.domain.architecture_brief_resolver` owns.  The provider validates
#: ``pattern`` at the StructuredOutput boundary and refuses a non-matching
#: call, so a field declared with this shape cannot be answered with prose:
#: the model is corrected inside its own turn instead of after it.
_LOCATOR_STRING: dict[str, Any] = {
    "type": "string",
    "pattern": REPOSITORY_RELATIVE_WHOLE_FILE_PATTERN,
}
_NON_EMPTY_STRING: dict[str, Any] = {"type": "string", "minLength": 1}
_SOLUTION_ARCHITECT_SCHEMA: dict[str, Any] = {
    **_OUTCOME_SCHEMA,
    "properties": {
        **_OUTCOME_SCHEMA["properties"],
        "design_facts": {
            "type": ["object", "null"],
            "properties": {
                "targets": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": _LOCATOR_STRING,
                            "decision": {
                                "type": "string",
                                "enum": ["EXTEND", "CREATE_NEW"],
                            },
                        },
                        "required": ["path", "decision"],
                        "additionalProperties": False,
                    },
                },
                "paradigm": {
                    "type": "string",
                    "enum": ["object_oriented", "functional"],
                },
                "decisions": {
                    "type": "array",
                    "minItems": 1,
                    "items": _NON_EMPTY_STRING,
                },
                "oracle": {"type": "string", "pattern": DESIGN_ORACLE_LOCATOR_PATTERN},
                # No lower bound: a slice whose oracle needs no test dependency
                # declares an EMPTY support list, which the guard admits too.
                "acceptance_supports": {
                    "type": "array",
                    "items": _LOCATOR_STRING,
                    "uniqueItems": True,
                },
                "verification": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "array",
                        "minItems": 1,
                        "items": _NON_EMPTY_STRING,
                    },
                },
                "oracle_verification_index": {"type": "integer", "minimum": 0},
                # A provider that returns typed facts must carry the field even
                # when no configured DESIGN-document constructor assigned a
                # section identity.  The constructor, never the provider,
                # later replaces the empty value with its configured locator.
                "authority_locator": {"type": "string"},
            },
            "required": [
                "targets",
                "paradigm",
                "decisions",
                "oracle",
                "acceptance_supports",
                "verification",
                "oracle_verification_index",
                "authority_locator",
            ],
            "additionalProperties": False,
        },
    },
    "required": ["outcome", "diagnostic", "design_facts"],
    # The same envelope law, on this role's payload.  `design_facts` is declared
    # `["object", "null"]` because BOTH are legitimate answers -- but not for the
    # same outcome.  Narrowing the union per branch is what makes "nonaccepting
    # DESIGN supplied facts" unrepresentable at the producer instead of caught
    # after the paid turn.
    "if": _ACCEPTING,
    "then": {"properties": {"design_facts": {"type": "object"}}},
    "else": {
        "properties": {
            "design_facts": {"type": "null"},
            "diagnostic": _NON_EMPTY_DIAGNOSTIC,
        }
    },
}


#: The charter Product Owner turn's closed qualitative payload. It never
#: carries `values`: this is not a decomposition, it is one value's charter.
_CHARTER_FACTS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent": _NON_EMPTY_STRING,
        "exploration": _NON_EMPTY_STRING,
        "positive_observations": {
            "type": "array",
            "minItems": 1,
            "items": _NON_EMPTY_STRING,
        },
        "negative_observation": _NON_EMPTY_STRING,
    },
    "required": [
        "intent",
        "exploration",
        "positive_observations",
        "negative_observation",
    ],
    "additionalProperties": False,
}
_EXPECTATION_CHARTER_SCHEMA: dict[str, Any] = {
    **_OUTCOME_SCHEMA,
    "properties": {
        **_OUTCOME_SCHEMA["properties"],
        "charter": {**_CHARTER_FACTS_SCHEMA, "type": ["object", "null"]},
    },
    "required": ["outcome", "diagnostic", "charter"],
    "if": _ACCEPTING,
    "then": {
        "properties": {
            "diagnostic": _NON_EMPTY_DIAGNOSTIC,
            "charter": _CHARTER_FACTS_SCHEMA,
        }
    },
    "else": {
        "properties": {
            "diagnostic": _NON_EMPTY_DIAGNOSTIC,
            "charter": {"type": "null"},
        }
    },
}


def _defect_owners_for(role_id: str) -> list[str]:
    role_id = _base_role_id(role_id)
    owners = [DefectOwner.Oracle.value, DefectOwner.Design.value]
    if role_id == _WHOLE_DIFF_REVIEWER:
        owners.append(DefectOwner.Implementation.value)
    return owners


def _acceptance_reviewer_schema(
    defect_values: tuple[str, ...] = (),
    *,
    role_id: str = _ACCEPTANCE_REVIEWER,
) -> dict[str, Any]:
    """Constrain findings to this reviewer's scope and this Request's values.

    Acceptance review can identify oracle or design defects. Whole-candidate
    review can also identify implementation defects; forcing such a finding
    into the design category requests rework from the wrong owner.

    The model names the owner. The schema and decoder preserve that fact; they
    do not choose a correction route. A null value represents a set-level
    finding, while an accepted result cannot carry a defect.
    """
    owners = _defect_owners_for(role_id)
    owner: dict[str, Any] = {
        "type": ["string", "null"],
        "enum": [*owners, None],
    }
    value: dict[str, Any] = {
        "type": ["string", "null"],
        "enum": [*defect_values, None],
    }
    return {
        **_OUTCOME_SCHEMA,
        "properties": {
            **_OUTCOME_SCHEMA["properties"],
            "defect_owner": owner,
            "defect_value": value,
        },
        "required": ["outcome", "diagnostic", "defect_owner", "defect_value"],
        # The same envelope law every payload role owes, on this role's payload:
        # an ownership word belongs to a refusal and to nothing else, so an
        # approval carrying one is a state the producer cannot build.
        "if": _NOT_ACCEPTING,
        "then": {
            "properties": {
                "diagnostic": _NON_EMPTY_DIAGNOSTIC,
                "defect_owner": {"type": "string", "enum": owners},
            }
        },
        "else": {
            "properties": {
                "defect_owner": {"type": "null"},
                "defect_value": {"type": "null"},
            }
        },
    }


_CRAFT_BLOCKERS = [blocker.value for blocker in CraftBlocker]

#: What a crafter that could NOT drive its batch green owes, in a word the
#: provider imposes.
#:
#: MEASURED THREE TIMES: runs 31 (`20260906T014933Z-735633`, turn 08), 32b
#: (`20260906T032332Z-921671`, turn 04) and 33 (`20260906T032944Z-924463`,
#: turns 05-06).  Each crafter implemented its batch, ran the declared oracle,
#: found a case still red for a defect of the ORACLE ITSELF -- absolute paths
#: compared across two temporary roots, the wrong fallback provider, the
#: `file:offset` site format of the text-search adapter -- and refused
#: honestly, «cannot be driven green without editing the oracle, which is
#: immutable».  The runner had exactly one answer for every craft refusal, so
#: the finding died in a terminal whose resume returns to the same crafter over
#: the same oracle, and the only way out was a NEW Request: Product Owner,
#: architect and acceptance designer paid again.  Three runs and roughly $8 on
#: findings one $0.3 designer turn answers.
#:
#: The MODEL decides who is blocking it; the SOFTWARE only routes on the word
#: (`boundary:software-measures-model-decides`).  Reading that owner off the
#: finding's prose is forbidden -- diagnostics are diagnostic only -- so it is
#: a field the provider validates against a closed enum and it reaches the
#: runner in the typed payload (GDP-0).
#:
#: The word belongs to a refusal and to nothing else, so an accepted turn
#: carrying one is a state the producer cannot build.  That is the same
#: envelope law every payload role owes, and it is stated with the one
#: conditional this boundary accepts: a top-level `if`/`then`/`else`.
_CRAFTER_SCHEMA: dict[str, Any] = {
    **_OUTCOME_SCHEMA,
    "properties": {
        **_OUTCOME_SCHEMA["properties"],
        "blocked_by": {"type": ["string", "null"], "enum": [*_CRAFT_BLOCKERS, None]},
    },
    "required": ["outcome", "diagnostic", "blocked_by"],
    "if": _NOT_ACCEPTING,
    "then": {
        "properties": {
            "diagnostic": _NON_EMPTY_DIAGNOSTIC,
            "blocked_by": {"type": "string", "enum": _CRAFT_BLOCKERS},
        }
    },
    "else": {"properties": {"blocked_by": {"type": "null"}}},
}


# The recovery turn does not author code or choose a route.  Its accepted
# payload is exactly the public v2 DISTILL grammar, so the caller can preserve
# its canonical bytes and submit them to the existing constructor unchanged.
_DISTILL_VALUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "observation": _NON_EMPTY_STRING,
        "acceptance_obligations": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "id": _NON_EMPTY_STRING,
                    "stimulus": _NON_EMPTY_STRING,
                    "expected": _NON_EMPTY_STRING,
                },
                "required": ["id", "stimulus", "expected"],
                "additionalProperties": False,
            },
        },
        "oracle": {"type": "string", "pattern": DESIGN_ORACLE_LOCATOR_PATTERN},
        "acceptance_supports": {
            "type": "array",
            "items": _LOCATOR_STRING,
            "uniqueItems": True,
        },
        "verification": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "array",
                "minItems": 1,
                "items": _NON_EMPTY_STRING,
            },
        },
        "oracle_verification_index": {"type": "integer", "minimum": 0},
    },
    "required": [
        "observation",
        "acceptance_obligations",
        "oracle",
        "acceptance_supports",
        "verification",
        "oracle_verification_index",
    ],
    "additionalProperties": False,
}
_DISTILL_DOCUMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "schema_version": {"type": "integer", "const": 2},
        "values": {"type": "array", "minItems": 1, "items": _DISTILL_VALUE_SCHEMA},
    },
    "required": ["schema_version", "values"],
    "additionalProperties": False,
}
_ACCEPTANCE_DESIGNER_SCHEMA: dict[str, Any] = {
    **_OUTCOME_SCHEMA,
    "properties": {
        **_OUTCOME_SCHEMA["properties"],
        "distill_document": {**_DISTILL_DOCUMENT_SCHEMA, "type": ["object", "null"]},
    },
    "required": ["outcome", "diagnostic", "distill_document"],
    "if": _ACCEPTING,
    "then": {
        "properties": {
            "diagnostic": _NON_EMPTY_DIAGNOSTIC,
            "distill_document": _DISTILL_DOCUMENT_SCHEMA,
        }
    },
    "else": {
        "properties": {
            "diagnostic": _NON_EMPTY_DIAGNOSTIC,
            "distill_document": {"type": "null"},
        }
    },
}


_ROLE_SCHEMAS = {
    _PRODUCT_OWNER: _PRODUCT_OWNER_SCHEMA,
    _SOLUTION_ARCHITECT: _SOLUTION_ARCHITECT_SCHEMA,
    _ACCEPTANCE_REVIEWER: _acceptance_reviewer_schema(),
    _WHOLE_DIFF_REVIEWER: _acceptance_reviewer_schema(),
    **dict.fromkeys(_CRAFTERS, _CRAFTER_SCHEMA),
}


def _schema_for(
    role_id: str,
    max_product_values: int | None = None,
    defect_values: tuple[str, ...] = (),
    semantic_task: str | None = None,
) -> str:
    role_id = _base_role_id(role_id)
    if role_id == _PRODUCT_OWNER and semantic_task == _EXPECTATION_CHARTER_TASK:
        return json.dumps(_EXPECTATION_CHARTER_SCHEMA, separators=(",", ":"))
    if role_id == _PRODUCT_OWNER and max_product_values is not None:
        return json.dumps(
            _product_owner_schema(max_product_values), separators=(",", ":")
        )
    if role_id in _DEFECT_NAMING:
        return json.dumps(
            _acceptance_reviewer_schema(defect_values, role_id=role_id),
            separators=(",", ":"),
        )
    schema = (
        _ACCEPTANCE_DESIGNER_SCHEMA
        if role_id == _ACCEPTANCE_DESIGNER
        and semantic_task == "selected-revision-recovery"
        else _ROLE_SCHEMAS.get(role_id, _OUTCOME_SCHEMA)
    )
    return json.dumps(
        schema,
        separators=(",", ":"),
    )


# Five of these six arguments are the CALL's own facts, not this decoder's
# choices.  `role_id`, `max_product_values`, `defect_values` and `semantic_task`
# are TaskInvocationPort.invoke's per-call declarations, re-stated here so an
# envelope that never met the provider's validator is judged against the same
# law it declared; `accounting` is the provenance its caller already unwrapped.
# Narrowing this signature therefore means grouping them AT `invoke`, which is
# the DESIGN change the port's own note declines (18 definitions, ~51 call
# sites) -- and a record built only inside this module's two callers would add an
# abstraction nothing else reads. Suppressed per FUNCTION, so a new over-wide function
# in this module is still caught.
def decode_model_run(  # noqa: PLR0913 - see the note above
    structured: dict[str, Any],
    *,
    role_id: str = "",
    max_product_values: int | None = None,
    defect_values: tuple[str, ...] = (),
    semantic_task: str | None = None,
    accounting: ModelAccounting | None = None,
) -> ModelRun:
    """Validate one already-unwrapped terminal structured-output object.

    The provider owns unwrapping.  This decoder owns the semantic envelope law,
    including cross-field checks a replayed or hand-written answer did not pass
    at the provider boundary.
    """
    semantic_role_id = _base_role_id(role_id)
    charter_task = (
        semantic_role_id == _PRODUCT_OWNER
        and semantic_task == _EXPECTATION_CHARTER_TASK
    )
    expected = {"outcome", "diagnostic"}
    if semantic_role_id == _PRODUCT_OWNER and not charter_task:
        expected.add("values")
    if charter_task:
        expected.add("charter")
    if semantic_role_id == _SOLUTION_ARCHITECT:
        expected.add("design_facts")
    recovery_task = (
        semantic_role_id == _ACCEPTANCE_DESIGNER
        and semantic_task == "selected-revision-recovery"
    )
    if recovery_task:
        expected.add("distill_document")
    if is_crafter_role(semantic_role_id):
        expected.add("blocked_by")
    # The ownership word routes a FINDING, so it is owed on a refusal and on
    # nothing else. The schema's own `else` branch already forces both fields to
    # null on an accepting envelope, so exactly one value is admissible there
    # and demanding the producer spell it buys nothing -- precautionary
    # ceremony (GDP-10). MEASURED 2026-09-06: making the whole-diff reviewer a
    # defect-naming role refused the k4 replay corpus's recorded turn 06, an
    # ACCEPTED review from before the word existed, for a field that could only
    # ever have been null. The half the routing depends on stays strict below.
    optional = (
        {"defect_owner", "defect_value"}
        if semantic_role_id in _DEFECT_NAMING
        else set()
    )
    if not set(structured) <= expected | optional or not expected <= set(structured):
        raise MalformedModelEnvelope(
            "ModelOutcomeMalformed: structured output has unexpected fields"
        )
    try:
        outcome = ModelOutcome(structured["outcome"])
    except (TypeError, ValueError):
        raise MalformedModelEnvelope("ModelOutcomeUnknown") from None
    diagnostic = structured["diagnostic"]
    if not isinstance(diagnostic, str):
        raise MalformedModelEnvelope(
            "ModelOutcomeMalformed: diagnostic must be a string"
        )
    values: tuple[ProductValue, ...] = ()
    if semantic_role_id == _PRODUCT_OWNER and not charter_task:
        raw_values = structured["values"]
        if not isinstance(raw_values, list):
            raise MalformedModelEnvelope("ProductValuesMalformed")
        extracted: list[ProductValue] = []
        for item in raw_values:
            if (
                not isinstance(item, dict)
                or set(item) != {"observation"}
                or not isinstance(item["observation"], str)
            ):
                raise MalformedModelEnvelope("ProductValuesMalformed")
            extracted.append(ProductValue(item["observation"]))
        # The provider does enforce the declared window (measured 2026-09-05);
        # the envelope law re-states it here because an envelope can also reach
        # this function without having passed that validator.  A provider that
        # answers outside its own window established no semantic result: that is
        # indeterminate, never a delivery refusal charged to the product.  The
        # window bounds the answer from above only: an empty answer is the
        # in-window statement that the preserved prefix already covers the
        # Request, and its consumer decides whether a prefix exists to close on.
        if max_product_values is not None and len(extracted) > max_product_values:
            raise MalformedModelEnvelope(
                f"ProductValuesOutsideWindow: the turn returned {len(extracted)} "
                f"values for a declared replacement window of {max_product_values}"
            )
        # The envelope law, re-stated here for the same reason the window is: an
        # envelope reaches this function without having passed the provider's
        # validator whenever it is replayed or hand-written.  A refusal carrying
        # a full decomposition establishes no semantic result -- the outcome says
        # one thing and the payload the other -- so it is indeterminate, never a
        # delivery refusal charged to the product.  Measured 2026-09-05, run
        # 20260905T062139Z-38400 turn 01: `rejected` with three ordered values,
        # whose whole graph the runner then discarded in silence.
        if outcome is not ModelOutcome.Accepted and extracted:
            raise MalformedModelEnvelope(
                f"EnvelopeOutcomeContradictsPayload: a {outcome.value} turn "
                f"carried {len(extracted)} product values; a non-accepting "
                "outcome carries none"
            )
        values = tuple(extracted)
    design_facts: DesignFacts | None = None
    if semantic_role_id == _SOLUTION_ARCHITECT:
        raw_facts = structured["design_facts"]
        if raw_facts is not None:
            try:
                supports = raw_facts["acceptance_supports"]
                # Codex strict output does not admit JSON Schema's
                # `uniqueItems`; its transport projection therefore omits the
                # keyword. The semantic collection is still a set by contract,
                # so enforce its uniqueness before constructing a ModelRun for
                # every provider and every replayed envelope. Do not
                # canonicalize duplicates away: their presence is invalid data.
                if (
                    not isinstance(supports, list)
                    or not all(isinstance(path, str) for path in supports)
                    or len(supports) != len(set(supports))
                ):
                    raise MalformedModelEnvelope(
                        "DesignFactsDuplicateAcceptanceSupport"
                    )
                raw_targets = raw_facts["targets"]
                oracle = raw_facts["oracle"]
                authority_locator = raw_facts["authority_locator"]
                if (
                    not isinstance(raw_targets, list)
                    or not all(
                        isinstance(item, dict) and isinstance(item.get("path"), str)
                        for item in raw_targets
                    )
                    or not isinstance(oracle, str)
                    or not isinstance(authority_locator, str)
                ):
                    raise MalformedModelEnvelope("DesignFactsMalformed")
                if (
                    not is_design_oracle_locator(oracle)
                    or not all(
                        is_repository_relative_whole_file_locator(item["path"])
                        for item in raw_targets
                    )
                    or not all(
                        is_repository_relative_whole_file_locator(path)
                        for path in supports
                    )
                    or not is_design_authority_locator(authority_locator)
                ):
                    # The provider schema carries the same grammar, but replayed
                    # and hand-written envelopes reach this shared decoder too.
                    # Keep traversal/prose locators from becoming DesignFacts
                    # after a provider-specific transport projection.
                    #
                    # The `<document>#<heading>` clauses are NOT spelled here:
                    # they are `des.domain.design_authority_locator`'s ordered
                    # table, which also publishes the statement the architect
                    # reads while authoring the field -- the rule that refuses a
                    # turn and the rule it was taught are one object.
                    raise MalformedModelEnvelope(UNSAFE_LOCATOR_REFUSAL)
                targets = tuple(
                    DesignTarget(item["path"], item["decision"]) for item in raw_targets
                )
                verification = tuple(tuple(argv) for argv in raw_facts["verification"])
                oracle_verification_index = raw_facts["oracle_verification_index"]
                if (
                    not isinstance(oracle_verification_index, int)
                    or isinstance(oracle_verification_index, bool)
                    or oracle_verification_index < 0
                    or oracle_verification_index >= len(verification)
                ):
                    raise MalformedModelEnvelope("OracleVerificationIndexInvalid")
                design_facts = DesignFacts(
                    targets,
                    raw_facts["paradigm"],
                    tuple(raw_facts["decisions"]),
                    oracle,
                    tuple(supports),
                    verification,
                    oracle_verification_index,
                    authority_locator=authority_locator,
                )
            except (KeyError, TypeError):
                raise MalformedModelEnvelope("DesignFactsMalformed") from None
    charter: ExpectationCharterAnswer | None = None
    if charter_task:
        raw_charter = structured["charter"]
        if outcome is ModelOutcome.Accepted:
            required_keys = {
                "intent",
                "exploration",
                "positive_observations",
                "negative_observation",
            }
            if not isinstance(raw_charter, dict) or set(raw_charter) != required_keys:
                raise MalformedModelEnvelope("CharterFactsMalformed")
            intent = raw_charter["intent"]
            exploration = raw_charter["exploration"]
            positives = raw_charter["positive_observations"]
            negative = raw_charter["negative_observation"]
            if (
                not isinstance(intent, str)
                or not intent.strip()
                or not isinstance(exploration, str)
                or not exploration.strip()
                or not isinstance(positives, list)
                or not positives
                or not all(isinstance(item, str) and item.strip() for item in positives)
                or not isinstance(negative, str)
                or not negative.strip()
            ):
                raise MalformedModelEnvelope("CharterFactsMalformed")
            charter = ExpectationCharterAnswer(
                intent, exploration, tuple(positives), negative
            )
        elif raw_charter is not None:
            raise MalformedModelEnvelope(
                "EnvelopeOutcomeContradictsPayload: a non-accepting charter turn "
                "carried charter facts"
            )
    distill_document: DistillDocument | None = None
    if recovery_task:
        raw_document = structured["distill_document"]
        if outcome is ModelOutcome.Accepted:
            if not isinstance(raw_document, dict):
                raise MalformedModelEnvelope("DistillDocumentMissing")
            try:
                distill_document = DistillDocument.from_json(
                    json.dumps(
                        raw_document,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    )
                )
            except DistillDocumentInvalid as error:
                raise MalformedModelEnvelope(
                    f"DistillDocumentMalformed: {error}"
                ) from None
        elif raw_document is not None:
            raise MalformedModelEnvelope(
                "EnvelopeOutcomeContradictsPayload: a non-accepting acceptance-designer turn carried a DISTILL document"
            )
    review_defect = (
        _review_defect(structured, outcome, defect_values, semantic_role_id)
        if semantic_role_id in _DEFECT_NAMING
        else None
    )
    craft_blocker = (
        _craft_blocker(structured, outcome) if is_crafter_role(role_id) else None
    )
    return ModelRun(
        outcome=outcome,
        diagnostic=diagnostic,
        exit_status=0,
        retry_safe=False,
        product_values=values,
        accounting=accounting,
        design_facts=design_facts,
        review_defect=review_defect,
        craft_blocker=craft_blocker,
        distill_document=distill_document,
        charter=charter,
    )


def _craft_blocker(
    structured: dict[str, Any], outcome: ModelOutcome
) -> CraftBlocker | None:
    """The crafter's routing word, re-stated against the same law it declared.

    The provider validates the enum at the StructuredOutput boundary; this
    function validates it again for the envelopes that never met that
    validator -- a replayed turn record, a hand-written double, a port stub.
    Every violation is a MALFORMED envelope and therefore indeterminate: the
    turn established no semantic result the runner may charge to the product.
    """
    blocker = structured["blocked_by"]
    if outcome is ModelOutcome.Accepted:
        if blocker is not None:
            raise MalformedModelEnvelope(
                "EnvelopeOutcomeContradictsPayload: an accepted craft turn named "
                "a blocker; a turn that delivered its batch is blocked by nothing"
            )
        return None
    try:
        return CraftBlocker(blocker)
    except (TypeError, ValueError):
        raise MalformedModelEnvelope(
            "CraftBlockerMissing: a non-accepting craft turn named no blocker in "
            f"{_CRAFT_BLOCKERS}"
        ) from None


def _review_defect(
    structured: dict[str, Any],
    outcome: ModelOutcome,
    defect_values: tuple[str, ...],
    role_id: str,
) -> ReviewDefect | None:
    """The reviewer's routing word, re-stated against the same law it declared.

    The provider validates the enums at the StructuredOutput boundary; this
    function validates them again for the envelopes that never met that
    validator -- a replayed turn record, a hand-written double, a port stub.
    Every violation is a MALFORMED envelope and therefore indeterminate: the
    turn established no semantic result the runner may charge to the product.
    """
    # Absent means null, and only on an accepting envelope: the caller admits
    # the omission there and nowhere else, so a refusal that omits the word
    # still reaches the `owner is None` refusal below.
    owner = structured.get("defect_owner")
    value = structured.get("defect_value")
    if value is not None and (not isinstance(value, str) or value not in defect_values):
        raise MalformedModelEnvelope(
            "ReviewDefectValueUnknown: the turn charged its defect to a value "
            "this Request does not contain"
        )
    if outcome is ModelOutcome.Accepted:
        if owner is not None or value is not None:
            raise MalformedModelEnvelope(
                "EnvelopeOutcomeContradictsPayload: an accepted review carried a "
                "defect owner; an approval owns no defect"
            )
        return None
    owners = _defect_owners_for(role_id)
    try:
        if owner not in owners:
            raise ValueError("owner outside role scope")
        return ReviewDefect(DefectOwner(owner), value)
    except (TypeError, ValueError):
        raise MalformedModelEnvelope(
            "ReviewDefectOwnerMissing: a non-accepting review named no owner in "
            f"{owners} for its finding"
        ) from None
