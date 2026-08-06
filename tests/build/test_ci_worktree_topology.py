"""Static contract for the focused worktree CI topology check."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
MANIFEST_PATH = REPO_ROOT / ".github" / "ci" / "worktree-topology-tests.txt"
EXPECTED_TESTS = [
    "tests/installer/unit/plugins/test_attribution_plugin.py",
    "tests/installer/unit/shared/test_git_hooks_paths.py",
    "tests/installer/unit/git_workflow/test_commit_msg_hook.py",
    "tests/build/test_git_env_scrub_session_guard.py",
    "tests/build/test_precommit_fastgate_lock_scoped_per_worktree.py",
    "tests/des/unit/runtime/test_worktree_git_detection.py",
]


def _workflow() -> dict[str, object]:
    parsed = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def _plan_matrices() -> tuple[dict[str, object], dict[str, object], str]:
    workflow = _workflow()
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    plan = jobs["plan"]
    assert isinstance(plan, dict)
    steps = plan["steps"]
    assert isinstance(steps, list)
    plan_run = next(step["run"] for step in steps if step.get("id") == "set")
    encoded_matrices = re.findall(r"echo 'matrix=(\{.+?\})' >>", plan_run)
    assert len(encoded_matrices) == 2
    scheduled, push_pr = (json.loads(matrix) for matrix in encoded_matrices)
    return scheduled, push_pr, plan_run


def test_push_pr_matrix_avoids_full_worktree_suite_but_scheduled_sweep_keeps_it() -> (
    None
):
    scheduled, push_pr, plan_run = _plan_matrices()

    assert 'github.event_name }}" == "schedule"' in plan_run
    assert 'github.event_name }}" == "workflow_dispatch"' in plan_run
    assert scheduled == {
        "os": ["ubuntu-latest"],
        "python-version": ["3.10", "3.11", "3.12", "3.13", "3.14"],
        "git_topology": ["main_checkout", "worktree"],
        "shard": [1, 2, 3, 4],
    }
    assert push_pr == {
        "os": ["ubuntu-latest"],
        "python-version": ["3.12"],
        "git_topology": ["main_checkout"],
        "shard": [1, 2, 3, 4],
    }
    assert 5 * 2 * 4 == 40
    assert 1 * 1 * 4 == 4


def test_worktree_topology_job_runs_exact_audited_contract_without_heavy_artifacts() -> (
    None
):
    workflow = _workflow()
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    job = jobs["worktree-topology"]
    assert isinstance(job, dict)
    assert job["needs"] == ["plan"]
    assert job["runs-on"] == "ubuntu-latest"
    assert "if" not in job

    steps = job["steps"]
    assert isinstance(steps, list)
    run_text = "\n".join(
        step["run"] for step in steps if isinstance(step, dict) and "run" in step
    )
    assert "git worktree add" in run_text
    assert "from scripts.shared.git_hooks_paths import resolve_hooks_dir" in run_text
    assert "dest = resolve_hooks_dir() / 'commit-msg'" in run_text
    assert "shutil.copy(validator, dest.parent / validator.name)" in run_text
    assert "commit -m 'invalid hook probe'" in run_text
    # The literal must be what scripts/hooks/commit_msg.py actually PRINTS.
    # It printed a lowercase "does"; the job grepped for a capital "D" with
    # grep -F, so the match never fired and the job failed on every run. This
    # assertion agreed with the YAML rather than with the hook, which is why it
    # could not catch that.
    assert (
        "ERROR: Commit message does not follow Conventional Commits format." in run_text
    )
    assert 'test "$(git rev-parse HEAD)" = "$before_head"' in run_text
    assert 'git diff --cached --name-only | grep -Fx "$proof_file"' in run_text
    assert "commit -m 'test(ci): prove worktree commit-msg hook'" in run_text
    assert "git reset --hard HEAD~1" in run_text
    assert 'test ! -e "$proof_file"' in run_text
    assert (
        "mapfile -t audited_tests < .github/ci/worktree-topology-tests.txt" in run_text
    )
    assert 'uv run pytest "${audited_tests[@]}" --tb=short' in run_text
    for forbidden in ("--splits", "--cov", "--html", "--alluredir"):
        assert forbidden not in run_text

    assert MANIFEST_PATH.read_text(encoding="utf-8").splitlines() == EXPECTED_TESTS


def test_terminal_and_notification_gates_include_identity_and_conditional_guard() -> (
    None
):
    workflow = _workflow()
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    for job_name in ("ci-success", "notify-slack"):
        job = jobs[job_name]
        assert isinstance(job, dict)
        assert {
            "worktree-topology",
            "commit-author-validation",
            "contamination-guard",
        } <= set(job["needs"])

    terminal = jobs["ci-success"]
    assert isinstance(terminal, dict)
    terminal_step = terminal["steps"][0]
    terminal_run = terminal_step["run"]
    assert "CONTAMINATION_GUARD_REQUIRED" in terminal_run
    assert (
        'allowed_skips = {"contamination-guard"} if not guard_required else set()'
        in terminal_run
    )
    assert (
        'name in allowed_skips and context.get("result") == "skipped"' in terminal_run
    )
    assert terminal_step["env"]["CONTAMINATION_GUARD_REQUIRED"] == (
        "${{ github.ref == 'refs/heads/master' || github.base_ref == 'master' }}"
    )

    slack = jobs["notify-slack"]
    assert isinstance(slack, dict)
    slack_step = next(
        step for step in slack["steps"] if step.get("id") == "current-status"
    )
    assert "CONTAMINATION_GUARD_REQUIRED" in slack_step["run"]
    assert (
        'allowed_skips = {"contamination-guard"} if not guard_required else set()'
        in slack_step["run"]
    )
    assert (
        'name in allowed_skips and context.get("result") == "skipped"'
        in slack_step["run"]
    )
    assert (
        slack_step["env"]["CONTAMINATION_GUARD_REQUIRED"]
        == terminal_step["env"]["CONTAMINATION_GUARD_REQUIRED"]
    )


def test_conditional_contamination_skip_policy_covers_feature_and_master_paths() -> (
    None
):
    def guard_required(github_ref: str, base_ref: str) -> bool:
        return github_ref == "refs/heads/master" or base_ref == "master"

    def non_success(guard_result: str, guard_required: bool) -> list[str]:
        allowed_skips = {"contamination-guard"} if not guard_required else set()
        results = {"contamination-guard": {"result": guard_result}}
        return [
            name
            for name, context in results.items()
            if context["result"] != "success"
            and not (name in allowed_skips and context["result"] == "skipped")
        ]

    assert non_success("skipped", guard_required("refs/heads/feature/fast", "")) == []
    assert non_success("failure", guard_required("refs/heads/feature/fast", "")) == [
        "contamination-guard"
    ]
    assert non_success("skipped", guard_required("refs/heads/master", "")) == [
        "contamination-guard"
    ]
    assert non_success("skipped", guard_required("refs/pull/42/merge", "master")) == [
        "contamination-guard"
    ]
