"""Unit tests for platform auto-detection in context_detector module.

Tests validate detection of target platforms (Claude Code, OpenCode)
based on filesystem markers, environment variables, and binary availability.
"""

from pathlib import Path

from scripts.install.context_detector import (
    TargetPlatform,
    _detect_claude_code,
    detect_target_platforms,
)


class TestDetectClaudeCodeViaDirctory:
    """Verify Claude Code detection via ~/.claude/ directory existence."""

    def test_detect_claude_code_via_directory(self, monkeypatch, tmp_path):
        """detect_target_platforms() includes claude_code when ~/.claude/ exists."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.delenv("CLAUDE_CODE", raising=False)
        monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
        monkeypatch.setattr("shutil.which", lambda _cmd: None)

        platforms = detect_target_platforms()

        assert TargetPlatform.CLAUDE_CODE in platforms

    def test_detect_claude_code_via_env_var(self, monkeypatch, tmp_path):
        """detect_target_platforms() includes claude_code when CLAUDE_CODE env var set."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
        monkeypatch.setenv("CLAUDE_CODE", "1")
        monkeypatch.setattr("shutil.which", lambda _cmd: None)

        platforms = detect_target_platforms()

        assert TargetPlatform.CLAUDE_CODE in platforms


class TestDetectClaudeCodeEmptyEnvVar:
    """Verify CLAUDE_CODE="" does NOT trigger Claude Code detection."""

    def test_detect_claude_code_empty_env_var_does_not_trigger(
        self, monkeypatch, tmp_path
    ):
        """_detect_claude_code() returns False when CLAUDE_CODE="" (empty string).

        The bool() check on empty string correctly returns False, meaning
        an empty CLAUDE_CODE env var is not treated as a positive signal.

        CLAUDE_CONFIG_DIR is deleted so the second signal -- the resolved
        Claude config directory -- is DECLARED absent rather than inherited
        from whatever the developer's shell happens to export. A test that
        reads a different answer on a machine where CLAUDE_CONFIG_DIR points
        at a real profile is measuring the host, not the code.
        """
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
        monkeypatch.setenv("CLAUDE_CODE", "")

        result = _detect_claude_code()

        assert result is False


class TestDetectOpenCodeViaBinary:
    """Verify OpenCode detection via opencode binary in PATH."""

    def test_detect_opencode_via_binary(self, monkeypatch, tmp_path):
        """detect_target_platforms() includes opencode when opencode binary found."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.delenv("CLAUDE_CODE", raising=False)
        monkeypatch.setattr(
            "scripts.install.context_detector.shutil.which",
            lambda cmd: "/usr/local/bin/opencode" if cmd == "opencode" else None,
        )

        platforms = detect_target_platforms()

        assert TargetPlatform.OPENCODE in platforms


class TestDetectOpenCodeViaConfigDir:
    """Verify OpenCode detection via ~/.config/opencode/ directory."""

    def test_detect_opencode_via_config_dir(self, monkeypatch, tmp_path):
        """detect_target_platforms() includes opencode when ~/.config/opencode/ exists."""
        opencode_dir = tmp_path / ".config" / "opencode"
        opencode_dir.mkdir(parents=True)

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.delenv("CLAUDE_CODE", raising=False)
        monkeypatch.setattr(
            "scripts.install.context_detector.shutil.which",
            lambda _cmd: None,
        )

        platforms = detect_target_platforms()

        assert TargetPlatform.OPENCODE in platforms


class TestDetectBothPlatforms:
    """Verify both platforms detected when both signals present."""

    def test_detect_both_platforms(self, monkeypatch, tmp_path):
        """detect_target_platforms() returns both when both signals present."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        opencode_dir = tmp_path / ".config" / "opencode"
        opencode_dir.mkdir(parents=True)

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.delenv("CLAUDE_CODE", raising=False)
        monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
        monkeypatch.setattr(
            "scripts.install.context_detector.shutil.which",
            lambda _cmd: None,
        )

        platforms = detect_target_platforms()

        assert TargetPlatform.CLAUDE_CODE in platforms
        assert TargetPlatform.OPENCODE in platforms
        assert len(platforms) == 2


class TestDetectNothingReturnsEmpty:
    """An ambiguous environment must not silently select a host."""

    def test_detect_nothing_returns_empty_set(self, monkeypatch, tmp_path):
        """detect_target_platforms() leaves host choice to the CLI operator."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.delenv("CLAUDE_CODE", raising=False)
        monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
        monkeypatch.setattr(
            "scripts.install.context_detector.shutil.which",
            lambda _cmd: None,
        )

        platforms = detect_target_platforms()

        assert platforms == set()


class TestTargetPlatformEnum:
    """Verify TargetPlatform enum values."""

    def test_claude_code_value(self):
        """TargetPlatform.CLAUDE_CODE has value 'claude_code'."""
        assert TargetPlatform.CLAUDE_CODE.value == "claude_code"

    def test_opencode_value(self):
        """TargetPlatform.OPENCODE has value 'opencode'."""
        assert TargetPlatform.OPENCODE.value == "opencode"
