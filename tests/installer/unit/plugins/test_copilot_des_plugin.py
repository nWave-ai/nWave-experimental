"""Unit witnesses for the Copilot DES hook installer.

The install-side contract is intentionally host-specific where Copilot's hook
schema differs, while retaining the common nWave guarantees: a host-neutral
runtime is wired, nWave owns only its own hook file, and uninstall preserves
the operator's unrelated configuration.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.copilot_des_plugin import CopilotDESPlugin


def _context_with_host_neutral_des(tmp_path: Path) -> InstallContext:
    """Build a Copilot-targeted context with only the shared runtime present."""
    project_root = tmp_path / "project"
    framework_source = project_root / "nWave"
    framework_source.mkdir(parents=True)
    (tmp_path / ".nwave" / "runtime" / "des").mkdir(parents=True)
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()

    return InstallContext(
        claude_dir=claude_dir,
        scripts_dir=project_root / "scripts",
        templates_dir=framework_source / "templates",
        logger=MagicMock(),
        project_root=project_root,
        framework_source=framework_source,
        target_platforms={"copilot"},
    )


def test_copilot_install_wires_shared_runtime_without_erasing_user_hook_files(
    tmp_path: Path, monkeypatch
) -> None:
    """A Copilot user receives one valid DES hook and keeps unrelated hooks."""
    copilot_dir = tmp_path / "home" / ".copilot"
    user_hook = copilot_dir / "hooks" / "user-policy.json"
    user_hook.parent.mkdir(parents=True)
    user_hook.write_text('{"preToolUse": []}\n', encoding="utf-8")
    runtime_root = tmp_path / ".nwave" / "runtime"

    monkeypatch.setattr(
        "scripts.install.plugins.copilot_des_plugin._copilot_config_dir",
        lambda: copilot_dir,
    )
    monkeypatch.setattr(
        "scripts.install.plugins.copilot_des_plugin.host_neutral_runtime_dir",
        lambda: runtime_root,
    )
    monkeypatch.setattr(
        "scripts.install.plugins.copilot_des_plugin.resolve_python_command_for_spawn",
        lambda: "/opt/nwave-runtime/bin/python",
    )
    monkeypatch.setattr(
        "scripts.install.plugins.copilot_des_plugin.resolve_des_lib_path_for_spawn",
        lambda: "/opt/nwave-runtime/python",
    )

    plugin = CopilotDESPlugin()
    context = _context_with_host_neutral_des(tmp_path)
    installed = plugin.install(context)

    hook_path = copilot_dir / "hooks" / "nwave-des.json"
    manifest_path = copilot_dir / ".nwave-des-manifest.json"
    assert installed.success is True
    assert installed.installed_files == [hook_path]
    assert user_hook.read_text(encoding="utf-8") == '{"preToolUse": []}\n'

    hook_config = json.loads(hook_path.read_text(encoding="utf-8"))
    handler = hook_config["preToolUse"][0]
    assert handler["matcher"] == ".*"
    assert handler["hooks"] == [
        {
            "type": "command",
            "bash": (
                "PYTHONPATH=/opt/nwave-runtime/python "
                "/opt/nwave-runtime/bin/python -m "
                "des.adapters.drivers.hooks.claude_code_hook_adapter pre-tool-use"
            ),
            "timeoutSec": 30,
        }
    ]
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == {
        "hook_file": str(hook_path),
        "python_path": "/opt/nwave-runtime/bin/python",
        "pythonpath": "/opt/nwave-runtime/python",
    }
    assert plugin.verify(context).success is True

    assert plugin.uninstall(context).success is True
    assert not hook_path.exists()
    assert not manifest_path.exists()
    assert user_hook.read_text(encoding="utf-8") == '{"preToolUse": []}\n'
