#!/usr/bin/env python3
"""
nWave Framework Installation Script

Cross-platform installer for the nWave methodology framework.
Installs specialized agents and commands to global Claude config directory.

Usage: python install_nwave.py [--backup-only] [--restore] [--dry-run] [--help]
"""

import argparse
import ast
import hashlib
import json
import os
import shlex
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import NamedTuple


_HASH_CHUNK_BYTES = 65536  # 64 KiB chunked read keeps SKILL.md etc. memory-bounded
_LEGACY_CODEX_AGENT_ALIASES = {"nw-architect", "nw-crafter"}

# HOW remedies for the Codex ownership preflight (see
# NWaveInstaller.validate_codex_ownership_preflight /
# _report_ownership_preflight_errors). Keyed by the ``kind`` tag attached to
# each collected error: distinct kinds need DISTINCT fixes -- adoption is the
# right remedy for an untracked collision, but the wrong one for a corrupted
# manifest -- so this is a lookup table, never one generic line reused for
# every failure shape.
_OWNERSHIP_PREFLIGHT_ADOPTABLE_COLLISION_HOW = (
    "If this is legacy nWave dev state, adopt it into the normal backup "
    "with `--adopt-legacy-codex-dev --dev --platform codex` (that flag "
    "requires both --dev and --platform codex). If it is NOT nWave "
    "state, remove or relocate it yourself, then re-run install."
)
_OWNERSHIP_PREFLIGHT_REMEDIES: dict[str, str] = {
    # Adoptable skill/agent collisions are split into two kinds -- not one
    # -- purely so the aggregate report in _report_ownership_preflight_errors
    # names BOTH host roots (skills dir, agents dir) and samples from each,
    # instead of one alphabetically-dominant root hiding the other.
    "foreign-collision-adoptable-skill": _OWNERSHIP_PREFLIGHT_ADOPTABLE_COLLISION_HOW,
    "foreign-collision-adoptable-agent": _OWNERSHIP_PREFLIGHT_ADOPTABLE_COLLISION_HOW,
    "foreign-collision-manual": (
        "This is not covered by --adopt-legacy-codex-dev. Back it up if you "
        "need it, remove it yourself, then re-run install so nWave writes "
        "its own trusted copy."
    ),
    "missing-owned-asset": (
        "nWave's own manifest says it owns this asset, but the file is "
        "gone. Re-run install to recreate it, or restore it from an nWave "
        "backup if you need the exact prior version."
    ),
    "unsafe-path": (
        "This path is a symlink, or the wrong type where nWave expects a "
        "plain file or directory. Inspect it, replace it with the expected "
        "type (or remove it), then re-run install."
    ),
    "corrupt-file": (
        "This file could not be read or parsed. Restore it from an nWave "
        "backup, or delete it and re-run install so nWave regenerates it."
    ),
    "untrusted-content": (
        "This file's content does not match what nWave generates or "
        "expects (hand-edited or incompatible). Back it up if you need it, "
        "delete it, then re-run install so nWave regenerates its own "
        "trusted copy."
    ),
}


def _file_md5(path: Path) -> str | None:
    """Compute md5 of *path* read in 64 KiB chunks; return None on read error.

    Returning ``None`` (vs. raising) lets the verifier treat "unreadable" the
    same as "drifted" — both reach the operator via the same diagnostic line
    naming the file, instead of crashing the verifier mid-walk.
    """
    try:
        digest = hashlib.md5()
        with path.open("rb") as fh:
            while True:
                chunk = fh.read(_HASH_CHUNK_BYTES)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _files_content_equal(source: Path, target: Path) -> bool:
    """Return True only when both files exist AND their md5 digests match.

    Used by the verifier to detect content drift between an installer source
    file and its installed counterpart. Existence check alone misses the
    silent-template-skip bug class (RCA fix-installer-silent-template-skip).
    """
    if not target.exists():
        return False
    return _file_md5(source) == _file_md5(target)


# Bootstrap sys.path BEFORE the import block below, so the `scripts.install.*`
# package imports resolve identically whether this file is run as a bare script
# (`python scripts/install/install_nwave.py`) or as a module
# (`python -m scripts.install.install_nwave`).
#
# `.resolve()` is load-bearing: in bare-script mode `__file__` is a *relative*
# path, so `Path(__file__).parent.parent.parent` without resolution collapses to
# a relative `.` that does not place the repo root ahead of any stale `scripts/`
# package shadowing it on sys.path. Resolving first yields the absolute repo
# root; inserting it at index 0 makes the repo's `scripts` win namespace-package
# resolution (F-05 dogfood friction regression).
#
# Move-to-FRONT unconditionally (not `if not in sys.path`): an editable-install
# `.pth` appends the repo root AFTER site-packages, so a presence-only guard
# leaves site-packages' stale wheel snapshot of `scripts/` FIRST in the PEP 420
# namespace-portion order — the running plugin code silently rots to the last
# `uv sync` (fix-dispatch-ssot slice-01: `dispatch` never shipped because the
# stale site-packages `des_plugin.py` predated the constant change).
_project_root = Path(__file__).resolve().parent.parent.parent
_project_root_entry = str(_project_root)
if _project_root_entry in sys.path:
    sys.path.remove(_project_root_entry)
sys.path.insert(0, _project_root_entry)


# Support both standalone execution and package import
try:
    from scripts.install.context_detector import detect_target_platforms
    from scripts.install.install_utils import (
        BackupManager,
        Logger,
        ManifestWriter,
        PathUtils,
    )
    from scripts.install.installation_verifier import InstallationVerifier
    from scripts.install.output_formatter import format_error
    from scripts.install.plugins.agents_plugin import AgentsPlugin
    from scripts.install.plugins.attribution_plugin import AttributionPlugin
    from scripts.install.plugins.base import InstallContext
    from scripts.install.plugins.codex_agents_plugin import CodexAgentsPlugin
    from scripts.install.plugins.codex_des_plugin import CodexDESPlugin
    from scripts.install.plugins.codex_skills_plugin import CodexSkillsPlugin
    from scripts.install.plugins.commands_plugin import CommandsPlugin
    from scripts.install.plugins.copilot_des_plugin import CopilotDESPlugin
    from scripts.install.plugins.des_plugin import DESPlugin
    from scripts.install.plugins.opencode_agents_plugin import OpenCodeAgentsPlugin
    from scripts.install.plugins.opencode_commands_plugin import OpenCodeCommandsPlugin
    from scripts.install.plugins.opencode_des_plugin import OpenCodeDESPlugin
    from scripts.install.plugins.opencode_skills_plugin import OpenCodeSkillsPlugin
    from scripts.install.plugins.registry import PluginRegistry
    from scripts.install.plugins.skills_plugin import SkillsPlugin
    from scripts.install.plugins.templates_plugin import TemplatesPlugin
    from scripts.install.plugins.utilities_plugin import UtilitiesPlugin
    from scripts.install.preflight_checker import PreflightChecker
    from scripts.shared.agent_catalog import is_public_agent, load_public_agents
except ImportError:
    # Safety-net fallback. With the sys.path bootstrap above the package
    # imports in the `try` block resolve in BOTH invocation modes, so this
    # branch is normally unreachable. It is retained as a defensive net and
    # MUST stay import-correct: bare `scripts/install` directory imports plus
    # an explicit re-bootstrap of the repo root for the `scripts.shared`
    # package (which lives one level up from `scripts/install`, so a bare
    # `from shared...` would fail — F-05 latent fallback bug).
    if _project_root_entry in sys.path:
        sys.path.remove(_project_root_entry)
    sys.path.insert(0, _project_root_entry)
    from context_detector import detect_target_platforms
    from install_utils import (
        BackupManager,
        Logger,
        ManifestWriter,
        PathUtils,
    )
    from installation_verifier import InstallationVerifier
    from output_formatter import format_error
    from plugins.agents_plugin import AgentsPlugin
    from plugins.attribution_plugin import AttributionPlugin
    from plugins.base import InstallContext
    from plugins.codex_agents_plugin import CodexAgentsPlugin
    from plugins.codex_des_plugin import CodexDESPlugin
    from plugins.codex_skills_plugin import CodexSkillsPlugin
    from plugins.commands_plugin import CommandsPlugin
    from plugins.copilot_des_plugin import CopilotDESPlugin
    from plugins.des_plugin import DESPlugin
    from plugins.opencode_agents_plugin import OpenCodeAgentsPlugin
    from plugins.opencode_commands_plugin import OpenCodeCommandsPlugin
    from plugins.opencode_des_plugin import OpenCodeDESPlugin
    from plugins.opencode_skills_plugin import OpenCodeSkillsPlugin
    from plugins.registry import PluginRegistry
    from plugins.skills_plugin import SkillsPlugin
    from plugins.templates_plugin import TemplatesPlugin
    from plugins.utilities_plugin import UtilitiesPlugin
    from preflight_checker import PreflightChecker

    from scripts.shared.agent_catalog import is_public_agent, load_public_agents

# ANSI color codes for --help output (only consumer)
_ANSI_BLUE = "\033[0;34m"
_ANSI_NC = "\033[0m"  # No Color


def _get_version() -> str:
    """Read version from package metadata (installed) or pyproject.toml (dev)."""
    # 1. Try importlib.metadata first (works when installed via pip/pipx)
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("nwave-ai")
    except PackageNotFoundError:
        pass

    # 2. Fallback: read pyproject.toml (dev checkout layout)
    pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
    if not pyproject_path.exists():
        return "0.0.0"
    try:
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib  # type: ignore[no-redef]
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        return data.get("project", {}).get("version", "0.0.0")
    except ModuleNotFoundError:
        import re

        content = pyproject_path.read_text()
        m = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
        return m.group(1) if m else "0.0.0"


__version__ = _get_version()


# Interpreter-path markers that identify a package-manager tool venv. Mirrors
# scripts/install/preflight_checker.TOOL_VENV_PATH_MARKERS — kept local to avoid
# a cross-module import for two string constants.
_PM_PATH_MARKERS: tuple[tuple[str, str], ...] = (
    ("/pipx/venvs/", "pipx"),
    ("/uv/tools/", "uv"),
)


def _detect_package_manager() -> str | None:
    """Best-effort: which PM installed this package, inferred from sys.executable.

    The installer runs from the tool venv that owns ``nwave-ai``, so its
    interpreter path reveals the manager (``pipx`` venvs live under
    ``/pipx/venvs/``, ``uv`` tools under ``/uv/tools/``). Returns None when the
    path matches neither (e.g. a plain pip/venv or system install) — the caller
    then simply omits the key rather than guessing.
    """
    exe = sys.executable or ""
    for marker, name in _PM_PATH_MARKERS:
        if marker in exe:
            return name
    return None


def _detect_installed_version() -> str | None:
    """Return the live ``nwave-ai`` package version, or None when unavailable.

    Metadata-only (no pyproject fallback): the recorded value must match what
    the doctor reads at runtime via ``importlib.metadata`` so a dev/editable
    checkout (no installed distribution) records nothing rather than a pyproject
    version that would read as spurious drift.
    """
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("nwave-ai")
    except PackageNotFoundError:
        return None


def record_install_metadata(
    global_config_path: Path,
    installed_version: str,
    package_manager: str | None,
) -> None:
    """Record install provenance into the global config (read-modify-write).

    Writes ``install.installed_version`` — the anchor the doctor
    ``VersionSyncCheck`` compares against the live package version to flag a
    package upgraded without re-running install — and, when known,
    ``install.package_manager`` (consumed by ``/nw-update``). All unrelated keys
    are preserved; a None ``package_manager`` never erases a previously recorded
    one.

    Best-effort: any failure is swallowed. A metadata write must never fail the
    install itself.
    """
    try:
        current: dict = {}
        if global_config_path.exists():
            try:
                loaded = json.loads(global_config_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    current = loaded
            except (json.JSONDecodeError, OSError):
                current = {}

        existing_install = current.get("install")
        install_block = (
            dict(existing_install) if isinstance(existing_install, dict) else {}
        )
        install_block["installed_version"] = installed_version
        if package_manager is not None:
            install_block["package_manager"] = package_manager
        current["install"] = install_block

        global_config_path.parent.mkdir(parents=True, exist_ok=True)
        global_config_path.write_text(json.dumps(current, indent=2), encoding="utf-8")
    except Exception:
        pass


def _component_synced(matched: int, expected: int) -> bool:
    """Return True iff a verifier component is synced.

    Pure equality predicate: a component is synced when the count of
    files present in the target equals the count expected from the
    source. The "no work needed" state (matched == 0 AND expected == 0)
    is success, NOT failure.

    Earlier inline expressions added a defensive `and expected > 0`
    clause that turned legitimate zero-expected states into hard fails
    (v3.12.1 install regression, RCA Bugs #2 and #5). The verifier's
    job is to assert that everything-expected is present — it does not
    decide what counts as suspicious.
    """
    return matched == expected


class ComponentResult(NamedTuple):
    """Per-component sync verification result.

    Carries the four facts the failure aggregator needs:
    - name      : human-readable component name (agents/commands/...)
    - matched   : count of files found in the target
    - expected  : count of files declared by the source
    - ok        : whether matched == expected (cached for clarity)
    """

    name: str
    matched: int
    expected: int
    ok: bool


def _format_sync_mismatch(components: list[ComponentResult]) -> str:
    """Format a per-component sync-mismatch failure message.

    Pure data transformation: take the list of component results, keep
    only the failures, render each as ``<name> (<matched>/<expected>)``,
    and join them under the prefix ``sync mismatch: ``.

    Replaces the legacy literal ``"agent/command sync mismatch"`` which
    blamed agents/commands regardless of which component actually failed
    (v3.12.1 install regression, RCA Bug #3). Mentioning only the failing
    components avoids contradiction with the per-component checkmarks
    printed above the aggregate failure line.
    """
    failing = [c for c in components if not c.ok]
    if not failing:
        # Defensive: caller should not invoke us when all components are
        # green, but if it does we still want a sensible non-empty token.
        return "sync mismatch: unknown"
    parts = [f"{c.name} ({c.matched}/{c.expected})" for c in failing]
    return f"sync mismatch: {', '.join(parts)}"


# ASCII art logo (raw text, no Rich markup)
_LOGO_ART = [
    "        \u2584\u2584\u2584\u2584  \u2584\u2584\u2584  \u2584\u2584\u2584\u2584",
    "        \u2580\u2588\u2588\u2588  \u2588\u2588\u2588  \u2588\u2588\u2588\u2580",
    "  \u2588\u2588\u2588\u2588\u2584  \u2588\u2588\u2588  \u2588\u2588\u2588  \u2588\u2588\u2588  \u2580\u2580\u2588\u2584 \u2588\u2588 \u2588\u2588 \u2584\u2588\u2580\u2588\u2584",
    "  \u2588\u2588 \u2588\u2588  \u2588\u2588\u2588\u2584\u2584\u2588\u2588\u2588\u2584\u2584\u2588\u2588\u2588 \u2584\u2588\u2580\u2588\u2588 \u2588\u2588\u2584\u2588\u2588 \u2588\u2588\u2584\u2588\u2580",
    "  \u2588\u2588 \u2588\u2588   \u2580\u2588\u2588\u2588\u2588\u2580\u2588\u2588\u2588\u2588\u2580  \u2580\u2588\u2584\u2588\u2588  \u2580\u2588\u2580  \u2580\u2588\u2584\u2584\u2584\u2584\u2582\u2582\u2581\u2581",
]
_TAGLINES = [
    " Orchestrated Agentic-AI code assistant for crafters.",
    " Modern Software Engineering at scale. Confidence at speed.",
]


class NWaveInstaller:
    """nWave framework installer."""

    def __init__(
        self,
        dry_run: bool = False,
        platform_override: set[str] | None = None,
        dev_mode: bool = False,
        adopt_legacy_codex_dev: bool = False,
    ):
        """Initialize installer.

        Args:
            dry_run: When True, show what would be done without making changes.
            platform_override: Override auto-detected platforms. None means auto-detect.
            dev_mode: When True, install ALL agents/skills (not just public).
            adopt_legacy_codex_dev: Explicitly quarantine unmanifested legacy
                Codex dev assets after a normal nWave backup, before install.
        """
        self.dry_run = dry_run
        self.dev_mode = dev_mode
        self.adopt_legacy_codex_dev = adopt_legacy_codex_dev
        self._platform_override = platform_override
        # The install must have one target truth.  In particular, auto mode
        # cannot install a detected Codex target and later reconstruct a
        # Claude-only validation set from the original CLI override.
        self._effective_target_platforms: set[str] | None = None
        self.script_dir = Path(__file__).parent
        self.project_root = PathUtils.get_project_root(self.script_dir)
        self.claude_config_dir = PathUtils.get_claude_config_dir()
        # Source-first: use nWave/ when in dev repo, dist/ only for distribution
        source_dir = self.project_root / "nWave"
        dist_dir = self.project_root / "dist"
        if source_dir.exists():
            self.framework_source = source_dir
        elif (dist_dir / "MANIFEST.json").exists():
            self.framework_source = dist_dir
        else:
            self.framework_source = source_dir  # fall through for error reporting

        # Persistent logging starts only after Codex ownership preflight.  A
        # refusal must leave every user-controlled byte untouched, including
        # an unrelated pre-existing Claude log.
        self._install_log_file = self.claude_config_dir / "nwave-install.log"
        self.logger = Logger(None)
        self.backup_manager = BackupManager(self.logger, "install")
        # Public observability contract for restore_backup: after a successful
        # restore, this attribute exposes the path of the backup that was
        # selected. Acceptance tests inspect this to verify selection without
        # re-running glob/sort logic in the test step (see DWD-09).
        self.last_restored_from: Path | None = None
        self._codex_backup_dir: Path | None = None

    @property
    def _legacy_codex_dev_adoption_enabled(self) -> bool:
        """Whether this invocation may adopt the narrowly scoped legacy state."""
        return (
            self.adopt_legacy_codex_dev
            and self.dev_mode
            and self.effective_target_platforms == {"codex"}
        )

    def enable_install_logging(self) -> None:
        """Enable persistent logging after the no-write ownership preflight."""
        if not self.dry_run:
            self.logger.log_file = self._install_log_file

    @property
    def effective_target_platforms(self) -> frozenset[str]:
        """Return the authoritative targets for this installer invocation.

        Platform detection is intentionally lazy so construction remains
        side-effect free, but it is cached at first use.  Every downstream
        stage therefore consumes the exact same explicit or detected set.
        """
        cached_target_platforms = getattr(self, "_effective_target_platforms", None)
        if cached_target_platforms is None:
            if self._platform_override is not None:
                self._effective_target_platforms = set(self._platform_override)
            else:
                self._effective_target_platforms = {
                    platform.value for platform in detect_target_platforms()
                }
        return frozenset(self._effective_target_platforms)

    def create_backup(self) -> None:
        """Create backup of existing installation, then enforce retention.

        Wires backup creation and retention pruning into a single seam so
        ``main()`` and any other caller automatically gets retention without
        having to remember to call ``apply_retention`` themselves.

        Retention is intentionally NOT applied in dry-run mode: dry-run must
        not delete anything from disk. In live runs, retention runs even when
        ``create_backup`` returns ``None`` (no prior install) — older
        accumulated backups from previous runs may still need pruning, and
        ``apply_retention`` is a no-op when the cap is not exceeded.

        Raises:
            ConfigValidationError: when ``~/.nwave/global-config.json``
                provides an invalid ``backups.max_count`` value. Bubbled up
                so ``main()`` aborts the install BEFORE ``install_framework``
                runs — see scope.md S9 ("no backup is touched if config is
                invalid"); equivalently, no install proceeds either.
        """
        if "codex" in self.effective_target_platforms:
            agents_home = Path(os.environ.get("NWAVE_AGENTS_HOME", Path.home()))
            codex_dir = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
            self.backup_manager.backup_root = agents_home / ".nwave" / "backups"
            self.backup_manager.backup_dir = (
                self.backup_manager.backup_root
                / f"nwave-install-{self.backup_manager.timestamp}"
            )
            self._codex_backup_dir = self.backup_manager.create_codex_backup(
                skills_dir=agents_home / ".agents" / "skills",
                agents_dir=codex_dir / "agents",
                codex_dir=codex_dir,
                dry_run=self.dry_run,
            )
        else:
            self.backup_manager.create_backup(dry_run=self.dry_run)
        if self.dry_run:
            return
        self.backup_manager.apply_retention(max_count=None)

    def _legacy_codex_dev_candidates(self) -> list[tuple[Path, Path]]:
        """Return only safe, non-manifested legacy dev assets for quarantine.

        This deliberately does not discover ownership by name in the default
        path.  It is reachable only from the explicit dev-only migration flag;
        malformed manifests, symlinks, files with the wrong shape, and all
        non-``nw-*`` assets remain fail-closed.
        """
        if not self._legacy_codex_dev_adoption_enabled:
            return []
        agents_home = Path(os.environ.get("NWAVE_AGENTS_HOME", Path.home()))
        skills_dir = agents_home / ".agents" / "skills"
        codex_dir = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        agents_dir = codex_dir / "agents"

        def manifest_names(path: Path, key: str) -> set[str]:
            if not path.exists() or path.is_symlink() or not path.is_file():
                return set()
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                return set()
            names = document.get(key) if isinstance(document, dict) else None
            if not (
                isinstance(document, dict)
                and document.get("version") == "1.0"
                and isinstance(names, list)
                and all(
                    isinstance(name, str)
                    and name.startswith("nw-")
                    and Path(name).name == name
                    for name in names
                )
            ):
                return set()
            return set(names)

        skills_manifest = manifest_names(
            skills_dir / ".nwave-manifest.json", "installed_skills"
        )
        agents_manifest = manifest_names(
            agents_dir / ".nwave-agents-manifest.json", "installed_agents"
        )
        candidates: list[tuple[Path, Path]] = []
        if skills_dir.is_dir() and not skills_dir.is_symlink():
            for path in sorted(skills_dir.glob("nw-*")):
                skill = path / "SKILL.md"
                if (
                    path.name not in skills_manifest
                    and not path.is_symlink()
                    and path.is_dir()
                    and skill.is_file()
                    and not skill.is_symlink()
                    and all(not child.is_symlink() for child in path.rglob("*"))
                ):
                    candidates.append(
                        (path, Path("legacy-codex-dev") / "skills" / path.name)
                    )
        if agents_dir.is_dir() and not agents_dir.is_symlink():
            for path in sorted(agents_dir.glob("nw-*.toml")):
                if (
                    path.stem not in agents_manifest
                    and path.is_file()
                    and not path.is_symlink()
                ):
                    candidates.append(
                        (path, Path("legacy-codex-dev") / "agents" / path.name)
                    )
        return candidates

    def adopt_legacy_codex_dev_assets(self) -> bool:
        """Quarantine opt-in legacy assets in this invocation's normal backup.

        The complete pre-migration state was snapshotted by ``create_backup``.
        Relocation itself is recoverable too: moved paths live under the same
        backup directory.  No hook, manifest-owned asset, or non-nWave path is
        considered here.
        """
        if not self._legacy_codex_dev_adoption_enabled:
            return True
        candidates = self._legacy_codex_dev_candidates()
        if not candidates:
            return True
        if self._codex_backup_dir is None:
            self.logger.error(
                "  ❌ Legacy Codex adoption refused: backup was not created"
            )
            return False
        try:
            for source, relative_destination in candidates:
                destination = self._codex_backup_dir / relative_destination
                if destination.exists() or destination.is_symlink():
                    raise FileExistsError(destination)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(destination))
            receipt = self._codex_backup_dir / "legacy-codex-dev" / "receipt.json"
            receipt.write_text(
                json.dumps(
                    {
                        "adopted_at": datetime.now().isoformat(timespec="seconds"),
                        "assets": [
                            {"source": str(source), "quarantine": str(relative)}
                            for source, relative in candidates
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            self.logger.info(
                f"  ✅ Quarantined {len(candidates)} legacy Codex dev asset(s) in {self._codex_backup_dir}"
            )
            return True
        except OSError as exc:
            self.logger.error(f"  ❌ Legacy Codex adoption failed: {exc}")
            return False

    def validate_codex_ownership_preflight(self) -> bool:
        """Reject ambiguous Codex ownership before the installer writes.

        Codex plugins intentionally preserve user configuration, but cannot
        safely decide whether an existing reserved nWave path is theirs without
        a well-formed, contained manifest.  This check runs before backup,
        target-directory creation, and plugin dispatch so a refusal leaves the
        complete user state untouched.
        """
        if "codex" not in self.effective_target_platforms:
            return True

        agents_home_override = os.environ.get("NWAVE_AGENTS_HOME")
        agents_home = (
            Path(agents_home_override) if agents_home_override else Path.home()
        )
        skills_dir = agents_home / ".agents" / "skills"
        codex_home_override = os.environ.get("CODEX_HOME")
        codex_dir = (
            Path(codex_home_override) if codex_home_override else Path.home() / ".codex"
        )
        agents_dir = codex_dir / "agents"
        # Each entry is (kind, line) rather than a bare string: ``kind`` keys
        # the aggregation + HOW-remedy lookup at the bottom of this method,
        # so a flood of same-shape collisions collapses to one header + one
        # remedy instead of N repeated, HOW-less log lines (see
        # _OWNERSHIP_PREFLIGHT_REMEDIES for the fixed set of kinds and why
        # each maps to a DIFFERENT fix, never one generic HOW for all).
        errors: list[tuple[str, str]] = []
        public_agents = load_public_agents(self.project_root / "nWave")
        legacy_agent_names = {
            source.stem
            for source in (self.framework_source / "agents").glob("nw-*.md")
            if is_public_agent(source.name, public_agents)
        } | _LEGACY_CODEX_AGENT_ALIASES
        hooks_path = codex_dir / "hooks.json"
        des_manifest_path = codex_dir / ".nwave-des-manifest.json"
        launcher_path = codex_dir / "nwave_claude_code_hook_adapter_launcher.py"

        def regular_file(path: Path) -> bool:
            return not path.is_symlink() and path.is_file()

        def safe_directory(path: Path) -> bool:
            return not path.is_symlink() and path.is_dir()

        def safe_skill_tree(path: Path) -> bool:
            if not safe_directory(path):
                return False
            try:
                skill = path / "SKILL.md"
                return regular_file(skill) and all(
                    not child.is_symlink() and (child.is_dir() or child.is_file())
                    for child in path.rglob("*")
                )
            except OSError:
                return False

        skills_dir_safe = not (
            skills_dir.exists() or skills_dir.is_symlink()
        ) or safe_directory(skills_dir)
        agents_dir_safe = not (
            agents_dir.exists() or agents_dir.is_symlink()
        ) or safe_directory(agents_dir)
        for label, path in (
            ("Codex skills directory", skills_dir),
            ("Codex agents directory", agents_dir),
            ("Codex hooks configuration", hooks_path),
            ("nWave DES manifest", des_manifest_path),
            ("nWave DES launcher", launcher_path),
        ):
            if (path.exists() or path.is_symlink()) and (
                (path in {skills_dir, agents_dir} and not safe_directory(path))
                or (path not in {skills_dir, agents_dir} and not regular_file(path))
            ):
                errors.append(("unsafe-path", f"unsafe {label}: {path}"))

        legacy_direct_command: str | None = None
        legacy_launcher_witness = False
        legacy_direct_hook_witness = False
        orphan_launcher_witness = False
        if regular_file(des_manifest_path) and regular_file(hooks_path):
            try:
                from scripts.install.plugins.codex_des_plugin import (
                    _legacy_direct_des_command,
                    _v1_launcher_source,
                )

                legacy_manifest = json.loads(
                    des_manifest_path.read_text(encoding="utf-8")
                )
                legacy_hooks = json.loads(hooks_path.read_text(encoding="utf-8"))
                legacy_direct_command = _legacy_direct_des_command(
                    legacy_manifest, hooks_path, legacy_hooks
                )
                expected_legacy_launcher_command = shlex.join(
                    [
                        legacy_manifest["python_path"],
                        str(launcher_path),
                        "pre-tool-use",
                    ]
                )
                legacy_pretool = (
                    legacy_hooks.get("hooks", {}).get("PreToolUse", [])
                    if isinstance(legacy_hooks, dict)
                    and isinstance(legacy_hooks.get("hooks"), dict)
                    else []
                )
                launcher_hook_present = any(
                    isinstance(group, dict)
                    and isinstance(group.get("hooks"), list)
                    and any(
                        isinstance(handler, dict)
                        and handler.get("command") == expected_legacy_launcher_command
                        for handler in group["hooks"]
                    )
                    for group in legacy_pretool
                )
                if (
                    isinstance(legacy_manifest, dict)
                    and set(legacy_manifest)
                    == {"hooks_file", "python_path", "pythonpath"}
                    and legacy_manifest.get("hooks_file") == str(hooks_path)
                    and isinstance(legacy_manifest.get("python_path"), str)
                    and legacy_manifest["python_path"]
                    and isinstance(legacy_manifest.get("pythonpath"), str)
                    and legacy_manifest["pythonpath"]
                    and regular_file(launcher_path)
                    and launcher_path.read_text(encoding="utf-8")
                    == _v1_launcher_source(
                        legacy_manifest["python_path"], legacy_manifest["pythonpath"]
                    )
                    and launcher_hook_present
                ):
                    legacy_launcher_witness = True
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                pass

        def manifest_names(path: Path, key: str) -> set[str] | None:
            if not (path.exists() or path.is_symlink()):
                return None
            if not regular_file(path):
                errors.append(("unsafe-path", f"unsafe nWave manifest {path}"))
                return set()
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(
                    ("corrupt-file", f"unreadable nWave manifest {path}: {exc}")
                )
                return set()
            names = document.get(key) if isinstance(document, dict) else None
            if (
                not isinstance(document, dict)
                or document.get("version") != "1.0"
                or not isinstance(names, list)
                or any(
                    not isinstance(name, str)
                    or not name.startswith("nw-")
                    or Path(name).name != name
                    for name in names
                )
                or len(names) != len(set(names))
            ):
                errors.append(("untrusted-content", f"untrusted nWave manifest {path}"))
                return set()
            return set(names)

        skill_manifest = (
            manifest_names(skills_dir / ".nwave-manifest.json", "installed_skills")
            if skills_dir_safe
            else None
        )
        agent_manifest = (
            manifest_names(
                agents_dir / ".nwave-agents-manifest.json", "installed_agents"
            )
            if agents_dir_safe
            else None
        )
        # Explicit dev-only adoption is the sole exception to the normal
        # name-is-not-ownership rule.  Only structurally safe, unmanifested
        # assets may be quarantined after the ordinary backup; every other
        # collision remains a preflight refusal.
        adoptable_skill_names: set[str] = set()
        adoptable_agent_names: set[str] = set()
        if self._legacy_codex_dev_adoption_enabled:
            if skills_dir_safe and skills_dir.exists():
                adoptable_skill_names = {
                    path.name
                    for path in skills_dir.glob("nw-*")
                    if (skill_manifest is None or path.name not in skill_manifest)
                    and safe_skill_tree(path)
                }
            if agents_dir_safe and agents_dir.exists():
                adoptable_agent_names = {
                    path.stem
                    for path in agents_dir.glob("nw-*.toml")
                    if (agent_manifest is None or path.stem not in agent_manifest)
                    and regular_file(path)
                }
        # This is deliberately separate from the manifest catalogue.  It can
        # contain only the closed set returned by the byte-level v1 witness;
        # no directory discovery result is ever promoted to ownership here.
        attested_legacy_skills: set[str] = set()

        # A v1 public Codex manifest historically omitted a closed pair of
        # command skills.  Its DES witness corroborates that this is the
        # bootstrap shape, while the skill helper proves every omitted tree
        # byte-for-byte.  No current command discovery participates here:
        # future nw-* directories remain foreign until a manifest records
        # them explicitly.
        if skills_dir_safe and skills_dir.exists() and skill_manifest is not None:
            try:
                from scripts.install.plugins.codex_skills_plugin import (
                    legacy_v1_omitted_command_skills,
                )

                skill_document = json.loads(
                    (skills_dir / ".nwave-manifest.json").read_text(encoding="utf-8")
                )
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                skill_document = None
            unlisted_skills = {
                path.name
                for path in skills_dir.glob("nw-*")
                if path.name not in skill_manifest
            }
            if unlisted_skills:
                omissions = (
                    legacy_v1_omitted_command_skills(skills_dir, skill_document)
                    if (legacy_direct_command is not None or legacy_launcher_witness)
                    else None
                )
                unadoptable_skills = unlisted_skills - adoptable_skill_names
                if omissions is not None and omissions == unlisted_skills:
                    attested_legacy_skills = omissions
                elif unadoptable_skills:
                    errors.extend(
                        (
                            "foreign-collision-adoptable-skill",
                            f"foreign or untracked Codex skill collision: {skills_dir / name}",
                        )
                        for name in sorted(unadoptable_skills)
                    )

        # A reserved nWave name without a manifest is not adoptable: it could
        # be a foreign file and the plugin would otherwise replace it.
        if skills_dir_safe and skills_dir.exists() and skill_manifest is None:
            for path in skills_dir.glob("nw-*"):
                if path.name not in adoptable_skill_names:
                    errors.append(
                        (
                            "foreign-collision-adoptable-skill",
                            f"foreign or untracked Codex skill collision: {path}",
                        )
                    )
        if agents_dir_safe and agents_dir.exists() and agent_manifest is None:
            for path in agents_dir.glob("nw-*.toml"):
                if (
                    not (
                        legacy_direct_command is not None
                        and path.stem in legacy_agent_names
                    )
                    and path.stem not in adoptable_agent_names
                ):
                    errors.append(
                        (
                            "foreign-collision-adoptable-agent",
                            f"foreign or untracked Codex agent collision: {path}",
                        )
                    )

        if skill_manifest is not None:
            owned_skill_names = skill_manifest | attested_legacy_skills
            for name in owned_skill_names:
                if not safe_skill_tree(skills_dir / name):
                    errors.append(
                        (
                            "missing-owned-asset",
                            f"manifest-owned Codex skill is missing: {name}",
                        )
                    )
            for path in skills_dir.glob("nw-*"):
                if (
                    path.name not in owned_skill_names
                    and path.name not in adoptable_skill_names
                ):
                    errors.append(
                        (
                            "foreign-collision-adoptable-skill",
                            f"foreign or untracked Codex skill collision: {path}",
                        )
                    )
        if agent_manifest is not None:
            for name in agent_manifest:
                if not regular_file(agents_dir / f"{name}.toml"):
                    errors.append(
                        (
                            "missing-owned-asset",
                            f"manifest-owned Codex agent is missing: {name}",
                        )
                    )
            for path in agents_dir.glob("nw-*.toml"):
                if (
                    path.stem not in agent_manifest
                    and path.stem not in adoptable_agent_names
                ):
                    errors.append(
                        (
                            "foreign-collision-adoptable-agent",
                            f"foreign or untracked Codex agent collision: {path}",
                        )
                    )

        hooks: object = None
        if regular_file(hooks_path):
            try:
                hooks_document = json.loads(hooks_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(
                    (
                        "corrupt-file",
                        f"malformed Codex hooks configuration {hooks_path}: {exc}",
                    )
                )
            else:
                hooks = (
                    hooks_document.get("hooks")
                    if isinstance(hooks_document, dict)
                    else None
                )
                if not isinstance(hooks, dict) or any(
                    not isinstance(entries, list) for entries in hooks.values()
                ):
                    errors.append(
                        (
                            "untrusted-content",
                            f"ambiguous Codex hooks configuration {hooks_path}",
                        )
                    )

        if regular_file(des_manifest_path):
            try:
                des_manifest = json.loads(des_manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(
                    (
                        "corrupt-file",
                        f"unreadable nWave DES manifest {des_manifest_path}: {exc}",
                    )
                )
            else:
                if legacy_direct_command is not None:
                    # A public direct-hook bootstrap could leave behind the
                    # newer canonical launcher without recording it in its
                    # three-field manifest.  Adopt that orphan only when the
                    # direct hook is exact and the launcher round-trips to the
                    # fixed generated template with both embedded paths under
                    # this user's historical .nwave runtime root.
                    try:
                        from scripts.install.plugins.codex_des_plugin import (
                            _build_hook_entry,
                            _launcher_source,
                        )

                        expected_direct = _build_hook_entry(
                            des_manifest["python_path"], des_manifest["pythonpath"]
                        )["hooks"][0]["command"]
                        legacy_direct_hook_witness = (
                            legacy_direct_command == expected_direct
                        )
                        launcher_source = launcher_path.read_text(encoding="utf-8")
                        launcher_tree = ast.parse(launcher_source)
                        launcher_values = {
                            node.targets[0].id: node.value.value
                            for node in launcher_tree.body
                            if isinstance(node, ast.Assign)
                            and len(node.targets) == 1
                            and isinstance(node.targets[0], ast.Name)
                            and isinstance(node.value, ast.Constant)
                            and isinstance(node.value.value, str)
                            and node.targets[0].id in {"PYTHON_PATH", "PYTHONPATH"}
                        }
                        launcher_python = launcher_values["PYTHON_PATH"]
                        launcher_pythonpath = launcher_values["PYTHONPATH"]
                        legacy_runtime_dir = agents_home / ".nwave"
                        runtime_root_is_safe = (
                            not legacy_runtime_dir.is_symlink()
                            and legacy_runtime_dir.is_dir()
                        )
                        legacy_runtime_root = legacy_runtime_dir.resolve(strict=False)
                        lexical_runtime_root = Path(
                            os.path.normpath(str(legacy_runtime_dir))
                        )
                        lexical_python = Path(os.path.normpath(launcher_python))
                        pythonpath_is_contained = Path(
                            launcher_pythonpath
                        ).is_absolute() and Path(launcher_pythonpath).resolve(
                            strict=False
                        ).is_relative_to(legacy_runtime_root)
                        # The candidate venv's terminal interpreter is often
                        # a symlink to the host Python.  Its pathname and its
                        # parent must still be inside .nwave; only that final
                        # interpreter link may leave the runtime root.
                        python_is_contained = (
                            lexical_python.is_absolute()
                            and lexical_python.is_relative_to(lexical_runtime_root)
                            and lexical_python.parent.resolve(
                                strict=False
                            ).is_relative_to(legacy_runtime_root)
                        )
                        orphan_launcher_witness = (
                            legacy_direct_hook_witness
                            and regular_file(launcher_path)
                            and runtime_root_is_safe
                            and pythonpath_is_contained
                            and python_is_contained
                            and launcher_source
                            == _launcher_source(launcher_python, launcher_pythonpath)
                        )
                    except (
                        KeyError,
                        OSError,
                        UnicodeDecodeError,
                        SyntaxError,
                        TypeError,
                        ValueError,
                    ):
                        orphan_launcher_witness = False
                    if launcher_path.exists() and not (
                        legacy_launcher_witness or orphan_launcher_witness
                    ):
                        errors.append(
                            (
                                "foreign-collision-manual",
                                f"untracked nWave DES launcher collision: {launcher_path}",
                            )
                        )
                elif not (
                    isinstance(des_manifest, dict)
                    and des_manifest.get("hooks_file") == str(hooks_path)
                    and des_manifest.get("launcher_file") == str(launcher_path)
                    and isinstance(des_manifest.get("python_path"), str)
                    and isinstance(des_manifest.get("pythonpath"), str)
                    and set(des_manifest)
                    in (
                        {
                            "hooks_file",
                            "python_path",
                            "pythonpath",
                            "launcher_file",
                        },
                        {
                            "hooks_file",
                            "python_path",
                            "pythonpath",
                            "launcher_file",
                            "session_start_launcher_file",
                            "resolver_script_file",
                        },
                    )
                ):
                    errors.append(
                        (
                            "untrusted-content",
                            f"untrusted nWave DES manifest {des_manifest_path}",
                        )
                    )
                else:
                    from scripts.install.plugins.codex_des_plugin import (
                        _command_owns_launcher,
                        _launcher_source,
                    )

                    try:
                        launcher_source = launcher_path.read_text(encoding="utf-8")
                    except OSError as exc:
                        errors.append(
                            (
                                "corrupt-file",
                                f"unreadable nWave DES launcher {launcher_path}: {exc}",
                            )
                        )
                    else:
                        if launcher_source != _launcher_source(
                            des_manifest["python_path"], des_manifest["pythonpath"]
                        ):
                            errors.append(
                                (
                                    "untrusted-content",
                                    f"untrusted nWave DES launcher {launcher_path}",
                                )
                            )
                    has_owned_launcher_hook = isinstance(hooks, dict) and any(
                        isinstance(group, dict)
                        and any(
                            isinstance(handler, dict)
                            and _command_owns_launcher(
                                handler.get("command", ""), launcher_path
                            )
                            for handler in group.get("hooks", [])
                            if isinstance(group.get("hooks", []), list)
                        )
                        for groups in hooks.values()
                        for group in groups
                    )
                    if not has_owned_launcher_hook:
                        errors.append(
                            (
                                "untrusted-content",
                                f"untrusted nWave DES hook {hooks_path}",
                            )
                        )
        elif launcher_path.exists():
            errors.append(
                (
                    "foreign-collision-manual",
                    f"untracked nWave DES launcher collision: {launcher_path}",
                )
            )

        self._report_ownership_preflight_errors(errors)
        return not errors

    _OWNERSHIP_PREFLIGHT_SAMPLE_LIMIT = 5

    def _report_ownership_preflight_errors(self, errors: list[tuple[str, str]]) -> None:
        """Emit the Codex ownership preflight refusal, aggregated with a HOW.

        A same-shape flood (e.g. one line per legacy Codex skill directory)
        must not become one near-identical, HOW-less log line per collision
        -- that buries the one fact the operator needs under noise (GDP-3)
        and forces them to read installer source to find the fix (GDP-4).
        Errors are grouped by ``kind``; each group prints a bounded sample
        (house style shared with e.g. check_trailing_whitespace.py's
        "... and N more") followed by the ONE remedy that fits that kind --
        never a single generic remedy reused across kinds that need
        different fixes. The method ends on an explicit verdict line so the
        log never simply stops on the last collision with the outcome left
        to be inferred.
        """
        if not errors:
            return
        by_kind: dict[str, list[str]] = {}
        for kind, line in errors:
            by_kind.setdefault(kind, []).append(line)
        for kind, lines in sorted(by_kind.items()):
            lines = sorted(lines)
            limit = self._OWNERSHIP_PREFLIGHT_SAMPLE_LIMIT
            for line in lines[:limit]:
                self.logger.error(f"  ❌ Ownership preflight: {line}")
            if len(lines) > limit:
                self.logger.error(f"       ... and {len(lines) - limit} more")
            how = _OWNERSHIP_PREFLIGHT_REMEDIES.get(kind)
            if how:
                self.logger.error(f"       HOW: {how}")
        self.logger.error(
            f"  ❌ Installation refused: {len(errors)} Codex ownership "
            f"collision(s) across {len(by_kind)} failure kind(s) -- "
            "0 files written, nothing changed."
        )

    def restore_backup(self) -> bool:
        """Restore from most recent backup.

        Returns True on success, False on failure. On success, the selected
        backup path is also exposed via ``self.last_restored_from`` (public
        observability contract — see ``__init__``). Bool return is preserved
        for the existing caller in ``main()``.
        """
        self.logger.info("  🔍 Looking for backups to restore...")

        backup_root = self.claude_config_dir / "backups"
        if not backup_root.exists():
            self.logger.error(f"  ❌ No backups found in {backup_root}")
            return False

        # Find latest backup
        backups = sorted(backup_root.glob("nwave-*"))
        if not backups:
            self.logger.error("  ❌ No nWave backups found")
            return False

        latest_backup = backups[-1]
        self.last_restored_from = latest_backup
        self.logger.info(f"  ⏳ Restoring from {latest_backup}")

        # Remove current installation
        agents_dir = self.claude_config_dir / "agents"
        commands_dir = self.claude_config_dir / "commands"

        if agents_dir.exists():
            import shutil

            shutil.rmtree(agents_dir)
        if commands_dir.exists():
            import shutil

            shutil.rmtree(commands_dir)

        # Restore from backup
        backup_agents = latest_backup / "agents"
        backup_commands = latest_backup / "commands"

        if backup_agents.exists():
            import shutil

            shutil.copytree(backup_agents, agents_dir)
            self.logger.info("  ✅ Agents restored")

        if backup_commands.exists():
            import shutil

            shutil.copytree(backup_commands, commands_dir)
            self.logger.info("  ✅ Commands restored")

        self.logger.info(f"  🍾 Restoration complete from {latest_backup}")
        return True

    def _create_plugin_registry(
        self, silent: bool = False, target_platforms: set[str] | None = None
    ) -> PluginRegistry:
        """Create and configure the plugin registry with all installation plugins.

        Args:
            silent: When True, pass logger=None to suppress registration log messages.
            target_platforms: Set of platform strings to install for.
                When None or contains "claude_code", registers Claude Code plugins.
                When contains "opencode", also registers OpenCode plugins.

        Returns:
            PluginRegistry configured with plugins for the target platforms.
        """
        registry = PluginRegistry(logger=None if silent else self.logger)
        requested_platforms = target_platforms or {"claude_code"}

        # The DES runtime is host-neutral.  Every other shared plugin writes a
        # Claude discovery surface and is therefore registered only for Claude.
        des_plugin = DESPlugin()
        if "claude_code" not in requested_platforms:
            des_plugin.set_dependencies([])
        registry.register(des_plugin)
        if "claude_code" in requested_platforms:
            registry.register(TemplatesPlugin())
            registry.register(UtilitiesPlugin())
            registry.register(AgentsPlugin())
            registry.register(CommandsPlugin())
            registry.register(SkillsPlugin())
            registry.register(AttributionPlugin())
        # OpenCode plugins (registered when opencode detected)
        if target_platforms and "opencode" in target_platforms:
            opencode_skills = OpenCodeSkillsPlugin()
            opencode_agents = OpenCodeAgentsPlugin()
            opencode_commands = OpenCodeCommandsPlugin()
            registry.register(opencode_skills)
            registry.register(opencode_agents)
            registry.register(opencode_commands)
            opencode_agents.set_dependencies(["opencode-skills"])
            opencode_commands.set_dependencies(["opencode-skills"])
            opencode_des = OpenCodeDESPlugin()
            registry.register(opencode_des)
        # Codex CLI plugins (registered when codex detected)
        if target_platforms and "codex" in target_platforms:
            codex_skills = CodexSkillsPlugin()
            registry.register(codex_skills)
            codex_agents = CodexAgentsPlugin()
            codex_agents.set_dependencies(["codex-skills"])
            registry.register(codex_agents)
            codex_des = CodexDESPlugin()
            codex_des.set_dependencies(["des", "codex-skills"])
            registry.register(codex_des)
        # Copilot CLI plugins (registered when copilot detected)
        if target_platforms and "copilot" in target_platforms:
            copilot_des = CopilotDESPlugin()
            copilot_des.set_dependencies(["des"])
            registry.register(copilot_des)
        return registry

    def install_framework(self) -> bool:
        """Install framework files using plugin-based orchestration.

        Uses PluginRegistry to orchestrate installation of all components:
        - agents (priority 10)
        - commands (priority 20)
        - templates (priority 30)
        - skills (priority 35)
        - utilities (priority 40)

        Returns:
            True if all plugins installed successfully, False otherwise.
        """
        target_platforms = self.effective_target_platforms
        if self.dry_run:
            if target_platforms == frozenset({"codex"}):
                from scripts.install.plugins.codex_agents_plugin import (
                    _codex_agents_dir,
                )
                from scripts.install.plugins.codex_des_plugin import _codex_config_dir
                from scripts.install.plugins.codex_skills_plugin import (
                    _codex_skills_dir,
                )
                from scripts.shared.agent_catalog import (
                    build_ownership_map,
                    detect_command_skills,
                )
                from scripts.shared.skill_distribution import (
                    enumerate_skills,
                    filter_public_skills,
                )

                agents_source = self.framework_source / "agents"
                public_agents = (
                    set()
                    if self.dev_mode
                    else load_public_agents(self.project_root / "nWave")
                )
                agent_count = sum(
                    is_public_agent(source.name, public_agents)
                    for source in agents_source.glob("nw-*.md")
                )
                skills_source = self.framework_source / "skills"
                skill_entries = enumerate_skills(skills_source)
                if not self.dev_mode:
                    skill_entries = filter_public_skills(
                        skill_entries,
                        public_agents,
                        build_ownership_map(agents_source),
                        detect_command_skills(skills_source),
                    )
                self.logger.info(
                    f"  🚨 [DRY RUN] Would install {len(skill_entries)} Codex skills to "
                    f"{_codex_skills_dir()}"
                )
                self.logger.info(
                    f"  🚨 [DRY RUN] Would install {agent_count} Codex agents to "
                    f"{_codex_agents_dir()}"
                )
                self.logger.info(
                    "  🚨 [DRY RUN] Would install Codex DES hook to "
                    f"{_codex_config_dir() / 'hooks.json'}"
                )
                return True
            self.logger.info(
                f"  🚨 [DRY RUN] Would install nWave framework to: {self.claude_config_dir}"
            )
            self.logger.info(
                f"  🚨 [DRY RUN] Would create target directory: {self.claude_config_dir}"
            )

            # Show what would be installed from nWave/ source
            agents_dir = self.project_root / "nWave" / "agents"
            commands_dir = self.project_root / "nWave" / "tasks" / "nw"

            if agents_dir.exists():
                agent_count = PathUtils.count_files(agents_dir, "nw-*.md")
                self.logger.info(
                    f"  🚨 [DRY RUN] Would install {agent_count} agent files"
                )

            if commands_dir.exists():
                command_count = PathUtils.count_files(commands_dir, "*.md")
                self.logger.info(
                    f"  🚨 [DRY RUN] Would install {command_count} command files"
                )

            return True

        self.logger.info("")
        # Announce the Claude directory ONLY when Claude Code is a target.  A
        # Codex/OpenCode/Copilot-only run writes nothing there, and naming a
        # path the run will never touch is a silent-wrong: the user reads a
        # location, follows the closing "reopen Claude Code" line, and finds an
        # empty directory.
        if "claude_code" in target_platforms:
            self.logger.info(f"  💿 Installing nWave → {self.claude_config_dir}")
        else:
            hosts = ", ".join(sorted(target_platforms))
            self.logger.info(f"  💿 Installing nWave → {hosts}")

        # Codex has no Claude activation surface.  Do not create an empty
        # ~/.claude directory merely because the installer knows its legacy
        # location.
        if "claude_code" in target_platforms:
            self.claude_config_dir.mkdir(parents=True, exist_ok=True)

        # Create plugin registry and install all components
        registry = self._create_plugin_registry(target_platforms=target_platforms)

        # Create installation context with all required utilities
        context = InstallContext(
            claude_dir=self.claude_config_dir,
            scripts_dir=self.project_root / "scripts" / "install",
            templates_dir=self.framework_source / "templates",
            logger=self.logger,
            project_root=self.project_root,
            framework_source=self.framework_source,
            dry_run=self.dry_run,
            dev_mode=self.dev_mode,
            target_platforms=target_platforms,
        )

        self.logger.info("  📑 Installing Context...")
        with self.logger.progress_spinner("  🚧 Work in progress..."):
            # Execute all plugins through registry
            results = registry.install_all(context)

        # Check if any plugin failed
        for plugin_name, result in results.items():
            if not result.success:
                self.logger.error(
                    f"  ❌ Plugin '{plugin_name}' failed: {result.message}"
                )
                return False

        # Close on the PROPERTY, not on "the branch was taken": an announced
        # Claude target that is still empty here means the run would otherwise
        # report success over a directory the user will find bare.  Degrade
        # LOUD rather than let the declared fact and the disk diverge.
        if "claude_code" in target_platforms and not any(
            self.claude_config_dir.iterdir()
        ):
            self.logger.error(
                f"  ❌ WHAT: nothing was installed into {self.claude_config_dir}, "
                "yet it was announced as the install target."
            )
            self.logger.error(
                "  WHY: the Claude Code plugins produced no files, so Claude Code "
                "would start with no nWave agents, skills or commands."
            )
            self.logger.error(
                "  HOW: re-run the installer with the target made explicit -- "
                f"CLAUDE_CONFIG_DIR={self.claude_config_dir} "
                "python -m nwave_ai.cli install"
            )
            return False

        return True

    def _validate_schema_template(self) -> bool:
        """Validate TDD cycle schema template has required fields.

        The schema file is shipped by TemplatesPlugin, which -- like
        CommandsPlugin and SkillsPlugin -- _create_plugin_registry registers
        only when "claude_code" is in the requested platforms. A Copilot/
        OpenCode-only install never receives it, so the check is not
        applicable there (fourth instance of the same gap in this module).
        """
        if "claude_code" not in self.effective_target_platforms:
            return True

        schema_file = (
            self.claude_config_dir / "templates" / "step-tdd-cycle-schema.json"
        )

        if not schema_file.exists():
            self.logger.error("  ❌ Schema template not found")
            return False

        try:
            import json

            with open(schema_file) as f:
                schema = json.load(f)

            # Check for schema_version field
            if "schema_version" not in schema:
                self.logger.error("  ❌ Schema missing 'schema_version' field")
                return False

            schema_version = schema.get("schema_version")

            # Validate schema version and phase count
            valid_schemas = {
                "2.0": {"phases": 8, "description": "8-phase TDD optimization"},
                "3.0": {
                    "phases": 7,
                    "description": "7-phase TDD (L4-L6 moved to orchestrator)",
                },
                "4.0": {
                    "phases": 5,
                    "description": "5-phase TDD (REVIEW/REFACTOR moved to deliver)",
                },
            }

            if schema_version not in valid_schemas:
                self.logger.warn(
                    f"  ⚠️ Schema version {schema_version}, expected 2.0, 3.0, or 4.0"
                )
                return False

            # Check phase count matches schema version
            phase_exec_log = schema.get("tdd_cycle", {}).get("phase_execution_log", [])
            expected_phases = valid_schemas[schema_version]["phases"]

            if len(phase_exec_log) != expected_phases:
                self.logger.error(
                    f"  ❌ Schema has {len(phase_exec_log)} phases, expected {expected_phases} for v{schema_version}"
                )
                return False

            schema_desc = valid_schemas[schema_version]["description"]
            self.logger.info(
                f"    👍 TDD cycle schema: v{schema_version} with {expected_phases} phases ({schema_desc})"
            )
            return True

        except Exception as e:
            self.logger.error(f"  ❌ Schema validation failed: {e}")
            return False

    def validate_installation(self) -> bool:
        """Validate installation using shared InstallationVerifier.

        Uses the InstallationVerifier module for consistent verification logic
        between standalone verification and post-build verification.

        Returns:
            True if verification passed, False otherwise.
        """
        target_platforms = self.effective_target_platforms
        codex_valid = True
        if "codex" in target_platforms:
            codex_only = target_platforms == {"codex"}
            codex_valid = self._validate_codex_installation(verify_plugins=codex_only)
            if codex_only:
                return codex_valid

        self.logger.info("")
        self.logger.info("  🔎 Validate Installation...")
        with self.logger.progress_spinner("  🚧 Work in progress..."):
            # Use shared InstallationVerifier for consistent verification
            verifier = InstallationVerifier(
                claude_config_dir=self.claude_config_dir,
                use_host_neutral_runtime="claude_code" not in target_platforms,
                check_essential_commands="claude_code" in target_platforms,
                check_manifest="claude_code" in target_platforms,
            )
            result = verifier.run_verification()

            # Validate schema template (additional check specific to installer)
            schema_valid = self._validate_schema_template()

        # Plugin verification via registry.verify_all()
        plugin_registry = self._create_plugin_registry(
            silent=True, target_platforms=target_platforms
        )
        plugin_context = InstallContext(
            claude_dir=self.claude_config_dir,
            scripts_dir=self.project_root / "scripts" / "install",
            templates_dir=self.framework_source / "templates",
            logger=self.logger,
            project_root=self.project_root,
            framework_source=self.framework_source,
            dry_run=self.dry_run,
            dev_mode=self.dev_mode,
            target_platforms=target_platforms,
        )
        plugin_results = plugin_registry.verify_all(plugin_context)
        plugin_failures = {
            name: r for name, r in plugin_results.items() if not r.success
        }

        # Verify components: compare source files vs installed target
        # Supports both dist/ layout (agents/nw/, commands/nw/) and
        # nWave/ source layout (agents/nw-*.md, tasks/nw/*.md)
        #
        # Agents/Commands/Templates/Scripts are all shipped by plugins that
        # _create_plugin_registry registers ONLY when "claude_code" is in the
        # requested platforms (TemplatesPlugin, UtilitiesPlugin, AgentsPlugin,
        # CommandsPlugin, SkillsPlugin -- "every other shared plugin writes a
        # Claude discovery surface"). A Copilot/OpenCode-only target never
        # gets those plugins, so judging it against these components' source
        # counts fails validation unconditionally, regardless of whether the
        # install the target actually owns succeeded.
        all_synced = True
        components: list[ComponentResult] = []

        if "claude_code" in target_platforms:
            # Agents: dist/agents/nw/ or nWave/agents/
            # In dev_mode, all agents are installed; otherwise only public
            dist_agents = self.framework_source / "agents" / "nw"
            if dist_agents.exists():
                agents_source = dist_agents
            else:
                agents_source = self.project_root / "nWave" / "agents"
            agents_target = self.claude_config_dir / "agents" / "nw"
            if agents_source.exists():
                public_agents = (
                    set()
                    if self.dev_mode
                    else load_public_agents(self.project_root / "nWave")
                )
                agent_source_files = sorted(
                    f
                    for f in agents_source.glob("nw-*.md")
                    if is_public_agent(f.name, public_agents)
                )
                agent_matched = sum(
                    1 for f in agent_source_files if (agents_target / f.name).exists()
                )
                agent_expected = len(agent_source_files)
                agent_ok = agent_matched == agent_expected and agent_expected > 0
                if not agent_ok:
                    all_synced = False
                components.append(
                    ComponentResult("agents", agent_matched, agent_expected, agent_ok)
                )
                self.logger.info(
                    f"    {'✅' if agent_ok else '❌'} Agents verified ({agent_matched}/{agent_expected})"
                )

            # Commands: now installed as skills (nw-{name}/SKILL.md with user-invocable)
            skills_target = self.claude_config_dir / "skills"
            essential_commands = [
                "nw-deliver",
                "nw-design",
                "nw-discuss",
                "nw-distill",
                "nw-devops",
                "nw-review",
            ]
            cmd_matched = sum(
                1
                for name in essential_commands
                if (skills_target / name / "SKILL.md").exists()
            )
            cmd_expected = len(essential_commands)
            cmd_ok = cmd_matched == cmd_expected
            if not cmd_ok:
                all_synced = False
            components.append(
                ComponentResult("commands", cmd_matched, cmd_expected, cmd_ok)
            )
            self.logger.info(
                f"    {'✅' if cmd_ok else '❌'} Commands verified ({cmd_matched}/{cmd_expected})"
            )

            # Templates from framework_source/templates/
            #
            # Content-aware verify (M1 fix-installer-silent-template-skip): replace
            # the existence-only check with a md5 compare so a stale target that
            # diverges from source is reported as drift instead of "verified".
            templates_source = self.framework_source / "templates"
            templates_target = self.claude_config_dir / "templates"
            if templates_source.exists():
                tmpl_files = [f for f in templates_source.iterdir() if f.is_file()]
                tmpl_drifted: list[str] = []
                tmpl_matched = 0
                for f in tmpl_files:
                    if _files_content_equal(f, templates_target / f.name):
                        tmpl_matched += 1
                    else:
                        tmpl_drifted.append(f.name)
                tmpl_expected = len(tmpl_files)
                tmpl_ok = _component_synced(tmpl_matched, tmpl_expected)
                if not tmpl_ok:
                    all_synced = False
                components.append(
                    ComponentResult("templates", tmpl_matched, tmpl_expected, tmpl_ok)
                )
                self.logger.info(
                    f"    {'✅' if tmpl_ok else '❌'} Templates verified ({tmpl_matched}/{tmpl_expected})"
                )
                for drifted in tmpl_drifted:
                    self.logger.error(
                        f"      ❌ Content drift: templates/{drifted} differs from source "
                        f"(re-run `python -m nwave_ai.cli install` to refresh)"
                    )

            # Scripts: dist/scripts/ or project_root/scripts/
            dist_scripts = self.framework_source / "scripts"
            if (
                dist_scripts.exists()
                and (dist_scripts / "install_nwave_target_hooks.py").exists()
            ):
                scripts_source = dist_scripts
            else:
                scripts_source = self.project_root / "scripts"
            scripts_target = self.claude_config_dir / "scripts"
            utility_scripts = ["install_nwave_target_hooks.py", "validate_step_file.py"]
            script_files = [s for s in utility_scripts if (scripts_source / s).exists()]
            script_matched = sum(
                1 for s in script_files if (scripts_target / s).exists()
            )
            script_expected = len(script_files)
            script_ok = _component_synced(script_matched, script_expected)
            if not script_ok:
                all_synced = False
            components.append(
                ComponentResult("scripts", script_matched, script_expected, script_ok)
            )
            self.logger.info(
                f"    {'✅' if script_ok else '❌'} Scripts verified ({script_matched}/{script_expected})"
            )

        self.logger.info(
            f"    {'✅' if result.manifest_exists else '❌'} Manifest created"
        )
        self.logger.info(f"    {'✅' if schema_valid else '❌'} Schema validated")

        # Report missing essential files
        if result.missing_essential_files:
            for missing_file in result.missing_essential_files:
                self.logger.error(f"    ❌ Missing essential: {missing_file}")

        # Report plugin verification results
        if plugin_failures:
            for name, r in plugin_failures.items():
                self.logger.error(
                    f"    ❌ {name} plugin verification failed: {r.message}"
                )
                for err in r.errors:
                    self.logger.error(f"      ❌ {err}")
        else:
            self.logger.info("    ✅ All plugins verified")

        # Determine overall success
        overall_success = (
            result.success
            and schema_valid
            and all_synced
            and not plugin_failures
            and codex_valid
        )

        if overall_success:
            self.logger.info("  🍾 Deployment validated")
            return True
        else:
            # Identify every failing condition for clear diagnostics
            failures: list[str] = []
            if not result.success:
                failures.append("essential files missing")
            if not schema_valid:
                failures.append("schema validation failed")
            if not all_synced:
                failures.append(_format_sync_mismatch(components))
            if plugin_failures:
                failures.append(
                    f"plugin verification failed: {', '.join(plugin_failures)}"
                )
            if not codex_valid:
                failures.append("Codex validation failed")
            if not result.manifest_exists:
                failures.append("manifest not created")
            detail = "; ".join(failures) if failures else "unknown condition"
            self.logger.error(
                f"  ❌ Validation failed ({len(failures)} issues: {detail})"
            )
            return False

    def _validate_codex_installation(self, *, verify_plugins: bool = True) -> bool:
        """Validate the Codex-native discovery surfaces selected for this install.

        The Codex skill manifest is the ownership oracle: a public release may
        legitimately omit skills that are private or unavailable for that host.
        Requiring a separate hard-coded command list here would turn that
        policy into a false deployment failure.  The Codex plugin verifies every
        manifest-declared skill; the all-target registry below independently
        verifies the Copilot and OpenCode surfaces.

        Args:
            verify_plugins: run the Codex-scoped plugin registry check here.
                False when the caller is about to run the full all-target
                registry check right after -- that check already covers the
                Codex plugin, and running both double-invokes the same
                registry.verify_all() for no additional signal.
        """
        self.logger.info("")
        self.logger.info("  🔎 Validate Codex Installation...")

        agents_home_override = os.environ.get("NWAVE_AGENTS_HOME")
        agents_home = (
            Path(agents_home_override) if agents_home_override else Path.home()
        )
        skills_dir = agents_home / ".agents" / "skills"
        codex_home_override = os.environ.get("CODEX_HOME")
        codex_home = (
            Path(codex_home_override) if codex_home_override else Path.home() / ".codex"
        )
        native_artifacts = [
            skills_dir / ".nwave-manifest.json",
            codex_home / "agents" / ".nwave-agents-manifest.json",
            codex_home / "hooks.json",
            codex_home / ".nwave-des-manifest.json",
        ]
        missing = [path for path in native_artifacts if not path.exists()]

        plugin_failures: dict[str, object] = {}
        if verify_plugins:
            registry = self._create_plugin_registry(
                silent=True, target_platforms={"codex"}
            )
            context = InstallContext(
                claude_dir=self.claude_config_dir,
                scripts_dir=self.project_root / "scripts" / "install",
                templates_dir=self.framework_source / "templates",
                logger=self.logger,
                project_root=self.project_root,
                framework_source=self.framework_source,
                dry_run=self.dry_run,
                dev_mode=self.dev_mode,
                target_platforms={"codex"},
            )
            plugin_failures = {
                name: result
                for name, result in registry.verify_all(context).items()
                if not result.success
            }
        for path in missing:
            self.logger.error(f"    ❌ Missing Codex artifact: {path}")
        for name, result in plugin_failures.items():
            self.logger.error(
                f"    ❌ {name} plugin verification failed: {result.message}"
            )

        if missing or plugin_failures:
            self.logger.error("  ❌ Codex deployment validation failed")
            return False
        self.logger.info("  🍾 Codex deployment validated")
        return True

    def create_manifest(self) -> None:
        """Create installation manifest."""
        if self.dry_run:
            self.logger.info("  🚨 [DRY RUN] Would create installation manifest")
            return

        ManifestWriter.write_install_manifest(
            self.claude_config_dir,
            self.backup_manager.backup_dir,
            self.script_dir,
            target_platforms=self.effective_target_platforms,
        )

        self.logger.info(
            f"  📄 Installation manifest created: {self.claude_config_dir / 'nwave-manifest.txt'}"
        )


def _force_utf8_console() -> None:
    """Make stdout/stderr able to carry the installer's non-ASCII output.

    The logo's block glyphs and the wave/siren emoji are unrepresentable in
    cp1252, still the default console encoding on a non-UTF-8 Windows box. The
    logo prints before any real work, so an encode error there is a hard install
    failure at the first line of output -- for decoration.

    ``errors="replace"`` is the second belt: if the encoding cannot be changed
    the output degrades to replacement characters instead of raising. A stream
    that cannot reconfigure at all is left alone rather than crashing the
    installer over cosmetics.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            try:
                reconfigure(errors="replace")
            except (ValueError, OSError):
                pass


def print_logo(logger: Logger | None = None) -> None:
    """Print the nWave ASCII art logo with version and taglines.

    Uses Rich markup via logger when available, ANSI fallback otherwise.
    """
    if logger:
        out = logger.print_styled
        wrap = lambda line: f"[cyan]{line}[/cyan]"  # noqa: E731
    else:
        out = print
        wrap = lambda line: f"{_ANSI_BLUE}{line}{_ANSI_NC}"  # noqa: E731

    out("")
    for line in _LOGO_ART[:-1]:
        out(wrap(line))
    out(f"{wrap(_LOGO_ART[-1])}  \U0001f30a \U0001f30a \U0001f30a  v{__version__}")
    out("")
    for tagline in _TAGLINES:
        out(tagline)


def show_title_panel(logger: Logger, dry_run: bool = False) -> None:
    """Display styled title panel when installer starts."""
    print_logo(logger)

    if dry_run:
        logger.print_styled(" 🚨 \\[DRY RUN]")

    logger.print_styled("")


def show_installation_summary(
    logger: Logger,
    target_dir: Path | None = None,
    target_platforms: set[str] | None = None,
) -> None:
    """Display installation summary panel at end of successful install."""
    codex_only = target_platforms == {"codex"}
    logger.info("")
    logger.info(f"  🎉 nWave v{__version__} installed and healthy!")
    if target_dir is not None and not (
        target_platforms and "codex" in target_platforms
    ):
        logger.info(f"  📂 Installed to: {target_dir}")
    logger.info("")
    logger.info("  📖 Quick start")
    command_prefix = "$" if codex_only else "/"
    commands = [
        (f"{command_prefix}nw-discover", "Evidence-based product discovery"),
        (
            f"{command_prefix}nw-discuss",
            "Requirements gathering and business analysis",
        ),
        (
            f"{command_prefix}nw-design",
            "Architecture design with visual representation",
        ),
        (
            f"{command_prefix}nw-distill",
            "Acceptance test creation and business validation",
        ),
        (
            f"{command_prefix}nw-deliver",
            "Outside-In TDD implementation with refactoring",
        ),
    ]
    for cmd, desc in commands:
        logger.info(f"    {cmd:<16} {desc}")
    mixed_hosts = bool(
        target_platforms and {"claude_code", "codex"}.issubset(target_platforms)
    )
    if mixed_hosts:
        logger.info(
            "    $nw-design       Architecture design with visual representation"
        )
    logger.info("")
    if codex_only:
        logger.info("  ⚠️  Quit and reopen Codex to load the new agents and skills.")
        logger.info(
            "  💡 Open Codex in any project directory and invoke the $nw-design skill."
        )
    elif mixed_hosts:
        logger.info(
            "  ⚠️  Quit and reopen Claude Code to load the new agents, skills, and commands."
        )
        logger.info("  ⚠️  Quit and reopen Codex to load the new agents and skills.")
        logger.info("  💡 Start with /nw-design in Claude Code or $nw-design in Codex.")
    else:
        logger.info(
            "  ⚠️  Quit and reopen Claude Code to load the new agents, skills, and commands."
        )
        logger.info(
            "  💡 Open Claude Code in any project directory and type a /nw- command."
        )
    logger.info("  📚 Docs: https://github.com/nWave-ai/nWave")


def show_help():
    """Show help message."""
    B, N = _ANSI_BLUE, _ANSI_NC

    print()
    for line in _LOGO_ART[:-1]:
        print(f"{B}{line}{N}")
    print(f"{B}{_LOGO_ART[-1]}{N}  \U0001f30a \U0001f30a \U0001f30a  v{__version__}")
    print()
    for tagline in _TAGLINES:
        print(tagline)

    help_text = f"""
{B}DESCRIPTION:{N}
    Installs the nWave methodology framework to your global Claude config directory.
    This makes all specialized agents and commands available across all projects.

{B}USAGE:{N}
    python install_nwave.py [OPTIONS]

{B}OPTIONS:{N}
    --backup-only     Create backup of existing nWave installation without installing
    --restore         Restore from the most recent backup
    --dry-run         Show what would be installed without making any changes.
                      Also surfaces Codex ownership-collision refusals safely,
                      before a real install -- run this first if unsure.
    --dev             Install ALL agents and skills (including private/unreleased)
    --adopt-legacy-codex-dev
                      With --dev --platform codex only, quarantine safely
                      backed-up legacy unmanifested Codex nWave assets
    --help            Show this help message

{B}EXAMPLES:{N}
    python install_nwave.py                    # Install nWave framework
    python install_nwave.py --dry-run          # Show what would be installed
    python install_nwave.py --backup-only      # Create backup only
    python install_nwave.py --restore          # Restore from latest backup

{B}WHAT GETS INSTALLED:{N}
    - nWave specialized agents (DISCOVER\u2192DISCUSS\u2192DESIGN\u2192DEVOP\u2192DISTILL\u2192DELIVER methodology)
    - nWave command interface for workflow orchestration
    - ATDD (Acceptance Test Driven Development) integration
    - Outside-In TDD with double-loop architecture
    - Quality validation network with continuous refactoring
    - 7-phase TDD enforcement with schema versioning

{B}INSTALLATION LOCATION:{N}
    ~/.claude/agents/nw/    # nWave agent specifications
    ~/.claude/commands/nw/  # nWave command integrations
    ~/.claude/templates/    # TDD cycle schema templates

For more information: https://github.com/nWave-ai/nWave
"""
    print(help_text)


def _resolve_platform_override(platform_flag: str) -> set[str] | None:
    """Resolve CLI --platform flag to a platform override set.

    Args:
        platform_flag: One of "auto", "claude-code", "opencode", "codex",
            "copilot", "all".

    Returns:
        None for auto-detect, or a set of platform string values.
    """
    platform_map = {
        "auto": None,
        "claude-code": {"claude_code"},
        "opencode": {"opencode"},
        "codex": {"codex"},
        "copilot": {"copilot"},
        "all": {"claude_code", "opencode", "codex", "copilot"},
    }
    return platform_map[platform_flag]


def main():
    """Main entry point."""
    _force_utf8_console()
    parser = argparse.ArgumentParser(
        description="Install nWave framework", add_help=False
    )
    parser.add_argument("--backup-only", action="store_true", help="Create backup only")
    parser.add_argument("--restore", action="store_true", help="Restore from backup")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done"
    )
    parser.add_argument("--help", "-h", action="store_true", help="Show help")
    parser.add_argument(
        "--platform",
        choices=["auto", "claude-code", "opencode", "codex", "copilot", "all"],
        default="auto",
        help="Target platform (default: auto-detect)",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Install ALL agents and skills (not just public). For local dev only.",
    )
    parser.add_argument(
        "--adopt-legacy-codex-dev",
        action="store_true",
        help=(
            "With --dev --platform codex only: quarantine legacy unmanifested "
            "Codex nWave dev assets in the normal nWave backup before installing."
        ),
    )

    args = parser.parse_args()

    if args.help:
        show_help()
        return 0

    if args.adopt_legacy_codex_dev and not (args.dev and args.platform == "codex"):
        parser.error("--adopt-legacy-codex-dev requires --dev --platform codex")

    # Resolve platform override from CLI flag
    platform_override = _resolve_platform_override(args.platform)

    installer = NWaveInstaller(
        dry_run=args.dry_run,
        platform_override=platform_override,
        dev_mode=args.dev,
        adopt_legacy_codex_dev=args.adopt_legacy_codex_dev,
    )

    # Codex has no Claude backup or restore surface.  Keep its explicit
    # restore command a no-op without consulting any retired runtime state.
    if args.restore and installer.effective_target_platforms == {"codex"}:
        return 0

    # Show title panel at startup
    show_title_panel(installer.logger, dry_run=args.dry_run)

    # Run preflight checks BEFORE any build or installation actions
    preflight = PreflightChecker()
    preflight_results = preflight.run_all_checks()

    # Display preflight results in TUI format
    installer.logger.info("  \U0001f50d Pre-flight checks")
    for result in preflight_results:
        if result.passed:
            installer.logger.info(f"  \u2705 {result.message}")
        else:
            installer.logger.error(f"  \u274c {result.message}")

    if preflight.has_blocking_failures(preflight_results):
        for failed_check in preflight.get_failed_checks(preflight_results):
            error_message = format_error(
                error_code=failed_check.error_code,
                message=failed_check.message,
                remediation=failed_check.remediation or "No remediation available.",
                recoverable=False,
            )
            installer.logger.error(error_message)
        return 1

    installer.logger.info("  \u2705 Pre-flight passed")
    installer.logger.info("")

    if args.dry_run:
        installer.logger.warn("  🚨 DRY RUN MODE - No changes will be made")

    # Handle backup-only mode
    if args.backup_only:
        # A native-only target (Codex, Copilot, OpenCode, or any combination
        # of them without Claude) has no Claude backup surface at all -- do
        # not enable Claude install logging or touch claude_config_dir for it.
        if "claude_code" not in installer.effective_target_platforms:
            return 0
        installer.enable_install_logging()
        installer.create_backup()
        installer.logger.info("  🍾 Backup completed successfully")
        return 0

    # Handle restore mode
    if args.restore:
        if installer.restore_backup():
            installer.logger.info("  🍾 Restoration completed successfully")
            return 0
        else:
            return 1

    # Normal installation
    # validate_codex_ownership_preflight already emits a full WHAT/WHY/HOW
    # report plus a "0 files written" verdict line for every collision when
    # it refuses (see _report_ownership_preflight_errors) -- no separate
    # generic message here, or the operator sees a redundant, less useful
    # second verdict on top of the specific one.
    if not installer.validate_codex_ownership_preflight():
        return 1

    if args.dry_run:
        return 0 if installer.install_framework() else 1

    # A native-only target (Codex, Copilot, OpenCode, or any combination of
    # them without Claude) has no Claude activation surface -- persistent
    # install logging must never create or write under claude_config_dir for
    # it. create_backup() is safe to call unconditionally: its Codex branch
    # never touches claude_config_dir, and its default (Claude) branch is a
    # no-op unless a prior Claude installation already exists on disk.
    if "claude_code" in installer.effective_target_platforms:
        installer.enable_install_logging()
    installer.create_backup()

    if not installer.adopt_legacy_codex_dev_assets():
        return 1

    if not installer.install_framework():
        return 1

    # Create manifest after installation but before validation
    # This prevents circular dependency where validation fails because
    # manifest doesn't exist yet. Only "claude_code" targets get a Claude
    # discovery surface (claude_config_dir) for the manifest to live in --
    # a native-only target (single or combined) must not create one.
    if "claude_code" in installer.effective_target_platforms:
        installer.create_manifest()

    # Dry-run preview: install_framework + create_manifest already returned
    # without side effects (each plugin honors context.dry_run). Skip the
    # post-install verifier — it asserts real installation state which by
    # definition does not exist in a dry-run preview. Fix for v1.1.14+
    # regression where --dry-run exited 1 with "DES config not found".
    if installer.dry_run:
        installer.logger.info("")
        installer.logger.info(
            "  🍾 Dry-run preview complete (no changes made, verifier skipped)"
        )
        return 0

    if installer.validate_installation():
        # Record install provenance (machine-scoped ~/.nwave, like update-check
        # state) so the doctor VersionSyncCheck can later detect a package
        # upgraded without re-running install. Best-effort; never fails the run.
        #
        # Known limitation: the record is keyed to the machine, NOT the install
        # target. A `--target` install shares this single ~/.nwave record with
        # the default install, so maintaining two targets backed by different
        # venvs could surface a spurious drift warning on the target not last
        # installed. Single-target is the norm; left as-is deliberately.
        installed_version = _detect_installed_version()
        if installed_version is not None:
            record_install_metadata(
                Path.home() / ".nwave" / "global-config.json",
                installed_version=installed_version,
                package_manager=_detect_package_manager(),
            )

        installer.logger.info("")
        show_installation_summary(
            installer.logger,
            installer.claude_config_dir,
            target_platforms=installer.effective_target_platforms,
        )

        return 0
    else:
        installer.logger.error("  ❌ Installation failed validation")
        installer.logger.warn("  ⚠️ Restore with: python install_nwave.py --restore")
        return 1


if __name__ == "__main__":
    sys.exit(main())
