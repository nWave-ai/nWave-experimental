"""
Regression: Claude ``skills/`` must survive backup -> upgrade replacement -> restore.

Bug: ``BackupManager.create_backup`` (scripts/install/install_utils.py) only
snapshots ``agents/`` and ``commands/``; it ignores ``skills/`` entirely, and
skips backup creation altogether when a Claude install has ONLY skills (no
agents/commands dirs exist). ``NWaveInstaller.restore_backup``
(scripts/install/install_nwave.py) mirrors the gap: it never restores
``skills/`` even when a snapshot happens to contain one.

These tests drive the real filesystem: a distributed ``SKILL.md`` is
customized by a user, "upgraded" (simulated by an overwrite matching what a
new install_framework pass would do), then restored from the backup taken
before the overwrite -- the customization must come back byte-for-byte.

Isolation: CLAUDE_CONFIG_DIR is monkeypatched per test (no real HOME touched);
NWAVE_AGENTS_HOME/NWAVE_PROJECT_ROOT are set by the session-scoped
``isolate_install_lock_destination`` fixture in tests/installer/conftest.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _make_skill(claude_dir: Path, name: str, content: str) -> Path:
    skill_dir = claude_dir / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(content, encoding="utf-8")
    return skill_md


class TestBackupManagerCapturesSkills:
    """scripts/install/install_utils.py BackupManager.create_backup."""

    def test_create_backup_snapshots_skills_directory(self, tmp_path, monkeypatch):
        """GIVEN a Claude install with agents, commands AND skills
        WHEN create_backup runs
        THEN the skills directory (including SKILL.md bytes) is captured too.
        """
        from scripts.install.install_utils import BackupManager, Logger

        claude_dir = tmp_path / ".claude"
        (claude_dir / "agents").mkdir(parents=True)
        (claude_dir / "agents" / "a.md").write_text("agent", encoding="utf-8")
        (claude_dir / "commands").mkdir(parents=True)
        original = "# nw-example\noriginal body\n"
        _make_skill(claude_dir, "nw-example", original)

        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_dir))

        manager = BackupManager(Logger(log_file=None), backup_type="install")
        backup_dir = manager.create_backup()

        assert backup_dir is not None
        backed_up_skill = backup_dir / "skills" / "nw-example" / "SKILL.md"
        assert backed_up_skill.exists(), (
            f"BackupManager.create_backup must snapshot skills/; "
            f"missing {backed_up_skill}"
        )
        assert backed_up_skill.read_text(encoding="utf-8") == original

    def test_create_backup_runs_for_skills_only_install(self, tmp_path, monkeypatch):
        """GIVEN a Claude install with ONLY a skills directory (no agents/commands)
        WHEN create_backup runs
        THEN a backup is still created (not skipped) and the skill is captured.
        """
        from scripts.install.install_utils import BackupManager, Logger

        claude_dir = tmp_path / ".claude"
        content = "# nw-solo\nbody\n"
        _make_skill(claude_dir, "nw-solo", content)

        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_dir))

        manager = BackupManager(Logger(log_file=None), backup_type="install")
        backup_dir = manager.create_backup()

        assert backup_dir is not None, (
            "create_backup must not skip when only skills/ exists "
            "(current code only checks agents_dir/commands_dir existence)"
        )
        backed_up_skill = backup_dir / "skills" / "nw-solo" / "SKILL.md"
        assert backed_up_skill.exists()
        assert backed_up_skill.read_text(encoding="utf-8") == content

    def test_create_backup_dry_run_does_not_touch_filesystem(
        self, tmp_path, monkeypatch
    ):
        """dry_run must remain non-mutating even with a skills-only source."""
        from scripts.install.install_utils import BackupManager, Logger

        claude_dir = tmp_path / ".claude"
        _make_skill(claude_dir, "nw-solo", "# nw-solo\nbody\n")

        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_dir))

        manager = BackupManager(Logger(log_file=None), backup_type="install")
        result = manager.create_backup(dry_run=True)

        assert result is None
        assert not manager.backup_dir.exists()


class TestRestoreBackupRestoresSkills:
    """scripts/install/install_nwave.py NWaveInstaller.restore_backup."""

    def test_upgrade_replacement_then_restore_recovers_customized_skill(
        self, tmp_path, monkeypatch
    ):
        """GIVEN a distributed SKILL.md customized by the user
        AND a backup was taken before an upgrade overwrote it
        WHEN restore_backup runs after the simulated upgrade
        THEN the customization is recovered byte-for-byte (before/after hashes match).
        """
        from scripts.install.install_nwave import NWaveInstaller
        from scripts.install.install_utils import BackupManager, Logger

        claude_dir = tmp_path / ".claude"
        (claude_dir / "agents").mkdir(parents=True)
        (claude_dir / "agents" / "a.md").write_text("agent", encoding="utf-8")
        customized = "# nw-example\ncustomized-by-user\n"
        skill_md = _make_skill(claude_dir, "nw-example", customized)

        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_dir))

        # Backup BEFORE the simulated upgrade (mirrors _run_install ordering:
        # create_backup runs before install_framework).
        manager = BackupManager(Logger(log_file=None), backup_type="install")
        backup_dir = manager.create_backup()
        assert backup_dir is not None

        # Simulate upgrade: a fresh install_framework pass overwrites SKILL.md
        # with the distributed (non-customized) content.
        skill_md.write_text("# nw-example\ndistributed-default\n", encoding="utf-8")
        assert skill_md.read_text(encoding="utf-8") != customized

        installer = NWaveInstaller(platform_override={"claude_code"})
        restored = installer.restore_backup()

        assert restored is True
        assert skill_md.read_text(encoding="utf-8") == customized, (
            "restore_backup must restore skills/ bytes; the customized "
            "SKILL.md must survive backup -> upgrade -> restore"
        )

    def test_restore_from_legacy_backup_without_skills_preserves_current_skills(
        self, tmp_path, monkeypatch
    ):
        """GIVEN a legacy backup that predates skills/ capture (agents/commands only)
        WHEN restore_backup restores from it
        THEN currently-installed skills are left in place, not deleted.
        """
        from scripts.install.install_nwave import NWaveInstaller
        from scripts.install.install_utils import Logger

        claude_dir = tmp_path / ".claude"
        (claude_dir / "agents").mkdir(parents=True)
        (claude_dir / "agents" / "a.md").write_text("agent", encoding="utf-8")
        current = "# nw-current\npresent-after-restore\n"
        skill_md = _make_skill(claude_dir, "nw-current", current)

        # Hand-craft a legacy backup dir (agents/commands only, no skills/) —
        # exactly what BackupManager produced before this fix.
        legacy_backup = claude_dir / "backups" / "nwave-install-20200101-000000"
        (legacy_backup / "agents").mkdir(parents=True)
        (legacy_backup / "agents" / "a.md").write_text("old-agent", encoding="utf-8")

        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_dir))
        Logger(log_file=None)  # not used directly; NWaveInstaller builds its own

        installer = NWaveInstaller(platform_override={"claude_code"})
        restored = installer.restore_backup()

        assert restored is True
        assert skill_md.exists(), (
            "restoring a legacy backup with no skills/ must not delete the "
            "currently-installed skill"
        )
        assert skill_md.read_text(encoding="utf-8") == current

    def test_restore_preserves_skill_absent_from_backup_snapshot(
        self, tmp_path, monkeypatch
    ):
        """GIVEN a backup snapshot that has ONE skill
        AND the current install has a SECOND skill added after the backup
        WHEN restore_backup runs
        THEN the independently-added second skill survives (overlay, not
             blanket delete of skills/ before restore).
        """
        from scripts.install.install_nwave import NWaveInstaller
        from scripts.install.install_utils import BackupManager, Logger

        claude_dir = tmp_path / ".claude"
        (claude_dir / "agents").mkdir(parents=True)
        (claude_dir / "agents" / "a.md").write_text("agent", encoding="utf-8")
        snapshot_content = "# nw-snapshot\nsnapshotted\n"
        _make_skill(claude_dir, "nw-snapshot", snapshot_content)

        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_dir))

        manager = BackupManager(Logger(log_file=None), backup_type="install")
        backup_dir = manager.create_backup()
        assert backup_dir is not None
        assert (backup_dir / "skills" / "nw-snapshot" / "SKILL.md").exists()

        # Independently added AFTER the backup was taken — absent from the
        # snapshot entirely.
        later_content = "# nw-added-later\nadded-after-backup\n"
        later_skill_md = _make_skill(claude_dir, "nw-added-later", later_content)

        installer = NWaveInstaller(platform_override={"claude_code"})
        restored = installer.restore_backup()

        assert restored is True
        assert later_skill_md.exists(), (
            "a skill independently added after the backup snapshot must "
            "survive restore (overlay semantics, not a blanket skills/ delete)"
        )
        assert later_skill_md.read_text(encoding="utf-8") == later_content

    @pytest.mark.parametrize("dry_run", [True])
    def test_restore_backup_reachable_target_is_unaffected_by_dry_run_create(
        self, tmp_path, monkeypatch, dry_run
    ):
        """dry_run create_backup must remain non-mutating for skills too."""
        from scripts.install.install_utils import BackupManager, Logger

        claude_dir = tmp_path / ".claude"
        _make_skill(claude_dir, "nw-example", "# nw-example\nbody\n")

        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_dir))

        manager = BackupManager(Logger(log_file=None), backup_type="install")
        result = manager.create_backup(dry_run=dry_run)

        assert result is None
        assert not (claude_dir / "backups").exists()
