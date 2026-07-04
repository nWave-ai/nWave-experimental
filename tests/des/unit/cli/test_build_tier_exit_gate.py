"""Pins for the per-slice build-tier exit check (design option i, ADD-not-mutate).

F-CONTRACT-GATE-EXCLUDES-BUILD-TIER-ARCH-TESTS / evolution-plan P1
deletion-safety precondition: ``des commit-slice`` EXECUTES ``tests/build/**``
before the commit lands. These pins are hermetic (tmp sandbox repos, never this
repo's tree) and run the arch worker serially (``NWAVE_GATE_JOBS=serial``) so a
tiny sandbox suite never pays xdist startup.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from des.cli.commit_slice import main as commit_slice_main
from des.cli.run_contract_gate import build_tier_exit_verdict


pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _serial_arch_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NWAVE_GATE_JOBS", "serial")


def _events(capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    parsed: list[dict[str, object]] = []
    for line in capsys.readouterr().out.splitlines():
        try:
            parsed.append(json.loads(line))
        except ValueError:
            continue
    return parsed


def _write_build_test(repo: Path, body: str) -> None:
    build_dir = repo / "tests" / "build"
    build_dir.mkdir(parents=True)
    (build_dir / "test_arch_invariant.py").write_text(body, encoding="utf-8")


_FAILING_ARCH_TEST = (
    "import pytest\n"
    "pytestmark = pytest.mark.unit\n\n"
    "def test_forbidden_import_ban():\n"
    '    assert False, "planted arch violation: forbidden import detected"\n'
)

_PASSING_ARCH_TEST = (
    "import pytest\n"
    "pytestmark = pytest.mark.unit\n\n"
    "def test_forbidden_import_ban():\n"
    "    assert True\n"
)


def test_absent_build_tier_is_honest_not_applicable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A target with no tests/build gets a DISTINCT N/A event, never a pass claim."""
    assert build_tier_exit_verdict(tmp_path) == 0
    events = _events(capsys)
    assert any(e.get("event") == "BuildTierNotApplicable" for e in events)
    assert not any(e.get("event") == "BuildTierVerified" for e in events)


def test_failing_arch_test_is_refused_naming_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A planted build-tier violation REFUSES (exit 1) naming the failing test."""
    _write_build_test(tmp_path, _FAILING_ARCH_TEST)
    assert build_tier_exit_verdict(tmp_path) == 1
    refused = [e for e in _events(capsys) if e.get("event") == "BuildTierRefused"]
    assert refused, "expected a BuildTierRefused event"
    payload = refused[0]
    assert payload["reason"] == "arch-invariant-failed"
    named = " ".join(str(n) for n in payload["failed_node_ids"])  # type: ignore[union-attr]
    assert "test_forbidden_import_ban" in named
    assert payload["what"] and payload["why"] and payload["how"]


def test_green_build_tier_verified_with_executed_count(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A green build tier clears, reporting how many arch tests EXECUTED."""
    _write_build_test(tmp_path, _PASSING_ARCH_TEST)
    assert build_tier_exit_verdict(tmp_path) == 0
    verified = [e for e in _events(capsys) if e.get("event") == "BuildTierVerified"]
    assert verified and int(verified[0]["collected"]) >= 1  # type: ignore[arg-type]


def test_vacuous_build_tier_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """tests/build present but zero contract-marked tests -> refused, not certified."""
    (tmp_path / "tests" / "build").mkdir(parents=True)
    assert build_tier_exit_verdict(tmp_path) == 1
    refused = [e for e in _events(capsys) if e.get("event") == "BuildTierRefused"]
    assert refused and refused[0]["reason"] == "arch-scope-zero-collected"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def test_commit_slice_refuses_before_any_commit_lands(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The slice exit path refuses a build-tier violation BEFORE committing.

    Fail-closed placement: the violation never ships -- HEAD stays on the
    pre-slice commit and no placeholder commit is created.
    """
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "pin@test")
    _git(tmp_path, "config", "user.name", "pin")
    (tmp_path / "README.md").write_text("seed\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "seed")
    head_before = _git(tmp_path, "rev-parse", "HEAD")

    _write_build_test(tmp_path, _FAILING_ARCH_TEST)
    exit_code = commit_slice_main(
        [
            "--repo",
            str(tmp_path),
            "--message",
            "feat: slice under test",
            "--slice-id",
            "slice-01",
            "--all",
        ]
    )
    assert exit_code == 1
    assert _git(tmp_path, "rev-parse", "HEAD") == head_before
    refused = [e for e in _events(capsys) if e.get("event") == "BuildTierRefused"]
    assert refused and refused[0]["reason"] == "arch-invariant-failed"
