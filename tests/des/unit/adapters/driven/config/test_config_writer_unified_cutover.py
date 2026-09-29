"""Real-filesystem contract for G1's unified configuration cutover."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.adapters.driven.config.config_writer import ConfigMigrationError, ConfigWriter
from des.adapters.driven.config.des_config import DESConfig


def _write(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def test_bootstrap_constructs_two_versioned_authorities_from_empty_roots(
    tmp_path: Path,
) -> None:
    home, repo = tmp_path / "home", tmp_path / "repo"
    repo.mkdir()

    result = ConfigWriter(home_dir=home, repo_root=repo).bootstrap()

    assert result.created_paths == (
        home / ".nwave" / "config.json",
        repo / ".nwave" / "config.json",
    )
    assert json.loads(result.global_path.read_text()) == {
        "schema-version": 1,
        "attribution": {
            "enabled": True,
            "trailer": "Co-Authored-By: nWave <nwave@nwave.ai>",
        },
    }
    assert json.loads(result.repo_path.read_text()) == {
        "audit_log_dir": ".nwave/des/logs",
        "audit_logging_enabled": True,
        "schema-version": 1,
    }


def test_bootstrap_coalesces_the_two_tiers_when_an_isolated_root_is_both(
    tmp_path: Path,
) -> None:
    """K4 may intentionally pin agents home and project root to one workspace."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = ConfigWriter(home_dir=workspace, repo_root=workspace).bootstrap()

    assert (
        result.global_path == result.repo_path == workspace / ".nwave" / "config.json"
    )
    assert result.created_paths == (workspace / ".nwave" / "config.json",)
    assert json.loads(result.repo_path.read_text()) == {
        "audit_log_dir": ".nwave/des/logs",
        "audit_logging_enabled": True,
        "attribution": {
            "enabled": True,
            "trailer": "Co-Authored-By: nWave <nwave@nwave.ai>",
        },
        "schema-version": 1,
    }


def test_explicit_writes_retire_only_update_check_and_preserve_preferences(
    tmp_path: Path,
) -> None:
    home, repo = tmp_path / "home", tmp_path / "repo"
    repo.mkdir()
    writer = ConfigWriter(home_dir=home, repo_root=repo)
    _write(
        writer.global_path,
        {
            "update_check": {"frequency": "weekly"},
            "documentation": {"density": "full", "expansion_prompt": "always-expand"},
            "attribution": {"enabled": False, "trailer": "Custom"},
            "model_runtime": {"default": {"provider": "openai", "model": "gpt-4"}},
            "custom": {"retained": True},
        },
    )
    _write(
        writer.repo_path,
        {
            "update_check": {"frequency": "daily"},
            "model_runtime": {
                "roles": {"reviewer": {"provider": "openai", "model": "gpt-4"}}
            },
            "custom": {"retained": True},
        },
    )

    writer.update_global(lambda config: config.update(verbosity="verbose"))
    writer.update_repo(lambda config: config.update(enabled=True))
    global_config = json.loads(writer.global_path.read_text())
    repo_config = json.loads(writer.repo_path.read_text())

    assert "update_check" not in global_config
    assert "update_check" not in repo_config
    assert global_config["documentation"] == {
        "density": "full",
        "expansion_prompt": "always-expand",
    }
    assert global_config["attribution"] == {"enabled": False, "trailer": "Custom"}
    assert global_config["model_runtime"] == {
        "default": {"provider": "openai", "model": "gpt-4"}
    }
    assert repo_config["model_runtime"]["roles"]["reviewer"]["model"] == "gpt-4"
    assert global_config["custom"] == repo_config["custom"] == {"retained": True}


def test_migration_preserves_values_backs_up_and_retires_every_legacy_source(
    tmp_path: Path,
) -> None:
    home, repo = tmp_path / "home", tmp_path / "repo"
    global_legacy = home / ".nwave" / "global-config.json"
    repo_legacy = repo / ".nwave" / "des-config.json"
    marker_legacy = repo / ".nwave" / "local-config.json"
    _write(
        global_legacy, {"activation": {"mode": "all"}, "attribution": {"enabled": True}}
    )
    _write(repo_legacy, {"audit_logging_enabled": False, "log_level": "debug"})
    _write(marker_legacy, {"enabled_for_repo": False})

    writer = ConfigWriter(home_dir=home, repo_root=repo)
    result = writer.bootstrap()
    config = DESConfig(cwd=repo, global_config_path=writer.global_path)

    assert result.migrated_legacy_paths == (global_legacy, repo_legacy, marker_legacy)
    assert not global_legacy.exists()
    assert not repo_legacy.exists()
    assert not marker_legacy.exists()
    assert config.activation_mode == "all"
    assert config.enabled_for_repo is False
    assert config.attribution_enabled is True
    assert config.audit_logging_enabled is False
    assert config.log_level == "DEBUG"
    for retired in (global_legacy, repo_legacy, marker_legacy):
        assert retired.with_name(f"{retired.name}.unified-config.bak").exists()

    second = writer.bootstrap()
    assert second.migrated_legacy_paths == ()
    assert second.created_paths == ()


def test_conflicting_legacy_input_refuses_before_writing_or_retiring(
    tmp_path: Path,
) -> None:
    home, repo = tmp_path / "home", tmp_path / "repo"
    unified = repo / ".nwave" / "config.json"
    legacy = repo / ".nwave" / "des-config.json"
    _write(unified, {"log_level": "warn"})
    _write(legacy, {"log_level": "debug"})

    with pytest.raises(ConfigMigrationError, match="conflicting values"):
        ConfigWriter(home_dir=home, repo_root=repo).bootstrap()

    assert json.loads(unified.read_text()) == {"log_level": "warn"}
    assert legacy.exists()
    assert not legacy.with_name(f"{legacy.name}.unified-config.bak").exists()


def test_conflicting_legacy_activation_declarations_refuse_without_any_write(
    tmp_path: Path,
) -> None:
    home, repo = tmp_path / "home", tmp_path / "repo"
    des_legacy = repo / ".nwave" / "des-config.json"
    marker_legacy = repo / ".nwave" / "local-config.json"
    _write(des_legacy, {"enabled": True})
    _write(marker_legacy, {"enabled_for_repo": False})
    before_des = des_legacy.read_bytes()
    before_marker = marker_legacy.read_bytes()

    with pytest.raises(
        ConfigMigrationError, match="conflicting activation declarations"
    ):
        ConfigWriter(home_dir=home, repo_root=repo).bootstrap()

    assert des_legacy.read_bytes() == before_des
    assert marker_legacy.read_bytes() == before_marker
    assert not (home / ".nwave" / "config.json").exists()
    assert not (repo / ".nwave" / "config.json").exists()
    assert not des_legacy.with_name(f"{des_legacy.name}.unified-config.bak").exists()
    assert not marker_legacy.with_name(
        f"{marker_legacy.name}.unified-config.bak"
    ).exists()


def test_malformed_legacy_input_refuses_before_writing_or_retiring(
    tmp_path: Path,
) -> None:
    home, repo = tmp_path / "home", tmp_path / "repo"
    legacy = home / ".nwave" / "global-config.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("{bad json", encoding="utf-8")

    with pytest.raises(ConfigMigrationError, match="invalid legacy config JSON"):
        ConfigWriter(home_dir=home, repo_root=repo).bootstrap()

    assert legacy.exists()
    assert not (home / ".nwave" / "config.json").exists()
    assert not (repo / ".nwave" / "config.json").exists()


def test_reader_never_uses_a_retired_file_as_runtime_fallback(tmp_path: Path) -> None:
    home, repo = tmp_path / "home", tmp_path / "repo"
    _write(home / ".nwave" / "global-config.json", {"attribution": {"enabled": True}})
    _write(repo / ".nwave" / "des-config.json", {"audit_logging_enabled": False})
    _write(repo / ".nwave" / "local-config.json", {"enabled_for_repo": True})

    config = DESConfig(
        cwd=repo,
        global_config_path=home / ".nwave" / "config.json",
    )

    assert config.attribution_enabled is False
    assert config.audit_logging_enabled is True
    assert config.enabled_for_repo is None
