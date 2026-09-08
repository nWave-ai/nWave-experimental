"""Provider translation is limited to the enforced outcome envelope."""

from __future__ import annotations

import json
from pathlib import Path
from subprocess import CompletedProcess

import jsonschema
import pytest

from des.adapters.driven.task_invocation.claude_code_task_adapter import (
    ClaudeCodeTaskAdapter,
    _acceptance_reviewer_schema,
    _is_retry_safe_api_error,
    extract_model_run,
)
from des.domain.agent_capability import ClaimRegister, resolve_declared_capability
from des.domain.architecture_brief_resolver import (
    DESIGN_ORACLE_LOCATOR_PATTERN,
    REPOSITORY_RELATIVE_WHOLE_FILE_PATTERN,
)
from des.ports.driven_ports.task_invocation_port import (
    CraftBlocker,
    DefectOwner,
    MalformedModelEnvelope,
    ModelOutcome,
)


def test_provider_529_before_an_operational_iteration_is_retry_safe() -> None:
    envelope = {
        "is_error": True,
        "terminal_reason": "api_error",
        "duration_api_ms": 1719,
        "total_cost_usd": 0.001452,
        "modelUsage": {"haiku": {"inputTokens": 1342, "outputTokens": 22}},
        "usage": {
            "iterations": [],
            "input_tokens": 1342,
            "output_tokens": 22,
        },
        "error": {"status": 529, "message": "Overloaded"},
    }

    assert _is_retry_safe_api_error(json.dumps(envelope)) is True


def test_native_accounting_is_nested_inclusive_or_absent() -> None:
    document = {
        "session_id": "provider-session",
        "total_cost_usd": 1.25,
        "num_turns": 2,
        "modelUsage": {
            "opus": {
                "inputTokens": 10,
                "outputTokens": 4,
                "cacheCreationInputTokens": 3,
                "cacheReadInputTokens": 2,
            },
            "haiku": {
                "inputTokens": 5,
                "outputTokens": 6,
                "cacheCreationInputTokens": 0,
                "cacheReadInputTokens": 0,
            },
        },
        "structured_output": {"outcome": "accepted", "diagnostic": ""},
    }

    accounting = extract_model_run(json.dumps(document)).accounting

    assert accounting is not None
    assert (
        accounting.input_tokens,
        accounting.output_tokens,
        accounting.cache_creation_input_tokens,
        accounting.cache_read_input_tokens,
    ) == (15, 10, 3, 2)
    document.pop("total_cost_usd")
    assert extract_model_run(json.dumps(document)).accounting is None
    document["total_cost_usd"] = 1.25
    document["modelUsage"]["haiku"].pop("cacheReadInputTokens")
    assert extract_model_run(json.dumps(document)).accounting is None


@pytest.mark.parametrize(
    "mutation",
    [
        {"usage": {"iterations": [{}]}},
        {"usage": {}},
        {"terminal_reason": "other"},
        {"is_error": False},
    ],
    ids=["operational-work", "missing-iterations", "not-api-error", "not-error"],
)
def test_provider_error_without_a_complete_zero_iteration_record_is_unsafe(
    mutation: dict[str, object],
) -> None:
    envelope: dict[str, object] = {
        "is_error": True,
        "terminal_reason": "api_error",
        "usage": {"iterations": []},
    }
    envelope.update(mutation)

    assert _is_retry_safe_api_error(json.dumps(envelope)) is False


def test_provider_enforces_the_three_outcome_schema() -> None:
    argv = ClaudeCodeTaskAdapter(Path("/usr/bin/claude")).argv_for(
        role_id="reviewer", model="sonnet"
    )

    schema = json.loads(argv[argv.index("--json-schema") + 1])

    assert schema == {
        "type": "object",
        "properties": {
            "outcome": {
                "type": "string",
                "enum": ["accepted", "rejected", "indeterminate"],
            },
            "diagnostic": {"type": "string"},
        },
        "required": ["outcome", "diagnostic"],
        "additionalProperties": False,
        # Every role owes the non-accepting half of the envelope law, and a
        # payload-free role owes nothing else.
        "if": {
            "properties": {"outcome": {"enum": ["rejected", "indeterminate"]}},
            "required": ["outcome"],
        },
        "then": {"properties": {"diagnostic": {"type": "string", "minLength": 1}}},
    }


def test_product_owner_alone_has_typed_ordered_values_schema() -> None:
    argv = ClaudeCodeTaskAdapter(Path("/usr/bin/claude")).argv_for(
        model="sonnet", role_id="nw-product-owner"
    )
    schema = json.loads(argv[argv.index("--json-schema") + 1])

    assert set(schema["properties"]) == {"outcome", "diagnostic", "values"}
    assert schema["properties"]["values"]["items"] == {
        "type": "object",
        # The floor is measured on accepted turns and lives in the port: every
        # real accepted observation is at least 289 characters, and the one
        # that was not was the placeholder of turn 06.
        "properties": {"observation": {"type": "string", "minLength": 40}},
        "required": ["observation"],
        "additionalProperties": False,
    }
    run = extract_model_run(
        json.dumps(
            {
                "structured_output": {
                    "outcome": "accepted",
                    "diagnostic": "",
                    "values": [{"observation": "A"}],
                }
            }
        ),
        role_id="nw-product-owner",
    )
    assert run.product_values[0].observation == "A"


def test_architect_schema_requires_typed_design_facts() -> None:
    argv = ClaudeCodeTaskAdapter(Path("/usr/bin/claude")).argv_for(
        model="sonnet", role_id="nw-solution-architect"
    )
    schema = json.loads(argv[argv.index("--json-schema") + 1])

    assert schema["required"] == ["outcome", "diagnostic", "design_facts"]
    assert schema["properties"]["design_facts"]["type"] == ["object", "null"]


@pytest.mark.parametrize(
    ("role_id", "expected_effort"),
    [
        ("nw-solution-architect", "high"),
        ("nw-software-crafter", "low"),
        ("nw-solution-architect-reviewer", "low"),
        ("other-role", "low"),
    ],
)
def test_provider_effort_is_derived_from_the_role_and_the_model_is_supplied(
    role_id: str, expected_effort: str
) -> None:
    """Effort is the adapter's fact; the model is the role's own spec's.

    Effort has no Claude Code frontmatter key, so it lives here and nowhere
    else. The model does have one, so the adapter projects the declared value
    instead of minting a second definition of it.
    """
    argv = ClaudeCodeTaskAdapter(Path("/usr/bin/claude")).argv_for(
        role_id=role_id, model="sonnet"
    )

    assert argv[argv.index("--model") + 1] == "sonnet"
    assert argv[argv.index("--effort") + 1] == expected_effort


def test_product_owner_turn_keeps_native_system_prompt_and_provider_contract() -> None:
    argv = ClaudeCodeTaskAdapter(Path("/usr/bin/claude")).argv_for(
        model="sonnet", role_id="nw-product-owner"
    )

    assert "--system-prompt" not in argv
    assert argv[argv.index("--agent") + 1] == "nw-product-owner"
    assert argv[argv.index("--effort") + 1] == "low"
    schema = json.loads(argv[argv.index("--json-schema") + 1])
    assert schema["required"] == ["outcome", "diagnostic", "values"]


def test_architect_outcome_keeps_opaque_diagnostic_and_typed_facts() -> None:
    diagnostic = "Updated the ADR; do not parse this sentence."

    run = extract_model_run(
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
                    },
                }
            }
        ),
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
        extract_model_run(envelope, role_id="nw-solution-architect")


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
    run = extract_model_run(envelope)

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
        extract_model_run(envelope)


@pytest.mark.parametrize(
    ("declared", "expected", "register"),
    [
        (" Read, Edit", ("Read", "Edit"), ClaimRegister.INSTRUCTED),
        (
            " Read, StructuredOutput",
            ("Read", "StructuredOutput"),
            ClaimRegister.INSTRUCTED,
        ),
        ("", (), ClaimRegister.ENFORCED),
    ],
)
def test_declared_tools_are_available_and_allowed_without_extra_permission(
    declared: str,
    expected: tuple[str, ...],
    register: ClaimRegister,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicitly empty `tools:` key is the only enforced empty capability.

    A source-reaching grant stays merely INSTRUCTED.
    """
    spec = tmp_path / "nWave/agents/reviewer.md"
    spec.parent.mkdir(parents=True)
    spec.write_text(
        f"---\nmodel: sonnet\ntools:{declared}\n---\nreview\n", encoding="utf-8"
    )
    capability = resolve_declared_capability("reviewer", repo_root=tmp_path)

    assert capability.declared_tools == expected
    assert capability.register is register

    captured: list[str] = []

    def fake_spawn(argv, **_kwargs):
        captured.extend(argv)
        return CompletedProcess(
            argv,
            0,
            json.dumps(
                {"structured_output": {"outcome": "accepted", "diagnostic": ""}}
            ),
            "",
        )

    monkeypatch.setattr("des.runtime.spawn.spawn", fake_spawn)
    run = ClaudeCodeTaskAdapter(Path("/usr/bin/claude")).invoke(
        role_id="reviewer", prompt="review", cwd=tmp_path
    )

    assert run.outcome is ModelOutcome.Accepted
    provider_tools = tuple(dict.fromkeys((*expected, "StructuredOutput")))
    granted = ",".join(provider_tools)
    assert captured[captured.index("--tools") + 1] == granted
    assert captured[captured.index("--allowedTools") + 1] == granted
    agents = json.loads(captured[captured.index("--agents") + 1])
    assert agents == {
        "reviewer": {
            "description": "reviewer",
            "prompt": spec.read_text(encoding="utf-8"),
            "tools": list(provider_tools),
        }
    }


def test_declared_specifier_grants_the_bare_tool_and_allows_only_that_invocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A `Bash(...)` specifier reaches the two provider flags in different shapes.

    Measured against Claude Code 2.1.261 under `--restricted` (2026-09-05): the
    specifier in `--tools` registers no tool at all, so the declaring role
    silently loses the capability; the bare name in `--tools` with the specifier
    in `--allowedTools` runs the named invocation and denies the sibling
    subcommand that writes.
    """
    spec = tmp_path / "nWave/agents/architect.md"
    spec.parent.mkdir(parents=True)
    spec.write_text(
        "---\nmodel: sonnet\ntools: Read, Bash(des code-fact:*)\n---\nd\n",
        encoding="utf-8",
    )

    captured: list[str] = []

    def fake_spawn(argv, **_kwargs):
        captured.extend(argv)
        return CompletedProcess(
            argv,
            0,
            json.dumps(
                {"structured_output": {"outcome": "accepted", "diagnostic": ""}}
            ),
            "",
        )

    monkeypatch.setattr("des.runtime.spawn.spawn", fake_spawn)
    run = ClaudeCodeTaskAdapter(Path("/usr/bin/claude")).invoke(
        role_id="architect", prompt="design", cwd=tmp_path
    )

    assert run.outcome is ModelOutcome.Accepted
    assert captured[captured.index("--tools") + 1] == "Read,Bash,StructuredOutput"
    assert captured[captured.index("--allowedTools") + 1] == (
        "Read,Bash(des code-fact:*),StructuredOutput"
    )
    agents = json.loads(captured[captured.index("--agents") + 1])
    assert agents["architect"]["tools"] == ["Read", "Bash", "StructuredOutput"]


def test_missing_declared_tools_fails_closed_without_provider_spend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "des.runtime.spawn.spawn", lambda *_args, **_kwargs: pytest.fail("spawned")
    )

    run = ClaudeCodeTaskAdapter(Path("/usr/bin/claude")).invoke(
        role_id="missing", prompt="review", cwd=tmp_path
    )

    assert run.outcome is ModelOutcome.Indeterminate
    assert "no explicit tools" in run.diagnostic


@pytest.mark.parametrize(("tools", "retry_safe"), [(" Read", True), (" Edit", False)])
def test_nonzero_provider_run_is_safe_only_for_effectively_read_only_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tools: str, retry_safe: bool
) -> None:
    spec = tmp_path / "nWave/agents/reviewer.md"
    spec.parent.mkdir(parents=True)
    spec.write_text(
        f"---\nmodel: sonnet\ntools:{tools}\n---\nreview\n", encoding="utf-8"
    )
    failure = json.dumps(
        {
            "is_error": True,
            "terminal_reason": "other",
            "session_id": "provider-session",
            "total_cost_usd": 1.25,
            "num_turns": 2,
            "modelUsage": {
                "opus": {
                    "inputTokens": 10,
                    "outputTokens": 4,
                    "cacheCreationInputTokens": 3,
                    "cacheReadInputTokens": 2,
                }
            },
            "usage": {"iterations": [{}]},
        }
    )
    monkeypatch.setattr(
        "des.runtime.spawn.spawn",
        lambda argv, **_kwargs: CompletedProcess(argv, 1, failure, ""),
    )

    run = ClaudeCodeTaskAdapter(Path("/usr/bin/claude")).invoke(
        role_id="reviewer", prompt="review", cwd=tmp_path
    )

    assert run.exit_status == 1
    assert run.retry_safe is retry_safe
    assert run.accounting is not None
    assert run.accounting.total_cost_usd == 1.25
    assert run.accounting.session_id == "provider-session"


def test_a_bounded_product_owner_call_makes_an_out_of_window_suffix_unrepresentable() -> (
    None
):
    """The replacement window is a fact of the CALL, not of the role.

    It bounds the answer from above only.  An empty answer is the Product
    Owner's statement that the preserved prefix already covers the Request, so
    the schema declares no lower bound to contradict it.
    """
    argv = ClaudeCodeTaskAdapter(Path("/usr/bin/claude")).argv_for(
        model="sonnet", role_id="nw-product-owner", max_product_values=2
    )

    values = json.loads(argv[argv.index("--json-schema") + 1])["properties"]["values"]

    assert values["maxItems"] == 2 and "minItems" not in values


def test_an_unbounded_product_owner_call_declares_no_window() -> None:
    """The forward decomposition has no window, so it declares no cardinality."""
    argv = ClaudeCodeTaskAdapter(Path("/usr/bin/claude")).argv_for(
        model="sonnet", role_id="nw-product-owner"
    )

    values = json.loads(argv[argv.index("--json-schema") + 1])["properties"]["values"]

    assert "minItems" not in values and "maxItems" not in values


def test_a_window_never_reaches_a_role_that_returns_no_values() -> None:
    argv = ClaudeCodeTaskAdapter(Path("/usr/bin/claude")).argv_for(
        model="sonnet", role_id="nw-solution-architect", max_product_values=2
    )

    schema = json.loads(argv[argv.index("--json-schema") + 1])

    assert "values" not in schema["properties"]


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
        extract_model_run(
            _product_owner_stdout(3),
            role_id="nw-product-owner",
            max_product_values=2,
        )


def test_an_empty_suffix_inside_a_declared_window_is_consumed() -> None:
    """Zero is inside the window: the consumer, not the envelope, judges it.

    The envelope law owns cardinality against the declared window; whether an
    empty suffix leaves a value in the graph is the correction consumer's
    decision, and it refuses there with a product-side diagnostic.
    """
    run = extract_model_run(
        _product_owner_stdout(0), role_id="nw-product-owner", max_product_values=2
    )

    assert run.product_values == ()


def test_a_suffix_inside_the_declared_window_is_consumed() -> None:
    run = extract_model_run(
        _product_owner_stdout(2), role_id="nw-product-owner", max_product_values=2
    )

    assert [value.observation for value in run.product_values] == ["v0", "v1"]


def test_an_unbounded_product_owner_turn_admits_any_cardinality() -> None:
    run = extract_model_run(_product_owner_stdout(5), role_id="nw-product-owner")

    assert len(run.product_values) == 5


def _fake_launcher(directory: Path) -> Path:
    """A real spawnable launcher that answers with the prompt length it read.

    Real, not a double: the defect under repair is an ``execve`` refusal, which
    only a genuine spawn can exhibit.  A patched ``spawn`` would pass over the
    very kernel boundary that failed.
    """
    launcher = directory / "fake-claude"
    # The envelope it answers is the one its `--agent` role owes: a role with a
    # payload that answered the payload-free shape would be malformed, and the
    # adapter would report an envelope defect for a launcher that behaved.
    launcher.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "import sys\n"
        "\n"
        "prompt = sys.stdin.read()\n"
        "role = sys.argv[sys.argv.index('--agent') + 1]\n"
        "payload = {'outcome': 'accepted', 'diagnostic': str(len(prompt))}\n"
        "if role == 'nw-acceptance-designer-reviewer':\n"
        "    payload['defect_owner'] = None\n"
        "    payload['defect_value'] = None\n"
        "print(json.dumps({'structured_output': payload}))\n",
        encoding="utf-8",
    )
    launcher.chmod(0o755)
    return launcher


def _repo_with_spec(root: Path, role_id: str) -> Path:
    spec = root / "nWave" / "agents" / f"{role_id}.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("---\nmodel: sonnet\ntools:\n---\njudge\n", encoding="utf-8")
    return root


def test_a_prompt_over_the_kernel_argument_ceiling_still_reaches_the_provider(
    tmp_path: Path,
) -> None:
    """One argv element is capped at 128 KiB (``MAX_ARG_STRLEN``); a prompt is not.

    Measured 2026-09-05, run 12: the aggregate acceptance review inlined the
    declared support bytes and ``execve`` refused the whole turn with
    ``[Errno 7] Argument list too long`` before the provider ever started.
    """
    root = _repo_with_spec(tmp_path, "nw-acceptance-designer-reviewer")
    prompt = "x" * (200 * 1024)

    run = ClaudeCodeTaskAdapter(_fake_launcher(tmp_path)).invoke(
        role_id="nw-acceptance-designer-reviewer", prompt=prompt, cwd=root
    )

    assert run.outcome is ModelOutcome.Accepted
    assert run.diagnostic == str(len(prompt))


def test_the_prompt_is_not_representable_in_argv(tmp_path: Path) -> None:
    """The ceiling is gone BY CONSTRUCTION: no argv element can carry a prompt."""
    argv = ClaudeCodeTaskAdapter(_fake_launcher(tmp_path)).argv_for(
        model="sonnet", role_id="nw-acceptance-designer-reviewer"
    )

    assert "-p" in argv
    assert max(len(part) for part in argv) < 4096


def _recorded_architect_answer() -> dict:
    """The EXACT structured output the provider returned for turn 04 of run
    20260905T002110Z-3913588 -- `accepted`, with six prose sentences where
    `acceptance_supports` requires repository-relative file locators."""
    return json.loads(
        (Path(__file__).parent / "turn_04_architect_structured_output.json").read_text(
            encoding="utf-8"
        )
    )


def _architect_schema() -> dict:
    argv = ClaudeCodeTaskAdapter(Path("/usr/bin/claude")).argv_for(
        model="sonnet", role_id="nw-solution-architect"
    )
    return json.loads(argv[argv.index("--json-schema") + 1])


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

    assert {tuple(error.absolute_path) for error in errors} == {
        ("design_facts", "acceptance_supports", index) for index in range(6)
    }
    assert all(error.validator == "pattern" for error in errors)


def test_architect_schema_admits_locator_shaped_design_facts() -> None:
    answer = _recorded_architect_answer()
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
    answer = _recorded_architect_answer()
    answer["design_facts"]["acceptance_supports"] = ["src/support.py"]
    answer["design_facts"].update(mutation)

    errors = list(
        jsonschema.Draft202012Validator(_architect_schema()).iter_errors(answer)
    )

    assert expected_path in {tuple(error.absolute_path) for error in errors}


def test_architect_schema_states_the_locator_grammar_only_once() -> None:
    """One contract, one spelling: the schema IMPORTS the domain grammar."""
    schema = _architect_schema()["properties"]["design_facts"]["properties"]

    assert (
        schema["acceptance_supports"]["items"]["pattern"]
        == schema["targets"]["items"]["properties"]["path"]["pattern"]
        == REPOSITORY_RELATIVE_WHOLE_FILE_PATTERN
    )
    assert schema["oracle"]["pattern"] == DESIGN_ORACLE_LOCATOR_PATTERN


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
    argv = ClaudeCodeTaskAdapter(Path("/usr/bin/claude")).argv_for(
        model="sonnet", role_id="nw-product-owner", max_product_values=window
    )
    return json.loads(argv[argv.index("--json-schema") + 1])


def test_the_schema_of_run_21_admitted_a_rejection_carrying_a_full_value_graph() -> (
    None
):
    """The defect, stated as the property that made it possible.

    Not a claim about the model: the ENVELOPE was self-contradictory and the
    schema in force admitted it, so nothing in the turn could correct it.
    """
    recorded = _recorded_product_owner_turn()
    envelope = recorded["structured_output"]
    assert envelope["outcome"] == "rejected" and len(envelope["values"]) == 3

    jsonschema.Draft202012Validator(recorded["schema_the_provider_enforced"]).validate(
        envelope
    )


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


def test_the_envelope_law_uses_the_only_conditional_the_api_accepts() -> None:
    """Measured 2026-09-05 against the installed launcher.

    A schema carrying `allOf`, `anyOf` or `oneOf` at the top level is refused
    by the API with HTTP 400 -- "input_schema does not support oneOf, allOf, or
    anyOf at the top level" -- before any model turn exists, so the law cannot
    be written as a union of two whole schemas.  A top-level `if`/`then`/`else`
    is accepted and enforced.  This test fails the day the law is rewritten in
    the shape the boundary rejects, which no local validator would catch.
    """
    for schema in (
        _product_owner_schema(),
        _product_owner_schema(3),
        _architect_schema(),
    ):
        assert not {"allOf", "anyOf", "oneOf"} & set(schema)
        assert "if" in schema and "then" in schema


@pytest.mark.parametrize("outcome", ["rejected", "indeterminate"])
def test_architect_schema_refuses_facts_on_a_non_accepting_outcome(
    outcome: str,
) -> None:
    """The state the runner used to catch post hoc as `DesignFactsMalformed`."""
    answer = _recorded_architect_answer()
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
        extract_model_run(
            json.dumps({"structured_output": envelope}),
            role_id="nw-product-owner",
        )

    assert "EnvelopeOutcomeContradictsPayload" in str(refused.value)
    assert f"a {outcome} turn carried 3 product values" in str(refused.value)


def test_a_coherent_refusal_still_reaches_the_runner_as_a_refusal() -> None:
    run = extract_model_run(
        json.dumps(
            {
                "structured_output": {
                    "outcome": "rejected",
                    "diagnostic": "one value only",
                    "values": [],
                }
            }
        ),
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
    argv = ClaudeCodeTaskAdapter(Path("/usr/bin/claude")).argv_for(
        role_id=role_id, model="sonnet"
    )
    return json.loads(argv[argv.index("--json-schema") + 1])


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


def test_the_payload_free_law_uses_a_conditional_with_no_else() -> None:
    """Measured 2026-09-05: `if`/`then` alone is accepted by the API and enforced.

    Asked to answer `rejected` with an empty diagnostic, the provider refused
    the StructuredOutput call with "must NOT have fewer than 1 characters
    (got 0), root: must match the 'then' schema".  This test fails the day the
    clause is written in the shape the boundary rejects, which no local
    validator would catch.
    """
    schema = _role_schema("nw-acceptance-designer")

    assert not {"allOf", "anyOf", "oneOf"} & set(schema)
    assert "if" in schema and "then" in schema and "else" not in schema


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


def test_the_craft_law_uses_the_only_conditional_the_api_accepts() -> None:
    """Measured 2026-09-05: `allOf`/`anyOf`/`oneOf` are refused at the top level."""
    schema = _role_schema("nw-software-crafter")

    assert not {"allOf", "anyOf", "oneOf"} & set(schema)
    assert {"if", "then", "else"} <= set(schema)


def test_a_replayed_craft_refusal_naming_no_blocker_is_indeterminate() -> None:
    """The envelope law, re-stated for the envelopes that never met the schema."""
    with pytest.raises(MalformedModelEnvelope, match="CraftBlockerMissing"):
        extract_model_run(
            _crafter_stdout(
                outcome="rejected", diagnostic="a finding", blocked_by=None
            ),
            role_id="nw-software-crafter",
        )


def test_a_replayed_accepted_craft_turn_carrying_a_blocker_is_indeterminate() -> None:
    with pytest.raises(
        MalformedModelEnvelope, match="EnvelopeOutcomeContradictsPayload"
    ):
        extract_model_run(
            _crafter_stdout(outcome="accepted", diagnostic="", blocked_by="oracle"),
            role_id="nw-software-crafter",
        )


def test_a_blocked_craft_turn_reaches_the_runner_as_typed_data() -> None:
    run = extract_model_run(
        _crafter_stdout(
            outcome="rejected",
            diagnostic="the oracle compares two absolute paths",
            blocked_by="oracle",
        ),
        role_id="nw-functional-software-crafter",
    )

    assert run.craft_blocker is CraftBlocker.Oracle


def test_a_delivered_craft_turn_reaches_the_runner_with_no_blocker() -> None:
    run = extract_model_run(
        _crafter_stdout(outcome="accepted", diagnostic="", blocked_by=None),
        role_id="nw-software-crafter",
    )

    assert run.outcome is ModelOutcome.Accepted and run.craft_blocker is None


#: The two values one Request's aggregate review may charge a defect to.
_REVIEWED = ("value one", "value two")
_REVIEWER = "nw-acceptance-designer-reviewer"


def _reviewer_stdout(**payload: object) -> str:
    return json.dumps({"structured_output": payload})


def test_the_review_call_declares_the_values_a_defect_may_be_charged_to() -> None:
    """The enum is a fact of the CALL: this Request's own observations."""
    argv = ClaudeCodeTaskAdapter(Path("/usr/bin/claude")).argv_for(
        model="sonnet", role_id=_REVIEWER, defect_values=_REVIEWED
    )

    schema = json.loads(argv[argv.index("--json-schema") + 1])

    assert schema["properties"]["defect_value"]["enum"] == [*_REVIEWED, None]
    assert schema["properties"]["defect_owner"]["enum"] == [
        *(owner.value for owner in DefectOwner),
        None,
    ]


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


def test_the_review_law_uses_the_only_conditional_the_api_accepts() -> None:
    schema = _acceptance_reviewer_schema(_REVIEWED)

    assert not {"allOf", "anyOf", "oneOf"} & set(schema)
    assert {"if", "then", "else"} <= set(schema)


def test_a_replayed_review_naming_no_owner_is_indeterminate_not_a_refusal() -> None:
    """The envelope law, re-stated for the envelopes that never met the schema."""
    with pytest.raises(MalformedModelEnvelope, match="ReviewDefectOwnerMissing"):
        extract_model_run(
            _reviewer_stdout(
                outcome="rejected",
                diagnostic="a defect",
                defect_owner=None,
                defect_value=None,
            ),
            role_id=_REVIEWER,
            defect_values=_REVIEWED,
        )


def test_a_replayed_review_charging_an_unknown_value_is_indeterminate() -> None:
    with pytest.raises(MalformedModelEnvelope, match="ReviewDefectValueUnknown"):
        extract_model_run(
            _reviewer_stdout(
                outcome="rejected",
                diagnostic="a defect",
                defect_owner="design",
                defect_value="value nine",
            ),
            role_id=_REVIEWER,
            defect_values=_REVIEWED,
        )


def test_a_replayed_approval_carrying_an_owner_is_indeterminate() -> None:
    with pytest.raises(
        MalformedModelEnvelope, match="EnvelopeOutcomeContradictsPayload"
    ):
        extract_model_run(
            _reviewer_stdout(
                outcome="accepted",
                diagnostic="",
                defect_owner="oracle",
                defect_value=None,
            ),
            role_id=_REVIEWER,
            defect_values=_REVIEWED,
        )


def test_an_owned_review_finding_reaches_the_runner_as_typed_data() -> None:
    run = extract_model_run(
        _reviewer_stdout(
            outcome="rejected",
            diagnostic="value two omits a target",
            defect_owner="design",
            defect_value="value two",
        ),
        role_id=_REVIEWER,
        defect_values=_REVIEWED,
    )

    assert run.review_defect is not None
    assert run.review_defect.owner is DefectOwner.Design
    assert run.review_defect.value == "value two"


def test_an_approving_review_reaches_the_runner_with_no_defect() -> None:
    run = extract_model_run(
        _reviewer_stdout(
            outcome="accepted",
            diagnostic="",
            defect_owner=None,
            defect_value=None,
        ),
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
    return extract_model_run(
        json.dumps({"structured_output": structured}), role_id=role_id
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
