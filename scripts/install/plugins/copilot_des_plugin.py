"""Plugin for wiring nWave DES hooks into GitHub Copilot CLI.

Copilot CLI hooks are configured via per-event config files in the Copilot
hooks directory. The empirical spike against @github/copilot v1.0.54
(docs/analysis/copilot-cli-prereq-spike-2026-05-28.md) established two binding
constraints this plugin honors:

- FM-1: an inline ``hooks`` block in ``<COPILOT_HOME>/settings.json`` does NOT
  fire in v1.0.54. The hook config MUST live as a FILE in the hooks directory
  (``<COPILOT_HOME>/hooks/nwave-des.json``), NOT inline in settings.json. This
  mirrors the Codex file-style precedent rather than the Claude Code inline
  settings.json style.
- FS-1: each hook entry MUST be DOUBLE-NESTED —
  ``{matcher?, hooks: [{type: "command", bash: "...", timeoutSec: N}]}`` — never
  the flat ``{type, bash}`` shape research originally quoted. NOTE the handler
  payload key is ``bash`` (Copilot), NOT ``command`` (which is the Codex key).

Walking-skeleton scope (slice-01):
- Writes a single preToolUse hook entry to ``<COPILOT_HOME>/hooks/nwave-des.json``
- The hook points to the same Python DES adapter used by Claude Code and Codex
- No postToolUse / sessionStop hooks in this slice (deferred)

Hook protocol is identical to Claude Code / Codex: JSON on stdin, decision on
stdout. The Copilot CLI exports ``COPILOT_CLI=1`` into the hook subprocess
(spike FE-4), which the shared adapter can branch on at runtime; the installer
does not need to inject a separate runtime marker.

A manifest (.nwave-des-manifest.json) tracks the installed hook config for
clean uninstallation.
"""

import json
import os
import shutil as _shutil
from pathlib import Path

from scripts.install.plugins.base import (
    InstallationPlugin,
    InstallContext,
    PluginResult,
)
from scripts.shared.install_paths import (
    host_neutral_runtime_dir,
    resolve_des_lib_path_for_spawn,
    resolve_python_command_for_spawn,
)


_HOOKS_DIRNAME = "hooks"
_DES_HOOK_FILENAME = "nwave-des.json"
_MANIFEST_FILENAME = ".nwave-des-manifest.json"

# Event key used by Copilot CLI (camelCase per spike FS-2: the binary's event
# allowlist Set membership tests use camelCase).
_PRE_TOOL_USE_EVENT = "preToolUse"


def _copilot_config_dir() -> Path:
    """Return the Copilot CLI configuration directory.

    Returns:
        Path to ~/.copilot/ (or $COPILOT_HOME if set, per spike §4).
    """
    override = os.environ.get("COPILOT_HOME")
    return Path(override) if override else Path.home() / ".copilot"


def _build_hook_config(python_path: str, pythonpath: str) -> dict:
    """Build the Copilot preToolUse hook config (FS-1 double-nested shape).

    The hook config is an event-keyed object whose ``preToolUse`` value is a
    list of hook entries. Each entry is double-nested:
    ``{matcher, hooks: [{type, bash, timeoutSec}]}`` — the shape Copilot v1.0.54
    actually honors (spike FS-1). The handler payload key is ``bash`` (the shell
    command Copilot runs), distinct from the Codex ``command`` key.

    The shared DES adapter (hook_router) requires an argv positional event token
    (``pre-tool-use``); Copilot does not inject the event name as argv, so the
    token is baked into the ``bash`` command string at install time (mirrors the
    Codex precedent — without it the adapter exits 1 on every fire).

    Args:
        python_path: Absolute path to the Python executable
        pythonpath: Path to add to PYTHONPATH for DES imports

    Returns:
        Event-keyed hook config dict in the FS-1 double-nested shape.
    """
    hook_command = (
        f"PYTHONPATH={pythonpath} {python_path} -m "
        "des.adapters.drivers.hooks.claude_code_hook_adapter "
        "pre-tool-use"
    )
    return {
        _PRE_TOOL_USE_EVENT: [
            {
                "matcher": ".*",
                "hooks": [
                    {
                        "type": "command",
                        "bash": hook_command,
                        "timeoutSec": 30,
                    }
                ],
            }
        ]
    }


class CopilotDESPlugin(InstallationPlugin):
    """Plugin for wiring nWave DES hooks into GitHub Copilot CLI."""

    def __init__(self) -> None:
        """Initialize Copilot DES plugin with name, priority, and dependencies."""
        super().__init__(name="copilot-des", priority=56)
        self.dependencies = ["des"]

    def validate_prerequisites(self, context: InstallContext) -> PluginResult:
        """Validate Copilot CLI and DES prerequisites.

        Checks:
        1. Copilot detected (COPILOT_HOME/.copilot dir exists OR COPILOT_CLI env
           set OR `copilot` binary in PATH) — skip if none.
        2. DES Python module is installed at <claude_dir>/lib/python/des/.

        Args:
            context: InstallContext with claude_dir

        Returns:
            PluginResult with success=True to skip/proceed, success=False on errors
        """
        copilot_dir = _copilot_config_dir()
        copilot_binary = _shutil.which("copilot") is not None
        copilot_env = bool(os.environ.get("COPILOT_CLI", ""))

        if not copilot_dir.exists() and not copilot_binary and not copilot_env:
            return PluginResult(
                success=True,
                plugin_name=self.name,
                message="Copilot CLI not detected, skipping DES hook installation",
            )

        des_module = (
            host_neutral_runtime_dir() / "des"
            if "claude_code" not in context.target_platforms
            else context.claude_dir / "lib" / "python" / "des"
        )
        if not des_module.exists():
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message=(
                    f"DES Python module not found at {des_module}. Install DES first."
                ),
                errors=["DES module must be installed before Copilot DES hooks"],
            )

        return PluginResult(
            success=True,
            plugin_name=self.name,
            message="Copilot DES prerequisites validated",
        )

    def install(self, context: InstallContext) -> PluginResult:
        """Install the DES preToolUse hook config into the Copilot hooks dir.

        Writes ``<COPILOT_HOME>/hooks/nwave-des.json`` (FM-1 file-in-dir, NOT an
        inline settings.json block) in the FS-1 double-nested shape. Each nWave
        install owns the whole ``nwave-des.json`` file, so reinstall is naturally
        idempotent — the file is overwritten in full.

        Args:
            context: InstallContext with shared installation utilities

        Returns:
            PluginResult indicating success or failure
        """
        prereq = self.validate_prerequisites(context)
        if not prereq.success:
            return prereq
        if "skip" in prereq.message.lower():
            return prereq

        copilot_dir = _copilot_config_dir()
        hooks_dir = copilot_dir / _HOOKS_DIRNAME
        hooks_dir.mkdir(parents=True, exist_ok=True)

        python_path = resolve_python_command_for_spawn()
        pythonpath = resolve_des_lib_path_for_spawn()

        hook_path = hooks_dir / _DES_HOOK_FILENAME
        config = _build_hook_config(python_path, pythonpath)
        hook_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

        manifest = {
            "hook_file": str(hook_path),
            "python_path": python_path,
            "pythonpath": pythonpath,
        }
        manifest_path = copilot_dir / _MANIFEST_FILENAME
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

        context.logger.info(f"  Copilot DES hook installed in {hook_path}")

        return PluginResult(
            success=True,
            plugin_name=self.name,
            message="Copilot DES hook installed successfully",
            installed_files=[hook_path],
        )

    def uninstall(self, context: InstallContext) -> PluginResult:
        """Remove the nWave DES hook config from the Copilot hooks dir.

        Removes ``<COPILOT_HOME>/hooks/nwave-des.json`` and the manifest. Because
        nWave owns its own dedicated hook file, any hook file the operator
        authored themselves (a different filename in the hooks dir) is preserved
        untouched.

        Args:
            context: InstallContext with shared installation utilities

        Returns:
            PluginResult indicating success or failure
        """
        copilot_dir = _copilot_config_dir()

        hook_path = copilot_dir / _HOOKS_DIRNAME / _DES_HOOK_FILENAME
        if hook_path.exists():
            hook_path.unlink()
            context.logger.info(f"  Removed nWave DES hook from {hook_path}")

        manifest_path = copilot_dir / _MANIFEST_FILENAME
        if manifest_path.exists():
            manifest_path.unlink()
            context.logger.info(f"  Removed Copilot DES manifest: {manifest_path}")

        return PluginResult(
            success=True,
            plugin_name=self.name,
            message="Copilot DES hook uninstalled",
        )

    def verify(self, context: InstallContext) -> PluginResult:
        """Verify the DES hook config is present in the Copilot hooks dir.

        Checks:
        1. <COPILOT_HOME>/hooks/nwave-des.json exists and references the adapter
        2. Manifest exists

        Args:
            context: InstallContext with shared installation utilities

        Returns:
            PluginResult indicating verification success or failure
        """
        copilot_dir = _copilot_config_dir()

        copilot_binary = _shutil.which("copilot") is not None
        copilot_env = bool(os.environ.get("COPILOT_CLI", ""))
        if not copilot_dir.exists() and not copilot_binary and not copilot_env:
            return PluginResult(
                success=True,
                plugin_name=self.name,
                message="Copilot CLI not detected, verification skipped",
            )

        errors: list[str] = []

        hook_path = copilot_dir / _HOOKS_DIRNAME / _DES_HOOK_FILENAME
        if not hook_path.exists():
            errors.append(f"DES hook config not found: {hook_path}")
        else:
            content = hook_path.read_text(encoding="utf-8")
            if "claude_code_hook_adapter" not in content:
                errors.append("DES hook config does not reference the shared adapter")

        manifest_path = copilot_dir / _MANIFEST_FILENAME
        if not manifest_path.exists():
            errors.append(f"DES manifest not found: {manifest_path}")

        if errors:
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message="Copilot DES hook verification failed",
                errors=errors,
            )

        context.logger.info("  Copilot DES hook verified")

        return PluginResult(
            success=True,
            plugin_name=self.name,
            message="Copilot DES hook verification passed",
        )
