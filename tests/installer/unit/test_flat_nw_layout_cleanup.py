"""Regression: only positively-identified legacy flat nw-* symlinks are
cleaned, and a dangling one must not crash the next install's backup.

Root cause (found 2026-06-17 on the dev machine): a public/flat install writes
flat ``~/.claude/agents/nw-*.md`` (symlinks), but uninstall's nested-only remover
deleted only ``agents/nw/`` -- leaving the flat symlinks DANGLING. The next
install's BackupManager.create_backup copytree then followed those broken
symlinks and aborted the whole install, wiping the environment.

Correction (Issue 98 follow-up): the original fix used an unconditional
``nw-*`` glob delete, which also deleted a user's own file/dir/symlink that
merely happened to start with ``nw-``. Ownership is now positive only -- a
flat symlink whose raw (unresolved) target lexically resolves inside the
dedicated ``{noun}/nw/`` root, dangling or not -- never a name-prefix glob.
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


def _seed_legacy_layout(cfg, noun):
    """nw/ subdir with one real entry + a valid flat symlink + a DANGLING one."""
    parent = cfg / noun
    nested = parent / "nw"
    nested.mkdir(parents=True)
    real = nested / "nw-foo.md"
    real.write_text("# foo\n", encoding="utf-8")
    valid_link = parent / "nw-foo.md"
    valid_link.symlink_to(real)
    dangling = parent / "nw-bar.md"
    dangling.symlink_to(nested / "nw-bar.md")  # lexically inside nw/, target absent
    return parent, valid_link, dangling


def _seed_user_siblings(parent):
    """A user-owned file, directory, and foreign-target symlink, all named nw-*."""
    user_file = parent / "nw-note.md"
    user_file.write_text("my note\n", encoding="utf-8")
    user_dir = parent / "nw-dir"
    user_dir.mkdir()
    (user_dir / "keep.txt").write_text("keep\n", encoding="utf-8")
    foreign_target = parent / "elsewhere.md"
    foreign_target.write_text("elsewhere\n", encoding="utf-8")
    foreign_link = parent / "nw-foreign.md"
    foreign_link.symlink_to(foreign_target)
    return user_file, user_dir, foreign_link


@pytest.mark.parametrize(
    "noun,remover", [("agents", "remove_agents"), ("commands", "remove_commands")]
)
class TestFlatNwNamespaceOwnership:
    def test_removes_legacy_flat_symlinks_including_dangling(
        self, claude_dir, noun, remover
    ):
        """Legacy flat symlinks (valid AND dangling) into nw/ are removed."""
        parent, valid_link, dangling = _seed_legacy_layout(claude_dir, noun)
        assert valid_link.is_symlink() and dangling.is_symlink()

        u = NWaveUninstaller(force=True)
        getattr(u, remover)()

        assert not (parent / "nw").exists(), "nested nw/ should be gone"
        assert not valid_link.is_symlink(), (
            "valid legacy flat symlink should be removed"
        )
        assert not dangling.is_symlink(), (
            "dangling legacy flat symlink should be removed"
        )

    def test_preserves_user_owned_flat_nw_star_entries(self, claude_dir, noun, remover):
        """A user file/dir/foreign-target symlink named nw-* survives removal
        and is never reported as residue."""
        parent, _, _ = _seed_legacy_layout(claude_dir, noun)
        user_file, user_dir, foreign_link = _seed_user_siblings(parent)

        u = NWaveUninstaller(force=True)
        getattr(u, remover)()

        assert user_file.exists() and not user_file.is_symlink()
        assert user_dir.is_dir()
        assert (user_dir / "keep.txt").exists()
        assert foreign_link.is_symlink()
        assert foreign_link.resolve().name == "elsewhere.md"
        assert u._has_flat_nw_residue(noun) is False

    def test_validate_removal_flags_legacy_residue_not_false_green(
        self, claude_dir, noun, remover
    ):
        """A leftover legacy (dangling) flat symlink drives an honest failure."""
        parent = claude_dir / noun
        parent.mkdir()
        nested = parent / "nw"
        (parent / "nw-orphan.md").symlink_to(nested / "missing-target.md")

        u = NWaveUninstaller(force=True)
        # nested {noun}/nw/ absent + manifest/log absent + no DES hooks, yet
        # the legacy flat residue must drive an HONEST failure (no false
        # "✅ removed").
        assert u._has_flat_nw_residue(noun) is True
        assert u.validate_removal() is False

    def test_second_removal_is_idempotent(self, claude_dir, noun, remover):
        """A second uninstall pass over an already-clean tree is a no-op."""
        parent, _, _ = _seed_legacy_layout(claude_dir, noun)
        _seed_user_siblings(parent)

        u = NWaveUninstaller(force=True)
        getattr(u, remover)()
        getattr(u, remover)()  # second run must not raise or change outcome

        assert not (parent / "nw").exists()
        assert u._has_flat_nw_residue(noun) is False


def test_backup_survives_dangling_flat_symlink(claude_dir):
    """BackupManager.create_backup must not crash on a broken legacy symlink."""
    agents = claude_dir / "agents"
    nested = agents / "nw"
    nested.mkdir(parents=True)
    (agents / "nw-real.md").write_text("# real\n", encoding="utf-8")
    (agents / "nw-broken.md").symlink_to(nested / "gone.md")  # dangling

    mgr = BackupManager(Logger(None, silent=True), "install")
    # Must return the backup path without raising shutil.Error on the broken link.
    backup_dir = mgr.create_backup()
    assert backup_dir is not None
    assert (backup_dir / "agents" / "nw-real.md").exists()
