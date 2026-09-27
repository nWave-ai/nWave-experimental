"""
Regression: two adjacent backup/restore mode boundaries.

Bug 1 -- ``NWaveInstaller.restore_backup`` (scripts/install/install_nwave.py)
ignored ``self.dry_run`` entirely: ``--restore --dry-run`` deleted
agents/commands/skills and copied the backup back in, then claimed a real
restoration, even though dry-run must never mutate the filesystem.

Bug 2 -- ``NWaveInstaller.create_backup`` selected ONLY the Codex backup
branch whenever "codex" was among the effective target platforms, so a
combined ``claude_code`` + ``codex`` selection silently skipped the Claude
backup entirely.

Isolation: CLAUDE_CONFIG_DIR is monkeypatched per test (no real HOME
touched); NWAVE_AGENTS_HOME/CODEX_HOME are session-isolated by
tests/conftest.py's ``_isolate_codex_and_agents_home``.
"""

from __future__ import annotations

from pathlib import Path


def _make_claude_install(claude_dir: Path) -> Path:
    (claude_dir / "agents").mkdir(parents=True)
    agent = claude_dir / "agents" / "a.md"
    agent.write_text("agent-original", encoding="utf-8")
    (claude_dir / "commands").mkdir(parents=True)
    (claude_dir / "commands" / "c.md").write_text("command-original", encoding="utf-8")
    return agent


class TestRestoreDryRunDoesNotMutate:
    """restore_backup must honor self.dry_run (Bug 1)."""

    def test_restore_backup_dry_run_leaves_filesystem_untouched(
        self, tmp_path, monkeypatch
    ):
        from scripts.install.install_nwave import NWaveInstaller
        from scripts.install.install_utils import BackupManager, Logger

        claude_dir = tmp_path / ".claude"
        agent = _make_claude_install(claude_dir)
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_dir))

        # Snapshot a backup, then mutate current state past the backup so a
        # (wrongly) real restore would be observable.
        manager = BackupManager(Logger(log_file=None), backup_type="install")
        backup_dir = manager.create_backup()
        assert backup_dir is not None
        agent.write_text("agent-mutated-after-backup", encoding="utf-8")

        installer = NWaveInstaller(dry_run=True, platform_override={"claude_code"})
        result = installer.restore_backup()

        assert result is True
        assert installer.last_restored_from == backup_dir, (
            "dry-run selection must still be observable via last_restored_from"
        )
        assert agent.read_text(encoding="utf-8") == "agent-mutated-after-backup", (
            "restore_backup(dry_run=True) must not overwrite current files"
        )

    def test_run_install_restore_dry_run_does_not_restore(self, tmp_path, monkeypatch):
        """End-to-end through _run_install: --restore --dry-run must be a no-op."""
        import argparse

        from scripts.install.install_nwave import NWaveInstaller, _run_install
        from scripts.install.install_utils import BackupManager, Logger

        claude_dir = tmp_path / ".claude"
        agent = _make_claude_install(claude_dir)
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_dir))

        manager = BackupManager(Logger(log_file=None), backup_type="install")
        backup_dir = manager.create_backup()
        assert backup_dir is not None
        agent.write_text("agent-mutated-after-backup", encoding="utf-8")

        installer = NWaveInstaller(dry_run=True, platform_override={"claude_code"})
        args = argparse.Namespace(dry_run=True, restore=True, backup_only=False)
        exit_code = _run_install(args, installer)

        assert exit_code == 0
        assert agent.read_text(encoding="utf-8") == "agent-mutated-after-backup", (
            "--restore --dry-run must not perform an actual restoration"
        )


class TestCombinedPlatformBackupCoversBothStores:
    """create_backup must snapshot EVERY selected platform (Bug 2)."""

    def test_combined_claude_and_codex_backs_up_both(self, tmp_path, monkeypatch):
        from scripts.install.install_nwave import NWaveInstaller

        claude_dir = tmp_path / ".claude"
        _make_claude_install(claude_dir)
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_dir))

        import os

        agents_home_dir = Path(os.environ["NWAVE_AGENTS_HOME"])
        codex_home_dir = Path(os.environ["CODEX_HOME"])
        skills_dir = agents_home_dir / ".agents" / "skills" / "nw-codex-skill"
        skills_dir.mkdir(parents=True, exist_ok=True)
        (skills_dir / "SKILL.md").write_text("codex-skill", encoding="utf-8")
        codex_agents_dir = codex_home_dir / "agents"
        codex_agents_dir.mkdir(parents=True, exist_ok=True)
        (codex_agents_dir / "nw-crafter.toml").write_text(
            "codex-agent", encoding="utf-8"
        )

        installer = NWaveInstaller(platform_override={"claude_code", "codex"})
        installer.create_backup()

        claude_backups = sorted((claude_dir / "backups").glob("nwave-install-*"))
        assert claude_backups, (
            "combined claude_code+codex selection must still create the "
            "Claude backup, not skip it in favor of the Codex-only branch"
        )
        claude_backup_dir = claude_backups[-1]
        assert (claude_backup_dir / "agents" / "a.md").read_text(
            encoding="utf-8"
        ) == "agent-original"

        codex_backup_root = agents_home_dir / ".nwave" / "backups"
        codex_backups = sorted(codex_backup_root.glob("nwave-install-*"))
        assert codex_backups, "combined selection must also snapshot Codex"
        codex_backup_dir = codex_backups[-1]
        assert (
            codex_backup_dir / "codex" / "skills" / "nw-codex-skill" / "SKILL.md"
        ).read_text(encoding="utf-8") == "codex-skill"
        assert (codex_backup_dir / "codex" / "agents" / "nw-crafter.toml").read_text(
            encoding="utf-8"
        ) == "codex-agent"

    def test_codex_only_selection_never_writes_claude_directory(
        self, tmp_path, monkeypatch
    ):
        """Preserve Codex-only isolation: no Claude directory writes."""
        import os

        from scripts.install.install_nwave import NWaveInstaller

        claude_dir = tmp_path / ".claude"
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_dir))

        agents_home_dir = Path(os.environ["NWAVE_AGENTS_HOME"])
        codex_home_dir = Path(os.environ["CODEX_HOME"])
        codex_agents_dir = codex_home_dir / "agents"
        codex_agents_dir.mkdir(parents=True, exist_ok=True)
        (codex_agents_dir / "nw-crafter.toml").write_text(
            "codex-agent", encoding="utf-8"
        )

        installer = NWaveInstaller(platform_override={"codex"})
        installer.create_backup()

        assert not claude_dir.exists(), (
            "Codex-only backup must never create/write the Claude config dir"
        )
        codex_backup_root = agents_home_dir / ".nwave" / "backups"
        codex_backups = sorted(codex_backup_root.glob("nwave-install-*"))
        assert codex_backups


class TestCombinedPlatformRetentionCoversBothStores:
    """A combined claude_code+codex run must prune retention on BOTH stores.

    Prior defect: ``apply_retention`` was invoked once, at the end of
    ``create_backup``, against whatever ``backup_manager.backup_root`` the
    LAST branch (Codex) had mutated it to. The Claude store therefore never
    had retention applied when both platforms were selected -- old Claude
    backups accumulated unpruned even past the configured cap.
    """

    def test_combined_selection_prunes_both_claude_and_codex_stores(
        self, tmp_path, monkeypatch
    ):
        import json
        import os

        from scripts.install.install_nwave import NWaveInstaller

        claude_dir = tmp_path / ".claude"
        _make_claude_install(claude_dir)
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_dir))

        agents_home_dir = Path(os.environ["NWAVE_AGENTS_HOME"])
        codex_home_dir = Path(os.environ["CODEX_HOME"])
        skills_dir = agents_home_dir / ".agents" / "skills" / "nw-codex-skill"
        skills_dir.mkdir(parents=True, exist_ok=True)
        (skills_dir / "SKILL.md").write_text("codex-skill", encoding="utf-8")
        codex_agents_dir = codex_home_dir / "agents"
        codex_agents_dir.mkdir(parents=True, exist_ok=True)
        (codex_agents_dir / "nw-crafter.toml").write_text(
            "codex-agent", encoding="utf-8"
        )

        nwave_config_dir = agents_home_dir / ".nwave"
        nwave_config_dir.mkdir(parents=True, exist_ok=True)
        (nwave_config_dir / "config.json").write_text(
            json.dumps({"backups": {"max_count": 1}}), encoding="utf-8"
        )

        claude_backup_root = claude_dir / "backups"
        codex_backup_root = agents_home_dir / ".nwave" / "backups"
        claude_backup_root.mkdir(parents=True, exist_ok=True)
        codex_backup_root.mkdir(parents=True, exist_ok=True)
        # Pre-existing OLD snapshots in BOTH stores, already over the cap of 1.
        for name in ("nwave-install-20200101-000000", "nwave-install-20200102-000000"):
            (claude_backup_root / name).mkdir()
            (codex_backup_root / name).mkdir()

        installer = NWaveInstaller(platform_override={"claude_code", "codex"})
        installer.create_backup()

        claude_survivors = sorted(
            p.name for p in claude_backup_root.glob("nwave-install-*")
        )
        codex_survivors = sorted(
            p.name for p in codex_backup_root.glob("nwave-install-*")
        )

        assert len(claude_survivors) == 1, (
            "retention must prune the Claude store too in a combined run, "
            f"not just Codex's -- got {claude_survivors}"
        )
        assert len(codex_survivors) == 1, (
            f"retention must prune the Codex store -- got {codex_survivors}"
        )
        # Both surviving snapshots must be from THIS install run, not one of
        # the deliberately old pre-existing ones.
        assert not claude_survivors[0].startswith("nwave-install-2020")
        assert not codex_survivors[0].startswith("nwave-install-2020")


class TestRepeatedCreateBackupDoesNotCrossContaminateStores:
    """A second ``create_backup()`` call must not redirect Claude bytes into
    the Codex store.

    Prior defect: ``create_backup`` mutated the SHARED, stateful
    ``backup_manager.backup_root``/``backup_dir`` only inside the Codex
    branch. Those fields persisted on the instance after the call returned,
    so a LATER ``create_backup()`` call -- even a Claude-only one, or a
    second combined call with a fresh timestamp -- read a Claude backup
    location that was still pointed at the previous call's Codex store,
    writing Claude agents/commands/skills bytes under
    ``install_root/.nwave/backups`` instead of ``claude_config_dir/backups``.
    """

    def test_second_call_still_binds_claude_store_correctly(
        self, tmp_path, monkeypatch
    ):
        import os

        from scripts.install.install_nwave import NWaveInstaller

        claude_dir = tmp_path / ".claude"
        _make_claude_install(claude_dir)
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_dir))

        agents_home_dir = Path(os.environ["NWAVE_AGENTS_HOME"])
        codex_home_dir = Path(os.environ["CODEX_HOME"])
        skills_dir = agents_home_dir / ".agents" / "skills" / "nw-codex-skill"
        skills_dir.mkdir(parents=True, exist_ok=True)
        (skills_dir / "SKILL.md").write_text("codex-skill", encoding="utf-8")
        codex_agents_dir = codex_home_dir / "agents"
        codex_agents_dir.mkdir(parents=True, exist_ok=True)
        (codex_agents_dir / "nw-crafter.toml").write_text(
            "codex-agent", encoding="utf-8"
        )

        installer = NWaveInstaller(platform_override={"claude_code", "codex"})
        # First call: combined -- this is the call that used to leave the
        # shared backup_manager's fields pointed at the Codex store.
        installer.create_backup()

        # Force a distinct timestamp so the second call's snapshot dir name
        # differs from the first, then re-mutate current Claude state so a
        # correctly-located second backup is observable.
        installer.backup_manager.timestamp = "20300101-000000"
        (claude_dir / "agents" / "a.md").write_text(
            "agent-mutated-for-second-call", encoding="utf-8"
        )

        # Second call, Claude-only: must still write into
        # claude_config_dir/backups, never into install_root/.nwave/backups.
        installer.create_backup()

        expected_dir = claude_dir / "backups" / "nwave-install-20300101-000000"
        assert expected_dir.exists(), (
            "second create_backup() call must bind the Claude store fresh, "
            f"not reuse the previous call's Codex-redirected location; "
            f"expected {expected_dir} to exist"
        )
        assert (expected_dir / "agents" / "a.md").read_text(
            encoding="utf-8"
        ) == "agent-mutated-for-second-call"

        codex_backup_root = agents_home_dir / ".nwave" / "backups"
        contaminated = codex_backup_root / "nwave-install-20300101-000000" / "agents"
        assert not contaminated.exists(), (
            "the second call's Claude bytes must not land under the Codex "
            f"store at {contaminated}"
        )
