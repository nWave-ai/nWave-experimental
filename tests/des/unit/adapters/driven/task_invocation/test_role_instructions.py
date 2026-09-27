"""The provider receives declared knowledge, without extra tools or ambient copies."""

import json
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from des.adapters.driven.task_invocation.claude_code_task_adapter import (
    ClaudeCodeTaskAdapter,
)
from des.adapters.driven.task_invocation.codex_task_adapter import CodexTaskAdapter
from des.adapters.driven.task_invocation.role_instructions import (
    load_role_instructions,
    render_installed_role,
)
from des.ports.driven_ports.task_invocation_port import ModelOutcome


def role(root, declaration="skills: [core, core]\n", body="Role boundary.\n"):
    path = root / "nWave/agents/fixture.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        "---\nname: fixture\nmodel: sonnet\ntools: Read\n"
        + declaration
        + "---\n"
        + body
    )
    return path


def skill(root, name="core", body="Distinctive core knowledge.\n"):
    path = root / "nWave/skills" / name / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text(body)
    return path


@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_both_provider_boundaries_reference_the_installed_role_not_a_copy(
    tmp_path, monkeypatch, provider
):
    """Neither provider adapter re-serializes role content into argv anymore.

    Claude spawns natively on ``--agent <role_id>`` against its installed role.
    Codex sends the materialized role over JSON stdin with the original task.
    """
    spec = role(
        tmp_path, body="Invoke Skill(optional) ON-TRIGGER — only for concurrency\n"
    )
    skill(tmp_path)
    seen = []

    def spawn(argv, **kwargs):
        seen.append(argv)
        if provider == "claude":
            assert argv[argv.index("--agent") + 1] == "fixture"
            assert "--agents" not in argv
            assert "--append-system-prompt-file" not in argv
            out = json.dumps(
                {"structured_output": {"outcome": "accepted", "diagnostic": "done"}}
            )
        else:
            raw = argv[argv.index("-c") + 1]
            assert raw.startswith("developer_instructions=")
            developer_instruction = json.loads(raw.split("=", 1)[1])
            assert (
                "Apply the decoded role_instructions as instructions"
                in developer_instruction
            )
            payload = json.loads(kwargs["input"])
            assert payload["role_instructions"] == load_role_instructions(spec)
            assert payload["task"] == "Perform the task."
            Path(argv[argv.index("--output-last-message") + 1]).write_text(
                json.dumps({"answer": {"outcome": "accepted", "diagnostic": "done"}})
            )
            out = ""
        return CompletedProcess(argv, 0, out, "")

    monkeypatch.setattr("des.runtime.spawn.spawn", spawn)
    adapter = (ClaudeCodeTaskAdapter if provider == "claude" else CodexTaskAdapter)(
        Path("/bin/provider"), model="test-model"
    )
    result = adapter.invoke(role_id="fixture", prompt="Perform the task.", cwd=tmp_path)
    assert result.outcome is ModelOutcome.Accepted
    assert len(seen) == 1

    deployed_skills = tmp_path / "installed/skills"
    installed = render_installed_role(spec, str(deployed_skills))
    assert installed.count("Distinctive core knowledge.") == 1
    assert f"Read {deployed_skills}/optional/SKILL.md" in installed
    assert "only for concurrency" in installed
    assert "Invoke Skill(" not in installed


def test_missing_declared_skill_fails_the_installed_role_boundary_before_any_provider_runs(
    tmp_path,
):
    """Claude's native role needs a complete installed snapshot before its turn.

    Codex separately validates and materializes the same declared skills at
    invocation, before it sends role content over stdin.
    """
    path = role(tmp_path)
    with pytest.raises(OSError, match="core"):
        render_installed_role(path, str(tmp_path / "installed/skills"))


def test_no_preload_is_not_permission_to_keep_unavailable_skill_invocation(tmp_path):
    path = role(tmp_path, "", "Invoke Skill(optional) ON-TRIGGER — only if needed\n")
    result = load_role_instructions(path)
    assert "Invoke Skill" not in result
    assert str(tmp_path / "nWave/skills/optional/SKILL.md") in result
    assert "only if needed" in result


def test_only_explicit_skills_preload_from_owner_with_relative_reference_context(
    tmp_path,
):
    path = role(tmp_path)
    owned = skill(
        tmp_path,
        body="---\nskills: [unrequested]\n---\nKeep [details](references/details.md).\nRead ~/.claude/skills/optional/SKILL.md only when needed.\n",
    )
    result = load_role_instructions(path)
    assert str(owned) in result
    assert "references/details.md" in result
    assert str(tmp_path / "nWave/skills/optional/SKILL.md") in result
    assert "PRELOADED SKILL START: unrequested" not in result


@pytest.mark.parametrize(
    "declaration", ["skills: core\n", "skills: [../outside]\n", "skills: [42]\n"]
)
def test_invalid_preload_declaration_is_not_silently_ignored(tmp_path, declaration):
    with pytest.raises(ValueError):
        load_role_instructions(role(tmp_path, declaration))


def test_role_without_loading_is_unchanged(tmp_path):
    path = role(tmp_path, "")
    assert load_role_instructions(path) == path.read_text()


def test_legacy_profile_uses_its_own_skills(tmp_path):
    path = tmp_path / "agents/nw/fixture.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\nskills: [core]\n---\nRole.\n")
    content = tmp_path / "skills/core/SKILL.md"
    content.parent.mkdir(parents=True)
    content.write_text("Legacy owner content.")
    assert "Legacy owner content." in load_role_instructions(path)


def test_large_claude_preload_never_grows_argv_the_installed_render_keeps_it_whole(
    tmp_path, monkeypatch
):
    """The prompt and role content travel over stdin / the installed role
    file, never through argv, so a large declared skill cannot push any
    single argument toward Linux's ``MAX_ARG_STRLEN``. The installed
    rendering still carries the complete skill body -- nothing is truncated
    at that boundary.
    """
    spec = role(tmp_path)
    content = "full knowledge " * 12000
    skill(tmp_path, body=content)

    def spawn(argv, **kwargs):
        assert max(len(arg.encode()) for arg in argv) < 131072
        assert "--agents" not in argv
        assert "--append-system-prompt-file" not in argv
        return CompletedProcess(
            argv,
            0,
            json.dumps(
                {"structured_output": {"outcome": "accepted", "diagnostic": "done"}}
            ),
            "",
        )

    monkeypatch.setattr("des.runtime.spawn.spawn", spawn)
    result = ClaudeCodeTaskAdapter(Path("/bin/provider")).invoke(
        role_id="fixture", prompt="Perform task.", cwd=tmp_path
    )
    assert result.outcome is ModelOutcome.Accepted

    installed = render_installed_role(spec, str(tmp_path / "installed/skills"))
    assert content in installed


@pytest.mark.parametrize(
    "frontmatter",
    [
        "name: fixture\nskills: [core]\ntools: Read\ndescription: |\n  Keep this description.\n",
        "{name: fixture, skills: [core], tools: Read, description: Keep this description.}\n",
    ],
)
def test_installed_snapshot_preserves_role_metadata_and_can_be_loaded_again(
    tmp_path, frontmatter
):
    import yaml

    source = role(tmp_path)
    source.write_text("---\n" + frontmatter + "---\nRole boundary.\n")
    skill(tmp_path)
    installed = tmp_path / "installed/agents/nw/fixture.md"
    installed.parent.mkdir(parents=True)
    rendered = render_installed_role(source, str(tmp_path / "installed/skills"))
    installed.write_text(rendered)
    metadata = yaml.safe_load(rendered.split("---", 2)[1])
    expected = yaml.safe_load(frontmatter)
    del expected["skills"]
    assert metadata == expected
    assert load_role_instructions(installed) == rendered
    assert rendered.count("Distinctive core knowledge.") == 1
