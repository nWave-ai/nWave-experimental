from __future__ import annotations

import json

import pytest

from des.adapters.driven.config.des_config import DESConfig
from des.domain.model_runtime import ModelProvider, ModelRuntimeConfigError


def _write(path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def test_des_config_applies_repo_role_then_global_default(tmp_path) -> None:
    repo = tmp_path / "repo"
    _write(
        repo / ".nwave" / "config.json",
        {"model_runtime": {"roles": {"role": {"provider": "codex", "model": "sol"}}}},
    )
    global_path = tmp_path / "home" / ".nwave" / "config.json"
    _write(
        global_path,
        {"model_runtime": {"default": {"provider": "claude", "model": "legacy"}}},
    )

    config = DESConfig(cwd=repo, global_config_path=global_path)

    selected = config.role_runtime("role")
    assert (selected.provider, selected.model) == (ModelProvider.CODEX, "sol")


def test_invalid_repo_runtime_is_loud_and_does_not_use_global(tmp_path) -> None:
    repo = tmp_path / "repo"
    _write(
        repo / ".nwave" / "config.json",
        {"model_runtime": {"default": {"provider": "codex"}}},
    )
    global_path = tmp_path / "home" / ".nwave" / "config.json"
    _write(
        global_path,
        {"model_runtime": {"default": {"provider": "claude", "model": "legacy"}}},
    )

    with pytest.raises(ModelRuntimeConfigError):
        DESConfig(cwd=repo, global_config_path=global_path).role_runtime("role")
