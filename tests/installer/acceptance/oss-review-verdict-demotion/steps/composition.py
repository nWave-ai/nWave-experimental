"""Composition root for the oss-review-verdict-demotion S5 installer set.

Drives the PRODUCTION install surface through two composition-root driving
ports (Mandate 13, Layer 3):

  * `NWaveInstaller._create_plugin_registry(...)` -- the production
    composition root that wires the install plugins. The registered-plugin
    set + count is read off the returned `PluginRegistry.plugins` dict. This
    is the seam the install pipeline itself uses (`install_framework` calls
    the same `_create_plugin_registry`); reading its product is reading the
    real registry the operator gets, not a hand-rebuilt one (Pillar 3).

  * `scripts/install/install_nwave.py` invoked as a real Python subprocess
    against a tmp_path target -- the full install pipeline. Used to prove
    end-to-end that a fresh install provisions NO signing key and that a
    PRE-EXISTING operator key file survives byte-identical (preserve-by-
    default).

Business logic -- building the registry observation, the subprocess
invocation, capturing the key-slot surface -- lives here as the single
source of truth; step bodies delegate to `InstallerDemotionFixture` methods
and never inline logic (Mandate-12 criterion 3).

RED-for-the-right-reason (at tip, before S5 lands):
  * the registry surface still carries `reviewer_signing` (count 8) -- the
    "registry registers 7, no signing plugin" assertions raise AssertionError;
  * the fresh keyless install still provisions a key file -- the "no key
    provisioned" assertion raises AssertionError;
  * the preserve-by-default leg is bound to the registry observation in the
    walking-skeleton scenario, so it too is RED at tip (the registry still
    carries the signing plugin) -- it is NOT a standalone always-green guard.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .domain_types import (
    DEMOTED_PLUGIN_NAME,
    EXPECTED_CLAUDE_PLUGIN_COUNT,
    KEY_RELPATH,
    SIGNING_KEY_ENV,
    RegistrySurface,
    TargetKeyObservation,
)


@dataclass(frozen=True)
class InstallRunResult:
    """Outcome of running the production registry against the tmp target.

    `tolerated_plugin_failures` names the registered plugins whose `install`
    raised against the minimal target context (non-signing plugins needing a
    framework source). Their failure is irrelevant to the signing-key
    contract -- they cannot create a key; the key-slot is the oracle.
    """

    tolerated_plugin_failures: tuple[str, ...]


class _NullLogger:
    """A no-op logger satisfying the InstallContext logger surface.

    The registry/plugins call `logger.error/.info/...`; we swallow them so a
    tolerated non-signing plugin failure does not crash the probe before the
    signing plugin is reached.
    """

    def __getattr__(self, _name: str):
        def _noop(*_args: object, **_kwargs: object) -> None:
            return None

        return _noop


class InstallerDemotionFixture:
    """Drives the production install surface for the S5 demotion contract.

    Each instance is bound to one tmp_path target tree. It exposes the
    composition methods step bodies invoke; no business logic is inlined in
    any step.
    """

    def __init__(self, target_root: Path) -> None:
        self._target_root = target_root
        self._target_root.mkdir(parents=True, exist_ok=True)

    # --- target arrange ----------------------------------------------------

    def _key_file(self) -> Path:
        return self._target_root / KEY_RELPATH

    def provision_preexisting_user_key(self, content: bytes) -> None:
        """Place a pre-existing operator key file on the target.

        Models the user who already has `.nwave/secrets/reviewer-signing.key`
        from a prior nWave version. Preserve-by-default: the demoted installer
        must leave this byte-identical.
        """
        key_file = self._key_file()
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_bytes(content)

    def clear_signing_key_env(self) -> None:
        """Scrub NWAVE_REVIEWER_SIGNING_KEY from the process environment.

        The demoted installer never reads it; we scrub so the keyless install
        path is exercised with no override in play.
        """
        os.environ.pop(SIGNING_KEY_ENV, None)

    # --- driving port 1: production registry composition root --------------

    def capture_production_registry(self) -> RegistrySurface:
        """Read the registered plugins off the production composition root.

        Builds the real `NWaveInstaller` and calls its production
        `_create_plugin_registry` (the SAME seam `install_framework` uses),
        for the default Claude-Code platform. Reading `registry.plugins`
        gives the operator-observable registered-plugin set.
        """
        from scripts.install.install_nwave import NWaveInstaller

        installer = NWaveInstaller(platform_override={"claude_code"})
        registry = installer._create_plugin_registry(
            silent=True, target_platforms={"claude_code"}
        )
        names = tuple(registry.plugins.keys())
        return RegistrySurface(plugin_names=names, count=len(names))

    # --- driving port 2: production registry install against tmp target ----

    def run_registry_install_against_target(self) -> InstallRunResult:
        """Run the production registry's plugins against the tmp target.

        Drives the SAME production composition root the operator gets
        (`NWaveInstaller._create_plugin_registry`) and invokes each registered
        plugin's real `install(context)` against an `InstallContext` rooted at
        the tmp target -- a live install, NOT dry-run (dry-run is vacuous for
        the key contract: every plugin honors `context.dry_run` and writes
        nothing, so a dry-run would pass even at tip while the signing plugin
        is still registered).

        The signing-key slot is the oracle. Non-signing plugins that need a
        framework source (agents/skills/des) raise against this minimal
        target context; their failure is tolerated -- they cannot create a
        signing key, and the contract under test is "no registered plugin
        provisions a key". At tip the registered `reviewer_signing` plugin
        DOES write the key (RED); post-demotion it is absent (green).

        The signing plugin has no dependency on a framework source, so it runs
        regardless of where it falls in the order -- the tolerate-and-continue
        loop guarantees it is reached.
        """
        from scripts.install.install_nwave import NWaveInstaller
        from scripts.install.plugins.base import InstallContext

        os.environ.pop(SIGNING_KEY_ENV, None)
        installer = NWaveInstaller(platform_override={"claude_code"})
        registry = installer._create_plugin_registry(
            silent=True, target_platforms={"claude_code"}
        )
        context = InstallContext(
            claude_dir=self._target_root / ".claude",
            scripts_dir=self._target_root / "scripts",
            templates_dir=self._target_root / "templates",
            logger=_NullLogger(),
            project_root=self._target_root,
        )
        tolerated: list[str] = []
        for name, plugin in registry.plugins.items():
            try:
                plugin.install(context)
            except Exception:
                # a real framework source; their failure cannot create a key
                # and the key-slot oracle is what we assert on.
                tolerated.append(name)
        return InstallRunResult(tolerated_plugin_failures=tuple(tolerated))

    # --- capture -----------------------------------------------------------

    def capture_key_slot(self) -> TargetKeyObservation:
        """Capture the target's signing-key slot state."""
        key_file = self._key_file()
        exists = key_file.is_file()
        return TargetKeyObservation(
            key_file_exists=exists,
            key_file_bytes=key_file.read_bytes() if exists else None,
        )

    # --- assert (the demotion contract) ------------------------------------

    @staticmethod
    def assert_registry_demoted(surface: RegistrySurface) -> None:
        """The production registry registers 7 plugins, none being signing.

        RED at tip: today the registry carries `reviewer_signing` (count 8).
        """
        assert DEMOTED_PLUGIN_NAME not in surface.plugin_names, (
            "The demoted install registry MUST NOT register the "
            f"{DEMOTED_PLUGIN_NAME!r} plugin; observed {surface.plugin_names!r}."
        )

        assert surface.count == EXPECTED_CLAUDE_PLUGIN_COUNT, (
            "The demoted Claude-Code install registry MUST honestly register "
            f"{EXPECTED_CLAUDE_PLUGIN_COUNT} plugins; observed {surface.count} "
            f"({surface.plugin_names!r})."
        )

    @staticmethod
    def assert_install_clean_and_keyless(
        result: InstallRunResult,
        key_slot: TargetKeyObservation,
    ) -> None:
        """Install runs without a signing plugin and provisions NO key file.

        The demoted registry MUST NOT register a key-provisioning plugin, so
        running its plugin set against a fresh keyless target leaves the
        signing-key slot empty. RED at tip: the registered `reviewer_signing`
        plugin still writes the key, so `key_file_exists` is True today.

        The signing plugin runs without raising (it needs no framework
        source), so it MUST NOT appear among the tolerated failures -- a
        guard that the probe genuinely reached the signing-provision path
        rather than skipping it.
        """
        assert DEMOTED_PLUGIN_NAME not in result.tolerated_plugin_failures, (
            "The signing plugin must be reachable in the registry probe (it "
            "needs no framework source); its appearance among tolerated "
            "failures would mean the key path was never exercised."
        )
        assert not key_slot.key_file_exists, (
            "The demoted installer MUST provision NO signing key on a fresh "
            f"keyless target; a key file appeared at {KEY_RELPATH}."
        )

    @staticmethod
    def assert_user_key_preserved(
        before: TargetKeyObservation, after: TargetKeyObservation
    ) -> None:
        """A pre-existing operator key survives install byte-identical.

        Preserve-by-default: the demoted installer never reads or deletes the
        user's key file. `before`/`after` straddle the install run.
        """
        assert before.key_file_exists and after.key_file_exists, (
            "Both before and after observations MUST carry the user's key "
            "file -- preserve-by-default forbids deleting it."
        )
        assert before.key_file_bytes == after.key_file_bytes, (
            "The demoted installer MUST leave the operator's pre-existing key "
            "file byte-identical (a user file -- never read, never rewritten)."
        )
