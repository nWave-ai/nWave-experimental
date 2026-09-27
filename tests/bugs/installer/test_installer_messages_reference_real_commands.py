"""Regression: installer success-surface messages must only ever name real
nWave commands.

Defect (audit AUDIT-installer.md #2, ALTA): the post-install Quick-start
panel (``install_nwave.py:show_installation_summary``) and the persisted
``nwave-manifest.txt`` (``install_utils.py:ManifestWriter.
write_install_manifest``) advertised ``/nw-develop`` and ``/nw-start`` --
neither exists. The real commands were ``/nw-deliver`` (Outside-In TDD
implementation with refactoring) and ``/nw-new`` (the feature-start wizard).
``/nw-new`` has since been retired: its Claude Code skill in ``cd0ce87c4``,
and its ``nWave/tasks/nw/new.md`` OpenCode and plugin command on 2026-09-21.
Wrong from the FIRST interaction offered after a declared-successful install,
and persisted to disk in the manifest (a durable reference, not a transient
terminal message).

Second defect (2026-09-17): the tasks directory is the SSOT for which commands
exist on OpenCode, not on Claude Code, where every command is a skill under
``nWave/skills/nw-<name>/``. So the Claude-facing manifest line and the
Claude ``CLAUDE.md`` section kept advertising ``/nw-new`` while the check below
passed. ``TestClaudeFacingSurfacesNameShippedSkills`` checks those surfaces
against the skills directory instead.

Fix: the two wrong tuples/strings were corrected. This module additionally
guards against RE-divergence: every ``/nw-*`` or ``$nw-*`` token that appears
in either surface must name a file that actually exists under
``nWave/tasks/nw/<name>.md`` -- the SSOT for which wave/utility commands
nWave ships. Full runtime derivation from that directory was judged
impractical here (the Quick-start panel deliberately uses shorter, curated
descriptions than the tasks' frontmatter, and spans multiple target-platform
branches with different prefixes); this mechanical existence check is the
alternative the audit calls for -- it fails the FUTURE edit that reintroduces
a stale or invented command name, without relying on a human re-reading
prose.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


pytestmark = pytest.mark.unit

_COMMAND_TOKEN_RE = re.compile(r"[/$](nw-[a-z][a-z-]*)")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _real_command_names() -> set[str]:
    """The SSOT: every command nWave ships, from nWave/tasks/nw/*.md."""
    tasks_dir = _project_root() / "nWave" / "tasks" / "nw"
    return {f"nw-{p.stem}" for p in tasks_dir.glob("*.md")}


def _assert_all_commands_are_real(text: str, *, surface: str) -> None:
    real = _real_command_names()
    assert real, "Sanity check: nWave/tasks/nw/*.md must be discoverable"
    referenced = set(_COMMAND_TOKEN_RE.findall(text))
    unknown = sorted(referenced - real)
    assert not unknown, (
        f"{surface} references command(s) that do not exist in "
        f"nWave/tasks/nw/: {unknown}. Known real commands: {sorted(real)}"
    )


class TestQuickStartPanelReferencesRealCommands:
    """install_nwave.py:show_installation_summary Quick-start panel."""

    def test_no_nonexistent_command_in_quick_start(self, capsys):
        from scripts.install.install_nwave import show_installation_summary
        from scripts.install.install_utils import Logger

        logger = Logger(log_file=None)
        show_installation_summary(logger)

        captured = capsys.readouterr()
        _assert_all_commands_are_real(captured.out, surface="Quick-start panel")

    def test_nw_develop_and_nw_start_are_absent(self, capsys):
        """Direct encoding of the reported defect (belt-and-suspenders)."""
        from scripts.install.install_nwave import show_installation_summary
        from scripts.install.install_utils import Logger

        logger = Logger(log_file=None)
        show_installation_summary(logger)

        captured = capsys.readouterr()
        assert "nw-develop" not in captured.out
        assert "nw-start" not in captured.out


class TestManifestReferencesRealCommands:
    """install_utils.py:ManifestWriter.write_install_manifest persisted text."""

    def test_no_nonexistent_command_in_manifest(self, tmp_path):
        from scripts.install.install_utils import ManifestWriter

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        ManifestWriter.write_install_manifest(claude_dir, None, tmp_path)

        manifest_text = (claude_dir / "nwave-manifest.txt").read_text(encoding="utf-8")
        _assert_all_commands_are_real(manifest_text, surface="nwave-manifest.txt")

    def test_nw_develop_and_nw_start_are_absent(self, tmp_path):
        from scripts.install.install_utils import ManifestWriter

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        ManifestWriter.write_install_manifest(claude_dir, None, tmp_path)

        manifest_text = (claude_dir / "nwave-manifest.txt").read_text(encoding="utf-8")
        assert "nw-develop" not in manifest_text
        assert "nw-start" not in manifest_text


_CLAUDE_SECTION_BEGIN = "<!-- BEGIN nWave-beta-section"
_CLAUDE_SECTION_END = "<!-- END nWave-beta-section -->"


def _shipped_skill_names() -> set[str]:
    """The Claude Code SSOT: every command ships as nWave/skills/nw-<name>/."""
    skills_dir = _project_root() / "nWave" / "skills"
    return {p.name for p in skills_dir.glob("nw-*") if (p / "SKILL.md").is_file()}


def _assert_all_commands_are_shipped_skills(text: str, *, surface: str) -> None:
    shipped = _shipped_skill_names()
    assert shipped, "Sanity check: nWave/skills/nw-*/SKILL.md must be discoverable"
    referenced = set(_COMMAND_TOKEN_RE.findall(text))
    unknown = sorted(referenced - shipped)
    assert not unknown, (
        f"{surface} names command(s) that Claude Code does not ship as a skill "
        f"under nWave/skills/: {unknown}"
    )


class TestClaudeFacingSurfacesNameShippedSkills:
    """Claude-facing text must name only commands Claude Code actually installs."""

    def test_claude_manifest_names_only_shipped_skills(self, tmp_path):
        from scripts.install.install_utils import ManifestWriter

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        ManifestWriter.write_install_manifest(claude_dir, None, tmp_path)

        manifest_text = (claude_dir / "nwave-manifest.txt").read_text(encoding="utf-8")
        _assert_all_commands_are_shipped_skills(
            manifest_text, surface="nwave-manifest.txt (Claude Code)"
        )

    def test_claude_section_template_names_only_shipped_skills(self):
        template = (
            _project_root() / "nWave" / "templates" / "beta-project-claude-section.md"
        ).read_text(encoding="utf-8")
        _assert_all_commands_are_shipped_skills(
            template, surface="beta-project-claude-section.md"
        )

    def test_rendered_repository_claude_section_names_only_shipped_skills(self):
        text = (_project_root() / "CLAUDE.md").read_text(encoding="utf-8")
        start = text.find(_CLAUDE_SECTION_BEGIN)
        end = text.find(_CLAUDE_SECTION_END)
        assert 0 <= start < end, "CLAUDE.md must carry the managed nWave section"
        _assert_all_commands_are_shipped_skills(
            text[start:end], surface="CLAUDE.md managed nWave section"
        )
