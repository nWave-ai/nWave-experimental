"""The Claude-local driven adapter for one model turn (ADR-SSOT-002 13d.2).

Everything provider-shaped lives HERE and never crosses
:class:`~des.ports.driven_ports.task_invocation_port.TaskInvocationPort`: the
executable, the effort level, the permission mode, the output format and the
argv shape are all adapter-local settings.

THE MODEL IS THE ONE EXCEPTION, and deliberately so.  It is the only one of
those settings that ALSO has a home in the role's published spec, so keeping a
copy here made every role's model true in two places at once -- and the copy the
provider honours is not always the one a reader opens.  It is therefore read
from the spec, by :func:`~des.domain.agent_capability.resolve_declared_capability`,
and projected into ``--model``; this module holds no model constant.

THE ENVELOPE IS NOT A TERMINAL GRAMMAR.  With ``--output-format json`` stdout is
a document whose result is constrained by the provider's ``--json-schema`` to
one semantic outcome.  Diagnostics remain opaque evidence; the runner never
derives control flow from model-authored prose.
"""

from __future__ import annotations

import json
import shutil
import stat
import time
from pathlib import Path
from typing import Any

from des.adapters.driven.task_invocation.turn_recorder import TurnRecorder
from des.domain.agent_capability import (
    ClaimRegister,
    provider_tool_name,
    resolve_declared_capability,
)
from des.domain.architecture_brief_resolver import (
    DESIGN_ORACLE_LOCATOR_PATTERN,
    REPOSITORY_RELATIVE_WHOLE_FILE_PATTERN,
)
from des.ports.driven_ports.task_invocation_port import (
    MINIMUM_OBSERVATION_CHARACTERS,
    CraftBlocker,
    DefectOwner,
    DesignFacts,
    DesignTarget,
    MalformedModelEnvelope,
    ModelAccounting,
    ModelOutcome,
    ModelRun,
    ProductValue,
    ReviewDefect,
    TaskInvocationPort,
)
from des.runtime.spawn import AGENT_TIMEOUT_ENV, SpawnTimeout, agent_timeout_seconds


_LAUNCHER_NAME = "claude"

#: The reasoning budget one turn spawns with.  Adapter-local on purpose: no
#: caller supplies it and no contract field carries it.
#:
#: OPEN QUESTION, deliberately not answered here (recorded in `defects.md`, row
#: `reviewer-effort-low-is-unmeasured`): `low` for a reviewer that must read a
#: whole candidate diff is a choice nobody has measured.  It is left as it is
#: because changing it without a measurement would trade one unevidenced
#: setting for another.
_EFFORT = "low"
_PERMISSION_MODE = "dontAsk"
_OUTPUT_FORMAT = "json"
_STRUCTURED_OUTPUT_TOOL = "StructuredOutput"
#: Declared entries whose whole reach is a read-only query.  A turn holding only
#: these stays retry-safe after a failed spawn.  A scoped grant on the
#: provider-neutral code-fact port reads; it never writes.
_READ_ONLY_PROVIDER_TOOLS = frozenset(
    {
        "Read",
        _STRUCTURED_OUTPUT_TOOL,
        "Bash(des code-fact:*)",
    }
)
_PRODUCT_OWNER = "nw-product-owner"
_SOLUTION_ARCHITECT = "nw-solution-architect"
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


_ACCEPTING: dict[str, Any] = {
    "properties": {"outcome": {"const": ModelOutcome.Accepted.value}},
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
            },
            "required": [
                "targets",
                "paradigm",
                "decisions",
                "oracle",
                "acceptance_supports",
                "verification",
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


_DEFECT_OWNERS = [owner.value for owner in DefectOwner]


def _acceptance_reviewer_schema(
    defect_values: tuple[str, ...] = (),
) -> dict[str, Any]:
    """The reviewer answers WHO owns each defect, in a word the provider imposes.

    MEASURED, run 28c (2026-09-06, turns 07-09) and the same class in run 25
    turn 04.  The aggregate review refused the oracle set over a fact of the
    DESIGN -- a test file a value's obligation must rewrite that the value's own
    `targets` list never declared -- and the runner opened its one correction
    window on the acceptance designer, who owns no target.  The designer could
    not repair it, the second review restated the same finding, and the Request
    ended `AcceptanceReviewRejected` after roughly $1.5 and 25 minutes of turns
    spent on a correction no role in that window was able to make.

    The MODEL decides whose defect it is; the SOFTWARE only routes on the word
    (`boundary:software-measures-model-decides`).  Reading the owner off the
    finding's prose is forbidden -- diagnostics are diagnostic only -- so the
    word is a field the provider validates against a closed enum, and the
    routing fact reaches the runner in the typed payload (GDP-0).

    ``defect_value`` carries the observation the defect is charged to.  Its enum
    is built by the caller from THIS Request's observations, so a value the
    Request does not contain is unrepresentable rather than caught afterwards.
    It admits `null` as well, because the aggregate review exists precisely to
    catch set-level defects -- a duplicate stimulus across two oracles belongs
    to no single value -- and forcing a name there would make the model invent
    one.  The one rule the schema does NOT state is "a `design` defect must name
    a value": that would need a second conditional nested in the first, a shape
    no probe has measured at this boundary, and its consumer already refuses
    LOUD (GDP-6) with a diagnostic naming the omission.
    """
    owner: dict[str, Any] = {
        "type": ["string", "null"],
        "enum": [*_DEFECT_OWNERS, None],
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
                "defect_owner": {"type": "string", "enum": _DEFECT_OWNERS},
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
) -> str:
    if role_id == _PRODUCT_OWNER and max_product_values is not None:
        return json.dumps(
            _product_owner_schema(max_product_values), separators=(",", ":")
        )
    if role_id in _DEFECT_NAMING:
        return json.dumps(
            _acceptance_reviewer_schema(defect_values), separators=(",", ":")
        )
    return json.dumps(
        _ROLE_SCHEMAS.get(role_id, _OUTCOME_SCHEMA),
        separators=(",", ":"),
    )


def _effort_for(role_id: str) -> str:
    """The adapter-owned reasoning budget for one declared role.

    Effort, unlike the model, has no home in the published spec: it is a
    provider-shaped knob with no Claude Code frontmatter key, so the adapter is
    the only place it can live and there is no second definition to reconcile.
    """
    if role_id == _SOLUTION_ARCHITECT:
        return "high"
    return _EFFORT


def resolve_launcher() -> Path | None:
    """The absolute model launcher on ``PATH``, or ``None`` when unresolvable.

    Separate from construction so the owned runner can admit the executable
    BEFORE any model spend and refuse with its own typed outcome, rather than
    discovering the absence as an exception mid-run (13d.3).
    """
    found = shutil.which(_LAUNCHER_NAME)
    if not found:
        return None
    launcher = Path(found)
    try:
        mode = launcher.lstat().st_mode
    except OSError:
        return None
    # Decide on the PROPERTY, never the designation: a name on PATH is not
    # evidence of a spawnable regular file.
    if launcher.is_symlink():
        try:
            resolved = launcher.resolve(strict=True)
            mode = resolved.lstat().st_mode
        except OSError:
            return None
        launcher = resolved
    if not stat.S_ISREG(mode):
        return None
    return launcher


class ClaudeCodeTaskAdapter(TaskInvocationPort):
    """Invoke one Claude turn through the shared spawn boundary."""

    def __init__(
        self,
        launcher: Path | None = None,
        recorder: TurnRecorder | None = None,
        record_root: Path | None = None,
    ) -> None:
        """Bind this adapter to one already-admitted absolute executable.

        ``launcher=None`` resolves it now, which is what the runtime smoke and
        any ad-hoc caller want.  The owned runner passes the executable it
        admitted before model spend, so the process that admitted the executable
        is the process that spawns it and no later ``PATH`` re-resolution can
        substitute a different one.

        The adapter carries its own :class:`TurnRecorder` because the runner
        builds exactly one adapter per run, so the adapter's lifetime IS the
        run: that makes the run id and the turn numbering derivable here,
        without widening the port with parameters no caller has.  ``record_root``
        anchors those records to the run's repository, because one turn -- the
        implementation review -- runs with the candidate worktree as its cwd.
        """
        resolved = launcher if launcher is not None else resolve_launcher()
        if resolved is None:
            raise ValueError(
                f"no {_LAUNCHER_NAME} model launcher is resolvable on PATH"
            )
        self._launcher = Path(resolved)
        self._recorder = (
            recorder if recorder is not None else TurnRecorder(root=record_root)
        )

    @property
    def launcher(self) -> Path:
        """The absolute executable every turn of this adapter spawns."""
        return self._launcher

    @property
    def run_id(self) -> str:
        """The id naming this run's turn-record directory (diagnostic only)."""
        return self._recorder.run_id

    def argv_for(
        self,
        *,
        role_id: str,
        model: str,
        agents: dict[str, object] | None = None,
        max_product_values: int | None = None,
        defect_values: tuple[str, ...] = (),
    ) -> list[str]:
        """The exact argv one turn spawns -- built once, here, and nowhere else.

        THE PROMPT IS NOT A PARAMETER.  Linux caps a SINGLE ``execve`` argument
        at ``MAX_ARG_STRLEN`` (128 KiB), and a prompt grows with the evidence the
        runner inlines, so ``-p <prompt>`` made that ceiling reachable by ordinary
        content: measured 2026-09-05, run 12 died with ``[Errno 7] Argument list
        too long`` before the provider process existed, which no ``HOW: observe
        the provider result`` can remedy.  ``claude -p`` reads the prompt from
        stdin when no positional prompt is given (``--input-format text``, the
        default), so :meth:`invoke` passes it there: the ceiling is gone BY
        CONSTRUCTION for every role, not bounded per call site.  Keeping the
        prompt out of this signature is the GDP-0 half -- an unrepresentable
        wrong state needs no gate.  Every remaining element is bounded by
        something that does NOT grow with content: the role-static schema, and an
        agent spec, which is a small tracked repository file (measured
        2026-09-05: largest spec 1.9 KB, largest schema 1.2 KB).

        ``model`` IS A PARAMETER BECAUSE IT IS NOT THE ADAPTER'S FACT.  It is
        what the role's published spec declares, read by
        :func:`resolve_declared_capability` from the same frontmatter and the
        same resolved file the declared tools come from.  There is no default:
        a default would silently answer for a spec that declares nothing, which
        is exactly the second definition this signature removes.

        ``--model`` and ``--effort`` configure THE SESSION THIS TURN IS, not
        some inner sub-agent.  ``--agent <role>`` makes the spawned session BE
        that role, so the outer ``--model`` is the model the role thinks with.
        Measured 2026-09-06 against Claude Code 2.1.261: a ``model`` key placed
        inside the ``--agents`` JSON is IGNORED -- declaring ``haiku`` there
        while the argv said ``--model sonnet`` produced a turn whose work landed
        wholly on ``claude-sonnet-5``, and the mirror probe (``sonnet``
        declared, ``--model haiku``) produced no sonnet entry at all.  Every
        turn also carries a small ambient ``claude-haiku-4-5`` entry
        (~1.8k in / ~20 out) that belongs to the launcher, not to the role, so
        a haiku line in ``modelUsage`` is never evidence that a role ran on
        haiku.
        """
        effort = _effort_for(role_id)
        argv = [
            str(self._launcher),
            "-p",
            "--agent",
            role_id,
            "--model",
            model,
            "--effort",
            effort,
            "--output-format",
            _OUTPUT_FORMAT,
            "--json-schema",
            _schema_for(role_id, max_product_values, defect_values),
            "--permission-mode",
            _PERMISSION_MODE,
            "--setting-sources",
            "user",
            "--strict-mcp-config",
            "--mcp-config",
            '{"mcpServers":{}}',
            "--no-chrome",
        ]
        if agents is not None:
            argv.extend(("--agents", json.dumps(agents, separators=(",", ":"))))
        return argv

    def invoke(
        self,
        *,
        role_id: str,
        prompt: str,
        cwd: Path,
        max_product_values: int | None = None,
        defect_values: tuple[str, ...] = (),
    ) -> ModelRun:
        """Run one turn, record it as a diagnostic, and report its terminal.

        The recording wraps :meth:`_run_turn` rather than living inside it so
        there is ONE write per turn on EVERY exit -- spawned or refused before
        spawn -- instead of a line repeated at each early return, where the next
        branch added would silently be the one that records nothing.

        THAT INCLUDES THE EXITS THAT RAISE, and they are the ones that matter
        most: ``_run_turn`` propagates ``MalformedModelEnvelope`` from
        :func:`extract_model_run` and ``OSError`` from the spawn.  Recording only
        the RETURNED ``ModelRun`` recorded nothing at all for those -- measured
        2026-09-05, both cases produced zero records -- and the second of them is
        run 12's own ``[Errno 7] Argument list too long``, the failure this whole
        change exists to explain.  A raised turn has no ``ModelRun``, so the
        record carries the honest ``indeterminate`` plus a ``raised`` field
        naming the exception type, which is what tells a reader (and a later
        replay) that this turn ended by raising rather than by answering.
        """
        started_at = time.time()
        # One mutable slot per CALL, filled by `_run_turn` the moment each piece
        # of evidence exists.  Per-call rather than per-instance so two turns can
        # never interleave their evidence, and filled progressively so a turn
        # that RAISES still records the argv it spawned and whatever the provider
        # had already written.
        captured: dict[str, Any] = {"argv": None, "stdout": None, "stderr": None}
        try:
            run = self._run_turn(
                role_id=role_id,
                prompt=prompt,
                cwd=cwd,
                max_product_values=max_product_values,
                defect_values=defect_values,
                captured=captured,
            )
        except (MalformedModelEnvelope, OSError) as error:
            self._recorder.record(
                root=cwd,
                role_id=role_id,
                prompt=prompt,
                argv=captured["argv"],
                outcome=ModelOutcome.Indeterminate.value,
                diagnostic=f"{type(error).__name__}: {error}",
                exit_status=-1,
                retry_safe=False,
                provider_stdout=captured["stdout"],
                provider_stderr=captured["stderr"],
                started_at=started_at,
                ended_at=time.time(),
                raised=type(error).__name__,
            )
            raise
        self._recorder.record(
            root=cwd,
            role_id=role_id,
            prompt=prompt,
            argv=captured["argv"],
            outcome=run.outcome.value,
            diagnostic=run.diagnostic,
            exit_status=run.exit_status,
            retry_safe=run.retry_safe,
            provider_stdout=captured["stdout"],
            provider_stderr=captured["stderr"],
            started_at=started_at,
            ended_at=time.time(),
        )
        return run

    def _run_turn(
        self,
        *,
        role_id: str,
        prompt: str,
        cwd: Path,
        max_product_values: int | None = None,
        defect_values: tuple[str, ...] = (),
        captured: dict[str, Any],
    ) -> ModelRun:
        """One turn, filling `captured` with the evidence the recorder wants.

        Evidence is deposited as soon as it exists rather than returned at the
        end, because the two exits that matter most -- a malformed envelope and
        a spawn that never started a provider -- leave by raising and would
        return nothing at all.
        """
        from des.runtime.spawn import spawn

        capability = resolve_declared_capability(role_id, repo_root=cwd)
        if (
            capability.register is ClaimRegister.UNKNOWN
            or capability.spec_path is None
            or capability.declared_tools is None
        ):
            return ModelRun(
                ModelOutcome.Indeterminate,
                "agent specification is missing, unreadable, or has no explicit tools",
                0,
                False,
            )
        if capability.declared_model is None:
            # The model has ONE home, the spec, so a spec that declares none
            # leaves the turn with nothing to spawn on.  Degrade LOUD (GDP-6):
            # falling back to an adapter constant would restore the second
            # definition and hide the omission behind a working run.
            return ModelRun(
                ModelOutcome.Indeterminate,
                "WHAT: the agent specification "
                f"{capability.spec_reference(role_id)} declares no `model:`. "
                "WHY: the model a role thinks with is projected from its own "
                "spec, so an undeclared model has no value to spawn with and a "
                "default would put it back in a second place. "
                "HOW: add a `model:` line to that spec's frontmatter.",
                0,
                True,
            )
        try:
            agent_spec = capability.spec_path.read_text(encoding="utf-8")
        except OSError:
            return ModelRun(
                ModelOutcome.Indeterminate,
                "agent specification is unreadable",
                0,
                False,
            )
        declared_entries = tuple(
            dict.fromkeys((*capability.declared_tools, _STRUCTURED_OUTPUT_TOOL))
        )
        provider_tools = tuple(
            dict.fromkeys(provider_tool_name(entry) for entry in declared_entries)
        )
        agents = {
            role_id: {
                "description": role_id,
                "prompt": agent_spec,
                "tools": list(provider_tools),
            },
        }
        argv = self.argv_for(
            role_id=role_id,
            model=capability.declared_model,
            agents=agents,
            max_product_values=max_product_values,
            defect_values=defect_values,
        )
        argv.extend(
            (
                "--restricted",
                "--disable-slash-commands",
                "--tools",
                ",".join(provider_tools),
                "--allowedTools",
                ",".join(declared_entries),
            )
        )
        captured["argv"] = argv
        try:
            completed = spawn(
                argv,
                # The prompt travels on the child's stdin, which the spawn
                # boundary turns into a pipe it writes and CLOSES.  That keeps
                # the boundary's own duty intact -- the descriptor reaches EOF,
                # so no descendant can inherit a stdin that delivers data and
                # never ends -- while removing the 128 KiB per-argument ceiling
                # the prompt used to be subject to.
                input=prompt,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=agent_timeout_seconds(),
                timeout_env=AGENT_TIMEOUT_ENV,
                reap_process_group=True,
            )
        except SpawnTimeout as expired:
            captured["stdout"] = expired.captured_text
            return ModelRun(
                outcome=ModelOutcome.Indeterminate,
                diagnostic=f"provider bound fired: {expired.captured_text}",
                exit_status=-1,
                retry_safe=False,
            )
        captured["stdout"] = completed.stdout
        captured["stderr"] = completed.stderr
        if completed.returncode:
            # The run already failed on its own terms.  Applying the envelope law
            # here would report an envelope defect for what is really a failed
            # turn, so the caller sees the verbatim exit status and whatever
            # terminal could be recovered.
            return ModelRun(
                outcome=ModelOutcome.Indeterminate,
                diagnostic=_best_effort_diagnostic(
                    completed.stdout or "", completed.stderr or ""
                ),
                exit_status=int(completed.returncode),
                retry_safe=(
                    _is_retry_safe_api_error(completed.stdout or "")
                    or set(declared_entries).issubset(_READ_ONLY_PROVIDER_TOOLS)
                ),
                accounting=_accounting_from_stdout(completed.stdout or ""),
            )
        return extract_model_run(
            completed.stdout or "",
            role_id=role_id,
            max_product_values=max_product_values,
            defect_values=defect_values,
        )


def _best_effort_diagnostic(stdout: str, stderr: str) -> str:
    """Preserve failed-turn evidence without assigning it semantics."""
    return stderr or stdout


def _is_retry_safe_api_error(stdout: str) -> bool:
    """Recognize a complete API failure before any operational iteration.

    Provider bookkeeping may charge or report an internal model attempt before
    it fails (for example HTTP 529).  It is not repository work.  Only the
    explicit empty operational-iteration record makes the failed invocation
    safe for the runner to retry.
    """
    try:
        document = json.loads(stdout)
    except json.JSONDecodeError:
        return False
    if not isinstance(document, dict):
        return False
    usage = document.get("usage")
    return (
        document.get("is_error") is True
        and document.get("terminal_reason") == "api_error"
        and isinstance(usage, dict)
        and usage.get("iterations") == []
    )


def _accounting(document: dict[str, object]) -> ModelAccounting | None:
    """Read one complete native accounting record without inventing zeroes."""
    cost = document.get("total_cost_usd")
    turns = document.get("num_turns")
    session_id = document.get("session_id")
    usage = document.get("modelUsage")
    if (
        not isinstance(cost, (int, float))
        or isinstance(cost, bool)
        or cost < 0
        or not isinstance(turns, int)
        or isinstance(turns, bool)
        or turns < 0
        or not isinstance(session_id, str)
        or not session_id
        or not isinstance(usage, dict)
        or not usage
    ):
        return None
    totals = [0, 0, 0, 0]
    for record in usage.values():
        if not isinstance(record, dict):
            return None
        values = (
            record.get("inputTokens"),
            record.get("outputTokens"),
            record.get("cacheCreationInputTokens"),
            record.get("cacheReadInputTokens"),
        )
        if not all(
            isinstance(value, int) and not isinstance(value, bool) and value >= 0
            for value in values
        ):
            return None
        totals = [total + value for total, value in zip(totals, values, strict=True)]
    return ModelAccounting(float(cost), turns, *totals, session_id)


def _accounting_from_stdout(stdout: str) -> ModelAccounting | None:
    try:
        document = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    return _accounting(document) if isinstance(document, dict) else None


def extract_model_run(
    stdout: str,
    *,
    role_id: str = "",
    max_product_values: int | None = None,
    defect_values: tuple[str, ...] = (),
) -> ModelRun:
    """Consume the native outcome and carry its diagnostic without parsing it."""
    try:
        document = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise MalformedModelEnvelope(
            "ModelEnvelopeNotSingleDocument: the model launcher's stdout is not "
            f"exactly one JSON document ({exc})"
        ) from None
    if not isinstance(document, dict):
        raise MalformedModelEnvelope(
            "ModelEnvelopeNotObject: the model launcher's response document is a "
            f"{type(document).__name__}, not a JSON object"
        )
    if document.get("is_error"):
        raise MalformedModelEnvelope(
            "ModelEnvelopeErrorOutcome: the model launcher reported an error "
            "outcome for this turn"
        )
    if "structured_output" not in document:
        raise MalformedModelEnvelope(
            "ModelEnvelopeStructuredOutputMissing: response carries no structured output"
        )
    structured = document["structured_output"]
    if not isinstance(structured, dict):
        raise MalformedModelEnvelope(
            "ModelOutcomeMalformed: structured output is not an object"
        )
    expected = {"outcome", "diagnostic"}
    if role_id == _PRODUCT_OWNER:
        expected.add("values")
    if role_id == _SOLUTION_ARCHITECT:
        expected.add("design_facts")
    if role_id in _CRAFTERS:
        expected.add("blocked_by")
    # The ownership word routes a FINDING, so it is owed on a refusal and on
    # nothing else. The schema's own `else` branch already forces both fields to
    # null on an accepting envelope, so exactly one value is admissible there
    # and demanding the producer spell it buys nothing -- precautionary
    # ceremony (GDP-10). MEASURED 2026-09-06: making the whole-diff reviewer a
    # defect-naming role refused the k4 replay corpus's recorded turn 06, an
    # ACCEPTED review from before the word existed, for a field that could only
    # ever have been null. The half the routing depends on stays strict below.
    optional = {"defect_owner", "defect_value"} if role_id in _DEFECT_NAMING else set()
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
    if role_id == _PRODUCT_OWNER:
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
    if role_id == _SOLUTION_ARCHITECT:
        raw_facts = structured["design_facts"]
        if raw_facts is not None:
            try:
                targets = tuple(
                    DesignTarget(item["path"], item["decision"])
                    for item in raw_facts["targets"]
                )
                verification = tuple(tuple(argv) for argv in raw_facts["verification"])
                design_facts = DesignFacts(
                    targets,
                    raw_facts["paradigm"],
                    tuple(raw_facts["decisions"]),
                    raw_facts["oracle"],
                    tuple(raw_facts["acceptance_supports"]),
                    verification,
                )
            except (KeyError, TypeError):
                raise MalformedModelEnvelope("DesignFactsMalformed") from None
    review_defect = (
        _review_defect(structured, outcome, defect_values)
        if role_id in _DEFECT_NAMING
        else None
    )
    craft_blocker = (
        _craft_blocker(structured, outcome) if role_id in _CRAFTERS else None
    )
    return ModelRun(
        outcome=outcome,
        diagnostic=diagnostic,
        exit_status=0,
        retry_safe=False,
        product_values=values,
        accounting=_accounting(document),
        design_facts=design_facts,
        review_defect=review_defect,
        craft_blocker=craft_blocker,
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
    try:
        return ReviewDefect(DefectOwner(owner), value)
    except (TypeError, ValueError):
        raise MalformedModelEnvelope(
            "ReviewDefectOwnerMissing: a non-accepting review named no owner in "
            f"{_DEFECT_OWNERS} for its finding"
        ) from None
