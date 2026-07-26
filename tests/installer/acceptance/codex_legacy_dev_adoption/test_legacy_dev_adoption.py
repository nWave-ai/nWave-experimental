"""Acceptance contract for the explicit Codex legacy-dev adoption path."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.install.install_nwave import NWaveInstaller


def _write_legacy_dev_state(home: Path) -> tuple[Path, Path]:
    """Create assets a v1 manifest did not record, plus a user hook sentinel."""
    skills = home / ".agents" / "skills"
    agents = home / ".codex" / "agents"
    legacy_skill = skills / "nw-legacy-dev-only"
    legacy_skill.mkdir(parents=True)
    (legacy_skill / "SKILL.md").write_text("legacy skill\n", encoding="utf-8")
    legacy_agent = agents / "nw-legacy-dev-only.toml"
    legacy_agent.parent.mkdir(parents=True, exist_ok=True)
    legacy_agent.write_text('name = "legacy"\n', encoding="utf-8")
    (skills / ".nwave-manifest.json").write_text(
        json.dumps({"installed_skills": [], "version": "1.0"}) + "\n",
        encoding="utf-8",
    )
    (agents / ".nwave-agents-manifest.json").write_text(
        json.dumps({"installed_agents": [], "version": "1.0"}) + "\n",
        encoding="utf-8",
    )
    (home / ".codex" / "hooks.json").write_text(
        json.dumps({"hooks": {"PreToolUse": [{"matcher": "^User$", "hooks": []}]}})
        + "\n",
        encoding="utf-8",
    )
    return legacy_skill, legacy_agent


def _installer(*, adopt: bool) -> NWaveInstaller:
    return NWaveInstaller(
        platform_override={"codex"},
        dev_mode=True,
        adopt_legacy_codex_dev=adopt,
    )


def test_explicit_dev_adoption_quarantines_unrecorded_assets_after_one_backup(
    tmp_path: Path, monkeypatch
) -> None:
    """A legacy dev upgrade is explicit, recoverable, and repeatable.

    The normal path refuses without changing a byte.  The explicit path first
    snapshots the Codex state in its one nWave backup, quarantines only the
    unrecorded nWave-shaped dev artifacts inside that same backup, installs
    the current dev catalogue, and leaves a subsequent reinstall admissible.
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("NWAVE_AGENTS_HOME", str(home))
    monkeypatch.setenv("CODEX_HOME", str(home / ".codex"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home / ".claude"))
    legacy_skill, legacy_agent = _write_legacy_dev_state(home)
    user_skill = home / ".agents" / "skills" / "personal-workflow"
    user_skill.mkdir()
    (user_skill / "SKILL.md").write_text("personal\n", encoding="utf-8")
    user_agent = home / ".codex" / "agents" / "personal.toml"
    user_agent.write_text('name = "personal"\n', encoding="utf-8")
    hooks_before = (home / ".codex" / "hooks.json").read_bytes()

    refused = _installer(adopt=False)
    assert not refused.validate_codex_ownership_preflight()
    assert legacy_skill.is_dir()
    assert legacy_agent.is_file()
    assert (home / ".codex" / "hooks.json").read_bytes() == hooks_before
    assert not (home / ".nwave" / "backups").exists()

    adopted = _installer(adopt=True)
    assert adopted.validate_codex_ownership_preflight()
    adopted.create_backup()
    assert adopted._codex_backup_dir is not None
    assert adopted.adopt_legacy_codex_dev_assets()
    assert not legacy_skill.exists()
    assert not legacy_agent.exists()
    backup = adopted._codex_backup_dir
    assert (backup / "codex" / "skills" / "nw-legacy-dev-only" / "SKILL.md").read_text(
        encoding="utf-8"
    ) == "legacy skill\n"
    assert (
        backup / "legacy-codex-dev" / "skills" / "nw-legacy-dev-only" / "SKILL.md"
    ).is_file()
    assert (
        backup / "legacy-codex-dev" / "agents" / "nw-legacy-dev-only.toml"
    ).is_file()
    assert (backup / "legacy-codex-dev" / "receipt.json").is_file()
    assert adopted.install_framework()
    assert (user_skill / "SKILL.md").read_text(encoding="utf-8") == "personal\n"
    assert user_agent.read_text(encoding="utf-8") == 'name = "personal"\n'
    installed_hooks = json.loads((home / ".codex" / "hooks.json").read_text())
    assert {
        "matcher": "^User$",
        "hooks": [],
    } in installed_hooks["hooks"]["PreToolUse"]

    # The new manifests record the installed dev catalogue, so the next
    # installation sees no legacy collision and needs no special migration.
    reinstall = _installer(adopt=False)
    assert reinstall.validate_codex_ownership_preflight()
    assert reinstall.install_framework()
