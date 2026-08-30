"""One install-root override owns every global nWave write destination."""

from __future__ import annotations

from pathlib import Path

import pytest
from nwave_ai.cli import _get_config_dir

from scripts.shared.install_paths import (
    active_runtime_pointer_path,
    agents_home,
    host_neutral_runtime_dir,
    nwave_config_dir,
    record_active_runtime,
)


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
