"""Integration test: `des commit-slice` produces a verified slice commit.

Closes the recurring gate-scope-timing defect (#67 facet-4 / AD-23 adjacent):
the committed-scope ``Gate-Scope:`` trailer must be correct BY CONSTRUCTION, so
the G_COMMIT exit gate (``run_contract_gate --verify-gate-scope``) verifies
clean with NO manual ``git commit --amend``.

The load-bearing scenario reproduces the EXACT defect: a slice that adds a NEW
test file (untracked at terminating-run time). The pre-fix producer digest --
computed before the commit, when the new file is untracked -- would have stamped
the PARENT's committed-scope digest, which the exit gate then rejects as a
mismatch. ``commit-slice`` stages -> commits -> computes the committed-scope
digest of the RESULTING HEAD (now including the new file) -> amends -> the
commit verifies clean.

Real I/O: a real tmp git work-tree, real ``git`` subprocesses, a real
``run_contract_gate --verify-gate-scope`` subprocess collection. Integration
layer (Mandate 6 -- subprocess adapter, real exit codes).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.commit_slice import main as commit_slice_main
from des.cli.run_contract_gate import main as run_contract_gate_main
from tests.des._helpers.commit_slice_git_template import (
    provision_commit_slice_repo,
)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _init_repo(root: Path) -> None:
    """Provision the git work-tree via the shared session-cached template.

    See ``tests.des._helpers.commit_slice_git_template`` -- the base repo
    (``git init`` + config + the "base: walking skeleton" commit, six real
    ``git`` subprocess spawns) is built ONCE per test process and cached;
    this call materializes an independent filesystem copy at ``root``, so
    no test's later mutations can leak into another test's repo.
    """
    provision_commit_slice_repo(root)


def _last_json_event(stdout: str) -> dict:
    json_lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    return json.loads(json_lines[-1])


def test_commit_slice_verifies_clean_with_new_untracked_at(
    tmp_path: Path, capsys
) -> None:
    """A slice adding a NEW (untracked) test file commits + verifies with NO amend.

    This is the acceptance proof for the gate-scope-timing fix: the committed
    commit carries the committed-scope digest of its OWN tree, so the exit gate
    verifies clean -- the manual --amend tax is eliminated.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)

    # The slice's NEW test file -- untracked, exactly the defect trigger.
    (repo / "tests" / "unit" / "test_slice_new.py").write_text(
        "def test_slice_new():\n    assert 2 + 2 == 4\n", encoding="utf-8"
    )

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--feature-id",
            "commit-slice-mechanics",
            "--all",
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            "tests/unit/test_slice_new.py",
            "--message",
            "feat(slice): add the new slice behaviour\n\nSlice-Id: slice-01",
        ]
    )
    out = capsys.readouterr().out
    event = _last_json_event(out)

    assert exit_code == 0
    assert event["event"] == "SliceCommitted"
    assert event["verified"] is True
    assert len(event["gate_scope_digest"]) == 64

    # The commit message carries the committed-scope digest as a Gate-Scope:
    # trailer -- and ONLY that, the placeholder is gone.
    message = _git(repo, "log", "-1", "--format=%B", "HEAD")
    assert f"Gate-Scope: {event['gate_scope_digest']}" in message
    assert "0" * 64 not in message
    assert "Slice-Id: slice-01" in message

    # Independent re-verification: the SAME gate the G_COMMIT exit gate runs
    # accepts HEAD with NO amend in between.
    capsys.readouterr()  # drain
    verify_code = run_contract_gate_main(
        ["--repo", str(repo), "--verify-gate-scope", "--commit", "HEAD"]
    )
    verify_event = _last_json_event(capsys.readouterr().out)
    assert verify_code == 0
    assert verify_event["event"] == "GateScopeVerified"


def test_commit_slice_refuses_message_with_gate_scope_trailer(
    tmp_path: Path, capsys
) -> None:
    """A --message that already carries a Gate-Scope: trailer is MalformedInput.

    The trailer is appended mechanically; a caller-supplied one would race the
    mechanical stamp. Fail closed (exit 2) before any git mutation.

    SPEED (2026-07-20): ``extract_gate_scope(args.message)`` is a pure regex
    scan of the message string, checked in ``main()`` before ``--repo`` is
    ever touched (before staging, before the gitlint check, before any
    ``git`` call) -- so no real git repo is provisioned; ``repo`` is never
    created on disk.
    """
    repo = tmp_path / "repo"

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--feature-id",
            "commit-slice-mechanics",
            "--all",
            "--message",
            "feat(x): thing\n\nGate-Scope: " + ("a" * 64),
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 2
    assert event["event"] == "MalformedInput"


def test_commit_slice_refuses_empty_index(tmp_path: Path, capsys) -> None:
    """Nothing staged -> MalformedInput exit 2 (no empty slice commit)."""
    repo = tmp_path / "repo"
    _init_repo(repo)  # clean tree, nothing new

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--feature-id",
            "commit-slice-mechanics",
            "--all",
            "--message",
            "feat(x): nothing to commit\n\nSlice-Id: slice-02",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 2
    assert event["event"] == "MalformedInput"


def _install_counting_pre_commit_hook(repo: Path, counter: Path) -> None:
    """Install a pre-commit hook that appends a line to ``counter`` per run.

    The hook is a portable POSIX shell stub whose ONLY job is to record that it
    fired -- the run count is ``len(counter.read_text().splitlines())``. It
    always exits 0 so it never blocks the commit; we measure HOW MANY TIMES the
    git hook machinery invoked it, not whether validation passed.
    """
    hooks_dir = repo / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook = hooks_dir / "pre-commit"
    hook.write_text(
        f'#!/bin/sh\necho ran >> "{counter}"\nexit 0\n',
        encoding="utf-8",
    )
    hook.chmod(0o755)


def _hook_run_count(counter: Path) -> int:
    if not counter.exists():
        return 0
    return len([line for line in counter.read_text().splitlines() if line.strip()])


def test_commit_slice_runs_pre_commit_hook_exactly_once(tmp_path: Path, capsys) -> None:
    """Without --no-verify-commit the pre-commit hook fires ONCE, not twice.

    The amend is message-only on an already-validated tree, so re-running the
    pre-commit hook on it is redundant by construction: ``_amend_trailer`` now
    passes --no-verify UNCONDITIONALLY. The acceptance signal is behavioural --
    a real git pre-commit hook that counts its own executions must record
    exactly ONE run (the first commit), never two (first + amend).

    This is the load-bearing regression for the double-run defect: a re-running
    amend hook re-executed the full pre-commit suite (~5 min) a second time on a
    byte-identical tree.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    counter = tmp_path / "hook_runs.log"
    _install_counting_pre_commit_hook(repo, counter)

    (repo / "tests" / "unit" / "test_slice_new.py").write_text(
        "def test_slice_new():\n    assert 2 + 2 == 4\n", encoding="utf-8"
    )

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--feature-id",
            "commit-slice-mechanics",
            "--all",
            # Real observed evidence for the pre-flight E1+E2 gate (a resolvable
            # .feature would work equally well; pytest-regression is the
            # lighter-weight fixture for a hook-counting test whose real
            # subject is orthogonal to AT kind).
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            "tests/unit/test_slice_new.py",
            "--message",
            "feat(slice): hook counted once\n\nSlice-Id: slice-01",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 0
    assert event["event"] == "SliceCommitted"
    # The first commit ran the hook once; the amend skipped it. Not twice.
    assert _hook_run_count(counter) == 1

    # The final Gate-Scope digest still verifies clean -- the skip did not
    # weaken the committed-scope acceptance proof.
    assert event["verified"] is True
    capsys.readouterr()  # drain
    verify_code = run_contract_gate_main(
        ["--repo", str(repo), "--verify-gate-scope", "--commit", "HEAD"]
    )
    verify_event = _last_json_event(capsys.readouterr().out)
    assert verify_code == 0
    assert verify_event["event"] == "GateScopeVerified"


def test_commit_slice_no_verify_commit_skips_hook_entirely(
    tmp_path: Path, capsys
) -> None:
    """With --no-verify-commit the pre-commit hook fires ZERO times.

    The user flag governs the FIRST commit (suppressing the hook there); the
    amend already skips it unconditionally. So the hook runs neither at commit
    nor at amend -> zero recorded executions.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    counter = tmp_path / "hook_runs.log"
    _install_counting_pre_commit_hook(repo, counter)

    (repo / "tests" / "unit" / "test_slice_new.py").write_text(
        "def test_slice_new():\n    assert 1 + 1 == 2\n", encoding="utf-8"
    )

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--feature-id",
            "commit-slice-mechanics",
            "--all",
            "--no-verify-commit",
            # Real observed evidence for the pre-flight E1+E2 gate -- orthogonal
            # to this test's real subject (the hook is skipped entirely).
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            "tests/unit/test_slice_new.py",
            "--message",
            "feat(slice): hook skipped entirely\n\nSlice-Id: slice-02",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 0
    assert event["event"] == "SliceCommitted"
    assert _hook_run_count(counter) == 0


# ---------------------------------------------------------------------------
# Reviewed-by: trailer stamping (recurring records-of-truth omission, class-#56)
# ---------------------------------------------------------------------------
#
# RCA: `des commit-slice` historically did NOT stamp the `Reviewed-by:` trailer
# -- it was hand-typed into `--message` by the crafter. When the agent forgot,
# the commit landed with NO Reviewed-by, no error, verified:true (e.g. #73
# slice-04 1998295b7, earned-verdict slice-04 05dbeb51f -- both had an APPROVED
# ATReviewVerdict in the ledger, yet no trailer). slice-03 of #73 (22bf4264)
# DID carry it, because that agent remembered. The trailer carries the
# ATReviewVerdict ledger record's `record_hash`. These tests pin the mechanical
# stamp (the read aligned with the write) + the degrade-LOUD warning.


def _record_at_review_verdict(repo: Path, feature_id: str, slice_id: str) -> str:
    """Append an APPROVED ATReviewVerdict via the M7 ledger; return record_hash.

    Mirrors the `des record-at-review-verdict` producer write (which routes
    through `AtCompletionLedger.append_review_verdict`); the returned record's
    `record_hash` is the value the `Reviewed-by:` trailer must carry.
    """
    ledger = AtCompletionLedger(feature_id=feature_id, project_root=repo)
    record = ledger.append_review_verdict(
        slice_id=slice_id,
        verdict_fields={
            "schema_version": "1.0.0",
            "verdict": "APPROVED",
            "reviewer_agent_id": "reviewer-abc123",
            "at_ids": ["AT-1", "AT-2"],
            "at_content_hash": "a" * 64,
            "timestamp": "2026-06-28T00:00:00Z",
            "findings_summary": [],
        },
    )
    return str(record["record_hash"])


def test_commit_slice_stamps_reviewed_by_from_ledger(tmp_path: Path, capsys) -> None:
    """record-at-review-verdict then commit-slice -> Reviewed-by: trailer present.

    The load-bearing regression for the recurrence: with an APPROVED
    ATReviewVerdict recorded for the slice, commit-slice mechanically stamps
    `Reviewed-by: <record_hash> (APPROVED)` WITHOUT the operator hand-typing it
    into --message. `--feature-id` is passed (now mandatory) matching the
    feature the verdict was recorded under -- the ledger READ (keyed by that
    feature-id) is aligned with the ledger WRITE below, exercising the SAME
    mechanical-stamp lookup this test guards.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id = "fix-recurring-reviewed-by"
    expected_hash = _record_at_review_verdict(repo, feature_id, "slice-01")

    (repo / "tests" / "unit" / "test_slice_new.py").write_text(
        "def test_slice_new():\n    assert 2 + 2 == 4\n", encoding="utf-8"
    )

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--feature-id",
            feature_id,
            "--all",
            # Real observed evidence for the pre-flight E1+E2 gate -- orthogonal
            # to this test's real subject (the Reviewed-by: mechanical stamp).
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            "tests/unit/test_slice_new.py",
            "--message",
            "feat(slice): behaviour with recorded review\n\nSlice-Id: slice-01",
        ]
    )
    captured = capsys.readouterr()
    event = _last_json_event(captured.out)

    assert exit_code == 0
    assert event["event"] == "SliceCommitted"

    message = _git(repo, "log", "-1", "--format=%B", "HEAD")
    assert f"Reviewed-by: {expected_hash} (APPROVED)" in message
    assert "Slice-Id: slice-01" in message


def test_commit_slice_warns_loud_when_no_recorded_verdict(
    tmp_path: Path, capsys
) -> None:
    """No APPROVED verdict recorded -> stderr WARNING, trailer OMITTED, not silent.

    Degrade-LOUD (no-silent-pass): the commit still lands (commit-slice's job is
    the commit + Gate-Scope, not the AT-review gate), but the absent trailer is
    surfaced with a what/why/how WARNING -- never silently dropped, never a
    fabricated hash.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)  # no ATReviewVerdict recorded

    (repo / "tests" / "unit" / "test_slice_new.py").write_text(
        "def test_slice_new():\n    assert 1 + 1 == 2\n", encoding="utf-8"
    )

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--feature-id",
            "commit-slice-mechanics",
            "--all",
            # Real observed evidence for the pre-flight E1+E2 gate -- orthogonal
            # to this test's real subject (the loud stderr WARNING).
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            "tests/unit/test_slice_new.py",
            "--message",
            "feat(slice): behaviour without recorded review\n\nSlice-Id: slice-07",
        ]
    )
    captured = capsys.readouterr()
    event = _last_json_event(captured.out)

    assert exit_code == 0
    assert event["event"] == "SliceCommitted"

    # The omission is LOUD on stderr (what/why/how), never silent.
    assert "WARNING" in captured.err
    assert "Reviewed-by" in captured.err
    assert "slice-07" in captured.err

    # No fabricated trailer landed in the commit.
    message = _git(repo, "log", "-1", "--format=%B", "HEAD")
    assert "Reviewed-by:" not in message


def test_commit_slice_preserves_hand_stamped_reviewed_by(
    tmp_path: Path, capsys
) -> None:
    """A --message already carrying a Reviewed-by: trailer is preserved verbatim.

    Idempotent / back-compat: an operator (or a still-hand-stamping agent) that
    supplies the trailer keeps it unchanged -- no duplicate, no override, no
    ledger lookup.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    # A DIFFERENT hash than any ledger record -- proves verbatim preservation.
    hand_hash = "b" * 64

    (repo / "tests" / "unit" / "test_slice_new.py").write_text(
        "def test_slice_new():\n    assert 3 + 3 == 6\n", encoding="utf-8"
    )

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--feature-id",
            "commit-slice-mechanics",
            "--all",
            # Real observed evidence for the pre-flight E1+E2 gate -- orthogonal
            # to this test's real subject (verbatim Reviewed-by: preservation).
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            "tests/unit/test_slice_new.py",
            "--message",
            "feat(slice): hand-stamped review\n\n"
            f"Reviewed-by: {hand_hash} (APPROVED)\n\nSlice-Id: slice-03",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 0
    assert event["event"] == "SliceCommitted"

    message = _git(repo, "log", "-1", "--format=%B", "HEAD")
    # Exactly the operator's trailer, exactly once.
    assert message.count(f"Reviewed-by: {hand_hash} (APPROVED)") == 1
