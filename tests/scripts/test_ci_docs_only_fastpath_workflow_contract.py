"""Structural contract for the docs-only fast path wired into .github/workflows/ci.yml.

Not an execution test (no runner available here) -- asserts plan owns
docs_only, test/worktree-topology are conditionally skipped off it, both
terminal aggregators (notify-slack, ci-success) require plan itself to
succeed while allowing exactly the four downstream skips under docs_only,
the schedule/workflow_dispatch classifier path stays fail-closed, and the
Publish exact-SHA gate in publish-experimental.yml is untouched.
"""

from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PUBLISH_PATH = REPO_ROOT / ".github" / "workflows" / "publish-experimental.yml"

CONDITIONAL_SKIPS = {"test", "worktree-topology", "coverage-combine", "agent-sync"}


def _jobs() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))["jobs"]


def _step(job: dict, name: str) -> dict:
    for step in job["steps"]:
        if step.get("name") == name:
            return step
    raise AssertionError(f"missing workflow step: {name}")


def test_plan_declares_docs_only_output_sourced_from_its_own_classifier_step() -> None:
    plan = _jobs()["plan"]
    assert plan["outputs"]["docs_only"] == "${{ steps.docs_only.outputs.docs_only }}"
    assert _step(plan, "Classify docs-only fast path")["id"] == "docs_only"


def test_classifier_step_is_fail_closed_for_schedule_and_workflow_dispatch() -> None:
    run = _step(_jobs()["plan"], "Classify docs-only fast path")["run"]
    assert (
        'if [ "$EVENT_NAME" = "schedule" ] || [ "$EVENT_NAME" = "workflow_dispatch" ]'
        in run
    )
    schedule_branch = run.split('workflow_dispatch" ]')[1].split("elif")[0]
    assert 'echo "docs_only=false"' in schedule_branch
    assert "no diffable base SHA" in run
    assert (
        'echo "docs_only=false"'
        in run.split("no diffable base SHA")[1].split("elif")[0]
    )


def test_test_and_worktree_topology_are_conditionally_skipped_on_docs_only() -> None:
    for name in ("test", "worktree-topology"):
        job = _jobs()[name]
        assert job["needs"] == ["plan"]
        assert job["if"] == "needs.plan.outputs.docs_only != 'true'"


def test_coverage_combine_and_agent_sync_cascade_skip_without_their_own_if() -> None:
    for name in ("coverage-combine", "agent-sync"):
        job = _jobs()[name]
        assert job["needs"] == ["test"]
        assert "if" not in job


def _allowed_skips_run(job_name: str, step_name: str) -> tuple[dict, str]:
    job = _jobs()[job_name]
    step = _step(job, step_name)
    return step, step["run"]


def test_notify_slack_and_ci_success_require_plan_and_expose_docs_only() -> None:
    for job_name in ("notify-slack", "ci-success"):
        job = _jobs()[job_name]
        assert "plan" in job["needs"]


def test_notify_slack_gates_plan_to_success_and_skips_exactly_the_four_under_docs_only() -> (
    None
):
    step, run = _allowed_skips_run("notify-slack", "Determine current status")
    assert step["env"]["DOCS_ONLY"] == "${{ needs.plan.outputs.docs_only }}"
    assert (
        'allowed_skips = {"contamination-guard"} if not guard_required else set()'
        in run
    )
    assert (
        'allowed_skips |= {"test", "worktree-topology", "coverage-combine", "agent-sync"}'
        in run
    )
    conditional_line = run.split("allowed_skips |=")[1].split("}")[0]
    named = {
        name.strip().strip('"') for name in conditional_line.split("{")[1].split(",")
    }
    assert named == CONDITIONAL_SKIPS
    assert '"plan"' not in run


def test_ci_success_gates_plan_to_success_and_skips_exactly_the_four_under_docs_only() -> (
    None
):
    step, run = _allowed_skips_run("ci-success", "Verify every gating job succeeded")
    assert step["env"]["DOCS_ONLY"] == "${{ needs.plan.outputs.docs_only }}"
    assert (
        'allowed_skips = {"contamination-guard"} if not guard_required else set()'
        in run
    )
    assert (
        'allowed_skips |= {"test", "worktree-topology", "coverage-combine", "agent-sync"}'
        in run
    )
    conditional_line = run.split("allowed_skips |=")[1].split("}")[0]
    named = {
        name.strip().strip('"') for name in conditional_line.split("{")[1].split(",")
    }
    assert named == CONDITIONAL_SKIPS
    assert '"plan"' not in run


def test_publish_experimental_ci_success_exact_sha_gate_is_untouched() -> None:
    publish = yaml.safe_load(PUBLISH_PATH.read_text(encoding="utf-8"))
    ci_gate = _step(
        publish["jobs"]["publish"],
        "Wait for successful CI Success on this exact commit",
    )
    assert ci_gate["env"] == {
        "GH_TOKEN": "${{ secrets.GITHUB_TOKEN }}",
        "REQUIRED_SHA": "${{ github.sha }}",
    }
    assert '"CI Success"' in ci_gate["run"] or "'CI Success'" in ci_gate["run"]
