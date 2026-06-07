"""Unit coverage for the contract-gate parallel-RUN worker-spec resolution.

The perf fix parallelises the whole-suite RUN with pytest-xdist (`-n auto`),
cutting the serial ~30 min feedback loop to ~6 min on 4 cores. The worker spec
is resolved through a small, pure decision surface:

* ``_scan_gate_jobs``      -- stdlib line-scan of the ``gate.jobs`` config key
* ``_resolve_gate_jobs``   -- env var > ``.nwave/config.yaml`` > ``auto``
* ``_parallel_pytest_args``-- the pytest argv fragment, with a LOUD serial
                              degrade when xdist is absent (genericita mandate)

These are deterministic, suite-free units (no nested pytest run). They guard the
default-parallel behaviour, the operator override knobs, and the absent-xdist
graceful degrade so a customer install without the optional ``pytest-xdist``
still runs the gate (serially, with a visible reason) rather than crashing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.cli import run_contract_gate as rcg


# --- _scan_gate_jobs: the narrow stdlib config scan ------------------------


def test_scan_gate_jobs_reads_nested_value() -> None:
    text = "gate:\n  jobs: 3\n"
    assert rcg._scan_gate_jobs(text) == "3"


def test_scan_gate_jobs_strips_trailing_comment() -> None:
    text = "gate:\n  jobs: auto  # one worker per CPU\n"
    assert rcg._scan_gate_jobs(text) == "auto"


def test_scan_gate_jobs_absent_block_returns_none() -> None:
    text = "workflow:\n  mode: atdd_pure\n"
    assert rcg._scan_gate_jobs(text) is None


def test_scan_gate_jobs_ignores_jobs_outside_gate_block() -> None:
    # A `jobs:` key under a different top-level block must NOT be picked up.
    text = "other:\n  jobs: 9\ngate:\n  carpaccio: 3\n"
    assert rcg._scan_gate_jobs(text) is None


# --- _resolve_gate_jobs: env > config > default ----------------------------


def test_resolve_defaults_to_auto_when_nothing_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(rcg._GATE_JOBS_ENV, raising=False)
    assert rcg._resolve_gate_jobs(tmp_path) == "auto"


def test_resolve_env_var_wins_over_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_dir = tmp_path / ".nwave"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text("gate:\n  jobs: 2\n", encoding="utf-8")
    monkeypatch.setenv(rcg._GATE_JOBS_ENV, "serial")
    assert rcg._resolve_gate_jobs(tmp_path) == "serial"


def test_resolve_reads_config_when_env_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_dir = tmp_path / ".nwave"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text("gate:\n  jobs: 4\n", encoding="utf-8")
    monkeypatch.delenv(rcg._GATE_JOBS_ENV, raising=False)
    assert rcg._resolve_gate_jobs(tmp_path) == "4"


def test_resolve_blank_env_var_falls_through_to_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(rcg._GATE_JOBS_ENV, "   ")
    assert rcg._resolve_gate_jobs(tmp_path) == "auto"


# --- _parallel_pytest_args: argv fragment + LOUD degrade -------------------


def test_parallel_args_auto_emits_xdist_loadgroup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(rcg._GATE_JOBS_ENV, raising=False)
    monkeypatch.setattr(rcg, "can_import", lambda _interp, _mod: True)
    args = rcg._parallel_pytest_args(tmp_path, "python3")
    assert args == ["-n", "auto", "--dist", "loadgroup"]


def test_parallel_args_serial_token_disables_parallelism(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(rcg._GATE_JOBS_ENV, "serial")
    # Even with xdist available, the operator opt-out yields a serial run.
    monkeypatch.setattr(rcg, "can_import", lambda _interp, _mod: True)
    assert rcg._parallel_pytest_args(tmp_path, "python3") == []


@pytest.mark.parametrize("token", ["0", "1", "off", "none", "SERIAL"])
def test_parallel_args_all_serial_tokens_disable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, token: str
) -> None:
    monkeypatch.setenv(rcg._GATE_JOBS_ENV, token)
    monkeypatch.setattr(rcg, "can_import", lambda _interp, _mod: True)
    assert rcg._parallel_pytest_args(tmp_path, "python3") == []


def test_parallel_args_absent_xdist_degrades_loud_to_serial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """xdist absent -> serial run + a LOUD one-line stderr notice (genericita).

    The genericita mandate forbids a silent dependency assumption: a customer
    install without the optional ``pytest-xdist`` must still run the gate, and
    must SAY why it is slow rather than degrade silently.
    """
    monkeypatch.delenv(rcg._GATE_JOBS_ENV, raising=False)
    monkeypatch.setattr(rcg, "can_import", lambda _interp, _mod: False)

    args = rcg._parallel_pytest_args(tmp_path, "python3")

    assert args == []
    err = capsys.readouterr().err
    assert "pytest-xdist" in err
    assert "SERIALLY" in err
