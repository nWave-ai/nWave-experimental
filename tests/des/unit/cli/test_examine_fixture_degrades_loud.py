"""D49 (mikado 2026-07-29): `des examine-fixture` previously had NO
degrade-LOUD path -- a git subprocess failure (`subprocess.CalledProcessError`,
`check=True`) or a ledger-write failure (`OSError`, per
`AtCompletionLedger.append_gate_event`'s own EAFP contract) propagated as an
UNCAUGHT exception straight to a raw Python traceback, never a JSON verdict.
Unified under `des.cli._scaffold_core.ScaffoldDegradeError` +
`emit_scaffold_verdict`, this is the strict improvement Ale required
alongside the scaffold-family unification: examine-fixture now inherits the
SAME JSON degrade-LOUD channel `charter-scaffold` /
`charter-scaffold` already uses.

The SUCCESS path (the full fixture-driving JSON payload) is untouched and
covered by
`tests/des/acceptance/examinable_gate_surface/test_slice_01_examiner_can_reach_the_certification_gate.py`
-- these tests cover ONLY the new failure path.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from des.cli import examine_fixture
from des.cli._scaffold_core import ScaffoldDegradeError


def test_a_git_failure_raises_scaffold_degrade_error_not_a_bare_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`_git` wraps `subprocess.CalledProcessError` into `ScaffoldDegradeError`
    -- the ONE place every git-backed scaffold step (`_git_init`,
    `_commit_with_trailer`, and therefore `build_fixture`) funnels through."""

    def _boom(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(
            returncode=128, cmd=["git", "init"], stderr="fatal: boom\n"
        )

    monkeypatch.setattr(examine_fixture.subprocess, "run", _boom)

    with pytest.raises(ScaffoldDegradeError) as excinfo:
        examine_fixture.build_fixture(tmp_path / "repo", "demo")

    assert "git" in excinfo.value.detail.lower()
    assert "boom" in excinfo.value.detail


def test_a_missing_git_executable_raises_scaffold_degrade_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`FileNotFoundError` (git not on PATH) degrades LOUD the same way as a
    non-zero git exit -- never a bare traceback either."""

    def _no_git(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("git")

    monkeypatch.setattr(examine_fixture.subprocess, "run", _no_git)

    with pytest.raises(ScaffoldDegradeError) as excinfo:
        examine_fixture.build_fixture(tmp_path / "repo", "demo")

    assert "git" in excinfo.value.detail.lower()


def test_a_ledger_write_failure_raises_scaffold_degrade_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`AtCompletionLedger.append_gate_event` documents `OSError` as its own
    surfaced failure (EAFP, no separate writability probe) -- `build_fixture`
    now catches exactly that and degrades LOUD instead of propagating it."""

    def _boom(self: object, **_kwargs: object) -> None:
        raise OSError("ledger directory is not writable")

    monkeypatch.setattr(examine_fixture.AtCompletionLedger, "append_gate_event", _boom)

    with pytest.raises(ScaffoldDegradeError) as excinfo:
        examine_fixture.build_fixture(tmp_path / "repo", "demo")

    assert "ledger" in excinfo.value.detail.lower()


def test_main_emits_a_json_verdict_and_nonzero_exit_on_degrade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The end-to-end contract: `main()` catches `ScaffoldDegradeError` and
    prints the SAME JSON-verdict vocabulary (`verdict`/`detail` keys) the
    other two scaffolds use, returning a non-zero exit -- never letting the
    exception escape to a traceback."""

    def _boom(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(
            returncode=128, cmd=["git", "init"], stderr="fatal: boom\n"
        )

    monkeypatch.setattr(examine_fixture.subprocess, "run", _boom)

    out_dir = tmp_path / "repo"
    exit_code = examine_fixture.main(["--out", str(out_dir), "--feature-id", "demo"])

    assert exit_code != 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["verdict"] != "accepted"
    assert "detail" in payload
    assert payload["repo"] == str(out_dir)
    assert payload["feature_id"] == "demo"
