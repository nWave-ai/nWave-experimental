"""Unit tests for Cursor DES hook installer plugin.

Tests validate that:
- validate_prerequisites() skips when Cursor is not detected
- validate_prerequisites() fails when Cursor is present but DES missing
- install() writes a preToolUse entry into ~/.cursor/hooks.json
- install() writes a manifest and ensures agents/ exists
- reinstall is idempotent and preserves user hooks
- uninstall() removes only nWave entries
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from nwave_ai.state_delta import assert_state_delta, set_to

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.cursor_des_plugin import CursorDESPlugin


if TYPE_CHECKING:
    from pathlib import Path


def _make_context(
    tmp_path: Path,
    *,
    des_module_exists: bool = True,
) -> InstallContext:
    """Create an InstallContext with a configurable DES module presence."""
    project_root = tmp_path / "project"
    framework_source = project_root / "nWave"
    framework_source.mkdir(parents=True)

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    if des_module_exists:
        des_dir = claude_dir / "lib" / "python" / "des"
        des_dir.mkdir(parents=True)
        (des_dir / "__init__.py").write_text("", encoding="utf-8")

    return InstallContext(
        claude_dir=claude_dir,
        scripts_dir=project_root / "scripts",
        templates_dir=framework_source / "templates",
        logger=MagicMock(),
        project_root=project_root,
        framework_source=framework_source,
    )


def _patch_cursor_config_dir(monkeypatch, cursor_config_dir: Path) -> None:
    """Redirect _cursor_config_dir() to a tmp path."""
    monkeypatch.setattr(
        "scripts.install.plugins.cursor_des_plugin._cursor_config_dir",
        lambda: cursor_config_dir,
    )


def _patch_path_resolvers(monkeypatch) -> None:
    """Force deterministic Python and PYTHONPATH resolution."""
    monkeypatch.setattr(
        "scripts.install.plugins.cursor_des_plugin.resolve_python_command_for_spawn",
        lambda: "/usr/bin/python3",
    )
    monkeypatch.setattr(
        "scripts.install.plugins.cursor_des_plugin.resolve_des_lib_path_for_spawn",
        lambda: "/home/tester/.claude/lib/python",
    )


def _patch_cursor_binary_absent(monkeypatch) -> None:
    """Force shutil.which('cursor') to return None inside the plugin."""
    monkeypatch.setattr(
        "scripts.install.plugins.cursor_des_plugin._shutil.which",
        lambda _name: None,
    )


class TestValidatePrerequisites:
    """validate_prerequisites: skip / fail / proceed branches."""

    def test_skips_gracefully_when_cursor_not_detected(self, tmp_path, monkeypatch):
        """
        GIVEN: ~/.cursor/ does not exist AND `cursor` not in PATH
        WHEN: validate_prerequisites() runs
        THEN: Returns success with skip message
        """
        context = _make_context(tmp_path)
        cursor_config_dir = tmp_path / "home" / ".cursor"
        _patch_cursor_config_dir(monkeypatch, cursor_config_dir)
        _patch_cursor_binary_absent(monkeypatch)

        plugin = CursorDESPlugin()
        result = plugin.validate_prerequisites(context)

        assert result.success is True
        assert (
            "skip" in result.message.lower() or "not detected" in result.message.lower()
        )

    def test_fails_when_cursor_present_but_des_module_missing(
        self, tmp_path, monkeypatch
    ):
        """
        GIVEN: Cursor is detected but DES Python module is NOT
        WHEN: validate_prerequisites() runs
        THEN: Returns failure citing the DES module
        """
        context = _make_context(tmp_path, des_module_exists=False)
        cursor_config_dir = tmp_path / "home" / ".cursor"
        cursor_config_dir.mkdir(parents=True)
        _patch_cursor_config_dir(monkeypatch, cursor_config_dir)

        plugin = CursorDESPlugin()
        result = plugin.validate_prerequisites(context)

        assert result.success is False
        assert "des" in result.message.lower()


class TestInstallWritesHooksJsonAndManifest:
    """install: writes hooks.json with the nWave DES entry + manifest."""

    def test_install_creates_hooks_json_manifest_and_agents_dir(
        self, tmp_path, monkeypatch
    ):
        """
        GIVEN: Cursor detected and DES module installed
        WHEN: install() runs (no prior hooks.json)
        THEN: hooks.json contains preToolUse nWave entry, manifest exists,
              and agents/ directory exists.
        """
        context = _make_context(tmp_path)
        cursor_config_dir = tmp_path / "home" / ".cursor"
        cursor_config_dir.mkdir(parents=True)
        _patch_cursor_config_dir(monkeypatch, cursor_config_dir)
        _patch_path_resolvers(monkeypatch)

        hooks_path = cursor_config_dir / "hooks.json"
        manifest_path = cursor_config_dir / ".nwave-des-manifest.json"
        agents_dir = cursor_config_dir / "agents"

        tracked = {"hooks.exists", "manifest.exists", "agents.exists"}

        def snapshot() -> dict[str, object]:
            return {
                "hooks.exists": hooks_path.is_file(),
                "manifest.exists": manifest_path.is_file(),
                "agents.exists": agents_dir.is_dir(),
            }

        before = snapshot()

        plugin = CursorDESPlugin()
        result = plugin.install(context)

        after = snapshot()

        assert result.success is True
        assert_state_delta(
            before,
            after,
            universe=tracked,
            expected={
                "hooks.exists": set_to(True),
                "manifest.exists": set_to(True),
                "agents.exists": set_to(True),
            },
        )

        doc = json.loads(hooks_path.read_text(encoding="utf-8"))
        assert isinstance(doc, dict)
        assert doc.get("version") == 1
        assert isinstance(doc.get("hooks"), dict)
        pretool = doc["hooks"].get("preToolUse")
        assert isinstance(pretool, list)
        assert len(pretool) == 1
        entry = pretool[0]
        assert "claude_code_hook_adapter" in entry["command"]
        assert "pre-tool-use" in entry["command"]
        assert "/usr/bin/python3" in entry["command"]
        assert entry["matcher"] == "Shell|Write|Edit|Delete"
        assert (context.claude_dir / "des-audit.jsonl").is_file()

    def test_reinstall_preserves_user_hooks_without_duplicating(
        self, tmp_path, monkeypatch
    ):
        """
        GIVEN: Prior nWave install plus a user hook
        WHEN: install() runs again
        THEN: User hook preserved and exactly one nWave entry remains
        """
        context = _make_context(tmp_path)
        cursor_config_dir = tmp_path / "home" / ".cursor"
        cursor_config_dir.mkdir(parents=True)
        _patch_cursor_config_dir(monkeypatch, cursor_config_dir)
        _patch_path_resolvers(monkeypatch)

        plugin = CursorDESPlugin()
        plugin.install(context)

        hooks_path = cursor_config_dir / "hooks.json"
        doc = json.loads(hooks_path.read_text(encoding="utf-8"))
        doc["hooks"].setdefault("sessionStart", []).append(
            {"command": "/usr/bin/echo user-hook", "timeout": 5}
        )
        hooks_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

        result = plugin.install(context)
        assert result.success is True

        final_doc = json.loads(hooks_path.read_text(encoding="utf-8"))
        assert len(final_doc["hooks"]["sessionStart"]) == 1
        pretool = final_doc["hooks"]["preToolUse"]
        nwave_entries = [
            e for e in pretool if "claude_code_hook_adapter" in e.get("command", "")
        ]
        assert len(nwave_entries) == 1


class TestUninstallAndVerify:
    """uninstall / verify behavior."""

    def test_uninstall_removes_nwave_keeps_user_hooks(self, tmp_path, monkeypatch):
        """
        GIVEN: hooks.json with nWave + user entries
        WHEN: uninstall() runs
        THEN: nWave gone, user entry remains, manifest removed
        """
        context = _make_context(tmp_path)
        cursor_config_dir = tmp_path / "home" / ".cursor"
        cursor_config_dir.mkdir(parents=True)
        _patch_cursor_config_dir(monkeypatch, cursor_config_dir)
        _patch_path_resolvers(monkeypatch)

        plugin = CursorDESPlugin()
        plugin.install(context)

        hooks_path = cursor_config_dir / "hooks.json"
        doc = json.loads(hooks_path.read_text(encoding="utf-8"))
        doc["hooks"]["beforeShellExecution"] = [
            {"command": "/usr/bin/echo keep-me", "timeout": 5}
        ]
        hooks_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

        result = plugin.uninstall(context)
        assert result.success is True

        final_doc = json.loads(hooks_path.read_text(encoding="utf-8"))
        assert "beforeShellExecution" in final_doc["hooks"]
        assert "preToolUse" not in final_doc["hooks"] or final_doc["hooks"][
            "preToolUse"
        ] == []
        # Empty list may remain; ensure no nWave marker remains anywhere.
        serialized = json.dumps(final_doc)
        assert "claude_code_hook_adapter" not in serialized
        assert not (cursor_config_dir / ".nwave-des-manifest.json").exists()

    def test_verify_passes_after_install(self, tmp_path, monkeypatch):
        """
        GIVEN: Successful install
        WHEN: verify() runs
        THEN: success
        """
        context = _make_context(tmp_path)
        cursor_config_dir = tmp_path / "home" / ".cursor"
        cursor_config_dir.mkdir(parents=True)
        _patch_cursor_config_dir(monkeypatch, cursor_config_dir)
        _patch_path_resolvers(monkeypatch)

        plugin = CursorDESPlugin()
        assert plugin.install(context).success is True
        result = plugin.verify(context)
        assert result.success is True
