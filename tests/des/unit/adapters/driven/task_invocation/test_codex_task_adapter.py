"""Codex translation is terminal-file based and preserves the shared envelope."""

from __future__ import annotations

import json
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from des.adapters.driven.task_invocation.codex_task_adapter import (
    _TOOL_FREE_FEATURES,
    CodexTaskAdapter,
    codex_schema_for,
)
from des.adapters.driven.task_invocation.model_envelope import decode_model_run
from des.ports.driven_ports.task_invocation_port import (
    MalformedModelEnvelope,
    ModelOutcome,
)


def _role(root: Path, role_id: str, tools: str = "Read, Edit") -> Path:
    path = root / "nWave" / "agents" / f"{role_id}.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        f"---\nname: {role_id}\nmodel: legacy-model\ntools: {tools}\n---\n"
        "Role developer instruction body.\n",
        encoding="utf-8",
    )
    return path


def test_codex_binds_role_as_developer_instruction_and_reads_only_terminal_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    role_id = "nw-software-crafter"
    spec = _role(tmp_path, role_id)
    observed: dict[str, object] = {}

    def fake_spawn(argv: list[str], **_: object) -> CompletedProcess[str]:
        observed["argv"] = argv
        terminal = Path(argv[argv.index("--output-last-message") + 1])
        observed["terminal_parent"] = terminal.parent
        terminal.write_text(
            json.dumps(
                {
                    "answer": {
                        "outcome": "accepted",
                        "diagnostic": "done",
                        "blocked_by": None,
                    }
                }
            ),
            encoding="utf-8",
        )
        # This conflicting stdout is provenance only. It must not become an
        # answer through a prose/result parser.
        return CompletedProcess(argv, 0, '{"binding":"user-bound"}\n', "")

    monkeypatch.setattr("des.runtime.spawn.spawn", fake_spawn)

    run = CodexTaskAdapter(Path("/bin/codex"), model="gpt-5.6-terra").invoke(
        role_id=role_id, prompt="user prompt", cwd=tmp_path
    )

    argv = observed["argv"]
    assert isinstance(argv, list)
    assert run.outcome is ModelOutcome.Accepted
    assert "--agent" not in argv
    assert argv[:5] == [
        "/bin/codex",
        "exec",
        "--strict-config",
        "--ephemeral",
        "--ignore-user-config",
    ]
    assert argv[argv.index("--sandbox") + 1] == "workspace-write"
    assert argv[argv.index("--model") + 1] == "gpt-5.6-terra"
    setting = argv[argv.index("-c") + 1]
    assert setting.startswith("developer_instructions=")
    assert json.loads(setting.split("=", 1)[1]) == spec.read_text(encoding="utf-8")
    assert not Path(observed["terminal_parent"]).exists()


def test_codex_uses_framework_role_bytes_but_keeps_candidate_execution_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = tmp_path / "candidate"
    _role(candidate, "role")
    framework = tmp_path / "framework"
    runtime_spec = _role(framework, "role", tools="Read")
    runtime_spec.write_text(
        "---\nname: role\nmodel: runtime\ntools: Read\n---\ncorrected runtime\n",
        encoding="utf-8",
    )
    observed: dict[str, object] = {}

    def fake_spawn(argv: list[str], **kwargs: object) -> CompletedProcess[str]:
        observed["argv"] = argv
        observed["cwd"] = kwargs["cwd"]
        observed["input"] = kwargs["input"]
        Path(argv[argv.index("--output-last-message") + 1]).write_text(
            '{"answer":{"outcome":"accepted","diagnostic":"done"}}',
            encoding="utf-8",
        )
        return CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr("des.runtime.spawn.spawn", fake_spawn)
    run = CodexTaskAdapter(
        Path("/bin/codex"), model="configured", framework_root=framework
    ).invoke(role_id="role", prompt="candidate prompt", cwd=candidate)

    argv = observed["argv"]
    assert run.outcome is ModelOutcome.Accepted
    assert observed["cwd"] == str(candidate)
    assert observed["input"] == "candidate prompt"
    assert isinstance(argv, list)
    setting = argv[argv.index("-c") + 1]
    assert json.loads(setting.split("=", 1)[1]) == runtime_spec.read_text(
        encoding="utf-8"
    )
    assert argv[argv.index("--model") + 1] == "configured"


def test_codex_without_framework_root_keeps_cwd_local_role_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _role(tmp_path, "role", tools="Read")
    observed: list[str] = []

    def fake_spawn(argv: list[str], **_: object) -> CompletedProcess[str]:
        observed.extend(argv)
        Path(argv[argv.index("--output-last-message") + 1]).write_text(
            '{"answer":{"outcome":"accepted","diagnostic":"done"}}',
            encoding="utf-8",
        )
        return CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr("des.runtime.spawn.spawn", fake_spawn)
    CodexTaskAdapter(Path("/bin/codex"), model="configured").invoke(
        role_id="role", prompt="local", cwd=tmp_path
    )

    setting = observed[observed.index("-c") + 1]
    assert json.loads(setting.split("=", 1)[1]) == spec.read_text(encoding="utf-8")


def test_codex_disables_each_tool_surface_for_an_empty_tool_role(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _role(tmp_path, "nw-user-examiner", tools="")
    (tmp_path / "AGENTS.md").write_text("source-only marker", encoding="utf-8")
    observed: dict[str, list[str]] = {}

    def fake_spawn(argv: list[str], **kwargs: object) -> CompletedProcess[str]:
        if argv[-1] == "--version":
            return CompletedProcess(argv, 0, "codex-cli 0.153.4\n", "")
        if argv[-2:] == ["features", "list"]:
            return CompletedProcess(
                argv,
                0,
                "\n".join(f"{feature} stable false" for feature in _TOOL_FREE_FEATURES),
                "",
            )
        observed["argv"] = argv
        observed["cwd"] = [str(kwargs["cwd"])]
        Path(argv[argv.index("--output-last-message") + 1]).write_text(
            '{"answer":{"outcome":"accepted","diagnostic":"blind"}}',
            encoding="utf-8",
        )
        return CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr("des.runtime.spawn.spawn", fake_spawn)

    run = CodexTaskAdapter(Path("/bin/codex"), model="gpt-5.6-luna").invoke(
        role_id="nw-user-examiner", prompt="inspect", cwd=tmp_path
    )

    assert run.outcome is ModelOutcome.Accepted
    assert observed["argv"].count("--disable") >= 10
    assert "--skip-git-repo-check" in observed["argv"]
    assert "mcp_servers={}" in observed["argv"]
    assert 'web_search="disabled"' in observed["argv"]
    assert "project_doc_max_bytes=0" in observed["argv"]
    assert "skills.include_instructions=false" in observed["argv"]
    assert "orchestrator.skills.enabled=false" in observed["argv"]
    assert "orchestrator.mcp.enabled=false" in observed["argv"]
    assert (
        observed["argv"][observed["argv"].index("skip_host_skill_discovery") - 1]
        == "--enable"
    )
    execution_cwd = Path(observed["cwd"][0])
    assert execution_cwd != tmp_path
    assert not (execution_cwd / "AGENTS.md").exists()


def test_codex_refuses_missing_terminal_file_even_when_stdout_looks_valid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _role(tmp_path, "nw-product-owner", tools="Read")

    def fake_spawn(argv: list[str], **_: object) -> CompletedProcess[str]:
        return CompletedProcess(
            argv, 0, '{"structured_output":{"outcome":"accepted"}}', ""
        )

    monkeypatch.setattr("des.runtime.spawn.spawn", fake_spawn)

    with pytest.raises(MalformedModelEnvelope, match="TerminalFileMalformed"):
        CodexTaskAdapter(Path("/bin/codex"), model="gpt-5.6-terra").invoke(
            role_id="nw-product-owner", prompt="classify", cwd=tmp_path
        )


def test_codex_refuses_an_unconfigured_runtime_before_spawning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _role(tmp_path, "nw-product-owner", tools="Read")

    def must_not_spawn(*_args: object, **_kwargs: object) -> CompletedProcess[str]:
        raise AssertionError("unconfigured Codex must not issue a provider process")

    monkeypatch.setattr("des.runtime.spawn.spawn", must_not_spawn)

    run = CodexTaskAdapter(Path("/bin/codex")).invoke(
        role_id="nw-product-owner", prompt="classify", cwd=tmp_path
    )

    assert run.outcome is ModelOutcome.Indeterminate
    assert run.issued is False
    assert "no declared model" in run.diagnostic


def test_codex_preserves_native_jsonl_error_when_the_process_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _role(tmp_path, "nw-product-owner", tools="Read")
    native_error = {
        "type": "turn.failed",
        "error": {"message": "invalid_json_schema: branch must name a type"},
    }

    def fake_spawn(argv: list[str], **_: object) -> CompletedProcess[str]:
        return CompletedProcess(argv, 1, json.dumps(native_error), "Reading prompt")

    monkeypatch.setattr("des.runtime.spawn.spawn", fake_spawn)

    run = CodexTaskAdapter(Path("/bin/codex"), model="gpt-5.6-terra").invoke(
        role_id="nw-product-owner", prompt="classify", cwd=tmp_path
    )

    assert run.outcome is ModelOutcome.Indeterminate
    assert run.diagnostic == native_error["error"]["message"]


def test_empty_tool_role_refuses_before_model_issue_when_cli_census_drifts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _role(tmp_path, "nw-user-examiner", tools="")

    def fake_spawn(argv: list[str], **_: object) -> CompletedProcess[str]:
        assert argv[-1] == "--version"
        return CompletedProcess(argv, 0, "codex-cli future-version\n", "")

    monkeypatch.setattr("des.runtime.spawn.spawn", fake_spawn)

    run = CodexTaskAdapter(Path("/bin/codex"), model="gpt-5.6-luna").invoke(
        role_id="nw-user-examiner", prompt="inspect", cwd=tmp_path
    )

    assert run.outcome is ModelOutcome.Indeterminate
    assert "audited CLI census" in run.diagnostic


def test_codex_schema_is_strict_but_the_decoder_keeps_semantic_coherence() -> None:
    schema = codex_schema_for("nw-software-crafter")

    assert schema["additionalProperties"] is False
    assert schema["required"] == ["answer"]
    branches = schema["properties"]["answer"]["anyOf"]
    assert {branch["properties"]["outcome"]["const"] for branch in branches} == {
        "accepted",
        "rejected",
        "indeterminate",
    }
    for branch in branches:
        assert branch["additionalProperties"] is False
        assert set(branch["required"]) == set(branch["properties"])
    accepted = next(
        branch
        for branch in branches
        if branch["properties"]["outcome"]["const"] == "accepted"
    )
    assert accepted["properties"]["blocked_by"] == {"type": "null"}


@pytest.mark.parametrize(
    "role_id",
    [
        "nw-product-owner",
        "nw-solution-architect",
        "nw-acceptance-designer",
        "nw-acceptance-designer-reviewer",
        "nw-software-crafter",
        "nw-functional-software-crafter",
        "nw-software-crafter-reviewer",
        "nw-user-examiner",
    ],
)
def test_codex_projection_excludes_every_rejected_unique_items_keyword(
    role_id: str,
) -> None:
    """The Codex transport excludes the keyword the real launcher rejects."""

    def keys(value: object) -> set[str]:
        if isinstance(value, list):
            return set().union(*(keys(item) for item in value)) if value else set()
        if isinstance(value, dict):
            return set(value).union(*(keys(item) for item in value.values()))
        return set()

    assert "uniqueItems" not in keys(codex_schema_for(role_id))


@pytest.mark.parametrize(
    "role_id",
    [
        "nw-product-owner",
        "nw-solution-architect",
        "nw-acceptance-designer",
        "nw-acceptance-designer-reviewer",
        "nw-software-crafter",
        "nw-functional-software-crafter",
        "nw-software-crafter-reviewer",
        "nw-user-examiner",
    ],
)
def test_codex_projection_uses_no_lookaround_pattern_for_any_role(role_id: str) -> None:
    """Every projected pattern stays inside the Codex strict regex subset."""

    def patterns(value: object) -> list[str]:
        if isinstance(value, list):
            return [pattern for item in value for pattern in patterns(item)]
        if isinstance(value, dict):
            own = [value["pattern"]] if isinstance(value.get("pattern"), str) else []
            return own + [
                pattern for item in value.values() for pattern in patterns(item)
            ]
        return []

    unsupported_lookarounds = ("(?=", "(?!", "(?<=", "(?<!")
    assert all(
        marker not in pattern
        for pattern in patterns(codex_schema_for(role_id))
        for marker in unsupported_lookarounds
    )


def test_shared_decoder_refuses_duplicate_design_supports_after_codex_projection() -> (
    None
):
    """Transport compatibility never canonicalizes an invalid support collection."""
    structured = {
        "outcome": "accepted",
        "diagnostic": "",
        "design_facts": {
            "targets": [{"path": "src/example.py", "decision": "EXTEND"}],
            "paradigm": "object_oriented",
            "decisions": ["extend the existing seam"],
            "oracle": "tests/test_example.py",
            "acceptance_supports": ["tests/support.py", "tests/support.py"],
            "verification": [["python", "-m", "pytest", "-q"]],
        },
    }

    with pytest.raises(MalformedModelEnvelope, match="DuplicateAcceptanceSupport"):
        decode_model_run(structured, role_id="nw-solution-architect")


@pytest.mark.parametrize(
    ("field", "unsafe_value"),
    [
        ("targets", [{"path": "../escape.py", "decision": "EXTEND"}]),
        ("acceptance_supports", ["tests/../escape.py"]),
        ("oracle", "tests/test_example.py::selector/../escape"),
    ],
)
def test_shared_decoder_refuses_unsafe_locator_in_every_design_fact_field(
    field: str, unsafe_value: object
) -> None:
    """A transport-compatible schema never lets traversal reach DesignFacts."""
    structured = {
        "outcome": "accepted",
        "diagnostic": "",
        "design_facts": {
            "targets": [{"path": "src/example.py", "decision": "EXTEND"}],
            "paradigm": "object_oriented",
            "decisions": ["extend the existing seam"],
            "oracle": "tests/test_example.py",
            "acceptance_supports": ["tests/support.py"],
            "verification": [["python", "-m", "pytest", "-q"]],
        },
    }
    structured["design_facts"][field] = unsafe_value

    with pytest.raises(MalformedModelEnvelope, match="DesignFactsUnsafeLocator"):
        decode_model_run(structured, role_id="nw-solution-architect")


def test_shared_decoder_preserves_legacy_oracle_selector_boundaries() -> None:
    """The former lookahead admitted dot segments adjacent to ``::`` only."""
    structured = {
        "outcome": "accepted",
        "diagnostic": "",
        "design_facts": {
            "targets": [{"path": "src/example.py", "decision": "EXTEND"}],
            "paradigm": "object_oriented",
            "decisions": ["extend the existing seam"],
            "oracle": ".::../selector",
            "acceptance_supports": ["tests/support.py"],
            "verification": [["python", "-m", "pytest", "-q"]],
        },
    }

    run = decode_model_run(structured, role_id="nw-solution-architect")

    assert run.design_facts is not None
    assert run.design_facts.oracle == ".::../selector"
