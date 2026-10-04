"""Consumer-visible isolation and invalid-attempt regressions.

A controlled subprocess mutation producer exercises filesystem/process boundaries;
its counts are not evidence of a real mutmut pilot. Real-tool smoke is separate.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from scripts.mutation import run_nightly_delta as driver
from scripts.mutation.nightly_delta import BaselineDecision, classify_failure


_CONTROLLED_PRODUCER = r"""
import json, os, sys, time
from pathlib import Path
stage, scope = sys.argv[1:]
scope = json.loads(scope)
mode = Path(scope[0]).read_text().strip()
if stage == "baseline":
    Path("ordinary-baseline.json").write_text(json.dumps({"exit_code": 0, "collected": 1, "call_reports": 1, "errors": 0, "argv": ["controlled-baseline"]}))
    Path("attempt-mode").write_text(mode)
    assert not Path("mutants").exists(), "inherited result/cache must not enter an attempt"
    sys.exit(0)
mode = Path("attempt-mode").read_text()
if stage == "run":
    Path("mutants").mkdir()
    Path("pyproject.toml").write_text("child-only mutated configuration")
    Path(scope[0]).write_text("child-only source mutation")
    for key in ("TMPDIR", "HOME", "XDG_CACHE_HOME", "UV_CACHE_DIR", "PYTHONPYCACHEPREFIX"):
        Path(os.environ[key], "child-marker").write_text(mode)
    native = Path("native-observations")
    native.mkdir()
    outcomes = {"a": [1, 0, 0, 0], "b": [1, 1], "zero": [], "interrupted": [1, 0], "invalid100": [4, 4, 4]}[mode]
    for index, exit_code in enumerate(outcomes):
        observed = exit_code != 4
        (native / f"{index}.json").write_text(json.dumps({
            "mutant": f"fixture.x_example__mutmut_{index}",
            "collected": int(observed), "call_reports": int(observed),
            "call_failures": int(exit_code == 1), "errors": 0,
            "exit_code": exit_code, "argv": ["controlled-native-selection"],
        }))
    time.sleep(0.1)
    sys.exit(130 if mode == "interrupted" else 0)
if stage == "export":
    counts = {
        "a": {"total": 4, "killed": 1, "survived": 3},
        "b": {"total": 2, "killed": 2},
        "zero": {"total": 0},
        "interrupted": {"total": 4, "killed": 1, "survived": 1, "check_was_interrupted_by_user": 2},
        "invalid100": {"total": 3, "killed": 3},
    }[mode]
    Path("mutants/mutmut-cicd-stats.json").write_text(json.dumps(counts))
if stage == "results":
    print(mode + ": current-invocation mutants")
"""


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    (repo / "src/des").mkdir(parents=True)
    for mode in ("a", "b", "zero", "interrupted", "invalid100"):
        (repo / f"src/des/{mode}.py").write_text(mode)
    (repo / "pyproject.toml").write_text("original configuration")
    (repo / "mutation-results.txt").write_text("stale caller survivor")
    (repo / "mutants").mkdir()
    (repo / "mutants/mutmut-cicd-stats.json").write_text('{"total":99,"killed":99}')
    _git(repo, "init", "-q")
    _git(repo, "add", ".")
    _git(
        repo,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-qm",
        "fixture",
    )
    return repo, _git(repo, "rev-parse", "HEAD")


def test_concurrent_deltas_preserve_caller_and_do_not_share_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, head = _repo(tmp_path)
    original = {
        str(p.relative_to(repo)): p.read_bytes()
        for p in repo.rglob("*")
        if p.is_file() and ".git" not in p.parts
    }
    # Caller WIP is deliberately different from the exact requested commit.
    (repo / "src/des/a.py").write_text("caller WIP must not be mutated or tested")
    original["src/des/a.py"] = (repo / "src/des/a.py").read_bytes()
    status = _git(repo, "status", "--porcelain")
    monkeypatch.setattr(driver, "_MUTMUT_CHILD", _CONTROLLED_PRODUCER)
    decision = BaselineDecision("ok", head, "explicit controlled delta")
    with ThreadPoolExecutor(max_workers=2) as pool:
        reports = list(
            pool.map(
                lambda mode: driver._run_scored(
                    decision, [f"src/des/{mode}.py"], 80, repo=repo, head_sha=head
                ),
                ("a", "b"),
            )
        )
    a, b = reports
    assert (a.score.killed, a.score.survived, classify_failure(a)) == (
        1,
        3,
        "below_threshold",
    )
    assert (b.score.killed, b.score.survived, classify_failure(b)) == (2, 0, None)
    assert a.results_text == "a: current-invocation mutants\n"
    assert b.results_text == "b: current-invocation mutants\n"
    assert a.provenance["invocation_id"] != b.provenance["invocation_id"]
    assert a.provenance["workspace"] != b.provenance["workspace"]
    assert (
        a.provenance["source_sha256"]["src/des/a.py"]
        == hashlib.sha256(b"a").hexdigest()
    )
    for report in reports:
        assert report.provenance["head_sha"] == head
        assert report.provenance["ordinary_baseline"]["collected"] == 1
        assert not Path(report.provenance["workspace"]).exists()
    current = {
        str(p.relative_to(repo)): p.read_bytes()
        for p in repo.rglob("*")
        if p.is_file() and ".git" not in p.parts
    }
    assert current == original
    assert _git(repo, "status", "--porcelain") == status


def test_zero_and_interrupted_attempts_retain_truthful_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, head = _repo(tmp_path)
    monkeypatch.setattr(driver, "_MUTMUT_CHILD", _CONTROLLED_PRODUCER)
    decision = BaselineDecision("ok", head, "explicit controlled delta")
    zero = driver._run_scored(
        decision, ["src/des/zero.py"], 80, repo=repo, head_sha=head
    )
    interrupted = driver._run_scored(
        decision, ["src/des/interrupted.py"], 80, repo=repo, head_sha=head
    )
    noop = driver._run_scored(decision, [], 80, repo=repo, head_sha=head)
    assert classify_failure(zero) == classify_failure(interrupted) == "infrastructure"
    assert zero.score.score_pct is None and not zero.score.passed
    assert (
        interrupted.score.killed,
        interrupted.score.survived,
        interrupted.score.incomplete_total,
    ) == (1, 1, 2)
    assert not interrupted.score.passed
    assert interrupted.provenance["stages"]["run"]["exit_code"] == 130
    assert "interrupted: current-invocation" in interrupted.results_text
    assert noop.score is None and noop.results_text == "" and noop.provenance is None


def test_zero_collection_exported_as_killed_never_becomes_valid_100(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, head = _repo(tmp_path)
    monkeypatch.setattr(driver, "_MUTMUT_CHILD", _CONTROLLED_PRODUCER)
    report = driver._run_scored(
        BaselineDecision("ok", head, "controlled no-collection counterexample"),
        ["src/des/invalid100.py"],
        80,
        repo=repo,
        head_sha=head,
    )
    assert classify_failure(report) == "infrastructure"
    assert report.provenance["raw_stats"] == {"total": 3, "killed": 3}
    assert report.provenance["native_counts"] == {"killed": 0, "survived": 0}
    assert report.score.killed == 0 and report.score.score_pct is None
    assert report.score.incomplete["unverified_test_observation"] == 3


def test_noop_issue_does_not_read_stale_shared_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mutation-results.txt").write_text("stale previous invocation")
    monkeypatch.setenv("GITHUB_SHA", "current-head")
    monkeypatch.setattr(driver, "_list_previous_runs", lambda *_: ([], True))
    report = tmp_path / "report.md"
    issue = tmp_path / "issue.md"
    evidence = tmp_path / "evidence.json"
    assert (
        driver.main(
            [
                "--workflow-name",
                "Fixture",
                "--report-path",
                str(report),
                "--issue-body-path",
                str(issue),
                "--evidence-path",
                str(evidence),
            ]
        )
        == 0
    )
    assert "stale previous invocation" not in issue.read_text()
    payload = json.loads(evidence.read_text())
    assert payload["score"] is None and payload["results_text"] == ""
    assert (
        tmp_path / "mutation-results.txt"
    ).read_text() == "stale previous invocation"
