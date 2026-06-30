"""Regression: the flat nw-* agent/command layout must be cleaned, and a
dangling flat symlink must not crash the next install's backup.

Root cause (found 2026-06-17 on the dev machine): a public/flat install writes
flat ``~/.claude/agents/nw-*.md`` (symlinks), but uninstall's nested-only remover
deleted only ``agents/nw/`` -- leaving the flat symlinks DANGLING. The next
install's BackupManager.create_backup copytree then followed those broken
symlinks and aborted the whole install, wiping the environment. Three fixes,
one per test below.
"""

from __future__ import annotations

import pytest


try:
    from scripts.install.install_utils import BackupManager, Logger, PathUtils
    from scripts.install.uninstall_nwave import NWaveUninstaller
except ImportError:  # pragma: no cover - direct-script import fallback
    from install_utils import BackupManager, Logger, PathUtils
    from uninstall_nwave import NWaveUninstaller

pytestmark = pytest.mark.unit


@pytest.fixture
def claude_dir(tmp_path, monkeypatch):
    """Point PathUtils.get_claude_config_dir() at a tmp ~/.claude."""
    cfg = tmp_path / ".claude"
    cfg.mkdir()
    monkeypatch.setattr(PathUtils, "get_claude_config_dir", staticmethod(lambda: cfg))
    return cfg


def _seed_flat_layout(cfg):
    """nw/ subdir with one real agent + a valid flat symlink + a DANGLING one."""
    agents = cfg / "agents"
    nested = agents / "nw"
    nested.mkdir(parents=True)
    real = nested / "nw-foo.md"
    real.write_text("# foo agent\n", encoding="utf-8")
    valid_link = agents / "nw-foo.md"
    valid_link.symlink_to(real)
    dangling = agents / "nw-bar.md"
    dangling.symlink_to(nested / "nw-bar.md")  # target does NOT exist
    return agents, valid_link, dangling


def test_uninstall_removes_flat_agent_symlinks_including_dangling(claude_dir):
    """Fix #1: remove_agents clears flat nw-* (valid AND dangling symlinks)."""
    agents, valid_link, dangling = _seed_flat_layout(claude_dir)
    assert valid_link.is_symlink() and dangling.is_symlink()

    u = NWaveUninstaller(force=True)
    u.remove_agents()

    assert not (agents / "nw").exists(), "nested nw/ should be gone"
    assert not valid_link.is_symlink(), "valid flat symlink should be removed"
    assert not dangling.is_symlink(), "dangling flat symlink should be removed"
    # No flat nw-* residue at all (glob yields dangling symlinks too).
    assert not list(agents.glob("nw-*")) if agents.exists() else True


def test_validate_removal_flags_flat_residue_not_false_green(claude_dir):
    """Fix #2: a leftover flat (dangling) symlink makes validate_removal False."""
    agents = claude_dir / "agents"
    agents.mkdir()
    (agents / "nw-orphan.md").symlink_to(agents / "missing-target.md")  # dangling

    u = NWaveUninstaller(force=True)
    # nested agents/nw/ absent + manifest/log absent + no DES hooks, yet the
    # flat residue must drive an HONEST failure (no false "✅ Agents removed").
    assert u._has_flat_nw_residue("agents") is True
    assert u.validate_removal() is False


def test_backup_survives_dangling_flat_symlink(claude_dir):
    """Fix #3: BackupManager.create_backup must not crash on a broken symlink."""
    agents = claude_dir / "agents"
    agents.mkdir()
    (agents / "nw-real.md").write_text("# real\n", encoding="utf-8")
    (agents / "nw-broken.md").symlink_to(agents / "gone.md")  # dangling

    mgr = BackupManager(Logger(None, silent=True), "install")
    # Must return the backup path without raising shutil.Error on the broken link.
    backup_dir = mgr.create_backup()
    assert backup_dir is not None
    assert (backup_dir / "agents" / "nw-real.md").exists()
