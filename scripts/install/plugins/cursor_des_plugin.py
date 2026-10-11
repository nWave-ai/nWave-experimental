"""Plugin for wiring nWave DES hooks into Cursor.

Cursor hooks are configured via ~/.cursor/hooks.json (user-level global) or
.cursor/hooks.json (project-level). This plugin writes a global preToolUse
entry that registers the existing Python DES adapter.

Cursor schema (cursor.com/docs/hooks) differs from Codex:
- Event key is camelCase ``preToolUse`` (not ``PreToolUse``)
- Hook entries are flat: ``{command, matcher?, timeout?}``
- Document may include top-level ``version``

Walking-skeleton scope:
- Writes a single preToolUse hook entry to ~/.cursor/hooks.json
- Ensures ~/.cursor/agents/ exists (checklist path)
- Writes .nwave-des-manifest.json for clean uninstall
- Preserves user-authored hooks and ``version``

Spike pending (S1): the event name ``preToolUse`` and matcher ``Shell|Write|
Edit|Delete`` have not been verified against a running Cursor host. Unlike the
Codex port (which records "Observed from codex-cli 0.145.0 on 2026-07-26"), no
live-run evidence exists here. A green install/verify only attests that
hooks.json was written correctly on disk; it does NOT attest that Cursor fires
the hook at runtime. To close this spike: install, restart Cursor, run a shell
action, and confirm ~/.claude/des-audit.jsonl receives a HOOK_INVOKED entry per
the smoke test in docs/guides/installing-cursor.md.
"""

from __future__ import annotations

import json
import os
import shutil as _shutil
from pathlib import Path
from typing import Any

from scripts.install.plugins.base import (
    InstallationPlugin,
    InstallContext,
    PluginResult,
)
from scripts.shared.install_paths import (
    resolve_des_lib_path_for_spawn,
    resolve_python_command_for_spawn,
)


_HOOKS_FILENAME = "hooks.json"
_MANIFEST_FILENAME = ".nwave-des-manifest.json"
_PRE_TOOL_USE_EVENT = "preToolUse"
_ADAPTER_MARKER = "claude_code_hook_adapter"


def _cursor_config_dir() -> Path:
    """Return the Cursor configuration directory.

    Returns:
        Path to ~/.cursor/ (or $CURSOR_HOME if set).
    """
    override = os.environ.get("CURSOR_HOME")
    return Path(override) if override else Path.home() / ".cursor"


def _build_hook_entry(python_path: str, pythonpath: str) -> dict[str, Any]:
    """Build a Cursor preToolUse hook entry for the DES adapter.

    Cursor uses a flat entry shape (command + optional matcher/timeout),
    not Codex's nested ``hooks: [{type, command}]`` groups.

    Matcher targets Cursor tool names commonly used for shell and edits.
    """
    hook_command = (
        f"PYTHONPATH={pythonpath} {python_path} -m "
        "des.adapters.drivers.hooks.claude_code_hook_adapter "
        "pre-tool-use"
    )
    return {
        "command": hook_command,
        "matcher": "Shell|Write|Edit|Delete",
        "timeout": 30,
    }


def _empty_doc() -> dict[str, Any]:
    """Return a fresh Cursor hooks document with schema version."""
    return {"version": 1, "hooks": {}}


def _read_hooks(hooks_path: Path) -> dict[str, Any]:
    """Read existing hooks.json or return an empty Cursor-shaped doc."""
    if not hooks_path.exists():
        return _empty_doc()
    try:
        data = json.loads(hooks_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return _empty_doc()

    if isinstance(data, list):
        return {"version": 1, "hooks": {_PRE_TOOL_USE_EVENT: list(data)}}

    if isinstance(data, dict):
        hooks_obj = data.get("hooks")
        if not isinstance(hooks_obj, dict):
            return _empty_doc()
        if "version" not in data:
            data = {**data, "version": 1}
        return data

    return _empty_doc()


def _is_nwave_entry(entry: object) -> bool:
    """True if a Cursor hook entry is an nWave DES handler."""
    if not isinstance(entry, dict):
        return False
    command = entry.get("command", "")
    if isinstance(command, str) and _ADAPTER_MARKER in command:
        return True
    # Tolerate accidental Codex-shaped nesting if present.
    nested = entry.get("hooks")
    if isinstance(nested, list):
        return any(
            isinstance(h, dict) and _ADAPTER_MARKER in str(h.get("command", ""))
            for h in nested
        )
    return False


def _remove_nwave_hooks(doc: dict[str, Any]) -> dict[str, Any]:
    """Strip nWave DES entries while preserving user hooks and version."""
    if not isinstance(doc, dict) or not isinstance(doc.get("hooks"), dict):
        return _empty_doc()

    cleaned_events: dict[str, Any] = {}
    for event_name, entries in doc["hooks"].items():
        if not isinstance(entries, list):
            cleaned_events[event_name] = entries
            continue
        cleaned_events[event_name] = [
            entry for entry in entries if not _is_nwave_entry(entry)
        ]

    result: dict[str, Any] = {"hooks": cleaned_events}
    if "version" in doc:
        result["version"] = doc["version"]
    return result


class CursorDESPlugin(InstallationPlugin):
    """Plugin for wiring nWave DES hooks into Cursor."""

    def __init__(self) -> None:
        """Initialize Cursor DES plugin with name, priority, and dependencies."""
        super().__init__(name="cursor-des", priority=55)
        self.dependencies = ["des"]

    def validate_prerequisites(self, context: InstallContext) -> PluginResult:
        """Validate Cursor and DES prerequisites."""
        cursor_dir = _cursor_config_dir()
        cursor_binary = _shutil.which("cursor") is not None

        if not cursor_dir.exists() and not cursor_binary:
            return PluginResult(
                success=True,
                plugin_name=self.name,
                message="Cursor not detected, skipping DES hook installation",
            )

        des_module = context.claude_dir / "lib" / "python" / "des"
        if not des_module.exists():
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message=(
                    f"DES Python module not found at {des_module}. Install DES first."
                ),
                errors=["DES module must be installed before Cursor DES hooks"],
            )

        return PluginResult(
            success=True,
            plugin_name=self.name,
            message="Cursor DES prerequisites validated",
        )

    def install(self, context: InstallContext) -> PluginResult:
        """Install DES preToolUse hook into ~/.cursor/hooks.json."""
        try:
            prereq = self.validate_prerequisites(context)
            if not prereq.success:
                return prereq
            if "skip" in prereq.message.lower():
                return prereq

            cursor_dir = _cursor_config_dir()
            cursor_dir.mkdir(parents=True, exist_ok=True)
            agents_dir = cursor_dir / "agents"
            agents_dir.mkdir(parents=True, exist_ok=True)

            python_path = resolve_python_command_for_spawn()
            pythonpath = resolve_des_lib_path_for_spawn()

            hooks_path = cursor_dir / _HOOKS_FILENAME
            doc = _remove_nwave_hooks(_read_hooks(hooks_path))
            doc.setdefault("version", 1)
            doc.setdefault("hooks", {})
            pretool_list = doc["hooks"].setdefault(_PRE_TOOL_USE_EVENT, [])
            pretool_list.append(_build_hook_entry(python_path, pythonpath))

            hooks_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

            manifest = {
                "hooks_file": str(hooks_path),
                "python_path": python_path,
                "pythonpath": pythonpath,
                "event": _PRE_TOOL_USE_EVENT,
            }
            manifest_path = cursor_dir / _MANIFEST_FILENAME
            manifest_path.write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )

            # Checklist expects the shared audit log path to exist after install.
            # Runtime still appends on first hook fire; create empty file if absent.
            audit_log = context.claude_dir / "des-audit.jsonl"
            if not audit_log.exists():
                audit_log.touch()

            context.logger.info(f"  Cursor DES hook installed in {hooks_path}")

            return PluginResult(
                success=True,
                plugin_name=self.name,
                message="Cursor DES hook installed successfully",
                installed_files=[hooks_path, agents_dir],
            )

        except Exception as e:
            context.logger.error(f"  Failed to install Cursor DES hook: {e}")
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message=f"Cursor DES hook installation failed: {e!s}",
                errors=[str(e)],
            )

    def uninstall(self, context: InstallContext) -> PluginResult:
        """Remove nWave DES hook entries from ~/.cursor/hooks.json."""
        try:
            cursor_dir = _cursor_config_dir()
            hooks_path = cursor_dir / _HOOKS_FILENAME
            if hooks_path.exists():
                existing = _read_hooks(hooks_path)
                cleaned = _remove_nwave_hooks(existing)
                events = cleaned.get("hooks", {}) if isinstance(cleaned, dict) else {}
                any_user_entries = any(
                    isinstance(v, list) and len(v) > 0 for v in events.values()
                )
                if any_user_entries:
                    hooks_path.write_text(
                        json.dumps(cleaned, indent=2) + "\n", encoding="utf-8"
                    )
                else:
                    hooks_path.unlink()
                context.logger.info(f"  Removed nWave DES hook from {hooks_path}")

            manifest_path = cursor_dir / _MANIFEST_FILENAME
            if manifest_path.exists():
                manifest_path.unlink()
                context.logger.info(f"  Removed Cursor DES manifest: {manifest_path}")

            return PluginResult(
                success=True,
                plugin_name=self.name,
                message="Cursor DES hook uninstalled",
            )

        except Exception as e:
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message=f"Cursor DES hook uninstall failed: {e}",
                errors=[str(e)],
            )

    def verify(self, context: InstallContext) -> PluginResult:
        """Verify the DES hook is present in ~/.cursor/hooks.json."""
        try:
            cursor_dir = _cursor_config_dir()
            cursor_binary = _shutil.which("cursor") is not None
            if not cursor_dir.exists() and not cursor_binary:
                return PluginResult(
                    success=True,
                    plugin_name=self.name,
                    message="Cursor not detected, verification skipped",
                )

            errors: list[str] = []

            hooks_path = cursor_dir / _HOOKS_FILENAME
            if not hooks_path.exists():
                errors.append(f"hooks.json not found: {hooks_path}")
            else:
                doc = _read_hooks(hooks_path)
                pretool = (
                    doc.get("hooks", {}).get(_PRE_TOOL_USE_EVENT, [])
                    if isinstance(doc, dict)
                    else []
                )
                nwave_entries = [e for e in pretool if _is_nwave_entry(e)]
                if not nwave_entries:
                    errors.append("No nWave DES hook entry found in hooks.json")

            manifest_path = cursor_dir / _MANIFEST_FILENAME
            if not manifest_path.exists():
                errors.append(f"DES manifest not found: {manifest_path}")

            agents_dir = cursor_dir / "agents"
            if not agents_dir.is_dir():
                errors.append(f"agents directory not found: {agents_dir}")

            if errors:
                return PluginResult(
                    success=False,
                    plugin_name=self.name,
                    message="Cursor DES hook verification failed",
                    errors=errors,
                )

            context.logger.info("  Cursor DES hook verified")
            return PluginResult(
                success=True,
                plugin_name=self.name,
                message="Cursor DES hook verification passed",
            )

        except Exception as e:
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message=f"Cursor DES hook verification failed: {e}",
                errors=[str(e)],
            )
