"""Structural contracts for the experimental and dev release entry points."""

from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTAL = REPO_ROOT / ".github" / "workflows" / "publish-experimental.yml"
RELEASE_DEV = REPO_ROOT / ".github" / "workflows" / "release-dev.yml"
WORKFLOW_README = REPO_ROOT / ".github" / "workflows" / "README.md"
PUBLISHER = REPO_ROOT / "scripts" / "release" / "publish_experimental.py"
SOURCE_BRANCH = "feature/atdd-pure-staging"


def _workflow(path: Path) -> dict[str, object]:
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def _step(workflow: dict[str, object], name: str) -> dict[str, object]:
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    publish = jobs["publish"]
    assert isinstance(publish, dict)
    steps = publish["steps"]
    assert isinstance(steps, list)
    for step in steps:
        if isinstance(step, dict) and step.get("name") == name:
            return step
    raise AssertionError(f"missing workflow step: {name}")


def test_experimental_dispatch_and_permissions_are_narrow() -> None:
    workflow = _workflow(EXPERIMENTAL)
    trigger = workflow[True]  # PyYAML resolves the YAML 1.1 key `on` as True.
    assert trigger["push"]["branches"] == [SOURCE_BRANCH]
    assert trigger["workflow_dispatch"] is None
    assert workflow["permissions"] == {"contents": "read", "actions": "read"}

    branch_guard = _step(
        workflow, "Refuse a source branch other than atdd-pure staging"
    )
    assert branch_guard["env"]["EVENT_REF_NAME"] == "${{ github.ref_name }}"
    assert '"$EVENT_REF_NAME" != "$SOURCE_BRANCH"' in branch_guard["run"]


def test_experimental_publish_requires_exact_sha_terminal_ci_success() -> None:
    workflow = _workflow(EXPERIMENTAL)
    ci_gate = _step(workflow, "Wait for successful CI Success on this exact commit")
    assert ci_gate["env"] == {
        "GH_TOKEN": "${{ secrets.GITHUB_TOKEN }}",
        "REQUIRED_SHA": "${{ github.sha }}",
    }
    run = ci_gate["run"]

    assert "readonly MAX_ATTEMPTS=180" in run
    assert "readonly WAIT_SECONDS=20" in run
    assert "--workflow ci.yml" in run
    assert '--commit "$REQUIRED_SHA"' in run
    assert 'gh run view "$run_id" --json status,conclusion,jobs' in run
    assert '.conclusion == "success"' in run
    assert '.name == "CI Success"' in run
    assert '$terminal[0].status == "completed"' in run
    assert '$terminal[0].conclusion == "success"' in run


def test_dev_release_refuses_non_master_before_ci_or_release_work() -> None:
    workflow = _workflow(RELEASE_DEV)
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    gate = jobs["branch-gate"]
    assert gate["name"] == "Master Source Gate"
    assert gate["steps"][0]["env"]["EVENT_REF_NAME"] == "${{ github.ref_name }}"
    assert '"$EVENT_REF_NAME" != "master"' in gate["steps"][0]["run"]
    assert jobs["ci-gate"]["needs"] == ["branch-gate"]


def test_experimental_publisher_and_workflow_docs_describe_public_target() -> None:
    publisher = PUBLISHER.read_text(encoding="utf-8")
    readme = WORKFLOW_README.read_text(encoding="utf-8")

    assert "nWave-ai/nWave-experimental" in publisher
    assert "target: {TARGET_SLUG}@{TARGET_BRANCH}  (PUBLIC)" in publisher
    assert "Preview access = PUBLIC repository" in publisher
    assert "wired only to the experimental" in publisher
    assert "PRIVATE repo" not in publisher
    assert "access-controlled PREVIEW" not in publisher

    assert "**public** `nWave-ai/nWave-experimental`" in readme
    assert "release.yml" not in readme
    assert "CI Success" in readme
