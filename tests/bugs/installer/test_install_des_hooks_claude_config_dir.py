"""Regression: standalone DESHookInstaller must honor CLAUDE_CONFIG_DIR, and
its success message must be conditioned on a verified write.

Defect (audit AUDIT-installer.md #1, ALTA): ``DESHookInstaller.__init__``
defaulted ``config_dir`` to a fixed ``Path.home() / ".claude"`` instead of
``PathUtils.get_claude_config_dir()`` (which honors ``CLAUDE_CONFIG_DIR`` --
the same property ``installation_verifier.py`` and ``verify_nwave.py``
already resolve on). On a multi-profile machine (documented in this repo's own
CLAUDE.md: claude / claude2 / claude3, each with its own ``CLAUDE_CONFIG_DIR``)
the standalone entry point
``python -m scripts.install.install_des_hooks --install`` -- the exact
invocation its own ``main()`` docstring/argparse advertises -- wrote hooks
into the WRONG profile's settings.json while unconditionally printing
"DES hooks installed successfully".

Same bug class as the AttributionPlugin claude_dir regression
(test_bug_attribution_plugin_claude_dir.py): decide on the PROPERTY (active
profile) not a fixed DESIGNATION (~/.claude).

Fix: __init__ defaults via PathUtils.get_claude_config_dir(); install()
reloads settings.json after saving and only prints success if the hooks are
verifiably present, and names the directory it wrote to (GDP-6/GDP-8:
no silent-wrong, decide on verified state not on the save call not raising).
"""

from pathlib import Path

from scripts.install.install_des_hooks import DESHookInstaller


class TestDESHookInstallerHonorsClaudeConfigDir:
    """__init__ must resolve the active profile, not a fixed ~/.claude."""

    def test_default_config_dir_honors_claude_config_dir_env(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """No explicit config_dir + CLAUDE_CONFIG_DIR set -> installer targets
        the env-var profile, not Path.home()/.claude."""
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

        active_profile = tmp_path / "claude-alt3"
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(active_profile))

        installer = DESHookInstaller()

        assert installer.config_dir == active_profile
        assert installer.config_dir != home / ".claude"

    def test_default_config_dir_falls_back_to_home_claude_without_env(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """No explicit config_dir + no CLAUDE_CONFIG_DIR -> unchanged legacy
        default of ~/.claude (backward compatible)."""
        monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

        installer = DESHookInstaller()

        assert installer.config_dir == home / ".claude"

    def test_explicit_config_dir_still_wins_over_env(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """An explicit config_dir argument is never overridden by the env var
        (explicit caller intent, e.g. install_nwave.py's own invocation)."""
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "env-profile"))
        explicit = tmp_path / "explicit-target"

        installer = DESHookInstaller(config_dir=explicit)

        assert installer.config_dir == explicit

    def test_install_writes_into_the_active_profile_not_home(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """End-to-end: install() with CLAUDE_CONFIG_DIR set writes hooks into
        that directory's settings.json, and leaves ~/.claude untouched."""
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

        active_profile = tmp_path / "claude-alt3"
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(active_profile))

        installer = DESHookInstaller()
        result = installer.install()

        assert result is True
        assert (active_profile / "settings.json").exists()
        assert not (home / ".claude" / "settings.json").exists()


class TestDESHookInstallerSuccessIsVerified:
    """The success message is a claim about disk state, checked before print."""

    def test_success_message_names_the_resolved_directory(
        self, tmp_path: Path, capsys
    ) -> None:
        target = tmp_path / "profile"
        installer = DESHookInstaller(config_dir=target)

        result = installer.install()

        assert result is True
        captured = capsys.readouterr()
        assert str(target) in captured.out

    def test_install_fails_loud_when_write_does_not_verify(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        """If _save_config silently no-ops (simulating a write that never
        lands, e.g. a read-only mount), install() must NOT claim success --
        it must reload and check, then report failure, never silent-wrong."""
        target = tmp_path / "profile"
        installer = DESHookInstaller(config_dir=target)
        monkeypatch.setattr(installer, "_save_config", lambda config: None)

        result = installer.install()

        assert result is False
        captured = capsys.readouterr()
        assert "installed successfully" not in captured.out
        assert "failed" in captured.err.lower()
