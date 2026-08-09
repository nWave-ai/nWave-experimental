"""Regression: AttributionPlugin must route every settings-touching call to
context.claude_dir, not Path.home()/.claude.

Defect (split-brain): the plugin passed only ``self._config_dir`` positionally
to the settings-touching helpers, so ``claude_dir`` defaulted to
``Path.home()/.claude``. Under ``install --target <path>`` the managed payload
landed in ``~/.claude`` (wrong) instead of ``<path>`` — the two halves of the
same feature split across two directories. RCA:
docs/feature/fix-attribution-plugin-claude-dir/deliver/rca.md.

ADR-CA-007 reconciliation: the un-gateable ``settings.json attribution.{commit,pr}``
WRITE is retired; the activation-gated PreToolUse hook (universal pre-tool-use
adapter) is the sole enforcement, observing ``attribution.enabled`` at
invocation time. Install instead calls ``cleanup_legacy_attribution_hook(
claude_dir=...)`` to remove any stale independent registration left by an
older install, and records the opt-in preference. The ``claude_dir`` injection
seam is LOAD-BEARING and PRESERVED — this regression still guards it, now over
the cleanup call site (the surviving settings-touching surface) instead of the
retired credit writer. Uninstall still routes ``remove_settings_attribution``
through ``claude_dir`` (RETAINED legacy-block cleanup), so that half is
unchanged.

These tests drive the REAL AttributionPlugin.install()/.uninstall() with NO
stubbing of the settings helpers — they live under tests/bugs/, which does NOT
inherit the module-scoped ``isolate_attribution_side_effects`` autouse fixture
from tests/installer/unit/plugins/test_attribution_plugin.py, so the real
settings read+write executes and the routing is observable.

This is a wiring/routing regression (verifies the plugin call sites forward
``context.claude_dir``): single-example by nature, EXEMPT from the PBT-default
mandate (mirrors test_milestone_2_uninstall_wiring.py).
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

from scripts.install.attribution_utils import (
    NWAVE_MANAGED_COMMIT,
    NWAVE_MANAGED_PR,
    _attribution_hook_command,
)
from scripts.install.plugins.attribution_plugin import AttributionPlugin
from scripts.install.plugins.base import InstallContext


def _make_context(claude_dir: Path, nwave_config_dir: Path) -> InstallContext:
    """Minimal InstallContext pointing claude_dir at the install target.

    Mirrors the shape of tests/installer/unit/plugins/test_attribution_plugin.py
    ::_make_context but is constructed directly so the autouse stub fixture in
    that module is NOT triggered.
    """
    return InstallContext(
        claude_dir=claude_dir,
        scripts_dir=claude_dir.parent / "scripts",
        templates_dir=claude_dir.parent / "templates",
        logger=MagicMock(),
        project_root=claude_dir.parent / "project",
        metadata={"nwave_config_dir": nwave_config_dir},
    )


def _settings_attribution_commit(claude_dir: Path) -> object | None:
    """Return settings.json attribution.commit for claude_dir, or None."""
    settings_path = claude_dir / "settings.json"
    if not settings_path.exists():
        return None
    with open(settings_path, encoding="utf-8") as f:
        settings = json.load(f)
    return (settings.get("attribution") or {}).get("commit")


def _attribution_hook_registered(claude_dir: Path) -> bool:
    """Whether the CA-007 PreToolUse commit-attribution hook is in claude_dir."""
    settings_path = claude_dir / "settings.json"
    if not settings_path.exists():
        return False
    with open(settings_path, encoding="utf-8") as f:
        settings = json.load(f)
    entries = (settings.get("hooks") or {}).get("PreToolUse") or []
    return any(
        entry.get("matcher") == "Bash"
        and any(
            "pre-commit-attribution" in (hook.get("command") or "")
            for hook in entry.get("hooks") or []
        )
        for entry in entries
    )


def test_install_routes_stale_cleanup_to_target_claude_dir(
    tmp_path: Path, monkeypatch
) -> None:
    """install() routes exact stale cleanup to ctx.claude_dir, not ~/.claude.

    ADR-CA-007/CA-006: install calls cleanup_legacy_attribution_hook on the
    install target. The claude_dir injection seam must route cleanup to the
    install target and leave the default ~/.claude untouched.
    """
    home = tmp_path / "home"
    home_claude = home / ".claude"
    home_claude.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    target_claude = tmp_path / "target_claude"
    target_claude.mkdir()

    nwave_config = tmp_path / ".nwave"

    # Seed stale hook into target (simulating prior install)
    (target_claude / "settings.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": _attribution_hook_command(target_claude),
                                }
                            ],
                        }
                    ]
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    ctx = _make_context(target_claude, nwave_config)
    AttributionPlugin(config_dir=nwave_config).install(ctx)

    # Stale hook removed from target (cleanup routed via seam).
    assert not _attribution_hook_registered(target_claude)
    # Stale hook cleaned from target (cleanup routed via seam).
    assert _settings_attribution_commit(target_claude) is None
    # Default ~/.claude never written.
    assert not (home_claude / "settings.json").exists()


def test_install_routes_settings_migration_to_target_claude_dir(
    tmp_path: Path, monkeypatch
) -> None:
    """install() routes settings.json legacy cleanup to ctx.claude_dir.

    install performs migrate_legacy_settings_attribution cleanup of retired
    settings.json attribution.{commit,pr}. The claude_dir injection seam must
    route that cleanup to the install target, leaving the default ~/.claude
    untouched.
    """
    home = tmp_path / "home"
    home_claude = home / ".claude"
    home_claude.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    target_claude = tmp_path / "target_claude"
    target_claude.mkdir()

    nwave_config = tmp_path / ".nwave"

    # Seed a nWave-managed legacy credit into the TARGET settings.json
    (target_claude / "settings.json").write_text(
        json.dumps(
            {"attribution": {"commit": NWAVE_MANAGED_COMMIT, "pr": NWAVE_MANAGED_PR}},
            indent=2,
        ),
        encoding="utf-8",
    )

    ctx = _make_context(target_claude, nwave_config)
    AttributionPlugin(config_dir=nwave_config).install(ctx)

    # Legacy credit removed from target (migration routed via seam).
    assert _settings_attribution_commit(target_claude) is None
    # Default ~/.claude never written.
    assert not (home_claude / "settings.json").exists()


def test_uninstall_removes_payload_from_target_claude_dir(
    tmp_path: Path, monkeypatch
) -> None:
    """uninstall() removes the managed payload from ctx.claude_dir and leaves
    ~/.claude untouched."""
    home = tmp_path / "home"
    home_claude = home / ".claude"
    home_claude.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    target_claude = tmp_path / "target_claude"
    target_claude.mkdir()

    # Seed the managed payload into the TARGET settings.json.
    (target_claude / "settings.json").write_text(
        json.dumps(
            {"attribution": {"commit": NWAVE_MANAGED_COMMIT, "pr": NWAVE_MANAGED_PR}},
            indent=2,
        ),
        encoding="utf-8",
    )

    nwave_config = tmp_path / ".nwave"
    ctx = _make_context(target_claude, nwave_config)

    AttributionPlugin(config_dir=nwave_config).uninstall(ctx)

    # Managed payload removed from the install target.
    assert _settings_attribution_commit(target_claude) is None
    # And ~/.claude was never touched (no settings.json created there).
    assert not (home_claude / "settings.json").exists()
