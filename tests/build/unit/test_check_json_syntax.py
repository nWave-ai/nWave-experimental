"""Regression coverage for the tracked-file JSON syntax gate."""

from __future__ import annotations

import importlib.util
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest


def _load_gate():
    script = Path(__file__).resolve().parents[3] / "scripts/hooks/check_json_syntax.py"
    spec = importlib.util.spec_from_file_location("check_json_syntax", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gate():
    return _load_gate()


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)


def _track(root: Path, path: Path) -> None:
    subprocess.run(["git", "add", "--", path.relative_to(root)], cwd=root, check=True)


def test_ignores_untracked_worktree_json_with_invalid_encoding(
    gate,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An ignored worktree artifact cannot crash a gate for tracked source."""
    _init_repo(tmp_path)
    tracked = tmp_path / "tracked.json"
    tracked.write_text('{"valid": true}\n', encoding="utf-8")
    _track(tmp_path, tracked)
    artifact = tmp_path / ".nwave/worktrees/fixture/ignored.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"\xff\xfebroken")
    monkeypatch.chdir(tmp_path)

    assert gate.main() == 0

    assert "All JSON files have valid syntax" in capsys.readouterr().out


@dataclass(frozen=True)
class _MalformedTrackedJson:
    """Malformed bytes tracked in the repo, with the diagnostic they must earn."""

    payload: bytes
    expected_diagnostic: str


@pytest.mark.parametrize(
    "malformed",
    [
        _MalformedTrackedJson(
            payload=b'{"missing": }', expected_diagnostic="invalid JSON"
        ),
        _MalformedTrackedJson(
            payload=b"\xff\xfebroken", expected_diagnostic="invalid UTF-8"
        ),
    ],
    ids=["invalid-json", "invalid-utf8"],
)
def test_reports_tracked_json_and_encoding_failures_with_path(
    gate,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    malformed: _MalformedTrackedJson,
) -> None:
    """Tracked malformed bytes fail cleanly and identify the offending file."""
    _init_repo(tmp_path)
    tracked = tmp_path / "broken.json"
    tracked.write_bytes(malformed.payload)
    _track(tmp_path, tracked)
    monkeypatch.chdir(tmp_path)

    assert gate.main() == 1

    output = capsys.readouterr().out
    assert "broken.json" in output
    assert malformed.expected_diagnostic in output
