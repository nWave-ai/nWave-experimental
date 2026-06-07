"""Tests for the pytest-xdist worker-count resolution in validate_tests hook.

Guards the target-machine-independence fix: the commit test gate defaults
to ``-n 1`` (no memory doubling, runs on memory-constrained hosts) and is
overridable via the ``NWAVE_PYTEST_XDIST_WORKERS`` env var.
"""

import importlib.util
from pathlib import Path

import pytest


_HOOK_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "hooks" / "validate_tests.py"
)


def _load_hook():
    spec = importlib.util.spec_from_file_location("validate_tests", _HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validate_tests = _load_hook()


def test_default_worker_count_is_one(monkeypatch):
    """Unset env var → default -n 1 (safe for any target machine)."""
    monkeypatch.delenv(validate_tests._XDIST_WORKERS_ENV, raising=False)
    assert validate_tests.resolve_xdist_workers() == "1"


@pytest.mark.parametrize(
    ("env_value", "expected"),
    [
        ("4", "4"),
        ("1", "1"),
        ("auto", "auto"),
        ("8", "8"),
    ],
)
def test_valid_env_override_is_honoured(monkeypatch, env_value, expected):
    """A positive integer or 'auto' is passed straight through to -n."""
    monkeypatch.setenv(validate_tests._XDIST_WORKERS_ENV, env_value)
    assert validate_tests.resolve_xdist_workers() == expected


@pytest.mark.parametrize(
    "env_value",
    ["", "  ", "0", "-2", "two", "2.5", "auto2"],
)
def test_invalid_env_override_falls_back_to_one(monkeypatch, env_value):
    """Empty / non-positive / non-numeric values fall back to -n 1."""
    monkeypatch.setenv(validate_tests._XDIST_WORKERS_ENV, env_value)
    assert validate_tests.resolve_xdist_workers() == "1"
