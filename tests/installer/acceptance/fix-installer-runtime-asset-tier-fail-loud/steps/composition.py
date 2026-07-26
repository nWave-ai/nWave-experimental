"""Composition root for the runtime-asset-tier fail-loud acceptance test.

Drives the REAL production method ``DESPlugin._install_nwave_runtime_assets``
(scripts/install/plugins/des_plugin.py) -- the plugin step that ships the
nWave runtime asset tier to ``<claude_dir>/lib/nWave/``, which is where the
installed package resolves it. Real filesystem under ``tmp_path`` (Pillar 3);
nothing about the method itself is mocked.

The "dropped family" scenario patches only ``shutil.copytree`` as seen by the
production module -- the stdlib driven boundary -- to simulate an
environmental partial copy (a permission race, a disk hiccup). It never
touches the method's own post-copy verification, which is exactly what that
scenario exists to exercise.

All scenario business logic (seeding, the plugin invocation, oracle
assertions) lives HERE as the single source of truth; step bodies in
``test_runtime_asset_tier_fail_loud.py`` delegate one call each
(SSOT-via-Types-Services-DSL mandate, criterion 3).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.des_plugin import DESPlugin, RuntimeAssetShippingError

from .domain_types import AssetFamilyName, ShippingOutcome


#: Captured BEFORE any patch call can shadow it -- `patch(
#: "scripts.install.plugins.des_plugin.shutil.copytree", ...)` mutates the
#: `copytree` attribute on the shared stdlib `shutil` module object itself
#: (module singletons), so calling `shutil.copytree` from inside the very
#: side_effect that replaced it would recurse into itself forever. Bind the
#: real implementation once, here, and call THAT.
_REAL_COPYTREE = shutil.copytree


class RuntimeAssetShippingJourney:
    """One real-filesystem invocation of ``_install_nwave_runtime_assets``."""

    def __init__(self, tmp_path: Path) -> None:
        self._tmp = tmp_path
        self._framework_source = tmp_path / "nWave"
        self._claude_dir = tmp_path / ".claude"
        self._target_root = self._claude_dir / "lib" / "nWave"
        self._outcome: ShippingOutcome | None = None
        self._refusal: str = ""
        self._dropped_family: str | None = None
        self._using_prebuilt = False

    # -- Given ---------------------------------------------------------------

    def prepare_isolated_target(self) -> None:
        self._framework_source.mkdir(parents=True, exist_ok=True)
        self._claude_dir.mkdir(parents=True, exist_ok=True)

    def seed_declared_nwave_tier(
        self, *, without: AssetFamilyName | None = None
    ) -> None:
        """Seed a source tree carrying the DECLARED families and the catalogue.

        Derived from the plugin's own declarations rather than a hand-copied
        list, so a family added to `_NWAVE_RUNTIME_ASSET_DIRS` is seeded here
        without an edit -- the guard tracks the contract instead of a snapshot
        of it.
        """
        for family in DESPlugin._NWAVE_RUNTIME_ASSET_DIRS:
            if family == without:
                continue
            family_dir = self._framework_source / family
            family_dir.mkdir(parents=True, exist_ok=True)
            (family_dir / "asset.yaml").write_text(f"# {family}\n")
        # The DECLARED FACT that marks this tree an nWave source tier.
        for filename in DESPlugin._NWAVE_RUNTIME_ASSET_FILES:
            (self._framework_source / filename).write_text("agents: []\n")

    def seed_declared_tier_with_no_asset_family(self) -> None:
        """Seed the catalogue alone -- the shape a channel gap actually leaves.

        A tree that announces itself an nWave tier and carries not one asset
        family is a broken distribution, as opposed to a tier that merely
        lacks one family (which varies legitimately by channel and era).
        """
        for filename in DESPlugin._NWAVE_RUNTIME_ASSET_FILES:
            (self._framework_source / filename).write_text("agents: []\n")

    def seed_target_without_nwave_tier(self) -> None:
        """Seed the shape of a legitimate external target.

        Scripts and templates only -- no catalogue, so nothing declares this
        tree an nWave source tier. This is the shape the target-machine-
        agnosticism mandate calls valid, and the shape the installer's own
        acceptance fixtures fabricate.
        """
        (self._framework_source / "scripts" / "des").mkdir(parents=True, exist_ok=True)
        (self._framework_source / "templates").mkdir(parents=True, exist_ok=True)

    def drop_family_during_copy(self, name: AssetFamilyName) -> None:
        self._dropped_family = name

    def ship_from_prebuilt_distribution(self) -> None:
        self._using_prebuilt = True

    # -- When ----------------------------------------------------------------

    def ship_runtime_assets(self) -> None:
        context = InstallContext(
            claude_dir=self._claude_dir,
            scripts_dir=Path("scripts/install"),
            templates_dir=self._framework_source / "templates",
            logger=_RecordingLogger(),
            project_root=self._tmp,
            framework_source=self._framework_source,
            dry_run=False,
            dev_mode=True,
        )
        try:
            if self._dropped_family is not None:
                with patch(
                    "scripts.install.plugins.des_plugin.shutil.copytree",
                    side_effect=self._copytree_then_drop,
                ):
                    shipped = DESPlugin()._install_nwave_runtime_assets(
                        context=context, using_prebuilt=self._using_prebuilt
                    )
            else:
                shipped = DESPlugin()._install_nwave_runtime_assets(
                    context=context, using_prebuilt=self._using_prebuilt
                )
        except RuntimeAssetShippingError as exc:
            self._outcome = ShippingOutcome.REFUSED
            self._refusal = str(exc)
        else:
            self._outcome = (
                ShippingOutcome.SHIPPED
                if shipped is not None
                else ShippingOutcome.NOT_APPLICABLE
            )

    def _copytree_then_drop(self, source, dest, *args, **kwargs):
        """Real copy, then remove the one family this scenario simulates losing.

        Models an environmental partial-copy failure (permission race, disk
        hiccup) that ``shutil.copytree`` itself would not raise on -- the
        exact gap the method's post-copy per-ENTRY check exists to catch, as
        opposed to trusting the weak signal "copytree did not raise".

        cpython's ``shutil.copytree`` recurses into subdirectories by calling
        the module-level ``copytree`` name again (not a private helper), so
        patching it also intercepts that recursive descent with a variable,
        positional-heavy signature. Forward everything through unchanged, and
        drop only when the destination IS the dropped family's own directory.
        """
        _REAL_COPYTREE(source, dest, *args, **kwargs)
        if Path(dest) == self._target_root / self._dropped_family:
            shutil.rmtree(dest, ignore_errors=True)

    # -- Then ----------------------------------------------------------------

    def assert_outcome(self, expected: ShippingOutcome) -> None:
        actual = self._require_outcome()
        assert actual is expected, (
            f"expected the shipping outcome to be {expected.value!r}, got "
            f"{actual.value!r}. The defect this guard closes is precisely the "
            "collapse of 'not applicable' and 'refused' onto one silent "
            f"result. refusal={self._refusal!r}"
        )

    def assert_every_declared_family_at_destination(self) -> None:
        missing = [
            family
            for family in DESPlugin._NWAVE_RUNTIME_ASSET_DIRS
            if not (self._target_root / family).is_dir()
        ]
        assert not missing, (
            f"declared asset families missing at the destination after a "
            f"reported-shipped install: {missing} -- destination "
            f"{self._target_root}"
        )

    def assert_destination_carries_family(self, name: AssetFamilyName) -> None:
        target = self._target_root / name
        assert target.is_dir(), (
            f"expected the destination to carry the {name!r} family -- the "
            "family whose absence was misdiagnosed as never-shipped; not "
            f"found at {target}"
        )

    def assert_refusal_names_family(self, name: AssetFamilyName) -> None:
        assert name in self._refusal, (
            f"a refusal that does not NAME the missing family {name!r} is "
            "itself the defect this guard closes (a bare failure gives the "
            f"reader nothing to act on). Actual refusal={self._refusal!r}"
        )

    def assert_refusal_explains_what_why_how(self) -> None:
        for marker in ("WHAT:", "WHY:", "HOW:"):
            assert marker in self._refusal, (
                f"a refusal missing {marker!r} gives the reader nothing to "
                "diagnose or act on -- that is itself the defect this guard "
                f"closes. Actual refusal={self._refusal!r}"
            )

    def assert_refusal_names_the_channel(self) -> None:
        """The channel is the actionable half of the HOW.

        Three channels ship three different layouts (dev checkout, flat
        `dist/` tarball, nested pipx wheel), so "assets missing" without the
        channel leaves the reader to work out WHICH tree to rebuild.
        """
        assert "wheel" in self._refusal or "tarball" in self._refusal, (
            "the refusal must name the distribution channel whose tree needs "
            f"rebuilding. Actual refusal={self._refusal!r}"
        )

    def assert_install_not_refused(self) -> None:
        actual = self._require_outcome()
        assert actual is not ShippingOutcome.REFUSED, (
            "a target that legitimately carries no nWave tier must NOT be "
            "refused -- the target-machine-agnosticism mandate makes that "
            f"shape valid. refusal={self._refusal!r}"
        )

    # -- internals -----------------------------------------------------------

    def _require_outcome(self) -> ShippingOutcome:
        assert self._outcome is not None, (
            "test setup error: ship_runtime_assets() was never invoked before "
            "an assertion ran"
        )
        return self._outcome


class _RecordingLogger:
    """Minimal logger double -- the production method logs, it does not query."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def info(self, message: str) -> None:
        self.messages.append(message)

    def warning(self, message: str) -> None:
        self.messages.append(message)

    def error(self, message: str) -> None:
        self.messages.append(message)
