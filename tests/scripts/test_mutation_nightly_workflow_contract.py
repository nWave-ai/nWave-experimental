"""Structural contract tests for .github/workflows/mutation-nightly.yml.

Not an execution test (no runner available here) — asserts the YAML shape
that scripts/mutation/nightly_delta.py and run_nightly_delta.py depend on:
triggers, least-privilege permissions, pinned actions, and that evidence
(artifact upload) plus the dedup issue create/update both precede the final
threshold/infrastructure failure step.
"""

from __future__ import annotations

from pathlib import Path

import yaml


WORKFLOW_PATH = Path(".github/workflows/mutation-nightly.yml")


def _load() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def test_workflow_file_exists() -> None:
    assert WORKFLOW_PATH.is_file()


def test_triggers_are_schedule_and_workflow_dispatch() -> None:
    doc = _load()
    triggers = (
        doc[True] if True in doc else doc["on"]
    )  # YAML 1.1 quirk: bare `on` -> True key
    assert "schedule" in triggers
    assert "workflow_dispatch" in triggers
    assert triggers["schedule"][0]["cron"]


def test_permissions_are_least_privilege() -> None:
    doc = _load()
    assert doc["permissions"] == {
        "contents": "read",
        "actions": "read",
        "issues": "write",
    }


def test_single_job_defined() -> None:
    doc = _load()
    assert "delta-mutation" in doc["jobs"]


def _steps() -> list[dict]:
    doc = _load()
    return doc["jobs"]["delta-mutation"]["steps"]


def test_actions_are_pinned_to_a_version_tag() -> None:
    for step in _steps():
        uses = step.get("uses")
        if uses is None:
            continue
        assert "@" in uses, f"unpinned action: {uses}"
        action, _, ref = uses.partition("@")
        assert ref, f"action {action} has an empty ref"


def test_checkout_step_present_and_pinned_convention() -> None:
    checkout = next(
        s for s in _steps() if s.get("uses", "").startswith("actions/checkout@")
    )
    assert checkout["uses"] == "actions/checkout@v7"


def test_upload_artifact_step_runs_always() -> None:
    upload = next(
        s for s in _steps() if s.get("uses", "").startswith("actions/upload-artifact@")
    )
    assert upload.get("if") == "always()"


def test_upload_artifact_includes_mutation_results_txt() -> None:
    upload = next(
        s for s in _steps() if s.get("uses", "").startswith("actions/upload-artifact@")
    )
    assert "mutation-results.txt" in upload["with"]["path"]


def _step_index(name_substring: str) -> int:
    for i, step in enumerate(_steps()):
        if name_substring.lower() in step.get("name", "").lower():
            return i
    raise AssertionError(f"no step found matching {name_substring!r}")


def test_artifact_upload_precedes_final_failure_step() -> None:
    assert _step_index("Upload mutation report") < _step_index("Fail loudly")


def test_issue_dedup_step_precedes_final_failure_step() -> None:
    assert _step_index("Create or update triage issue") < _step_index("Fail loudly")


def test_delta_run_step_has_continue_on_error() -> None:
    steps = _steps()
    delta_step = next(s for s in steps if s.get("id") == "delta")
    assert delta_step.get("continue-on-error") is True


def test_final_failure_step_gates_on_threshold_or_infrastructure_only() -> None:
    steps = _steps()
    fail_step = next(s for s in steps if "Fail loudly" in s.get("name", ""))
    condition = fail_step["if"]
    assert "below_threshold" in condition
    assert "infrastructure" in condition
    assert fail_step["run"].strip().endswith("exit 1")


def test_no_full_repo_or_hidden_checkout_mutation_markers() -> None:
    raw = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "git commit" not in raw
    assert "git push" not in raw
    assert "--full-repo" not in raw


def test_issue_create_does_not_require_a_pre_existing_label() -> None:
    raw = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "--label" not in raw


def test_existing_issue_is_updated_via_edit_not_only_commented() -> None:
    raw = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "gh issue edit" in raw


def test_issue_dedup_selects_by_exact_title_equality() -> None:
    steps = _steps()
    issue_step = next(
        s for s in steps if s.get("name") == "Create or update triage issue"
    )
    run = issue_step["run"]
    # Must NOT use the invalid --jq --arg form (gh --jq cannot forward jq args)
    assert "--jq --arg" not in run
    assert "--jq" not in run.split("--json")[1].split("|")[0], (
        "--jq must not appear between --json and the pipe"
    )
    # Must use the valid pipe-to-jq form with --arg
    assert "| jq --arg title" in run
    assert "select(.title == $title)" in run


def test_delta_step_falls_back_to_infrastructure_exit_class_on_nonzero_rc() -> None:
    steps = _steps()
    delta_step = next(s for s in steps if s.get("id") == "delta")
    run = delta_step["run"]
    assert "GITHUB_OUTPUT" in run
    assert "exit_class=infrastructure" in run
    # The wrapper must itself exit 0 so downstream evidence/issue steps run
    # even when the driver crashed.
    assert run.strip().endswith("exit 0")
