from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

import pytest
from nwave_ai.cli import main

from des.adapters.driven.config.des_config import DESConfig
from des.domain.model_runtime import ModelProvider


def _invoke(args: list[str]) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    with (
        patch("sys.argv", ["nwave-ai", *args]),
        patch("sys.stdout", out),
        patch("sys.stderr", err),
    ):
        code = main()
    return code, out.getvalue(), err.getvalue()


def test_model_set_writes_complete_project_role_pair(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    role_spec = tmp_path / "nWave" / "agents" / "nw-solution-architect.md"
    role_spec.parent.mkdir(parents=True)
    role_spec.write_text(
        "---\nname: nw-solution-architect\ntools: Read\n---\n",
        encoding="utf-8",
    )

    code, _, stderr = _invoke(
        [
            "model",
            "set",
            "--provider",
            "codex",
            "--model",
            "gpt-5.6-sol",
            "--role",
            "nw-solution-architect",
            "--project",
        ]
    )

    assert code == 0, stderr
    written = json.loads((tmp_path / ".nwave" / "config.json").read_text())
    assert written["model_runtime"]["roles"] == {
        "nw-solution-architect": {"provider": "codex", "model": "gpt-5.6-sol"}
    }
    selected = DESConfig(
        cwd=tmp_path,
        global_config_path=tmp_path / "home" / ".nwave" / "config.json",
    ).role_runtime("nw-solution-architect")
    assert (selected.provider, selected.model) == (ModelProvider.CODEX, "gpt-5.6-sol")


def test_model_set_competence_writes_distinct_pair_from_the_ordinary_role(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    role_spec = tmp_path / "nWave" / "agents" / "nw-solution-architect.md"
    role_spec.parent.mkdir(parents=True)
    role_spec.write_text(
        "---\nname: nw-solution-architect\ntools: Read\n---\n",
        encoding="utf-8",
    )

    code, stdout, stderr = _invoke(
        [
            "model",
            "set",
            "--provider",
            "codex",
            "--model",
            "gpt-5.6-adv",
            "--role",
            "nw-solution-architect",
            "--competence",
            "advanced",
            "--project",
        ]
    )

    assert code == 0, stderr
    written = json.loads((tmp_path / ".nwave" / "config.json").read_text())
    assert written["model_runtime"]["roles"] == {
        "nw-solution-architect#advanced": {"provider": "codex", "model": "gpt-5.6-adv"}
    }
    config = DESConfig(
        cwd=tmp_path,
        global_config_path=tmp_path / "home" / ".nwave" / "config.json",
    )
    advanced = config.role_runtime("nw-solution-architect#advanced")
    assert (advanced.provider, advanced.model) == (ModelProvider.CODEX, "gpt-5.6-adv")
    # The confirmation names the key actually persisted, not the bare role --
    # a reader uses this line as evidence of what the config now contains.
    assert "role nw-solution-architect#advanced" in stdout
    assert "role nw-solution-architect " not in stdout


def test_model_set_without_competence_confirms_the_bare_role_as_today(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    role_spec = tmp_path / "nWave" / "agents" / "nw-solution-architect.md"
    role_spec.parent.mkdir(parents=True)
    role_spec.write_text(
        "---\nname: nw-solution-architect\ntools: Read\n---\n",
        encoding="utf-8",
    )

    code, stdout, stderr = _invoke(
        [
            "model",
            "set",
            "--provider",
            "codex",
            "--model",
            "gpt-5.6-sol",
            "--role",
            "nw-solution-architect",
            "--project",
        ]
    )

    assert code == 0, stderr
    assert "role nw-solution-architect set" in stdout


def test_unknown_provider_refuses_before_any_config_write(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    code, _, stderr = _invoke(
        ["model", "set", "--provider", "other", "--model", "x", "--project"]
    )

    assert code == 2
    assert "requires provider" in stderr
    assert not (tmp_path / ".nwave").exists()
    assert not (tmp_path / "home" / ".nwave").exists()


def test_unknown_role_refuses_before_mutating_existing_config_bytes(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    config_path = tmp_path / ".nwave" / "config.json"
    config_path.parent.mkdir()
    original = b'{"model_runtime":{"default":{"provider":"claude","model":"sonnet"}}}\n'
    config_path.write_bytes(original)

    code, _, stderr = _invoke(
        [
            "model",
            "set",
            "--provider",
            "codex",
            "--model",
            "gpt-5.6-terra",
            "--role",
            "nw-typo-role",
            "--project",
        ]
    )

    assert code == 2
    assert "readable published agent specification" in stderr
    assert config_path.read_bytes() == original


def test_global_model_write_uses_the_same_redirected_home_that_des_reads(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "unselected-home"))
    monkeypatch.setenv("NWAVE_AGENTS_HOME", str(tmp_path / "agents-home"))

    code, _, stderr = _invoke(
        ["model", "set", "--provider", "codex", "--model", "gpt-5.6-terra"]
    )

    assert code == 0, stderr
    written = tmp_path / "agents-home" / ".nwave" / "config.json"
    assert written.is_file()
    selected = DESConfig(cwd=tmp_path).role_runtime("nw-product-owner")
    assert (selected.provider, selected.model) == (ModelProvider.CODEX, "gpt-5.6-terra")
    assert not (tmp_path / "unselected-home" / ".nwave").exists()


def test_help_advertises_model_configuration() -> None:
    code, stdout, _ = _invoke(["--help"])

    assert code == 0
    assert "model" in stdout


def test_model_set_help_exits_zero_without_creating_config(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    code, stdout, stderr = _invoke(["model", "set", "--help"])

    assert code == 0
    assert "Usage: nwave-ai model set" in stdout
    assert not stderr
    assert not (tmp_path / ".nwave").exists()


@pytest.mark.parametrize(
    ("override_name", "argv"),
    [
        (
            "NWAVE_AGENTS_HOME",
            ["model", "set", "--provider", "codex", "--model", "gpt-5.6-terra"],
        ),
        ("CLAUDE_CONFIG_DIR", ["mode", "all"]),
        ("CODEX_HOME", ["project", "set", "verbosity", "terse", "--yes"]),
        ("CLAUDE_CONFIG_DIR", ["attribution", "on"]),
        ("NWAVE_AGENTS_HOME", ["project", "enable", "--yes"]),
    ],
)
def test_relative_selected_home_override_refuses_every_cli_config_write(
    tmp_path, monkeypatch, override_name: str, argv: list[str]
) -> None:
    """A malformed selected-home override cannot fall back to native HOME on writes."""
    project = tmp_path / "project"
    project.mkdir()
    native_home = tmp_path / "native-home"
    native_config = native_home / ".nwave" / "config.json"
    native_config.parent.mkdir(parents=True)
    original = b'{"activation":{"mode":"opt-in"}}\n'
    native_config.write_bytes(original)
    monkeypatch.chdir(project)
    monkeypatch.setenv("HOME", str(native_home))
    monkeypatch.delenv("NWAVE_AGENTS_HOME", raising=False)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setenv(override_name, "relative-selected-home")

    code, _, stderr = _invoke(argv)

    assert code == 1
    assert override_name in stderr
    assert "absolute paths" in stderr
    assert native_config.read_bytes() == original
    assert not (project / ".nwave").exists()
    assert not (project / ".gitignore").exists()
    assert not (project / "CLAUDE.md").exists()
    assert not (project / "AGENTS.md").exists()
