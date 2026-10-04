"""Nightly delta adapter for this repository's pinned Python/mutmut runner.

Each attempt archives the exact head commit into a unique disposable workspace.
The ordinary pytest baseline and mutation stages share that snapshot, but never
caller configuration, build directories, caches or result files. Only explicitly
named report artifacts are written to the caller. This is not a native runner
framework: unsupported mutmut versions and unavailable evidence are indeterminate.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import sys
import tarfile
import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from des.runtime.spawn import spawn
from scripts.mutation.nightly_delta import (
    BaselineDecision,
    RunReport,
    WorkflowRun,
    bounded_issue_summary,
    bounded_results_excerpt,
    build_infrastructure_report,
    build_noop_report,
    build_scored_report,
    classify_failure,
    compute_score,
    issue_dedup_title,
    parse_cicd_stats,
    render_report,
    resolve_baseline,
    select_changed_python_files,
)


if TYPE_CHECKING:
    import subprocess


# Private mutmut configuration is installed only in a fresh child, never in the
# driver process. All stages use the same explicit scope, including exports.
_MUTMUT_CHILD = r"""
import dataclasses
import importlib.metadata
import json
import sys
import uuid
from pathlib import Path

version = importlib.metadata.version("mutmut")
if version != "3.8.0":
    raise RuntimeError(f"unsupported mutmut {version}; this adapter pins 3.8.0")
from mutmut import configuration
from mutmut import __main__ as runner
stage, encoded_scope = sys.argv[1:]
loaded_config = configuration._load_config()
# pspec rewrites nodeids even without --pspec. mutmut's focused selections
# cannot resolve those IDs; its worker converts usage errors to "killed".
# Isolate this reporting plugin only in this adapter's declared child recipe.
config = dataclasses.replace(
    loaded_config, only_mutate=json.loads(encoded_scope),
    pytest_add_cli_args=[*loaded_config.pytest_add_cli_args, "-p", "no:pspec"],
)
configuration._config = config

class Observation:
    def __init__(self):
        self.collected = 0
        self.call_reports = 0
        self.call_failures = 0
        self.errors = 0
        self.exit_code = None
    def pytest_collection_finish(self, session):
        self.collected = len(session.items)
    def pytest_runtest_logreport(self, report):
        if report.when == "call" and report.outcome != "skipped":
            self.call_reports += 1
            self.call_failures += int(report.outcome == "failed")
        elif report.outcome == "failed":
            self.errors += 1
    def pytest_sessionfinish(self, session, exitstatus):
        self.exit_code = int(exitstatus)

if stage == "baseline":
    import pytest
    observation = Observation()
    argv = config.pytest_add_cli_args + config.pytest_add_cli_args_test_selection
    code = int(pytest.main(argv, plugins=[observation]))
    Path("ordinary-baseline.json").write_text(json.dumps({
        **vars(observation), "exit_code": code,
        "argv": [sys.executable, "-m", "pytest", *argv], "mutmut_version": version,
        "cwd": str(Path.cwd()),
        "scope": config.only_mutate,
        "pytest_add_cli_args": config.pytest_add_cli_args,
        "pytest_add_cli_args_test_selection": config.pytest_add_cli_args_test_selection,
    }))
    sys.exit(code)
elif stage == "run":
    from mutmut.runners.harness import PytestRunner
    from mutmut.mutation.trampoline import get_mutant_under_test
    observations_dir = Path("native-observations").resolve()
    observations_dir.mkdir()
    original_execute = PytestRunner.execute_pytest
    def observed_execute(self, params, **kwargs):
        observation = Observation()
        kwargs["plugins"] = [*kwargs.get("plugins", []), observation]
        mutant = get_mutant_under_test()
        try:
            return original_execute(self, params, **kwargs)
        finally:
            (observations_dir / (uuid.uuid4().hex + ".json")).write_text(json.dumps({
                **vars(observation), "mutant": mutant,
                "cwd": str(Path.cwd()),
                "argv": [sys.executable, "-m", "pytest", *(["-vv"] if config.debug else []),
                         "--rootdir=.", "--tb=native", *params, *config.pytest_add_cli_args],
            }))
    PytestRunner.execute_pytest = observed_execute
    runner._run([], max_children=None)
elif stage == "export":
    runner.export_cicd_stats.callback()
elif stage == "results":
    runner.results.callback(all=True)
else:
    raise ValueError(stage)
"""


def _run(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return spawn(args, cwd=cwd, capture_output=True, text=True, check=False)


def _is_ancestor(candidate_sha: str, head_sha: str) -> bool:
    result = _run(["git", "merge-base", "--is-ancestor", candidate_sha, head_sha])
    return result.returncode == 0


def _list_previous_runs(
    repo: str, workflow_name: str
) -> tuple[list[WorkflowRun], bool]:
    result = _run(
        [
            "gh",
            "run",
            "list",
            "--repo",
            repo,
            "--workflow",
            workflow_name,
            "--status",
            "success",
            "--json",
            "headSha,conclusion,number,workflowName",
            "--limit",
            "20",
        ]
    )
    if result.returncode != 0:
        return [], False
    rows = json.loads(result.stdout or "[]")
    return [
        WorkflowRun(
            row["headSha"],
            row["conclusion"] or "success",
            row["workflowName"],
            row["number"],
        )
        for row in rows
    ], True


def _changed_paths(baseline_sha: str, head_sha: str) -> list[str]:
    result = _run(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=ACMR",
            f"{baseline_sha}..{head_sha}",
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(f"cannot measure mutation delta: {result.stderr.strip()}")
    return [line for line in result.stdout.splitlines() if line]


def _git_identity(repo: Path, expression: str) -> str:
    result = _run(["git", "rev-parse", "--verify", expression], cwd=repo)
    if result.returncode != 0:
        raise RuntimeError(f"cannot resolve {expression}: {result.stderr.strip()}")
    return result.stdout.strip()


def _workspace_env(root: Path) -> dict[str, str]:
    env = os.environ.copy()
    for name in ("PYTHONPATH", "PYTEST_ADDOPTS", "PYTEST_DEBUG", "MUTANT_UNDER_TEST"):
        env.pop(name, None)
    for name, directory in (
        ("TMPDIR", "tmp"),
        ("HOME", "home"),
        ("XDG_CACHE_HOME", "cache"),
        ("UV_CACHE_DIR", "uv-cache"),
        ("PYTHONPYCACHEPREFIX", "bytecode"),
    ):
        location = root / directory
        location.mkdir()
        env[name] = str(location)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    return env


def _run_mutmut_scoped(
    changed_files: list[str],
    workspace: Path,
    env: dict[str, str],
    stage: str,
) -> subprocess.CompletedProcess:
    """Invoke one bounded stage with child-local configuration and cwd."""
    return spawn(
        [sys.executable, "-c", _MUTMUT_CHILD, stage, json.dumps(changed_files)],
        cwd=workspace,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=3300,
        reap_process_group=True,
    )


def _run_scored(
    decision: BaselineDecision,
    changed: list[str],
    threshold: float,
    *,
    repo: Path | None = None,
    head_sha: str | None = None,
) -> RunReport:
    """Retain counts and provenance even if the isolated attempt fails."""
    if not changed:
        return build_noop_report(
            dataclasses.replace(decision, reason="no eligible changed Python files")
        )
    repo = (repo or Path.cwd()).resolve()
    provenance: dict[str, object] = {
        "invocation_id": uuid.uuid4().hex,
        "baseline_sha": decision.baseline_sha,
        "requested_files": list(changed),
        "python": sys.executable,
        "python_version": sys.version,
        "stages": {},
    }
    results_text = ""
    score = None
    errors: list[str] = []
    try:
        compute_score({}, threshold)  # validate policy before starting any tool
        head = _git_identity(repo, f"{head_sha or 'HEAD'}^{{commit}}")
        provenance["head_sha"] = head
        provenance["tree_sha"] = _git_identity(repo, f"{head}^{{tree}}")
        with tempfile.TemporaryDirectory(prefix="nwave-mutation-") as disposable:
            root = Path(disposable)
            workspace = root / "checkout"
            workspace.mkdir()
            archive = root / "source.tar"
            archived = _run(["git", "archive", f"--output={archive}", head], cwd=repo)
            if archived.returncode != 0:
                raise RuntimeError(
                    f"cannot archive mutation source: {archived.stderr.strip()}"
                )
            excluded_outputs = {
                "mutants",
                ".mutmut-cache",
                ".pytest_cache",
                "native-observations",
                "ordinary-baseline.json",
            }
            provenance["excluded_generated_paths"] = sorted(excluded_outputs)
            with tarfile.open(archive) as source:
                for member in source:
                    if Path(member.name).parts[0] not in excluded_outputs:
                        source.extract(member, workspace, filter="data")
            for rel in changed:
                target = workspace / rel
                if (
                    not target.resolve().is_relative_to(workspace)
                    or not target.is_file()
                    or target.suffix != ".py"
                ):
                    raise ValueError(
                        f"mutation target absent/unsafe in exact source snapshot: {rel}"
                    )
            provenance["source_sha256"] = {
                rel: hashlib.sha256((workspace / rel).read_bytes()).hexdigest()
                for rel in changed
            }
            # The immutable git tree includes test/support/config content, not
            # just the changed production files. No caller WIP is substituted.
            provenance["test_support_tree_sha"] = provenance["tree_sha"]
            provenance["workspace"] = str(workspace)
            env = _workspace_env(root)
            provenance["isolated_environment"] = {
                key: env.get(key)
                for key in (
                    "PATH",
                    "PYTHONPATH",
                    "PYTEST_ADDOPTS",
                    "PYTHONDONTWRITEBYTECODE",
                    "TMPDIR",
                    "HOME",
                    "XDG_CACHE_HOME",
                    "UV_CACHE_DIR",
                    "PYTHONPYCACHEPREFIX",
                )
            }
            stages = provenance["stages"]
            assert isinstance(stages, dict)

            def execute(stage: str) -> bool:
                nonlocal results_text
                try:
                    result = _run_mutmut_scoped(changed, workspace, env, stage)
                    stages[stage] = {
                        "exit_code": result.returncode,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "argv": result.args,
                        "cwd": str(workspace),
                    }
                    if stage == "results":
                        results_text = result.stdout or ""
                    if result.returncode != 0:
                        errors.append(f"mutmut {stage} failed (rc={result.returncode})")
                        return False
                    return True
                except (Exception, KeyboardInterrupt) as exc:
                    failure = exc

                    def captured(name: str) -> str | None:
                        value = getattr(failure, name, None)
                        return (
                            value.decode("utf-8", errors="replace")
                            if isinstance(value, bytes)
                            else value
                        )

                    stages[stage] = {
                        "interrupted_or_failed": type(exc).__name__,
                        "reason": str(exc),
                        "stdout": captured("stdout"),
                        "stderr": captured("stderr"),
                        "argv": [
                            sys.executable,
                            "-c",
                            _MUTMUT_CHILD,
                            stage,
                            json.dumps(changed),
                        ],
                        "cwd": str(workspace),
                    }
                    errors.append(
                        f"mutmut {stage} interrupted/failed: {type(exc).__name__}: {exc}"
                    )
                    return False

            baseline_ok = execute("baseline")
            baseline_path = workspace / "ordinary-baseline.json"
            if baseline_path.is_file():
                baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
                provenance["ordinary_baseline"] = baseline
                baseline_ok = (
                    baseline_ok
                    and baseline.get("exit_code") == 0
                    and baseline.get("collected", 0) > 0
                    and baseline.get("call_reports", 0) > 0
                    and baseline.get("errors", 0) == 0
                )
            else:
                baseline_ok = False
            if not baseline_ok:
                errors.append(
                    "ordinary pytest baseline is not observed GREEN with collected tests"
                )
            else:
                execute("run")
                # Export partial persisted metadata even after run failure. All
                # files are fresh in THIS workspace, never a previous checkout.
                execute("export")
                execute("results")
                stats_path = workspace / "mutants" / "mutmut-cicd-stats.json"
                if stats_path.is_file():
                    stats = json.loads(stats_path.read_text(encoding="utf-8"))
                    provenance["raw_stats"] = stats
                    reported_counts = parse_cicd_stats(stats)
                    reported_score = compute_score(reported_counts, threshold)
                    score = reported_score
                    observations = [
                        json.loads(path.read_text(encoding="utf-8"))
                        for path in sorted(
                            (workspace / "native-observations").glob("*.json")
                        )
                    ]
                    provenance["native_observations"] = observations
                    mutant_observations = [
                        observation
                        for observation in observations
                        if "__mutmut_" in observation.get("mutant", "")
                    ]
                    native_outcomes: dict[str, str] = {}
                    for observation in mutant_observations:
                        valid = (
                            observation.get("collected", 0) > 0
                            and observation.get("call_reports", 0) > 0
                            and observation.get("errors", 0) == 0
                            and (
                                (
                                    observation.get("exit_code") == 0
                                    and observation.get("call_failures", 0) == 0
                                )
                                or (
                                    observation.get("exit_code") == 1
                                    and observation.get("call_failures", 0) > 0
                                )
                            )
                        )
                        if valid:
                            native_outcomes[observation["mutant"]] = (
                                "killed"
                                if observation["exit_code"] == 1
                                else "survived"
                            )
                        else:
                            errors.append(
                                f"non-conclusive native test observation for {observation.get('mutant')}"
                            )
                    native_counts = {
                        "killed": sum(
                            outcome == "killed" for outcome in native_outcomes.values()
                        ),
                        "survived": sum(
                            outcome == "survived"
                            for outcome in native_outcomes.values()
                        ),
                    }
                    provenance["native_counts"] = native_counts
                    if (native_counts["killed"], native_counts["survived"]) != (
                        reported_score.killed,
                        reported_score.survived,
                    ):
                        errors.append(
                            "exported killed/survived counts disagree with authentic per-mutant test observations"
                        )
                    confirmed_counts = {**reported_counts, **native_counts}
                    missing = reported_score.scored_total - sum(native_counts.values())
                    if missing > 0:
                        confirmed_counts["unverified_test_observation"] = missing
                    score = compute_score(confirmed_counts, threshold)
                    if score.scored_total == 0:
                        errors.append("zero conclusive mutants in this invocation")
                    if score.has_incomplete:
                        errors.append(
                            "incomplete mutant observations in this invocation"
                        )
                else:
                    errors.append("no fresh mutation stats produced in this invocation")
    except (Exception, KeyboardInterrupt) as exc:
        errors.append(f"mutation attempt failed: {type(exc).__name__}: {exc}")
    if errors:
        if score is not None:
            score = dataclasses.replace(score, passed=False)
        report = build_infrastructure_report(
            decision, changed, "; ".join(errors), score
        )
    else:
        assert score is not None
        report = build_scored_report(decision, changed, score)
    return dataclasses.replace(report, provenance=provenance, results_text=results_text)


def _write_outputs(exit_class: str, issue_title: str, outcome: str) -> None:
    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as fh:
            fh.write(
                f"exit_class={exit_class}\nissue_title={issue_title}\noutcome={outcome}\n"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow-name", required=True)
    parser.add_argument("--report-path", required=True, type=Path)
    parser.add_argument("--issue-body-path", required=True, type=Path)
    parser.add_argument(
        "--results-path",
        type=Path,
        help="Explicit current-invocation results artifact.",
    )
    parser.add_argument(
        "--evidence-path",
        type=Path,
        help="Retained JSON provenance, stage output and counts.",
    )
    parser.add_argument("--threshold", type=float, default=80.0)
    args = parser.parse_args(argv)
    decision = BaselineDecision("query_failed", None, "baseline query not completed")
    try:
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        run_number_raw = os.environ.get("GITHUB_RUN_NUMBER", "")
        head_sha = os.environ.get("GITHUB_SHA") or _git_identity(
            Path.cwd(), "HEAD^{commit}"
        )
        exclude = int(run_number_raw) if run_number_raw.isdigit() else None
        runs, query_ok = _list_previous_runs(repo, args.workflow_name)
        if not query_ok:
            report = build_infrastructure_report(
                decision, [], "gh run list failed; no baseline inferred"
            )
        else:
            decision = resolve_baseline(
                runs, args.workflow_name, head_sha, _is_ancestor, exclude
            )
            if decision.status != "ok":
                report = build_noop_report(decision)
            else:
                changed = select_changed_python_files(
                    _changed_paths(decision.baseline_sha, head_sha),
                    lambda _: True,
                )
                if not changed:
                    report = build_noop_report(
                        dataclasses.replace(
                            decision, reason="no eligible changed Python files"
                        )
                    )
                else:
                    report = _run_scored(
                        decision, changed, args.threshold, head_sha=head_sha
                    )
    except (Exception, KeyboardInterrupt) as exc:
        report = build_infrastructure_report(
            decision, [], f"driver failed: {type(exc).__name__}: {exc}"
        )
    args.report_path.write_text(render_report(report), encoding="utf-8")
    issue_body = bounded_issue_summary(report)
    excerpt = bounded_results_excerpt(report.results_text)
    if excerpt:
        issue_body += f"\n\nCurrent invocation results:\n```\n{excerpt}\n```\n"
    args.issue_body_path.write_text(issue_body, encoding="utf-8")
    if args.results_path:
        args.results_path.write_text(report.results_text, encoding="utf-8")
    if args.evidence_path:
        args.evidence_path.write_text(
            json.dumps(dataclasses.asdict(report), indent=2) + "\n", encoding="utf-8"
        )
    failure = classify_failure(report)
    outcome = (
        "indeterminate"
        if failure == "infrastructure"
        else (
            "not-applicable" if report.score is None else "fail" if failure else "pass"
        )
    )
    _write_outputs(failure or "none", issue_dedup_title(args.workflow_name), outcome)
    return 0  # workflow publishes evidence before raising its explicit failure


if __name__ == "__main__":
    sys.exit(main())
