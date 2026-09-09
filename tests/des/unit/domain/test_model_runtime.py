from __future__ import annotations

import pytest

from des.domain.model_runtime import (
    ModelProvider,
    ModelRuntimeConfigError,
    resolve_role_runtime,
)


def _pair(provider: str, model: str) -> dict[str, str]:
    return {"provider": provider, "model": model}


def test_role_override_wins_without_cross_tier_pair_mixing(tmp_path) -> None:
    runtime = resolve_role_runtime(
        "nw-solution-architect",
        repo_root=tmp_path,
        global_tier={"model_runtime": {"default": _pair("claude", "global")}},
        repo_tier={
            "model_runtime": {"roles": {"nw-solution-architect": _pair("codex", "sol")}}
        },
    )

    assert runtime.provider is ModelProvider.CODEX
    assert runtime.model == "sol"


@pytest.mark.parametrize(
    "declared",
    [
        {"provider": "codex"},
        {"model": "gpt-5.6-terra"},
        _pair("unknown", "model"),
        _pair("codex", " "),
    ],
)
def test_present_invalid_pair_refuses_instead_of_falling_to_global(
    tmp_path, declared: dict[str, str]
) -> None:
    with pytest.raises(ModelRuntimeConfigError):
        resolve_role_runtime(
            "nw-product-owner",
            repo_root=tmp_path,
            global_tier={"model_runtime": {"default": _pair("claude", "global")}},
            repo_tier={"model_runtime": {"default": declared}},
        )


def test_absent_config_preserves_declared_claude_model(tmp_path) -> None:
    agents = tmp_path / "nWave" / "agents"
    agents.mkdir(parents=True)
    (agents / "nw-product-owner.md").write_text(
        "---\nmodel: claude-legacy\ntools: Read\n---\n", encoding="utf-8"
    )

    runtime = resolve_role_runtime(
        "nw-product-owner", repo_root=tmp_path, global_tier={}, repo_tier={}
    )

    assert runtime.provider is ModelProvider.CLAUDE
    assert runtime.model == "claude-legacy"


def test_absent_config_uses_framework_role_model_before_subject(tmp_path) -> None:
    framework = tmp_path / "framework"
    framework_spec = framework / "nWave" / "agents" / "role.md"
    framework_spec.parent.mkdir(parents=True)
    framework_spec.write_text(
        "---\nmodel: framework\ntools: Read\n---\n", encoding="utf-8"
    )
    subject = tmp_path / "subject"
    subject_spec = subject / "nWave" / "agents" / "role.md"
    subject_spec.parent.mkdir(parents=True)
    subject_spec.write_text("---\nmodel: stale\ntools: Read\n---\n", encoding="utf-8")

    runtime = resolve_role_runtime(
        "role",
        repo_root=subject,
        framework_root=framework,
        global_tier={},
        repo_tier={},
    )

    assert runtime == type(runtime)(ModelProvider.CLAUDE, "framework")
