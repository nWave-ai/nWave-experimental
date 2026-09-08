"""The strip must not leave a public agent pointing at work it removed.

A public agent that survives the strip while its frontmatter still names a
removed skill ships a dangling instruction: the public user gets an agent
that loads a file the package does not contain, and nothing fails loudly.
This runs the production ``strip()`` against a planted fixture tree, never
the repository, so it keeps discriminating no matter which skills the real
catalog declares private.
"""

import sys
from pathlib import Path

import pytest
import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.release.strip_private_agents import strip


PUBLIC_AGENT = """---
name: nw-widget-maker
description: public agent
skills:
  - nw-open-lens
  - nw-secret-lens
---

# Widget Maker

| ALWAYS at start | `~/.claude/skills/nw-open-lens/SKILL.md` | context |
"""

PRIVATE_AGENT = """---
name: nw-backroom
description: private agent
skills:
  - nw-secret-lens
---

# Backroom
"""

CATALOG = """name: test
agents:
  widget-maker:
    public: true
    description: public
  backroom:
    public: false
    description: private
skills:
  nw-secret-lens:
    public: false
    description: declared private while a public agent still owns it
"""


@pytest.fixture
def planted_tree(tmp_path):
    """A public agent whose frontmatter names a catalog-declared private skill."""
    nwave = tmp_path / "nWave"
    (nwave / "agents").mkdir(parents=True)
    (nwave / "agents" / "nw-widget-maker.md").write_text(PUBLIC_AGENT, encoding="utf-8")
    (nwave / "agents" / "nw-backroom.md").write_text(PRIVATE_AGENT, encoding="utf-8")
    (nwave / "framework-catalog.yaml").write_text(CATALOG, encoding="utf-8")
    for skill in ("nw-open-lens", "nw-secret-lens"):
        d = nwave / "skills" / skill
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            f"---\nname: {skill}\nuser-invocable: false\n"
            f"disable-model-invocation: true\n---\n",
            encoding="utf-8",
        )
    return tmp_path


def _frontmatter(agent_file: Path) -> dict:
    text = agent_file.read_text(encoding="utf-8")
    assert text.startswith("---"), "frontmatter must survive intact"
    return yaml.safe_load(text[3 : text.index("---", 3)])


class TestStripScrubsRemovedSkillReferences:
    def test_removed_skill_is_dropped_from_the_public_agent_frontmatter(
        self, planted_tree
    ):
        removed = strip(planted_tree)
        assert "nWave/skills/nw-secret-lens" in removed["skills"], (
            "fixture precondition: the strip must remove the privately-owned skill"
        )
        agent = planted_tree / "nWave" / "agents" / "nw-widget-maker.md"
        assert _frontmatter(agent)["skills"] == ["nw-open-lens"]

    def test_the_scrub_is_reported(self, planted_tree):
        removed = strip(planted_tree)
        assert any("nw-widget-maker" in entry for entry in removed["references"]), (
            f"the scrub must be reported, got {removed['references']}"
        )

    def test_a_surviving_skill_reference_is_untouched(self, planted_tree):
        """Falsifier: the scrub removes only what the strip actually removed."""
        strip(planted_tree)
        agent = planted_tree / "nWave" / "agents" / "nw-widget-maker.md"
        assert "nw-open-lens" in _frontmatter(agent)["skills"]

    def test_the_rest_of_the_agent_file_is_untouched(self, planted_tree):
        """Falsifier: a line-scoped edit, not a YAML round-trip rewrite."""
        strip(planted_tree)
        text = (planted_tree / "nWave" / "agents" / "nw-widget-maker.md").read_text(
            encoding="utf-8"
        )
        assert "# Widget Maker" in text
        assert "`~/.claude/skills/nw-open-lens/SKILL.md`" in text
        assert "description: public agent" in text

    def test_no_skill_removed_means_no_rewrite(self, tmp_path):
        """Falsifier: nothing is rewritten when the strip removes no skill."""
        nwave = tmp_path / "nWave"
        (nwave / "agents").mkdir(parents=True)
        (nwave / "agents" / "nw-widget-maker.md").write_text(
            "---\nname: nw-widget-maker\nskills:\n  - nw-open-lens\n---\n\nbody\n",
            encoding="utf-8",
        )
        (nwave / "framework-catalog.yaml").write_text(
            "name: t\nagents:\n  widget-maker:\n    public: true\nskills: {}\n",
            encoding="utf-8",
        )
        d = nwave / "skills" / "nw-open-lens"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("---\nname: nw-open-lens\n---\n", encoding="utf-8")
        before = (nwave / "agents" / "nw-widget-maker.md").read_text(encoding="utf-8")
        removed = strip(tmp_path)
        assert removed["skills"] == []
        assert removed["references"] == []
        assert (nwave / "agents" / "nw-widget-maker.md").read_text(
            encoding="utf-8"
        ) == before
