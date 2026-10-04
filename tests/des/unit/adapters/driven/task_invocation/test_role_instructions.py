"""The provider receives declared knowledge, without extra tools or ambient copies."""

import pytest

from des.adapters.driven.task_invocation.role_instructions import (
    load_role_instructions,
    render_installed_role,
)


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


_LATE_INDEX = (
    "# Fixture role\nWorkflow step one.\nWorkflow step two.\n"
    "<!-- GENERATED:role-skill-loading START -->\n"
    "- Read `~/.claude/skills/optional/SKILL.md` ON-TRIGGER — a rare condition\n"
    "<!-- GENERATED:role-skill-loading END -->\n"
)


@pytest.mark.parametrize(
    "render",
    [
        load_role_instructions,
        lambda path: render_installed_role(path, "~/.agents/skills"),
    ],
    ids=["runtime", "installed"],
)
def test_conditional_index_precedes_the_role_body_wherever_the_source_puts_it(
    tmp_path, render
):
    """A role reads its conditional index before its workflow, in every
    projection, even when the source carries the index after the workflow."""
    skill(tmp_path)
    result = render(role(tmp_path, body=_LATE_INDEX))
    index = result.index("ON-TRIGGER — a rare condition")
    assert result.count("ON-TRIGGER — a rare condition") == 1
    assert index < result.index("# Fixture role")
    assert index < result.index("Workflow step two.")
    assert result.startswith("---\n")


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
