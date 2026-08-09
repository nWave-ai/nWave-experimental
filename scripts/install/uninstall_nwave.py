#!/usr/bin/env python3
"""
nWave Framework Uninstallation Script

Cross-platform uninstaller for the nWave methodology framework.
Completely removes nWave framework from global Claude config directory.

Usage: python uninstall_nwave.py [--backup] [--force] [--dry-run] [--help]
"""

import argparse
import json
import os
import shutil
import sys
from dataclasses import dataclass
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
    from scripts.shared.skill_distribution import (
        DATA_FAMILY_KEY,
        MANIFEST_FILENAME,
        SKILLS_FAMILY_KEY,
        TEMPLATES_FAMILY_KEY,
        UTILITIES_FAMILY_KEY,
        FamilyRemovalEvidence,
        read_family_record,
        remove_family_record,
    )
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
    from shared.skill_distribution import (
        DATA_FAMILY_KEY,
        MANIFEST_FILENAME,
        SKILLS_FAMILY_KEY,
        TEMPLATES_FAMILY_KEY,
        UTILITIES_FAMILY_KEY,
        FamilyRemovalEvidence,
        read_family_record,
        remove_family_record,
    )

# The DES manifest filename each native (non-Claude) plugin writes under its
# own host config dir -- each plugin module repeats this same literal as a
# private module-level constant, so it is repeated here rather than reaching
# into another module's private name.
_NATIVE_DES_MANIFEST_FILENAME = ".nwave-des-manifest.json"

# ANSI color codes for --help output (only consumer)
_ANSI_BLUE = "\033[0;34m"
_ANSI_NC = "\033[0m"  # No Color

__version__ = "1.1.0"


@dataclass(frozen=True)
class ClaudeOwnershipInventory:
    """Positive-ownership snapshot of the Claude discovery surface.

    Produced by exactly one read-only scan (`scan_claude_ownership`), which
    both `validate_removal` and the removal methods consult instead of each
    re-deriving ownership ad hoc. Ownership is established only by manifest
    membership under the family's OWN key (never a legacy/superseded key --
    `remove_family_record` never adopts or removes those, so a scan that
    claimed them as owned would report residue nothing can ever clear), or
    an exact dedicated legacy root -- never a `nw-*` prefix/glob, which would
    misclassify a coincidentally-named user file as nWave residue.
    """

    agents_legacy_root_present: bool
    commands_legacy_root_present: bool
    skills_legacy_root_present: bool
    skills_manifest_status: str  # "absent" | "corrupt" | "present"
    skills_owned_present: frozenset[str]
    templates_manifest_status: str  # "absent" | "corrupt" | "present"
    templates_owned_present: frozenset[str]
    utilities_manifest_status: str  # "absent" | "corrupt" | "present"
    utilities_owned_present: frozenset[str]
    data_manifest_status: str  # "absent" | "corrupt" | "present"
    data_owned_present: frozenset[str]


def _scan_family_ownership(target_dir: Path, *, key: str) -> tuple[str, frozenset[str]]:
    """Read-only ownership scan for one manifest-tracked family.

    Shared by every family scanned by `scan_claude_ownership` -- a missing
    or corrupt manifest yields an empty owned set (never a guess), and a
    tracked name only counts as owned if it still exists on disk.
    """
    manifest_path = target_dir / MANIFEST_FILENAME
    if not manifest_path.exists():
        return "absent", frozenset()
    try:
        record = read_family_record(target_dir, key=key)
    except (OSError, ValueError, AttributeError):
        return "corrupt", frozenset()
    tracked = record.tracked or frozenset()
    owned = frozenset(
        name
        for name in tracked
        if (target_dir / name).exists() or (target_dir / name).is_symlink()
    )
    return "present", owned


def scan_claude_ownership(claude_config_dir: Path) -> ClaudeOwnershipInventory:
    """Read-only total scan of what nWave positively owns, once.

    Never mutates the tree and never calls `remove_family_record` -- it only
    reads the manifest (`read_family_record`) and stats dedicated paths, so
    two scans with no intervening removal return an equal (`==`) inventory.
    A missing or corrupt manifest yields an empty owned set (never a guess);
    a scan can therefore never manufacture ownership by itself.
    `adopt_legacy` is deliberately NOT passed: `remove_family_record` only
    ever reads/removes the family's own key, so honoring a legacy-adopted
    key here would claim ownership over members mutation can never clear.
    """
    skills_dir = claude_config_dir / "skills"
    templates_dir = claude_config_dir / "templates"
    scripts_dir = claude_config_dir / "scripts"
    data_dir = claude_config_dir / "data"

    skills_manifest_status, skills_owned_present = _scan_family_ownership(
        skills_dir, key=SKILLS_FAMILY_KEY
    )
    templates_manifest_status, templates_owned_present = _scan_family_ownership(
        templates_dir, key=TEMPLATES_FAMILY_KEY
    )
    utilities_manifest_status, utilities_owned_present = _scan_family_ownership(
        scripts_dir, key=UTILITIES_FAMILY_KEY
    )
    data_manifest_status, data_owned_present = _scan_family_ownership(
        data_dir, key=DATA_FAMILY_KEY
    )

    return ClaudeOwnershipInventory(
        agents_legacy_root_present=(claude_config_dir / "agents" / "nw").exists(),
        commands_legacy_root_present=(claude_config_dir / "commands" / "nw").exists(),
        skills_legacy_root_present=(skills_dir / "nw").exists(),
        skills_manifest_status=skills_manifest_status,
        skills_owned_present=skills_owned_present,
        templates_manifest_status=templates_manifest_status,
        templates_owned_present=templates_owned_present,
        utilities_manifest_status=utilities_manifest_status,
        utilities_owned_present=utilities_owned_present,
        data_manifest_status=data_manifest_status,
        data_owned_present=data_owned_present,
    )


def _is_legacy_flat_nw_symlink(entry: Path, nested_dir: Path) -> bool:
    """True if `entry` is a legacy flat symlink into the dedicated `nested_dir`.

    Positive identification only -- never name-prefix ownership. `entry` must
    itself be a symlink named `nw-*` whose RAW (unresolved) target lexically
    resolves inside `nested_dir` (the dedicated `{noun}/nw/` root this same
    family owns), dangling target included. Uses `Path.readlink` -- never
    `Path.resolve()` -- so neither the symlink itself nor any intermediate
    path component is ever followed on disk; only the link's own recorded
    text and `nested_dir` are compared lexically. A regular file, a
    directory, or a symlink pointing anywhere else is a preserved user
    sibling even when its name starts with `nw-`.
    """
    if not entry.is_symlink() or not entry.name.startswith("nw-"):
        return False
    try:
        raw_target = entry.readlink()
    except OSError:
        return False
    target = Path(raw_target)
    if not target.is_absolute():
        target = entry.parent / target
    normalized_target = Path(os.path.normpath(str(target)))
    normalized_nested = Path(os.path.normpath(str(nested_dir)))
    try:
        normalized_target.relative_to(normalized_nested)
    except ValueError:
        return False
    return True


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
        # Set by remove_skills(); classified by _skills_removal_state() and
        # consulted by validate_removal() -- None means remove_skills() has
        # not run yet this instance, which validates the same as a missing
        # manifest (never a false green).
        self._skills_removal_evidence: FamilyRemovalEvidence | None = None
        # Set by remove_templates()/remove_utility_scripts()/remove_data();
        # keyed by family label, consulted by validate_removal() via
        # _family_removal_state(). A missing entry validates the same as a
        # missing manifest (never a false green).
        self._family_removal_evidence: dict[str, FamilyRemovalEvidence] = {}

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
        """Remove nWave skills via manifest ownership record only.

        Flat `~/.claude/skills/nw-<name>/` directories listed in
        skills/.nwave-manifest.json are removed via remove_family_record
        (ownership tracking) -- the sole mutator, which always runs and
        revalidates safety immediately before deleting. scan_claude_ownership's
        skills_manifest_status classification picks which outcome message
        fires (a genuine decision input, not just the count it also reports).
        Legacy nested `~/.claude/skills/nw/<name>/` layout is removed
        unconditionally. User-created skills (untracked nw-*) and non-nw-*
        files are preserved. Missing/corrupt manifest preserves all
        skills/nw-* entries.
        """
        skills_dir = self.claude_config_dir / "skills"

        if self.dry_run:
            self.logger.info("  🚨 [DRY RUN] Would remove nWave skills")
            if skills_dir.exists():
                if (skills_dir / ".nwave-manifest.json").exists():
                    self.logger.info(
                        "    🚨 [DRY RUN] Would consider manifest-owned "
                        "skills/nw-* members for removal"
                    )
                else:
                    self.logger.info(
                        "    🚨 [DRY RUN] No manifest found; would preserve "
                        "all skills/nw-* entries"
                    )
                if (skills_dir / "nw").exists():
                    self.logger.info(
                        "    🚨 [DRY RUN] Would remove legacy skills/nw/ dir"
                    )
            return

        with self.logger.progress_spinner("  🚧 Removing nWave skills..."):
            if skills_dir.exists():
                # scan_claude_ownership() is the one total read-only scan;
                # its skills_manifest_status classification -- not a second
                # reading of result.status -- picks which message below
                # fires, so the scan genuinely drives what gets reported
                # instead of existing only for the count on the next line.
                # remove_family_record still runs unconditionally: it is the
                # sole mutator and the only one that revalidates safety
                # (and can detect "blocked") immediately before deleting.
                inventory = scan_claude_ownership(self.claude_config_dir)
                self.logger.info(
                    f"  🔍 {len(inventory.skills_owned_present)} manifest-owned "
                    "skills currently on disk"
                )
                result = remove_family_record(skills_dir, key=SKILLS_FAMILY_KEY)
                self._skills_removal_evidence = result

                if inventory.skills_manifest_status != "present":
                    category = (
                        "absent"
                        if inventory.skills_manifest_status == "absent"
                        else "corrupt"
                    )
                    self.logger.warn(self._skills_removal_diagnosis(category))
                elif result.status == "blocked":
                    self.logger.warn(
                        f"  ⚠️ Could not remove {len(result.blocked)} skills "
                        f"(non-success)\n{self._skills_removal_diagnosis('blocked')}"
                    )
                else:
                    self.logger.info(
                        f"  🗑️ Removed {len(result.removed)} manifest-owned "
                        "skills/nw-* members"
                    )

                legacy_nested = skills_dir / "nw"
                if legacy_nested.exists():
                    shutil.rmtree(legacy_nested)
                    self.logger.info("  🗑️ Removed legacy skills/nw directory")
            else:
                # Nothing was ever installed under skills/ -- already clean,
                # not the same state as "a manifest was expected but missing".
                self._skills_removal_evidence = FamilyRemovalEvidence(
                    "complete", frozenset(), frozenset(), frozenset()
                )

            if skills_dir.exists():
                try:
                    if not any(skills_dir.iterdir()):
                        skills_dir.rmdir()
                        self.logger.info("  🗑️ Removed empty skills directory")
                    else:
                        self.logger.info("  📂 Kept skills directory (contains files)")
                except OSError:
                    self.logger.info("  📂 Kept skills directory (contains files)")

    def _skills_removal_state(self) -> str:
        """Classify this run's skills removal into the five owed states.

        "absent-before-run" (no manifest existed) and "corrupt" (manifest
        unparsable) never validate green -- ownership was never established,
        so nothing can be honestly asserted as removed. "blocked" stays red
        (a tracked member survived). A completed run is green whether it
        actually deleted members this run ("removed-completely-this-run")
        or found the family already clean ("already-clean").

        `evidence is None` means remove_skills() has not run this instance
        (e.g. validate_removal() called standalone). That is honestly
        "already-clean" -- not "absent-before-run" -- when the skills
        directory does not currently exist on disk: a family that was never
        installed carries no manifest to be missing. When the directory DOES
        exist unread, ownership genuinely was never established, so it stays
        "absent-before-run".
        """
        evidence = self._skills_removal_evidence
        if evidence is None:
            skills_dir = self.claude_config_dir / "skills"
            return "already-clean" if not skills_dir.exists() else "absent-before-run"
        if evidence.status == "missing_manifest":
            return "absent-before-run"
        if evidence.status == "invalid_manifest":
            return "corrupt"
        if evidence.status == "blocked":
            return "blocked"
        return "removed-completely-this-run" if evidence.removed else "already-clean"

    def _skills_removal_diagnosis(self, category: str) -> str:
        """WHAT/WHY/HOW for a non-green skills outcome, with an actionable HOW.

        Shared by remove_skills() (reported as it happens) and
        validate_removal() (reported as the final verdict) so the two
        surfaces never drift into two different explanations for the same
        category. `category` is one of "absent" | "corrupt" | "blocked" |
        "residue" (the last covers a reported-clean run whose post-removal
        scan still finds owned or legacy residue).
        """
        what, why, how = {
            "absent": (
                "no skills/.nwave-manifest.json was found before this run",
                "ownership was never established, so no skills/nw-* entry "
                "could be honestly attributed to nWave and removed",
                "re-run the nWave installer to regenerate the manifest, "
                "then re-run uninstall; if skills/nw-* entries remain and "
                "you can confirm they are nWave-owned, remove them by hand",
            ),
            "corrupt": (
                "skills/.nwave-manifest.json could not be parsed",
                "ownership was never established, so no skills/nw-* entry "
                "could be honestly attributed to nWave and removed",
                "restore skills/.nwave-manifest.json from a backup or "
                "reinstall to regenerate it, then re-run uninstall; if "
                "skills/nw-* entries remain and you can confirm they are "
                "nWave-owned, remove them by hand",
            ),
            "blocked": (
                "one or more manifest-owned skills/nw-* entries could not be removed",
                "a filesystem or permission error stopped the mutation "
                "part-way through",
                "check filesystem permissions on the skills directory and "
                "re-run uninstall; if it persists, remove the reported "
                "skills/nw-* entries by hand after confirming ownership",
            ),
            "residue": (
                "a manifest-owned skill or the legacy skills/nw directory "
                "is still present on disk",
                "the removal pass reported success but a fresh scan found "
                "residue anyway",
                "inspect skills/ for leftover nw-* entries or a legacy "
                "skills/nw directory and remove them by hand, then re-run "
                "uninstall to confirm",
            ),
        }[category]
        return f"  WHAT: {what} WHY: {why} HOW: {how}"

    def remove_templates(self) -> None:
        """Remove nWave templates via manifest ownership record only."""
        self._remove_family_dir(
            subdir="templates", key=TEMPLATES_FAMILY_KEY, family_label="templates"
        )

    def remove_utility_scripts(self) -> None:
        """Remove nWave non-hook utility scripts via manifest ownership record only.

        Shares `~/.claude/scripts/` with DES hook scripts (removed separately
        by `remove_des_hook_scripts`); `remove_family_record` only ever
        touches its own `UTILITIES_FAMILY_KEY` members, so the sibling hook
        scripts and the manifest key that tracks them are untouched.
        """
        self._remove_family_dir(
            subdir="scripts", key=UTILITIES_FAMILY_KEY, family_label="utility scripts"
        )

    def remove_data(self) -> None:
        """Remove the installed nWave data tree via manifest ownership record only."""
        self._remove_family_dir(subdir="data", key=DATA_FAMILY_KEY, family_label="data")

    def _remove_family_dir(self, *, subdir: str, key: str, family_label: str) -> None:
        """Remove one manifest-tracked family from `~/.claude/{subdir}/`.

        Shared by remove_templates/remove_utility_scripts/remove_data: each
        owns a distinct manifest key inside a directory that may be shared
        with sibling families or untracked user files, so `remove_family_record`
        (the sole mutator) is the only thing that ever deletes -- it removes
        only its own key's listed members and preserves everything else,
        including sibling manifest keys and untracked siblings. The parent
        directory is removed only if it becomes fully empty.
        """
        target_dir = self.claude_config_dir / subdir

        if self.dry_run:
            self.logger.info(f"  🚨 [DRY RUN] Would remove nWave {family_label}")
            return

        with self.logger.progress_spinner(f"  🚧 Removing nWave {family_label}..."):
            if target_dir.exists():
                result = remove_family_record(target_dir, key=key)
                self._family_removal_evidence[family_label] = result

                if result.status == "blocked":
                    self.logger.warn(
                        f"  ⚠️ Could not remove {len(result.blocked)} {family_label} "
                        f"(non-success)\n{self._family_removal_diagnosis(family_label, 'blocked')}"
                    )
                elif result.status == "missing_manifest":
                    self.logger.info(
                        f"  ℹ️ No {family_label} manifest found; nothing to remove"
                    )
                elif result.status == "invalid_manifest":
                    self.logger.warn(
                        f"  ⚠️ {family_label} manifest could not be parsed"
                        f"\n{self._family_removal_diagnosis(family_label, 'corrupt')}"
                    )
                else:
                    self.logger.info(
                        f"  🗑️ Removed {len(result.removed)} manifest-owned "
                        f"{family_label}"
                    )
            else:
                self._family_removal_evidence[family_label] = FamilyRemovalEvidence(
                    "complete", frozenset(), frozenset(), frozenset()
                )

            if target_dir.exists():
                try:
                    if not any(target_dir.iterdir()):
                        target_dir.rmdir()
                        self.logger.info(f"  🗑️ Removed empty {subdir} directory")
                except OSError:
                    pass

    # family_label -> subdir name under claude_config_dir, for the
    # dir-existence check `_family_removal_state` needs when its remover
    # never ran this instance (validate_removal() called standalone).
    _FAMILY_SUBDIRS = {
        "templates": "templates",
        "utility scripts": "scripts",
        "data": "data",
    }

    def _family_removal_state(self, family_label: str) -> str:
        """Classify a family removal into the same states `_skills_removal_state` uses.

        `evidence is None` means this family's remover has not run this
        instance. That is honestly "already-clean" -- not
        "absent-before-run" -- when the family's directory does not
        currently exist on disk: a family that was never installed carries
        no manifest to be missing.
        """
        evidence = self._family_removal_evidence.get(family_label)
        if evidence is None:
            subdir = self._FAMILY_SUBDIRS[family_label]
            target_dir = self.claude_config_dir / subdir
            return "already-clean" if not target_dir.exists() else "absent-before-run"
        if evidence.status == "missing_manifest":
            return "absent-before-run"
        if evidence.status == "invalid_manifest":
            return "corrupt"
        if evidence.status == "blocked":
            return "blocked"
        return "removed-completely-this-run" if evidence.removed else "already-clean"

    def _family_removal_diagnosis(self, family_label: str, category: str) -> str:
        """WHAT/WHY/HOW for a non-green family removal outcome."""
        what, why, how = {
            "absent": (
                f"no {family_label} manifest was found before this run",
                "ownership was never established, so no entry could be "
                "honestly attributed to nWave and removed",
                "re-run the nWave installer to regenerate the manifest, "
                "then re-run uninstall",
            ),
            "corrupt": (
                f"the {family_label} manifest could not be parsed",
                "ownership was never established, so no entry could be "
                "honestly attributed to nWave and removed",
                "restore the manifest from a backup or reinstall to "
                "regenerate it, then re-run uninstall",
            ),
            "blocked": (
                f"one or more manifest-owned {family_label} could not be removed",
                "a filesystem or permission error stopped the mutation "
                "part-way through",
                f"check filesystem permissions and re-run uninstall; the "
                f"blocked {family_label} stay recorded in the manifest for retry",
            ),
            "residue": (
                f"a manifest-owned {family_label} entry is still present on disk",
                "the removal pass reported success but a fresh scan found "
                "residue anyway",
                f"inspect the {family_label} directory for leftovers and "
                "remove them by hand, then re-run uninstall to confirm",
            ),
        }[category]
        return f"  WHAT: {what} WHY: {why} HOW: {how}"

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

            # Flat layout: a public/flat install writes flat {noun}/nw-*.md
            # symlinks into the dedicated nested_dir above; the nested remover
            # only clears the nested root, missing them. Ownership here is
            # POSITIVE, never prefix/glob: only a symlink whose raw target
            # lexically resolves inside nested_dir (dangling included, so it
            # is unlinked rather than followed -- a followed dangling link
            # would otherwise survive uninstall and crash the next install's
            # backup step) is ours. A regular file, a directory, or a symlink
            # pointing elsewhere is a preserved user sibling even when its
            # name starts with nw-.
            flat_removed = 0
            if parent_dir.exists():
                for entry in parent_dir.glob("nw-*"):
                    if _is_legacy_flat_nw_symlink(entry, nested_dir):
                        entry.unlink()
                        flat_removed += 1
            if flat_removed:
                self.logger.info(
                    f"  🗑️ Removed {flat_removed} legacy flat {noun}/nw-* symlinks"
                )

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
        """True if a positively-identified legacy flat nw-* symlink survives
        under ~/.claude/{noun}/.

        Detects the orphan flat layout the nested-only remover used to miss,
        INCLUDING dangling symlinks (glob yields them without stat) -- but
        only a symlink whose raw target lexically resolves inside the
        dedicated {noun}/nw/ root (see `_is_legacy_flat_nw_symlink`). A
        user-owned flat file, directory, or a symlink pointing elsewhere is
        never residue, even when its name starts with nw-. Used by
        validate_removal so a genuine legacy leftover is an honest ❌, never
        a false ✅, while a coincidentally-named user sibling is never
        misclassified as nWave residue.
        """
        parent = self.claude_config_dir / noun
        if not parent.exists():
            return False
        nested_dir = parent / "nw"
        return any(
            _is_legacy_flat_nw_symlink(entry, nested_dir)
            for entry in parent.glob("nw-*")
        )

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

        inventory = scan_claude_ownership(self.claude_config_dir)
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
                not inventory.agents_legacy_root_present
                and not self._has_flat_nw_residue("agents"),
            ),
            (
                "Commands",
                not inventory.commands_legacy_root_present
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

        skills_state = self._skills_removal_state()
        skills_clean = (
            skills_state in ("removed-completely-this-run", "already-clean")
            and not inventory.skills_owned_present
            and not inventory.skills_legacy_root_present
        )
        if skills_clean:
            self.logger.info("    ✅ Skills removed")
        else:
            category = {
                "absent-before-run": "absent",
                "corrupt": "corrupt",
                "blocked": "blocked",
            }.get(skills_state, "residue")
            self.logger.error(
                f"    ❌ Skills not verified clean:\n"
                f"{self._skills_removal_diagnosis(category)}"
            )
            errors += 1

        for family_label, owned_present, display_name in (
            ("templates", inventory.templates_owned_present, "Templates"),
            ("utility scripts", inventory.utilities_owned_present, "Utility scripts"),
            ("data", inventory.data_owned_present, "Data"),
        ):
            state = self._family_removal_state(family_label)
            # Unlike skills (always installed, so an unmanifested skills dir
            # is suspicious), these families are optional: a directory that
            # was never installer-owned -- no manifest, no owned residue --
            # is an idempotent no-op, not a validation failure. Only
            # "corrupt"/"blocked"/actual residue stay LOUD.
            clean = (
                state
                in ("removed-completely-this-run", "already-clean", "absent-before-run")
                and not owned_present
            )
            if clean:
                self.logger.info(f"    ✅ {display_name} removed")
            else:
                category = {
                    "corrupt": "corrupt",
                    "blocked": "blocked",
                }.get(state, "residue")
                self.logger.error(
                    f"    ❌ {display_name} not verified clean:\n"
                    f"{self._family_removal_diagnosis(family_label, category)}"
                )
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
    uninstaller.remove_templates()
    uninstaller.remove_utility_scripts()
    uninstaller.remove_data()
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
