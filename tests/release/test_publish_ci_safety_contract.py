"""Structural contracts for the experimental and dev release entry points."""

from __future__ import annotations

import os
import re
import stat
import subprocess
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


# =============================================================================
# Behavioral contract: the CI gate's bounded retry loop under transient
# `gh` failures (production incident: run 31575715724, a single transient
# TLS x509 error from `gh run view` exited the gate immediately even though
# MAX_ATTEMPTS=180 and CI itself was healthy). These tests execute the
# step's actual `run:` shell script -- extracted verbatim from the workflow
# YAML -- against a fake `gh` on PATH. No network call is made; MAX_ATTEMPTS
# and WAIT_SECONDS are shrunk in the extracted copy so the loop-exhaustion
# case runs in well under a second instead of MAX_ATTEMPTS * WAIT_SECONDS.
# =============================================================================

_MOCK_GH = r"""#!/usr/bin/env bash
set -euo pipefail

if [ "$1" = "run" ] && [ "$2" = "list" ]; then
  count=0
  [ -f "$GH_MOCK_LIST_COUNTER" ] && count=$(cat "$GH_MOCK_LIST_COUNTER")
  count=$((count + 1))
  echo "$count" > "$GH_MOCK_LIST_COUNTER"
  if [ "${GH_MOCK_FAIL_TARGET:-}" = "list" ] && [ "$count" -le "${GH_MOCK_FAIL_UNTIL:-0}" ]; then
    echo "x509: certificate signed by unknown authority (mock list failure)" >&2
    exit 1
  fi
  echo "999"
  exit 0
fi

if [ "$1" = "run" ] && [ "$2" = "view" ]; then
  count=0
  [ -f "$GH_MOCK_VIEW_COUNTER" ] && count=$(cat "$GH_MOCK_VIEW_COUNTER")
  count=$((count + 1))
  echo "$count" > "$GH_MOCK_VIEW_COUNTER"
  if [ "${GH_MOCK_FAIL_TARGET:-}" = "view" ] && [ "$count" -le "${GH_MOCK_FAIL_UNTIL:-0}" ]; then
    echo "x509: certificate signed by unknown authority (mock view failure)" >&2
    exit 1
  fi
  echo '{"status":"completed","conclusion":"success","jobs":[{"name":"CI Success","status":"completed","conclusion":"success"}]}'
  exit 0
fi

echo "unexpected mock gh invocation: $*" >&2
exit 99
"""


def _extract_ci_gate_script(max_attempts: int, wait_seconds: int) -> str:
    workflow = _workflow(EXPERIMENTAL)
    ci_gate = _step(workflow, "Wait for successful CI Success on this exact commit")
    run = ci_gate["run"]

    run, n_attempts = re.subn(
        r"readonly MAX_ATTEMPTS=\d+",
        f"readonly MAX_ATTEMPTS={max_attempts}",
        run,
    )
    run, n_wait = re.subn(
        r"readonly WAIT_SECONDS=\d+",
        f"readonly WAIT_SECONDS={wait_seconds}",
        run,
    )
    assert (n_attempts, n_wait) == (1, 1), (
        "workflow script shape changed; update the extractor"
    )
    return run


def _run_ci_gate(
    tmp_path: Path, *, max_attempts: int, extra_env: dict
) -> subprocess.CompletedProcess:
    script = _extract_ci_gate_script(max_attempts=max_attempts, wait_seconds=0)
    script_path = tmp_path / "ci_gate.sh"
    script_path.write_text(script, encoding="utf-8")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh_path = bin_dir / "gh"
    gh_path.write_text(_MOCK_GH, encoding="utf-8")
    gh_path.chmod(gh_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    env = {
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "HOME": os.environ.get("HOME", "/tmp"),
        "REQUIRED_SHA": "deadbeefcafef00ddeadbeefcafef00ddeadbeef",
        "GH_TOKEN": "mock-token",
        "GH_MOCK_LIST_COUNTER": str(tmp_path / "list_counter"),
        "GH_MOCK_VIEW_COUNTER": str(tmp_path / "view_counter"),
    }
    env.update(extra_env)

    return subprocess.run(
        ["bash", str(script_path)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _counter(tmp_path: Path, name: str) -> int:
    path = tmp_path / name
    return int(path.read_text().strip()) if path.exists() else 0


def test_ci_gate_retries_past_a_transient_gh_run_view_failure(tmp_path: Path) -> None:
    """Reproduces run 31575715724: `gh run view` fails transiently on an
    otherwise-healthy CI run. The gate must retry within its bounded budget
    and still land on the successful exact-SHA terminal CI Success, instead
    of exiting on the first transient error."""
    result = _run_ci_gate(
        tmp_path,
        max_attempts=5,
        extra_env={"GH_MOCK_FAIL_TARGET": "view", "GH_MOCK_FAIL_UNTIL": "2"},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "CI Success passed" in result.stdout
    assert "::warning title=Transient CI query failure" in (
        result.stdout + result.stderr
    )
    # Proves the gate survived past the first transient failure via retries,
    # not that it happened to succeed on attempt 1.
    assert _counter(tmp_path, "view_counter") == 3


def test_ci_gate_retries_past_a_transient_gh_run_list_failure(tmp_path: Path) -> None:
    result = _run_ci_gate(
        tmp_path,
        max_attempts=5,
        extra_env={"GH_MOCK_FAIL_TARGET": "list", "GH_MOCK_FAIL_UNTIL": "2"},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "CI Success passed" in result.stdout
    assert _counter(tmp_path, "list_counter") == 3


def test_ci_gate_exhausts_bounded_budget_and_fails_closed_on_persistent_transient_errors(
    tmp_path: Path,
) -> None:
    """The regression test for the incident: with the pre-fix code, a
    transient `gh run view` failure exits the gate on attempt 1 regardless
    of MAX_ATTEMPTS. Here MAX_ATTEMPTS is shrunk to 4 and `gh` is made to
    fail on every call -- the fixed gate must consume the *entire* bounded
    budget (view_counter == max_attempts) before failing closed, never
    publish without proof, and never exit early."""
    max_attempts = 4
    result = _run_ci_gate(
        tmp_path,
        max_attempts=max_attempts,
        extra_env={"GH_MOCK_FAIL_TARGET": "view", "GH_MOCK_FAIL_UNTIL": "999"},
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert "Experimental publish CI gate failed" in (result.stdout + result.stderr)
    # The load-bearing assertion: this fails against the old immediate-exit
    # behavior, which would leave the counter at 1, not at max_attempts.
    assert _counter(tmp_path, "view_counter") == max_attempts
