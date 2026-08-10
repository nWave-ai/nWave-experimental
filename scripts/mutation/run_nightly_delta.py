"""CLI driver for nightly delta mutation testing.

Thin orchestration only: all decision logic (baseline selection, ancestor
validation, file scoping, scoring, report/issue rendering) lives in the pure
`scripts.mutation.nightly_delta` module and is unit-tested there. This module
wires that logic to git/gh/mutmut subprocess calls and writes the
workflow-facing artifacts (report file, issue-body file, mutation results
file, $GITHUB_OUTPUT).

Never rewrites pyproject.toml or any checked-out file other than the report
artifacts named on the CLI. mutmut 3.6's `run` command has no
`--paths-to-mutate` (or any other dynamic-scope) CLI flag — scoping to the
exact changed-file list is config-only (`only_mutate`), so `_run_mutmut_scoped`
below overrides that one field on an in-memory Config, never the checkout.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    import subprocess

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


STATS_PATH = Path("mutants/mutmut-cicd-stats.json")
RESULTS_PATH = Path("mutation-results.txt")


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return spawn(
        args,
        capture_output=True,
        text=True,
        check=False,
    )


def _is_ancestor(candidate_sha: str, head_sha: str) -> bool:
    result = _run(["git", "merge-base", "--is-ancestor", candidate_sha, head_sha])
    return result.returncode == 0


def _list_previous_runs(
    repo: str, workflow_name: str
) -> tuple[list[WorkflowRun], bool]:
    """Query prior successful runs of `workflow_name`.

    Returns (runs, query_ok). query_ok is False only when the `gh` call
    itself failed (nonzero exit) — a FAILED query is never resolved as
    "first_run": an unanswered "were there prior runs?" is not evidence of
    "there were none" (see BaselineDecision docstring). A successful query
    that simply returns zero rows IS a legitimate first_run, and reports
    query_ok=True with an empty list.
    """
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
    if not result.stdout.strip():
        return [], True
    rows = json.loads(result.stdout)
    return [
        WorkflowRun(
            sha=row["headSha"],
            conclusion=row["conclusion"] or "success",
            workflow_name=row["workflowName"],
            run_number=row["number"],
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
        return []
    return [line for line in result.stdout.splitlines() if line]


def _run_mutmut_scoped(changed_files: list[str]) -> None:
    """Run mutmut 3.6 scoped to exactly `changed_files`, preserving the checkout.

    mutmut 3.6's `run` CLI accepts only positional MUTANT_NAMES and
    `--max-children` — there is no `--paths-to-mutate` (or any other
    dynamic-scope) flag, and rewriting `pyproject.toml` on disk would mutate
    the checked-out tree. Dynamic path selection is config-only
    (`Config.only_mutate`), so this loads the normal Config via
    `mutmut.configuration._load_config`, overrides only that field with the
    exact changed-file list, installs it as `mutmut.configuration._config`
    (the module-level cache `Config.get()` reads), and calls the
    documented-in-source `mutmut.__main__._run([], max_children=None)`
    directly — the same entry point the `run` CLI command itself dispatches
    to.

    This is a private API pinned to mutmut==3.6 (see pyproject.toml). It is
    isolated in this one small function and fails loudly (RuntimeError) if
    the seam is unavailable, rather than silently falling back to an
    unscoped or full-repo run.
    """
    try:
        from mutmut import configuration
        from mutmut.__main__ import _run as mutmut_run
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError(
            "mutmut 3.6 programmatic run seam unavailable "
            "(mutmut.configuration._load_config / mutmut.__main__._run) — "
            "this repo pins mutmut==3.6.0; an upgrade changed the private "
            "API this driver depends on. Fix: re-verify mutmut.configuration "
            "and mutmut.__main__ internals against the installed version and "
            "update _run_mutmut_scoped."
        ) from exc
    try:
        scoped_config = dataclasses.replace(
            configuration._load_config(), only_mutate=list(changed_files)
        )
    except (AttributeError, TypeError) as exc:
        raise RuntimeError(
            "mutmut 3.6 configuration seam drifted (_load_config missing or "
            "Config has no 'only_mutate' field) — re-verify "
            "mutmut.configuration against the pinned version and update "
            "_run_mutmut_scoped."
        ) from exc
    configuration._config = scoped_config
    mutmut_run([], max_children=None)


def _run_scored(
    decision: BaselineDecision, changed: list[str], threshold: float
) -> RunReport:
    """Run mutmut for `changed`, export/parse stats, and score conservatively.

    Any nonzero mutmut run/export/results exit, a missing or malformed stats
    file, or a scored run with zero conclusive (killed+survived) mutants is
    an infrastructure failure — never a silently empty/zero score.
    """
    try:
        _run_mutmut_scoped(changed)
    except Exception as exc:
        return build_infrastructure_report(
            decision, changed, f"mutmut run failed: {exc}"
        )

    export = _run(["mutmut", "export-cicd-stats"])
    if export.returncode != 0:
        return build_infrastructure_report(
            decision,
            changed,
            f"mutmut export-cicd-stats failed (rc={export.returncode}): "
            f"{export.stderr.strip()[:500]}",
        )

    results = _run(["mutmut", "results"])
    RESULTS_PATH.write_text(results.stdout or "", encoding="utf-8")
    if results.returncode != 0:
        return build_infrastructure_report(
            decision, changed, f"mutmut results failed (rc={results.returncode})"
        )

    if not STATS_PATH.exists():
        return build_infrastructure_report(
            decision, changed, f"{STATS_PATH} missing after export-cicd-stats"
        )
    try:
        stats = json.loads(STATS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return build_infrastructure_report(
            decision, changed, f"malformed {STATS_PATH}: {exc}"
        )

    counts = parse_cicd_stats(stats)
    score = compute_score(counts, threshold=threshold)
    if score.scored_total == 0:
        return build_infrastructure_report(
            decision,
            changed,
            "zero conclusive (killed+survived) mutants with eligible changed files",
        )
    return build_scored_report(decision, changed, score)


def _write_outputs(exit_class: str, issue_title: str) -> None:
    gh_output = os.environ.get("GITHUB_OUTPUT")
    if not gh_output:
        return
    with open(gh_output, "a", encoding="utf-8") as fh:
        fh.write(f"exit_class={exit_class}\n")
        fh.write(f"issue_title={issue_title}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow-name", required=True)
    parser.add_argument("--report-path", required=True, type=Path)
    parser.add_argument("--issue-body-path", required=True, type=Path)
    parser.add_argument("--threshold", type=float, default=80.0)
    args = parser.parse_args(argv)

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    run_number_raw = os.environ.get("GITHUB_RUN_NUMBER", "")
    head_sha = os.environ.get("GITHUB_SHA", "")
    exclude_run_number = int(run_number_raw) if run_number_raw.isdigit() else None

    runs, query_ok = _list_previous_runs(repo, args.workflow_name)

    if not query_ok:
        decision = BaselineDecision(
            status="query_failed",
            baseline_sha=None,
            reason=(
                f"gh run list --workflow {args.workflow_name!r} failed; "
                "a failed query is not evidence of a first run"
            ),
        )
        report = build_infrastructure_report(decision, [], decision.reason)
    else:
        decision = resolve_baseline(
            runs, args.workflow_name, head_sha, _is_ancestor, exclude_run_number
        )
        if decision.status != "ok":
            report = build_noop_report(decision)
        else:
            changed = select_changed_python_files(
                _changed_paths(decision.baseline_sha, head_sha), os.path.exists
            )
            if not changed:
                report = build_noop_report(
                    BaselineDecision(
                        status="ok",
                        baseline_sha=decision.baseline_sha,
                        reason="no eligible changed Python files under configured source scopes",
                    )
                )
            else:
                report = _run_scored(decision, changed, args.threshold)

    args.report_path.write_text(render_report(report), encoding="utf-8")

    issue_body = bounded_issue_summary(report)
    if RESULTS_PATH.exists():
        excerpt = bounded_results_excerpt(RESULTS_PATH.read_text(encoding="utf-8"))
        if excerpt:
            issue_body += f"\n\nResults excerpt (full results in the uploaded artifact):\n```\n{excerpt}\n```\n"
    args.issue_body_path.write_text(issue_body, encoding="utf-8")

    failure_class = classify_failure(report)
    _write_outputs(failure_class or "none", issue_dedup_title(args.workflow_name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
