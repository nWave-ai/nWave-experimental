"""Real cleanup observation for a reviewer checkout after provider refusal."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process
from tests.des.acceptance import fake_provider
from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    PACKAGE_PARENT,
    hermetic_environment,
)
from tests.des.acceptance.steps_for_the_orchestrator.test_host_review_examine_artifacts import (
    _prepare,
    _provider_free_verify,
)
from tests.des.acceptance.steps_for_the_orchestrator.test_verify_retains_native_evidence_without_provider import (
    _crafted,
)


def test_failed_reviewer_invocation_removes_its_real_candidate_checkout(
    root, step, tmp_path
):
    _crafted(root, step)
    candidate, _, _ = _provider_free_verify(root, tmp_path)
    _, prepared = _prepare(root, step, "reviewer", candidate)

    code, _out, _err = step(
        "invoke-role",
        "--repo-root",
        str(root),
        "--role",
        "reviewer",
        "--candidate",
        candidate,
        "--provider",
        "claude",
        "--input",
        str(prepared.relative_to(root)),
    )

    assert code != 0
    worktrees = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "nwave-reviewer-" not in worktrees


def test_failed_reviewer_invocation_retains_a_dirty_real_candidate_checkout(
    root, step, tmp_path
):
    """A provider process dirties its reviewer worktree before refusing."""
    _crafted(root, step)
    candidate, _, _ = _provider_free_verify(root, tmp_path)
    _, prepared = _prepare(root, step, "reviewer", candidate)

    launcher_dir = tmp_path / "dirty-provider-bin"
    environment = fake_provider.environment(
        root,
        launcher_dir=launcher_dir,
        results=tmp_path / "unused-results.json",
        log=tmp_path / "unused-model-log.json",
        package_parent=PACKAGE_PARENT,
    )
    dirty_file = "actual-reviewer-dirty-artifact"
    launcher = launcher_dir / "claude"
    launcher.write_text(
        "#!/bin/sh\n"
        f"printf dirty > {dirty_file}\n"
        "printf 'provider refused after writing reviewer context\\n' >&2\n"
        "exit 23\n",
        encoding="utf-8",
    )
    launcher.chmod(0o755)
    environment = hermetic_environment(environment, tmp_path / "claude-config")

    code, out, err = run_cli_in_process(
        [
            "invoke-role",
            "--repo-root",
            str(root),
            "--role",
            "reviewer",
            "--candidate",
            candidate,
            "--provider",
            "claude",
            "--input",
            str(prepared.relative_to(root)),
        ],
        cwd=root,
        env=environment,
        catch_all=True,
    )

    assert code != 0
    terminal = out + "\n" + err
    assert "RETAINED-CONTEXT: " in terminal
    retained = terminal.split("RETAINED-CONTEXT: ", 1)[1].split(": ", 1)[0]
    reviewer_checkout = Path(retained)
    assert reviewer_checkout.is_dir()
    assert (reviewer_checkout / dirty_file).read_text(encoding="utf-8") == "dirty"
    assert (
        subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.find(f"worktree {reviewer_checkout}")
        >= 0
    )
    assert (
        subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=reviewer_checkout,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        == f"?? {dirty_file}\n"
    )
