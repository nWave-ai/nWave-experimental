"""Tests for simulate_plugin — plugin build simulation (step 02-02).

Validates that simulate_plugin() builds a plugin in a temp directory,
checks hooks.json for 5 event types, verifies agent/skill counts,
and reports PASS/FAIL via StepResult.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from scripts.release.simulate import Status, simulate_plugin


# ---------------------------------------------------------------------------
# Helpers: build a minimal valid plugin directory
# ---------------------------------------------------------------------------

EXPECTED_EVENT_TYPES = frozenset(
    ["PreToolUse", "PostToolUse", "SubagentStop", "SessionStart", "SubagentStart"]
)


def _create_minimal_plugin(plugin_dir: Path, *, agent_count: int = 23) -> None:
    """Create a minimal valid plugin structure for testing."""
    # hooks.json with 5 event types
    hooks_dir = plugin_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hooks_config = {
        "hooks": {
            event_type: [{"matcher": ".*", "hooks": [{"command": "echo test"}]}]
            for event_type in EXPECTED_EVENT_TYPES
        }
    }
    (hooks_dir / "hooks.json").write_text(json.dumps(hooks_config))

    # Agents
    agents_dir = plugin_dir / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    for i in range(agent_count):
        (agents_dir / f"nw-agent-{i}.md").write_text(f"# Agent {i}")

    # Skills
    skills_dir = plugin_dir / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    for i in range(5):
        skill_subdir = skills_dir / f"nw-skill-{i}"
        skill_subdir.mkdir(parents=True, exist_ok=True)
        (skill_subdir / "SKILL.md").write_text(f"# Skill {i}")


# ---------------------------------------------------------------------------
# Acceptance: simulate_plugin returns PASS for valid build
# ---------------------------------------------------------------------------


class TestSimulatePluginAcceptance:
    """Acceptance: simulate_plugin builds plugin and validates structure."""

    def test_valid_plugin_build_returns_pass(self, monkeypatch, tmp_path):
        """Given a working build_plugin that produces valid output,
        simulate_plugin should return PASS with counts."""

        def fake_build(config, *, version_override=None):
            """Fake build that creates a valid plugin structure."""
            from scripts.build_plugin import BuildResult

            _create_minimal_plugin(config.output_dir)
            return BuildResult(
                output_dir=config.output_dir,
                success=True,
                metadata={"version": "3.3.0"},
                steps=(),
            )

        monkeypatch.setattr("scripts.release.simulate.build", fake_build)

        result = simulate_plugin("3.3.0")

        assert result.status == Status.PASS
        assert result.name == "Plugin build"
        assert "5 event types" in result.message
        assert "23 agents" in result.message

    def test_temp_directory_is_cleaned_up(self, monkeypatch, tmp_path):
        """After simulate_plugin completes, no temp directory remains."""
        created_dirs: list[Path] = []

        original_mkdtemp = tempfile.mkdtemp

        def tracking_mkdtemp(**kwargs):
            d = original_mkdtemp(**kwargs)
            created_dirs.append(Path(d))
            return d

        monkeypatch.setattr(tempfile, "mkdtemp", tracking_mkdtemp)

        def fake_build(config, *, version_override=None):
            from scripts.build_plugin import BuildResult

            _create_minimal_plugin(config.output_dir)
            return BuildResult(
                output_dir=config.output_dir,
                success=True,
                metadata={"version": "3.3.0"},
                steps=(),
            )

        monkeypatch.setattr("scripts.release.simulate.build", fake_build)

        simulate_plugin("3.3.0")

        assert len(created_dirs) >= 1
        for d in created_dirs:
            assert not d.exists(), f"Temp dir {d} was not cleaned up"


# ---------------------------------------------------------------------------
# Unit: hooks.json validation
# ---------------------------------------------------------------------------


class TestSimulatePluginHooksValidation:
    """Unit: hooks.json must have exactly 5 event types."""

    def test_missing_event_type_returns_fail(self, monkeypatch):
        """hooks.json with only 4 event types should FAIL."""

        def fake_build(config, *, version_override=None):
            from scripts.build_plugin import BuildResult

            plugin_dir = config.output_dir
            _create_minimal_plugin(plugin_dir)
            # Remove one event type from hooks.json
            hooks_path = plugin_dir / "hooks" / "hooks.json"
            data = json.loads(hooks_path.read_text())
            del data["hooks"]["SessionStart"]
            hooks_path.write_text(json.dumps(data))
            return BuildResult(
                output_dir=plugin_dir,
                success=True,
                metadata={"version": "3.3.0"},
                steps=(),
            )

        monkeypatch.setattr("scripts.release.simulate.build", fake_build)

        result = simulate_plugin("3.3.0")

        assert result.status == Status.FAIL
        assert "event type" in result.message.lower()


# ---------------------------------------------------------------------------
# Unit: agent count validation
# ---------------------------------------------------------------------------


class TestSimulatePluginAgentCount:
    """Unit: plugin must have at least 20 agents."""

    def test_insufficient_agents_returns_fail(self, monkeypatch):
        """Fewer than 20 agents should FAIL."""

        def fake_build(config, *, version_override=None):
            from scripts.build_plugin import BuildResult

            _create_minimal_plugin(config.output_dir, agent_count=5)
            return BuildResult(
                output_dir=config.output_dir,
                success=True,
                metadata={"version": "3.3.0"},
                steps=(),
            )

        monkeypatch.setattr("scripts.release.simulate.build", fake_build)

        result = simulate_plugin("3.3.0")

        assert result.status == Status.FAIL
        assert "agent" in result.message.lower()


# ---------------------------------------------------------------------------
# Unit: build failure propagation
# ---------------------------------------------------------------------------


class TestSimulatePluginBuildFailure:
    """Unit: when build() fails, simulate_plugin returns FAIL."""

    def test_build_failure_returns_fail(self, monkeypatch):
        """Build failure should propagate as FAIL."""

        def fake_build(config, *, version_override=None):
            from scripts.build_plugin import BuildResult

            return BuildResult(
                output_dir=config.output_dir,
                success=False,
                error="Source tree missing",
            )

        monkeypatch.setattr("scripts.release.simulate.build", fake_build)

        result = simulate_plugin("3.3.0")

        assert result.status == Status.FAIL
        assert "Source tree missing" in result.message


# ---------------------------------------------------------------------------
# Unit: skills presence validation
# ---------------------------------------------------------------------------


class TestSimulatePluginSkillsPresence:
    """Unit: plugin must have skills present."""

    def test_no_skills_returns_fail(self, monkeypatch):
        """Zero skills should FAIL."""

        def fake_build(config, *, version_override=None):
            from scripts.build_plugin import BuildResult

            plugin_dir = config.output_dir
            _create_minimal_plugin(plugin_dir)
            # Remove skills directory
            import shutil

            shutil.rmtree(plugin_dir / "skills")
            return BuildResult(
                output_dir=plugin_dir,
                success=True,
                metadata={"version": "3.3.0"},
                steps=(),
            )

        monkeypatch.setattr("scripts.release.simulate.build", fake_build)

        result = simulate_plugin("3.3.0")

        assert result.status == Status.FAIL
        assert "skill" in result.message.lower()
