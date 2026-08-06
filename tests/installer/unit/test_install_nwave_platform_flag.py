"""Tests for install_nwave._resolve_platform_override() — --platform flag.

Codifies the contract: every choice surfaced by argparse MUST have a
corresponding entry in the platform_map.  Regression guards against
silent dropping of a target when a new platform is added (or removed).
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from scripts.install import install_nwave
from scripts.install.install_nwave import NWaveInstaller, _resolve_platform_override


class TestPlatformFlagResolution:
    """The --platform flag must resolve to the documented platform set."""

    def test_auto_returns_none_for_autodetect(self):
        assert _resolve_platform_override("auto") is None

    def test_claude_code_returns_singleton(self):
        assert _resolve_platform_override("claude-code") == {"claude_code"}

    def test_opencode_returns_singleton(self):
        assert _resolve_platform_override("opencode") == {"opencode"}

    def test_codex_returns_singleton(self):
        """Codex must be selectable explicitly, not only via auto-detect."""
        assert _resolve_platform_override("codex") == {"codex"}

    def test_copilot_returns_singleton(self):
        """Copilot CLI must be selectable explicitly, not only via auto-detect."""
        assert _resolve_platform_override("copilot") == {"copilot"}

    def test_all_includes_every_explicit_platform(self):
        """``--platform all`` must include every explicit platform target —
        otherwise users requesting "all" silently miss the absent target.
        """
        explicit = {
            _resolve_platform_override(flag).pop()
            for flag in ("claude-code", "opencode", "codex", "copilot")
        }
        assert _resolve_platform_override("all") == explicit

    def test_unknown_flag_raises(self):
        """Argparse normally guards this, but the resolver must fail loud
        if called with a value outside its choices set.
        """
        with pytest.raises(KeyError):
            _resolve_platform_override("unknown")


def test_effective_targets_are_cached_and_externally_immutable(monkeypatch):
    """Auto-detected target truth cannot be changed by a downstream caller."""
    monkeypatch.setattr(
        "scripts.install.install_nwave.detect_target_platforms",
        lambda: (SimpleNamespace(value="codex"),),
    )
    installer = NWaveInstaller()

    targets = installer.effective_target_platforms

    assert targets == frozenset({"codex"})
    with pytest.raises(AttributeError):
        targets.add("claude_code")
    assert installer.effective_target_platforms == frozenset({"codex"})


def test_create_manifest_receives_the_authoritative_effective_targets(monkeypatch):
    """Manifest creation cannot reconstruct a different target set."""
    installer = NWaveInstaller(platform_override={"codex"})
    received: dict[str, object] = {}

    monkeypatch.setattr(
        "scripts.install.install_nwave.ManifestWriter.write_install_manifest",
        lambda *_args, **kwargs: received.update(kwargs),
    )

    installer.create_manifest()

    assert received["target_platforms"] == frozenset({"codex"})


def test_main_refuses_undetected_host_before_any_install_surface(monkeypatch, capsys):
    """Auto mode fails loud rather than writing an arbitrary host configuration."""

    def no_host_is_detected() -> set[object]:
        return set()

    monkeypatch.setattr(install_nwave, "detect_target_platforms", no_host_is_detected)
    monkeypatch.setattr(sys, "argv", ["install_nwave.py"])
    monkeypatch.setattr(
        install_nwave,
        "show_title_panel",
        lambda *_args, **_kwargs: pytest.fail("title panel must not run"),
    )
    monkeypatch.setattr(
        install_nwave.PreflightChecker,
        "run_all_checks",
        lambda *_args, **_kwargs: pytest.fail("preflight must not run"),
    )
    monkeypatch.setattr(
        install_nwave.NWaveInstaller,
        "create_backup",
        lambda *_args, **_kwargs: pytest.fail("backup must not run"),
    )
    monkeypatch.setattr(
        install_nwave.NWaveInstaller,
        "install_framework",
        lambda *_args, **_kwargs: pytest.fail("installation must not run"),
    )

    assert install_nwave.main() == 2

    assert "--platform" in capsys.readouterr().err
