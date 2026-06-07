"""
Shared fixtures for lean-wave-documentation acceptance tests.

Strategy C — Real local: real wave skill files modified, real
~/.nwave/global-config.json reads via tmp_path + monkeypatched HOME, real
JsonlAuditLogWriter writing to tmp_path. NO mocks.

All fixtures use pytest tmp_path for test isolation -- no real filesystem
state leaks between tests, no host environment pollution.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest


if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Marco's nWave home — real filesystem under tmp_path with monkeypatched HOME
# ---------------------------------------------------------------------------


@pytest.fixture
def marco_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Marco's home directory under tmp_path with HOME env var monkeypatched.

    Real filesystem operations -- no mocks. Density resolver and audit log
    writer will see this directory as $HOME for the duration of the test.

    Returns:
        Path to Marco's home (parent of .nwave/)
    """
    home = tmp_path / "marco-home"
    home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture
def marco_nwave_dir(marco_home: Path) -> Path:
    """
    Marco's ~/.nwave/ directory (created lazily; tests control whether
    global-config.json exists).
    """
    nwave_dir = marco_home / ".nwave"
    nwave_dir.mkdir(parents=True, exist_ok=True)
    return nwave_dir


@pytest.fixture
def global_config_path(marco_home: Path) -> Path:
    """
    Path to Marco's ~/.nwave/global-config.json.

    File is NOT created -- tests control existence via given steps.
    """
    return marco_home / ".nwave" / "global-config.json"


# ---------------------------------------------------------------------------
# Marco's project worktree — real repo directory under tmp_path
# ---------------------------------------------------------------------------


@pytest.fixture
def marco_repo(tmp_path: Path) -> Path:
    """
    Marco's project repository root with docs/ subtree.

    Returns:
        Path to the repository root
    """
    repo = tmp_path / "repo"
    (repo / "docs" / "feature").mkdir(parents=True)
    (repo / "docs" / "reference").mkdir(parents=True)
    (repo / "docs" / "guides").mkdir(parents=True)
    return repo


# ---------------------------------------------------------------------------
# Real audit log directory — JsonlAuditLogWriter writes here for real
# ---------------------------------------------------------------------------


@pytest.fixture
def audit_log_dir(marco_home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Audit log directory under Marco's home.

    Sets DES_AUDIT_LOG_DIR so JsonlAuditLogWriter resolves to this path.
    Real JSONL files written and read here -- no in-memory writer.
    """
    log_dir = marco_home / ".nwave" / "des" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DES_AUDIT_LOG_DIR", str(log_dir))
    return log_dir


# ---------------------------------------------------------------------------
# Scenario context — mutable bag shared across Given/When/Then for one scenario
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx() -> dict[str, Any]:
    """Mutable context bag for sharing state between steps in a scenario."""
    return {}


# ---------------------------------------------------------------------------
# Helpers (pure functions — no filesystem state)
# ---------------------------------------------------------------------------


def write_global_config(config_path: Path, payload: dict[str, Any]) -> None:
    """Write a JSON config file, creating parent dirs if needed."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_global_config(config_path: Path) -> dict[str, Any]:
    """Read a JSON config file."""
    return json.loads(config_path.read_text(encoding="utf-8"))
