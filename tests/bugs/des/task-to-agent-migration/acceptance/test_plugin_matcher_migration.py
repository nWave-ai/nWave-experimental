"""
Regression Tests: DES Plugin Hook Matcher Migration (Task -> Agent)

PROBLEM STATEMENT:
Claude Code v2.1.63 renamed the "Task" tool to "Agent". The DES plugin
generates hook configuration in settings.json with "matcher" values that
tell Claude Code which tool invocations should trigger each hook.

With "matcher": "Task", hooks never fire because Claude Code now sends
tool_name="Agent" for agent invocations. The DES plugin must generate
"matcher": "Agent" for PreToolUse and PostToolUse hooks.

EXPECTED BEHAVIOR:
- DESPlugin._install_des_hooks generates PreToolUse hook with matcher "Agent"
- DESPlugin._install_des_hooks generates PostToolUse hook with matcher "Agent"
- SubagentStop hook has no matcher (fires for all subagent stops) - unchanged

BUSINESS IMPACT:
With "Task" matchers, ALL DES hooks silently stop firing, disabling the
entire Deterministic Execution System without any error message.
"""

import json
import logging
from pathlib import Path

import pytest

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.des_plugin import DESPlugin


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def test_logger() -> logging.Logger:
    """Provide a configured logger for test execution."""
    logger = logging.getLogger("test.plugin_matcher_migration")
    logger.setLevel(logging.DEBUG)
    return logger


@pytest.fixture
def project_root() -> Path:
    """Return the nWave project root directory."""
    current = Path(__file__).resolve()
    # tests/bugs/des/task-to-agent-migration/acceptance/ -> 5 levels up
    return current.parents[4]


@pytest.fixture
def install_context(
    tmp_path: Path, project_root: Path, test_logger: logging.Logger
) -> InstallContext:
    """Create InstallContext with minimal settings.json for hook testing."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    # Create empty settings.json (hooks will be added by plugin)
    settings_file = claude_dir / "settings.json"
    settings_file.write_text("{}")

    return InstallContext(
        claude_dir=claude_dir,
        scripts_dir=project_root / "scripts" / "install",
        templates_dir=project_root / "nWave" / "templates",
        logger=test_logger,
        project_root=project_root,
        framework_source=project_root / "nWave",
        dry_run=False,
    )


def _read_settings(context: InstallContext) -> dict:
    """Read the settings.json produced by hook installation."""
    settings_file = context.claude_dir / "settings.json"
    with open(settings_file, encoding="utf-8") as f:
        return json.load(f)


def _find_des_hooks(hooks_list: list[dict], matcher_value: str) -> list[dict]:
    """Find hook entries matching a given matcher value."""
    return [h for h in hooks_list if h.get("matcher") == matcher_value]


def _find_des_agent_hooks(hooks_list: list[dict]) -> list[dict]:
    """Find DES hooks that use 'claude_code_hook_adapter' in their command."""
    results = []
    for hook in hooks_list:
        for inner in hook.get("hooks", []):
            if "claude_code_hook_adapter" in inner.get("command", ""):
                results.append(hook)
                break
    return results


class TestPluginMatcherMigration:
    """Tests that DES plugin generates correct hook matchers after migration.

    The DES plugin must generate "Agent" matchers (not "Task") for PreToolUse
    and PostToolUse hooks. SubagentStop has no matcher (unchanged).

    These tests invoke through the DES plugin's hook installation method,
    which is the driving port for hook configuration generation.
    """

    def test_des_plugin_generates_agent_matcher_for_pre_tool_use(
        self, install_context: InstallContext
    ):
        """
        GIVEN the DES installation plugin
        WHEN it generates PreToolUse hook configuration
        THEN the DES hook matcher is "Agent" (not "Task")

        This ensures hooks fire when Claude Code sends tool_name="Agent"
        for agent invocations.
        """
        # GIVEN: DES plugin
        plugin = DESPlugin()

        # WHEN: Install hooks
        result = plugin._install_des_hooks(install_context)

        # THEN: Installation succeeded
        assert result.success, f"Hook installation failed: {result.message}"

        # THEN: PreToolUse has an "Agent" matcher for the DES hook
        settings = _read_settings(install_context)
        pre_tool_use_hooks = settings.get("hooks", {}).get("PreToolUse", [])

        # Find DES-specific hooks (containing claude_code_hook_adapter)
        des_hooks = _find_des_agent_hooks(pre_tool_use_hooks)
        assert len(des_hooks) > 0, (
            "Should have at least one DES hook in PreToolUse. "
            f"Found hooks: {pre_tool_use_hooks}"
        )

        # The DES pre-task hook should have matcher "Agent"
        des_pretask_hook = des_hooks[0]
        assert des_pretask_hook.get("matcher") == "Agent", (
            f"DES PreToolUse hook matcher should be 'Agent'. "
            f"Got: {des_pretask_hook.get('matcher')}"
        )

        # Verify no "Task" matcher exists for DES hooks
        task_matchers = _find_des_hooks(pre_tool_use_hooks, "Task")
        des_task_hooks = [
            h
            for h in task_matchers
            if any(
                "claude_code_hook_adapter" in inner.get("command", "")
                for inner in h.get("hooks", [])
            )
        ]
        assert len(des_task_hooks) == 0, (
            f"No DES hooks should use 'Task' matcher. Found: {des_task_hooks}"
        )

    def test_des_plugin_generates_agent_matcher_for_post_tool_use(
        self, install_context: InstallContext
    ):
        """
        GIVEN the DES installation plugin
        WHEN it generates PostToolUse hook configuration
        THEN the DES hook matcher is "Agent" (not "Task")

        PostToolUse hooks clean up DES task signals after agent completion.
        They must also fire for the renamed Agent tool.
        """
        # GIVEN: DES plugin
        plugin = DESPlugin()

        # WHEN: Install hooks
        result = plugin._install_des_hooks(install_context)

        # THEN: Installation succeeded
        assert result.success, f"Hook installation failed: {result.message}"

        # THEN: PostToolUse has an "Agent" matcher for the DES hook
        settings = _read_settings(install_context)
        post_tool_use_hooks = settings.get("hooks", {}).get("PostToolUse", [])

        des_hooks = _find_des_agent_hooks(post_tool_use_hooks)
        assert len(des_hooks) > 0, (
            "Should have at least one DES hook in PostToolUse. "
            f"Found hooks: {post_tool_use_hooks}"
        )

        des_post_hook = des_hooks[0]
        assert des_post_hook.get("matcher") == "Agent", (
            f"DES PostToolUse hook matcher should be 'Agent'. "
            f"Got: {des_post_hook.get('matcher')}"
        )

        # Verify no "Task" matcher exists for DES hooks
        task_matchers = _find_des_hooks(post_tool_use_hooks, "Task")
        des_task_hooks = [
            h
            for h in task_matchers
            if any(
                "claude_code_hook_adapter" in inner.get("command", "")
                for inner in h.get("hooks", [])
            )
        ]
        assert len(des_task_hooks) == 0, (
            f"No DES hooks should use 'Task' matcher. Found: {des_task_hooks}"
        )

    def test_subagent_stop_hook_has_no_matcher(self, install_context: InstallContext):
        """
        GIVEN the DES installation plugin
        WHEN it generates SubagentStop hook configuration
        THEN the hook has no matcher (fires for all subagent stops)

        SubagentStop hooks are unaffected by the Task-to-Agent migration
        because they never had a tool matcher -- they fire on subagent
        completion regardless of tool name.
        """
        # GIVEN: DES plugin
        plugin = DESPlugin()

        # WHEN: Install hooks
        result = plugin._install_des_hooks(install_context)

        # THEN: Installation succeeded
        assert result.success, f"Hook installation failed: {result.message}"

        # THEN: SubagentStop hook has no matcher
        settings = _read_settings(install_context)
        subagent_stop_hooks = settings.get("hooks", {}).get("SubagentStop", [])

        des_hooks = _find_des_agent_hooks(subagent_stop_hooks)
        assert len(des_hooks) > 0, (
            "Should have at least one DES hook in SubagentStop. "
            f"Found hooks: {subagent_stop_hooks}"
        )

        des_stop_hook = des_hooks[0]
        assert "matcher" not in des_stop_hook, (
            f"SubagentStop hook should have no matcher. Got: {des_stop_hook}"
        )
