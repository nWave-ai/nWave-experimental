"""Install refuses an invalid active wave-end preference before writing config."""

from __future__ import annotations

from pathlib import Path

from nwave_ai import cli


def test_install_refuses_invalid_expansion_without_rewriting_config(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "project"
    repo.mkdir()
    config_path = home / ".nwave" / "config.json"
    config_path.parent.mkdir(parents=True)
    original = b'{"documentation":{"density":"full","expansion_prompt":"typo"}}\n'
    config_path.write_bytes(original)
    monkeypatch.setenv("NWAVE_AGENTS_HOME", str(home))
    monkeypatch.chdir(repo)
    assert cli._handle_install(["--yes"]) != 0
    error = capsys.readouterr().err
    assert "documentation.expansion_prompt" in error
    assert "ask-intelligent" in error
    assert config_path.read_bytes() == original
