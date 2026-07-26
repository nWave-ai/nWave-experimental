"""
Regression tests: the post-install manifest omits the installed skill count.

Bug (found by Vera's uncontaminated post-install examine, 2026-07-08): the
manifest (`nwave-manifest.txt`) reports `Total agents: N` and
`Total commands: M` but has NO line for the installed skill count. Vera
observed 207 skill dirs actually installed under `<claude_config_dir>/skills/`
-- unreported. A user reading the manifest cannot see that skills landed.

RCA locus: `ManifestWriter.write_install_manifest`
(`scripts/install/install_utils.py`, ~line 651) computes `agents_count` and
`commands_count` via `PathUtils.count_files(dir, "*.md")` but never computes
or emits an analogous skills count -- the manifest template has no
`- Total skills: ...` line.

This module authors the regression AT ONLY. The fix (adding the skills count
line, mirroring the existing agents/commands pattern) is NOT implemented here.
"""

from __future__ import annotations

import re

import pytest


try:
    from scripts.install.install_utils import ManifestWriter
except ImportError:  # pragma: no cover - direct-script import fallback
    from install_utils import ManifestWriter

pytestmark = pytest.mark.unit


def _seed_installed_tree(
    claude_dir, agents_count: int, commands_count: int, skills_count: int
):
    """Populate agents/commands/skills dirs with the given file counts.

    Mirrors the production layout: agents/*.md, commands/*.md, and one
    nw-*/SKILL.md directory per skill (per skills_plugin.py NEW_FLAT layout).
    """
    agents_dir = claude_dir / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    for i in range(agents_count):
        (agents_dir / f"nw-agent-{i}.md").write_text("# agent\n", encoding="utf-8")

    commands_dir = claude_dir / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)
    for i in range(commands_count):
        (commands_dir / f"nw-command-{i}.md").write_text(
            "# command\n", encoding="utf-8"
        )

    skills_dir = claude_dir / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    for i in range(skills_count):
        skill_dir = skills_dir / f"nw-skill-{i}"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text("# skill\n", encoding="utf-8")

    return agents_dir, commands_dir, skills_dir


@pytest.mark.parametrize(
    "agents_count,commands_count,skills_count",
    [
        pytest.param(35, 1, 207, id="representative-production-counts"),
        pytest.param(3, 1, 5, id="small-counts"),
        pytest.param(0, 0, 12, id="skills-only-no-agents-no-commands"),
    ],
)
def test_manifest_reports_skill_count_alongside_agents_and_commands(
    tmp_path, agents_count, commands_count, skills_count
):
    """GIVEN an install with agents, commands, and skills present
    WHEN the manifest is written
    THEN the manifest text reports a "Total skills: <n>" line matching the
    actual installed skill count -- not just agents and commands.
    """
    claude_dir = tmp_path / ".claude"
    _seed_installed_tree(claude_dir, agents_count, commands_count, skills_count)

    ManifestWriter.write_install_manifest(claude_dir, None, tmp_path)

    manifest_text = (claude_dir / "nwave-manifest.txt").read_text(encoding="utf-8")

    assert re.search(rf"Total skills:\s*{skills_count}\b", manifest_text), (
        f"Manifest should report 'Total skills: {skills_count}' alongside "
        f"agents/commands. Actual manifest:\n{manifest_text}"
    )


def test_manifest_never_silently_omits_skill_count_when_skills_are_installed(tmp_path):
    """GIVEN 207 skills are installed (Vera's exact observed count)
    WHEN the manifest is written
    THEN the manifest must NOT report agents+commands while staying silent
    about skills -- the exact bug: skills present on disk, absent from the
    manifest a user reads to verify what landed.
    """
    claude_dir = tmp_path / ".claude"
    _seed_installed_tree(
        claude_dir, agents_count=35, commands_count=1, skills_count=207
    )

    ManifestWriter.write_install_manifest(claude_dir, None, tmp_path)

    manifest_text = (claude_dir / "nwave-manifest.txt").read_text(encoding="utf-8")

    assert "total agents" in manifest_text.lower(), (
        "Sanity check: manifest should still report agents.\n"
        f"Actual manifest:\n{manifest_text}"
    )
    assert "skill" in manifest_text.lower(), (
        "Manifest silently omits any mention of skills despite 207 being "
        f"installed -- the exact reported bug. Actual manifest:\n{manifest_text}"
    )


@pytest.mark.parametrize(
    ("targets", "expects_claude"),
    [
        pytest.param(frozenset({"codex"}), False, id="codex-only"),
        pytest.param(frozenset({"claude_code", "codex"}), True, id="mixed"),
    ],
)
def test_targeted_manifest_labels_each_host_without_claude_only_claims(
    tmp_path, monkeypatch, targets, expects_claude
):
    """Codex target facts must not be reported as a universal Claude install."""
    claude_dir = tmp_path / ".claude"
    codex_home = tmp_path / ".codex"
    agents_home = tmp_path
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("NWAVE_AGENTS_HOME", str(agents_home))
    _seed_installed_tree(claude_dir, agents_count=3, commands_count=2, skills_count=5)
    (agents_home / ".agents" / "skills" / "nw-design").mkdir(parents=True)
    (agents_home / ".agents" / "skills" / "nw-design" / "SKILL.md").write_text(
        "# codex skill\n", encoding="utf-8"
    )
    (codex_home / "agents").mkdir(parents=True)
    (codex_home / "agents" / "nw-architect.toml").write_text(
        "# agent\n", encoding="utf-8"
    )
    (codex_home / "hooks.json").write_text("{}\n", encoding="utf-8")

    ManifestWriter.write_install_manifest(
        claude_dir, None, tmp_path, target_platforms=targets
    )

    manifest_text = (claude_dir / "nwave-manifest.txt").read_text(encoding="utf-8")
    assert "Target platforms: " in manifest_text
    assert "Codex skills: 1" in manifest_text
    assert "Codex agents: 1" in manifest_text
    assert "Total agents:" not in manifest_text
    assert "Installation directory:" not in manifest_text
    assert "'/nw-discuss'" not in manifest_text
    assert ("Claude Code agents: 3" in manifest_text) is expects_claude
