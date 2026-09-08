"""One install-root override owns every global nWave write destination."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from nwave_ai.cli import _get_config_dir, _handle_mode, _handle_status

from scripts.install.install_nwave import NWaveInstaller
from scripts.shared.install_paths import (
    active_runtime_pointer_path,
    agents_home,
    host_neutral_runtime_dir,
    nwave_config_dir,
    record_active_runtime,
)


def test_agents_home_override_unifies_mode_write_and_status_read(
    tmp_path: Path, monkeypatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """P-SSOT-1: `nwave-ai mode all` writes through `agents_home()`
    (`nwave_ai/cli.py:969-983,245-247`) while `nwave-ai status` used to read
    `DESConfig`'s `Path.home()`-rooted default
    (`src/des/adapters/driven/config/des_config.py:96`,
    `nwave_ai/cli.py:986-997`), splitting write destination from read
    destination whenever `NWAVE_AGENTS_HOME` differs from `HOME`. With
    HOME=A and NWAVE_AGENTS_HOME=B, both commands must agree on B.
    """
    home_a = tmp_path / "native-home"
    agents_home_b = tmp_path / "agents-home"
    home_a.mkdir()
    agents_home_b.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home_a))
    monkeypatch.setenv("NWAVE_AGENTS_HOME", str(agents_home_b))
    monkeypatch.chdir(tmp_path)

    assert _handle_mode(["all"]) == 0

    written = agents_home_b / ".nwave" / "global-config.json"
    assert written.exists()
    assert (
        json.loads(written.read_text(encoding="utf-8"))["activation"]["mode"] == "all"
    )
    assert not (home_a / ".nwave" / "global-config.json").exists()

    capsys.readouterr()
    assert _handle_status([]) == 0
    out = capsys.readouterr().out
    assert "Global activation mode: all" in out


@pytest.mark.parametrize(
    "env_var",
    ["NWAVE_AGENTS_HOME", "CLAUDE_CONFIG_DIR", "CODEX_HOME"],
    ids=["agents-home-override", "claude-config-override", "codex-config-override"],
)
@pytest.mark.parametrize(
    ("override", "expect_refusal"),
    [
        (None, False),
        ("", False),
        ("absolute-override", False),
        ("relative-override", True),
    ],
    ids=["unset", "empty", "absolute", "relative"],
)
def test_nwave_installer_refuses_a_relative_override_before_any_write(
    tmp_path: Path,
    monkeypatch,
    env_var: str,
    override: str | None,
    expect_refusal: bool,
) -> None:
    """P-SSOT-1 INVALID_STATE, BROAD_INPUT_DOMAIN: the construction site
    `NWaveInstaller.__init__` builds one location result from all three
    ordered override channels -- `NWAVE_AGENTS_HOME` (agents_home_override),
    `CLAUDE_CONFIG_DIR` (claude_config_override) and `CODEX_HOME`
    (codex_config_override) -- before any public method runs. Per channel,
    an absent or empty override is absent (native home); an absolute
    override is a valid root; a relative override never becomes a root --
    construction refuses before any write, never silently joining it under
    an ambient cwd. For every non-refusing shape, construction itself is
    observed to perform no filesystem write.
    """
    home_a = tmp_path / "native-home"
    home_a.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home_a))
    monkeypatch.chdir(tmp_path)

    if override is None:
        monkeypatch.delenv(env_var, raising=False)
    elif override == "absolute-override":
        absolute_override = tmp_path / f"absolute-{env_var.lower()}"
        absolute_override.mkdir()
        monkeypatch.setenv(env_var, str(absolute_override))
    else:
        monkeypatch.setenv(env_var, override)

    pre_existing = set(tmp_path.rglob("*"))

    if expect_refusal:
        with pytest.raises(Exception, match="(?i)relative"):
            NWaveInstaller(platform_override={"claude_code"})
        assert not (home_a / ".nwave").exists()
        assert set(tmp_path.rglob("*")) == pre_existing
    else:
        NWaveInstaller(platform_override={"claude_code"})
        assert not (home_a / ".nwave").exists()
        assert set(tmp_path.rglob("*")) == pre_existing


def test_agents_home_override_isolates_config_runtime_and_pointer(
    tmp_path: Path, monkeypatch
) -> None:
    real_home = tmp_path / "operator-home"
    isolated_home = tmp_path / "verification-home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: real_home))
    monkeypatch.setenv("NWAVE_AGENTS_HOME", str(isolated_home))

    runtime = isolated_home / ".nwave" / "runtime"
    record_active_runtime(runtime)

    assert agents_home() == isolated_home
    assert nwave_config_dir() == isolated_home / ".nwave"
    assert _get_config_dir() == isolated_home / ".nwave"
    assert host_neutral_runtime_dir() == runtime
    assert active_runtime_pointer_path().read_text(encoding="utf-8") == (
        runtime.as_posix() + "\n"
    )
    assert not (real_home / ".nwave").exists()


@pytest.mark.parametrize("override", [None, ""])
def test_absent_or_empty_override_preserves_the_operator_home(
    tmp_path: Path, monkeypatch, override: str | None
) -> None:
    real_home = tmp_path / "operator-home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: real_home))
    if override is None:
        monkeypatch.delenv("NWAVE_AGENTS_HOME", raising=False)
    else:
        monkeypatch.setenv("NWAVE_AGENTS_HOME", override)

    assert agents_home() == real_home
    assert nwave_config_dir() == real_home / ".nwave"
    assert _get_config_dir() == real_home / ".nwave"
    assert host_neutral_runtime_dir() == real_home / ".nwave" / "runtime"
    assert active_runtime_pointer_path() == real_home / ".nwave" / "active-runtime"
