"""Dense unit tests for scripts/mutation/nightly_delta.py.

All functions under test are pure — no git repo, no filesystem, no network
required. Fixtures inject fakes for exists_fn/is_ancestor_fn.
"""

from __future__ import annotations

import pytest

from scripts.mutation.nightly_delta import (
    DEFAULT_SOURCE_SCOPES,
    BaselineDecision,
    WorkflowRun,
    bounded_issue_summary,
    build_noop_report,
    build_scored_report,
    classify_failure,
    compute_score,
    is_eligible_source_path,
    issue_dedup_title,
    parse_cicd_stats,
    render_report,
    resolve_baseline,
    select_changed_python_files,
    select_previous_successful_run,
)


WORKFLOW = "Nightly Delta Mutation"


# ---------------------------------------------------------------------------
# is_eligible_source_path / select_changed_python_files
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("src/des/foo.py", True),
        ("src/des/sub/bar.py", True),
        ("src/des/testarch/x.py", True),
        ("scripts/install/installer.py", True),
        ("src/desnot/foo.py", False),  # prefix collision, not a real scope boundary
        ("src/des/foo.txt", False),  # wrong extension
        ("docs/feature/x/design/foo.py", False),  # outside all scopes
        ("scripts/mutation/nightly_delta.py", False),  # scripts/mutation not in scope
    ],
)
def test_is_eligible_source_path(path: str, expected: bool) -> None:
    assert is_eligible_source_path(path, DEFAULT_SOURCE_SCOPES) is expected


def test_select_changed_python_files_filters_scope_extension_and_existence() -> None:
    changed = [
        "src/des/foo.py",  # eligible + exists
        "src/des/deleted.py",  # eligible scope/ext but deleted -> excluded
        "src/desnot/bar.py",  # wrong scope -> excluded
        "src/des/notes.md",  # wrong extension -> excluded
        "src/des/foo.py",  # duplicate -> deduped
    ]
    exists = {"src/des/foo.py"}.__contains__
    result = select_changed_python_files(changed, exists)
    assert result == ["src/des/foo.py"]


def test_select_changed_python_files_empty_input_is_empty_output() -> None:
    assert select_changed_python_files([], lambda _p: True) == []


def test_select_changed_python_files_is_sorted_deterministic() -> None:
    changed = ["src/des/z.py", "src/des/a.py", "src/des/m.py"]
    result = select_changed_python_files(changed, lambda _p: True)
    assert result == ["src/des/a.py", "src/des/m.py", "src/des/z.py"]


# ---------------------------------------------------------------------------
# select_previous_successful_run / resolve_baseline
# ---------------------------------------------------------------------------


def test_select_previous_successful_run_picks_highest_run_number() -> None:
    runs = [
        WorkflowRun("sha1", "success", WORKFLOW, 1),
        WorkflowRun("sha3", "success", WORKFLOW, 3),
        WorkflowRun("sha2", "success", WORKFLOW, 2),
    ]
    result = select_previous_successful_run(runs, WORKFLOW)
    assert result == WorkflowRun("sha3", "success", WORKFLOW, 3)


def test_select_previous_successful_run_excludes_current_run_number() -> None:
    runs = [
        WorkflowRun("sha3", "success", WORKFLOW, 3),
        WorkflowRun("sha2", "success", WORKFLOW, 2),
    ]
    result = select_previous_successful_run(runs, WORKFLOW, exclude_run_number=3)
    assert result == WorkflowRun("sha2", "success", WORKFLOW, 2)


def test_select_previous_successful_run_ignores_other_workflow_and_failed() -> None:
    runs = [
        WorkflowRun("sha1", "failure", WORKFLOW, 5),
        WorkflowRun("sha2", "success", "Other Workflow", 6),
    ]
    assert select_previous_successful_run(runs, WORKFLOW) is None


def test_select_previous_successful_run_no_candidates_returns_none() -> None:
    assert select_previous_successful_run([], WORKFLOW) is None


def test_resolve_baseline_first_run_when_no_prior_success() -> None:
    decision = resolve_baseline([], WORKFLOW, "headsha", lambda a, b: True)
    assert decision.status == "first_run"
    assert decision.baseline_sha is None


def test_resolve_baseline_non_ancestor_when_history_rewritten() -> None:
    runs = [WorkflowRun("oldsha", "success", WORKFLOW, 1)]
    decision = resolve_baseline(runs, WORKFLOW, "headsha", lambda a, b: False)
    assert decision.status == "non_ancestor"
    assert decision.baseline_sha == "oldsha"


def test_resolve_baseline_ok_when_ancestor_validated() -> None:
    runs = [WorkflowRun("oldsha", "success", WORKFLOW, 1)]
    decision = resolve_baseline(runs, WORKFLOW, "headsha", lambda a, b: True)
    assert decision == BaselineDecision("ok", "oldsha", "validated ancestor")


def test_resolve_baseline_is_deterministic_given_same_inputs() -> None:
    runs = [WorkflowRun("oldsha", "success", WORKFLOW, 1)]
    d1 = resolve_baseline(runs, WORKFLOW, "headsha", lambda a, b: True)
    d2 = resolve_baseline(runs, WORKFLOW, "headsha", lambda a, b: True)
    assert d1 == d2


# ---------------------------------------------------------------------------
# parse_cicd_stats — mutmut 3.6 export-cicd-stats JSON, conservative remainder
# ---------------------------------------------------------------------------


def test_parse_cicd_stats_passes_through_known_nonzero_keys() -> None:
    stats = {"total": 10, "killed": 7, "survived": 3}
    assert parse_cicd_stats(stats) == {"killed": 7, "survived": 3}


def test_parse_cicd_stats_unaccounted_total_becomes_not_checked() -> None:
    # total=10 but only 6 accounted for (4 killed + 2 survived) -> 4 not_checked.
    stats = {"total": 10, "killed": 4, "survived": 2}
    assert parse_cicd_stats(stats) == {"killed": 4, "survived": 2, "not_checked": 4}


def test_parse_cicd_stats_missing_total_never_yields_negative_not_checked() -> None:
    assert parse_cicd_stats({"killed": 5}) == {"killed": 5}


# ---------------------------------------------------------------------------
# compute_score — conservative scoring, no inflation from incomplete statuses
# ---------------------------------------------------------------------------


def test_compute_score_pure_killed_survived() -> None:
    result = compute_score({"killed": 90, "survived": 10})
    assert result.score_pct == pytest.approx(90.0)
    assert result.passed is True
    assert result.has_incomplete is False


def test_compute_score_below_threshold_fails() -> None:
    result = compute_score({"killed": 79, "survived": 21})
    assert result.score_pct == pytest.approx(79.0)
    assert result.passed is False


@pytest.mark.parametrize(
    "incomplete_status",
    [
        "error",
        "not_checked",
        "no_tests",
        "suspicious",
        "timeout",
        "check_was_interrupted",
        "segfault",
    ],
)
def test_compute_score_incomplete_statuses_never_inflate_score(
    incomplete_status: str,
) -> None:
    # 5 killed / 5 survived == 50% on the conclusive subset; a large incomplete
    # count must not move score_pct up toward passing.
    counts = {"killed": 5, "survived": 5, incomplete_status: 1000}
    result = compute_score(counts, threshold=80.0)
    assert result.score_pct == pytest.approx(50.0)
    assert result.passed is False
    assert result.has_incomplete is True
    assert result.incomplete[incomplete_status] == 1000


def test_compute_score_unknown_status_is_treated_as_incomplete_conservatively() -> None:
    result = compute_score({"killed": 10, "totally_unrecognized_status": 3})
    assert result.score_pct == pytest.approx(100.0)  # 10 killed / 10 scored
    assert result.has_incomplete is True
    assert result.incomplete["totally_unrecognized_status"] == 3


def test_compute_score_no_conclusive_mutants_yields_none_score_and_fails() -> None:
    result = compute_score({"no_tests": 4})
    assert result.score_pct is None
    assert result.passed is False


def test_compute_score_zero_counts_is_none_score() -> None:
    result = compute_score({})
    assert result.score_pct is None
    assert result.scored_total == 0


def test_compute_score_exact_threshold_boundary_passes() -> None:
    result = compute_score({"killed": 80, "survived": 20}, threshold=80.0)
    assert result.score_pct == pytest.approx(80.0)
    assert result.passed is True


# ---------------------------------------------------------------------------
# report / issue rendering + failure classification
# ---------------------------------------------------------------------------


def test_build_noop_report_and_render_first_run() -> None:
    decision = BaselineDecision("first_run", None, "no prior successful run")
    report = build_noop_report(decision)
    rendered = render_report(report)
    assert "first_run" in rendered
    assert "no prior successful run" in rendered
    assert classify_failure(report) is None  # no-op is always success


def test_build_noop_report_non_ancestor_never_triggers_full_repo_fallback() -> None:
    decision = BaselineDecision("non_ancestor", "oldsha", "history rewritten")
    report = build_noop_report(decision)
    assert report.changed_files == ()
    assert report.score is None
    assert classify_failure(report) is None


def test_build_scored_report_render_includes_all_changed_files() -> None:
    decision = BaselineDecision("ok", "basesha", "validated ancestor")
    score = compute_score({"killed": 100, "survived": 0})
    report = build_scored_report(decision, ["src/des/a.py", "src/des/b.py"], score)
    rendered = render_report(report)
    assert "src/des/a.py" in rendered
    assert "src/des/b.py" in rendered
    assert "100.0%" in rendered


def test_classify_failure_infrastructure_takes_priority_over_below_threshold() -> None:
    decision = BaselineDecision("ok", "basesha", "validated ancestor")
    # 0 killed / 0 survived but a huge error count: below threshold AND incomplete.
    score = compute_score({"error": 50})
    report = build_scored_report(decision, ["src/des/a.py"], score)
    assert classify_failure(report) == "infrastructure"


def test_classify_failure_below_threshold_when_conclusive_but_low() -> None:
    decision = BaselineDecision("ok", "basesha", "validated ancestor")
    score = compute_score({"killed": 50, "survived": 50})
    report = build_scored_report(decision, ["src/des/a.py"], score)
    assert classify_failure(report) == "below_threshold"


def test_classify_failure_none_when_passing_and_complete() -> None:
    decision = BaselineDecision("ok", "basesha", "validated ancestor")
    score = compute_score({"killed": 90, "survived": 10})
    report = build_scored_report(decision, ["src/des/a.py"], score)
    assert classify_failure(report) is None


def test_bounded_issue_summary_truncates_long_file_lists() -> None:
    decision = BaselineDecision("ok", "basesha", "validated ancestor")
    score = compute_score({"killed": 1, "survived": 99})
    files = [f"src/des/f{i}.py" for i in range(15)]
    report = build_scored_report(decision, files, score)
    body = bounded_issue_summary(report, max_files=10)
    assert "f0.py" in body
    assert "f9.py" in body
    assert "f14.py" not in body
    assert "and 5 more" in body


def test_bounded_issue_summary_noop_is_short() -> None:
    decision = BaselineDecision("first_run", None, "no prior successful run")
    report = build_noop_report(decision)
    body = bounded_issue_summary(report)
    assert "No-op run" in body


def test_issue_dedup_title_is_stable_for_same_workflow() -> None:
    assert issue_dedup_title(WORKFLOW) == issue_dedup_title(WORKFLOW)
    assert WORKFLOW in issue_dedup_title(WORKFLOW)
