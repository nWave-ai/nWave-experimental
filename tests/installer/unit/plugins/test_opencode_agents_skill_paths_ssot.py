"""AC-4 acceptance test -- OpenCode agents on the shared SSOT helper.

Feature: installer-per-host-skill-path-portability.

Post-refactor, the OpenCode agents plugin replaces its hardcoded
body.replace("~/.claude/skills/", ...) with the shared helper
rewrite_host_paths(body, "opencode"), then appends the shared batching
fragment. The contract:
  - skills paths still rewritten to ~/.config/opencode/skills/
  - the ~/.claude/lib/python exception is preserved (NOT rewritten)
  - output equals shared host rewrite plus shared batching append.

ACTIVE-RED (atdd_pure): the shared helper module
scripts.shared.skill_path_rewrite does NOT exist yet, so importing it raises
ModuleNotFoundError (an ImportError subclass) at collection -> right-reason RED.
"""

from pathlib import Path
from unittest.mock import MagicMock

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.opencode_agents_plugin import OpenCodeAgentsPlugin
from scripts.install.plugins.opencode_common import parse_frontmatter
from scripts.shared.batching_fragment import (
    append_batching_fragment,
    load_batching_fragment,
)

# Right-reason RED anchor: helper not yet created -> ModuleNotFoundError here.
from scripts.shared.skill_path_rewrite import rewrite_host_paths


_AGENT_WITH_SKILL_AND_LIB_PATHS = (
    "---\n"
    "name: nw-foo\n"
    "description: Some agent\n"
    "model: inherit\n"
    "tools: Read, Write, Edit, Bash\n"
    "maxTurns: 50\n"
    "---\n"
    "\n"
    "# nw-foo\n"
    "\n"
    "Load `~/.claude/skills/nw-foo/SKILL.md`.\n"
    "DES runtime lives at `~/.claude/lib/python` -- never rewritten.\n"
)


def _make_context(tmp_path):
    project_root = tmp_path / "project"
    framework_source = tmp_path / "framework"

    agents_source = project_root / "nWave" / "agents"
    agents_source.mkdir(parents=True)
    (project_root / "nWave" / "framework-catalog.yaml").write_text("agents: {}\n")

    # OpenCodeAgentsPlugin.install() loads nWave/templates/tool-batching-fragment.md
    # via context.project_root / "nWave"; seed it from the canonical file.
    templates_dir = project_root / "nWave" / "templates"
    templates_dir.mkdir(parents=True)
    source_fragment = (
        Path(__file__).resolve().parents[4]
        / "nWave"
        / "templates"
        / "tool-batching-fragment.md"
    )
    (templates_dir / "tool-batching-fragment.md").write_text(
        source_fragment.read_text(encoding="utf-8"), encoding="utf-8"
    )

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)

    context = InstallContext(
        claude_dir=claude_dir,
        scripts_dir=tmp_path / "scripts",
        templates_dir=tmp_path / "templates",
        logger=MagicMock(),
        project_root=project_root,
        framework_source=framework_source,
        dev_mode=True,
    )

    target = tmp_path / "home" / ".config" / "opencode" / "agents"
    return context, agents_source, target


class TestOpenCodeAgentsOnSharedSsotHelper:
    """OpenCode agents body rewrite delegates to the shared SSOT helper."""

    def test_opencode_agent_body_matches_shared_helper(self, tmp_path, monkeypatch):
        """
        GIVEN: An agent referencing ~/.claude/skills/ AND ~/.claude/lib/python
        WHEN: The OpenCode agents plugin installs it
        THEN: skills path -> ~/.config/opencode/skills/, lib/python preserved,
              and the installed body equals shared host rewrite plus shared batching append.

        CONTRACT_SHAPE: bounded-change
        Outcome anchor: design.md value (DISCUSS wave skipped — optional)
        """
        context, agents_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_agents_plugin._opencode_agents_dir",
            lambda: target,
        )
        (agents_source / "nw-foo.md").write_text(_AGENT_WITH_SKILL_AND_LIB_PATHS)

        OpenCodeAgentsPlugin().install(context)

        installed = (target / "nw-foo.md").read_text()
        _, installed_body = parse_frontmatter(installed)
        _, source_body = parse_frontmatter(_AGENT_WITH_SKILL_AND_LIB_PATHS)

        assert "~/.config/opencode/skills/" in installed_body
        assert "~/.claude/skills/" not in installed_body
        # Exception preserved.
        assert "~/.claude/lib/python" in installed_body, (
            "~/.claude/lib/python exception must NOT be rewritten"
        )
        # Behaviour-match with the shared helper (the SSOT contract).
        fragment = load_batching_fragment(context.project_root / "nWave")
        expected = append_batching_fragment(
            rewrite_host_paths(source_body, "opencode"), fragment
        )
        assert installed_body == expected
