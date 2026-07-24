"""Composition root for the data-tree-completeness acceptance test.

Drives the REAL production method ``DESPlugin._install_des_data``
(scripts/install/plugins/des_plugin.py) — the plugin step responsible for
propagating ``<framework_source>/data/`` (eight runtime modules read it) to
the operator's ``<claude_dir>/data/`` tree. Real filesystem under
``tmp_path`` (Pillar 3); nothing about the method itself is mocked.

The "dropped entry" scenario patches only ``shutil.copytree`` as seen by the
production module — the stdlib driven boundary — to simulate an
environmental partial copy (a permission race, a disk hiccup). It never
touches ``_install_des_data``'s own post-copy verification logic, which is
exactly what that scenario exists to exercise.

All scenario business logic (seeding, the plugin invocation, oracle
assertions) lives HERE as the single source of truth; step bodies in
``test_data_tree_completeness.py`` delegate one call each
(SSOT-via-Types-Services-DSL mandate, criterion 3).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

from scripts.install.plugins.base import InstallContext, PluginResult
from scripts.install.plugins.des_plugin import DESPlugin

from .domain_types import DataEntryName


#: Captured BEFORE any patch.object call can shadow it -- `patch(
#: "scripts.install.plugins.des_plugin.shutil.copytree", ...)` mutates the
#: `copytree` attribute on the shared stdlib `shutil` module object itself
#: (module singletons), so calling `shutil.copytree` from inside the very
#: side_effect that replaced it would recurse into itself forever. Bind the
#: real implementation once, here, and call THAT.
_REAL_COPYTREE = shutil.copytree


class DataTreeInstallationJourney:
    """One real-filesystem invocation of ``_install_des_data``."""

    #: A representative data shape (not a copy of production's exact content
    #: — decoupled on purpose, so this guard survives nWave/data/ evolving).
    #: Must include the entry the RCA named explicitly (orchestrator-
    #: affordance) since that is the consumer that revealed the defect.
    _DECLARED_ENTRIES: tuple[str, ...] = (
        "orchestrator-affordance",
        "log-persistence-defaults.yaml",
        "dor-items.yaml",
        "omission-classes.json",
    )

    def __init__(self, tmp_path: Path) -> None:
        self._tmp = tmp_path
        self._framework_source = tmp_path / "nWave"
        self._data_source_dir = self._framework_source / "data"
        self._claude_dir = tmp_path / ".claude"
        self._result: PluginResult | None = None
        self._dropped_entry: str | None = None

    # -- Given ---------------------------------------------------------------

    def prepare_isolated_target(self) -> None:
        self._framework_source.mkdir(parents=True, exist_ok=True)
        self._claude_dir.mkdir(parents=True, exist_ok=True)

    def seed_declared_data_entries(self) -> None:
        self._data_source_dir.mkdir(parents=True, exist_ok=True)
        affordance_dir = self._data_source_dir / "orchestrator-affordance"
        affordance_dir.mkdir(parents=True, exist_ok=True)
        (affordance_dir / "catalogue.yaml").write_text("# catalogue\n")
        for name in self._DECLARED_ENTRIES:
            if name == "orchestrator-affordance":
                continue
            (self._data_source_dir / name).write_text("# fixture content\n")

    def ensure_no_data_directory_anywhere(self) -> None:
        # No-op by construction: prepare_isolated_target() never creates a
        # `data/` subdir under framework_source, and project_root (the same
        # tmp base) carries no `nWave/data/` either — the fallback the
        # production method tries also resolves to nothing.
        assert not self._data_source_dir.exists(), (
            "test setup error: the data source dir must NOT exist for this "
            f"scenario — found {self._data_source_dir}"
        )

    def drop_entry_during_copy(self, name: DataEntryName) -> None:
        assert name in self._DECLARED_ENTRIES, (
            f"test setup error: {name!r} is not one of the seeded declared "
            f"entries {self._DECLARED_ENTRIES}"
        )
        self._dropped_entry = name

    # -- When ------------------------------------------------------------------

    def install_data_tree(self) -> None:
        context = InstallContext(
            claude_dir=self._claude_dir,
            scripts_dir=Path("scripts/install"),
            templates_dir=self._framework_source / "templates",
            logger=None,
            project_root=self._tmp,
            framework_source=self._framework_source,
            dry_run=False,
            dev_mode=True,
        )
        if self._dropped_entry is not None:
            with patch(
                "scripts.install.plugins.des_plugin.shutil.copytree",
                side_effect=self._copytree_then_drop,
            ):
                self._result = DESPlugin()._install_des_data(context)
        else:
            self._result = DESPlugin()._install_des_data(context)

    def _copytree_then_drop(self, source, dest, *args, **kwargs):
        """Real copy, then remove the one entry this scenario simulates losing.

        Models an environmental partial-copy failure (permission race, disk
        hiccup) that ``shutil.copytree`` itself would not raise on — the
        exact gap the method's own post-copy STRUCTURED FACT check exists to
        catch, as opposed to trusting the weak signal "copytree did not
        raise".

        cpython's ``shutil.copytree`` recurses into subdirectories by calling
        the module-level ``copytree`` name again (not a private helper), so
        patching ``shutil.copytree`` also intercepts that recursive descent
        with a variable, positional-heavy signature. Accept ``*args,
        **kwargs`` and forward everything through unchanged; only drop the
        simulated entry once the copy has landed at the TOP-level
        destination, never on a recursive per-subdirectory call.
        """
        _REAL_COPYTREE(source, dest, *args, **kwargs)
        if Path(dest) != self._claude_dir / "data":
            return
        dropped = Path(dest) / self._dropped_entry
        if dropped.is_dir():
            shutil.rmtree(dropped)
        elif dropped.exists():
            dropped.unlink()

    # -- Then ------------------------------------------------------------------

    def assert_plugin_reports_success(self) -> None:
        result = self._require_result()
        assert result.success, (
            "expected the plugin to report success when a valid data source "
            f"tree is installed; got success={result.success!r} "
            f"message={result.message!r}"
        )

    def assert_every_declared_entry_at_destination(self) -> None:
        target_dir = self._claude_dir / "data"
        missing = [
            name for name in self._DECLARED_ENTRIES if not (target_dir / name).exists()
        ]
        assert not missing, (
            f"declared data entries missing at the destination after a "
            f"reported-success install: {missing} — destination {target_dir}"
        )

    def assert_destination_carries_entry(self, name: DataEntryName) -> None:
        target = self._claude_dir / "data" / name
        assert target.exists(), (
            f"expected the destination to carry {name!r} (the consumer that "
            f"revealed the defect); not found at {target}"
        )

    def assert_plugin_does_not_report_success(self) -> None:
        result = self._require_result()
        assert result.success is False, (
            "THE DEFECT: the plugin reported success=True while the framework "
            "data tree was not fully deployed — the exact "
            "weak-signal-instead-of-structured-fact failure this guard "
            f"exists to close. message={result.message!r}"
        )

    def assert_failure_names_source_path(self) -> None:
        result = self._require_result()
        assert str(self._data_source_dir) in result.message, (
            "the failure must name the source path it tried, so the operator "
            f"can diagnose it. Tried: {self._data_source_dir}. Actual "
            f"message={result.message!r}"
        )

    def assert_failure_explains_what_why_how(self) -> None:
        result = self._require_result()
        for marker in ("WHAT:", "WHY:", "HOW:"):
            assert marker in result.message, (
                f"a failure missing {marker!r} gives the operator nothing to "
                f"diagnose or act on — that is itself the defect this guard "
                f"closes. Actual message={result.message!r}"
            )

    def assert_failure_names_missing_entry(self, name: DataEntryName) -> None:
        result = self._require_result()
        assert name in result.message, (
            f"a failure that does not NAME the missing entry {name!r} is "
            "itself the defect this guard closes (a bare failure gives the "
            f"operator nothing to act on). Actual message={result.message!r}"
        )

    # -- internals ---------------------------------------------------------

    def _require_result(self) -> PluginResult:
        assert self._result is not None, (
            "test setup error: install_data_tree() was never invoked before "
            "an assertion ran"
        )
        return self._result
