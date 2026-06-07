"""Canary skill tests for auto-injection detection (ADR-006).

These tests verify that the canary skill:
1. Exists in source with known passphrase
2. Survives installation without content modification
3. Detects any injection or tampering

The canary skill is a sentinel: if its passphrase is modified or
content injected, we know the skill pipeline is compromised.
"""

import logging
from pathlib import Path

import pytest

from scripts.install.plugins.base import InstallContext, PluginResult
from scripts.install.plugins.skills_plugin import SkillsPlugin


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CANARY_SOURCE = PROJECT_ROOT / "nWave" / "skills" / "nw-canary" / "SKILL.md"
PASSPHRASE = "NWAVE_SKILL_INJECTION_ACTIVE_2026"


@pytest.mark.canary
class TestCanarySkillIntegrity:
    """Verify canary skill exists and is tamper-free."""

    def test_canary_skill_exists(self):
        """Canary SKILL.md must exist in the source tree."""
        assert CANARY_SOURCE.exists(), (
            f"Canary skill not found at {CANARY_SOURCE}. "
            "ADR-006 requires nw-canary/SKILL.md in nWave/skills/."
        )

    def test_canary_passphrase_intact(self):
        """Canary SKILL.md must contain the known passphrase unchanged."""
        content = CANARY_SOURCE.read_text(encoding="utf-8")
        assert PASSPHRASE in content, (
            f"Passphrase '{PASSPHRASE}' not found in canary skill. "
            "Content may have been modified or injected."
        )

    def test_canary_survives_install(self, tmp_path):
        """Canary skill must be present and unmodified after install."""
        # Arrange: create a minimal install context pointing at nWave/skills/
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        logger = logging.getLogger("canary-test")
        context = InstallContext(
            claude_dir=claude_dir,
            scripts_dir=tmp_path / "scripts",
            templates_dir=tmp_path / "templates",
            logger=logger,
            project_root=PROJECT_ROOT,
            framework_source=PROJECT_ROOT / "nWave",
        )

        # Act: run the skills plugin install
        plugin = SkillsPlugin()
        result: PluginResult = plugin.install(context)

        # Assert: install succeeded
        assert result.success, f"Skills install failed: {result.message}"

        # Assert: canary file exists in target
        installed_canary = claude_dir / "skills" / "nw-canary" / "SKILL.md"
        assert installed_canary.exists(), (
            "Canary skill was not installed to target directory. "
            "The skills plugin may be filtering it out."
        )

        # Assert: passphrase is intact (no injection or modification)
        installed_content = installed_canary.read_text(encoding="utf-8")
        assert PASSPHRASE in installed_content, (
            f"Passphrase '{PASSPHRASE}' not found in installed canary. "
            "Content was modified during installation."
        )

        # Assert: content matches source exactly (byte-for-byte)
        source_content = CANARY_SOURCE.read_text(encoding="utf-8")
        assert installed_content == source_content, (
            "Installed canary content differs from source. "
            "Something modified the file during installation."
        )
