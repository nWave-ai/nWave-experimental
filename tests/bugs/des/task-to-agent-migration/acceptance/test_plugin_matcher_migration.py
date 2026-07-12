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

Track WS-15 P2 collapse (2026-07-12): migration stable since 2026-06-20
(22 days, no follow-up bug citing this migration). Per skill 3.5 the
3-scenario net collapses to 1 single-iteration test reporting all
violations at once (skill 3.2 dict-iteration) -- the per-hook expected
matcher table remains a module-level constant so a failure still
identifies WHICH hook regressed.
"""

import json
import logging
from pathlib import Path

import pytest

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.des_plugin import DESPlugin


# hook name -> expected matcher value (None means "no matcher key at all")
EXPECTED_MATCHERS = {
    "PreToolUse": "Agent",
    "PostToolUse": "Agent",
    "SubagentStop": None,
}


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


def _find_des_agent_hooks(hooks_list: list[dict]) -> list[dict]:
    """Find DES hooks that use 'claude_code_hook_adapter' in their command."""
    results = []
    for hook in hooks_list:
        for inner in hook.get("hooks", []):
            if "claude_code_hook_adapter" in inner.get("command", ""):
                results.append(hook)
                break
    return results


def test_des_plugin_hook_matchers_match_agent_tool_baseline(
    install_context: InstallContext,
) -> None:
    """Every DES hook's matcher must match the post-migration baseline.

    Iterates EXPECTED_MATCHERS once; failure message lists every hook whose
    matcher drifted (expected vs actual side by side), so a single failure
    is as diagnosable as the pre-collapse 3-test version. This is THE key
    regression: with "Task" matchers, ALL DES hooks silently stop firing
    because Claude Code v2.1.63 sends tool_name="Agent", not "Task".
    """
    plugin = DESPlugin()
    result = plugin._install_des_hooks(install_context)
    assert result.success, f"Hook installation failed: {result.message}"

    settings = _read_settings(install_context)
    drifted: list[str] = []
    for hook_name, expected_matcher in EXPECTED_MATCHERS.items():
        hooks_for_name = settings.get("hooks", {}).get(hook_name, [])
        des_hooks = _find_des_agent_hooks(hooks_for_name)
        if not des_hooks:
            drifted.append(f"{hook_name}: no DES hook found (expected >= 1)")
            continue
        actual_matcher = des_hooks[0].get("matcher")
        if actual_matcher != expected_matcher:
            drifted.append(
                f"{hook_name}: expected matcher {expected_matcher!r}, "
                f"got {actual_matcher!r}"
            )

    assert not drifted, (
        "DES hook matchers drifted from the Task->Agent migration baseline:\n  "
        + "\n  ".join(drifted)
    )
