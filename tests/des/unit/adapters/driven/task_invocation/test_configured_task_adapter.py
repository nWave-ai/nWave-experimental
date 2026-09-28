from __future__ import annotations

import json
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from des.adapters.driven.config.des_config import DESConfig
from des.adapters.driven.task_invocation.configured_task_adapter import (
    ConfiguredTaskAdapter,
    ModelRuntimeUnavailable,
)
from des.application.delivery_continuation import (
    DeliveryContinuationRunner,
    FrozenHandover,
    RoleTurn,
)
from des.domain.delivery_disposition import Disposition
from des.ports.driven_ports.task_invocation_port import ModelOutcome


def test_missing_selected_launcher_refuses_before_turn_or_record(tmp_path) -> None:
    config_path = tmp_path / ".nwave" / "config.json"
    config_path.parent.mkdir()
    config_path.write_text(
        json.dumps(
            {
                "model_runtime": {
                    "default": {"provider": "codex", "model": "gpt-5.6-terra"}
                }
            }
        ),
        encoding="utf-8",
    )
    adapter = ConfiguredTaskAdapter(tmp_path, DESConfig(cwd=tmp_path))

    with patch(
        "des.adapters.driven.task_invocation.codex_task_adapter.resolve_launcher",
        return_value=None,
    ):
        with pytest.raises(ModelRuntimeUnavailable, match="codex launcher"):
            adapter.invoke(role_id="nw-product-owner", prompt="x", cwd=tmp_path)

    assert not (tmp_path / ".nwave" / "des" / "turns").exists()


def test_runner_reports_selected_launcher_absence_without_provider_fallback(
    tmp_path,
) -> None:
    config_path = tmp_path / ".nwave" / "config.json"
    config_path.parent.mkdir()
    config_path.write_text(
        json.dumps(
            {
                "model_runtime": {
                    "default": {"provider": "codex", "model": "gpt-5.6-terra"}
                }
            }
        ),
        encoding="utf-8",
    )
    adapter = ConfiguredTaskAdapter(tmp_path, DESConfig(cwd=tmp_path))

    with patch(
        "des.adapters.driven.task_invocation.codex_task_adapter.resolve_launcher",
        return_value=None,
    ):
        outcome = DeliveryContinuationRunner()._invoke(
            adapter,
            tmp_path,
            RoleTurn(role="nw-product-owner", prompt="x"),
            FrozenHandover(raw=None),
        )

    assert outcome.disposition is Disposition.Retry
    assert outcome.failure is not None
    assert outcome.failure.what == "ModelNotIssued"
    assert not (tmp_path / ".nwave" / "des" / "turns").exists()


@pytest.mark.parametrize(
    ("provider", "model", "launcher"),
    [
        ("claude", "configured-claude", Path("/bin/claude")),
        ("codex", "configured-codex", Path("/bin/codex")),
    ],
)
def test_configured_adapter_uses_framework_role_and_explicit_runtime_pair(
    tmp_path, monkeypatch: pytest.MonkeyPatch, provider: str, model: str, launcher: Path
) -> None:
    candidate = tmp_path / "candidate"
    config_path = candidate / ".nwave" / "config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {"model_runtime": {"default": {"provider": provider, "model": model}}}
        ),
        encoding="utf-8",
    )
    stale = candidate / "nWave" / "agents" / "role.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("---\nmodel: stale\ntools: Edit\n---\nstale\n", encoding="utf-8")
    framework = tmp_path / "framework"
    runtime = framework / "nWave" / "agents" / "role.md"
    runtime.parent.mkdir(parents=True)
    runtime.write_text(
        "---\nmodel: runtime\ntools: Read\n---\ncorrected\n", encoding="utf-8"
    )
    observed: dict[str, object] = {}

    def fake_spawn(argv, **kwargs):
        observed["argv"] = argv
        observed["cwd"] = kwargs["cwd"]
        observed["input"] = kwargs["input"]
        if provider == "codex":
            Path(argv[argv.index("--output-last-message") + 1]).write_text(
                '{"answer":{"outcome":"accepted","diagnostic":"done"}}',
                encoding="utf-8",
            )
            return CompletedProcess(argv, 0, "", "")
        return CompletedProcess(
            argv,
            0,
            json.dumps(
                {"structured_output": {"outcome": "accepted", "diagnostic": ""}}
            ),
            "",
        )

    monkeypatch.setattr(
        "des.adapters.driven.task_invocation.configured_task_adapter.installed_package_root",
        lambda: framework,
    )
    monkeypatch.setattr("des.runtime.spawn.spawn", fake_spawn)
    launcher_module = {
        "claude": "claude_code_task_adapter",
        "codex": "codex_task_adapter",
    }[provider]
    monkeypatch.setattr(
        f"des.adapters.driven.task_invocation.{launcher_module}.resolve_launcher",
        lambda: launcher,
    )

    run = ConfiguredTaskAdapter(candidate, DESConfig(cwd=candidate)).invoke(
        role_id="role", prompt="candidate prompt", cwd=candidate
    )

    argv = observed["argv"]
    assert run.outcome is ModelOutcome.Accepted
    assert observed["cwd"] == str(candidate)
    if provider == "codex":
        assert json.loads(observed["input"]) == {
            "role_instructions": runtime.read_text(),
            "task": "candidate prompt",
        }
    else:
        assert observed["input"] == "candidate prompt"
    assert isinstance(argv, list)
    assert argv[argv.index("--model") + 1] == model
    if provider == "claude":
        assert argv[argv.index("--agent") + 1] == "role"
    else:
        setting_index = argv.index("-c")
        while not argv[setting_index + 1].startswith("developer_instructions="):
            setting_index = argv.index("-c", setting_index + 1)
        setting = argv[setting_index + 1]
        assert "Apply the decoded role_instructions as instructions" in json.loads(
            setting.split("=", 1)[1]
        )
