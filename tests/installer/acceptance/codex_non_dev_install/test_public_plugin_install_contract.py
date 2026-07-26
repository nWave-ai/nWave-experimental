"""Regression AT for the isolated non-development Codex install contract."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import tomllib

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.codex_agents_plugin import CodexAgentsPlugin
from scripts.install.plugins.codex_skills_plugin import CodexSkillsPlugin


CLAUDE_LABELS = (
    "inherit",
    "haiku",
    "sonnet",
    "opus",
    "claude-haiku-4-5",
    "claude-sonnet-4-5",
    "claude-opus-4-1",
)


def test_non_dev_public_install_never_loses_portable_codex_assets(
    tmp_path: Path, monkeypatch
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: EXP-fix-codex-bootstrap-spine-1 (Expected observations).

    Witness portable artifacts; reject each known lossy install mutation.
    """
    project = tmp_path / "project"
    framework = project / "nWave"
    skills = framework / "skills"
    agents = framework / "agents"
    skills.mkdir(parents=True)
    agents.mkdir()

    command = skills / "nw-design"
    command.mkdir()
    (command / "SKILL.md").write_text(
        "---\nname: nw-design\ndescription: Design\n"
        "user-invocable: true\n---\n\n# Design\n",
        encoding="utf-8",
    )

    resource_skill = skills / "nw-public-resource"
    (resource_skill / "resources").mkdir(parents=True)
    (resource_skill / "SKILL.md").write_text(
        "---\nname: nw-public-resource\ndescription: Resource skill\n"
        "user-invocable: false\ndisable-model-invocation: true\n---\n\n"
        "Read [the companion](resources/guide.md).\n",
        encoding="utf-8",
    )
    (resource_skill / "resources" / "guide.md").write_text(
        "COMPANION RESOURCE WITNESS\n", encoding="utf-8"
    )

    catalog = ["name: fixture", "agents:"]
    for index, label in enumerate(CLAUDE_LABELS):
        name = f"fixture-agent-{index}"
        catalog.extend((f"  {name}:", "    public: true"))
        (agents / f"nw-{name}.md").write_text(
            "---\n"
            f"name: nw-{name}\n"
            f"description: Fixture {label}\n"
            f"model: {label}\n"
            "skills:\n  - nw-public-resource\n"
            "---\n\n"
            'Hostile body: """ and invalid-basic-string escape C:\\agent\\q.\n',
            encoding="utf-8",
        )
    (framework / "framework-catalog.yaml").write_text(
        "\n".join(catalog) + "\n", encoding="utf-8"
    )

    isolated_home = tmp_path / "home"
    codex_home = isolated_home / ".codex"
    codex_home.mkdir(parents=True)
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("NWAVE_AGENTS_HOME", str(isolated_home))

    context = InstallContext(
        claude_dir=tmp_path / ".claude",
        scripts_dir=project / "scripts",
        templates_dir=framework / "templates",
        logger=MagicMock(),
        project_root=project,
        framework_source=framework,
        dev_mode=False,
    )
    skill_result = CodexSkillsPlugin().install(context)
    agent_result = CodexAgentsPlugin().install(context)
    assert skill_result.success and agent_result.success, (
        "WHAT: the two public Codex plugins did not complete. "
        "WHY: their installed tree is the user-visible contract. "
        "HOW: keep both non-dev plugin entry points installable."
    )

    installed_skills = isolated_home / ".agents" / "skills"
    # Witness/mutation: a core command exists / is not filtered as unowned.
    assert (installed_skills / "nw-design" / "SKILL.md").is_file(), (
        "WHAT: non-dev install omitted nw-design/SKILL.md. "
        "WHY: core user-invocable commands must remain callable. "
        "HOW: detect command-skills and supply them to public-skill filtering."
    )
    # Witness/mutation: the declared resource exists / is not a SKILL.md-only copy.
    companion = installed_skills / "nw-public-resource" / "resources" / "guide.md"
    assert companion.read_text(encoding="utf-8") == "COMPANION RESOURCE WITNESS\n", (
        "WHAT: the public skill lost its declared companion resource. "
        "WHY: SKILL.md now points at a broken installed path. "
        "HOW: preserve the complete flat skill directory."
    )

    policies = sorted((codex_home / "agents").glob("nw-fixture-agent-*.toml"))
    assert len(policies) == len(CLAUDE_LABELS), (
        "WHAT: the installed agent-policy population is incomplete. "
        "WHY: every public fixture label must be checked. "
        "HOW: emit every catalogued public agent."
    )
    parsed = [tomllib.loads(path.read_text(encoding="utf-8")) for path in policies]
    leaked = {
        policy["name"]: policy["model"]
        for policy in parsed
        if policy.get("model") in CLAUDE_LABELS
        or str(policy.get("model", "")).startswith("claude-")
    }
    assert not leaked, (
        "WHAT: Claude-only labels became Codex model policy. "
        f"Observed: {leaked!r}. WHY: those labels cannot select Codex models. "
        "HOW: omit them unless an explicit Codex mapping exists."
    )
