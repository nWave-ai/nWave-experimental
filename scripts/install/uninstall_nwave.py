#!/usr/bin/env python3
"""
nWave Framework Uninstallation Script

Cross-platform uninstaller for the nWave methodology framework.
Completely removes nWave framework from global Claude config directory.

Usage: python uninstall_nwave.py [--backup] [--force] [--dry-run] [--help]
"""

import argparse
import json
import shutil
import sys
from pathlib import Path


try:
    from scripts.install.attribution_utils import (
        NWAVE_MANAGED_COMMIT,
        remove_settings_attribution,
    )
    from scripts.install.install_nwave import print_logo
    from scripts.install.install_utils import (
        BackupManager,
        Logger,
        ManifestWriter,
        PathUtils,
        confirm_action,
    )
    from scripts.install.plugins.codex_des_plugin import _codex_config_dir
    from scripts.install.plugins.copilot_des_plugin import _copilot_config_dir
    from scripts.install.plugins.opencode_des_plugin import _opencode_config_dir
    from scripts.shared.install_paths import host_neutral_runtime_dir
except ImportError:
    from attribution_utils import (
        NWAVE_MANAGED_COMMIT,
        remove_settings_attribution,
    )
    from install_nwave import print_logo
    from install_utils import (
        BackupManager,
        Logger,
        ManifestWriter,
        PathUtils,
        confirm_action,
    )
    from plugins.codex_des_plugin import _codex_config_dir
    from plugins.copilot_des_plugin import _copilot_config_dir
    from plugins.opencode_des_plugin import _opencode_config_dir
    from shared.install_paths import host_neutral_runtime_dir

# The DES manifest filename each native (non-Claude) plugin writes under its
# own host config dir -- each plugin module repeats this same literal as a
# private module-level constant, so it is repeated here rather than reaching
# into another module's private name.
_NATIVE_DES_MANIFEST_FILENAME = ".nwave-des-manifest.json"

# ANSI color codes for --help output (only consumer)
_ANSI_BLUE = "\033[0;34m"
_ANSI_NC = "\033[0m"  # No Color

__version__ = "1.1.0"


class NWaveUninstaller:
    """nWave framework uninstaller."""

    def __init__(
        self,
        backup_before_removal: bool = False,
        force: bool = False,
        dry_run: bool = False,
    ):
        """
        Initialize uninstaller.

        Args:
            backup_before_removal: Create backup before uninstalling
            force: Skip confirmation prompts
            dry_run: Show what would be done without executing
        """
        self.backup_before_removal = backup_before_removal
        self.force = force
        self.dry_run = dry_run

        self.claude_config_dir = PathUtils.get_claude_config_dir()
        # Persistent logging (and the uninstall report) start only after
        # check_installation() confirms a genuine Claude discovery surface
        # exists -- a native-only (Codex/Copilot/OpenCode, alone or combined)
        # uninstall must never create ~/.claude merely to hold its own log or
        # report (mirrors install_nwave.py's enable_install_logging).
        self._uninstall_log_file = self.claude_config_dir / "nwave-uninstall.log"
        self.logger = Logger(None)
        self.backup_manager = BackupManager(self.logger, "uninstall")
        self.claude_installation_present = False

    def enable_uninstall_logging(self) -> None:
        """Enable persistent logging once a Claude installation is confirmed."""
        if not self.dry_run:
            self.logger.log_file = self._uninstall_log_file

    def check_installation(self) -> bool:
        """Check for existing nWave installation.

        Sets ``self.claude_installation_present`` so callers know whether a
        Claude discovery surface actually exists (and therefore whether it is
        safe to enable persistent logging / write the uninstall report under
        ``claude_config_dir``). A native-only (Codex/Copilot/OpenCode)
        installation makes this return True without setting that flag.
        """
        self.logger.info("  🔍 Checking for nWave installation...")

        installation_found = False

        agents_dir = self.claude_config_dir / "agents" / "nw"
        commands_dir = self.claude_config_dir / "commands" / "nw"
        manifest_file = self.claude_config_dir / "nwave-manifest.txt"
        install_log = self.claude_config_dir / "nwave-install.log"
        backups_dir = self.claude_config_dir / "backups"

        if agents_dir.exists():
            installation_found = True
            self.logger.info(f"    📂 Found nWave agents in: {agents_dir}")

        if commands_dir.exists():
            installation_found = True
            self.logger.info(f"    📂 Found nWave commands in: {commands_dir}")

        skills_dir = self.claude_config_dir / "skills" / "nw"
        if skills_dir.exists():
            installation_found = True
            self.logger.info(f"    📂 Found nWave skills in: {skills_dir}")

        if manifest_file.exists():
            installation_found = True
            self.logger.info("    📄 Found nWave manifest file")

        if install_log.exists():
            installation_found = True
            self.logger.info("    📄 Found nWave installation logs")

        if backups_dir.exists():
            nwave_backups = list(backups_dir.glob("nwave-*"))
            if nwave_backups:
                installation_found = True
                self.logger.info("    📦 Found nWave backup directories")

        # Check for DES hooks
        settings_file = self.claude_config_dir / "settings.json"
        if settings_file.exists():
            try:
                with open(settings_file, encoding="utf-8") as f:
                    config = json.load(f)
                    if "hooks" in config:
                        hooks_str = json.dumps(config["hooks"])
                        if (
                            "des/adapters/drivers/hooks/claude_code_hook_adapter"
                            in hooks_str
                        ):
                            installation_found = True
                            self.logger.info("    🔗 Found DES hooks in settings.json")
            except (OSError, json.JSONDecodeError):
                pass

        # This point onward: every check above is Claude-owned (all live
        # under claude_config_dir). Record that BEFORE looking at native
        # surfaces, so a pure native installation never flips this flag.
        self.claude_installation_present = installation_found

        # Native (non-Claude) DES surfaces: a Codex/Copilot/OpenCode-only
        # installation has no Claude discovery surface at all, so the checks
        # above always miss it -- without this, check_installation() would
        # wrongly report "nothing to uninstall" and silently no-op, leaving
        # the native hook/manifest and the host-neutral DES runtime behind.
        codex_manifest = _codex_config_dir() / _NATIVE_DES_MANIFEST_FILENAME
        if codex_manifest.exists():
            installation_found = True
            self.logger.info(f"    📄 Found Codex DES manifest: {codex_manifest}")

        copilot_manifest = _copilot_config_dir() / _NATIVE_DES_MANIFEST_FILENAME
        if copilot_manifest.exists():
            installation_found = True
            self.logger.info(f"    📄 Found Copilot DES manifest: {copilot_manifest}")

        opencode_manifest = _opencode_config_dir() / _NATIVE_DES_MANIFEST_FILENAME
        if opencode_manifest.exists():
            installation_found = True
            self.logger.info(f"    📄 Found OpenCode DES manifest: {opencode_manifest}")

        native_runtime_dir = host_neutral_runtime_dir() / "des"
        if native_runtime_dir.exists():
            installation_found = True
            self.logger.info(
                f"    📂 Found host-neutral DES runtime: {native_runtime_dir}"
            )

        if not installation_found:
            self.logger.info("  ⚠️ No nWave framework installation detected")
            self.logger.info("  ⚠️ Nothing to uninstall")
            return False

        return True

    def confirm_removal(self) -> bool:
        """Confirm uninstallation with user."""
        if self.force:
            return True

        self.logger.info("")
        self.logger.error(
            "  🚨 WARNING: This will completely remove the framework from your system"
        )
        self.logger.info("")
        self.logger.warn("  ⚠️ The following will be removed:")
        self.logger.warn("    🗑️ All nWave agents")
        self.logger.warn("    🗑️ All nWave commands")
        self.logger.warn("    🗑️ DES hooks from Claude Code settings")
        self.logger.warn("    🗑️ Configuration files and manifest")
        self.logger.warn("    🗑️ Installation logs and backup directories")
        self.logger.info("")

        if self.backup_before_removal:
            self.logger.info("  ✅ A backup will be created before removal at:")
            self.logger.info(f"    📦 {self.backup_manager.backup_dir}")
            self.logger.info("")
        else:
            self.logger.error(
                "  🚨 No backup will be created. This action cannot be undone"
            )
            self.logger.error(
                "  🚨 To create a backup, cancel and run with --backup option"
            )
            self.logger.info("")

        return confirm_action("Are you sure you want to proceed?")

    def check_global_config(
        self,
        global_config_path: Path | None = None,
        prompt_fn: object = None,
    ) -> None:
        """Check for global config and prompt user about handling it.

        Called between confirm_removal() and create_backup() in the
        uninstall flow. Handles keep/delete prompt in interactive mode,
        auto-preserves in force mode, and logs status in dry-run mode.

        Args:
            global_config_path: Override path to global config file.
                Defaults to ~/.nwave/global-config.json.
            prompt_fn: Optional callable(prompt_str) -> bool for testing.
                Defaults to confirm_action from install_utils.
        """
        path = global_config_path or (Path.home() / ".nwave" / "global-config.json")

        if not path.exists():
            return

        if self.dry_run:
            self.logger.info(f"  [DRY RUN] Would prompt about global config at {path}")
            return

        if self.force:
            self.logger.info("  Preserved global config (--force: skipping prompt)")
            return

        # Interactive mode: prompt user to keep or delete
        ask = prompt_fn if prompt_fn is not None else confirm_action
        self.logger.info("")
        self.logger.info(f"  Found global configuration at {path}")
        should_delete = ask("  Delete global config? (No = keep for next install)")

        if not should_delete:
            self.logger.info(f"  Preserved global config at {path}")
            return

        path.unlink()
        self.logger.info(f"  Deleted global config at {path}")

        # Clean up empty directory
        nwave_dir = path.parent
        if nwave_dir.exists() and not any(nwave_dir.iterdir()):
            nwave_dir.rmdir()
            self.logger.info(f"  Removed empty directory {nwave_dir}")

    def create_backup(self) -> None:
        """Create backup before removal."""
        if not self.backup_before_removal:
            return

        self.backup_manager.create_backup(dry_run=self.dry_run)

    def remove_agents(self) -> None:
        """Remove nWave agents (delegates to shared nw-namespace remover)."""
        self._remove_nw_namespace_subdir("agents")

    def remove_skills(self) -> None:
        """Remove nWave skills.

        Install layout writes flat `~/.claude/skills/nw-<name>/` directories
        (NEW_FLAT layout per skills_plugin.py). The legacy nested
        `~/.claude/skills/nw/<name>/` layout is also handled for backward
        compatibility with users still on pre-flat installs. User-created
        skills (no `nw-` prefix) are preserved.
        """
        skills_dir = self.claude_config_dir / "skills"

        if self.dry_run:
            self.logger.info("  🚨 [DRY RUN] Would remove nWave skills")
            if skills_dir.exists():
                nw_dirs = sorted(skills_dir.glob("nw-*"))
                legacy_nested = skills_dir / "nw"
                if nw_dirs:
                    self.logger.info(
                        f"    🚨 [DRY RUN] Would remove {len(nw_dirs)} skills/nw-* dirs"
                    )
                if legacy_nested.exists():
                    self.logger.info(
                        "    🚨 [DRY RUN] Would remove legacy skills/nw/ dir"
                    )
            return

        with self.logger.progress_spinner("  🚧 Removing nWave skills..."):
            removed_count = 0
            if skills_dir.exists():
                # New flat layout: skills/nw-<name>/
                for nw_dir in skills_dir.glob("nw-*"):
                    if nw_dir.is_dir():
                        shutil.rmtree(nw_dir)
                        removed_count += 1
                # Legacy nested layout: skills/nw/<name>/
                legacy_nested = skills_dir / "nw"
                if legacy_nested.exists():
                    shutil.rmtree(legacy_nested)
                    self.logger.info("  🗑️ Removed legacy skills/nw directory")

            if removed_count:
                self.logger.info(f"  🗑️ Removed {removed_count} skills/nw-* dirs")

            # Remove parent skills directory if empty
            if skills_dir.exists():
                try:
                    if not any(skills_dir.iterdir()):
                        skills_dir.rmdir()
                        self.logger.info("  🗑️ Removed empty skills directory")
                    else:
                        self.logger.info(
                            "  📂 Kept skills directory (contains user files)"
                        )
                except OSError:
                    self.logger.info("  📂 Kept skills directory (contains user files)")

    def remove_lib_python(self) -> None:
        """Remove the installed DES runtime library (`des/`), wherever it lives.

        The installer writes the DES runtime under `lib/python/des/` (Claude
        targets) and/or `host_neutral_runtime_dir()/des/` (Codex/Copilot/
        OpenCode targets, or the mirror half of a mixed target) for the hook
        adapters to import. Uninstall must remove EVERY location the SAME
        target-platform detection resolves to -- not just the Claude-scoped
        path -- via `DESPlugin.resolve_des_module_locations`, the single
        source of truth `install()` also uses to decide where to write the
        module. A hardcoded Claude-only path here orphaned the module on
        disk for any non-Claude-only target (the uninstall-vs-install path
        divergence bug). Sibling lib/python/ contents (non-des) are
        preserved; parent dirs are removed only if empty.
        """
        try:
            from scripts.install.context_detector import detect_target_platforms
            from scripts.install.plugins.base import InstallContext
            from scripts.install.plugins.des_plugin import DESPlugin
        except ImportError:
            from context_detector import detect_target_platforms
            from plugins.base import InstallContext
            from plugins.des_plugin import DESPlugin

        target_platforms = {platform.value for platform in detect_target_platforms()}
        context = InstallContext(
            claude_dir=self.claude_config_dir,
            scripts_dir=self.claude_config_dir / "scripts",
            templates_dir=self.claude_config_dir / "templates",
            logger=self.logger,
            target_platforms=target_platforms,
        )
        des_module_locations = DESPlugin.resolve_des_module_locations(context)

        if self.dry_run:
            for lib_des in des_module_locations:
                if lib_des.exists():
                    self.logger.info(f"  🚨 [DRY RUN] Would remove {lib_des}")
            return

        with self.logger.progress_spinner("  🚧 Removing nWave Python runtime..."):
            for lib_des in des_module_locations:
                if lib_des.exists():
                    shutil.rmtree(lib_des)
                    self.logger.info(f"  🗑️ Removed {lib_des}")

                # Cascade-clean empty parents (e.g. lib/python then lib, or
                # runtime then .nwave for the host-neutral location)
                for parent in (lib_des.parent, lib_des.parent.parent):
                    if parent.exists():
                        try:
                            if not any(parent.iterdir()):
                                parent.rmdir()
                                self.logger.info(f"  🗑️ Removed empty {parent.name}")
                        except OSError:
                            pass

    def remove_host_neutral_des_runtime(self) -> None:
        """Remove ~/.nwave/runtime/des/ (shared DES runtime for native hosts).

        Codex/Copilot/OpenCode adapters import the DES runtime from the
        host-neutral shared location (see host_neutral_runtime_dir()) rather
        than claude_config_dir/lib/python/des -- a native-only uninstall must
        remove it too, mirroring remove_lib_python for the Claude location.
        Only the "des" subtree is removed; sibling ~/.nwave content
        (global-config.json, nWave/ operator state, etc.) is untouched, and
        the "runtime" parent is removed only if it becomes empty.
        """
        runtime_des = host_neutral_runtime_dir() / "des"

        if self.dry_run:
            if runtime_des.exists():
                self.logger.info(
                    "  🚨 [DRY RUN] Would remove host-neutral DES runtime directory"
                )
            return

        with self.logger.progress_spinner("  🚧 Removing host-neutral DES runtime..."):
            if runtime_des.exists():
                shutil.rmtree(runtime_des)
                self.logger.info("  🗑️ Removed host-neutral DES runtime directory")

            runtime_parent = runtime_des.parent
            if runtime_parent.exists():
                try:
                    if not any(runtime_parent.iterdir()):
                        runtime_parent.rmdir()
                        self.logger.info(f"  🗑️ Removed empty {runtime_parent.name}")
                except OSError:
                    pass

    def remove_commands(self) -> None:
        """Remove nWave commands (delegates to shared nw-namespace remover)."""
        self._remove_nw_namespace_subdir("commands")

    def _remove_nw_namespace_subdir(self, noun: str) -> None:
        """Remove ~/.claude/{noun}/nw/ directory + cascade-clean empty parent.

        Shared by remove_agents("agents") and remove_commands("commands").
        Both followed identical 27-line bodies; consolidated 2026-05-03 (RPP L3).

        Args:
            noun: Plural label for logging + directory name ("agents" / "commands").
        """
        nested_dir = self.claude_config_dir / noun / "nw"
        parent_dir = self.claude_config_dir / noun

        if self.dry_run:
            self.logger.info(f"  🚨 [DRY RUN] Would remove nWave {noun}")
            if nested_dir.exists():
                self.logger.info(f"    🚨 [DRY RUN] Would remove {noun}/nw directory")
            return

        with self.logger.progress_spinner(f"  🚧 Removing nWave {noun}..."):
            if nested_dir.exists():
                shutil.rmtree(nested_dir)
                self.logger.info(f"  🗑️ Removed {noun}/nw directory")

            # Flat layout: {noun}/nw-* files/symlinks/dirs (a public/flat install
            # writes flat nw-*.md; the nested remover above misses them). Symmetric
            # with remove_skills. is_symlink() is checked FIRST so DANGLING symlinks
            # (target already gone) are unlinked, not followed -- otherwise they
            # survive uninstall and crash the next install's backup step.
            flat_removed = 0
            if parent_dir.exists():
                for entry in parent_dir.glob("nw-*"):
                    if entry.is_symlink() or entry.is_file():
                        entry.unlink()
                        flat_removed += 1
                    elif entry.is_dir():
                        shutil.rmtree(entry)
                        flat_removed += 1
            if flat_removed:
                self.logger.info(f"  🗑️ Removed {flat_removed} flat {noun}/nw-* entries")

            # Remove parent directory if empty
            if parent_dir.exists():
                try:
                    if not any(parent_dir.iterdir()):
                        parent_dir.rmdir()
                        self.logger.info(f"  🗑️ Removed empty {noun} directory")
                    else:
                        self.logger.info(
                            f"  📂 Kept {noun} directory (contains other files)"
                        )
                except OSError:
                    self.logger.info(
                        f"  📂 Kept {noun} directory (contains other files)"
                    )

    def remove_config_files(self) -> None:
        """Remove nWave configuration files."""
        if self.dry_run:
            self.logger.info("  🚨 [DRY RUN] Would remove nWave configuration files")
            return

        with self.logger.progress_spinner("  🚧 Removing nWave configuration files..."):
            config_files = ["nwave-manifest.txt", "nwave-install.log"]

            for config_file in config_files:
                file_path = self.claude_config_dir / config_file
                if file_path.exists():
                    file_path.unlink()
                    self.logger.info(f"  🗑️ Removed {config_file}")

    def remove_backups(self) -> None:
        """Remove nWave backup directories."""
        if self.dry_run:
            self.logger.info("  🚨 [DRY RUN] Would remove nWave backup directories")
            return

        with self.logger.progress_spinner("  🚧 Removing nWave backup directories..."):
            backup_count = 0
            backups_dir = self.claude_config_dir / "backups"

            if backups_dir.exists():
                for backup_dir in backups_dir.glob("nwave-*"):
                    if backup_dir.is_dir():
                        # Skip the backup we just created during this uninstall
                        if (
                            self.backup_before_removal
                            and backup_dir == self.backup_manager.backup_dir
                        ):
                            self.logger.info(
                                f"  📦 Preserving current uninstall backup: {backup_dir.name}"
                            )
                            continue

                        shutil.rmtree(backup_dir)
                        backup_count += 1

            if backup_count > 0:
                self.logger.info(
                    f"  🗑️ Removed {backup_count} old nWave backup directories"
                )
            else:
                self.logger.info("  ✅ No old nWave backup directories found")

    def remove_des_hooks(self) -> None:
        """Remove installer-owned DES hooks from Claude Code settings.

        ``DESPlugin`` is the sole writer and cleanup authority for this
        surface.  The former standalone hook installer was a second writer
        with substring-based ownership detection, so it could delete a
        neighbouring user or Lyra hook merely because its command happened to
        contain a DES-looking fragment.
        """
        if self.dry_run:
            self.logger.info("  🚨 [DRY RUN] Would remove DES hooks from settings.json")
            return

        with self.logger.progress_spinner("  🚧 Removing DES hooks..."):
            try:
                from scripts.install.plugins.base import InstallContext
                from scripts.install.plugins.des_plugin import DESPlugin
            except ImportError:
                from plugins.base import InstallContext
                from plugins.des_plugin import DESPlugin

            context = InstallContext(
                claude_dir=self.claude_config_dir,
                scripts_dir=self.claude_config_dir / "scripts",
                templates_dir=self.claude_config_dir / "templates",
                logger=self.logger,
                target_platforms={"claude_code"},
            )
            result = DESPlugin()._uninstall_des_hooks(context)

            if result.success:
                self.logger.info("  🗑️ Removed DES hooks from settings.json")
            else:
                self.logger.warn(f"  ⚠️ DES hook removal: {result.message}")

    def remove_copilot_des_hooks(self) -> None:
        """Remove the nWave DES hook config from the Copilot CLI hooks dir.

        slice-01 of copilot-cli-integration: the installer writes
        ``<COPILOT_HOME>/hooks/nwave-des.json`` (FM-1 file-in-dir) when Copilot
        is detected. Clean uninstall MUST remove it (and the manifest) while
        leaving any hook the operator authored themselves untouched -- the
        plugin owns its own dedicated file, so foreign hooks survive.
        """
        if self.dry_run:
            self.logger.info("  🚨 [DRY RUN] Would remove Copilot DES hook config")
            return

        try:
            from scripts.install.plugins.base import InstallContext
            from scripts.install.plugins.copilot_des_plugin import CopilotDESPlugin
        except ImportError:
            from plugins.base import InstallContext
            from plugins.copilot_des_plugin import CopilotDESPlugin

        context = InstallContext(
            claude_dir=self.claude_config_dir,
            scripts_dir=self.claude_config_dir / "scripts",
            templates_dir=self.claude_config_dir / "templates",
            logger=self.logger,
        )
        result = CopilotDESPlugin().uninstall(context)
        if result.success:
            self.logger.info("  🗑️ Removed Copilot DES hook config")
        else:
            self.logger.warn(f"  ⚠️ Copilot DES hook removal: {result.message}")

    def remove_opencode_des_hooks(self) -> None:
        """Remove the nWave DES shim from the OpenCode plugins dir.

        The installer writes ``<OPENCODE_CONFIG_DIR>/plugins/nwave-des.ts``
        and its manifest when OpenCode is detected. Clean uninstall MUST
        remove both (mirrors remove_copilot_des_hooks) while leaving any
        plugin the operator authored themselves untouched -- OpenCodeDESPlugin
        owns only its own dedicated shim file.
        """
        if self.dry_run:
            self.logger.info("  🚨 [DRY RUN] Would remove OpenCode DES shim")
            return

        try:
            from scripts.install.plugins.base import InstallContext
            from scripts.install.plugins.opencode_des_plugin import OpenCodeDESPlugin
        except ImportError:
            from plugins.base import InstallContext
            from plugins.opencode_des_plugin import OpenCodeDESPlugin

        context = InstallContext(
            claude_dir=self.claude_config_dir,
            scripts_dir=self.claude_config_dir / "scripts",
            templates_dir=self.claude_config_dir / "templates",
            logger=self.logger,
        )
        result = OpenCodeDESPlugin().uninstall(context)
        if result.success:
            self.logger.info("  🗑️ Removed OpenCode DES shim")
        else:
            self.logger.warn(f"  ⚠️ OpenCode DES shim removal: {result.message}")

    def remove_des_hook_scripts(self) -> None:
        """Remove current and retired installer-owned DES hook scripts."""
        if self.dry_run:
            self.logger.info("  🚨 [DRY RUN] Would remove DES hook scripts")
            return

        # Current scripts come from the canonical install list. The small
        # retired list is intentional migration cleanup for old installations.
        from scripts.install.plugins.des_plugin import DESPlugin

        scripts_dir = self.claude_config_dir / "scripts"
        removed_count = 0
        for hook_script_name in (*DESPlugin.DES_HOOKS, *DESPlugin.RETIRED_HOOK_SCRIPTS):
            hook_script_path = scripts_dir / hook_script_name
            if hook_script_path.exists():
                hook_script_path.unlink()
                removed_count += 1
                self.logger.info(f"  🗑️ Removed DES hook script: {hook_script_name}")

        if removed_count == 0:
            self.logger.info("  ✅ No DES hook scripts to remove (already clean)")

    def _has_flat_nw_residue(self, noun: str) -> bool:
        """True if any flat nw-* entry survives under ~/.claude/{noun}/.

        Detects the orphan flat layout the nested-only remover used to miss,
        INCLUDING dangling symlinks (glob yields them without stat). Used by
        validate_removal so a flat-layout leftover is an honest ❌, not a false ✅.
        """
        parent = self.claude_config_dir / noun
        if not parent.exists():
            return False
        return any(parent.glob("nw-*"))

    def remove_attribution(self) -> None:
        """Remove the nWave-managed attribution payload from settings.json.

        Mirrors remove_des_hooks: dry-run guard + fail-safe try/except so an
        attribution-removal failure NEVER aborts the uninstall. Delegates to the
        already-hardened remove_settings_attribution, which removes the payload
        only when it still matches what nWave wrote (a user-modified value is
        preserved) and leaves neighbouring settings.json keys intact and ordered.

        claude_dir is passed EXPLICITLY so CLAUDE_CONFIG_DIR / non-standard
        installs are honoured; omitting it would default to ~/.claude and
        reintroduce the residue bug under isolation.
        """
        if self.dry_run:
            self.logger.info(
                "  🚨 [DRY RUN] Would remove nWave attribution from settings.json"
            )
            return

        with self.logger.progress_spinner("  🚧 Removing nWave attribution..."):
            try:
                remove_settings_attribution(claude_dir=self.claude_config_dir)
                self.logger.info("  🗑️ Removed nWave attribution from settings.json")
            except Exception as exc:  # fail-safe: never abort the uninstall
                self.logger.warn(f"  ⚠️ Attribution removal skipped: {exc}")

    def validate_removal(self) -> bool:
        """Validate complete removal."""
        if self.dry_run:
            self.logger.info("  🚨 [DRY RUN] Would validate complete removal")
            return True

        self.logger.info("  🔍 Validating complete removal...")

        agents_nw_dir = self.claude_config_dir / "agents" / "nw"
        commands_nw_dir = self.claude_config_dir / "commands" / "nw"
        manifest_file = self.claude_config_dir / "nwave-manifest.txt"
        install_log = self.claude_config_dir / "nwave-install.log"

        # Check DES hooks + managed attribution removed
        des_hooks_removed = True
        attribution_removed = True
        settings_file = self.claude_config_dir / "settings.json"
        if settings_file.exists():
            try:
                with open(settings_file, encoding="utf-8") as f:
                    config = json.load(f)
                    if "hooks" in config:
                        hooks_str = json.dumps(config["hooks"])
                        if (
                            "des/adapters/drivers/hooks/claude_code_hook_adapter"
                            in hooks_str
                        ):
                            des_hooks_removed = False
                    # Fail only on the MANAGED value; a user-modified credit must
                    # NOT fail validation (compare to the constant, not presence).
                    if (config.get("attribution") or {}).get(
                        "commit"
                    ) == NWAVE_MANAGED_COMMIT:
                        attribution_removed = False
            except (OSError, json.JSONDecodeError):
                pass

        checks = [
            (
                "Agents",
                not agents_nw_dir.exists() and not self._has_flat_nw_residue("agents"),
            ),
            (
                "Commands",
                not commands_nw_dir.exists()
                and not self._has_flat_nw_residue("commands"),
            ),
            ("DES Hooks", des_hooks_removed),
            ("Attribution", attribution_removed),
            ("Manifest", not manifest_file.exists()),
            ("Install Log", not install_log.exists()),
        ]

        errors = 0
        for name, removed in checks:
            if removed:
                self.logger.info(f"    ✅ {name} removed")
            else:
                self.logger.error(f"    ❌ {name} still exists")
                errors += 1

        if errors == 0:
            self.logger.info("  ✅ Uninstallation validation passed")
            return True
        else:
            self.logger.error(
                f"  ❌ Uninstallation validation failed ({errors} errors)"
            )
            return False

    def create_uninstall_report(self) -> None:
        """Create uninstallation report."""
        if self.dry_run:
            self.logger.info("  🚨 [DRY RUN] Would create uninstall report")
            return

        backup_dir = (
            self.backup_manager.backup_dir if self.backup_before_removal else None
        )

        ManifestWriter.write_uninstall_report(self.claude_config_dir, backup_dir)

        self.logger.info("  📄 Uninstall report created")


def show_title_panel(logger: Logger, dry_run: bool = False) -> None:
    """Display styled title panel when uninstaller starts.

    Args:
        logger: Logger instance for styled output.
        dry_run: Whether running in dry-run mode.
    """
    print_logo(logger)
    mode_indicator = " 🚨 [DRY RUN]" if dry_run else ""
    logger.info("")
    logger.info(f"  🗑️ Uninstaller v{__version__}{mode_indicator}")
    logger.info("")


def show_uninstall_summary(logger: Logger, backup_dir=None) -> None:
    """Display uninstallation summary panel at end of successful uninstall.

    Args:
        logger: Logger instance for styled output.
        backup_dir: Path to backup directory (if created).
    """
    logger.info("")
    logger.info("  🍾 Framework removed successfully")
    logger.info("    ✅ All nWave agents removed")
    logger.info("    ✅ All nWave commands removed")
    logger.info("    ✅ DES hooks removed")
    logger.info("    ✅ Configuration files removed")
    logger.info("    ✅ Installation logs removed")
    logger.info("    ✅ Old backup directories removed")
    if backup_dir:
        logger.info(f"    📦 Backup: {backup_dir}")
    else:
        logger.info("    🗑️ No backup created")
    logger.info("")


def show_help():
    """Show help message."""
    print_logo()
    B, N = _ANSI_BLUE, _ANSI_NC
    help_text = f"""
{B}DESCRIPTION:{N}
    Completely removes the nWave ATDD agent framework from your global Claude config directory.
    This removes all specialized agents, commands, configuration files, logs, and backups.

{B}USAGE:{N}
    python uninstall_nwave.py [OPTIONS]

{B}OPTIONS:{N}
    --backup         Create backup before removal (recommended)
    --force          Skip confirmation prompts
    --dry-run        Show what would be removed without making any changes
    --help           Show this help message

{B}EXAMPLES:{N}
    python uninstall_nwave.py              # Interactive uninstall with confirmation
    python uninstall_nwave.py --dry-run    # Show what would be removed
    python uninstall_nwave.py --backup     # Create backup before removal
    python uninstall_nwave.py --force      # Uninstall without confirmation prompts

{B}WHAT GETS REMOVED:{N}
    - All nWave agents in agents/nw/ directory
    - All nWave commands in commands/nw/ directory
    - DES hooks from Claude Code settings.json
    - nWave configuration files (manifest)
    - nWave installation logs and backup directories

{B}IMPORTANT:{N}
    This action cannot be undone unless you use --backup option.
"""
    print(help_text)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Uninstall nWave framework", add_help=False
    )
    parser.add_argument(
        "--backup", action="store_true", help="Create backup before removal"
    )
    parser.add_argument(
        "--force", action="store_true", help="Skip confirmation prompts"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done"
    )
    parser.add_argument("--help", "-h", action="store_true", help="Show help")

    args = parser.parse_args()

    if args.help:
        show_help()
        return 0

    uninstaller = NWaveUninstaller(
        backup_before_removal=args.backup, force=args.force, dry_run=args.dry_run
    )

    # Show title panel at startup
    show_title_panel(uninstaller.logger, dry_run=args.dry_run)

    if args.dry_run:
        uninstaller.logger.info("  🚨 DRY RUN MODE; no changes will be made")

    # Check for installation
    if not uninstaller.check_installation():
        return 0

    # A native-only (Codex/Copilot/OpenCode) uninstall has no Claude
    # discovery surface -- do not enable persistent uninstall logging under
    # claude_config_dir for it.
    if uninstaller.claude_installation_present:
        uninstaller.enable_uninstall_logging()

    # Confirm removal
    if not uninstaller.confirm_removal():
        uninstaller.logger.info("")
        uninstaller.logger.info("  ⚠️ Uninstallation cancelled by user")
        return 0

    # Check global config (prompt keep/delete before backup)
    uninstaller.check_global_config()

    # Create backup
    uninstaller.create_backup()

    # Remove components
    uninstaller.remove_agents()
    uninstaller.remove_skills()
    uninstaller.remove_commands()
    uninstaller.remove_lib_python()
    uninstaller.remove_host_neutral_des_runtime()
    uninstaller.remove_des_hooks()
    uninstaller.remove_copilot_des_hooks()
    uninstaller.remove_opencode_des_hooks()
    uninstaller.remove_des_hook_scripts()
    uninstaller.remove_attribution()
    uninstaller.remove_config_files()
    uninstaller.remove_backups()

    # Validate and report
    if not uninstaller.validate_removal():
        uninstaller.logger.error("  ❌ Uninstallation failed validation")
        return 1

    # A native-only uninstall has no Claude discovery surface for the report
    # to live in -- skip writing it rather than creating claude_config_dir.
    if uninstaller.claude_installation_present:
        uninstaller.create_uninstall_report()

    # Show uninstall summary panel
    backup_dir = uninstaller.backup_manager.backup_dir if args.backup else None
    show_uninstall_summary(uninstaller.logger, backup_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
