"""Characterization guard for DESPlugin._hooks_already_installed.

`_hooks_already_installed(config)` is live production code
(scripts/install/plugins/des_plugin.py:1071), called by verify()
(des_plugin.py:1249). Its documented contract:

    "Returns True if ANY hook event type has a DES hook. This handles
     cases where only partial hooks exist (e.g., old format)."

WTBD-165 / PR #89 retired the bug-1 "Hook detection works for both old and
new command formats" acceptance scenario. That scenario's step 2 ("the hook
detection should return True" for an OLD-format hook) was the ONLY test
exercising this method — after the retirement `grep -rn _hooks_already_installed
tests/` returned nothing. The stale strict count-equality step was correctly
dropped, but the *valid* old-format DETECTION assertion went with it. This
module restores that lost coverage directly at the unit level.

These are GREEN-now characterization tests of existing, correct behaviour —
they pin the method's documented contract, they do not drive new code.

Paradigm note (bypass): `_hooks_already_installed` is a pure boolean classifier
over a config dict with a single return value and no side effects. Per the
state-delta / PBT mandate this is an EXEMPT category (pure-function, single
output) — example-based tests expressing each documented branch are the
correct, minimal shape. There is no multi-slot state surface to declare.
"""

import json
import logging
from pathlib import Path

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.des_plugin import DESPlugin


# Old-format DES command shape, matching the retired scenario's
# `settings_with_old_format_hook` fixture
# (tests/bugs/plugins/des/installation/acceptance/steps/conftest.py:234).
# Flat entry, path-style invocation (not `-m`), carries the canonical
# "claude_code_hook_adapter" marker.
_OLD_FORMAT_COMMAND = (
    "python3 src/des/adapters/drivers/hooks/claude_code_hook_adapter.py pre-task"
)

# New-format DES command shape: nested `-m` module invocation, the format the
# canonical installer writes today.
_NEW_FORMAT_COMMAND = (
    "PYTHONPATH=/tmp/.claude/lib/python python3 -m "
    "des.adapters.drivers.hooks.claude_code_hook_adapter pre-task"
)


def _historical_affordance_command(event: str) -> str:
    """The exact standalone lifecycle command emitted by the retired registry."""
    return (
        "# des-hook:orchestrator-affordance-refresh-standalone\n"
        'python3 -c "import os,sys,runpy;from pathlib import Path;'
        "n='orchestrator_affordance_refresh.py';"
        "r=os.environ.get('CLAUDE_PLUGIN_ROOT','');h=os.environ.get('HOME','');"
        "c=[Path(r)/'scripts'/n] if r else [];"
        "c+=sorted(Path(h).joinpath('.claude/plugins/cache').glob('*/nw/*/scripts/'+n)) if h else [];"
        "c+=[Path(h)/'.claude'/'scripts'/n] if h else [];"
        "s=next((p for p in c if p.exists()),None);"
        f"sys.argv=[n,'{event}'];"
        "runpy.run_path(str(s),run_name='__main__') if s "
        "else sys.stderr.write('[orchestrator-affordance-refresh] script not found\\n')\""
    )


def _hook_context(tmp_path: Path) -> InstallContext:
    project_root = Path(__file__).resolve().parents[4]
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    return InstallContext(
        claude_dir=claude_dir,
        scripts_dir=project_root / "scripts" / "install",
        templates_dir=project_root / "nWave" / "templates",
        logger=logging.getLogger("test.des_plugin.retired_lifecycle"),
        project_root=project_root,
        framework_source=project_root / "nWave",
        dry_run=False,
    )


def _nested(command: str) -> dict:
    return {"hooks": [{"type": "command", "command": command}]}


def _write_lifecycle_fixture(context: InstallContext, plugin: DESPlugin) -> None:
    exact_session = _historical_affordance_command("SessionStart")
    exact_prompt = _historical_affordance_command("UserPromptSubmit")
    legacy_prompt_adapter = plugin._generate_hook_command(context, "user-prompt-submit")
    (context.claude_dir / "settings.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "SessionStart": [
                        _nested(exact_session),
                        _nested("python3 -m lyra.session_start"),
                        _nested(exact_session + " --user-supplied-argument"),
                    ],
                    "UserPromptSubmit": [
                        _nested(exact_prompt),
                        _nested(legacy_prompt_adapter),
                        _nested("python3 /opt/persona/prompt_context.py"),
                        _nested(exact_prompt + " --user-supplied-argument"),
                    ],
                }
            }
        )
    )


def _lifecycle_commands(context: InstallContext, event: str) -> list[str]:
    document = json.loads((context.claude_dir / "settings.json").read_text())
    return [entry["hooks"][0]["command"] for entry in document["hooks"][event]]


def test_old_format_hook_is_detected_as_installed():
    """An OLD-format (flat, path-style) DES hook returns True.

    This is the exact assertion the retired bug-1 scenario's step 2 covered:
    the partial/legacy installation must be recognised so install can clean up
    and reinstall. Regression guard for WTBD-165.
    """
    config = {
        "permissions": {"allow": []},
        "hooks": {
            "PreToolUse": [{"matcher": "Task", "command": _OLD_FORMAT_COMMAND}],
            "SubagentStop": [],
        },
    }

    assert DESPlugin()._hooks_already_installed(config) is True


def test_new_format_hook_is_detected_as_installed():
    """A NEW-format (nested `-m` module) DES hook returns True."""
    config = {
        "permissions": {"allow": []},
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Task",
                    "hooks": [{"type": "command", "command": _NEW_FORMAT_COMMAND}],
                }
            ],
        },
    }

    assert DESPlugin()._hooks_already_installed(config) is True


def test_non_des_hook_only_is_not_detected_as_installed():
    """A config whose only hook is non-DES returns False."""
    config = {
        "permissions": {"allow": []},
        "hooks": {
            "PreToolUse": [
                {"matcher": "Write", "command": "custom-write-validator.py"}
            ],
        },
    }

    assert DESPlugin()._hooks_already_installed(config) is False


def test_config_without_hooks_key_is_not_detected_as_installed():
    """A config with no "hooks" key returns False (the early-return branch)."""
    config = {"permissions": {"allow": []}}

    assert DESPlugin()._hooks_already_installed(config) is False


def test_reinstall_removes_only_exact_retired_lifecycle_hooks(tmp_path: Path):
    """Reinstall cleans its old lifecycle entries without touching Lyra or users."""
    context = _hook_context(tmp_path)
    plugin = DESPlugin()
    _write_lifecycle_fixture(context, plugin)

    result = plugin._install_des_hooks(context)

    assert result.success
    assert _lifecycle_commands(context, "SessionStart") == [
        "python3 -m lyra.session_start",
        _historical_affordance_command("SessionStart") + " --user-supplied-argument",
    ]
    assert _lifecycle_commands(context, "UserPromptSubmit") == [
        "python3 /opt/persona/prompt_context.py",
        _historical_affordance_command("UserPromptSubmit")
        + " --user-supplied-argument",
    ]


def test_uninstall_removes_only_exact_retired_lifecycle_hooks(tmp_path: Path):
    """Uninstall has the same narrow migration cleanup as reinstall."""
    context = _hook_context(tmp_path)
    plugin = DESPlugin()
    _write_lifecycle_fixture(context, plugin)

    result = plugin._uninstall_des_hooks(context)

    assert result.success
    assert _lifecycle_commands(context, "SessionStart") == [
        "python3 -m lyra.session_start",
        _historical_affordance_command("SessionStart") + " --user-supplied-argument",
    ]
    assert _lifecycle_commands(context, "UserPromptSubmit") == [
        "python3 /opt/persona/prompt_context.py",
        _historical_affordance_command("UserPromptSubmit")
        + " --user-supplied-argument",
    ]
