"""DES (Deterministic Execution System) installation plugin."""

import errno
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.shared import hook_definitions as shared_hooks
from scripts.shared.install_paths import (
    host_neutral_runtime_dir,
    resolve_python_path_for_shell,
)
from scripts.shared.skill_distribution import (
    SCRIPTS_FAMILY_KEY,
    UTILITIES_FAMILY_KEY,
    FamilyRecord,
    preserve_warning_message,
    read_family_record,
    sweep_retired_assets,
    unaccounted_names,
    write_family_record,
)

from .base import InstallationPlugin, InstallContext, PluginResult


# ---------------------------------------------------------------------------
# Inlined canonical tree hash (bootstrap-self exemption — slice-01 of
# fix-installer-self-referential-des-import).
#
# This function is a verbatim copy of `des.runtime.tree_hash.canonical_tree_hash`
# (src/des/runtime/tree_hash.py). It MUST NOT be imported from `des.*` at
# install time because at PyPI-install time `des` lives under
# `site-packages/nWave/lib/python/des/` which is NOT on `sys.path` —
# importing it raises `ModuleNotFoundError` and the installer fails with
# `DES module install failed: No module named 'des'`.
#
# SSOT-drift guard: tests/installer/unit/test_des_plugin_tree_hash_parity.py
# asserts byte-identical parity between this inlined copy and the canonical
# `des.runtime.tree_hash.canonical_tree_hash` on 3 fixture trees plus a
# format-lock. Future drift fails loudly.
# ---------------------------------------------------------------------------


def _canonical_tree_hash(tree_root: Path) -> str:
    """Return ``"sha256:<hex>"`` for the canonical hash of ``tree_root``.

    Pure function — reads ``*.py`` files under ``tree_root`` once each. The
    algorithm matches §1.6 of fix-des-self-hosted-gate-sync feature-delta.

    BOOTSTRAP-SELF INLINE COPY of `des.runtime.tree_hash.canonical_tree_hash`.
    Parity locked by tests/installer/unit/test_des_plugin_tree_hash_parity.py.
    """
    sha = hashlib.sha256()
    py_files = sorted(tree_root.rglob("*.py"), key=lambda p: p.relative_to(tree_root))
    for py_file in py_files:
        rel = py_file.relative_to(tree_root).as_posix()
        digest = hashlib.md5(py_file.read_bytes()).hexdigest()
        sha.update(f"{rel}\0{digest}\n".encode())
    return f"sha256:{sha.hexdigest()}"


# Config-asset suffixes the SYS-4 / AD-27 envelope hashes (bootstrap-self inline
# copy — mirrors `des.runtime.tree_hash._CONFIG_ASSET_SUFFIXES`).
_CONFIG_ASSET_SUFFIXES = (".yaml", ".yml", ".json")


def _canonical_config_assets_hash(assets_root: Path) -> str:
    """Return ``"sha256:<hex>"`` for the canonical hash of the config assets.

    SYS-4 / AD-27 config-asset envelope: same algorithm shape as
    ``_canonical_tree_hash`` but over the shipped declarative config glob
    (``*.yaml`` / ``*.yml`` / ``*.json``) under ``assets_root`` instead of
    ``*.py``. BOOTSTRAP-SELF INLINE COPY of
    ``des.runtime.tree_hash.canonical_config_assets_hash`` (cannot import ``des``
    at install time — see the ``_canonical_tree_hash`` note above). Parity locked
    by tests/installer/unit/test_des_plugin_tree_hash_parity.py.
    """
    sha = hashlib.sha256()
    assets = sorted(
        (
            p
            for p in assets_root.rglob("*")
            if p.is_file() and p.suffix in _CONFIG_ASSET_SUFFIXES
        ),
        key=lambda p: p.relative_to(assets_root).as_posix(),
    )
    for asset in assets:
        rel = asset.relative_to(assets_root).as_posix()
        digest = hashlib.md5(asset.read_bytes()).hexdigest()
        sha.update(f"{rel}\0{digest}\n".encode())
    return f"sha256:{sha.hexdigest()}"


# --- Slice-03: CLI shim discovery (feature-delta §2.2 Addition 2 + DDD-4) ---
#
# The filesystem under `src/des/cli/` is the SSOT for the canonical CLI
# module set the spine dispatches. `_discover_shims(source_dir)` globs the
# directory and emits one shim name per CLI module — newly-added CLIs ship
# automatically on next install, closing the drift-across-boundary (F1)
# class the hand-maintained `DESPlugin.DES_SHIMS` list historically hit
# (verify_environmental_e2e, verify_slice_commit_completeness,
# run_contract_gate all got added to the CLI dir but missed by the constant).
#
# `DES_SHIMS_FLOOR` is the frozen regression-floor set the spine MUST keep:
# discovery is asserted ≥ floor by `tests/installer/acceptance/
# fix-des-self-hosted-gate-sync/slice-03-shim-discovery-floor.feature`.
# A release-time engineer adding a new load-bearing CLI module adds its
# stem to this constant; the constant never shrinks silently.

DES_SHIMS_FLOOR = frozenset(
    {
        "at_review_verdict",
        "carpaccio_slice_gate",
        "check_slice_at_completeness",
        "classify_features",
        "convert_to_atdd_pure",
        "health_check",
        "reverify_slice_commit",
        "run_contract_gate",
        "verify_commit_trailers",
        "verify_deliver_integrity",
        "verify_environmental_e2e",
        "verify_slice_commit_completeness",
        "walking_skeleton_done_gate",
        "walking_skeleton_gate",
    }
)


def _discover_shims(source_dir: Path) -> frozenset[str]:
    """Enumerate CLI module stems under `source_dir` (filesystem is SSOT).

    Globs `*.py` files directly under `source_dir`, drops underscore-prefixed
    files (`__init__.py`, `__main__.py`, any future private module), and
    returns the set of stems (no `.py` suffix). Pure function — no side
    effects beyond reading the directory listing.

    Used by the install plugin at install time to enumerate which CLI
    shims to register, replacing the hand-maintained constant that
    historically drifted out of sync with the source tree.
    """
    return frozenset(
        path.stem for path in source_dir.glob("*.py") if not path.stem.startswith("_")
    )


# --- Issue #43: reinstall-over-an-active-runtime __pycache__ race ---
#
# `shutil.rmtree` raises `ENOTEMPTY` when a live process (e.g. an import
# mid-flight against the module being replaced) writes a fresh `__pycache__`
# entry into the tree WHILE the removal walk is in progress. `_robust_rmtree`
# is the single SSOT tolerance wrapper used at both racing loci
# (`_install_des_module`'s module replace, `_clear_bytecode_cache`'s cache
# clear) — a genuine non-race `OSError` (permission denied, etc.) still
# propagates; only `ENOTEMPTY` / `ENOENT` are treated as a settle-and-retry
# race.
def _robust_rmtree(path: Path) -> None:
    """Remove ``path`` recursively, tolerating a concurrent-writer race.

    Retries ``shutil.rmtree`` a few times on ``ENOTEMPTY`` (a racing writer
    settles between attempts) and treats ``ENOENT`` (already gone) as
    success. If the race outlives the retries, falls back to a best-effort
    removal — a leftover racing ``__pycache__`` is harmless: it is either
    overwritten by the fresh copy or recompiled from source on next import.
    Any other ``OSError`` (permission denied, etc.) propagates immediately.
    """
    for _ in range(3):
        try:
            shutil.rmtree(path)
            return
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                return
            if exc.errno != errno.ENOTEMPTY:
                raise
    shutil.rmtree(path, ignore_errors=True)


# SINGLE AUTHORITY for the `scripts/hooks/` source directory across every
# distribution channel and every consumer (fix-cross-host-sessionstart-
# packaging-path, RCA: three independent re-derivations of this same path
# had drifted -- `_get_hook_scripts_source_dir` and `_install_des_hook_
# scripts` each hand-rolled a FLAT-only probe that can never match a wheel
# install, silently shipping zero independent hook scripts to
# `~/.claude/scripts/`.
def _resolve_hook_scripts_source_dir(context: InstallContext) -> Path:
    """Return the one true source directory for `scripts/hooks/*.py`.

    Three physical layouts carry these scripts, tried in existence order
    (NESTED-FIRST, unambiguous by construction -- mirrors the probe already
    proven correct in `DESPlugin._install_nwave_runtime_assets`):

      1. PyPI/pipx wheel -- NESTED under `framework_source/nWave/hooks/`.
         `patch_pyproject.py`'s force-include ships required hook scripts to
         `nWave/nWave/hooks/`, one level
         deeper than `framework_source` itself, which already resolves to
         `site-packages/nWave/` on a pipx install.
      2. GitHub-release `dist/` tarball -- FLAT under
         `framework_source/scripts/hooks/` (no nested `nWave/` child, so
         probe 1 can never false-match this layout).
      3. Dev checkout -- `project_root/scripts/hooks/`.

    Every install-time consumer of `scripts/hooks/*.py` -- the prerequisite
    presence check, the Claude-scoped hook-script copy, and the host-neutral
    runtime-asset copy -- MUST call this one function instead of re-deriving
    the path locally.
    """
    if context.framework_source is not None:
        nested = context.framework_source / "nWave" / "hooks"
        if nested.is_dir():
            return nested
        flat = context.framework_source / "scripts" / "hooks"
        if flat.is_dir():
            return flat
    if context.project_root:
        return context.project_root / "scripts" / "hooks"
    return Path("scripts/hooks")


class RuntimeAssetShippingError(RuntimeError):
    """An nWave source tier failed to ship its declared runtime assets.

    Raised -- never swallowed -- because the defect this guards is a SILENT
    one: the installed package resolves `nWave/` assets as siblings of
    `lib/python`, so an install that omits them reports success and relocates
    the failure onto the operator's machine. Carries a WHAT/WHY/HOW message
    that names the distribution channel to fix.
    """


class DESPlugin(InstallationPlugin):
    """Plugin for installing DES (Deterministic Execution System).

    Demonstrates extensibility: adding DES requires only plugin registration
    without modifying core installer logic.

    Includes hooks installation that properly preserves all existing settings
    in settings.json (global config: permissions, other hooks, etc.).
    """

    # Seconds allowed for the module-import verification subprocess. Sized for
    # slow filesystems (WSL, especially Windows-mounted /mnt/c paths) where
    # Python startup plus first-run .pyc compilation exceeds a tighter budget.
    # A broken install fails fast with a non-zero return code, so a generous
    # timeout only protects the slow-but-correct path — it cannot mask a real
    # failure. See issue #73.
    DES_VERIFY_IMPORT_TIMEOUT_SECONDS = 15

    # DES scripts installed to ~/.claude/scripts/
    DES_SCRIPTS = [
        "scope_boundary_check.py",
    ]

    # Independent DES hook scripts installed to ~/.claude/scripts/.
    DES_HOOKS = [
        "git_stash_guard.py",
        # fix-worktree-removal-liveness-guard (Ale-authorised 2026-07-29):
        # the PreToolUse/Bash hook (wired via hook_definitions.
        # _BASH_WORKTREE_REMOVAL_GUARD) that refuses `git worktree remove`
        # while a live process's cwd is inside the target, the target
        # carries an explicit `git worktree lock`, or the target's branch
        # carries unmerged commits -- replacing "did you check `git
        # status`?" (a confirmation prompt that collects confident-but-wrong
        # yeses) with a decision on the PROPERTY (GDP-8).
        "worktree_removal_guard.py",
    ]

    # Exact files shipped by the retired spine-ledger protocol. Keep this small
    # migration list until upgrades have had a chance to remove old artifacts;
    # it is intentionally not part of DES_HOOKS, so no fresh install can revive
    # the protocol.
    RETIRED_HOOK_SCRIPTS = (
        "spine_ledger_gate.py",
        "spine_ledger_pre_commit_hook.py",
        "spine_ledger_subagent_stop_detector.py",
        "no_verify_reminder.py",
    )
    # These are the complete command strings emitted by the retired shared
    # hook registry.  Upgrade cleanup deliberately uses equality, rather than
    # token matching: hooks.json is user-owned outside the entries installed by
    # this plugin, so a Lyra or user hook may legitimately mention a retired
    # protocol while doing something unrelated.
    _RETIRED_HOOK_COMMANDS = (
        "# des-hook:pre-bash-spine-ledger\n"
        "INPUT=$(cat); "
        'CMD=$(echo "$INPUT" | python3 -c '
        '"import sys,json; print(json.load(sys.stdin)'
        ".get('tool_input',{}).get('command',''))\"); "
        "echo \"$CMD\" | grep -qE '^\\s*git\\s+commit\\b' || exit 0; "
        'echo "$INPUT" | python3 -m scripts.hooks.spine_ledger_pre_commit_hook',
        "# des-hook:pre-bash-spine-ledger-gate-installed\n"
        "INPUT=$(cat); "
        'CMD=$(echo "$INPUT" | python3 -c '
        '"import sys,json; print(json.load(sys.stdin)'
        ".get('tool_input',{}).get('command',''))\"); "
        "echo \"$CMD\" | grep -qE '^\\s*git\\s+commit\\b' || exit 0; "
        "python3 -m scripts.hooks.spine_ledger_gate "
        "--commit-msg-file .git/COMMIT_EDITMSG "
        "--ledger-root .nwave/telemetry/atdd-pure "
        "--target-root . >/dev/null 2>&1 || true",
        "# des-hook:subagent-stop-spine-detector\n"
        "INPUT=$(cat); "
        'echo "$INPUT" | python3 -m scripts.hooks.spine_ledger_subagent_stop_detector',
        "# des-hook:pre-bash-no-verify-reminder\n"
        "INPUT=$(cat); "
        "CMD=$(printf '%s' \"$INPUT\" | python3 -c "
        '"import sys,json; print(json.load(sys.stdin)'
        ".get('tool_input',{}).get('command',''))\"); "
        "printf '%s' \"$CMD\" | grep -qE '\\bgit\\b' || exit 0; "
        "printf '%s' \"$INPUT\" | python3 -m scripts.hooks.no_verify_reminder",
        # fix-execution-log-bash-guard-consolidation (Ale-authorised
        # 2026-08-09): the standalone PreToolUse/Bash execution-log guard
        # (formerly hook_definitions._BASH_EXECUTION_LOG_GUARD) was retired.
        # Upgrade cleanup removes the exact stale registration this installer
        # previously wrote; a user's own hook that happens to mention
        # execution-log is unaffected (equality match, not token match).
        "# des-hook:pre-bash\n"
        "INPUT=$(cat); "
        "CMD=$(printf '%s' \"$INPUT\" | python3 -c "
        '"import sys,json; print(json.load(sys.stdin)'
        ".get('tool_input',{}).get('command',''))\"); "
        "printf '%s' \"$CMD\" | grep -q 'execution-log' || exit 0; "
        "printf '%s' \"$CMD\" | grep -qE "
        "'des\\.cli\\.verify_deliver_integrity|des +verify-integrity' && exit 0; "
        'printf \'%s\\n\' \'{"decision":"block","reason":"Direct modification of '
        "execution-log.json via Bash is blocked.\\n"
        "To read it, use the Read tool.\\n"
        "This retired artifact must not be recreated or modified.\"}'; "
        "exit 2",
        # fix-execution-log-bash-guard-consolidation follow-on
        # (Ale-authorised 2026-08-09): the standalone git-stash guard
        # PreToolUse/Bash registration was retired -- the pre-activation
        # universal `hook_router` call now evaluates the same decision
        # inline on every installed PreToolUse/Bash invocation.
        "# des-hook:pre-bash-git-stash-guard\n"
        "INPUT=$(cat); "
        "CMD=$(printf '%s' \"$INPUT\" | python3 -c "
        '"import sys,json; print(json.load(sys.stdin)'
        ".get('tool_input',{}).get('command',''))\"); "
        "printf '%s' \"$CMD\" | grep -qE '^\\s*git\\s+stash\\b' || exit 0; "
        "printf '%s' \"$INPUT\" | python3 -m scripts.hooks.git_stash_guard",
        # fix-execution-log-bash-guard-consolidation follow-on
        # (Ale-authorised 2026-08-09): the standalone worktree-removal guard
        # PreToolUse/Bash registration was retired for the same reason.
        "# des-hook:pre-bash-worktree-removal-guard\n"
        "INPUT=$(cat); "
        "CMD=$(printf '%s' \"$INPUT\" | python3 -c "
        '"import sys,json; print(json.load(sys.stdin)'
        ".get('tool_input',{}).get('command',''))\"); "
        "printf '%s' \"$CMD\" | grep -qE 'git\\s+worktree\\s+remove' || exit 0; "
        "printf '%s' \"$INPUT\" | python3 -m scripts.hooks.worktree_removal_guard",
    )
    # Retired lifecycle event arrays are intentionally outside HOOK_EVENTS:
    # fresh installs never recreate them.  Upgrade/uninstall still visit only
    # these two historical arrays to remove entries this installer emitted.
    _RETIRED_LIFECYCLE_EVENTS = ("SessionStart", "UserPromptSubmit")
    # SHA-256 values of the two complete historical standalone-affordance
    # commands (SessionStart and UserPromptSubmit).  Equality of the digest is
    # deliberately stricter than the normal DES marker classifier: an entry
    # merely mentioning the old script remains user-owned.
    _RETIRED_AFFORDANCE_COMMAND_DIGESTS = frozenset(
        {
            "4968a29b5dd45962f95dda193b6aa6ec1312550060c22b0acba00ae8fc44298d",
            "fdf22c1f420b78ddec5c3993f316c713ea08a6e1e94567d060a4dc132df0f0f8",
        }
    )
    # Asset-family key for the DES scripts list in the shared
    # .nwave-manifest.json mechanism (scripts/shared/skill_distribution.py).
    SCRIPTS_MANIFEST_KEY = SCRIPTS_FAMILY_KEY

    # DES shims installed to ~/.claude/bin/
    DES_SHIMS = [
        "des",
    ]

    # Pre-consolidation shims removed on upgrade (R17 residuality, slice-01 of
    # fix-des-single-entry-point-consolidation). Any of these found in
    # ~/.claude/bin/ from a previous install is deleted by _install_des_shims
    # so the operator's PATH no longer advertises the legacy entry points.
    LEGACY_DES_SHIMS = (
        "des-log-phase",
        "des-commit",
        "des-init-log",
        "des-verify-integrity",
        "des-health-check",
    )

    # Minimal POSIX system directories written as a last-resort fallback when
    # settings.json has no prior env.PATH AND os.environ has no PATH at install
    # time (highly unusual). Claude Code REPLACES env.PATH entirely (no merge
    # with the inherited shell PATH), so on the normal path the installer
    # seeds env.PATH from os.environ["PATH"] to preserve user-visible
    # directories (~/.local/bin, ~/.deno/bin, /snap/bin, etc.).
    SYSTEM_PATH_FALLBACK = "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

    # DES templates installed to ~/.claude/templates/
    DES_TEMPLATES = [
        ".pre-commit-config-nwave.yaml",
        ".des-audit-README.md",
    ]

    # Hook command template - substituted at install time:
    #   {lib_path}    → $HOME/.claude/lib/python (shell-expanded per machine)
    #   {python_path} → python3 (system PATH) for portability across machines
    #   {action}      → hook action (pre-task, subagent-stop, post-tool-use)
    # Uses $HOME for portability: settings.json is shared across machines
    # via ~/.claude synced directory, so paths must resolve per-machine.
    HOOK_COMMAND_TEMPLATE = (
        "PYTHONPATH={lib_path} {python_path} -m "
        "des.adapters.drivers.hooks.claude_code_hook_adapter {action}"
    )

    # Hook event types that DES registers (from shared definitions)
    HOOK_EVENTS = tuple(shared_hooks.HOOK_EVENT_TYPES)

    def __init__(self) -> None:
        """Initialize DES plugin with name, priority, and dependencies."""
        super().__init__(name="des", priority=50)
        self.dependencies = ["templates", "utilities"]
        self._original_settings: dict[str, Any] | None = (
            None  # For uninstall restoration
        )

    def validate_prerequisites(self, context: InstallContext) -> PluginResult:
        """Validate that DES prerequisites exist before installation.

        Checks for:
        1. DES scripts directory at nWave/scripts/des/
        2. DES templates at nWave/templates/

        Returns:
            PluginResult with success=False and clear error message if missing.
        """
        errors = []

        # Check for DES scripts directory
        scripts_dir = self._get_scripts_source_dir(context)
        if not scripts_dir.exists():
            errors.append(
                "DES scripts not found: nWave/scripts/des/. "
                "Ensure prerequisite scripts are created before DES installation."
            )
        else:
            # Check for required script files
            missing_scripts = []
            for script_name in self.DES_SCRIPTS:
                script_path = scripts_dir / script_name
                if not script_path.exists():
                    missing_scripts.append(script_name)
            if missing_scripts:
                errors.append(
                    f"Missing DES scripts: {', '.join(missing_scripts)}. "
                    f"Required scripts: {', '.join(self.DES_SCRIPTS)}"
                )

            # Check for required shim files in the same scripts/des/ directory
            missing_shims = []
            for shim_name in self.DES_SHIMS:
                shim_path = scripts_dir / shim_name
                if not shim_path.exists():
                    missing_shims.append(shim_name)
            if missing_shims:
                errors.append(
                    f"Missing DES shims: {', '.join(missing_shims)}. "
                    f"Required shims: {', '.join(self.DES_SHIMS)}"
                )

        # Check for the independently useful DES hook scripts.
        hooks_source_dir = self._get_hook_scripts_source_dir(context)
        if hooks_source_dir.exists():
            missing_hooks = []
            for hook_name in self.DES_HOOKS:
                hook_path = hooks_source_dir / hook_name
                if not hook_path.exists():
                    missing_hooks.append(hook_name)
            if missing_hooks:
                errors.append(
                    f"Missing DES hook scripts: {', '.join(missing_hooks)}. "
                    f"Required hooks: {', '.join(self.DES_HOOKS)}"
                )

        # Check for DES templates (use framework_source for dist/ or nWave/)
        templates_dir = (
            context.framework_source / "templates"
            if context.framework_source
            else context.project_root / "nWave" / "templates"
            if context.project_root
            else Path("nWave/templates")
        )
        missing_templates = []
        for template_name in self.DES_TEMPLATES:
            template_path = templates_dir / template_name
            if not template_path.exists():
                missing_templates.append(template_name)

        if missing_templates:
            errors.append(
                f"DES templates not found: {', '.join(missing_templates)}. "
                f"Ensure prerequisite templates exist at nWave/templates/ before DES installation."
            )

        if errors:
            return PluginResult(
                success=False,
                plugin_name="des",
                message=f"DES prerequisite validation failed: {errors[0]}",
                errors=errors,
            )

        return PluginResult(
            success=True,
            plugin_name="des",
            message="DES prerequisites validated successfully",
        )

    def _get_scripts_source_dir(self, context: InstallContext) -> Path:
        """Get the source directory for DES scripts."""
        if context.framework_source:
            source_dir = context.framework_source / "scripts" / "des"
            if source_dir.exists():
                return source_dir
        if context.project_root:
            return context.project_root / "nWave" / "scripts" / "des"
        return Path("nWave/scripts/des")

    def _get_hook_scripts_source_dir(self, context: InstallContext) -> Path:
        """Get the source directory for independently useful DES hook scripts."""
        return _resolve_hook_scripts_source_dir(context)

    def install(self, context: InstallContext) -> PluginResult:
        """Install DES module, scripts, and templates.

        Validates prerequisites before installation to ensure graceful failure
        with clear error messages when required files are missing.
        """
        try:
            # Validate prerequisites first - fail fast with clear message
            prereq_result = self.validate_prerequisites(context)
            if not prereq_result.success:
                context.logger.error(
                    f"  ❌ DES prerequisite check failed: {prereq_result.message}"
                )
                return prereq_result

            # Install DES module
            module_result = self._install_des_module(context)
            if not module_result.success:
                return module_result

            # Every step below this point (data/templates/hooks/shims/config)
            # writes into context.claude_dir -- a Claude discovery surface.
            # A target that never requested "claude_code" (Codex-only,
            # Copilot-only, OpenCode-only, or any combination of those
            # without Claude) must not gain one just because the DES module
            # itself is host-neutral. The prior condition required "codex"
            # specifically to be in the target, so a Copilot- or OpenCode-only
            # install fell through and got the full Claude-scoped install
            # anyway -- a pure non-Claude target creating a Claude discovery
            # surface (fix-non-claude-target-still-creates-claude-surface).
            if "claude_code" not in context.target_platforms:
                return PluginResult(
                    success=True,
                    plugin_name="des",
                    message="host-neutral DES runtime installed (no Claude target requested)",
                )

            # Install DES scripts
            scripts_result = self._install_des_scripts(context)
            if not scripts_result.success:
                return scripts_result

            # Install the independently useful DES hook scripts.
            hook_scripts_result = self._install_des_hook_scripts(context)
            if not hook_scripts_result.success:
                return hook_scripts_result

            # NOTE (fix-pre-push-hook-dual-installer-collision, slice-01): the
            # `_install_git_pre_push_backstop` call formerly here is RETIRED.
            # It wrote a second, non-pre-commit-managed `.git/hooks/pre-push`
            # on top of `pre-commit install`'s banner-marked one, tripping
            # `verify-hooks`'s foreign-hook detector -- see the RCA:
            # docs/analysis/root-cause-analysis-pre-push-hook-dual-installer-collision.md
            # The declare-done backstop's behavior is unchanged and still
            # fires -- it is now a `local` `stages: [pre-push]` hook in
            # `.pre-commit-config.yaml`, so `pre-commit install` is the SOLE
            # writer of `.git/hooks/pre-push`.

            # Install the framework DATA tree -- the runtime reads it, and
            # installing its consumers without it is a silent runtime failure
            # on the operator's machine (fix-installer-never-ships-data-tree).
            data_result = self._install_des_data(context)
            if not data_result.success:
                return data_result

            # Install DES templates
            templates_result = self._install_des_templates(context)
            if not templates_result.success:
                return templates_result

            # Install DES hooks into settings.local.json
            hooks_result = self._install_des_hooks(context)
            if not hooks_result.success:
                return hooks_result

            # Install DES shims to ~/.claude/bin/ and update PATH
            shims_result = self._install_des_shims(context)
            if not shims_result.success:
                return shims_result

            # Bootstrap project-level DES config
            config_result = self._bootstrap_des_config(context)
            if not config_result.success:
                return config_result

            return PluginResult(
                success=True,
                plugin_name="des",
                message="DES installed successfully (module, scripts, templates, hooks, shims, config)",
            )

        except Exception as e:
            return PluginResult(
                success=False,
                plugin_name="des",
                message=f"DES installation failed: {e}",
            )

    def _install_des_module(self, context: InstallContext) -> PluginResult:
        """Install DES Python module to ~/.claude/lib/python/des/."""
        try:
            # Check dist/ pre-built DES module first (imports already rewritten)
            if context.framework_source is not None:
                pre_built = context.framework_source / "lib" / "python" / "des"
                using_prebuilt = (
                    pre_built.exists() and (pre_built / "__init__.py").exists()
                )
            else:
                pre_built = None
                using_prebuilt = False

            if using_prebuilt:
                source_dir = pre_built
            elif context.project_root:
                source_dir = context.project_root / "src" / "des"
            else:
                source_dir = Path("src/des")

            if not source_dir.exists():
                return PluginResult(
                    success=False,
                    plugin_name="des",
                    message=f"DES source not found: {source_dir}",
                )

            lib_python_dir = self._runtime_python_dir(context)
            target_dir = lib_python_dir / "des"

            lib_python_dir.mkdir(parents=True, exist_ok=True)

            # Backup existing if present
            if context.backup_manager and target_dir.exists():
                context.logger.info(f"  💾 Backing up DES module: {target_dir}")
                context.backup_manager.backup_directory(target_dir)

            # Copy module
            if context.dry_run:
                context.logger.info(
                    f"  🚨 [DRY RUN] Would copy {source_dir} → {target_dir}"
                )
            else:
                if target_dir.exists():
                    # Rename-aside atomically frees target_dir even while a
                    # racing importer still holds the old tree's inode open
                    # (issue #43) -- copytree below never contends with a
                    # concurrent __pycache__ write. Fall back to an in-place
                    # resilient removal if the rename itself cannot proceed
                    # (e.g. cross-device target_dir).
                    aside = target_dir.with_name(f"{target_dir.name}.old-{os.getpid()}")
                    try:
                        target_dir.replace(aside)
                    except OSError:
                        _robust_rmtree(target_dir)
                    else:
                        _robust_rmtree(aside)
                # Skip bytecode caches: source __pycache__ is build artefact,
                # not module surface. Without ignore we hit Errno 17 when
                # backup_manager raced on the same nested path.
                shutil.copytree(
                    source_dir,
                    target_dir,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
                )

                # Skip rewriting if pre-built from dist/ (already done by build_dist.py)
                if not using_prebuilt:
                    self._rewrite_import_paths(target_dir, context)

                # Clear bytecode cache to prevent stale .pyc files
                self._clear_bytecode_cache(target_dir, context)

                # Ship the nWave runtime assets the installed des package
                # resolves as siblings of lib/python (Path(__file__).parents[N]
                # / "nWave" / ...): flavors/ (carpaccio_intercept atdd_pure
                # dispatch), data/ (log_persistence + doctor), templates/ +
                # schemas/ (tdd / roadmap loaders), framework-catalog.yaml
                # (carpaccio_slice_gate). The installer shipped the code but
                # never these assets, so every atdd_pure dispatch crashed with
                # a missing lib/nWave/flavors/atdd_pure.yaml
                # (F-DES-INSTALL-SHIPS-NWAVE-RUNTIME-ASSETS).
                #
                # Shipped BEFORE the manifest so the schema-v2 manifest can
                # snapshot the config-asset tree-hash (SYS-4 / AD-27): the
                # runtime freshness gate compares the installed `lib/nWave/`
                # content against this snapshot to catch a drifted shipped
                # config asset.
                nwave_assets_root = self._install_nwave_runtime_assets(
                    context=context,
                    using_prebuilt=using_prebuilt,
                )

                # Write the runtime freshness gate's source-of-truth manifest
                # (fix-des-self-hosted-gate-sync §1.4 + §2.2 Addition 1 +
                # DDD-3). Colocated with the installed package so a partial
                # copy cannot desync it from the code it describes. Schema v2
                # when the config assets were shipped (carries
                # `config_assets_tree_hash`), v1 otherwise.
                self._write_install_manifest(
                    target_dir=target_dir,
                    source_dir=source_dir,
                    using_prebuilt=using_prebuilt,
                    nwave_assets_root=nwave_assets_root,
                )

                # A mixed target (claude_code alongside codex/copilot/opencode)
                # needs the fully-processed module at BOTH runtime locations --
                # each host's own hook hardcodes its own PYTHONPATH independent
                # of which one was chosen as primary above. Mirror the already
                # rewritten+asset-shipped result instead of re-deriving from
                # source, so the two copies cannot diverge.
                secondary_lib_python_dir = self._secondary_runtime_python_dir(
                    context, lib_python_dir
                )
                if secondary_lib_python_dir is not None:
                    secondary_target_dir = secondary_lib_python_dir / "des"
                    secondary_lib_python_dir.mkdir(parents=True, exist_ok=True)
                    if secondary_target_dir.exists():
                        _robust_rmtree(secondary_target_dir)
                    shutil.copytree(
                        target_dir,
                        secondary_target_dir,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
                    )
                    if nwave_assets_root is not None:
                        secondary_assets_root = (
                            secondary_lib_python_dir.parent / "nWave"
                        )
                        if secondary_assets_root.exists():
                            _robust_rmtree(secondary_assets_root)
                        shutil.copytree(
                            nwave_assets_root,
                            secondary_assets_root,
                            ignore=shutil.ignore_patterns(
                                "__pycache__", "*.pyc", "*.pyo"
                            ),
                        )

            return PluginResult(
                success=True,
                plugin_name="des",
                message=f"DES module copied to {target_dir}",
            )

        except RuntimeAssetShippingError as e:
            # Already a WHAT/WHY/HOW message naming the channel -- surface it
            # verbatim rather than burying it under a generic prefix.
            return PluginResult(success=False, plugin_name="des", message=str(e))

        except Exception as e:
            return PluginResult(
                success=False,
                plugin_name="des",
                message=f"DES module install failed: {e}",
            )

    # nWave runtime assets the installed des package resolves as siblings of
    # lib/python (Path(__file__).parents[N] / "nWave" / ...). Code-only shipping
    # leaves these absent and breaks every atdd_pure dispatch.
    _NWAVE_RUNTIME_ASSET_DIRS = (
        "flavors",
        "data",
        "templates",
        "schemas",
        "dispatch",
        "waves",
    )
    _NWAVE_RUNTIME_ASSET_FILES = ("framework-catalog.yaml",)
    _NWAVE_RUNTIME_HOOK_FILES: tuple[str, ...] = ()

    def _install_nwave_runtime_assets(
        self, *, context: InstallContext, using_prebuilt: bool
    ) -> Path | None:
        """Ship nWave runtime assets to ``<claude_dir>/lib/nWave/``.

        Returns the shipped ``lib/nWave/`` root when assets were copied (so the
        caller can snapshot the config-asset tree-hash into the schema-v2
        manifest), or ``None`` when the source is absent or this is a dry run.

        The installed des package reads config siblings of ``lib/python`` at
        runtime: ``carpaccio_intercept`` loads ``nWave/flavors/atdd_pure.yaml``,
        ``log_persistence`` + ``doctor`` read ``nWave/data/``, the tdd / roadmap
        loaders read ``nWave/templates/`` + ``nWave/schemas/``, and
        ``carpaccio_slice_gate`` reads ``nWave/framework-catalog.yaml``. The
        installer shipped only the code, so these resolutions failed on every
        installed instance (F-DES-INSTALL-SHIPS-NWAVE-RUNTIME-ASSETS).

        Two independent "prebuilt" channels ship different physical layouts
        under the same ``using_prebuilt`` flag: the GitHub-release ``dist/``
        tarball is FLAT under ``framework_source`` (``dist/data/``,
        ``dist/flavors/``, ... — no nested ``nWave/`` prefix; ``build_dist.py``'s
        ``build_nwave_runtime_assets`` produces exactly that layout), while the
        PyPI/pipx wheel is NESTED (``site-packages/nWave/nWave/<name>`` —
        ``patch_pyproject.py``'s force-include map ships these assets one
        level deeper, since ``framework_source`` itself already resolves to
        ``site-packages/nWave/`` on a pipx install). Probe NESTED-FIRST with a
        FLAT FALLBACK: a ``dist/`` tarball ``framework_source`` never has a
        ``nWave`` child (no ``build_dist.py`` step ever creates ``dist/nWave/``),
        so the nested probe can only ever match the wheel layout, making the
        two branches unambiguous by construction.

        The hook-script source directory (``runtime_hook_source`` below) uses
        the SAME probe shape, factored out as the single authority
        `_resolve_hook_scripts_source_dir` -- every other consumer of
        `scripts/hooks/*.py` at install time calls it too.
        """
        if using_prebuilt and context.framework_source is not None:
            nested = context.framework_source / "nWave"
            nwave_source = nested if nested.is_dir() else context.framework_source
        elif context.project_root:
            nwave_source = context.project_root / "nWave"
        else:
            nwave_source = Path("nWave")

        runtime_hook_source = _resolve_hook_scripts_source_dir(context)

        channel = self._describe_asset_channel(
            context=context, using_prebuilt=using_prebuilt, nwave_source=nwave_source
        )

        # DECLARED N/A -- not a refusal. A target that carries no nWave tier is
        # a LEGITIMATE install target under the target-machine-agnosticism
        # mandate, so the install proceeds. Said at WARNING so it is visible in
        # the log: a silent `info` is how "no assets shipped" became invisible.
        if not nwave_source.exists():
            context.logger.warning(
                f"  ⚠️  N/A: no nWave tier at {nwave_source} ({channel}) — "
                "runtime assets not applicable to this target; install continues"
            )
            return None

        catalogue = self._nwave_tier_manifest(nwave_source)
        if catalogue is None:
            context.logger.warning(
                f"  ⚠️  N/A: {nwave_source} carries no "
                f"{self._NWAVE_RUNTIME_ASSET_FILES[0]} ({channel}), so it is not "
                "an nWave source tier — runtime assets not applicable to this "
                "target; install continues"
            )
            return None

        target_root = self._runtime_python_dir(context).parent / "nWave"

        if context.dry_run:
            context.logger.info(
                f"  🚨 [DRY RUN] Would ship nWave runtime assets "
                f"{nwave_source} → {target_root}"
            )
            return None

        # `_NWAVE_RUNTIME_ASSET_DIRS` is a CANDIDATE list, not a mandate: the
        # families a given tier ships vary by channel and by era, and nothing
        # declares which ones a particular tree owes. So absence of an
        # individual family is NOT an error -- inferring that mandate from the
        # candidate list would be reading a declaration as stronger than it is.
        # What IS an error is a tier that yields NOTHING: a tree carrying the
        # catalogue but no asset family at all is a broken distribution, and
        # that is the shape a channel gap actually produces.
        target_root.mkdir(parents=True, exist_ok=True)

        shipped_dirs = []
        for subdir in self._NWAVE_RUNTIME_ASSET_DIRS:
            src = nwave_source / subdir
            if (
                not src.is_dir()
                and subdir == "templates"
                and context.templates_dir.is_dir()
            ):
                # Hatch normalizes the "nWave/templates" and "nWave/templates/"
                # force-include keys onto the SAME flat source path, so a
                # nested wheel runtime tier (nwave_source == framework_source /
                # "nWave") never gets its own templates/ subdir -- the flat
                # context.templates_dir is the canonical source in that case.
                src = context.templates_dir
            if not src.is_dir():
                continue
            dst = target_root / subdir
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(
                src,
                dst,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
            )
            shipped_dirs.append(subdir)

        shipped_files = []
        for filename in self._NWAVE_RUNTIME_ASSET_FILES:
            src = nwave_source / filename
            if src.exists():
                shutil.copy2(src, target_root / filename)
                shipped_files.append(filename)

        shipped_hooks = []
        for filename in self._NWAVE_RUNTIME_HOOK_FILES:
            src = runtime_hook_source / filename
            if not src.is_file():
                continue
            destination = target_root / "hooks" / filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, destination)
            destination.chmod(0o755)
            shipped_hooks.append(filename)

        if not shipped_dirs:
            raise RuntimeAssetShippingError(
                f"WHAT: {nwave_source} declares itself an nWave source tier "
                f"(it ships {self._NWAVE_RUNTIME_ASSET_FILES[0]}) but carries "
                "none of the runtime asset families "
                f"({', '.join(self._NWAVE_RUNTIME_ASSET_DIRS)}), so nothing "
                "was shipped. "
                "WHY: the installed des package resolves these as siblings of "
                "lib/python (Path(__file__).parents[N] / 'nWave' / ...) -- a "
                "tier that ships the catalogue and no assets is a broken "
                "distribution, and installing it reports success while every "
                "such read fails later on the operator's machine. "
                f"HOW: this is the {channel}; rebuild it so the tier carries "
                "its assets -- for a distribution run scripts/build_dist.py "
                "(build_nwave_runtime_assets ships "
                f"{'/'.join(self._NWAVE_RUNTIME_ASSET_DIRS)}, build_templates "
                "ships templates), and for a wheel check the force-include map "
                "in scripts/release/patch_pyproject.py."
            )

        # Verify the STRUCTURED FACT -- every entry we actually copied is
        # present at the destination -- never the weak signal "copytree did
        # not raise".
        unarrived = [
            name for name in shipped_dirs if not (target_root / name).is_dir()
        ] + [name for name in shipped_files if not (target_root / name).is_file()]
        unarrived += [
            f"hooks/{name}"
            for name in shipped_hooks
            if not (target_root / "hooks" / name).is_file()
        ]
        if unarrived:
            raise RuntimeAssetShippingError(
                f"WHAT: {len(unarrived)} runtime asset entr"
                f"{'y' if len(unarrived) == 1 else 'ies'} copied from "
                f"{nwave_source} did not arrive at {target_root}: "
                f"{', '.join(unarrived)}. "
                "WHY: a package installed without the assets it resolves fails "
                "at runtime on the operator's machine while the install "
                "reports success. "
                "HOW: check write permissions and free space on the Claude "
                "config directory, then re-run the install."
            )

        context.logger.info(f"  📦 nWave runtime assets shipped to {target_root}")
        return target_root

    @staticmethod
    def _describe_asset_channel(
        *, context: InstallContext, using_prebuilt: bool, nwave_source: Path
    ) -> str:
        """Name the distribution channel a refusal is talking about.

        A refusal that says only "assets missing" leaves the reader to work out
        WHICH tree to fix. The three channels ship three different layouts, so
        the channel IS the actionable part of the HOW.
        """
        if not using_prebuilt:
            return "development checkout"
        if (
            context.framework_source is not None
            and nwave_source == context.framework_source / "nWave"
        ):
            return "PyPI/pipx wheel (nested nWave/nWave/ layout)"
        return "GitHub-release dist/ tarball (flat layout)"

    @classmethod
    def _nwave_tier_manifest(cls, nwave_source: Path) -> Path | None:
        """Return the catalogue file that marks `nwave_source` an nWave tier.

        The DECLARED fact that discriminates "this tree is an nWave source
        tier, so its assets are expected" from "this is an external target
        that legitimately has no nWave tier". Keyed on a shipped file rather
        than inferred from how many assets happen to be present, because a
        partially-populated tree must read as INCOMPLETE, not as absent.
        """
        for filename in cls._NWAVE_RUNTIME_ASSET_FILES:
            candidate = nwave_source / filename
            if candidate.is_file():
                return candidate
        return None

    @staticmethod
    def _runtime_python_dir(context: InstallContext) -> Path:
        """Choose the shared host-neutral runtime, legacy Claude path otherwise.

        The property that matters is whether Claude is targeted at all, not
        whether Codex specifically is: an OpenCode-only or Copilot-only
        target satisfies neither half of the old "codex in platforms" check
        and fell through to the Claude-scoped path, so its module landed
        somewhere its own hook's declared PYTHONPATH never pointed at
        (verified by _require_hook_runtime finding a dangling runtime dir).
        """
        if "claude_code" not in context.target_platforms:
            return host_neutral_runtime_dir()
        return context.claude_dir / "lib" / "python"

    _HOST_NEUTRAL_PLATFORMS = frozenset({"codex", "copilot", "opencode"})

    @classmethod
    def _secondary_runtime_python_dir(
        cls, context: InstallContext, primary: Path
    ) -> Path | None:
        """The OTHER runtime dir a mixed target also needs, if any.

        `resolve_des_lib_path_for_spawn()` hardcodes `host_neutral_runtime_dir()`
        for every non-Claude host's own generated hook (Codex, Copilot,
        OpenCode) -- independent of which single directory `_runtime_python_dir`
        picked as the PRIMARY install target above. A target that mixes
        claude_code with any of those three therefore needs the module in
        BOTH places: whichever one `_runtime_python_dir` did not already
        choose. Returns None when only one family is targeted (nothing to
        mirror) or the secondary already equals the primary.
        """
        wants_claude = "claude_code" in context.target_platforms
        wants_host_neutral = bool(
            cls._HOST_NEUTRAL_PLATFORMS & context.target_platforms
        )
        if not (wants_claude and wants_host_neutral):
            return None
        claude_dir = context.claude_dir / "lib" / "python"
        neutral_dir = host_neutral_runtime_dir()
        secondary = neutral_dir if primary == claude_dir else claude_dir
        return None if secondary == primary else secondary

    @classmethod
    def resolve_des_module_locations(cls, context: InstallContext) -> list[Path]:
        """Every on-disk `des/` directory a target described by `context` can have.

        SSOT for "where does the installed DES module live" -- built directly
        on `_runtime_python_dir` (the primary target) and
        `_secondary_runtime_python_dir` (the mirror a mixed claude_code +
        host-neutral target also needs), the same two methods `install()`
        uses to decide where to WRITE the module. Uninstall must walk this
        exact same list to REMOVE it, or a mixed/host-neutral target orphans
        the module in whichever location a hardcoded single-path uninstall
        never looked at (the uninstall-vs-install path divergence bug).
        """
        primary = cls._runtime_python_dir(context) / "des"
        locations = [primary]
        secondary = cls._secondary_runtime_python_dir(context, primary.parent)
        if secondary is not None:
            locations.append(secondary / "des")
        return locations

    def _rewrite_import_paths(self, target_dir: Path, context: InstallContext) -> None:
        """Rewrite import paths in installed DES module.

        Transforms:
        - "from src.des." -> "from des."
        - "import src.des." -> "import des."
        - "src.des." in any context -> "des."

        This ensures the installed package works without PYTHONPATH pointing
        to the development source directory.
        """
        import re

        # Pattern to match import statements
        from_pattern = re.compile(r"\bfrom\s+src\.des\b")
        import_pattern = re.compile(r"\bimport\s+src\.des\b")
        # Pattern to match src.des. in any context (strings, comments, etc.)
        general_pattern = re.compile(r"\bsrc\.des\.")

        files_modified = 0
        files_skipped = 0
        for py_file in target_dir.rglob("*.py"):
            try:
                # Security: Skip symbolic links to prevent path traversal attacks
                if py_file.is_symlink():
                    context.logger.warn(f"  ⚠️ Skipping symlink (security): {py_file}")
                    files_skipped += 1
                    continue

                # Security: Verify path is within target_dir (defense in depth)
                try:
                    py_file.resolve().relative_to(target_dir.resolve())
                except ValueError:
                    context.logger.warn(f"  ⚠️ Skipping file outside target: {py_file}")
                    files_skipped += 1
                    continue

                # Security: Skip files larger than 10MB to prevent DoS
                file_size = py_file.stat().st_size
                if file_size > 10_000_000:  # 10MB limit
                    context.logger.warn(
                        f"  ⚠️ Skipping large file: {py_file} ({file_size} bytes)"
                    )
                    files_skipped += 1
                    continue

                # Read file content
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()

                # Track if file was modified
                original_content = content

                # Rewrite import statements
                content = from_pattern.sub("from des", content)
                content = import_pattern.sub("import des", content)
                # Rewrite any remaining src.des. references (strings, comments, etc.)
                content = general_pattern.sub("des.", content)

                # Write back if modified
                if content != original_content:
                    with open(py_file, "w", encoding="utf-8") as f:
                        f.write(content)
                    files_modified += 1

            except Exception as e:
                context.logger.warn(f"  ⚠️ Failed to rewrite imports in {py_file}: {e}")

        if files_modified > 0:
            context.logger.info(f"  🔄 Rewrote import paths in {files_modified} files")
        if files_skipped > 0:
            context.logger.info(f"  ⚠️ Skipped {files_skipped} files for security")

    def _clear_bytecode_cache(self, target_dir: Path, context: InstallContext) -> None:
        """Clear __pycache__ directories from installed DES module.

        After copying and rewriting imports, stale .pyc files from previous
        installs can cause import errors or use outdated code. Removing all
        __pycache__ directories forces Python to recompile from source.

        Resilient to a concurrent writer racing one of the cache dirs (issue
        #43): a leftover racing directory is harmless -- its stale .pyc is
        recompiled from source on next import -- so aborting the whole clear
        would be worse than tolerating it.
        """
        cleared = 0
        for cache_dir in target_dir.rglob("__pycache__"):
            if cache_dir.is_dir():
                _robust_rmtree(cache_dir)
                cleared += 1
        if cleared > 0:
            context.logger.info(
                f"  🧹 Cleared {cleared} __pycache__ directories from {target_dir}"
            )

    def _write_install_manifest(
        self,
        *,
        target_dir: Path,
        source_dir: Path,
        using_prebuilt: bool,
        nwave_assets_root: Path | None = None,
    ) -> None:
        """Write `_install_manifest.json` colocated with the installed package.

        Per fix-des-self-hosted-gate-sync §1.4 + DDD-3: the manifest is the
        runtime freshness gate's source-of-truth pointer back to the source
        tree the install was produced from. The runtime gate reads it via
        :class:`des.adapters.driven.freshness.RepoSourceProbe` and discriminates
        the §1.3 four-state truth table from its fields.

        Eight v1 fields (§1.4 schema_version=1):

        * ``schema_version`` — integer (1 without config assets, 2 with).
        * ``installed_version`` — what the installer thought it was installing.
        * ``installed_at_iso`` — UTC ISO-8601 of the install.
        * ``source_tree`` — absolute path to the source dir that was copied.
        * ``source_commit`` — git SHA at copy time (empty when not a repo).
        * ``source_dirty`` — `git status --porcelain` non-empty at copy time.
        * ``source_kind`` — ``dev-checkout`` / ``pre-built`` / ``wheel``.
        * ``tree_hash`` — SHA-256 of the canonical tree-hash of the installed
          tree (post-rewrite content; §1.6 algorithm).

        SYS-4 / AD-27 schema v2 — when ``nwave_assets_root`` is shipped, the
        manifest bumps to schema_version 2 and adds ``config_assets_tree_hash``:
        the canonical hash of the shipped ``lib/nWave/`` config assets at install
        time, so the runtime gate can name a later config-asset drift LOUD. When
        no config assets were shipped (e.g. the staged source had no ``nWave/``),
        the manifest stays v1 — no config-asset envelope.

        Side effect: writes one JSON file under ``target_dir``. No exceptions
        raised on the happy path; ``source_commit`` falls back to empty when
        the source tree is not a git repo (a wheel's transient staging dir).
        """
        from datetime import datetime, timezone

        from scripts.install.install_nwave import _get_version

        source_kind = self._classify_source_kind(source_dir, using_prebuilt)
        source_commit, source_dirty = self._interrogate_source_git(source_dir)
        manifest = {
            "schema_version": 1,
            "installed_version": _get_version(),
            "installed_at_iso": datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "source_tree": str(source_dir.resolve()),
            "source_commit": source_commit,
            "source_dirty": source_dirty,
            "source_kind": source_kind,
            "tree_hash": _canonical_tree_hash(target_dir),
        }
        if nwave_assets_root is not None and nwave_assets_root.exists():
            manifest["schema_version"] = 2
            manifest["config_assets_tree_hash"] = _canonical_config_assets_hash(
                nwave_assets_root
            )
        manifest_path = target_dir / "_install_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    @staticmethod
    def _classify_source_kind(source_dir: Path, using_prebuilt: bool) -> str:
        """Map the install source to one of three §1.4 ``source_kind`` values.

        * ``pre-built`` — ``lib/python/des/`` of a dist tarball (rewrites
          already applied).
        * ``wheel`` — site-packages staging path that will not survive past the
          install (PyPI install topology; detected by the path containing
          ``site-packages``).
        * ``dev-checkout`` — the repo's ``src/des/`` (the default).
        """
        if using_prebuilt:
            return "pre-built"
        if "site-packages" in source_dir.parts:
            return "wheel"
        return "dev-checkout"

    @staticmethod
    def _interrogate_source_git(source_dir: Path) -> tuple[str, bool]:
        """Return ``(source_commit, source_dirty)`` for ``source_dir``.

        Tolerates ``source_dir`` not being a git repo (returns ``("", False)``)
        and missing ``git`` on PATH. The returned tuple feeds §1.4 manifest
        fields ``source_commit`` + ``source_dirty``.
        """
        try:
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(source_dir),
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.SubprocessError):
            return "", False
        if head.returncode != 0:
            return "", False
        commit = head.stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", str(source_dir)],
            cwd=str(source_dir),
            capture_output=True,
            text=True,
            timeout=5,
        )
        dirty = bool(status.stdout.strip()) if status.returncode == 0 else False
        return commit, dirty

    def _install_des_scripts(self, context: InstallContext) -> PluginResult:
        """Install DES utility scripts, sweeping manifest-tracked orphans.

        On upgrade, scripts tracked by the shared manifest but absent from
        the new source set are deleted BEFORE copying, and the manifest is
        rewritten. Without a manifest (pre-record, 3.16.0-shaped target)
        nothing is deleted: unrecorded scripts are preserved and the user
        is warned (preserve-by-default hard contract). Under ``dry_run``
        no file is deleted and no manifest is written.
        """
        try:
            # Use framework source if available, fallback to nWave/scripts/des
            if context.framework_source:
                source_dir = context.framework_source / "scripts" / "des"
                if not source_dir.exists():
                    # Fallback to nWave/scripts/des if framework source doesn't have DES scripts
                    source_dir = context.project_root / "nWave" / "scripts" / "des"
            else:
                source_dir = Path("nWave/scripts/des")

            target_dir = context.claude_dir / "scripts"
            target_dir.mkdir(parents=True, exist_ok=True)

            record = read_family_record(
                target_dir,
                key=self.SCRIPTS_MANIFEST_KEY,
                sibling_keys=frozenset({UTILITIES_FAMILY_KEY}),
                adopt_legacy=True,
            )
            if not context.dry_run:
                self._sweep_retired_scripts(target_dir, record, context)

            installed = []
            for script_name in self.DES_SCRIPTS:
                source = source_dir / script_name
                target = target_dir / script_name

                if source.exists():
                    if not context.dry_run:
                        shutil.copy2(source, target)
                        target.chmod(0o755)
                    installed.append(script_name)

            if not context.dry_run:
                write_family_record(
                    target_dir,
                    installed,
                    key=self.SCRIPTS_MANIFEST_KEY,
                    superseded_keys=record.superseded_keys,
                )

            return PluginResult(
                success=True,
                plugin_name="des",
                message=f"Installed {len(installed)} DES scripts",
            )

        except Exception as e:
            return PluginResult(
                success=False,
                plugin_name="des",
                message=f"DES scripts install failed: {e}",
            )

    def _install_des_hook_scripts(self, context: InstallContext) -> PluginResult:
        """Install the independent DES hook scripts to ~/.claude/scripts/."""
        try:
            source_dir = _resolve_hook_scripts_source_dir(context)

            target_dir = context.claude_dir / "scripts"
            target_dir.mkdir(parents=True, exist_ok=True)

            # An upgrade may find files from the withdrawn protocol even when
            # every current hook is already present. Remove only exact
            # installer-owned names; user scripts remain untouched.
            for script_name in self.RETIRED_HOOK_SCRIPTS:
                retired = target_dir / script_name
                if retired.exists() and not context.dry_run:
                    retired.unlink()
                    context.logger.info(
                        f"  🗑️ Removed retired DES hook script: {script_name}"
                    )

            installed = []
            for script_name in self.DES_HOOKS:
                source = source_dir / script_name
                target = target_dir / script_name

                if source.exists():
                    if not context.dry_run:
                        shutil.copy2(source, target)
                        target.chmod(0o755)
                    installed.append(script_name)

            return PluginResult(
                success=True,
                plugin_name="des",
                message=f"Installed {len(installed)} DES hook scripts",
            )

        except Exception as e:
            return PluginResult(
                success=False,
                plugin_name="des",
                message=f"DES hook scripts install failed: {e}",
            )

    def _install_git_pre_push_backstop(self, context: InstallContext) -> PluginResult:
        """Retired (fix-pre-push-hook-dual-installer-collision RCA, slice-01).

        Formerly rendered `hook_definitions._GIT_PRE_PUSH_DECLARE_DONE_BACKSTOP`
        into the shared `.git/hooks/pre-push`, chaining any pre-existing hook
        aside to `pre-push.nwave-original`. That wrapper carried no
        pre-commit-generated banner, so it collided with `pre-commit install`
        (`.pre-commit-config.yaml`'s SSOT-intended writer) -- a SECOND writer
        of the SAME file tripped `verify-hooks`'s foreign-hook detector. RCA:
        docs/analysis/root-cause-analysis-pre-push-hook-dual-installer-collision.md

        The declare-done backstop's BEHAVIOR is unchanged and still fires --
        it is now installed as a `local` `stages: [pre-push]` hook in
        `.pre-commit-config.yaml` (guarded for the script's absence on
        another machine, per target-machine independence), so
        `pre-commit install` is the SOLE writer of `.git/hooks/pre-push`.

        This method is now a deliberate no-op: it performs NO writes to the
        git hooks directory. It is kept (not deleted) because
        `tests/build/f_pre_push_hook_dual_installer_collision/
        test_dual_installer_collision_regression.py` exercises it directly,
        as its own real-production-entry-point regression guard against the
        two-writer collision recurring.
        """
        return PluginResult(
            success=True,
            plugin_name="des",
            message=(
                "DES git pre-push backstop retired: folded into "
                ".pre-commit-config.yaml as a local pre-push hook -- "
                "pre-commit install is the sole writer of .git/hooks/pre-push"
            ),
        )

    def _sweep_retired_scripts(
        self, target_dir: Path, record: FamilyRecord, context: InstallContext
    ) -> None:
        """Delete this family's tracked scripts the current version retired."""
        if record.tracked is None:
            self._warn_unrecorded_scripts(target_dir, record.accounted, context)
            return
        removed, blocked = sweep_retired_assets(
            target_dir, record.tracked - set(self.DES_SCRIPTS)
        )
        for retired_name in removed:
            context.logger.info(f"  🧹 Removed retired DES script: {retired_name}")
        for blocked_name in blocked:
            context.logger.warning(
                f"  ⚠️ Cannot remove read-only retired DES script: {blocked_name}"
            )

    def _warn_unrecorded_scripts(
        self, target_dir: Path, accounted: frozenset[str], context: InstallContext
    ) -> None:
        """Preserve-by-default: warn about scripts no record accounts for."""
        unrecorded = unaccounted_names(
            target_dir, accounted=accounted, expected=frozenset(self.DES_SCRIPTS)
        )
        if not unrecorded:
            return
        context.logger.warning(
            preserve_warning_message(
                target_dir,
                unrecorded,
                family_label="DES scripts manifest",
                item_label="script",
            )
        )

    def _install_des_data(self, context: InstallContext) -> PluginResult:
        """Install the framework DATA tree (`nWave/data/`) to `<claude_dir>/data/`.

        WHY THIS EXISTS: eight runtime modules read `nWave/data/` -- log
        persistence defaults, the coverage-map digest fixtures, the flavor
        dispatcher's tables and `des doctor`. None of it was
        ever copied to the operator's tree, so every one of those reads
        resolved against a directory that exists only in a development
        checkout. The installed CONSUMER was being deployed without the DATA
        it consumes, and the install reported success regardless.

        FAIL-LOUD CONTRACT: a missing source tree is NOT skipped silently.
        Installing a consumer without its data is the defect this method
        exists to close, so an absent or empty source is a hard failure that
        names WHAT is missing, WHY it matters, and HOW to fix it.
        """
        try:
            source_dir = context.framework_source / "data"
            # A public wheel has the host-facing templates at the flat root,
            # while runtime data is intentionally packaged under nWave/nWave.
            # Resolve that package-owned tier before considering a development
            # checkout fallback; otherwise an all-target install has copied a
            # valid runtime tree but fails on this legacy flat lookup.
            packaged_data = context.framework_source / "nWave" / "data"
            if not source_dir.exists() and packaged_data.is_dir():
                source_dir = packaged_data
            if not source_dir.exists() and context.project_root:
                source_dir = context.project_root / "nWave" / "data"

            if not source_dir.exists():
                return PluginResult(
                    success=False,
                    plugin_name="des",
                    message=(
                        f"WHAT: the framework data tree was not found at "
                        f"{source_dir}. "
                        "WHY: eight runtime modules read it (log-persistence "
                        "defaults, coverage-map fixtures, flavor dispatcher "
                        "tables and des doctor) -- without "
                        "it they resolve against a path that does not exist on "
                        "the target machine. "
                        "HOW: reinstall from a source tree that ships nWave/data/, "
                        "or from a distribution built by scripts/build_dist.py "
                        "with the data family included."
                    ),
                )

            target_dir = context.claude_dir / "data"
            if not context.dry_run:
                target_dir.mkdir(parents=True, exist_ok=True)
                shutil.copytree(
                    source_dir,
                    target_dir,
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
                )

            # Verify the STRUCTURED FACT -- every top-level entry present at
            # the destination -- never the weak signal "copytree did not raise".
            declared = sorted(p.name for p in source_dir.iterdir())
            if not context.dry_run:
                arrived = {p.name for p in target_dir.iterdir()}
                missing = [name for name in declared if name not in arrived]
                if missing:
                    return PluginResult(
                        success=False,
                        plugin_name="des",
                        message=(
                            f"WHAT: {len(missing)} data entr(y|ies) declared at "
                            f"{source_dir} did not arrive at {target_dir}: "
                            f"{', '.join(missing)}. "
                            "WHY: a consumer installed without the data it reads "
                            "fails at runtime on the operator's machine while the "
                            "install reports success. "
                            "HOW: check permissions and free space on the target, "
                            "then re-run the install."
                        ),
                    )

            return PluginResult(
                success=True,
                plugin_name="des",
                message=(
                    f"Installed {len(declared)} framework data entries to "
                    f"{context.claude_dir / 'data'}"
                ),
            )

        except Exception as e:
            return PluginResult(
                success=False,
                plugin_name="des",
                message=(
                    f"WHAT: installing the framework data tree failed ({e}). "
                    "WHY: eight runtime modules read nWave/data/ and resolve "
                    "against the installed copy. "
                    "HOW: re-run the install; if it persists, check write "
                    "permissions on the Claude config directory."
                ),
            )

    def _install_des_templates(self, context: InstallContext) -> PluginResult:
        """Install DES templates."""
        try:
            # Use framework_source for dist/ or nWave/ layout
            source_dir = context.framework_source / "templates"
            target_dir = context.claude_dir / "templates"
            target_dir.mkdir(parents=True, exist_ok=True)

            installed = []
            for template_name in self.DES_TEMPLATES:
                source = source_dir / template_name
                target = target_dir / template_name

                if source.exists():
                    if not context.dry_run:
                        shutil.copy2(source, target)
                    installed.append(template_name)

            return PluginResult(
                success=True,
                plugin_name="des",
                message=f"Installed {len(installed)} DES templates",
            )

        except Exception as e:
            return PluginResult(
                success=False,
                plugin_name="des",
                message=f"DES templates install failed: {e}",
            )

    @staticmethod
    def _resolve_python_path() -> str:
        """Resolve the Python interpreter path for hook commands.

        Delegates to the shared SSOT `resolve_python_path_for_shell()`
        (scripts/shared/install_paths.py) -- this used to be a standalone,
        byte-identical copy of the same logic duplicated in
        attribution_utils._resolve_python_path
        (D3-code-duplication-resolve-python-path, techdebt.md). Kept as a
        thin delegating wrapper (rather than inlined at the two call
        sites) so existing callers/tests that patch
        `DESPlugin._resolve_python_path` keep working unchanged.
        """
        return resolve_python_path_for_shell()

    def _generate_hook_command(self, context: InstallContext, action: str) -> str:
        """Generate hook command with portable paths for cross-machine use.

        Uses $HOME shell variable instead of absolute paths so that
        settings.json works when synced across machines (via ~/.claude).
        Uses the installer's Python (with $HOME substitution) to ensure
        dependencies like PyYAML are available at hook runtime.

        Args:
            context: InstallContext with claude_dir
            action: Hook action (pre-task, subagent-stop, post-tool-use)

        Returns:
            Complete command string with $HOME-based paths
        """
        # When the install target is the default ~/.claude/, keep the portable
        # $HOME form so settings.json works across machines via a synced
        # ~/.claude/. When the target is non-default (e.g. ~/.claude-nwave
        # via `nwave-ai install --target`, or a project-scoped <repo>/.claude),
        # emit the absolute path: Claude Code passes hook commands to a shell
        # that resolves $HOME to the user's real home, NOT to the chosen
        # target, so the portable form would point at the wrong directory.
        # See ADR-002 (per-project-install feature).
        if context.claude_dir == Path.home() / ".claude":
            lib_path = "$HOME/.claude/lib/python"
        else:
            lib_path = str(context.claude_dir / "lib" / "python")
        python_path = self._resolve_python_path()
        return self.HOOK_COMMAND_TEMPLATE.format(
            lib_path=lib_path,
            python_path=python_path,
            action=action,
        )

    @staticmethod
    def _resolve_nwave_hook_version() -> str:
        """Resolve the installed nWave version for the D6 `nwave_hook_version` stamp.

        Reuses `install_nwave._get_version` -- the single installer-side version
        primitive (package metadata when pip/pipx-installed, pyproject.toml in a
        dev checkout). The stamp lets the runtime hooks (and the SessionStart
        skew detector) compare the installed hook surface against the running
        checkout (ADR-030 D6 / M13).
        """
        try:
            from scripts.install.install_nwave import _get_version

            return _get_version()
        except Exception:
            return "0.0.0"

    @classmethod
    def _is_retired_lifecycle_hook_entry(
        cls, entry: dict[str, Any], *, legacy_adapter_command: str
    ) -> bool:
        """Recognize only exact installer-owned retired lifecycle commands."""
        commands = [entry.get("command", "")]
        commands.extend(hook.get("command", "") for hook in entry.get("hooks", []))
        return any(
            command == legacy_adapter_command
            or hashlib.sha256(command.encode("utf-8")).hexdigest()
            in cls._RETIRED_AFFORDANCE_COMMAND_DIGESTS
            for command in commands
        )

    # --- P1-C settings provenance (reversible settings.json edits) ---
    #
    # `nwave_hook_version` (D6/M13 stamp) and the `env.PATH` shim-bin prepend
    # are the two settings.json edits nWave owns and must be able to reverse.
    # The receipt is the SSOT for "what nWave found before it ever touched
    # this settings.json" -- written once (first-receipt-wins) and cleared
    # only by a successful uninstall, so v1 -> v2 -> uninstall restores the
    # true pre-nWave absence/value rather than whatever v2 last wrote.
    #
    # Location is derived entirely from `context.claude_dir` (the resolved
    # CLAUDE_CONFIG_DIR -- see `PathUtils.get_claude_config_dir`), never from
    # `Path.home()`: a DESPlugin driven with a temp/custom claude_dir (tests,
    # --target installs) must not infer or write the developer's real
    # ~/.nwave. The key embeds a hash of the resolved claude_dir so two
    # profiles sharing the same parent directory (e.g. ~/.claude and
    # ~/.claude-alt both rooted at the real $HOME) never collide.
    SETTINGS_RECEIPT_SCHEMA_VERSION = 2

    # Sentinel distinguishing "caller did not touch this field" from a
    # legitimate recorded value of `None` (e.g. no `nwave_hook_version`
    # existed before nWave ever wrote one).
    _UNSET = object()

    @staticmethod
    def _settings_receipt_path(context: InstallContext) -> Path:
        """Path of the settings-provenance receipt for this `claude_dir`."""
        root = context.claude_dir.parent / ".nwave" / "install-receipts"
        key = hashlib.sha256(
            str(context.claude_dir.resolve()).encode("utf-8")
        ).hexdigest()[:16]
        return root / f"settings-{key}.json"

    def _record_settings_receipt(
        self,
        context: InstallContext,
        *,
        hook_version_before: Any = _UNSET,
        hook_version_written: Any = _UNSET,
        path_before: Any = _UNSET,
        path_written: Any = _UNSET,
    ) -> None:
        """Merge-write the settings-provenance receipt.

        The `*_before` fields are first-wins: recorded once (the key is
        absent) and never overwritten afterwards, so they keep anchoring the
        true pre-nWave state across every later install. The `*_written`
        fields always take the latest call's value -- they track exactly
        what nWave itself most recently wrote, which is the sole basis
        `_restore_settings_from_receipt` compares the current settings
        against (never a recomputed package version or PATH).
        """
        if context.dry_run:
            return
        receipt_path = self._settings_receipt_path(context)
        receipt: dict[str, Any] = {}
        if receipt_path.exists():
            try:
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                receipt = {}
        receipt["schema_version"] = self.SETTINGS_RECEIPT_SCHEMA_VERSION
        receipt["claude_config_dir"] = str(context.claude_dir.resolve())
        if (
            hook_version_before is not self._UNSET
            and "nwave_hook_version_before" not in receipt
        ):
            receipt["nwave_hook_version_before"] = hook_version_before
        if hook_version_written is not self._UNSET:
            receipt["nwave_hook_version_written"] = hook_version_written
        if path_before is not self._UNSET and "path_before" not in receipt:
            receipt["path_before"] = path_before
        if path_written is not self._UNSET:
            receipt["path_written"] = path_written
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    def _restore_settings_from_receipt(
        self, context: InstallContext, config: dict[str, Any]
    ) -> bool:
        """Reverse nWave's settings.json edits using the receipt, if any.

        Restores/removes `nwave_hook_version` and the PATH segment nWave
        wrote ONLY when the current value still equals the receipt's
        recorded `*_written` value -- never a recomputed package version or
        a re-derived PATH segment. A value the user has since edited by hand
        no longer matches the recorded write and is preserved untouched,
        order and all other content included. Returns whether `config` was
        mutated.
        """
        changed = False

        receipt_path = self._settings_receipt_path(context)
        if not receipt_path.exists():
            return changed
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return changed

        written_version = receipt.get("nwave_hook_version_written", self._UNSET)
        if (
            written_version is not self._UNSET
            and config.get("nwave_hook_version") == written_version
        ):
            original = receipt.get("nwave_hook_version_before")
            if original is None:
                if config.pop("nwave_hook_version", None) is not None:
                    changed = True
            elif config.get("nwave_hook_version") != original:
                config["nwave_hook_version"] = original
                changed = True

        written_path = receipt.get("path_written", self._UNSET)
        if (
            written_path is not self._UNSET
            and config.get("env", {}).get("PATH", "") == written_path
        ):
            original_path = receipt.get("path_before")
            env = config.setdefault("env", {})
            if not original_path:
                if env.pop("PATH", None) is not None:
                    changed = True
            elif env.get("PATH") != original_path:
                env["PATH"] = original_path
                changed = True

        return changed

    def _clear_settings_receipt(self, context: InstallContext) -> None:
        """Delete the settings-provenance receipt (successful-uninstall reset).

        Idempotent -- a missing receipt (already cleared, or never written
        because this target never touched settings.json) is not an error.
        """
        if context.dry_run:
            return
        receipt_path = self._settings_receipt_path(context)
        if receipt_path.exists():
            receipt_path.unlink()

    def _install_des_hooks(self, context: InstallContext) -> PluginResult:
        """Install DES hooks into settings.json (global config).

        CRITICAL: Preserves ALL existing settings (permissions, other hooks, etc.).
        Only modifies the hooks.PreToolUse and hooks.SubagentStop arrays.

        Hook commands use PYTHONPATH to point to installed location:
        ~/.claude/lib/python/des/

        Replaces any old-format DES hooks with new format to prevent duplicates.
        Always removes and re-adds DES hooks to ensure latest format is used.
        """
        try:
            settings_file = context.claude_dir / "settings.json"

            # Load existing config (preserve everything)
            config = self._load_settings(settings_file)

            # Store original for uninstall restoration
            self._original_settings = json.loads(json.dumps(config))

            # Ensure hooks structure exists WITHOUT overwriting other keys
            if "hooks" not in config:
                config["hooks"] = {}
            for event in self.HOOK_EVENTS:
                if event not in config["hooks"]:
                    config["hooks"][event] = []

            # Generate the desired hook config using shared definitions
            def _installer_command(action: str) -> str:
                return self._generate_hook_command(context, action)

            def _installer_guard_command(action: str) -> str:
                python_cmd = self._generate_hook_command(context, action)
                return shared_hooks.build_guard_command(python_cmd)

            desired_hooks = shared_hooks.generate_hook_config(
                _installer_command, guard_command_fn=_installer_guard_command
            )

            def _without_retired_hook_commands(
                entry: dict[str, Any],
            ) -> dict[str, Any] | None:
                """Remove only exact commands emitted by the withdrawn registry.

                Settings entries belong to their author unless they exactly
                match one of the historical installer payloads above. A nested
                entry may contain unrelated sibling hooks, so preserve those
                hooks and all entry metadata; drop the entry only when empty.
                """
                if entry.get("command", "") in self._RETIRED_HOOK_COMMANDS:
                    return None

                hooks = entry.get("hooks", [])
                retained_hooks = [
                    hook
                    for hook in hooks
                    if hook.get("command", "") not in self._RETIRED_HOOK_COMMANDS
                ]
                if len(retained_hooks) == len(hooks):
                    return entry
                if not retained_hooks:
                    return None
                return {**entry, "hooks": retained_hooks}

            retired_hook_removed = False
            legacy_user_prompt_command = self._generate_hook_command(
                context, "user-prompt-submit"
            )
            for event, entries in config["hooks"].items():
                if not isinstance(entries, list):
                    continue
                retained = []
                for entry in entries:
                    reconciled = _without_retired_hook_commands(entry)
                    if reconciled is None:
                        retired_hook_removed = True
                        continue
                    if (
                        event in self._RETIRED_LIFECYCLE_EVENTS
                        and self._is_retired_lifecycle_hook_entry(
                            reconciled,
                            legacy_adapter_command=legacy_user_prompt_command,
                        )
                    ):
                        retired_hook_removed = True
                        continue
                    if reconciled != entry:
                        retired_hook_removed = True
                    retained.append(reconciled)
                if retained != entries:
                    config["hooks"][event] = retained

            # Check if hooks already exist with correct format.
            # Both command AND matcher must match on the SAME entry to count
            # as up-to-date (previously checked independently, which could
            # yield false positives when entries were shuffled).
            def _entry_matches(
                existing_entry: dict[str, Any], desired_entry: dict[str, Any]
            ) -> bool:
                """Check if an existing entry matches a desired entry exactly."""
                # Compare matcher (None == absent)
                if existing_entry.get("matcher") != desired_entry.get("matcher"):
                    return False
                # Compare command in nested hooks list
                desired_cmd = desired_entry["hooks"][0]["command"]
                return any(
                    h.get("command") == desired_cmd
                    for h in existing_entry.get("hooks", [])
                )

            all_up_to_date = True
            for event, desired_entries in desired_hooks.items():
                existing = config["hooks"].get(event, [])
                for desired in desired_entries:
                    if not any(_entry_matches(e, desired) for e in existing):
                        all_up_to_date = False
                        break
                if not all_up_to_date:
                    break

            # Ensure slash command budget is sufficient for nWave commands
            # Without this, commands disappear in long sessions (>50% context)
            env_changed = False
            if "env" not in config:
                config["env"] = {}
            if "SLASH_COMMAND_TOOL_CHAR_BUDGET" not in config.get("env", {}):
                config["env"]["SLASH_COMMAND_TOOL_CHAR_BUDGET"] = "100000"
                env_changed = True

            # D6 / M13: stamp `nwave_hook_version` into settings.json. The stamp
            # records the nWave version whose DES hook surface is installed; the
            # runtime SessionStart skew detector compares it against the running
            # checkout. The stamp write is ATOMIC with the hook-array rewrite --
            # `config` is one in-memory object written once by `_save_settings`,
            # so a fresh hook set never carries a stale or absent stamp.
            hook_version = self._resolve_nwave_hook_version()
            version_changed = config.get("nwave_hook_version") != hook_version
            # P1-C settings provenance: snapshot the pre-nWave `nwave_hook_
            # version` (first-wins) and record the value nWave is about to
            # write (always latest) BEFORE mutating `config`, so restore can
            # compare against what was actually written instead of
            # recomputing the package version.
            self._record_settings_receipt(
                context,
                hook_version_before=config.get("nwave_hook_version"),
                hook_version_written=hook_version,
            )
            if version_changed:
                config["nwave_hook_version"] = hook_version

            if (
                all_up_to_date
                and not env_changed
                and not version_changed
                and not retired_hook_removed
            ):
                context.logger.info("  ✅ DES hooks up-to-date")
                return PluginResult(
                    success=True,
                    plugin_name="des",
                    message="DES hooks already installed",
                )

            if all_up_to_date and (
                env_changed or version_changed or retired_hook_removed
            ):
                # Only env / version stamp needs updating, hooks are fine. The
                # single `_save_settings` write keeps the version stamp atomic
                # with the (unchanged) hook arrays already in `config`.
                if not context.dry_run:
                    self._save_settings(settings_file, config, context)
                context.logger.info(
                    "  ✅ DES hooks up-to-date + configuration/retired-hook cleanup applied"
                )
                return PluginResult(
                    success=True,
                    plugin_name="des",
                    message="DES hooks up-to-date, configuration and retired hooks reconciled",
                )

            # Remove any existing DES hooks (both old flat and new nested format)
            for event in self.HOOK_EVENTS:
                if event in config["hooks"]:
                    config["hooks"][event] = [
                        h
                        for h in config["hooks"][event]
                        if not shared_hooks.is_des_hook_entry(h)
                    ]

            # Add all DES hooks from shared definitions
            for event, entries in desired_hooks.items():
                for entry in entries:
                    config["hooks"][event].append(entry)

            if not context.dry_run:
                self._save_settings(settings_file, config, context)

            return PluginResult(
                success=True,
                plugin_name="des",
                message="DES hooks installed (preserving existing settings)",
            )

        except Exception as e:
            return PluginResult(
                success=False,
                plugin_name="des",
                message=f"DES hooks install failed: {e}",
            )

    _DEFAULT_DES_CONFIG = {
        "audit_logging_enabled": True,
        "audit_log_dir": ".nwave/des/logs",
    }

    def _write_json_config(self, path: Path, data: dict[str, Any]) -> None:
        """Write dict as pretty-printed JSON with trailing newline."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")

    def _read_json_config(self, path: Path) -> dict[str, Any]:
        """Read JSON config file, returning empty dict on parse or IO error."""
        try:
            with open(path, encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
                return data
        except (json.JSONDecodeError, OSError):
            return {}

    def _migrate_config(
        self, config_file: Path, context: InstallContext
    ) -> PluginResult:
        """Seed missing default blocks into an existing config (migration path).

        Each seed is independent and idempotent: a block is added only when it is
        absent, and an existing block is never overwritten. All pre-existing keys
        are preserved (read-modify-write).
        """
        # Ensure .gitignore on every install/upgrade (migration for existing installs)
        self._ensure_gitignore(config_file.parent)

        return PluginResult(
            success=True,
            plugin_name="des",
            message="DES config already exists",
        )

    @staticmethod
    def _ensure_gitignore(nwave_dir: Path) -> None:
        """Create .nwave/.gitignore with '*' to prevent accidental commits.

        Idempotent: preserves user-customized .gitignore (no nWave marker).
        Handles read-only directories gracefully.
        """
        gitignore = nwave_dir / ".gitignore"
        marker = "# Generated by nWave. Do not edit."
        try:
            if gitignore.exists():
                content = gitignore.read_text(encoding="utf-8")
                if marker not in content:
                    return  # User-customized, don't overwrite
            gitignore.write_text(f"{marker}\n*\n", encoding="utf-8")
        except OSError:
            pass  # Read-only directory, skip silently

    def _create_config(
        self, config_file: Path, nwave_dir: Path, context: InstallContext
    ) -> PluginResult:
        """Create des-config.json with default settings."""
        default_config = self._DEFAULT_DES_CONFIG
        if context.dry_run:
            context.logger.info(f"  🚨 [DRY RUN] Would create {config_file}")
        else:
            nwave_dir.mkdir(parents=True, exist_ok=True)
            self._ensure_gitignore(nwave_dir)
            self._write_json_config(config_file, default_config)
            context.logger.info(f"  ✅ DES config created: {config_file}")
        return PluginResult(
            success=True,
            plugin_name="des",
            message=f"DES config bootstrapped at {config_file}",
        )

    def _bootstrap_des_config(self, context: InstallContext) -> PluginResult:
        """Bootstrap .nwave/des-config.json with default settings.

        Creates the config file if it doesn't exist. If it already exists
        and otherwise preserves its user-owned content unchanged.

        The config lives in the project directory (.nwave/), not ~/.claude,
        because audit log paths are project-relative.

        Resilience: when the resolved project directory is read-only (e.g.
        running the installer from a read-only mount or a site-packages
        dir that the user doesn't own), silently skip config creation.
        DES runs with sensible built-in defaults when the config is absent;
        blocking the install over an optional customization file is wrong.
        """
        try:
            project_root = context.project_root or Path.cwd()
            nwave_dir = project_root / ".nwave"
            config_file = nwave_dir / "des-config.json"

            if config_file.exists():
                return self._migrate_config(config_file, context)

            return self._create_config(config_file, nwave_dir, context)

        except OSError as e:
            # EROFS, EACCES, ENOSPC, etc. — directory not writable.
            # Treat as soft-skip: DES operates on built-in defaults when
            # the project-level config file is missing, so the install
            # can continue safely.  The warning surfaces the condition
            # without breaking the happy path.
            context.logger.info(
                f"  ⚠️  DES config skipped (read-only project dir): {e}. "
                f"Built-in defaults apply; customize later via "
                f"{config_file} when project dir is writable."
            )
            return PluginResult(
                success=True,
                plugin_name="des",
                message=(
                    f"DES config skipped (project dir not writable): {e}. "
                    "Built-in defaults in effect."
                ),
            )
        except Exception as e:
            return PluginResult(
                success=False,
                plugin_name="des",
                message=f"DES config bootstrap failed: {e}",
            )

    def _load_settings(self, settings_file: Path) -> dict[str, Any]:
        """Load settings from JSON file, return empty dict if not exists."""
        if not settings_file.exists():
            return {}

        try:
            with open(settings_file, encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
                return data
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {settings_file}: {e}")

    def _save_settings(
        self, settings_file: Path, config: dict[str, Any], context: InstallContext
    ) -> None:
        """Save settings to JSON file with proper formatting and file locking.

        Uses exclusive file locking to prevent race conditions during concurrent
        modifications (defense in depth).
        """
        # Ensure directory exists
        settings_file.parent.mkdir(parents=True, exist_ok=True)

        # Try to import fcntl for Unix file locking
        try:
            import fcntl

            has_fcntl = True
        except ImportError:
            # Windows doesn't have fcntl, fallback to no locking
            has_fcntl = False

        # Write with proper formatting and optional file locking
        mode = "r+" if settings_file.exists() else "w"
        with open(settings_file, mode, encoding="utf-8") as f:
            try:
                # Acquire exclusive lock if available (Unix only)
                if has_fcntl:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)

                # Truncate file if opened in r+ mode
                if mode == "r+":
                    f.seek(0)
                    f.truncate()

                # Write JSON with proper formatting
                json.dump(config, f, indent=2)
                f.write("\n")  # Add trailing newline

            finally:
                # Release lock if acquired
                if has_fcntl:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        context.logger.info(f"  ✅ Settings updated at {settings_file}")

    def _install_des_shims(self, context: InstallContext) -> PluginResult:
        """Copy the DES CLI shims to ~/.claude/bin/ with mode 0o755.

        Also prepends $HOME/.claude/bin to settings.json env.PATH so the
        shim command names are resolvable from the Bash tool without an
        env-var-prefix first token.

        Idempotent: repeated invocations overwrite shims (shutil.copy2) and
        skip the PATH entry if already present.
        """
        try:
            # Resolve source: framework_source/scripts/des or project nWave/scripts/des
            if context.framework_source:
                source_dir = context.framework_source / "scripts" / "des"
                if not source_dir.exists() and context.project_root:
                    source_dir = context.project_root / "nWave" / "scripts" / "des"
            elif context.project_root:
                source_dir = context.project_root / "nWave" / "scripts" / "des"
            else:
                source_dir = Path("nWave/scripts/des")

            if not source_dir.exists():
                return PluginResult(
                    success=False,
                    plugin_name="des",
                    message=f"DES shims source not found: {source_dir}",
                )

            target_bin = context.claude_dir / "bin"
            target_bin.mkdir(parents=True, exist_ok=True)

            for shim_name in self.DES_SHIMS:
                src = source_dir / shim_name
                if not src.exists():
                    return PluginResult(
                        success=False,
                        plugin_name="des",
                        message=f"DES shim not found in source: {shim_name}",
                    )
                dst = target_bin / shim_name
                if not context.dry_run:
                    shutil.copy2(src, dst)
                    dst.chmod(0o755)

            # R17 residuality cleanup: delete pre-consolidation des-* shims
            # left over from a prior install. Mirrors DDD-7 break-immediate
            # migration policy on the deployed target.
            if not context.dry_run:
                for legacy_name in self.LEGACY_DES_SHIMS:
                    legacy_path = target_bin / legacy_name
                    if legacy_path.exists():
                        legacy_path.unlink()
                        context.logger.info(
                            f"  🗑️  Removed legacy DES shim: {legacy_name}"
                        )

            # Update settings.json env.PATH with absolute bin path
            des_bin_path = str(context.claude_dir / "bin")
            self._update_path_in_settings(context, des_bin_path)

            context.logger.info(
                f"  ✅ Installed {len(self.DES_SHIMS)} DES shims to {target_bin}"
            )
            return PluginResult(
                success=True,
                plugin_name="des",
                message=f"Installed {len(self.DES_SHIMS)} DES shims to {target_bin}",
            )

        except Exception as e:
            return PluginResult(
                success=False,
                plugin_name="des",
                message=f"DES shims install failed: {e}",
            )

    def _update_path_in_settings(
        self, context: InstallContext, des_bin_path: str
    ) -> None:
        """Prepend the absolute DES bin path to settings.json env.PATH if not present.

        Idempotent: skips prepend if des_bin_path is already a colon-delimited
        segment of the current PATH value.

        When settings.json has no prior env.PATH, seeds it from the live
        install-time PATH (os.environ["PATH"]) so user-visible directories
        (~/.local/bin, ~/.deno/bin, ~/.cargo/bin, /snap/bin, ~/bin, etc.)
        remain reachable. Claude Code REPLACES env.PATH (it does not merge
        with the inherited shell PATH), so seeding from a hardcoded minimum
        would strip the user's real PATH. Falls back to SYSTEM_PATH_FALLBACK
        only when os.environ has no PATH (highly unusual).

        Auto-heals settings written by older installer versions whose PATH
        equals exactly '<des_bin>:<SYSTEM_PATH_FALLBACK>': those values
        replaced the user's real PATH and broke bare-name resolution of
        binaries in ~/.local/bin (where pipx-installed CLIs live, including
        claude and nwave-ai itself).

        Normalizes pre-existing $HOME entries to absolute paths. Claude Code passes
        env.PATH verbatim to exec() without shell expansion, so $HOME literals never
        resolve to the actual filesystem directory. Re-running install on a settings.json
        with $HOME entries rewrites them to absolute paths (BUG-2 from RCA).

        Uses absolute path resolved at install time. env.PATH values are passed
        verbatim to exec() and are never shell-expanded. Re-run 'nwave-ai install'
        on each machine if settings.json is synced.
        """
        settings_file = context.claude_dir / "settings.json"
        config = self._load_settings(settings_file)

        if "env" not in config:
            config["env"] = {}

        existing_path = config["env"].get("PATH", "")
        # P1-C settings provenance: the value found BEFORE this call touches
        # it, captured once (first-wins) so uninstall can restore the true
        # pre-nWave PATH rather than whatever the most recent install left.
        path_before = existing_path

        # Normalize any $HOME references in existing PATH entries to absolute paths.
        # Claude Code does not shell-expand env values, so $HOME must be resolved now.
        if existing_path and "$HOME" in existing_path:
            home = str(Path.home())
            segments = [s.replace("$HOME", home) for s in existing_path.split(":")]
            existing_path = ":".join(segments)

        # Auto-heal settings written by older installer versions: detect the
        # exact byte-for-byte signature of the prior fabricated value
        # (des_bin + SYSTEM_PATH_FALLBACK only) and rewrite from the live
        # install-time PATH. Probability of a user manually configuring
        # exactly this value is effectively zero, so this is safe to assume
        # is installer-fabricated.
        legacy_fabricated_path = f"{des_bin_path}:{self.SYSTEM_PATH_FALLBACK}"
        if existing_path == legacy_fabricated_path:
            live_path = os.environ.get("PATH") or self.SYSTEM_PATH_FALLBACK
            config["env"]["PATH"] = des_bin_path + ":" + live_path
            self._record_settings_receipt(
                context, path_before=path_before, path_written=config["env"]["PATH"]
            )
            if not context.dry_run:
                self._save_settings(settings_file, config, context)
            return

        if des_bin_path in existing_path.split(":"):
            if existing_path != config["env"].get("PATH", ""):
                config["env"]["PATH"] = existing_path
                if not context.dry_run:
                    self._save_settings(settings_file, config, context)
            self._record_settings_receipt(
                context, path_before=path_before, path_written=existing_path
            )
            return

        if existing_path:
            config["env"]["PATH"] = des_bin_path + ":" + existing_path
        else:
            # Seed from the user's live install-time PATH so binaries reachable
            # from their shell (claude itself in ~/.local/bin, pnpm, node, etc.)
            # remain reachable inside Claude Code sessions and hooks.
            live_path = os.environ.get("PATH") or self.SYSTEM_PATH_FALLBACK
            config["env"]["PATH"] = des_bin_path + ":" + live_path

        self._record_settings_receipt(
            context, path_before=path_before, path_written=config["env"]["PATH"]
        )
        if not context.dry_run:
            self._save_settings(settings_file, config, context)

    def _hooks_already_installed(self, config: dict[str, Any]) -> bool:
        """Check if DES hooks are already installed.

        Returns True if ANY hook event type has a DES hook.
        This handles cases where only partial hooks exist (e.g., old format).
        The install process will clean up and reinstall all properly.
        """
        if "hooks" not in config:
            return False

        return any(
            any(
                shared_hooks.is_des_hook_entry(h)
                for h in config["hooks"].get(event, [])
            )
            for event in self.HOOK_EVENTS
        )

    def _is_des_hook_entry(self, hook_entry: dict[str, Any]) -> bool:
        """Check if a hook entry is a DES hook.

        Delegates to shared hook_definitions module for consistent detection
        across plugin builder and installer paths.
        """
        return shared_hooks.is_des_hook_entry(hook_entry)

    def uninstall(self, context: InstallContext) -> PluginResult:
        """Uninstall DES plugin.

        Removes DES hooks from settings.local.json while preserving all other settings.
        Also removes DES module, scripts, and templates.
        """
        try:
            errors = []

            # 1. Remove DES hooks from settings
            hooks_result = self._uninstall_des_hooks(context)
            if not hooks_result.success:
                errors.append(hooks_result.message)

            # 2. Remove DES module (every location this target may use --
            # primary + secondary mirror for mixed claude_code/host-neutral
            # targets, see resolve_des_module_locations)
            for des_module in self.resolve_des_module_locations(context):
                if des_module.exists():
                    shutil.rmtree(des_module)
                    context.logger.info(f"  🗑️ Removed DES module: {des_module}")

            # 3. Remove DES scripts
            scripts_dir = context.claude_dir / "scripts"
            for script_name in self.DES_SCRIPTS:
                script_path = scripts_dir / script_name
                if script_path.exists():
                    script_path.unlink()
                    context.logger.info(f"  🗑️ Removed DES script: {script_name}")

            # 3b. Remove current and retired installer-owned hook scripts.
            for hook_script_name in (*self.DES_HOOKS, *self.RETIRED_HOOK_SCRIPTS):
                hook_script_path = scripts_dir / hook_script_name
                if hook_script_path.exists():
                    hook_script_path.unlink()
                    context.logger.info(
                        f"  🗑️ Removed DES hook script: {hook_script_name}"
                    )

            # 4. Remove DES templates
            templates_dir = context.claude_dir / "templates"
            for template_name in self.DES_TEMPLATES:
                template_path = templates_dir / template_name
                if template_path.exists():
                    template_path.unlink()
                    context.logger.info(f"  🗑️ Removed DES template: {template_name}")

            if errors:
                return PluginResult(
                    success=False,
                    plugin_name="des",
                    message=f"DES uninstall had errors: {'; '.join(errors)}",
                    errors=errors,
                )

            return PluginResult(
                success=True,
                plugin_name="des",
                message="DES uninstalled successfully",
            )

        except Exception as e:
            return PluginResult(
                success=False,
                plugin_name="des",
                message=f"DES uninstall failed: {e}",
            )

    def _uninstall_des_hooks(self, context: InstallContext) -> PluginResult:
        """Remove DES hooks from settings.json (global config).

        Preserves all other settings (permissions, other hooks, etc.).
        """
        try:
            settings_file = context.claude_dir / "settings.json"

            if not settings_file.exists():
                # A missing settings.json is itself a successful uninstall
                # outcome -- clear the receipt so a future install is
                # treated as first-ever, not poisoned by a stale receipt
                # pointing at settings this uninstall never got to see.
                self._clear_settings_receipt(context)
                return PluginResult(
                    success=True,
                    plugin_name="des",
                    message="No settings file to clean up",
                )

            config = self._load_settings(settings_file)

            # Remove only DES hooks, preserve everything else
            if "hooks" in config:
                legacy_user_prompt_command = self._generate_hook_command(
                    context, "user-prompt-submit"
                )
                for event in self.HOOK_EVENTS:
                    if event in config["hooks"]:
                        config["hooks"][event] = [
                            h
                            for h in config["hooks"][event]
                            if not shared_hooks.is_des_hook_entry(h)
                        ]
                for event in self._RETIRED_LIFECYCLE_EVENTS:
                    if event in config["hooks"]:
                        config["hooks"][event] = [
                            hook
                            for hook in config["hooks"][event]
                            if not self._is_retired_lifecycle_hook_entry(
                                hook,
                                legacy_adapter_command=legacy_user_prompt_command,
                            )
                        ]

            # P1-C settings provenance: reverse the `nwave_hook_version`
            # stamp and the PATH shim-bin prepend using the first-wins
            # receipt, then clear the receipt so the next install is
            # treated as first-ever again.
            self._restore_settings_from_receipt(context, config)

            self._save_settings(settings_file, config, context)
            self._clear_settings_receipt(context)

            return PluginResult(
                success=True,
                plugin_name="des",
                message="DES hooks removed (other settings preserved)",
            )

        except Exception as e:
            return PluginResult(
                success=False,
                plugin_name="des",
                message=f"DES hooks uninstall failed: {e}",
            )

    def verify(self, context: InstallContext) -> PluginResult:
        """Verify DES installation."""
        # Dry-run preview never wrote files, so verification has nothing to
        # assert against. Defensive guard — the primary caller already skips
        # validate_installation under dry_run, but any future caller (e.g. a
        # standalone verifier) that forwards an InstallContext with dry_run
        # must not be misled into reporting failure for a no-op preview.
        if context.dry_run:
            return PluginResult(
                success=True,
                plugin_name="des",
                message="dry-run: verification skipped",
            )

        if "claude_code" not in context.target_platforms:
            runtime = self._runtime_python_dir(context) / "des"
            return PluginResult(
                success=runtime.is_dir(),
                plugin_name="des",
                message=(
                    "host-neutral DES runtime verified"
                    if runtime.is_dir()
                    else f"host-neutral DES runtime missing: {runtime}"
                ),
            )

        errors = []

        # 1. Verify DES module importable under the SAME Python that hooks use
        # (sys.executable = installer's Python, which is also the hook Python)
        try:
            lib_python = str(self._runtime_python_dir(context))
            # Use repr() to properly escape backslashes on Windows paths
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    f"import sys; sys.path.insert(0, {lib_python!r}); import yaml; from des.cli.__main__ import main",
                ],
                capture_output=True,
                text=True,
                timeout=self.DES_VERIFY_IMPORT_TIMEOUT_SECONDS,
            )
            if result.returncode != 0:
                errors.append(f"DES module import failed: {result.stderr}")
        except Exception as e:
            errors.append(f"DES module verify failed: {e}")

        # 2. Verify scripts present
        for script in self.DES_SCRIPTS:
            script_path = context.claude_dir / "scripts" / script
            if not script_path.exists():
                errors.append(f"Missing DES script: {script}")

        # 3. Verify templates present
        for template in self.DES_TEMPLATES:
            template_path = context.claude_dir / "templates" / template
            if not template_path.exists():
                errors.append(f"Missing DES template: {template}")

        # 4. Verify hooks installed in settings.json (global config)
        settings_file = context.claude_dir / "settings.json"
        if settings_file.exists():
            try:
                config = self._load_settings(settings_file)
                if not self._hooks_already_installed(config):
                    errors.append("DES hooks not found in settings.json")
            except Exception as e:
                errors.append(f"Could not verify DES hooks: {e}")
        else:
            errors.append("settings.json not found - DES hooks not installed")

        # 5. Verify DES config exists and is valid JSON
        context.logger.info("  \U0001f50e Verifying DES config...")
        project_root = context.project_root or Path.cwd()
        config_file = project_root / ".nwave" / "des-config.json"
        nwave_dir = project_root / ".nwave"
        if not config_file.exists():
            if nwave_dir.exists():
                default_config = {
                    "audit_logging_enabled": True,
                    "audit_log_dir": ".nwave/des/logs",
                }
                try:
                    nwave_dir.mkdir(parents=True, exist_ok=True)
                    with open(config_file, "w", encoding="utf-8") as f:
                        json.dump(default_config, f, indent=2)
                        f.write("\n")
                    context.logger.info(
                        f"  \u2705 DES config created (migration): {config_file}"
                    )
                    des_cfg = default_config
                except OSError as e:
                    # Read-only project dir (e.g. installer invoked from a
                    # mounted source repo); built-in defaults apply.  Match
                    # the _bootstrap_des_config soft-skip semantics.
                    context.logger.info(
                        f"  \u26a0\ufe0f  DES config skipped (read-only project "
                        f"dir): {e}. Built-in defaults apply."
                    )
                    des_cfg = default_config
            else:
                errors.append("DES config not found: .nwave/des-config.json")
        if not errors and config_file.exists():
            try:
                with open(config_file, encoding="utf-8") as f:
                    des_cfg = json.load(f)
                audit_on = "on" if des_cfg.get("audit_logging_enabled") else "off"
                log_dir = des_cfg.get("audit_log_dir", "not set")
                context.logger.info(f"  \u2705 DES config ({config_file}):")
                context.logger.info(f"    \u2699\ufe0f audit_logging={audit_on}")
                context.logger.info(f"    \u2699\ufe0f log_dir={log_dir}")
            except json.JSONDecodeError:
                errors.append("DES config is not valid JSON: .nwave/des-config.json")

        if errors:
            return PluginResult(
                success=False,
                plugin_name="des",
                message="DES verification failed",
                errors=errors,
            )

        return PluginResult(
            success=True,
            plugin_name="des",
            message="DES verification passed (module, scripts, templates, hooks, config OK)",
        )
