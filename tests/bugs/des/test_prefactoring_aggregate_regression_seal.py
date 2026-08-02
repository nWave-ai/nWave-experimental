# @feature-prefactoring-aggregate-regression-seal
# @slice-01
"""Active-RED acceptance scaffolds for declared pytest parity aggregates.

Focused checks drive ``verify_slice_commit_completeness.main(argv)`` in-process.
The one walking skeleton drives the shipped ``des verify-slice-commit`` protocol
in a subprocess.  Neither path imports an unbuilt aggregate implementation.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import itertools
import json
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from des.application.slice_at_completeness import canonical_regression_test_path
from des.cli import verify_slice_commit_completeness as verify_slice_commit
from des.cli.run_contract_gate import (
    _CollectionError,
    compute_gate_scope_digest,
    gate_scope_digest,
)
from des.runtime.interpreter import InterpreterUnavailable


_FEATURE_ID = "prefactoring-aggregate-regression-seal"
_SLICE_ID = "slice-01"
_LEGACY_RECEIPT_TREE_HASH = (
    "e8f3f602dda455dd7ca97d005220c27a4f2b16fd4979043c4a8f1c3c16109e0d"
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _git_output(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _init_declared_aggregate(
    repo: Path,
    *,
    annotation: str = "@prefactoring",
    beta_body: str = "def test_parity_holds():\n    assert True\n",
    trailer_slice_id: str = _SLICE_ID,
    include_suite_declaration: bool = True,
    declared_suite_paths: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "aggregate@example.test")
    _git(repo, "config", "user.name", "Aggregate Maintainer")
    delta = repo / "docs" / "feature" / _FEATURE_ID / "feature-delta.md"
    delta.parent.mkdir(parents=True)
    delta.write_text(
        "# Feature Delta\n\n## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
        "| slice-01 | a maintainer seals the complete declared parity aggregate | pending | "
        f"{annotation} | existing evidence only |\n",
        encoding="utf-8",
    )
    members = (
        "tests/parity/test_alpha.py",
        "tests/parity/test_beta.py",
        "tests/parity/test_gamma.py",
    )
    for member in members:
        path = repo / member
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            beta_body
            if member.endswith("beta.py")
            else "def test_parity_holds():\n    assert True\n",
            encoding="utf-8",
        )
    _git(repo, "add", "-A")
    trailer_paths = (
        declared_suite_paths if declared_suite_paths is not None else members
    )
    declaration = (
        "".join(f"\nRegression-Suite: {path}" for path in trailer_paths)
        if include_suite_declaration
        else ""
    )
    _git(
        repo,
        "commit",
        "-q",
        "-m",
        f"refactor: preserve parity\n\nSlice-Id: {trailer_slice_id}{declaration}",
    )
    # Gate-Scope: is orthogonal to Regression-Suite: -- stamp the REAL
    # committed-scope digest of this repo's own contract suite (computed via
    # the shipped ``run_contract_gate.gate_scope_digest``, never a hardcoded
    # literal or the all-zero placeholder) so the trunk gate's
    # ``gate_scope_unsealed`` leg does not short-circuit into
    # SliceCommitIndeterminate before the aggregate contract is exercised.
    try:
        real_gate_scope_digest = gate_scope_digest(repo)
    except _CollectionError:
        # Some scenarios deliberately seed an uncollectable declared member
        # (e.g. a `beta_body` that raises at import time) to exercise the
        # aggregate's OWN collection-error refusal -- a genuinely broken
        # contract suite cannot yield a fresh committed-scope digest either
        # (`des commit-slice`'s own `_committed_scope_digest_quiet` fails
        # closed identically). The trunk `gate_scope_unsealed` leg only checks
        # the trailer's SHAPE (well-formed hex, not the all-zero placeholder)
        # -- it never re-derives a fresh digest to compare against -- so a
        # real digest from the SAME production hash function over the empty
        # scope seals the commit honestly without fabricating a value.
        real_gate_scope_digest = compute_gate_scope_digest([])
    original_message = _git_output(repo, "log", "-1", "--format=%B", "HEAD")
    _git(
        repo,
        "commit",
        "-q",
        "--amend",
        "-m",
        f"{original_message}\n\nGate-Scope: {real_gate_scope_digest}",
    )
    return members


def _payload(output: str) -> dict[str, object]:
    payloads = [
        json.loads(line)
        for line in output.splitlines()
        if line.strip().startswith("{") and line.strip().endswith("}")
    ]
    return payloads[-1] if payloads else {"raw_output": output}


def _aggregate_argv(
    repo: Path, members: tuple[str, ...], *, commit_sha: str | None = None
) -> list[str]:
    selected_commit = commit_sha or _git_output(repo, "rev-parse", "HEAD")
    return [
        "--repo",
        str(repo),
        "--commit",
        selected_commit,
        "--feature-id",
        _FEATURE_ID,
        "--at-kind",
        "pytest-regression-aggregate",
        "--regression-test-files",
        *members,
    ]


def _verify_aggregate(
    repo: Path, members: tuple[str, ...], *, commit_sha: str | None = None
) -> tuple[int, dict[str, object]]:
    """Drive the stable public verification entry in-process."""
    return _verify_public(_aggregate_argv(repo, members, commit_sha=commit_sha))


def _verify_public(argv: list[str]) -> tuple[int, dict[str, object]]:
    """Drive the public CLI entry without substituting an internal seam."""
    output = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        try:
            exit_code = verify_slice_commit.main(argv)
        except SystemExit as exc:
            exit_code = exc.code if isinstance(exc.code, int) else 1
        except AssertionError as exc:
            exit_code = 1
            print(
                json.dumps(
                    {
                        "event": "UnexpectedCandidateExecution",
                        "error": str(exc),
                    }
                )
            )
    return exit_code, _payload(output.getvalue())


def _discover_prefactoring_aggregate(
    repo: Path, *extra_args: str
) -> tuple[int, dict[str, object]]:
    """Drive discovery through the public CLI with no sealing inputs."""
    return _verify_public(
        [
            "--repo",
            str(repo),
            "--feature-id",
            _FEATURE_ID,
            "--slice-id",
            _SLICE_ID,
            "--discover-prefactoring-aggregate",
            *extra_args,
        ]
    )


def _discover_prefactoring_outcome(
    repo: Path, *extra_args: str
) -> tuple[int, dict[str, object]]:
    """Capture a public discovery crash as an observable RED, not test breakage."""
    try:
        return _discover_prefactoring_aggregate(repo, *extra_args)
    except Exception as exc:
        return 1, {
            "event": "PrefactoringAggregateDiscoveryCrashed",
            "exception_type": type(exc).__name__,
            "error": str(exc),
        }


def _member_hashes(repo: Path, members: tuple[str, ...]) -> dict[str, str]:
    return {
        member: hashlib.sha256((repo / member).read_bytes()).hexdigest()
        for member in members
    }


def _declaration_digest(members: tuple[str, ...]) -> str:
    """Mirror the public declaration's canonical lexically sorted tuple."""
    canonical = "\n".join(sorted(members))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _verified_ledger_record(repo: Path) -> dict[str, object]:
    """Read the public gate's durable receipt, not its echoed stdout payload."""
    ledger = repo / ".nwave" / "telemetry" / "atdd-pure" / f"{_FEATURE_ID}.jsonl"
    records = [
        json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()
    ]
    return next(
        record
        for record in reversed(records)
        if record.get("event") == "SliceCommitVerified"
    )


def _ledger_records(repo: Path) -> list[dict[str, object]]:
    ledger = repo / ".nwave" / "telemetry" / "atdd-pure" / f"{_FEATURE_ID}.jsonl"
    if not ledger.is_file():
        return []
    return [
        json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()
    ]


def _stable_receipt_tree_hash(receipt: dict[str, object]) -> str:
    """Hash the complete stable receipt tree, not an enumerated field subset."""
    stable_receipt = {
        key: value for key, value in receipt.items() if key != "commit_sha"
    }
    canonical_tree = json.dumps(
        stable_receipt,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical_tree.encode("utf-8")).hexdigest()


@pytest.mark.negative_at
def test_empty_declaration_is_rejected_before_execution(tmp_path: Path) -> None:
    """CONTRACT_SHAPE: bounded-change."""
    # covers: R1
    repo = tmp_path / "repo"
    _init_declared_aggregate(repo)
    exit_code, receipt = _verify_aggregate(repo, ())
    assert exit_code != 0 and receipt.get("event") == "AggregateDeclarationMalformed", (
        "WHAT: an empty aggregate was accepted; WHY: it proves no population; HOW: reject it "
        f"and require every parity suite explicitly. receipt={receipt!r}"
    )


@pytest.mark.negative_at
def test_duplicate_declaration_is_rejected_before_a_seal_is_minted(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change."""
    # covers: R1
    repo = tmp_path / "repo"
    members = _init_declared_aggregate(repo)
    exit_code, receipt = _verify_aggregate(repo, (members[0], members[0]))
    assert exit_code != 0 and receipt.get("event") == "AggregateDeclarationMalformed", (
        "WHAT: a duplicate member was accepted; WHY: it can hide an omitted member; HOW: "
        f"refuse duplicate declarations. receipt={receipt!r}"
    )


@pytest.mark.negative_at
def test_public_cli_rejects_mixed_single_and_aggregate_declarations_before_a_seal(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change."""
    # covers: R10
    repo = tmp_path / "repo"
    members = _init_declared_aggregate(repo)
    argv = [
        "--repo",
        str(repo),
        "--commit",
        "HEAD",
        "--feature-id",
        _FEATURE_ID,
        "--at-kind",
        "pytest-regression-aggregate",
        "--regression-test-file",
        members[0],
        "--regression-test-files",
        *members,
    ]
    exit_code, receipt = _verify_public(argv)

    assert (
        exit_code != 0
        and receipt.get("event") == "AggregateDeclarationMalformed"
        and not _ledger_records(repo)
    ), (
        "WHAT: mixed single-file and aggregate declarations minted a seal; WHY: one invocation "
        "must name exactly one evidence population; HOW: reject the conflicting flags before E1/E2 "
        f"or ledger append. receipt={receipt!r}"
    )


@pytest.mark.negative_at
def test_missing_declared_path_refuses_candidate_selection_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CONTRACT_SHAPE: bounded-change."""
    # covers: R15
    # covers: R16
    repo = tmp_path / "repo"
    members = _init_declared_aggregate(repo)
    selected_sha = _git_output(repo, "rev-parse", "HEAD")
    missing = "tests/parity/test_missing.py"
    before = _ledger_records(repo)
    pytest_invocations: list[tuple[object, ...]] = []

    def pytest_must_not_run(*args: object, **_kwargs: object) -> object:
        pytest_invocations.append(args)
        raise AssertionError(
            "WHAT: a path outside the selected candidate reached pytest; WHY: selection must "
            "close the candidate tuple before evidence can run; HOW: refuse the declaration "
            "before execution or ledger mutation."
        )

    monkeypatch.setattr(verify_slice_commit, "des_spawn", pytest_must_not_run)
    exit_code, receipt = _verify_public(
        _aggregate_argv(repo, (*members, missing), commit_sha=selected_sha)
    )
    assert (
        exit_code != 0
        and receipt.get("event") == "PrefactoringAggregateSelectionRefused"
        and receipt.get("requested_commit") == selected_sha
        and receipt.get("reason") == "declared-suite-tuple-mismatch"
        and missing in json.dumps(receipt)
        and receipt.get("error")
        and receipt.get("how")
        and not pytest_invocations
        and _ledger_records(repo) == before
    ), (
        "WHAT: a nonexistent declared path was treated as runner-level evidence; WHY: it is not "
        "part of the selected candidate's committed tuple; HOW: name it in a pre-execution "
        f"selection refusal. receipt={receipt!r} invocations={pytest_invocations!r}"
    )


@pytest.mark.negative_at
def test_collection_error_member_is_named_in_the_refusal(tmp_path: Path) -> None:
    """CONTRACT_SHAPE: bounded-change."""
    # covers: R4
    repo = tmp_path / "repo"
    members = _init_declared_aggregate(
        repo, beta_body="raise RuntimeError('collection broken')\n"
    )
    exit_code, receipt = _verify_aggregate(repo, members)
    assert exit_code != 0 and members[1] in json.dumps(receipt), (
        "WHAT: a collection-error member was not named; WHY: it never executed; HOW: refuse "
        f"the aggregate and identify the affected suite. receipt={receipt!r}"
    )


@pytest.mark.negative_at
def test_ordinary_failing_member_is_named_in_the_refusal(tmp_path: Path) -> None:
    """CONTRACT_SHAPE: bounded-change."""
    # covers: R4
    repo = tmp_path / "repo"
    members = _init_declared_aggregate(
        repo, beta_body="def test_parity_holds():\n    assert False\n"
    )
    exit_code, receipt = _verify_aggregate(repo, members)
    assert exit_code != 0 and members[1] in json.dumps(receipt), (
        "WHAT: a failing member was not named; WHY: partial green is not aggregate parity; HOW: "
        f"refuse and identify the failed suite. receipt={receipt!r}"
    )


@pytest.mark.negative_at
def test_member_with_no_collected_tests_is_not_silently_omitted(tmp_path: Path) -> None:
    """CONTRACT_SHAPE: bounded-change."""
    # covers: R4
    repo = tmp_path / "repo"
    members = _init_declared_aggregate(repo, beta_body="# no collected tests\n")
    exit_code, receipt = _verify_aggregate(repo, members)
    assert (
        exit_code != 0
        and receipt.get("event") == "AggregateExecutionIncomplete"
        and members[1] in json.dumps(receipt)
    ), (
        "WHAT: an unobserved member was silently omitted; WHY: green siblings cannot certify it; "
        f"HOW: refuse cardinality or tuple mismatch and name it. receipt={receipt!r}"
    )


def test_complete_green_aggregate_receipt_has_exact_member_population(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change."""
    # covers: R2
    # covers: R3
    repo = tmp_path / "repo"
    members = _init_declared_aggregate(repo)
    expected_hashes = _member_hashes(repo, members)
    exit_code, receipt = _verify_aggregate(repo, members)
    observed_members = tuple(receipt.get("regression_test_files_executed", ()))
    observed_hashes = receipt.get("member_hashes")
    assert (
        exit_code == 0
        and observed_members == members
        and observed_hashes == expected_hashes
    ), (
        "WHAT: the sealed population differs from the declaration; WHY: a representative result "
        "cannot prove aggregate parity; HOW: bind the exact canonical tuple to every member hash. "
        f"receipt={receipt!r}"
    )
    assert receipt.get("aggregate_digest"), (
        "WHAT: a complete aggregate receipt lacks its digest; WHY: its member population cannot "
        f"be integrity-bound; HOW: record an aggregate digest. receipt={receipt!r}"
    )


def test_repeated_aggregate_seals_append_independent_auditable_evidence(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change."""
    # covers: R11
    repo = tmp_path / "repo"
    members = _init_declared_aggregate(repo)

    first_code, first_receipt = _verify_aggregate(repo, members)
    second_code, second_receipt = _verify_aggregate(repo, members)
    verified_records = [
        record
        for record in _ledger_records(repo)
        if record.get("event") == "SliceCommitVerified"
    ]

    assert (
        first_code == second_code == 0
        and len(verified_records) == 2
        and (
            first_receipt.get("aggregate_digest")
            == second_receipt.get("aggregate_digest")
        )
        and all(
            tuple(record.get("regression_test_files_executed", ())) == members
            for record in verified_records
        )
    ), (
        "WHAT: a repeated aggregate seal lost or changed its evidence; WHY: the upstream append-only, "
        "set-valued ledger contract permits repeat attempts without corrupting the slice chain; HOW: "
        f"append one complete receipt per successful invocation. records={verified_records!r}"
    )


@pytest.mark.negative_at
def test_uncommitted_imported_support_cannot_certify_committed_aggregate(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change."""
    # covers: R7
    repo = tmp_path / "repo"
    members = _init_declared_aggregate(repo)
    support = repo / "tests" / "parity" / "parity_support.py"
    support.write_text("def proves_parity():\n    return False\n", encoding="utf-8")
    for member in members:
        (repo / member).write_text(
            "from parity_support import proves_parity\n\n"
            "def test_parity_holds():\n    assert proves_parity()\n",
            encoding="utf-8",
        )
    _git(repo, "add", "-A")
    _git(
        repo,
        "commit",
        "-q",
        "-m",
        "refactor: bind support to commit\n\nSlice-Id: slice-01\n"
        "Regression-Suite: tests/parity/test_alpha.py\n"
        "Regression-Suite: tests/parity/test_beta.py\n"
        "Regression-Suite: tests/parity/test_gamma.py",
    )
    support.write_text("def proves_parity():\n    return True\n", encoding="utf-8")

    exit_code, receipt = _verify_aggregate(repo, members)

    assert exit_code != 0 and receipt.get("event") in {
        "AggregateExecutionRefused",
        "AggregateExecutionIncomplete",
        "SliceCommitIndeterminate",
    }, (
        "WHAT: a worktree-only imported helper certified the committed aggregate; WHY: member "
        "hashes do not bind imported behaviour; HOW: run an isolated committed tree or refuse "
        f"the uncommitted dependency. receipt={receipt!r}"
    )


@pytest.mark.negative_at
def test_unavailable_pytest_evidence_records_indeterminate_not_aggregate_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTRACT_SHAPE: bounded-change."""
    # covers: R8
    repo = tmp_path / "repo"
    members = _init_declared_aggregate(repo)

    def unavailable_pytest(*_args: object, **_kwargs: object) -> object:
        raise InterpreterUnavailable("pytest", ["missing-pytest"], repo_root=repo)

    monkeypatch.setattr(verify_slice_commit, "des_spawn", unavailable_pytest)
    exit_code, receipt = _verify_aggregate(repo, members)

    assert (
        exit_code != 1
        and receipt.get("event") == "SliceCommitIndeterminate"
        and (receipt.get("reason") == "regression_test_file_interpreter_unavailable")
    ), (
        "WHAT: unavailable pytest evidence was recorded as an ordinary aggregate refusal; WHY: "
        "the maintainer cannot distinguish a failed suite from an unrun one; HOW: retain the "
        f"SliceCommitIndeterminate outcome and reason. receipt={receipt!r}"
    )


def test_unavailable_aggregate_evidence_durably_names_the_unrun_member(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTRACT_SHAPE: bounded-change."""
    # covers: R12
    repo = tmp_path / "repo"
    members = _init_declared_aggregate(repo)

    def unavailable_pytest(*_args: object, **_kwargs: object) -> object:
        raise InterpreterUnavailable("pytest", ["missing-pytest"], repo_root=repo)

    monkeypatch.setattr(verify_slice_commit, "des_spawn", unavailable_pytest)
    exit_code, receipt = _verify_aggregate(repo, members)
    durable = next(
        record
        for record in reversed(_ledger_records(repo))
        if record.get("event") == "SliceCommitIndeterminate"
    )

    assert (
        exit_code != 0
        and receipt.get("member") == members[0]
        and durable.get("member") == members[0]
    ), (
        "WHAT: unavailable aggregate evidence did not durably name the unrun member; WHY: a later "
        "auditor cannot distinguish which member lacked trustworthy execution; HOW: persist the member "
        f"alongside the indeterminate reason. receipt={receipt!r} durable={durable!r}"
    )


@pytest.mark.negative_at
def test_aggregate_failure_outcomes_match_the_declared_closed_vocabulary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTRACT_SHAPE: bounded-change."""
    # covers: R13
    empty_repo = tmp_path / "empty"
    _init_declared_aggregate(empty_repo)
    _, empty = _verify_aggregate(empty_repo, ())

    duplicate_repo = tmp_path / "duplicate"
    duplicate_members = _init_declared_aggregate(duplicate_repo)
    _, duplicate = _verify_aggregate(
        duplicate_repo, (duplicate_members[0], duplicate_members[0])
    )

    missing_repo = tmp_path / "missing"
    missing_members = _init_declared_aggregate(missing_repo)
    _, missing = _verify_aggregate(
        missing_repo, (*missing_members, "tests/parity/test_missing.py")
    )

    uncollectable_repo = tmp_path / "uncollectable"
    uncollectable_members = _init_declared_aggregate(
        uncollectable_repo, beta_body="raise RuntimeError('collection broken')\n"
    )
    _, uncollectable = _verify_aggregate(uncollectable_repo, uncollectable_members)

    incomplete_repo = tmp_path / "incomplete"
    incomplete_members = _init_declared_aggregate(
        incomplete_repo, beta_body="# no collected tests\n"
    )
    _, incomplete = _verify_aggregate(incomplete_repo, incomplete_members)

    mutated_repo = tmp_path / "mutated"
    mutated_members = _init_declared_aggregate(mutated_repo)
    (mutated_repo / mutated_members[-1]).write_text(
        "def test_parity_holds():\n    assert True\n# changed\n", encoding="utf-8"
    )
    _, mutated = _verify_aggregate(mutated_repo, mutated_members)

    unavailable_repo = tmp_path / "unavailable"
    unavailable_members = _init_declared_aggregate(unavailable_repo)

    def unavailable_pytest(*_args: object, **_kwargs: object) -> object:
        raise InterpreterUnavailable(
            "pytest", ["missing-pytest"], repo_root=unavailable_repo
        )

    monkeypatch.setattr(verify_slice_commit, "des_spawn", unavailable_pytest)
    _, unavailable = _verify_aggregate(unavailable_repo, unavailable_members)

    outcomes = {
        "empty": empty.get("event"),
        "duplicate": duplicate.get("event"),
        "missing": missing.get("event"),
        "uncollectable": uncollectable.get("event"),
        "incomplete": incomplete.get("event"),
        "mutated": mutated.get("event"),
        "unavailable": unavailable.get("event"),
    }
    assert outcomes == {
        "empty": "AggregateDeclarationMalformed",
        "duplicate": "AggregateDeclarationMalformed",
        "missing": "PrefactoringAggregateSelectionRefused",
        "uncollectable": "AggregateMemberUncollectable",
        "incomplete": "AggregateExecutionIncomplete",
        "mutated": "AggregateContentMismatch",
        "unavailable": "SliceCommitIndeterminate",
    }, (
        "WHAT: aggregate outcomes escaped the public closed vocabulary; WHY: a declaration that differs "
        "from its selected candidate is not runner evidence and must not bypass selection; HOW: retain "
        "PrefactoringAggregateSelectionRefused for tuple mismatch, SliceCommitIndeterminate for "
        f"incapacity, and member-specific errors only after selection. outcomes={outcomes!r}"
    )


def test_verified_aggregate_evidence_is_persisted_with_the_seal(tmp_path: Path) -> None:
    """CONTRACT_SHAPE: bounded-change."""
    # covers: R9
    repo = tmp_path / "repo"
    members = _init_declared_aggregate(repo)
    expected_hashes = _member_hashes(repo, members)

    exit_code, receipt = _verify_aggregate(repo, members)
    record = _verified_ledger_record(repo)

    assert (
        exit_code == 0
        and record.get("event") == "SliceCommitVerified"
        and (tuple(record.get("regression_test_files_executed", ())) == members)
        and record.get("member_hashes") == expected_hashes
        and record.get("declaration_digest") == _declaration_digest(members)
        and (record.get("aggregate_digest") == receipt.get("aggregate_digest"))
    ), (
        "WHAT: aggregate evidence existed only in terminal output; WHY: a later auditor cannot "
        "reconstruct which trailer declaration the seal covered; HOW: persist the full SHA, ordered "
        "declared and executed tuples, member hashes, declaration digest, and "
        f"aggregate digest in SliceCommitVerified. record={record!r}, receipt={receipt!r}"
    )


@pytest.mark.negative_at
def test_still_green_member_changed_after_declaration_refuses_digest_mismatch(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change."""
    # covers: R5
    repo = tmp_path / "repo"
    members = _init_declared_aggregate(repo)
    declared_hashes = _member_hashes(repo, members)
    (repo / members[-1]).write_text(
        "def test_parity_holds():\n    assert True\n# changed\n", encoding="utf-8"
    )
    changed_hashes = _member_hashes(repo, members)
    exit_code, receipt = _verify_aggregate(repo, members)
    assert (
        declared_hashes != changed_hashes
        and exit_code != 0
        and receipt.get("event") == "AggregateContentMismatch"
        and members[-1] in json.dumps(receipt)
    ), (
        "WHAT: a still-green changed member sealed under its old declaration; WHY: its digest no "
        "longer identifies the declared evidence; HOW: compare declared member hashes and aggregate "
        f"digest before success, then name the changed path. receipt={receipt!r}"
    )


@pytest.mark.walking_skeleton
def test_maintainer_seals_complete_parity_aggregate_through_shipped_cli(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change."""
    # covers: R2
    # covers: R3
    repo = tmp_path / "repo"
    members = _init_declared_aggregate(repo)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "des",
            "verify-slice-commit",
            *_aggregate_argv(repo, members),
        ],
        capture_output=True,
        text=True,
    )
    receipt = _payload(completed.stdout + completed.stderr)
    assert (
        completed.returncode == 0
        and tuple(receipt.get("regression_test_files_executed", ())) == members
    ), (
        "WHAT: the shipped des verify-slice-commit protocol did not seal the complete aggregate; "
        "WHY: users consume that CLI, not an internal helper; HOW: wire the aggregate kind through "
        f"the installed command and emit the exact member tuple. receipt={receipt!r}"
    )


def test_single_file_pytest_regression_keeps_its_legacy_receipt_shape(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation."""
    # covers: R6
    repo = tmp_path / "repo"
    member = _init_declared_aggregate(repo, annotation="")[0]
    ledger = repo / ".nwave" / "telemetry" / "atdd-pure" / f"{_FEATURE_ID}.jsonl"
    audited_write_paths: set[Path] = set()
    capture_audit_events = True

    def capture_write(event: str, args: tuple[object, ...]) -> None:
        if (
            not capture_audit_events
            or event not in {"open", "io.open"}
            or len(args) < 2
        ):
            return
        path, mode = args[:2]
        if (
            not isinstance(path, str)
            or not isinstance(mode, str)
            or not {"w", "a", "x"} & set(mode)
        ):
            return
        candidate = Path(path).resolve()
        if candidate.is_relative_to(repo.resolve()):
            audited_write_paths.add(candidate)

    sys.addaudithook(capture_write)
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            exit_code = verify_slice_commit.main(
                [
                    "--repo",
                    str(repo),
                    "--commit",
                    "HEAD",
                    "--feature-id",
                    _FEATURE_ID,
                    "--at-kind",
                    "pytest-regression",
                    "--regression-test-file",
                    member,
                ]
            )
    finally:
        capture_audit_events = False
    receipt = _payload(output.getvalue())
    actual_tree_hash = _stable_receipt_tree_hash(receipt)
    assert (
        exit_code == 0
        and actual_tree_hash == _LEGACY_RECEIPT_TREE_HASH
        and audited_write_paths == {ledger.resolve()}
    ), (
        "WHAT: the legacy one-file receipt tree or its write boundary changed; WHY: aggregate "
        "evidence is additive and must not add, remove, or mutate a stable legacy field; HOW: "
        "preserve the canonical receipt tree (excluding only commit_sha) and append only the "
        f"existing ledger receipt. tree_hash={actual_tree_hash!r} writes={audited_write_paths!r} receipt={receipt!r}"
    )


def test_maintainer_discovers_one_committed_prefactoring_candidate_without_sealing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation."""
    # covers: R14
    repo = tmp_path / "repo"
    members = _init_declared_aggregate(repo)
    commit_sha = _git_output(repo, "rev-parse", "HEAD")
    uncommitted_suite = repo / "tests" / "parity" / "test_uncommitted.py"
    uncommitted_suite.write_text(
        "def test_uncommitted():\n    assert True\n", encoding="utf-8"
    )

    def pytest_must_not_run(*_args: object, **_kwargs: object) -> object:
        raise AssertionError(
            "WHAT: discovery invoked pytest; WHY: candidate projection is read-only; "
            "HOW: return committed candidates before the sealing route."
        )

    monkeypatch.setattr(verify_slice_commit, "des_spawn", pytest_must_not_run)
    exit_code, receipt = _discover_prefactoring_aggregate(repo)

    assert (
        exit_code == 0
        and receipt
        == {
            "event": "PrefactoringAggregateDiscovery",
            "feature_id": _FEATURE_ID,
            "slice_id": _SLICE_ID,
            "candidates": [
                {
                    "commit_sha": commit_sha,
                    "declared_suite_paths": list(members),
                    "declaration_digest": _declaration_digest(members),
                    "provenance": "commit-trailer",
                }
            ],
            "aggregate": "UNDECLARED",
        }
        and not _ledger_records(repo)
    ), (
        "WHAT: discovery did not expose exactly one trailer-declared bounded suite population; "
        "WHY: a maintainer must choose declared evidence instead of receiving an inferred seal; "
        "HOW: emit the full reachable SHA, canonical declaration, and digest without "
        f"pytest or ledger writes. receipt={receipt!r} records={_ledger_records(repo)!r}"
    )


@pytest.mark.negative_at
def test_no_trailer_bound_prefactoring_candidate_is_unavailable_without_sealing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation."""
    # covers: R15
    repo = tmp_path / "repo"
    _init_declared_aggregate(repo, include_suite_declaration=False)
    monkeypatch.setattr(
        verify_slice_commit,
        "des_spawn",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("pytest ran")),
    )

    exit_code, receipt = _discover_prefactoring_aggregate(repo)

    assert (
        exit_code != 0
        and receipt.get("event") == "PrefactoringAggregateDiscoveryUnavailable"
        and (receipt.get("reason") == "legacy-or-missing-declaration")
        and receipt.get("error")
        and receipt.get("how")
        and not _ledger_records(repo)
    ), (
        "WHAT: discovery treated Slice-Id-only provenance as a sealable declaration; WHY: no "
        "trailer tuple proves the bounded population; HOW: report legacy-or-missing-declaration and "
        f"direct the maintainer to a fully declared replacement commit. receipt={receipt!r}"
    )


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "declared_suite_paths",
    (
        ("tests/parity/test_alpha.py", "tests/parity/test_alpha.py"),
        ("tests/parity/test_beta.py", "tests/parity/test_alpha.py"),
        ("tests/parity/test_missing.py",),
    ),
    ids=("duplicate", "unordered", "missing-from-commit"),
)
def test_malformed_trailer_declaration_is_not_a_selectable_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    declared_suite_paths: tuple[str, ...],
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation."""
    # covers: R14
    repo = tmp_path / "repo"
    _init_declared_aggregate(repo, declared_suite_paths=declared_suite_paths)
    before = _ledger_records(repo)
    monkeypatch.setattr(
        verify_slice_commit,
        "des_spawn",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("pytest ran")),
    )
    monkeypatch.setattr(
        verify_slice_commit,
        "_run_verify_checks",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("E1/E2 ran")),
    )

    exit_code, receipt = _discover_prefactoring_aggregate(repo)

    assert (
        exit_code != 0
        and receipt.get("event") == "PrefactoringAggregateDiscoveryUnavailable"
        and receipt.get("reason") == "malformed-declared-aggregate"
        and _git_output(repo, "rev-parse", "HEAD") in json.dumps(receipt)
        and receipt.get("error")
        and receipt.get("how")
        and _ledger_records(repo) == before
    ), (
        "WHAT: malformed trailer provenance appeared as a selectable aggregate; WHY: duplicate, "
        "unordered, or absent paths cannot name one complete proof population; HOW: refuse it before "
        f"pytest, E1/E2, or a ledger write. receipt={receipt!r}"
    )


@pytest.mark.negative_at
def test_legacy_prefactoring_commits_are_unavailable_without_side_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation."""
    # covers: R17
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "aggregate@example.test")
    _git(repo, "config", "user.name", "Aggregate Maintainer")
    delta = repo / "docs" / "feature" / _FEATURE_ID / "feature-delta.md"
    delta.parent.mkdir(parents=True)
    delta.write_text(
        "# Feature Delta\n\n## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
        "| slice-01 | a maintainer inspects declared prefactoring evidence | pending | "
        "@prefactoring | existing evidence only |\n",
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(
        repo,
        "commit",
        "-q",
        "-m",
        "refactor: preserve documentation\n\nSlice-Id: slice-01",
    )
    (repo / "README.md").write_text("second suite-less candidate\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "refactor: retain notes\n\nSlice-Id: slice-01")
    before_status = _git_output(repo, "status", "--porcelain")
    before_records = _ledger_records(repo)

    def runner_must_not_run(*_args: object, **_kwargs: object) -> object:
        raise AssertionError(
            "WHAT: discovery invoked pytest; WHY: suite-less candidates are unavailable "
            "before execution; HOW: return the typed discovery outcome read-only."
        )

    def verification_must_not_run(*_args: object, **_kwargs: object) -> object:
        raise AssertionError(
            "WHAT: discovery entered seal verification; WHY: unavailable candidate discovery "
            "cannot mint evidence; HOW: return before E1/E2 verification."
        )

    def ledger_must_not_append(*_args: object, **_kwargs: object) -> object:
        raise AssertionError(
            "WHAT: discovery appended ledger evidence; WHY: it only observes candidates; "
            "HOW: preserve the ledger while reporting unavailability."
        )

    monkeypatch.setattr(verify_slice_commit, "des_spawn", runner_must_not_run)
    monkeypatch.setattr(
        verify_slice_commit, "_run_verify_checks", verification_must_not_run
    )
    monkeypatch.setattr(
        verify_slice_commit.AtCompletionLedger,
        "append_gate_event",
        ledger_must_not_append,
    )

    exit_code, receipt = _discover_prefactoring_aggregate(repo)

    assert (
        exit_code != 0
        and receipt.get("event") == "PrefactoringAggregateDiscoveryUnavailable"
        and receipt.get("reason") == "legacy-or-missing-declaration"
        and receipt.get("error")
        and receipt.get("how")
        and _ledger_records(repo) == before_records
        and _git_output(repo, "status", "--porcelain") == before_status
    ), (
        "WHAT: a Slice-Id-only history was treated as bounded evidence; WHY: slice provenance "
        "does not declare a proof population; HOW: emit legacy-or-missing-declaration before pytest, E1/E2, "
        f"or ledger mutation. receipt={receipt!r} records={_ledger_records(repo)!r}"
    )


@pytest.mark.negative_at
def test_maintainer_receives_every_usable_prefactoring_candidate_before_selecting_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation."""
    # covers: R14
    repo = tmp_path / "repo"
    first_members = _init_declared_aggregate(repo)
    first_sha = _git_output(repo, "rev-parse", "HEAD")
    (repo / "tests" / "parity" / "test_delta.py").write_text(
        "def test_new_parity_holds():\n    assert True\n", encoding="utf-8"
    )
    (repo / "README.md").write_text("second candidate\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(
        repo,
        "commit",
        "-q",
        "-m",
        "refactor: retain parity\n\nSlice-Id: slice-01\n"
        "Regression-Suite: tests/parity/test_alpha.py\n"
        "Regression-Suite: tests/parity/test_beta.py\n"
        "Regression-Suite: tests/parity/test_delta.py\n"
        "Regression-Suite: tests/parity/test_gamma.py",
    )
    second_sha = _git_output(repo, "rev-parse", "HEAD")
    monkeypatch.setattr(
        verify_slice_commit,
        "des_spawn",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("pytest ran")),
    )

    exit_code, receipt = _discover_prefactoring_aggregate(repo)

    expected_candidates = [
        {
            "commit_sha": commit_sha,
            "declared_suite_paths": suite_paths,
            "declaration_digest": _declaration_digest(tuple(suite_paths)),
            "provenance": "commit-trailer",
        }
        for commit_sha, suite_paths in sorted(
            (
                (first_sha, sorted(first_members)),
                (
                    second_sha,
                    sorted((*first_members, "tests/parity/test_delta.py")),
                ),
            )
        )
    ]
    assert (
        exit_code == 0
        and receipt
        == {
            "event": "PrefactoringAggregateDiscovery",
            "feature_id": _FEATURE_ID,
            "slice_id": _SLICE_ID,
            "candidates": expected_candidates,
            "aggregate": "UNDECLARED",
        }
        and not _ledger_records(repo)
    ), (
        "WHAT: discovery did not list the complete usable candidate population; WHY: selecting "
        "newest or one representative hides competing provenance; HOW: emit every full SHA with "
        f"its lexically sorted committed paths before declaration. receipt={receipt!r}"
    )


@pytest.mark.negative_at
def test_discovery_keeps_usable_candidates_when_a_sibling_has_no_committed_suites(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation."""
    # covers: R14
    repo = tmp_path / "repo"
    usable_members = _init_declared_aggregate(repo)
    usable_sha = _git_output(repo, "rev-parse", "HEAD")
    for member in usable_members:
        (repo / member).unlink()
    _git(repo, "add", "-A")
    _git(
        repo,
        "commit",
        "-q",
        "-m",
        "refactor: remove obsolete parity suites\n\nSlice-Id: slice-01",
    )
    before_status = _git_output(repo, "status", "--porcelain")
    before_records = _ledger_records(repo)

    def pytest_must_not_run(*_args: object, **_kwargs: object) -> object:
        raise AssertionError(
            "WHAT: discovery invoked pytest; WHY: candidate projection is read-only; "
            "HOW: retain usable committed candidates without entering sealing."
        )

    monkeypatch.setattr(verify_slice_commit, "des_spawn", pytest_must_not_run)
    exit_code, receipt = _discover_prefactoring_aggregate(repo)

    assert (
        exit_code == 0
        and receipt
        == {
            "event": "PrefactoringAggregateDiscovery",
            "feature_id": _FEATURE_ID,
            "slice_id": _SLICE_ID,
            "candidates": [
                {
                    "commit_sha": usable_sha,
                    "declared_suite_paths": list(usable_members),
                    "declaration_digest": _declaration_digest(usable_members),
                    "provenance": "commit-trailer",
                }
            ],
            "aggregate": "UNDECLARED",
        }
        and _ledger_records(repo) == before_records
        and _git_output(repo, "status", "--porcelain") == before_status
    ), (
        "WHAT: a sibling without committed Python suites made usable discovery unavailable; "
        "WHY: a maintainer still needs every usable full-SHA candidate and its exact committed "
        "suite paths; HOW: exclude unusable siblings, reserve unavailable for an empty usable "
        f"population or unreadable evidence, and keep discovery read-only. receipt={receipt!r}"
    )


def test_explicit_full_sha_selection_binds_the_aggregate_seal_to_that_candidate(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change."""
    # covers: R15
    repo = tmp_path / "repo"
    first_members = _init_declared_aggregate(repo)
    selected_sha = _git_output(repo, "rev-parse", "HEAD")
    (repo / "README.md").write_text("later candidate\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "refactor: later candidate\n\nSlice-Id: slice-01")

    exit_code, receipt = _verify_aggregate(repo, first_members, commit_sha=selected_sha)
    record = _verified_ledger_record(repo)

    assert (
        exit_code == 0
        and receipt.get("commit_sha") == selected_sha
        and (record.get("commit_sha") == selected_sha)
        and tuple(receipt.get("declared_suite_paths", ())) == first_members
        and tuple(record.get("declared_suite_paths", ())) == first_members
        and receipt.get("declaration_digest") == _declaration_digest(first_members)
        and record.get("declaration_digest") == _declaration_digest(first_members)
        and tuple(receipt.get("regression_test_files_executed", ())) == first_members
    ), (
        "WHAT: the aggregate seal was not bound to the maintainer's full-SHA selection; WHY: "
        "a later or default candidate could certify different evidence; HOW: validate the listed full "
        "SHA and persist its canonical declared tuple and digest with the executed tuple. "
        f"receipt={receipt!r}"
    )


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "declaration_shape",
    ("strict-subset", "excess-member"),
)
def test_candidate_selection_refuses_a_declared_tuple_that_differs_from_committed_suites(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    declaration_shape: str,
) -> None:
    """CONTRACT_SHAPE: bounded-change."""
    # covers: R15
    # covers: R16
    repo = tmp_path / "repo"
    committed_members = _init_declared_aggregate(repo)
    selected_sha = _git_output(repo, "rev-parse", "HEAD")
    declared_members = (
        committed_members[:-1]
        if declaration_shape == "strict-subset"
        else (*committed_members, "tests/parity/test_unlisted.py")
    )
    before = _ledger_records(repo)
    pytest_invocations: list[tuple[object, ...]] = []

    def pytest_must_not_run(*args: object, **_kwargs: object) -> object:
        pytest_invocations.append(args)
        raise AssertionError(
            "WHAT: a tuple that differs from the selected candidate reached pytest; "
            "WHY: only the candidate's complete committed suite population is evidence; "
            "HOW: refuse the tuple before execution, evidence, or a ledger append."
        )

    monkeypatch.setattr(verify_slice_commit, "des_spawn", pytest_must_not_run)
    exit_code, receipt = _verify_public(
        _aggregate_argv(repo, declared_members, commit_sha=selected_sha)
    )

    assert (
        exit_code != 0
        and receipt.get("event") == "PrefactoringAggregateSelectionRefused"
        and receipt.get("requested_commit") == selected_sha
        and receipt.get("reason") == "declared-suite-tuple-mismatch"
        and receipt.get("error")
        and receipt.get("how")
        and not pytest_invocations
        and _ledger_records(repo) == before
    ), (
        "WHAT: a strict subset or excess declared suite tuple bypassed candidate selection; WHY: "
        "a selected commit can be certified only by its complete lexically sorted committed tuple; "
        "HOW: compare the declaration with the discovered candidate before pytest, E1/E2, or a "
        f"ledger append. shape={declaration_shape!r} receipt={receipt!r} "
        f"pytest_invocations={pytest_invocations!r} records={_ledger_records(repo)!r}"
    )


@pytest.mark.negative_at
def test_aggregate_declaration_without_feature_identity_refuses_before_legacy_processing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CONTRACT_SHAPE: bounded-change."""
    # covers: R16
    repo = tmp_path / "repo"
    members = _init_declared_aggregate(repo)
    selected_sha = _git_output(repo, "rev-parse", "HEAD")
    before = _ledger_records(repo)
    legacy_invocations: list[tuple[object, ...]] = []
    pytest_invocations: list[tuple[object, ...]] = []

    def legacy_must_not_run(*args: object, **_kwargs: object) -> int:
        legacy_invocations.append(args)
        raise AssertionError(
            "WHAT: an aggregate declaration without feature identity reached legacy processing; "
            "WHY: legacy mode cannot select a prefactoring candidate; HOW: refuse before it runs."
        )

    def pytest_must_not_run(*args: object, **_kwargs: object) -> object:
        pytest_invocations.append(args)
        raise AssertionError("pytest ran after a featureless aggregate declaration")

    monkeypatch.setattr(
        verify_slice_commit, "_run_legacy_completeness", legacy_must_not_run
    )
    monkeypatch.setattr(verify_slice_commit, "des_spawn", pytest_must_not_run)
    exit_code, receipt = _verify_public(
        [
            "--repo",
            str(repo),
            "--commit",
            selected_sha,
            "--at-kind",
            "pytest-regression-aggregate",
            "--regression-test-files",
            *members,
        ]
    )

    assert (
        exit_code != 0
        and receipt.get("event") == "PrefactoringAggregateSelectionRefused"
        and receipt.get("reason") == "feature-id-required"
        and receipt.get("error")
        and receipt.get("how")
        and not legacy_invocations
        and not pytest_invocations
        and _ledger_records(repo) == before
    ), (
        "WHAT: a featureless aggregate declaration entered legacy processing; WHY: that route has "
        "no candidate identity to validate; HOW: require --feature-id and refuse before legacy "
        f"execution, pytest, evidence, or ledger mutation. receipt={receipt!r} "
        f"legacy_invocations={legacy_invocations!r} pytest_invocations={pytest_invocations!r} "
        f"records={_ledger_records(repo)!r}"
    )


@pytest.mark.negative_at
@pytest.mark.parametrize(
    ("requested_commit", "extra_arguments"),
    [
        (None, ()),
        ("a" * 12, ()),
        ("f" * 40, ()),
        ("HEAD", ()),
        (None, ("--slice-id", _SLICE_ID)),
    ],
    ids=("missing", "abbreviated", "unlisted", "head", "override-bypass"),
)
def test_untrusted_candidate_selection_refuses_before_execution_or_ledger_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    requested_commit: str | None,
    extra_arguments: tuple[str, ...],
) -> None:
    """CONTRACT_SHAPE: bounded-change."""
    # covers: R16
    repo = tmp_path / "repo"
    members = _init_declared_aggregate(repo)
    before = _ledger_records(repo)

    def pytest_must_not_run(*_args: object, **_kwargs: object) -> object:
        raise AssertionError(
            "WHAT: an invalid selection reached execution; WHY: selection must be validated "
            "before proof; HOW: refuse it before pytest, E1, E2, or ledger mutation."
        )

    monkeypatch.setattr(verify_slice_commit, "des_spawn", pytest_must_not_run)
    argv = [
        "--repo",
        str(repo),
        "--feature-id",
        _FEATURE_ID,
        "--at-kind",
        "pytest-regression-aggregate",
        "--regression-test-files",
        *members,
    ]
    if requested_commit is not None:
        argv.extend(("--commit", requested_commit))
    argv.extend(extra_arguments)
    exit_code, receipt = _verify_public(argv)

    assert (
        exit_code != 0
        and receipt.get("event") == "PrefactoringAggregateSelectionRefused"
        and (receipt.get("requested_commit") == requested_commit)
        and receipt.get("error")
        and receipt.get("how")
        and _ledger_records(repo) == before
    ), (
        "WHAT: an omitted, abbreviated, unlisted, HEAD, or override selection did not stop "
        "before sealing; WHY: a candidate must be chosen from the displayed full-SHA population; "
        f"HOW: refuse the request and direct the maintainer to discovery. receipt={receipt!r}"
    )


@pytest.mark.negative_at
def test_unreadable_prefactoring_history_is_unavailable_without_pytest_or_ledger_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation."""
    # covers: R15
    repo = tmp_path / "repo"
    _init_declared_aggregate(repo)

    def unreadable_history(*_args: object, **_kwargs: object) -> str:
        raise OSError("history is unreadable")

    monkeypatch.setattr(verify_slice_commit, "_git", unreadable_history)
    monkeypatch.setattr(
        verify_slice_commit,
        "des_spawn",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("pytest ran")),
    )
    exit_code, receipt = _discover_prefactoring_aggregate(repo)

    assert (
        exit_code != 0
        and receipt.get("event") == "PrefactoringAggregateDiscoveryUnavailable"
        and (receipt.get("reason") == "history-unreadable")
        and receipt.get("error")
        and receipt.get("how")
        and not _ledger_records(repo)
    ), (
        "WHAT: unreadable candidate history was collapsed into an empty or successful discovery; WHY: "
        "the CLI cannot prove reachability or SHA/message binding; HOW: emit an unavailable result and "
        f"ask the maintainer to restore readable committed evidence. receipt={receipt!r}"
    )


@pytest.mark.negative_at
def test_existing_verified_receipt_excludes_its_prefactoring_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation."""
    # covers: R15
    repo = tmp_path / "repo"
    members = _init_declared_aggregate(repo)
    seal_code, _ = _verify_aggregate(repo, members)
    before = _ledger_records(repo)
    monkeypatch.setattr(
        verify_slice_commit,
        "des_spawn",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("pytest ran")),
    )

    exit_code, receipt = _discover_prefactoring_aggregate(repo)

    assert (
        seal_code == 0
        and exit_code != 0
        and (receipt.get("event") == "PrefactoringAggregateDiscoveryUnavailable")
        and receipt.get("reason") == "no-trailer-bound-candidate"
        and (_ledger_records(repo) == before)
    ), (
        "WHAT: discovery offered a candidate that already has a matching verified receipt; WHY: "
        "a completed slice must not be rediscovered for a second implicit seal; HOW: consult the "
        f"ledger seam and exclude the matching commit without appending a record. receipt={receipt!r}"
    )


@pytest.mark.negative_at
def test_corrupt_prefactoring_ledger_is_unavailable_without_overwriting_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation."""
    # covers: R15
    repo = tmp_path / "repo"
    _init_declared_aggregate(repo)
    ledger = repo / ".nwave" / "telemetry" / "atdd-pure" / f"{_FEATURE_ID}.jsonl"
    ledger.parent.mkdir(parents=True)
    corrupt = "{not-json}\n"
    ledger.write_text(corrupt, encoding="utf-8")
    monkeypatch.setattr(
        verify_slice_commit,
        "des_spawn",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("pytest ran")),
    )

    exit_code, receipt = _discover_prefactoring_aggregate(repo)

    assert (
        exit_code != 0
        and receipt.get("event") == "PrefactoringAggregateDiscoveryUnavailable"
        and (receipt.get("reason") == "ledger-unreadable")
        and receipt.get("error")
        and receipt.get("how")
        and ledger.read_text(encoding="utf-8") == corrupt
    ), (
        "WHAT: corrupt receipt evidence became an empty ledger or was overwritten; WHY: discovery "
        "cannot prove which candidates were already sealed; HOW: return unavailable and preserve the "
        f"ledger for repair. receipt={receipt!r}"
    )


@pytest.mark.negative_at
def test_invalid_utf8_prefactoring_ledger_is_unavailable_without_crashing_or_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation."""
    # covers: R15
    repo = tmp_path / "repo"
    _init_declared_aggregate(repo)
    ledger = repo / ".nwave" / "telemetry" / "atdd-pure" / f"{_FEATURE_ID}.jsonl"
    ledger.parent.mkdir(parents=True)
    corrupt = b"\xff\xfe\n"
    ledger.write_bytes(corrupt)
    monkeypatch.setattr(
        verify_slice_commit,
        "des_spawn",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("pytest ran")),
    )

    exit_code, receipt = _discover_prefactoring_outcome(repo)

    assert (
        exit_code != 0
        and receipt.get("event") == "PrefactoringAggregateDiscoveryUnavailable"
        and (receipt.get("reason") == "ledger-unreadable")
        and receipt.get("error")
        and receipt.get("how")
        and ledger.read_bytes() == corrupt
    ), (
        "WHAT: invalid UTF-8 in the ledger crashed discovery or became absent evidence; WHY: the "
        "candidate cannot be trusted until existing receipts are readable; HOW: return the typed "
        f"unavailable outcome and preserve the bytes for repair. receipt={receipt!r}"
    )


@pytest.mark.negative_at
def test_directory_at_prefactoring_ledger_path_is_unavailable_without_candidate_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation."""
    # covers: R15
    repo = tmp_path / "repo"
    _init_declared_aggregate(repo)
    ledger = repo / ".nwave" / "telemetry" / "atdd-pure" / f"{_FEATURE_ID}.jsonl"
    ledger.parent.mkdir(parents=True)
    ledger.mkdir()
    monkeypatch.setattr(
        verify_slice_commit,
        "des_spawn",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("pytest ran")),
    )

    exit_code, receipt = _discover_prefactoring_outcome(repo)

    assert (
        exit_code != 0
        and receipt.get("event") == "PrefactoringAggregateDiscoveryUnavailable"
        and (receipt.get("reason") == "ledger-unreadable")
        and receipt.get("error")
        and receipt.get("how")
        and ledger.is_dir()
    ), (
        "WHAT: a directory at the expected ledger path was treated as an absent ledger; WHY: it "
        "prevents trustworthy exclusion of prior receipts; HOW: return unavailable before candidate "
        f"selection and preserve the path for repair. receipt={receipt!r}"
    )


@pytest.mark.negative_at
def test_dangling_prefactoring_ledger_symlink_is_unavailable_without_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation."""
    # covers: R15
    repo = tmp_path / "repo"
    _init_declared_aggregate(repo)
    ledger = repo / ".nwave" / "telemetry" / "atdd-pure" / f"{_FEATURE_ID}.jsonl"
    ledger.parent.mkdir(parents=True)
    target = ledger.parent / "missing-ledger.jsonl"
    ledger.symlink_to(target)
    monkeypatch.setattr(
        verify_slice_commit,
        "des_spawn",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("pytest ran")),
    )

    exit_code, receipt = _discover_prefactoring_outcome(repo)

    assert (
        exit_code != 0
        and receipt.get("event") == "PrefactoringAggregateDiscoveryUnavailable"
        and (receipt.get("reason") == "ledger-unreadable")
        and receipt.get("error")
        and receipt.get("how")
        and ledger.is_symlink()
        and not target.exists()
    ), (
        "WHAT: a dangling ledger symlink was treated as absent or replaced; WHY: discovery cannot "
        "trust prior receipt exclusion through an unreadable evidence path; HOW: return ledger-unreadable "
        f"without selecting a candidate or changing the link. receipt={receipt!r}"
    )


@pytest.mark.negative_at
def test_non_prefactoring_slice_is_unavailable_before_history_or_sealing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation."""
    # covers: R15
    repo = tmp_path / "repo"
    _init_declared_aggregate(repo, annotation="@infrastructure")
    monkeypatch.setattr(
        verify_slice_commit,
        "des_spawn",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("pytest ran")),
    )

    exit_code, receipt = _discover_prefactoring_aggregate(repo)

    assert (
        exit_code != 0
        and receipt.get("event") == "PrefactoringAggregateDiscoveryUnavailable"
        and (receipt.get("reason") == "no-prefactoring-lane")
        and receipt.get("error")
        and receipt.get("how")
        and not _ledger_records(repo)
    ), (
        "WHAT: discovery accepted a slice outside the declared prefactoring lane; WHY: a directory "
        "or test-name inference can select unrelated work; HOW: require the Slice Plan's @prefactoring "
        f"annotation before reading candidates or sealing. receipt={receipt!r}"
    )


@pytest.mark.negative_at
@pytest.mark.parametrize(
    ("forbidden", "arguments"),
    [
        ("--commit", ("--commit", "HEAD")),
        (
            "--regression-test-file",
            ("--regression-test-file", "tests/parity/test_alpha.py"),
        ),
        (
            "--regression-test-files",
            ("--regression-test-files", "tests/parity/test_alpha.py"),
        ),
        ("--expected-head", ("--expected-head", "a" * 40)),
        ("--scope-feature-id", ("--scope-feature-id", _FEATURE_ID)),
        ("--at-kind", ("--at-kind", "pytest-regression-aggregate")),
    ],
)
def test_discovery_refuses_sealing_only_inputs_before_candidate_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    forbidden: str,
    arguments: tuple[str, ...],
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation."""
    # covers: R15
    repo = tmp_path / "repo"
    _init_declared_aggregate(repo)
    monkeypatch.setattr(
        verify_slice_commit,
        "des_spawn",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("pytest ran")),
    )

    exit_code, receipt = _discover_prefactoring_aggregate(repo, *arguments)

    assert (
        exit_code != 0
        and receipt.get("event") == "PrefactoringAggregateDiscoveryUnavailable"
        and (receipt.get("reason") == "forbidden-discovery-input")
        and receipt.get("forbidden_flag") == forbidden
        and receipt.get("error")
        and receipt.get("how")
        and not _ledger_records(repo)
    ), (
        "WHAT: discovery accepted a sealing-only input before candidate selection; WHY: the mode "
        "must expose a plan, never a hidden verification route; HOW: refuse the forbidden flag before "
        f"history, pytest, or ledger access. forbidden={forbidden!r} receipt={receipt!r}"
    )


def _historical_declaration_file(
    repo: Path,
    *,
    declaration_id: str,
    target_commit: str,
    members: tuple[str, ...],
    supersedes: str | None = None,
    correction_reason: str | None = None,
    completeness_attestation: str
    | None = "I examined the named parity evidence and attest this tuple is complete.",
    declarer: str = "Maria Santos",
) -> Path:
    """Create maintainer-supplied provenance; it never creates a declaration itself."""
    declaration = {
        "declaration_id": declaration_id,
        "target_commit": target_commit,
        "intent": "carpaccio gate parity",
        "suite_paths": list(members),
        "declarer": declarer,
        "declared_at": "2026-07-30T09:15:00Z",
        "source_evidence": [
            "release-notes/2026-06-14-carpaccio-parity.md",
            "review/PR-418-parity-audit.md",
        ],
        "completeness_attestation": completeness_attestation,
    }
    if supersedes is not None:
        declaration["supersedes"] = supersedes
    if correction_reason is not None:
        declaration["correction_reason"] = correction_reason
    source = repo / "migration-input" / f"{declaration_id}.json"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(json.dumps(declaration), encoding="utf-8")
    return source


def _seed_governed_migration_authority(
    repo: Path, *declarers: str, granted_at: str = "2026-01-15T00:00:00Z"
) -> Path:
    """Seed ADR-001's governed migration authority ledger for ``declarers``.

    Writes the repo-local, git-tracked-shaped grant ledger
    (``.nwave/governed-migration-authority.jsonl``, one JSON object per line:
    ``{"declarer": ..., "granted_at": ...}``) the future
    ``_register_historical_declaration`` authorization leg reads (ADR-001,
    docs/feature/prefactoring-aggregate-regression-seal/design/adrs/adr-001-
    governed-migration-authority-for-historical-declarer.md). Seeding this
    file is INERT today -- the only declarer check currently wired is the
    pre-existing non-empty-string test -- but it must exist NOW so a
    success-path scenario granting "Maria Santos" does not regress to
    ``unauthorized-declarer``/``migration-authority-unavailable`` the moment
    ADR-001's exact-match authorization check ships.
    """
    path = repo / ".nwave" / "governed-migration-authority.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps({"declarer": declarer, "granted_at": granted_at}) + "\n"
            for declarer in declarers
        ),
        encoding="utf-8",
    )
    return path


def _register_historical_declaration(
    repo: Path, source: Path
) -> tuple[int, dict[str, object]]:
    """Drive the future governed migration port, never a record-store seam."""
    return _verify_public(
        [
            "--repo",
            str(repo),
            "--feature-id",
            _FEATURE_ID,
            "--register-historical-prefactoring-aggregate",
            "--historical-declaration",
            str(source),
        ]
    )


def _init_trailerless_prefactoring_repo(repo: Path) -> None:
    """Build a repo whose target commit carries NO Slice-Id trailer at all.

    Unlike ``_init_declared_aggregate`` -- which unconditionally stamps a
    ``Slice-Id:`` trailer regardless of ``include_suite_declaration`` -- this
    fixture's single commit carries no ``Slice-Id:``/``Step-Id:`` trailer
    line whatsoever. The commit message deliberately mentions "slice-01" in
    ordinary prose (not as a trailer line) so a caller that verified
    trailer-absence with a naive substring search would be fooled; real
    verification must use git's own trailer parsing
    (``--format=%(trailers:key=Slice-Id,valueonly)``), exactly as this
    module's tests below do.

    This is the historically real population the governed historical
    declaration mechanism exists for (feature-delta.md scenario 6, C-8):
    a maintainer with a genuine prefactoring commit that predates the
    ``Slice-Id:`` trailer convention.
    """
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "aggregate@example.test")
    _git(repo, "config", "user.name", "Aggregate Maintainer")
    delta = repo / "docs" / "feature" / _FEATURE_ID / "feature-delta.md"
    delta.parent.mkdir(parents=True)
    delta.write_text(
        "# Feature Delta\n\n## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
        "| slice-01 | a maintainer seals the complete declared parity aggregate | pending | "
        "@prefactoring | existing evidence only |\n",
        encoding="utf-8",
    )
    suite = repo / "tests" / "parity" / "test_alpha.py"
    suite.parent.mkdir(parents=True, exist_ok=True)
    suite.write_text("def test_parity_holds():\n    assert True\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(
        repo,
        "commit",
        "-q",
        "-m",
        "refactor: preserve parity for slice-01 with no machine-readable trailer",
    )


def test_governed_historical_declaration_is_offered_for_a_commit_with_no_slice_id_trailer(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change."""
    # covers: R17
    repo = tmp_path / "legacy-repo"
    _init_trailerless_prefactoring_repo(repo)
    target_commit = _git_output(repo, "rev-parse", "HEAD")
    trailer_value = _git_output(
        repo,
        "log",
        "-1",
        "--format=%(trailers:key=Slice-Id,valueonly)",
        target_commit,
    )
    members = ("tests/parity/test_alpha.py",)
    source = _historical_declaration_file(
        repo,
        declaration_id="HAD-trailerless-parity-001",
        target_commit=target_commit,
        members=members,
    )
    _seed_governed_migration_authority(repo, "Maria Santos")

    registered_code, registered = _register_historical_declaration(repo, source)
    discovered_code, discovered = _discover_prefactoring_aggregate(repo)

    candidates = discovered.get("candidates", [])
    assert (
        trailer_value == ""
        and registered_code == 0
        and registered.get("event") == "HistoricalAggregateDeclarationRegistered"
        and discovered_code == 0
        and any(
            candidate.get("declaration_id") == "HAD-trailerless-parity-001"
            and candidate.get("commit_sha") == target_commit
            and tuple(candidate.get("declared_suite_paths", ())) == members
            and candidate.get("provenance") == "governed-historical-declaration"
            for candidate in candidates
            if isinstance(candidate, dict)
        )
    ), (
        "WHAT: a valid governed historical declaration for a commit carrying NO Slice-Id trailer "
        "was not offered as a selectable discovery candidate; WHY: the historical declaration "
        "mechanism exists precisely for commits that lack a machine-readable trailer -- gating "
        "discovery on trailer presence before it will honour the declaration defeats the "
        "declaration's entire purpose (feature-delta.md scenario 6, C-8); HOW: surface the "
        "registered declaration once it is valid and its declared suite exists at the target "
        "commit, independent of whether that commit itself carries a Slice-Id trailer. "
        f"trailer_value={trailer_value!r} registered={registered!r} discovered={discovered!r}"
    )


@pytest.mark.negative_at
def test_no_trailer_bound_candidate_refusal_survives_with_no_historical_declaration_either(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation."""
    # covers: R17
    repo = tmp_path / "legacy-repo"
    _init_trailerless_prefactoring_repo(repo)
    monkeypatch.setattr(
        verify_slice_commit,
        "des_spawn",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("pytest ran")),
    )

    exit_code, receipt = _discover_prefactoring_aggregate(repo)

    assert (
        exit_code != 0
        and receipt.get("event") == "PrefactoringAggregateDiscoveryUnavailable"
        and receipt.get("reason") == "no-trailer-bound-candidate"
        and receipt.get("error")
        and receipt.get("how")
        and not _ledger_records(repo)
    ), (
        "WHAT: the honest no-trailer-bound-candidate refusal changed shape when NEITHER a "
        "trailer-bound commit NOR any governed historical declaration exists; WHY: this refusal "
        "is correct for its real case (no evidence of any kind) and must not become collateral "
        "damage of fixing the trailerless-declaration discovery gap; HOW: keep refusing "
        f"no-trailer-bound-candidate when there is truly no selectable evidence. receipt={receipt!r}"
    )


def test_clean_tree_historical_declaration_is_discovered_selected_and_sealed(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change."""
    # covers: R17
    repo = tmp_path / "legacy-repo"
    members = _init_declared_aggregate(repo, include_suite_declaration=False)
    target_commit = _git_output(repo, "rev-parse", "HEAD")
    source = _historical_declaration_file(
        repo,
        declaration_id="HAD-carpaccio-parity-001",
        target_commit=target_commit,
        members=members,
    )
    _seed_governed_migration_authority(repo, "Maria Santos")

    registered_code, registered = _register_historical_declaration(repo, source)
    discovered_code, discovered = _discover_prefactoring_aggregate(repo)
    sealed_code, sealed = _verify_public(
        [
            *_aggregate_argv(repo, members, commit_sha=target_commit),
            "--historical-declaration-id",
            "HAD-carpaccio-parity-001",
        ]
    )

    candidates = discovered.get("candidates", [])
    assert (
        registered_code == discovered_code == sealed_code == 0
        and registered.get("event") == "HistoricalAggregateDeclarationRegistered"
        and any(
            candidate.get("declaration_id") == "HAD-carpaccio-parity-001"
            and candidate.get("commit_sha") == target_commit
            and tuple(candidate.get("declared_suite_paths", ())) == members
            and candidate.get("provenance") == "governed-historical-declaration"
            for candidate in candidates
            if isinstance(candidate, dict)
        )
        and sealed.get("historical_declaration_id") == "HAD-carpaccio-parity-001"
    ), (
        "WHAT: a clean legacy tree could not turn one governed finite declaration into a "
        "selectable complete proof; WHY: absent commit trailers must not force guessed membership; "
        "HOW: register the supplied provenance, display its exact tuple, and seal only that selected "
        f"declaration. registered={registered!r} discovered={discovered!r} sealed={sealed!r}"
    )


def test_governed_historical_declaration_seals_a_commit_with_no_slice_id_trailer(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change.

    The seal's own trailer resolution is independent of discovery -- round 7
    fixed discovery to offer a governed historical declaration for a commit
    with NO Slice-Id:/Step-Id: trailer at all (see
    ``test_governed_historical_declaration_is_offered_for_a_commit_with_no_slice_id_trailer``
    above), but ``main``'s aggregate path still calls ``_resolve_slice_ids``
    unconditionally inside ``_run_verify_checks`` -- it refuses
    ``MalformedInput`` before ever consulting the already-selected
    ``args.prefactoring_candidate``. Establishing an immutable migration
    declaration is pointless if it can never be sealed (feature-delta.md
    scenario 6): this asserts the seal itself must accept an explicitly
    selected, authorized, complete governed historical declaration on a
    trailerless commit and mint a real ``SliceCommitVerified`` record.
    """
    # covers: R17
    repo = tmp_path / "legacy-repo"
    _init_trailerless_prefactoring_repo(repo)
    target_commit = _git_output(repo, "rev-parse", "HEAD")
    trailer_value = _git_output(
        repo,
        "log",
        "-1",
        "--format=%(trailers:key=Slice-Id,valueonly)",
        target_commit,
    )
    members = ("tests/parity/test_alpha.py",)
    declaration_id = "HAD-trailerless-seal-001"
    source = _historical_declaration_file(
        repo,
        declaration_id=declaration_id,
        target_commit=target_commit,
        members=members,
    )
    _seed_governed_migration_authority(repo, "Maria Santos")
    registered_code, registered = _register_historical_declaration(repo, source)

    exit_code, receipt = _verify_public(
        [
            *_aggregate_argv(repo, members, commit_sha=target_commit),
            "--historical-declaration-id",
            declaration_id,
        ]
    )
    record = _verified_ledger_record(repo) if exit_code == 0 else {}

    assert (
        trailer_value == ""
        and registered_code == 0
        and exit_code == 0
        and receipt.get("historical_declaration_id") == declaration_id
        and tuple(receipt.get("regression_test_files_executed", ())) == members
        and record.get("event") == "SliceCommitVerified"
        and record.get("historical_declaration_id") == declaration_id
        and record.get("member_outcomes")
        == [{"path": member, "outcome": "passed"} for member in members]
    ), (
        "WHAT: an explicitly selected, authorized, complete governed historical declaration "
        "could not seal a commit carrying NO Slice-Id:/Step-Id: trailer, even though discovery "
        "now advertises it as a selectable candidate; WHY: establishing a migration declaration "
        "is pointless if it can never be sealed (feature-delta.md scenario 6) -- the seal's own "
        "trailer check must not be blind to a governed historical declaration discovery already "
        "offered; HOW: when --historical-declaration-id names an authorized, complete declaration "
        "whose suites exist and pass, seal it and record its declaration id and per-member "
        f"outcomes without requiring a Slice-Id trailer. trailer_value={trailer_value!r} "
        f"registered={registered!r} receipt={receipt!r} record={record!r}"
    )


@pytest.mark.negative_at
def test_trailerless_commit_without_historical_declaration_id_still_refuses_missing_trailer(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation.

    Sibling-branch pin (paired with the success test above): the ordinary
    sealing path -- no ``--historical-declaration-id`` supplied at all --
    must keep refusing a trailerless commit for its real, honest reason. A
    crafter must not "fix" the sibling success case by deleting or widening
    the trailer check outright; this must survive the fix byte-identically.
    """
    # covers: R17
    repo = tmp_path / "legacy-repo"
    _init_trailerless_prefactoring_repo(repo)
    target_commit = _git_output(repo, "rev-parse", "HEAD")
    members = ("tests/parity/test_alpha.py",)
    source = _historical_declaration_file(
        repo,
        declaration_id="HAD-trailerless-no-selection-001",
        target_commit=target_commit,
        members=members,
    )
    _seed_governed_migration_authority(repo, "Maria Santos")
    _register_historical_declaration(repo, source)
    before = _ledger_records(repo)

    exit_code, receipt = _verify_aggregate(repo, members, commit_sha=target_commit)

    assert (
        exit_code != 0
        and receipt.get("event") == "MalformedInput"
        and receipt.get("error") == "commit carries no Slice-Id:/Step-Id: trailer"
        and _ledger_records(repo) == before
    ), (
        "WHAT: a trailerless commit sealed (or refused for a different reason) even though the "
        "maintainer never selected a governed historical declaration; WHY: this refusal is "
        "correct for the ordinary sealing path and must not become collateral damage of "
        "honouring an explicitly selected declaration; HOW: keep refusing "
        f"'commit carries no Slice-Id:/Step-Id: trailer' when no --historical-declaration-id was "
        f"given. receipt={receipt!r}"
    )


@pytest.mark.negative_at
def test_historical_declaration_with_missing_suite_still_refuses_at_seal(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation.

    Second sibling-branch pin: honouring an explicitly selected historical
    declaration on a trailerless commit must not become a blanket bypass
    of member-evidence checking. A declaration whose suite does not exist
    must still refuse at seal with ``AggregateMemberMissing`` -- the SAME
    closed-vocabulary member-specific outcome the trailer-bound aggregate
    path already uses (see ``_run_regression_aggregate``), never a silent
    or differently-shaped success.
    """
    # covers: R17
    repo = tmp_path / "legacy-repo"
    _init_trailerless_prefactoring_repo(repo)
    target_commit = _git_output(repo, "rev-parse", "HEAD")
    missing_suite = "tests/parity/test_GHOST.py"
    declaration_id = "HAD-trailerless-ghost-001"
    source = _historical_declaration_file(
        repo,
        declaration_id=declaration_id,
        target_commit=target_commit,
        members=(missing_suite,),
    )
    _seed_governed_migration_authority(repo, "Maria Santos")
    _register_historical_declaration(repo, source)
    before = _ledger_records(repo)

    exit_code, receipt = _verify_public(
        [
            *_aggregate_argv(repo, (missing_suite,), commit_sha=target_commit),
            "--historical-declaration-id",
            declaration_id,
        ]
    )

    assert (
        exit_code != 0
        and receipt.get("event") == "AggregateMemberMissing"
        and receipt.get("member") == missing_suite
        and _ledger_records(repo) == before
    ), (
        "WHAT: a governed historical declaration naming a suite absent from the worktree/commit "
        "sealed, or refused under the wrong outcome, on a trailerless commit; WHY: honouring an "
        "explicit historical-declaration selection must not bypass member-evidence checking; HOW: "
        "run the same AggregateMemberMissing member check the trailer-bound aggregate path already "
        f"applies, naming the missing member, before any ledger write. receipt={receipt!r}"
    )


@pytest.mark.negative_at
def test_missing_aggregate_flags_refusal_names_the_flags_not_the_absent_trailer(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation.

    Vera's eighth examine + a same-repo, same-commit, same-trailerless-commit
    side-by-side reproduction: passing ``--historical-declaration-id`` WITHOUT
    ``--at-kind``/``--regression-test-files`` refuses ``MalformedInput:
    "commit carries no Slice-Id:/Step-Id: trailer"``, while the IDENTICAL
    command plus ``--at-kind pytest-regression-aggregate
    --regression-test-files <suite>`` succeeds with ``SliceCommitVerified``
    (see ``test_governed_historical_declaration_seals_a_commit_with_no_slice_id_trailer``
    above) -- the round-8 slice-identity fallback is reached only on the
    aggregate path. The refusal names the WRONG cause: it blames a missing
    trailer when the real cause is the two missing flags, sending a
    maintainer who follows discovery to fix something that is not the
    problem -- the sixth instance in this file of a refusal that misdirects.
    A human explicitly deferred deriving ``--at-kind``/
    ``--regression-test-files`` from the selected declaration to a later
    DISCUSS/DESIGN pass (it would make the CLI contract's flags conditional);
    THE FIX IS THE MESSAGE, NOT THE CONTRACT. This asserts: the refusal must
    name the missing ``--at-kind``/``--regression-test-files`` flags and must
    never blame the absent trailer as the cause; a maintainer who follows
    that guidance literally (adds exactly those two flags) reaches a
    successful seal; and both sibling branches survive unchanged -- with
    BOTH aggregate flags present the seal still succeeds on this trailerless
    commit, and with NO ``--historical-declaration-id`` at all the ordinary
    missing-trailer refusal is still correct -- so a crafter cannot "fix"
    this by flattening the aggregate and ordinary paths into one generic
    response.
    """
    # covers: R17
    repo = tmp_path / "legacy-repo"
    _init_trailerless_prefactoring_repo(repo)
    target_commit = _git_output(repo, "rev-parse", "HEAD")
    members = ("tests/parity/test_alpha.py",)
    declaration_id = "HAD-trailerless-misdirected-refusal-001"
    source = _historical_declaration_file(
        repo,
        declaration_id=declaration_id,
        target_commit=target_commit,
        members=members,
    )
    _seed_governed_migration_authority(repo, "Maria Santos")
    _register_historical_declaration(repo, source)
    before = _ledger_records(repo)

    # The human's exact FAILS command: --historical-declaration-id WITHOUT
    # the aggregate flags.
    under_specified_argv = [
        "--repo",
        str(repo),
        "--commit",
        target_commit,
        "--feature-id",
        _FEATURE_ID,
        "--historical-declaration-id",
        declaration_id,
    ]
    misdirected_exit_code, misdirected = _verify_public(under_specified_argv)
    misdirected_text = (
        f"{misdirected.get('error', '')} {misdirected.get('how', '')}".lower()
    )

    # Ordinary sibling branch: no --historical-declaration-id at all must
    # still refuse the trailerless commit for its real, honest reason
    # (reuses the SAME aggregate-argv helper the passing sibling test above
    # already exercises for this exact property).
    ordinary_exit_code, ordinary = _verify_aggregate(
        repo, members, commit_sha=target_commit
    )
    unmutated_after_refusals = _ledger_records(repo)

    # Mechanically-compliant maintainer: add exactly the two flags the
    # refusal should have named, nothing more, and retry once -- the human's
    # exact WORKS command.
    guided_exit_code, guided = _verify_public(
        [
            *under_specified_argv,
            "--at-kind",
            "pytest-regression-aggregate",
            "--regression-test-files",
            *members,
        ]
    )
    guided_record = _verified_ledger_record(repo) if guided_exit_code == 0 else {}

    assert (
        misdirected_exit_code != 0
        and "--at-kind" in misdirected_text
        and "--regression-test-files" in misdirected_text
        and "trailer" not in misdirected_text
        and ordinary_exit_code != 0
        and ordinary.get("event") == "MalformedInput"
        and ordinary.get("error") == "commit carries no Slice-Id:/Step-Id: trailer"
        and unmutated_after_refusals == before
        and guided_exit_code == 0
        and guided.get("event") == "SliceCommitVerified"
        and guided.get("historical_declaration_id") == declaration_id
        and guided_record.get("historical_declaration_id") == declaration_id
    ), (
        "WHAT: the under-specified invocation (--historical-declaration-id without "
        "--at-kind/--regression-test-files) either failed to name the two missing "
        "flags, or still blamed the absent trailer, or the guided retry did not seal, "
        "or a sibling branch (the ordinary no-selection refusal, or the fully-flagged "
        "success) changed shape; WHY: a refusal that names the wrong cause sends a "
        "maintainer who follows discovery to fix something that is not the problem -- "
        "the sixth instance of this misdirection class in this file; HOW: when "
        "--historical-declaration-id is supplied but the aggregate flags are absent, "
        "name --at-kind and --regression-test-files as the missing input instead of "
        "the trailer, while leaving the guided-success and no-selection sibling "
        f"branches byte-identical. misdirected={misdirected!r} ordinary={ordinary!r} "
        f"guided={guided!r}"
    )


@pytest.mark.negative_at
@pytest.mark.parametrize(
    ("members", "completeness_attestation", "declarer", "reason"),
    [
        (
            ("tests/parity/test_alpha.py",),
            None,
            "Maria Santos",
            "completeness-attestation-required",
        ),
        (
            ("tests/parity/test_alpha.py", "tests/parity/test_alpha.py"),
            "complete",
            "Maria Santos",
            "duplicate-suite-path",
        ),
        (
            ("../outside/test_stolen.py",),
            "complete",
            "Maria Santos",
            "unsafe-suite-path",
        ),
        (("tests/parity/test_alpha.py",), "complete", "", "unauthorized-declarer"),
    ],
    ids=("incomplete", "duplicate", "unsafe", "unauthorized"),
)
def test_historical_declaration_refuses_incomplete_or_unsafe_evidence_before_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    members: tuple[str, ...],
    completeness_attestation: str | None,
    declarer: str,
    reason: str,
) -> None:
    """CONTRACT_SHAPE: bounded-change."""
    # covers: R18
    repo = tmp_path / "legacy-repo"
    _init_declared_aggregate(repo, include_suite_declaration=False)
    target_commit = _git_output(repo, "rev-parse", "HEAD")
    source = _historical_declaration_file(
        repo,
        declaration_id=f"HAD-refusal-{reason}",
        target_commit=target_commit,
        members=members,
        completeness_attestation=completeness_attestation,
        declarer=declarer,
    )
    # Grant "Maria Santos" (the non-unauthorized parametrizations' declarer)
    # so ADR-001's authorization leg -- evaluated BEFORE the
    # completeness/duplicate/unsafe checks this test targets -- never
    # preempts the intended refusal reason with `unauthorized-declarer` /
    # `migration-authority-unavailable`. Inert for the "unauthorized" case
    # (empty declarer), which already refuses at the pre-existing
    # non-empty-string test.
    _seed_governed_migration_authority(repo, "Maria Santos")
    before = _ledger_records(repo)

    monkeypatch.setattr(
        verify_slice_commit,
        "des_spawn",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("pytest must not run while historical evidence is invalid")
        ),
    )
    exit_code, receipt = _register_historical_declaration(repo, source)

    assert (
        exit_code != 0
        and receipt.get("event") == "HistoricalAggregateDeclarationRefused"
        and receipt.get("reason") == reason
        and receipt.get("error")
        and receipt.get("how")
        and _ledger_records(repo) == before
    ), (
        "WHAT: invalid historical evidence registered or reached execution; WHY: incomplete, unsafe, "
        "duplicate, or unauthorized provenance cannot establish membership; HOW: refuse the named "
        f"defect before a declaration, pytest run, or seal. receipt={receipt!r}"
    )


@pytest.mark.negative_at
def test_conflicting_historical_declarations_refuse_discovery_without_selecting_a_winner(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation."""
    # covers: R19
    repo = tmp_path / "legacy-repo"
    members = _init_declared_aggregate(repo, include_suite_declaration=False)
    target_commit = _git_output(repo, "rev-parse", "HEAD")
    first = _historical_declaration_file(
        repo,
        declaration_id="HAD-carpaccio-parity-001",
        target_commit=target_commit,
        members=members,
    )
    second = _historical_declaration_file(
        repo,
        declaration_id="HAD-carpaccio-parity-002",
        target_commit=target_commit,
        members=members[:2],
    )
    _seed_governed_migration_authority(repo, "Maria Santos")

    _register_historical_declaration(repo, first)
    _register_historical_declaration(repo, second)
    exit_code, receipt = _discover_prefactoring_aggregate(repo)

    assert (
        exit_code != 0
        and receipt.get("event") == "HistoricalAggregateDeclarationAmbiguous"
        and receipt.get("reason") == "conflicting-historical-declarations"
        and "HAD-carpaccio-parity-001" in json.dumps(receipt)
        and "HAD-carpaccio-parity-002" in json.dumps(receipt)
        and not _ledger_records(repo)
    ), (
        "WHAT: conflicting governed declarations silently produced a candidate; WHY: neither record "
        "can outrank the other or be merged; HOW: name both declaration identities and refuse discovery. "
        f"receipt={receipt!r}"
    )


def test_historical_correction_appends_a_linked_successor_without_rewriting_the_original(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation."""
    # covers: R20
    repo = tmp_path / "legacy-repo"
    members = _init_declared_aggregate(repo, include_suite_declaration=False)
    target_commit = _git_output(repo, "rev-parse", "HEAD")
    original = _historical_declaration_file(
        repo,
        declaration_id="HAD-carpaccio-parity-001",
        target_commit=target_commit,
        members=members,
    )
    correction = _historical_declaration_file(
        repo,
        declaration_id="HAD-carpaccio-parity-002",
        target_commit=target_commit,
        members=members,
        supersedes="HAD-carpaccio-parity-001",
        correction_reason="the first source-evidence reference omitted the audit number",
    )
    _seed_governed_migration_authority(repo, "Maria Santos")

    first_code, first = _register_historical_declaration(repo, original)
    second_code, second = _register_historical_declaration(repo, correction)
    discovery_code, discovery = _discover_prefactoring_aggregate(repo)

    assert (
        first_code == second_code == discovery_code == 0
        and first.get("declaration_id") == "HAD-carpaccio-parity-001"
        and second.get("declaration_id") == "HAD-carpaccio-parity-002"
        and second.get("supersedes") == "HAD-carpaccio-parity-001"
        and second.get("correction_reason")
        and any(
            candidate.get("declaration_id") == "HAD-carpaccio-parity-002"
            and candidate.get("supersedes") == "HAD-carpaccio-parity-001"
            for candidate in discovery.get("candidates", [])
            if isinstance(candidate, dict)
        )
    ), (
        "WHAT: correcting historical provenance rewrote or hid the original declaration; WHY: audit "
        "history must distinguish correction from quiet editing; HOW: append a linked successor with "
        f"a reason and preserve both identities. first={first!r} second={second!r} discovery={discovery!r}"
    )


def test_historical_aggregate_seal_receipt_binds_declaration_and_every_member_outcome(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change."""
    # covers: R21
    repo = tmp_path / "legacy-repo"
    members = _init_declared_aggregate(repo, include_suite_declaration=False)
    target_commit = _git_output(repo, "rev-parse", "HEAD")
    source = _historical_declaration_file(
        repo,
        declaration_id="HAD-carpaccio-parity-001",
        target_commit=target_commit,
        members=members,
    )
    _seed_governed_migration_authority(repo, "Maria Santos")
    _register_historical_declaration(repo, source)

    exit_code, receipt = _verify_public(
        [
            *_aggregate_argv(repo, members, commit_sha=target_commit),
            "--historical-declaration-id",
            "HAD-carpaccio-parity-001",
        ]
    )
    member_outcomes = receipt.get("member_outcomes", [])
    assert (
        exit_code == 0
        and receipt.get("historical_declaration_id") == "HAD-carpaccio-parity-001"
        and receipt.get("commit_sha") == target_commit
        and tuple(receipt.get("regression_test_files_executed", ())) == members
        and {
            outcome.get("path")
            for outcome in member_outcomes
            if isinstance(outcome, dict)
        }
        == set(members)
        and all(
            outcome.get("outcome") == "passed"
            for outcome in member_outcomes
            if isinstance(outcome, dict)
        )
    ), (
        "WHAT: a historical aggregate seal lacks declaration identity or a member-level result; WHY: "
        "a later auditor cannot join the proof to its authority or detect an omitted suite; HOW: record "
        f"the immutable declaration id, target commit, exact tuple, and one outcome per member. receipt={receipt!r}"
    )


@pytest.mark.negative_at
def test_unapproved_named_declarer_is_refused_before_historical_register_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CONTRACT_SHAPE: bounded-change."""
    # covers: R18
    repo = tmp_path / "legacy-repo"
    members = _init_declared_aggregate(repo, include_suite_declaration=False)
    source = _historical_declaration_file(
        repo,
        declaration_id="HAD-unapproved-named-declarer",
        target_commit=_git_output(repo, "rev-parse", "HEAD"),
        members=members,
        declarer="Mallory Unapproved",
    )
    # ADR-001 item 2: a WELL-FORMED authority file that grants someone else
    # ("Maria Santos") but never "Mallory Unapproved" -- the file must exist
    # so the refusal reason is the roster-membership token
    # `unauthorized-declarer`, never the absent-ledger token
    # `migration-authority-unavailable` a missing file would produce instead.
    _seed_governed_migration_authority(repo, "Maria Santos")
    store = repo / ".nwave" / "historical-prefactoring-aggregates.jsonl"
    before_store = store.read_bytes() if store.exists() else None
    before_ledger = _ledger_records(repo)

    monkeypatch.setattr(
        verify_slice_commit,
        "des_spawn",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("pytest must not run while declarer authority is refused")
        ),
    )
    exit_code, receipt = _register_historical_declaration(repo, source)

    assert (
        exit_code != 0
        and receipt.get("event") == "HistoricalAggregateDeclarationRefused"
        and receipt.get("reason") == "unauthorized-declarer"
        and receipt.get("error")
        and receipt.get("how")
        and (store.read_bytes() if store.exists() else None) == before_store
        and _ledger_records(repo) == before_ledger
    ), (
        "WHAT: an unapproved but named declarer registered historical evidence; WHY: a non-empty "
        "name alone is not accountable authority; HOW: verify the declarer against governed authority "
        f"before writing the declaration store. receipt={receipt!r}"
    )


@pytest.mark.negative_at
def test_historical_declaration_without_governed_authority_file_is_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CONTRACT_SHAPE: bounded-change.

    ADR-001 item 3: the fail-closed-on-absence property scenario 2 (a
    well-formed file that merely omits the declarer) does not exercise --
    NO `.nwave/governed-migration-authority.jsonl` file at all must refuse
    with the distinct token `migration-authority-unavailable`, never silently
    proceed and never collapse onto `unauthorized-declarer` (an operator
    seeing that token for a MISSING ledger would misdiagnose "add my name"
    when the real defect is "the ledger itself does not exist").
    """
    # covers: R18
    repo = tmp_path / "legacy-repo"
    members = _init_declared_aggregate(repo, include_suite_declaration=False)
    source = _historical_declaration_file(
        repo,
        declaration_id="HAD-no-authority-file",
        target_commit=_git_output(repo, "rev-parse", "HEAD"),
        members=members,
    )
    authority_path = repo / ".nwave" / "governed-migration-authority.jsonl"
    assert not authority_path.exists(), (
        "WHAT: the fixture itself seeded an authority file; WHY: this scenario proves the "
        "absent-ledger refusal, which requires genuine absence; HOW: do not call "
        f"_seed_governed_migration_authority for this test. authority_path={authority_path}"
    )
    store = repo / ".nwave" / "historical-prefactoring-aggregates.jsonl"
    before_store = store.read_bytes() if store.exists() else None
    before_ledger = _ledger_records(repo)

    monkeypatch.setattr(
        verify_slice_commit,
        "des_spawn",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError(
                "pytest must not run while the governed authority ledger is absent"
            )
        ),
    )
    exit_code, receipt = _register_historical_declaration(repo, source)

    assert (
        exit_code != 0
        and receipt.get("event") == "HistoricalAggregateDeclarationRefused"
        and receipt.get("reason") == "migration-authority-unavailable"
        and receipt.get("error")
        and receipt.get("how")
        and (store.read_bytes() if store.exists() else None) == before_store
        and _ledger_records(repo) == before_ledger
    ), (
        "WHAT: an absent governed-authority ledger registered historical evidence or was "
        "misdiagnosed as an unauthorized declarer; WHY: a missing/corrupt authority record is a "
        "distinct governance defect from a name simply not being listed; HOW: refuse with the "
        f"dedicated migration-authority-unavailable token before any write. receipt={receipt!r}"
    )


@pytest.mark.negative_at
def test_multiple_historical_declarations_require_an_explicit_identity_before_sealing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CONTRACT_SHAPE: bounded-change."""
    # covers: R19
    repo = tmp_path / "legacy-repo"
    members = _init_declared_aggregate(repo, include_suite_declaration=False)
    target_commit = _git_output(repo, "rev-parse", "HEAD")
    first = _historical_declaration_file(
        repo,
        declaration_id="HAD-explicit-selection-001",
        target_commit=target_commit,
        members=members,
    )
    second = _historical_declaration_file(
        repo,
        declaration_id="HAD-explicit-selection-002",
        target_commit=target_commit,
        members=members[:2],
    )
    second_payload = json.loads(second.read_text(encoding="utf-8"))
    second_payload["intent"] = "carpaccio gate evidence review"
    second.write_text(json.dumps(second_payload), encoding="utf-8")
    _seed_governed_migration_authority(repo, "Maria Santos")
    _register_historical_declaration(repo, first)
    _register_historical_declaration(repo, second)
    before_ledger = _ledger_records(repo)

    monkeypatch.setattr(
        verify_slice_commit,
        "des_spawn",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("pytest must not run before historical identity selection")
        ),
    )
    exit_code, receipt = _verify_public(
        _aggregate_argv(repo, members, commit_sha=target_commit)
    )

    assert (
        exit_code != 0
        and receipt.get("event") == "PrefactoringAggregateSelectionRefused"
        and receipt.get("reason") == "historical-declaration-id-required"
        and "HAD-explicit-selection-001" in json.dumps(receipt)
        and "HAD-explicit-selection-002" in json.dumps(receipt)
        and receipt.get("how")
        and _ledger_records(repo) == before_ledger
    ), (
        "WHAT: a seal chose one of several historical declarations by default; WHY: distinct "
        "governed identities cannot be silently substituted; HOW: name every available identity and "
        f"require --historical-declaration-id before execution. receipt={receipt!r}"
    )


def test_historical_aggregate_seal_persists_its_authority_and_member_outcomes_in_ledger(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change."""
    # covers: R21
    repo = tmp_path / "legacy-repo"
    members = _init_declared_aggregate(repo, include_suite_declaration=False)
    target_commit = _git_output(repo, "rev-parse", "HEAD")
    source = _historical_declaration_file(
        repo,
        declaration_id="HAD-durable-seal-witness-001",
        target_commit=target_commit,
        members=members,
    )
    _seed_governed_migration_authority(repo, "Maria Santos")
    _register_historical_declaration(repo, source)

    exit_code, _receipt = _verify_public(
        [
            *_aggregate_argv(repo, members, commit_sha=target_commit),
            "--historical-declaration-id",
            "HAD-durable-seal-witness-001",
        ]
    )
    record = _verified_ledger_record(repo)
    member_outcomes = record.get("member_outcomes", [])

    assert (
        exit_code == 0
        and record.get("historical_declaration_id") == "HAD-durable-seal-witness-001"
        and record.get("commit_sha") == target_commit
        and tuple(record.get("regression_test_files_executed", ())) == members
        and {
            outcome.get("path")
            for outcome in member_outcomes
            if isinstance(outcome, dict)
        }
        == set(members)
        and all(
            outcome.get("outcome") == "passed"
            for outcome in member_outcomes
            if isinstance(outcome, dict)
        )
    ), (
        "WHAT: the durable slice-commit ledger lacks a historical declaration or member outcomes; "
        "WHY: stdout cannot be used to reconstruct a sealed historical proof; HOW: append the "
        f"declaration id and one outcome for every member with the seal. record={record!r}"
    )


@pytest.mark.negative_at
def test_trailer_authority_stays_with_its_commit_while_unrelated_history_remains_selectable(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation."""
    # covers: R17
    # covers: R19
    repo = tmp_path / "repo"
    members = _init_declared_aggregate(repo)
    trailer_commit = _git_output(repo, "rev-parse", "HEAD")
    (repo / "README.md").write_text("legacy parity context\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(
        repo,
        "commit",
        "-q",
        "-m",
        "refactor: retain legacy context\n\nSlice-Id: slice-01",
    )
    legacy_commit = _git_output(repo, "rev-parse", "HEAD")
    unrelated_source = _historical_declaration_file(
        repo,
        declaration_id="HAD-unrelated-legacy-001",
        target_commit=legacy_commit,
        members=members,
    )
    _seed_governed_migration_authority(repo, "Maria Santos")
    _register_historical_declaration(repo, unrelated_source)
    store = repo / ".nwave" / "historical-prefactoring-aggregates.jsonl"
    before_store = store.read_bytes()
    conflicting_source = _historical_declaration_file(
        repo,
        declaration_id="HAD-cannot-replace-trailer-001",
        target_commit=trailer_commit,
        members=members[:2],
    )

    refused_code, refused = _register_historical_declaration(repo, conflicting_source)
    discovery_code, discovery = _discover_prefactoring_aggregate(repo)
    candidates = discovery.get("candidates", [])

    assert (
        refused_code != 0
        and refused.get("event") == "HistoricalAggregateDeclarationRefused"
        and refused.get("reason") == "commit-trailer-authoritative"
        and refused.get("how")
        and store.read_bytes() == before_store
        and discovery_code == 0
        and any(
            candidate.get("commit_sha") == trailer_commit
            and candidate.get("provenance") == "commit-trailer"
            for candidate in candidates
            if isinstance(candidate, dict)
        )
        and any(
            candidate.get("commit_sha") == legacy_commit
            and candidate.get("declaration_id") == "HAD-unrelated-legacy-001"
            and candidate.get("provenance") == "governed-historical-declaration"
            for candidate in candidates
            if isinstance(candidate, dict)
        )
    ), (
        "WHAT: a historical record displaced trailer authority or made unrelated history unavailable; "
        "WHY: each target commit retains its own evidence authority; HOW: refuse historical registration "
        f"for trailer-declared commits while listing independent governed history. refused={refused!r} "
        f"discovery={discovery!r}"
    )


@pytest.mark.negative_at
def test_missing_required_provenance_refusal_names_the_absent_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTRACT_SHAPE: bounded-change.

    Vera's charter FAIL, defect 1: the refusal for a declaration missing
    ``intent`` and ``declared_at`` never says WHICH field is absent, so the
    maintainer must guess among the four required fields.
    """
    # covers: R18
    repo = tmp_path / "legacy-repo"
    members = _init_declared_aggregate(repo, include_suite_declaration=False)
    target_commit = _git_output(repo, "rev-parse", "HEAD")
    _seed_governed_migration_authority(repo, "Maria Santos")
    full = _historical_declaration_file(
        repo,
        declaration_id="HAD-missing-fields-001",
        target_commit=target_commit,
        members=members,
    )
    payload = json.loads(full.read_text(encoding="utf-8"))
    del payload["intent"]
    del payload["declared_at"]
    incomplete = repo / "migration-input" / "HAD-missing-fields-001-partial.json"
    incomplete.write_text(json.dumps(payload), encoding="utf-8")

    def pytest_must_not_run(*_args: object, **_kwargs: object) -> object:
        raise AssertionError(
            "WHAT: pytest ran while required provenance was absent; WHY: an incomplete "
            "declaration must never reach execution; HOW: refuse it first."
        )

    monkeypatch.setattr(verify_slice_commit, "des_spawn", pytest_must_not_run)
    exit_code, receipt = _register_historical_declaration(repo, incomplete)

    receipt_text = json.dumps(receipt)
    assert (
        exit_code != 0
        and receipt.get("event") == "HistoricalAggregateDeclarationRefused"
        and receipt.get("reason") == "missing-required-provenance"
        and "intent" in receipt_text
        and "declared_at" in receipt_text
    ), (
        "WHAT: the refusal for a declaration missing intent and declared_at never named which "
        "field(s) were absent; WHY: a maintainer supplying a partial declaration cannot tell which "
        "of the required fields to add without guessing; HOW: name every absent required field in "
        f"the refusal payload. receipt={receipt!r}"
    )


_HISTORICAL_DECLARATION_REQUIRED_FIELD_PHRASES: dict[str, tuple[str, ...]] = {
    "declaration_id": ("declaration id", "declaration_id"),
    "target_commit": ("target commit", "target_commit"),
    "intent": ("intent",),
    "declared_at": ("time", "declared at", "declared_at", "timestamp"),
    "source_evidence": ("source evidence", "source_evidence"),
    "completeness_attestation": (
        "completeness attestation",
        "completeness_attestation",
    ),
}


@pytest.mark.negative_at
def test_missing_required_provenance_how_names_every_field_registration_actually_requires(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTRACT_SHAPE: bounded-change.

    Vera's charter FAIL, defect 2 (the more serious one -- it actively
    misleads): the ``missing-required-provenance`` refusal's ``how`` text
    reads "supply declaration id, target commit, intent, declarer, time, and
    completeness attestation" but omits ``source_evidence``, which
    ``_register_historical_declaration`` requires separately. A maintainer
    who follows that ``how`` text exactly is refused a second time.

    This test derives the TRUE required-field set by PROBING production
    behaviour rather than hardcoding it: starting from one fully valid
    declaration, each candidate field is independently removed and
    registration re-run. A field counts as "actually required" only when its
    removal alone produces a refusal in the missing-field family
    (``missing-required-provenance``, ``source-evidence-required``,
    ``completeness-attestation-required``). Every field proven required this
    way must then be nameable in the ``missing-required-provenance`` how
    text -- so the assertion tracks the real requirement set and cannot rot
    the way the hand-written how string did.
    """
    # covers: R18
    repo = tmp_path / "legacy-repo"
    members = _init_declared_aggregate(repo, include_suite_declaration=False)
    target_commit = _git_output(repo, "rev-parse", "HEAD")
    _seed_governed_migration_authority(repo, "Maria Santos")
    full = _historical_declaration_file(
        repo,
        declaration_id="HAD-probe-full-001",
        target_commit=target_commit,
        members=members,
    )
    full_payload = json.loads(full.read_text(encoding="utf-8"))

    def pytest_must_not_run(*_args: object, **_kwargs: object) -> object:
        raise AssertionError(
            "WHAT: pytest ran while probing required provenance fields; WHY: every probe "
            "declaration is deliberately incomplete; HOW: refuse each before execution."
        )

    monkeypatch.setattr(verify_slice_commit, "des_spawn", pytest_must_not_run)

    required_family = {
        "missing-required-provenance",
        "source-evidence-required",
        "completeness-attestation-required",
    }
    probed_required_fields: list[str] = []
    how_text = ""
    for field in _HISTORICAL_DECLARATION_REQUIRED_FIELD_PHRASES:
        probe_payload = dict(full_payload)
        del probe_payload[field]
        probe_path = repo / "migration-input" / f"HAD-probe-missing-{field}.json"
        probe_path.write_text(json.dumps(probe_payload), encoding="utf-8")
        exit_code, receipt = _register_historical_declaration(repo, probe_path)
        reason = receipt.get("reason")
        if exit_code != 0 and reason in required_family:
            probed_required_fields.append(field)
            if reason == "missing-required-provenance":
                how_text = str(receipt.get("how") or how_text)

    assert probed_required_fields and how_text, (
        "sanity: probing must independently prove at least one field required and capture the "
        f"missing-required-provenance how text before the real assertion runs. "
        f"probed={probed_required_fields!r} how={how_text!r}"
    )

    how_lower = how_text.lower()
    unnamed_fields = [
        field
        for field in probed_required_fields
        if not any(
            phrase in how_lower
            for phrase in _HISTORICAL_DECLARATION_REQUIRED_FIELD_PHRASES[field]
        )
    ]
    assert not unnamed_fields, (
        "WHAT: the missing-required-provenance how text omits field(s) that registration "
        f"independently proved required by probing: {unnamed_fields!r}; WHY: a maintainer who "
        "supplies EXACTLY what how lists is refused a second time for a field how never named -- "
        "the exact defect Vera's charter FAIL surfaced (source_evidence proven required but absent "
        "from how); HOW: enumerate the complete required set in the how text. "
        f"how={how_text!r} probed_required_fields={probed_required_fields!r}"
    )


_SOURCE_EVIDENCE_SHAPE_HINT_PHRASES: tuple[str, ...] = ("list", "array")


def _mechanically_shaped_source_evidence(how_text: str, base_reference: str) -> object:
    """Construct the next ``source_evidence`` candidate from ONLY the shape
    signal a maintainer could read in the refusal's own ``how`` text.

    This deliberately encodes no hardcoded knowledge that production requires
    a list -- it recognizes generic collection-shape signal words. Absent
    such a signal, the literal, most natural reading of "record the evidence
    references examined by the declarer" is a single reference string.
    """
    if any(hint in how_text.lower() for hint in _SOURCE_EVIDENCE_SHAPE_HINT_PHRASES):
        return [base_reference]
    return base_reference


def test_source_evidence_refusal_guides_a_mechanically_compliant_maintainer_to_acceptance(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change.

    Vera's charter FAIL, round 2, blocker A: the ``source-evidence-required``
    refusal names WHICH field is missing ("declaration has no source
    evidence") but never its required SHAPE (a non-empty list of strings).
    Its ``how`` text -- "record the evidence references examined by the
    declarer" -- is satisfied literally by a single string reference, which
    production then refuses with the IDENTICAL message, teaching the
    maintainer nothing new. This test plays that maintainer mechanically: it
    supplies only what each refusal's own ``how`` text tells it, and asserts
    the loop reaches acceptance within a bounded number of attempts -- never
    consulting source code, tests, or docs.
    """
    # covers: R18
    repo = tmp_path / "legacy-repo"
    members = _init_declared_aggregate(repo, include_suite_declaration=False)
    target_commit = _git_output(repo, "rev-parse", "HEAD")
    _seed_governed_migration_authority(repo, "Maria Santos")
    full = _historical_declaration_file(
        repo,
        declaration_id="HAD-mechanical-shape-001",
        target_commit=target_commit,
        members=members,
    )
    payload = json.loads(full.read_text(encoding="utf-8"))
    base_reference = payload["source_evidence"][0]
    del payload["source_evidence"]
    probe_path = repo / "migration-input" / "HAD-mechanical-shape-001-probe.json"

    candidate: object = None
    attempt_log: list[dict[str, object]] = []
    accepted = False
    for _attempt in range(5):
        if candidate is None:
            payload.pop("source_evidence", None)
        else:
            payload["source_evidence"] = candidate
        probe_path.write_text(json.dumps(payload), encoding="utf-8")
        exit_code, receipt = _register_historical_declaration(repo, probe_path)
        attempt_log.append({"candidate": candidate, "receipt": receipt})
        if (
            exit_code == 0
            and receipt.get("event") == "HistoricalAggregateDeclarationRegistered"
        ):
            accepted = True
            break
        assert (
            receipt.get("event") == "HistoricalAggregateDeclarationRefused"
            and receipt.get("reason") == "source-evidence-required"
        ), (
            "sanity: the mechanical loop must exercise only the source-evidence "
            f"blocker, never an unrelated refusal. receipt={receipt!r}"
        )
        next_candidate = _mechanically_shaped_source_evidence(
            str(receipt.get("how") or ""), base_reference
        )
        if next_candidate == candidate:
            break
        candidate = next_candidate

    assert accepted, (
        "WHAT: a maintainer who mechanically supplies exactly what each "
        "source-evidence-required refusal's own how text says never reaches "
        "acceptance; WHY: the how text names the missing field but never its "
        "required shape (a non-empty list of strings), so literal compliance "
        "repeats the identical refusal forever; HOW: name the required shape "
        f"in the how text so a compliant maintainer converges. attempts={attempt_log!r}"
    )


def _mechanically_shaped_scalar_or_list(how_text: str, literal_value: object) -> object:
    """Generalize ``_mechanically_shaped_source_evidence``'s text-only shape
    recognition to ANY field: return ``literal_value`` wrapped in a list iff
    the refusal's own ``how`` text carries a collection-shape signal word
    (``list``/``array``); otherwise the single most literal reading of a
    refusal that names a field but never states its shape. Encodes no
    hardcoded per-field knowledge -- the same recognizer must apply whether
    the field turns out to be ``source_evidence`` (whose ``how`` text was
    fixed to carry the signal) or ``suite_paths`` (whose ``how`` text, as of
    this run, still does not).
    """
    if any(hint in how_text.lower() for hint in _SOURCE_EVIDENCE_SHAPE_HINT_PHRASES):
        return [literal_value]
    return literal_value


@dataclass(frozen=True)
class _FieldResolver:
    """One entry in the small SEED table mapping 'a field the CLI can ask
    for' to 'how to recognize the refusal names it, and how to synthesise a
    plausible value purely from what that refusal's own text says' (never
    from source, tests, or docs). ``phrases`` drives RECOGNITION only -- the
    loop scans every refusal's combined error+how text for these substrings
    and applies whichever fields match, learning what to fill and in what
    order strictly from what production actually demands each attempt, never
    from a fixed reason-to-field map declared up front. ``synthesize``
    returns ``None`` when the matched text carries no extractable shape/value
    signal beyond the field's bare name -- the loop reads that as "this field
    cannot be satisfied mechanically from its own refusal text alone".
    """

    phrases: tuple[str, ...]
    synthesize: Callable[[str, str], object]


def test_registration_refusal_chain_mechanically_guides_a_maintainer_to_acceptance_or_names_the_unteachable_field(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change.

    Supersedes-in-spirit ``test_source_evidence_refusal_guides_a_mechanically_
    compliant_maintainer_to_acceptance`` (kept above as a standing regression
    guard for its own field): that test builds a COMPLETE valid declaration,
    deletes exactly ONE key, and asserts the loop encounters only the
    ``source-evidence-required`` refusal -- by construction it can never meet,
    and therefore never guard, any OTHER under-explained field. Vera's charter
    has now returned FAIL three times, each time on a DIFFERENT
    under-explained field the narrow probe could not see: first an unnamed
    missing field, then ``source_evidence``'s missing shape, now
    ``unsafe-suite-path``.

    This test plays the same mechanically-compliant maintainer end to end:
    starting from the LEAST the CLI will accept (an empty declaration
    object), it repeatedly registers, reads whichever refusal production
    actually returns, and applies ONLY what that refusal's own text states --
    via a small field-recognition table keyed by literal phrases found in the
    refusal text, never by a pre-declared reason-to-field map -- until either
    registration succeeds or the identical refusal repeats with no new
    information to act on. Every refusal the loop meets is in scope; none is
    excluded by construction. When a field cannot be resolved this way, the
    failure names that field and quotes the unhelpful refusal text verbatim,
    so the crafter knows precisely what to improve without a fourth Vera
    round.
    """
    # covers: R18
    repo = tmp_path / "legacy-repo"
    _init_declared_aggregate(repo, include_suite_declaration=False)
    target_commit = _git_output(repo, "rev-parse", "HEAD")
    declarer = "Maria Santos"
    _seed_governed_migration_authority(repo, declarer)

    declaration_id_attempts = itertools.count(1)

    def _synthesize_declaration_id(_how: str, _error: str) -> object:
        return f"HAD-journey-{next(declaration_id_attempts):04d}"

    def _synthesize_target_commit(_how: str, _error: str) -> object:
        # A maintainer always knows their OWN target commit -- no refusal
        # text could ever teach a maintainer their own commit sha.
        return target_commit

    def _synthesize_intent(_how: str, _error: str) -> object:
        return "carpaccio gate parity"

    def _synthesize_declared_at(_how: str, _error: str) -> object:
        return "2026-07-30T09:15:00Z"

    def _synthesize_source_evidence(how_text: str, _error: str) -> object:
        return _mechanically_shaped_scalar_or_list(
            how_text, "release-notes/2026-06-14-carpaccio-parity.md"
        )

    def _synthesize_completeness_attestation(_how: str, _error: str) -> object:
        return "I examined the named parity evidence and attest this tuple is complete."

    def _synthesize_declarer(_how: str, _error: str) -> object:
        # A maintainer always knows who THEY are -- no refusal text could
        # ever teach a maintainer their own governed identity.
        return declarer

    def _synthesize_suite_paths(how_text: str, _error: str) -> object:
        return _mechanically_shaped_scalar_or_list(
            how_text, "tests/parity/test_suite.py"
        )

    resolvers: dict[str, _FieldResolver] = {
        "declaration_id": _FieldResolver(
            ("declaration id", "declaration_id"), _synthesize_declaration_id
        ),
        "target_commit": _FieldResolver(
            ("target commit", "target_commit"), _synthesize_target_commit
        ),
        "intent": _FieldResolver(("intent",), _synthesize_intent),
        "declared_at": _FieldResolver(
            ("declared at", "declared_at", "timestamp"), _synthesize_declared_at
        ),
        "source_evidence": _FieldResolver(
            ("source evidence", "source_evidence"), _synthesize_source_evidence
        ),
        "completeness_attestation": _FieldResolver(
            ("completeness attestation", "completeness_attestation"),
            _synthesize_completeness_attestation,
        ),
        "declarer": _FieldResolver(("declarer",), _synthesize_declarer),
        "suite_paths": _FieldResolver(
            ("suite paths", "suite_paths"), _synthesize_suite_paths
        ),
    }

    payload: dict[str, object] = {}
    probe_path = repo / "migration-input" / "HAD-journey-probe.json"
    probe_path.parent.mkdir(parents=True, exist_ok=True)
    attempt_log: list[dict[str, object]] = []
    accepted = False
    unresolved: dict[str, object] | None = None
    max_attempts = 30
    for _attempt in range(max_attempts):
        probe_path.write_text(json.dumps(payload), encoding="utf-8")
        exit_code, receipt = _register_historical_declaration(repo, probe_path)
        attempt_log.append({"payload": dict(payload), "receipt": receipt})
        if (
            exit_code == 0
            and receipt.get("event") == "HistoricalAggregateDeclarationRegistered"
        ):
            accepted = True
            break
        assert receipt.get("event") == "HistoricalAggregateDeclarationRefused", (
            "sanity: every non-accepting attempt must be a typed refusal, never a "
            f"crash or an unrelated event. receipt={receipt!r}"
        )
        reason = str(receipt.get("reason") or "")
        error_text = str(receipt.get("error") or "")
        how_text = str(receipt.get("how") or "")
        combined = f"{error_text} {how_text}".lower()

        matched_fields = [
            field
            for field, resolver in resolvers.items()
            if any(phrase in combined for phrase in resolver.phrases)
        ]
        progressed = False
        stuck_fields: list[str] = []
        for field in matched_fields:
            candidate = resolvers[field].synthesize(how_text, error_text)
            if candidate is None or payload.get(field) == candidate:
                stuck_fields.append(field)
                continue
            payload[field] = candidate
            progressed = True

        if not progressed:
            unresolved = {
                "reason": reason,
                "error": error_text,
                "how": how_text,
                "matched_fields": matched_fields
                or ["<none recognized by the resolver table>"],
                "stuck_fields": stuck_fields,
            }
            break

    assert accepted, (
        "WHAT: the mechanical registration journey never reached "
        f"HistoricalAggregateDeclarationRegistered within {max_attempts} attempts, "
        "following ONLY what each refusal's own error/how text stated; WHY: a "
        "maintainer who reads every refusal literally and supplies exactly the "
        "shape it names must converge -- if it never converges, the refusal text "
        "for the field(s) below is under-specified; HOW: for each field listed, "
        "state its JSON key explicitly, its required shape (scalar vs "
        "list/array), whether it must reference an artifact already present at "
        "the target commit, and how many are required, so a mechanically "
        f"compliant maintainer converges. unresolved={unresolved!r} "
        f"attempts={attempt_log!r}"
    )


@pytest.mark.negative_at
def test_discovery_unavailable_refusal_directs_to_governed_history_without_dumping_every_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation.

    Vera's charter FAIL, round 2, blocker B: feature-delta.md line 119's own
    outcome-5 oracle requires the CLI to list a bounded candidate OR clearly
    say that none is available AND HOW TO CORRECT IT. When many reachable
    commits carry only ``Slice-Id`` (no ``Regression-Suite`` trailer, no
    historical declaration), ``PrefactoringAggregateDiscoveryUnavailable``
    today emits ``how="repair the unavailable evidence, then re-run
    discovery"`` -- no route to the governed historical-declaration path this
    feature's own Slice Plan value statement (feature-delta.md line 106)
    promises for exactly this case -- and its ``error`` grows one bare commit
    SHA per undeclared commit instead of staying bounded.
    """
    # covers: R17
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "aggregate@example.test")
    _git(repo, "config", "user.name", "Aggregate Maintainer")
    delta = repo / "docs" / "feature" / _FEATURE_ID / "feature-delta.md"
    delta.parent.mkdir(parents=True)
    delta.write_text(
        "# Feature Delta\n\n## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
        "| slice-01 | a maintainer inspects declared prefactoring evidence | pending | "
        "@prefactoring | existing evidence only |\n",
        encoding="utf-8",
    )
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "chore: seed docs\n\nSlice-Id: slice-01")
    undeclared_commit_count = 25
    for index in range(undeclared_commit_count):
        (repo / f"note-{index}.txt").write_text(f"note {index}\n", encoding="utf-8")
        _git(repo, "add", f"note-{index}.txt")
        _git(
            repo,
            "commit",
            "-q",
            "-m",
            f"refactor: retain note {index}\n\nSlice-Id: slice-01",
        )

    def runner_must_not_run(*_args: object, **_kwargs: object) -> object:
        raise AssertionError(
            "WHAT: discovery invoked pytest; WHY: an unavailable candidate "
            "population is read-only; HOW: return the typed outcome without "
            "executing evidence."
        )

    monkeypatch.setattr(verify_slice_commit, "des_spawn", runner_must_not_run)
    exit_code, receipt = _discover_prefactoring_aggregate(repo)

    assert (
        exit_code != 0
        and receipt.get("event") == "PrefactoringAggregateDiscoveryUnavailable"
        and receipt.get("reason") == "legacy-or-missing-declaration"
        and receipt.get("error")
        and receipt.get("how")
    ), (
        "sanity: this scenario must exercise the legacy-or-missing-declaration "
        f"outcome, not a different refusal. receipt={receipt!r}"
    )

    error_text = str(receipt.get("error") or "")
    how_text = str(receipt.get("how") or "").lower()
    dumped_shas = re.findall(r"\b[0-9a-f]{40}\b", error_text)

    assert len(dumped_shas) < undeclared_commit_count, (
        "WHAT: the refusal's error payload names one bare commit SHA per "
        f"undeclared commit ({len(dumped_shas)} of {undeclared_commit_count} "
        "reachable commits dumped verbatim); WHY: an unbounded per-commit SHA "
        "dump is operator-hostile, not a diagnosis; HOW: report the undeclared "
        "population as a bounded summary, not an enumerated dump. "
        f"error={error_text!r}"
    )
    assert (
        "historical" in how_text
        and "register-historical-prefactoring-aggregate" in how_text
    ), (
        "WHAT: the how text gives no route to the governed historical-declaration "
        "path this feature's own Slice Plan value statement promises for exactly "
        "this case (historic Git lacking the original declaration); WHY: "
        "'repair the unavailable evidence, then re-run discovery' names no "
        "correcting action; HOW: direct the maintainer to register a governed "
        "historical declaration via --register-historical-prefactoring-aggregate. "
        f"how={how_text!r}"
    )


@pytest.mark.negative_at
def test_discovery_never_lists_a_missing_suite_declaration_as_a_plain_selectable_candidate(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change.

    Vera's fourth examine, independently-judged defect: a governed historical
    declaration whose declared suite does NOT exist in its target commit is
    still returned by ``--discover-prefactoring-aggregate`` as a plain,
    selection-ready candidate carrying canonical ``governed-historical-
    declaration`` provenance, with no signal that the suite is missing --
    only the SEAL later refuses it with ``AggregateMemberMissing``. This
    violates both the positive oracle (every displayed candidate must carry
    a complete, EXISTING suite tuple) and the negative oracle (incapacity to
    obtain evidence must be declared, never presented as clean/complete).

    Registration itself must stay permissive (a declaration can be recorded
    before its suite exists -- that existence check was deliberately removed
    FROM REGISTRATION so the maintainer journey stays possible). The check
    belongs at DISCOVERY, the moment candidates are offered for selection.
    """
    # covers: R14
    missing_suite = "tests/parity/test_GHOST.py"

    ghost_repo = tmp_path / "ghost-repo"
    _init_declared_aggregate(ghost_repo, include_suite_declaration=False)
    ghost_target_commit = _git_output(ghost_repo, "rev-parse", "HEAD")
    ghost_declaration_id = "HAD-ghost-suite-001"
    ghost_source = _historical_declaration_file(
        ghost_repo,
        declaration_id=ghost_declaration_id,
        target_commit=ghost_target_commit,
        members=(missing_suite,),
    )
    _seed_governed_migration_authority(ghost_repo, "Maria Santos")

    ghost_registered_code, ghost_registered = _register_historical_declaration(
        ghost_repo, ghost_source
    )
    assert (
        ghost_registered_code == 0
        and ghost_registered.get("event") == "HistoricalAggregateDeclarationRegistered"
    ), (
        "WHAT: a declaration naming a not-yet-existing suite was refused at "
        "registration; WHY: registration must stay permissive -- the existence "
        "check was deliberately moved OFF registration so a declaration can be "
        "recorded before its suite exists; HOW: keep registration accepting "
        f"any well-formed declaration. registered={ghost_registered!r}"
    )

    ghost_exit_code, ghost_discovered = _discover_prefactoring_aggregate(ghost_repo)
    ghost_candidates = [
        candidate
        for candidate in ghost_discovered.get("candidates", []) or []
        if isinstance(candidate, dict)
        and candidate.get("declaration_id") == ghost_declaration_id
    ]
    ghost_serialized = json.dumps(ghost_discovered)

    if ghost_candidates:
        # Surfaced-explicitly-unavailable branch: the candidate may appear,
        # but it must carry an honest signal beyond the bare declared tuple
        # -- an unchanged plain-candidate shape with unchanged provenance
        # IS the current defect, not an honest fix.
        candidate = ghost_candidates[0]
        plain_shape_keys = {
            "commit_sha",
            "declared_suite_paths",
            "declaration_digest",
            "provenance",
            "declaration_id",
            "supersedes",
        }
        extra_keys = set(candidate) - plain_shape_keys
        assert (
            extra_keys
            or candidate.get("provenance") != "governed-historical-declaration"
        ) and missing_suite in json.dumps(candidate), (
            "WHAT: a declaration whose suite is absent from its target commit "
            "was surfaced as an ordinary, unmarked selection-ready candidate; "
            "WHY: nothing distinguishes it from a candidate whose full suite "
            "actually exists, so a maintainer selects it believing it is "
            "complete and only the seal later refuses it; HOW: mark the "
            "candidate as explicitly unavailable (a new field, a distinct "
            f"provenance, etc.) and name the missing suite. candidate={candidate!r}"
        )
    else:
        # Withheld branch: the candidate must never appear as selection-ready,
        # but its absence must be explained -- the missing suite must be
        # named SOMEWHERE in the discovery response, not silently dropped.
        assert missing_suite in ghost_serialized, (
            "WHAT: a declaration whose suite is absent from its target commit "
            "was silently dropped from discovery with no explanation anywhere "
            "in the response; WHY: silent omission is indistinguishable from a "
            "maintainer who simply never declared anything; HOW: withhold the "
            "candidate WITH a self-explaining reason naming the missing suite. "
            f"discovered={ghost_discovered!r} exit_code={ghost_exit_code!r}"
        )

    # Complement: a sibling declaration whose suite DOES exist must still be
    # listed as a normal, unmarked selectable candidate -- a blanket "hide
    # every historical candidate" patch must not pass this test.
    real_repo = tmp_path / "real-repo"
    real_members = _init_declared_aggregate(real_repo, include_suite_declaration=False)
    real_target_commit = _git_output(real_repo, "rev-parse", "HEAD")
    real_declaration_id = "HAD-existing-suite-001"
    real_source = _historical_declaration_file(
        real_repo,
        declaration_id=real_declaration_id,
        target_commit=real_target_commit,
        members=real_members,
    )
    _seed_governed_migration_authority(real_repo, "Maria Santos")
    real_registered_code, real_registered = _register_historical_declaration(
        real_repo, real_source
    )
    real_exit_code, real_discovered = _discover_prefactoring_aggregate(real_repo)
    real_candidates = real_discovered.get("candidates", []) or []

    assert (
        real_registered_code == 0
        and real_exit_code == 0
        and any(
            candidate.get("declaration_id") == real_declaration_id
            and candidate.get("commit_sha") == real_target_commit
            and tuple(candidate.get("declared_suite_paths", ())) == real_members
            and candidate.get("provenance") == "governed-historical-declaration"
            for candidate in real_candidates
            if isinstance(candidate, dict)
        )
    ), (
        "WHAT: a declaration whose suite genuinely exists was not listed as an "
        "ordinary selectable candidate; WHY: an existence check on missing "
        "suites must not blanket-suppress every historical candidate; HOW: "
        "verify each declared suite individually and keep existing candidates "
        f"unaffected. real_registered={real_registered!r} real_discovered={real_discovered!r}"
    )


# ---------------------------------------------------------------------------
# ADR-002: E1 completeness population for an explicit historical selection
# ---------------------------------------------------------------------------
#
# docs/feature/prefactoring-aggregate-regression-seal/design/adrs/
# adr-002-e1-completeness-population-for-explicit-historical-selection.md
#
# `missing_at_files` derives E1's expected-AT population by scanning TODAY's
# working tree (`feature_files_for_slice`), then checking each scan hit
# against the historical TARGET commit. A governed historical declaration
# names a target commit in the past by construction, so a `.feature`/AT file
# the scan finds in today's tree is systematically newer than that target --
# E1 refuses the genuinely historical case the governed-declaration mechanism
# exists to serve. These four ATs exercise the fix's four required
# behaviours (ADR-002 "What DISTILL/DELIVER must exercise").


def _write_uncommitted_slice_feature_file(
    repo: Path, *, relative_path: str | None = None
) -> str:
    """Author a `.feature` AT file for ``_SLICE_ID`` on disk WITHOUT
    committing it -- the "today's working tree" artifact ADR-002 describes:
    scan-discoverable (file-level ``@feature-{id}`` tag + per-scenario
    ``@slice-01`` tag, exactly the ``feature_files_for_slice`` taxonomy) yet
    absent from every commit, so it can never be tracked-before a historical
    target commit that predates its authorship.
    """
    path = repo / (
        relative_path
        or f"tests/bugs/{_FEATURE_ID}/acceptance/{_SLICE_ID.replace('-', '_')}.feature"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"@feature-{_FEATURE_ID}\n"
        "Feature: parity preserved\n\n"
        f"  @{_SLICE_ID}\n"
        "  Scenario: parity holds\n"
        "    Given committed parity evidence\n"
        "    Then parity holds\n",
        encoding="utf-8",
    )
    return str(path.relative_to(repo))


def test_historical_target_predating_todays_tree_clears_e1(tmp_path: Path) -> None:
    """CONTRACT_SHAPE: bounded-change.

    ADR-002 Decision + "What DISTILL/DELIVER must exercise" item 1: on an
    EXPLICIT historical selection, E1's expected-AT population comes SOLELY
    from the declaration's own canonical suite tuple -- never unioned with a
    today's-working-tree scan. The target commit here predates a `.feature`
    AT file the slice only authors AFTERWARDS (present on today's disk,
    absent from -- and not tracked-before -- the target commit's history):
    the working-tree scan would flag it missing relative to that older
    target, but every declared aggregate member IS tracked at the target
    commit itself. E1 must clear and control must reach E2, sealing cleanly.
    """
    # covers: R18
    repo = tmp_path / "repo"
    members = _init_declared_aggregate(repo, include_suite_declaration=False)
    target_commit = _git_output(repo, "rev-parse", "HEAD")
    stray = _write_uncommitted_slice_feature_file(repo)
    declaration_id = "HAD-predating-parity-001"
    source = _historical_declaration_file(
        repo,
        declaration_id=declaration_id,
        target_commit=target_commit,
        members=members,
    )
    _seed_governed_migration_authority(repo, "Maria Santos")
    _register_historical_declaration(repo, source)
    before = _ledger_records(repo)

    exit_code, receipt = _verify_public(
        [
            *_aggregate_argv(repo, members, commit_sha=target_commit),
            "--historical-declaration-id",
            declaration_id,
        ]
    )
    record = _verified_ledger_record(repo) if exit_code == 0 else {}

    assert (
        exit_code == 0
        and receipt.get("event") != "SliceCommitRefused"
        and record.get("event") == "SliceCommitVerified"
        and record.get("historical_declaration_id") == declaration_id
        and tuple(receipt.get("regression_test_files_executed", ())) == members
        and len(_ledger_records(repo)) == len(before) + 1
    ), (
        "WHAT: an explicit historical selection whose declared members are all "
        "tracked at the target commit was refused at E1 because today's "
        f"working tree also carries {stray!r}, a `.feature` AT file authored "
        "AFTER that commit; WHY: ADR-002 requires E1's population to come "
        "solely from the declaration on this path, never unioned with the "
        "stale scan; HOW: when --historical-declaration-id names an "
        "explicit selection, derive the E1 population from the declared "
        "suite tuple alone and let control reach E2. "
        f"stray={stray!r} exit_code={exit_code!r} receipt={receipt!r} record={record!r}"
    )


def test_declared_but_absent_historical_member_defers_to_e2(tmp_path: Path) -> None:
    """CONTRACT_SHAPE: bounded-change.

    ADR-002 Decision + "What DISTILL/DELIVER must exercise" item 2 + the
    Context's near-miss: today only ``aggregate_members[0]`` ever reaches
    the declared-but-absent carve-out that keeps a declared regression file
    out of E1's ``missing`` list -- "a multi-member aggregate's remaining
    members never reach E1 as evidence either way". Member index 1 (not 0)
    is declared here, deliberately made scan-discoverable via the
    pytest-regression path-naming convention AND genuinely absent from the
    target commit and its history: today the scan unconditionally unions it
    into E1's population and hard-flags it missing. After the fix it must be
    EXCLUDED from E1's population like any declared-but-absent member --
    never appearing in E1's ``missing`` list -- and the seal's outcome must
    come from E2's regression gate (``AggregateMemberMissing``), never a
    ``SliceCommitRefused``/E1 payload.
    """
    # covers: R18
    repo = tmp_path / "repo"
    members = _init_declared_aggregate(repo, include_suite_declaration=False)
    target_commit = _git_output(repo, "rev-parse", "HEAD")
    ghost_member = canonical_regression_test_path(
        _FEATURE_ID, _SLICE_ID, suffix="ghost"
    )
    ghost_path = repo / ghost_member
    ghost_path.parent.mkdir(parents=True, exist_ok=True)
    ghost_path.write_text("def test_ghost():\n    assert True\n", encoding="utf-8")
    declared_members = (members[0], ghost_member)
    declaration_id = "HAD-nonfirst-absent-001"
    source = _historical_declaration_file(
        repo,
        declaration_id=declaration_id,
        target_commit=target_commit,
        members=declared_members,
    )
    _seed_governed_migration_authority(repo, "Maria Santos")
    _register_historical_declaration(repo, source)
    before = _ledger_records(repo)

    exit_code, receipt = _verify_public(
        [
            *_aggregate_argv(repo, declared_members, commit_sha=target_commit),
            "--historical-declaration-id",
            declaration_id,
        ]
    )

    assert (
        exit_code != 0
        and receipt.get("event") != "SliceCommitRefused"
        and receipt.get("event") == "AggregateMemberMissing"
        and receipt.get("member") == ghost_member
        and _ledger_records(repo) == before
    ), (
        "WHAT: a declared-but-absent SECOND aggregate member -- scan-"
        "discoverable via the pytest-regression naming convention and "
        "genuinely absent from the target commit's history -- was hard-"
        "flagged missing by E1 (SliceCommitRefused) instead of being "
        "excluded and deferred to E2; WHY: ADR-002 requires the same "
        "declared-but-absent carve-out for EVERY declared member, not only "
        "index 0; HOW: derive E1's population solely from the declared "
        "tuple on this path and let a member that is neither present-in-"
        "commit nor tracked-before-commit be silently excluded, never a "
        f"hard miss. ghost_member={ghost_member!r} exit_code={exit_code!r} "
        f"receipt={receipt!r}"
    )


@pytest.mark.negative_at
def test_ordinary_non_historical_aggregate_seal_stays_refused_at_e1(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation.

    ADR-002 "What DISTILL/DELIVER must exercise" item 3 + the Decision's
    ``historical_selection=False`` branch ("every path unchanged today"):
    sibling-branch pin, paired with the two success tests above. No
    ``--historical-declaration-id`` is supplied here -- a crafter must not
    satisfy the historical-path fixes by making E1 defer to the declared
    population unconditionally; that is the "weaken E1 globally" alternative
    ADR-002 explicitly rejects. A stray `.feature` AT file authored (but
    never committed) for this slice must still hard-refuse E1 exactly as
    before this ADR, even though a declared, present, tracked aggregate
    member also exists. Must hold byte-identically both before and after
    the fix.
    """
    # covers: R18
    repo = tmp_path / "repo"
    members = _init_declared_aggregate(repo)
    commit = _git_output(repo, "rev-parse", "HEAD")
    stray = _write_uncommitted_slice_feature_file(repo)
    before = _ledger_records(repo)

    exit_code, receipt = _verify_aggregate(repo, members, commit_sha=commit)

    assert (
        exit_code != 0
        and receipt.get("event") == "SliceCommitRefused"
        and receipt.get("refused_half") == "E1"
        and stray
        in receipt.get("missing_feature_files_by_slice", {}).get(_SLICE_ID, [])
        and _ledger_records(repo) == before
    ), (
        "WHAT: an ordinary, non-historical aggregate seal stopped refusing "
        "E1 for a stray, never-committed `.feature` AT file once the "
        "historical-selection fix landed; WHY: ADR-002's fix is gated "
        "strictly behind an explicit --historical-declaration-id -- it must "
        "never weaken E1 for a seal that made no such selection; HOW: keep "
        "the working-tree scan unconditionally unioned into E1's population "
        f"when historical_selection is False. stray={stray!r} "
        f"exit_code={exit_code!r} receipt={receipt!r}"
    )


@pytest.mark.negative_at
def test_ordinary_single_file_pytest_regression_seal_stays_refused_at_e1(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation.

    Sibling-branch pin for the single-file (non-aggregate) ``pytest-
    regression`` path, mirroring the aggregate pin above -- ADR-002's
    "ordinary ... single-file paths are byte-identical to today" clause.
    ``missing_at_files``'s scan-union stays wired for every ordinary
    (non-historical) single-file seal too: a stray `.feature` AT file
    authored (but never committed) for this slice must still hard-refuse E1
    exactly as before this ADR, even though the seal also carries a
    declared, present, tracked ``--regression-test-file``.
    """
    # covers: R18
    repo = tmp_path / "repo"
    member = _init_declared_aggregate(repo, annotation="")[0]
    commit = _git_output(repo, "rev-parse", "HEAD")
    stray = _write_uncommitted_slice_feature_file(repo)
    before = _ledger_records(repo)

    exit_code, receipt = _verify_public(
        [
            "--repo",
            str(repo),
            "--commit",
            commit,
            "--feature-id",
            _FEATURE_ID,
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            member,
        ]
    )

    assert (
        exit_code != 0
        and receipt.get("event") == "SliceCommitRefused"
        and receipt.get("refused_half") == "E1"
        and stray
        in receipt.get("missing_feature_files_by_slice", {}).get(_SLICE_ID, [])
        and _ledger_records(repo) == before
    ), (
        "WHAT: an ordinary, non-historical single-file pytest-regression "
        "seal stopped refusing E1 for a stray, never-committed `.feature` "
        "AT file once the historical-selection fix landed; WHY: the fix "
        "must never weaken E1 for a seal that made no explicit historical "
        "selection, single-file or aggregate alike; HOW: keep the "
        "working-tree scan unconditionally unioned into E1's population "
        f"when historical_selection is False. stray={stray!r} "
        f"exit_code={exit_code!r} receipt={receipt!r}"
    )


def test_multi_member_historical_forwarding_treats_every_member_as_declared_evidence(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change.

    ADR-002 Context's near-miss + "What DISTILL/DELIVER must exercise" item
    4: today only ``aggregate_members[0]`` ever reaches
    ``missing_at_files`` -- "a multi-member aggregate's remaining members
    never reach E1 as evidence either way". This declares all THREE
    ``_init_declared_aggregate`` members (not one) for an explicit
    historical selection, with the SAME unrelated stray `.feature` AT-file
    interference as the single-member case above. E1 must clear using the
    FULL declared tuple as its population (not a single member), and the
    durable receipt must bind the historical declaration with every member
    named as executed evidence -- proving the fix forwards the complete
    tuple, not merely index 0.
    """
    # covers: R18
    repo = tmp_path / "repo"
    members = _init_declared_aggregate(repo, include_suite_declaration=False)
    assert len(members) >= 2, "fixture must declare a genuine multi-member aggregate"
    target_commit = _git_output(repo, "rev-parse", "HEAD")
    stray = _write_uncommitted_slice_feature_file(repo)
    declaration_id = "HAD-multi-member-forwarding-001"
    source = _historical_declaration_file(
        repo,
        declaration_id=declaration_id,
        target_commit=target_commit,
        members=members,
    )
    _seed_governed_migration_authority(repo, "Maria Santos")
    _register_historical_declaration(repo, source)

    exit_code, receipt = _verify_public(
        [
            *_aggregate_argv(repo, members, commit_sha=target_commit),
            "--historical-declaration-id",
            declaration_id,
        ]
    )
    record = _verified_ledger_record(repo) if exit_code == 0 else {}

    assert (
        exit_code == 0
        and record.get("event") == "SliceCommitVerified"
        and record.get("historical_declaration_id") == declaration_id
        and tuple(receipt.get("regression_test_files_executed", ())) == members
        and record.get("member_outcomes")
        == [{"path": member, "outcome": "passed"} for member in members]
    ), (
        "WHAT: a THREE-member historical aggregate declaration was refused "
        f"at E1 because of the stray AT file {stray!r}, even though every "
        "declared member is tracked at the target commit; WHY: ADR-002's "
        "fix must forward the FULL declared tuple as E1's population, not "
        "only aggregate_members[0] -- a partial fix that special-cases a "
        "single member would still leave a multi-member declaration's "
        "remaining members unrecognized as E1 evidence; HOW: forward the "
        "complete aggregate_members tuple as regression_test_files and let "
        "E1 clear using every declared member. "
        f"stray={stray!r} exit_code={exit_code!r} receipt={receipt!r} record={record!r}"
    )
