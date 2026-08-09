"""Falsifiers for the templates / utility-scripts / data uninstall gap (Issue 98).

Reuses the same manifest-ownership family mechanism proven for skills
(``remove_family_record`` / ``scan_claude_ownership``) -- no second registry,
no wildcard/prefix ownership.
"""

import pytest

from scripts.install.uninstall_nwave import NWaveUninstaller, scan_claude_ownership
from scripts.shared.skill_distribution import (
    DATA_FAMILY_KEY,
    TEMPLATES_FAMILY_KEY,
    UTILITIES_FAMILY_KEY,
    read_family_record,
    write_family_record,
)


def _fs_snapshot(path):
    return {
        str(p.relative_to(path)): p.read_bytes() if p.is_file() else None
        for p in sorted(path.glob("**/*"))
    }


def _make_uninstaller(tmp_path, monkeypatch, *, dry_run=False):
    config_dir = tmp_path / "claude_config"
    config_dir.mkdir()
    monkeypatch.setattr(
        "scripts.install.uninstall_nwave.PathUtils.get_claude_config_dir",
        lambda: config_dir,
    )
    return config_dir, NWaveUninstaller(dry_run=dry_run)


@pytest.mark.parametrize(
    "subdir,key,remover",
    [
        ("templates", TEMPLATES_FAMILY_KEY, "remove_templates"),
        ("scripts", UTILITIES_FAMILY_KEY, "remove_utility_scripts"),
        ("data", DATA_FAMILY_KEY, "remove_data"),
    ],
)
class TestFamilyRemovalOwnershipSemantics:
    def test_owned_removed_sibling_preserved(
        self, tmp_path, monkeypatch, subdir, key, remover
    ):
        config_dir, uninstaller = _make_uninstaller(tmp_path, monkeypatch)
        target_dir = config_dir / subdir
        target_dir.mkdir()
        (target_dir / "owned.yaml").write_text("owned")
        write_family_record(target_dir, ["owned.yaml"], key=key)
        (target_dir / "user-custom.yaml").write_text("user data")

        getattr(uninstaller, remover)()

        assert not (target_dir / "owned.yaml").exists()
        assert (target_dir / "user-custom.yaml").read_text() == "user data"

    def test_sibling_manifest_key_preserved(
        self, tmp_path, monkeypatch, subdir, key, remover
    ):
        config_dir, uninstaller = _make_uninstaller(tmp_path, monkeypatch)
        target_dir = config_dir / subdir
        target_dir.mkdir()
        (target_dir / "owned.yaml").write_text("owned")
        write_family_record(target_dir, ["owned.yaml"], key=key)
        write_family_record(target_dir, ["sibling-owned.yaml"], key="a_sibling_key")
        (target_dir / "sibling-owned.yaml").write_text("sibling")

        getattr(uninstaller, remover)()

        record = read_family_record(target_dir, key="a_sibling_key")
        assert record.tracked == frozenset({"sibling-owned.yaml"})
        assert (target_dir / "sibling-owned.yaml").exists()

    def test_missing_manifest_never_mutates(
        self, tmp_path, monkeypatch, subdir, key, remover
    ):
        config_dir, uninstaller = _make_uninstaller(tmp_path, monkeypatch)
        target_dir = config_dir / subdir
        target_dir.mkdir()
        (target_dir / "unaccounted.yaml").write_text("unaccounted")
        tree_before = _fs_snapshot(target_dir)

        getattr(uninstaller, remover)()

        assert _fs_snapshot(target_dir) == tree_before

    def test_dry_run_immutable(self, tmp_path, monkeypatch, subdir, key, remover):
        config_dir, uninstaller = _make_uninstaller(tmp_path, monkeypatch, dry_run=True)
        target_dir = config_dir / subdir
        target_dir.mkdir()
        (target_dir / "owned.yaml").write_text("owned")
        write_family_record(target_dir, ["owned.yaml"], key=key)
        tree_before = _fs_snapshot(target_dir)

        getattr(uninstaller, remover)()

        assert _fs_snapshot(target_dir) == tree_before

    def test_second_run_idempotent(self, tmp_path, monkeypatch, subdir, key, remover):
        config_dir, uninstaller = _make_uninstaller(tmp_path, monkeypatch)
        target_dir = config_dir / subdir
        target_dir.mkdir()
        (target_dir / "owned.yaml").write_text("owned")
        write_family_record(target_dir, ["owned.yaml"], key=key)

        getattr(uninstaller, remover)()
        state_after_first = _fs_snapshot(config_dir)

        getattr(uninstaller, remover)()
        assert _fs_snapshot(config_dir) == state_after_first

    def test_blocked_entry_retained_for_retry(
        self, tmp_path, monkeypatch, subdir, key, remover
    ):
        config_dir, uninstaller = _make_uninstaller(tmp_path, monkeypatch)
        target_dir = config_dir / subdir
        target_dir.mkdir()
        write_family_record(target_dir, ["../escape"], key=key)

        getattr(uninstaller, remover)()

        record = read_family_record(target_dir, key=key)
        assert record.tracked == frozenset({"../escape"})


class TestScanClaudeOwnershipExtendedFamilies:
    def test_scan_reports_owned_present_per_family(self, tmp_path):
        config_dir = tmp_path / "claude_config"
        config_dir.mkdir()
        templates_dir = config_dir / "templates"
        templates_dir.mkdir()
        (templates_dir / "owned.yaml").write_text("owned")
        write_family_record(templates_dir, ["owned.yaml"], key=TEMPLATES_FAMILY_KEY)

        inventory = scan_claude_ownership(config_dir)

        assert inventory.templates_owned_present == frozenset({"owned.yaml"})
        assert inventory.utilities_owned_present == frozenset()
        assert inventory.data_owned_present == frozenset()


class TestInstallSideTemplateManifestRoundTrip:
    """TemplatesPlugin, not DESPlugin, owns the manifest key uninstall reads.

    TemplatesPlugin owns the complete installed_templates family (including
    schema files). DESPlugin._install_des_templates copies a partial subset
    of that same target directory but must never write the family record
    itself -- doing so would clobber TemplatesPlugin's complete record with
    a partial one, silently dropping other tracked templates (e.g. schemas)
    from future upgrade/uninstall sweeps. This proves the full round trip:
    TemplatesPlugin's manifest survives a DESPlugin install and uninstall
    still removes everything TemplatesPlugin tracked.
    """

    def test_templates_plugin_manifest_survives_des_install_then_uninstall_removes_it(
        self, tmp_path, monkeypatch
    ):
        from unittest.mock import MagicMock

        from scripts.install.plugins.base import InstallContext
        from scripts.install.plugins.des_plugin import DESPlugin
        from scripts.install.plugins.templates_plugin import TemplatesPlugin

        source_dir = tmp_path / "framework_source" / "templates"
        source_dir.mkdir(parents=True)
        (source_dir / ".pre-commit-config-nwave.yaml").write_text("repos: []\n")

        config_dir, uninstaller = _make_uninstaller(tmp_path, monkeypatch)
        context = InstallContext(
            claude_dir=config_dir,
            scripts_dir=tmp_path / "scripts",
            templates_dir=source_dir,
            logger=MagicMock(),
            project_root=None,
            framework_source=tmp_path / "framework_source",
            target_platforms={"claude_code"},
        )

        templates_result = TemplatesPlugin().install(context)
        assert templates_result.success is True, templates_result.message

        target_dir = config_dir / "templates"
        record_after_templates = read_family_record(
            target_dir, key=TEMPLATES_FAMILY_KEY
        )
        assert record_after_templates.tracked == frozenset(
            {".pre-commit-config-nwave.yaml"}
        )

        des_result = DESPlugin()._install_des_templates(context)
        assert des_result.success is True, des_result.message

        record_after_des = read_family_record(target_dir, key=TEMPLATES_FAMILY_KEY)
        assert record_after_des.tracked == record_after_templates.tracked

        uninstaller.remove_templates()

        assert not (target_dir / ".pre-commit-config-nwave.yaml").exists()
