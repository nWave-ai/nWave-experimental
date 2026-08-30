"""Safe Git constructor readback, including E4 K replay and post-seal dirt."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from des.application import delivery_snapshot
from des.application.delivery_snapshot import (
    ApprovedClosure,
    CandidateConstructor,
    FinalizedDelivery,
    _DeliveryPaths,
    construct_closure,
    construct_closure_correction,
    finalize_candidate,
    recognize_candidate,
    recognize_closure,
)
from des.domain.workspace_test_command_resolver import PreservationVector


_GITHUB_IDENTITY = ("octocat", "123456+octocat@users.noreply.github.com")


@pytest.fixture(autouse=True)
def _clear_inherited_git_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in tuple(os.environ):
        if variable in {
            "GIT_AUTHOR_NAME",
            "GIT_AUTHOR_EMAIL",
            "GIT_COMMITTER_NAME",
            "GIT_COMMITTER_EMAIL",
            "GIT_CONFIG_PARAMETERS",
        } or variable.startswith("GIT_CONFIG_"):
            monkeypatch.delenv(variable, raising=False)


def _git(root: Path, *argv: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *argv], check=True, text=True, capture_output=True
    ).stdout.strip()


def _forged_commit(
    root: Path, *, tree: str, parent: str, name: str, email: str, message: str
) -> str:
    raw = (
        f"tree {tree}\n"
        f"parent {parent}\n"
        f"author {name} <{email}> 0 +0000\n"
        f"committer {name} <{email}> 0 +0000\n"
        f"\n{message}\n"
    )
    return subprocess.run(
        ["git", "-C", str(root), "hash-object", "-t", "commit", "-w", "--stdin"],
        input=raw,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def _repo(tmp_path: Path) -> tuple[Path, dict[str, object], str, bytes, str, bytes]:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", _GITHUB_IDENTITY[0])
    _git(tmp_path, "config", "user.email", _GITHUB_IDENTITY[1])
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("before\n")
    (tmp_path / "oracle.py").write_text("assert False\n")
    (tmp_path / "verify.sh").write_text("#!/bin/sh\nexit 0\n")
    (tmp_path / "verify.sh").chmod(0o755)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "base")
    base = _git(tmp_path, "rev-parse", "HEAD")
    contract: dict[str, object] = {
        "schema-version": "1.3",
        "delivery-id": "delivery",
        "outcome": "change",
        "paradigm": "object_oriented",
        "delivery-route": "RED_TO_GREEN",
        "obligations": ["PRESERVATION"],
        "repository": {"worktree": ".", "base-revision": f"git-sha1:{base}"},
        "targets": {
            "src/a.py": {
                "candidate": "src/a.py",
                "overlap": "none",
                "decision": "EXTEND",
                "justification": "test",
                "declared-imports": [],
                "contract-shape": "bounded-change",
                "boundary": {
                    "failure-behavior": "raise",
                    "substrate-lie": "none",
                    "substrate-probe": "test",
                    "double-blind-spot": "none",
                },
            }
        },
        "acceptance-tests": {"locator": "oracle.py"},
        "verification-scope": {
            "commands": [
                {
                    "executable": {"kind": "repository", "path": "verify.sh"},
                    "arguments": [],
                }
            ]
        },
        "applicability": {"independent-review": True, "examine": False},
        "budget": {"token-limit": 1, "wall-clock-minutes": 1},
    }
    return (
        tmp_path,
        contract,
        "delivery.json",
        json.dumps(contract, sort_keys=True).encode(),
        "oracle.py",
        b"assert True\n",
    )


def _write_executable(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(0o755)


def _missing_venv_vector() -> PreservationVector:
    return PreservationVector(
        argv=(("./.venv/bin/preserve",),),
        sources=((".venv/bin/preserve", "base-owned-executable"),),
    )


def _claude_declared_vector(argv: tuple[str, ...]) -> PreservationVector:
    return PreservationVector(argv=(argv,), sources=(("CLAUDE.md", "declared"),))


def test_preservation_uses_trusted_missing_venv_executable_from_fresh_cwd(
    tmp_path: Path,
) -> None:
    integration = tmp_path / "integration"
    fresh = tmp_path / "fresh"
    integration.mkdir()
    fresh.mkdir()
    _write_executable(
        integration / ".venv/bin/preserve",
        "pwd > preservation-cwd.txt\n",
    )

    delivery_snapshot.run_preservation(
        fresh, _missing_venv_vector(), trusted_execution_root=integration
    )

    assert (fresh / "preservation-cwd.txt").read_text(encoding="utf-8").strip() == str(
        fresh
    )
    assert not (fresh / ".venv").exists()


def test_preservation_uses_trusted_bare_path_executable_declared_by_claude(
    tmp_path: Path,
) -> None:
    integration = tmp_path / "integration"
    fresh = tmp_path / "fresh"
    integration.mkdir()
    fresh.mkdir()
    executable = "k4-fixture-venv/bin/python"
    _write_executable(
        integration / executable,
        "printf declared-path > preservation-origin.txt\n",
    )

    delivery_snapshot.run_preservation(
        fresh,
        _claude_declared_vector((executable,)),
        trusted_execution_root=integration,
    )

    assert (fresh / "preservation-origin.txt").read_text(encoding="utf-8") == (
        "declared-path"
    )


def test_preservation_never_falls_back_for_bare_path_tool_from_claude(
    tmp_path: Path,
) -> None:
    integration = tmp_path / "integration"
    fresh = tmp_path / "fresh"
    integration.mkdir()
    fresh.mkdir()
    # This directory would cause a loud trusted-executable refusal if ``sh``
    # were misclassified as a repository path.  A bare tool name must use PATH.
    (integration / "sh").mkdir()

    delivery_snapshot.run_preservation(
        fresh,
        _claude_declared_vector(
            ("sh", "-c", "printf path-tool > preservation-origin.txt")
        ),
        trusted_execution_root=integration,
    )

    assert (fresh / "preservation-origin.txt").read_text(
        encoding="utf-8"
    ) == "path-tool"


@pytest.mark.parametrize("kind", ("symlink", "nonregular"))
def test_preservation_refuses_unsafe_trusted_missing_venv_executable(
    tmp_path: Path, kind: str
) -> None:
    integration = tmp_path / "integration"
    fresh = tmp_path / "fresh"
    integration.mkdir()
    fresh.mkdir()
    target = integration / ".venv/bin/preserve"
    target.parent.mkdir(parents=True)
    if kind == "symlink":
        real = integration / "real-preserve"
        _write_executable(real, "exit 0\n")
        target.symlink_to(real)
    else:
        target.mkdir()

    with pytest.raises(ValueError, match="regular non-symlink executable"):
        delivery_snapshot.run_preservation(
            fresh, _missing_venv_vector(), trusted_execution_root=integration
        )


def test_preservation_never_uses_trusted_executable_when_checkout_has_one(
    tmp_path: Path,
) -> None:
    integration = tmp_path / "integration"
    fresh = tmp_path / "fresh"
    integration.mkdir()
    fresh.mkdir()
    _write_executable(
        fresh / ".venv/bin/preserve",
        "printf checkout > preservation-origin.txt\n",
    )
    # A non-regular trusted target would be a loud refusal if consulted; the
    # checkout executable must win without even resolving this fallback.
    (integration / ".venv/bin/preserve").mkdir(parents=True)

    delivery_snapshot.run_preservation(
        fresh, _missing_venv_vector(), trusted_execution_root=integration
    )

    assert (fresh / "preservation-origin.txt").read_text(encoding="utf-8") == "checkout"


def test_closure_and_candidate_are_admitted_deterministic_children(
    tmp_path: Path,
) -> None:
    repo, contract, locator, contents, oracle, oracle_bytes = _repo(tmp_path)
    closure = construct_closure(
        repo,
        contract=contract,
        contract_locator=locator,
        contract_bytes=contents,
        oracle_locator=oracle,
        oracle_bytes=oracle_bytes,
        supporting=(),
    )
    (closure.root / "src/a.py").write_text("after\n")
    candidate = CandidateConstructor().seal(
        ApprovedClosure(closure, locator, oracle, "d" * 64, contract),
        closure.root,
        {"src/a.py"},
    )
    assert _git(candidate.root, "rev-parse", "HEAD^") == closure.commit
    assert (
        _git(candidate.root, "diff", "--name-only", closure.commit, candidate.commit)
        == "src/a.py"
    )


def test_constructor_commits_ignore_author_only_hook_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, contract, locator, contents, oracle, oracle_bytes = _repo(tmp_path)
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    hook.chmod(0o755)
    monkeypatch.setenv("GIT_AUTHOR_NAME", "hook author only")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "hook-author@example.invalid")
    monkeypatch.delenv("GIT_COMMITTER_NAME", raising=False)
    monkeypatch.delenv("GIT_COMMITTER_EMAIL", raising=False)

    closure = construct_closure(
        repo,
        contract=contract,
        contract_locator=locator,
        contract_bytes=contents,
        oracle_locator=oracle,
        oracle_bytes=oracle_bytes,
        supporting=(),
    )
    (closure.root / "src/a.py").write_text("after\n")
    candidate = CandidateConstructor().seal(
        ApprovedClosure(closure, locator, oracle, "d" * 64, contract),
        closure.root,
        {"src/a.py"},
    )
    base = str(contract["repository"]["base-revision"]).split(":", 1)[1]
    finalized = finalize_candidate(
        repo,
        candidate=candidate,
        base=base,
        authorized_paths={locator, oracle, "src/a.py"},
        target_ref="refs/heads/master",
        contract_locator=locator,
    )

    expected_identity = (*_GITHUB_IDENTITY, *_GITHUB_IDENTITY)
    for commit in (closure.commit, candidate.commit, finalized.commit):
        metadata = delivery_snapshot._metadata(repo, commit)
        assert metadata[2:6] == expected_identity


def test_constructor_commits_use_gate_run_timeout_but_git_probes_do_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, contract, locator, contents, oracle, oracle_bytes = _repo(tmp_path)
    git_timeout = 17.0
    gate_timeout = 91.0
    original_spawn = delivery_snapshot.spawn
    git_calls: list[tuple[list[str], float | None]] = []

    def observe_spawn(argv: list[str], **kwargs: object):
        if argv and argv[0] == "git":
            git_calls.append((argv, kwargs.get("timeout")))
        return original_spawn(argv, **kwargs)

    monkeypatch.setattr(delivery_snapshot, "git_timeout_seconds", lambda: git_timeout)
    monkeypatch.setattr(delivery_snapshot, "run_timeout_seconds", lambda: gate_timeout)
    monkeypatch.setattr(delivery_snapshot, "spawn", observe_spawn)

    closure = construct_closure(
        repo,
        contract=contract,
        contract_locator=locator,
        contract_bytes=contents,
        oracle_locator=oracle,
        oracle_bytes=oracle_bytes,
        supporting=(),
    )
    (closure.root / "src/a.py").write_text("after\n")
    candidate = CandidateConstructor().seal(
        ApprovedClosure(closure, locator, oracle, "d" * 64, contract),
        closure.root,
        {"src/a.py"},
    )
    base = str(contract["repository"]["base-revision"]).split(":", 1)[1]
    finalize_candidate(
        repo,
        candidate=candidate,
        base=base,
        authorized_paths={locator, oracle, "src/a.py"},
        target_ref="refs/heads/master",
        contract_locator=locator,
    )

    commits = [timeout for argv, timeout in git_calls if "commit" in argv]
    probes = [timeout for argv, timeout in git_calls if "commit" not in argv]
    assert commits and all(timeout == gate_timeout for timeout in commits)
    assert any("--amend" in argv for argv, _timeout in git_calls)
    assert any(
        "commit" in argv and "chore(des): finalize delivery" in argv
        for argv, _timeout in git_calls
    )
    assert probes and all(timeout == git_timeout for timeout in probes)


def test_snapshot_determinism_excludes_effective_git_identity(tmp_path: Path) -> None:
    repo, contract, locator, contents, oracle, oracle_bytes = _repo(tmp_path)
    first = construct_closure(
        repo,
        contract=contract,
        contract_locator=locator,
        contract_bytes=contents,
        oracle_locator=oracle,
        oracle_bytes=oracle_bytes,
        supporting=(),
    )
    _git(repo, "config", "user.name", "other")
    _git(repo, "config", "user.email", "other@users.noreply.github.com")
    second = construct_closure(
        repo,
        contract=contract,
        contract_locator=locator,
        contract_bytes=contents,
        oracle_locator=oracle,
        oracle_bytes=oracle_bytes,
        supporting=(),
    )

    assert _git(repo, "rev-parse", f"{first.commit}^{{tree}}") == _git(
        repo, "rev-parse", f"{second.commit}^{{tree}}"
    )
    assert _git(repo, "diff", "--name-only", first.parent, first.commit) == _git(
        repo, "diff", "--name-only", second.parent, second.commit
    )
    assert _git(repo, "show", "-s", "--format=%B%x00%at%x00%ct", first.commit) == (
        "chore(des): construct delivery closure\n\x000\x000"
    )
    assert _git(repo, "show", "-s", "--format=%B%x00%at%x00%ct", second.commit) == (
        "chore(des): construct delivery closure\n\x000\x000"
    )
    assert first.commit != second.commit


def test_finalizer_allows_same_root_k_as_its_explicit_cas_predecessor(
    tmp_path: Path,
) -> None:
    repo, contract, locator, contents, oracle, oracle_bytes = _repo(tmp_path)
    closure = construct_closure(
        repo,
        contract=contract,
        contract_locator=locator,
        contract_bytes=contents,
        oracle_locator=oracle,
        oracle_bytes=oracle_bytes,
        supporting=(),
        constructor_root=repo,
    )
    (repo / "src/a.py").write_text("after\n")
    candidate = CandidateConstructor().seal(
        ApprovedClosure(closure, locator, oracle, "d" * 64, contract),
        repo,
        {"src/a.py"},
    )
    base = str(contract["repository"]["base-revision"]).split(":", 1)[1]
    finalized = finalize_candidate(
        repo,
        candidate=candidate,
        base=base,
        authorized_paths={locator, oracle, "src/a.py"},
        target_ref="refs/heads/master",
        contract_locator=locator,
    )
    assert isinstance(finalized, FinalizedDelivery)
    assert _git(repo, "rev-parse", "refs/heads/master") == finalized.commit
    assert _git(repo, "rev-parse", f"{finalized.commit}^") == base
    assert finalized.authorized_paths == frozenset({locator, oracle, "src/a.py"})
    assert finalized.preservation == candidate.preservation
    assert finalized.clean_checkout is True
    expected = "\x00".join((*_GITHUB_IDENTITY, *_GITHUB_IDENTITY, "0", "0"))
    assert (
        _git(
            repo,
            "show",
            "-s",
            "--format=%an%x00%ae%x00%cn%x00%ce%x00%at%x00%ct",
            finalized.commit,
        )
        == expected
    )
    assert (
        _git(
            repo,
            "show",
            "-s",
            "--format=%an%x00%ae%x00%cn%x00%ce%x00%at%x00%ct",
            closure.commit,
        )
        == expected
    )
    assert (
        _git(
            repo,
            "show",
            "-s",
            "--format=%an%x00%ae%x00%cn%x00%ce%x00%at%x00%ct",
            candidate.commit,
        )
        == expected
    )
    assert closure.commit not in _git(repo, "rev-list", finalized.commit).splitlines()
    assert candidate.commit not in _git(repo, "rev-list", finalized.commit).splitlines()

    _git(repo, "config", "user.name", "changed-later")
    _git(repo, "config", "user.email", "changed-later@example.invalid")
    assert recognize_closure(repo, closure.commit).commit == closure.commit
    assert recognize_candidate(repo, candidate.commit).commit == candidate.commit
    assert (
        finalize_candidate(
            repo,
            candidate=candidate,
            base=base,
            authorized_paths={locator, oracle, "src/a.py"},
            target_ref="refs/heads/master",
            contract_locator=locator,
        ).commit
        == finalized.commit
    )


def test_recognition_refuses_forged_author_committer_mismatch(tmp_path: Path) -> None:
    repo, contract, locator, contents, oracle, oracle_bytes = _repo(tmp_path)
    closure = construct_closure(
        repo,
        contract=contract,
        contract_locator=locator,
        contract_bytes=contents,
        oracle_locator=oracle,
        oracle_bytes=oracle_bytes,
        supporting=(),
    )
    tree = _git(repo, "rev-parse", f"{closure.commit}^{{tree}}")
    forged = subprocess.run(
        ["git", "-C", str(repo), "commit-tree", tree, "-p", closure.parent],
        input="chore(des): construct delivery closure\n",
        text=True,
        capture_output=True,
        check=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": _GITHUB_IDENTITY[0],
            "GIT_AUTHOR_EMAIL": _GITHUB_IDENTITY[1],
            "GIT_COMMITTER_NAME": "forged",
            "GIT_COMMITTER_EMAIL": "forged@example.invalid",
            "GIT_AUTHOR_DATE": "@0 +0000",
            "GIT_COMMITTER_DATE": "@0 +0000",
        },
    ).stdout.strip()

    with pytest.raises(ValueError, match="metadata mismatch"):
        recognize_closure(repo, forged)


@pytest.mark.parametrize(
    ("name", "email", "admitted"),
    [
        ("octocat", "654321+octocat@users.noreply.github.com", True),
        ("octocat", "bad", False),
        ("octocat", "octo cat@example.com", False),
        ("octocat", "octo\x7fcat@example.com", False),
        ("octocat", "octocat@example", False),
        ("octocat", "octocat@@example.com", False),
        ("octocat", "octocat@.example.com", False),
    ],
)
def test_recognition_validates_forged_identity_wire_shape(
    tmp_path: Path, name: str, email: str, admitted: bool
) -> None:
    repo, contract, locator, contents, oracle, oracle_bytes = _repo(tmp_path)
    closure = construct_closure(
        repo,
        contract=contract,
        contract_locator=locator,
        contract_bytes=contents,
        oracle_locator=oracle,
        oracle_bytes=oracle_bytes,
        supporting=(),
    )
    forged = _forged_commit(
        repo,
        tree=_git(repo, "rev-parse", f"{closure.commit}^{{tree}}"),
        parent=closure.parent,
        name=name,
        email=email,
        message="chore(des): construct delivery closure",
    )

    if admitted:
        assert recognize_closure(repo, forged).commit == forged
    else:
        with pytest.raises(ValueError, match="metadata mismatch"):
            recognize_closure(repo, forged)


def test_finalizer_reverifies_existing_f_without_creating_second_commit(
    tmp_path: Path,
) -> None:
    repo, contract, locator, contents, oracle, oracle_bytes = _repo(tmp_path)
    closure = construct_closure(
        repo,
        contract=contract,
        contract_locator=locator,
        contract_bytes=contents,
        oracle_locator=oracle,
        oracle_bytes=oracle_bytes,
        supporting=(),
        constructor_root=repo,
    )
    (repo / "src/a.py").write_text("after\n")
    candidate = CandidateConstructor().seal(
        ApprovedClosure(closure, locator, oracle, "d" * 64, contract),
        repo,
        {"src/a.py"},
    )
    base = str(contract["repository"]["base-revision"]).split(":", 1)[1]
    first = finalize_candidate(
        repo,
        candidate=candidate,
        base=base,
        authorized_paths={locator, oracle, "src/a.py"},
        target_ref="refs/heads/master",
        contract_locator=locator,
    )
    second = finalize_candidate(
        repo,
        candidate=candidate,
        base=base,
        authorized_paths={locator, oracle, "src/a.py"},
        target_ref="refs/heads/master",
        contract_locator=locator,
    )
    assert second == first
    assert _git(repo, "rev-list", "--count", "refs/heads/master") == "2"


def test_finalizer_refuses_existing_f_when_target_moves_during_reverification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, contract, locator, contents, oracle, oracle_bytes = _repo(tmp_path)
    closure = construct_closure(
        repo,
        contract=contract,
        contract_locator=locator,
        contract_bytes=contents,
        oracle_locator=oracle,
        oracle_bytes=oracle_bytes,
        supporting=(),
        constructor_root=repo,
    )
    (repo / "src/a.py").write_text("after\n")
    candidate = CandidateConstructor().seal(
        ApprovedClosure(closure, locator, oracle, "d" * 64, contract),
        repo,
        {"src/a.py"},
    )
    base = str(contract["repository"]["base-revision"]).split(":", 1)[1]
    final = finalize_candidate(
        repo,
        candidate=candidate,
        base=base,
        authorized_paths={locator, oracle, "src/a.py"},
        target_ref="refs/heads/master",
        contract_locator=locator,
    )
    verify = delivery_snapshot._verify_final_checkout

    def verify_then_move(
        repo_arg: Path, *, commit: str, vector: PreservationVector
    ) -> bool:
        clean = verify(repo_arg, commit=commit, vector=vector)
        _git(repo_arg, "update-ref", "refs/heads/master", candidate.commit, commit)
        return clean

    monkeypatch.setattr(delivery_snapshot, "_verify_final_checkout", verify_then_move)
    with pytest.raises(ValueError, match="changed during final replay"):
        finalize_candidate(
            repo,
            candidate=candidate,
            base=base,
            authorized_paths={locator, oracle, "src/a.py"},
            target_ref="refs/heads/master",
            contract_locator=locator,
        )
    assert _git(repo, "rev-parse", "refs/heads/master") == candidate.commit
    assert final.commit != candidate.commit


def test_finalizer_refuses_forged_final_author_or_date(tmp_path: Path) -> None:
    repo, contract, locator, contents, oracle, oracle_bytes = _repo(tmp_path)
    closure = construct_closure(
        repo,
        contract=contract,
        contract_locator=locator,
        contract_bytes=contents,
        oracle_locator=oracle,
        oracle_bytes=oracle_bytes,
        supporting=(),
        constructor_root=repo,
    )
    (repo / "src/a.py").write_text("after\n")
    candidate = CandidateConstructor().seal(
        ApprovedClosure(closure, locator, oracle, "d" * 64, contract),
        repo,
        {"src/a.py"},
    )
    base = str(contract["repository"]["base-revision"]).split(":", 1)[1]
    final = finalize_candidate(
        repo,
        candidate=candidate,
        base=base,
        authorized_paths={locator, oracle, "src/a.py"},
        target_ref="refs/heads/master",
        contract_locator=locator,
    )
    tree = _git(repo, "rev-parse", f"{final.commit}^{{tree}}")
    _git(repo, "branch", "published", base)
    forged = subprocess.run(
        ["git", "-C", str(repo), "commit-tree", tree, "-p", base],
        input="chore(des): finalize delivery\n",
        text=True,
        capture_output=True,
        check=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "forged",
            "GIT_AUTHOR_EMAIL": "forged@example.invalid",
            "GIT_COMMITTER_NAME": "forged",
            "GIT_COMMITTER_EMAIL": "forged@example.invalid",
            "GIT_AUTHOR_DATE": "@1 +0000",
            "GIT_COMMITTER_DATE": "@1 +0000",
        },
    ).stdout.strip()
    _git(repo, "update-ref", "refs/heads/published", forged, base)
    with pytest.raises(ValueError, match="target ref changed"):
        finalize_candidate(
            repo,
            candidate=candidate,
            base=base,
            authorized_paths={locator, oracle, "src/a.py"},
            target_ref="refs/heads/published",
            contract_locator=locator,
        )
    assert _git(repo, "rev-parse", "refs/heads/published") == forged


def test_finalizer_refuses_forged_final_with_malformed_identity(
    tmp_path: Path,
) -> None:
    repo, contract, locator, contents, oracle, oracle_bytes = _repo(tmp_path)
    closure = construct_closure(
        repo,
        contract=contract,
        contract_locator=locator,
        contract_bytes=contents,
        oracle_locator=oracle,
        oracle_bytes=oracle_bytes,
        supporting=(),
        constructor_root=repo,
    )
    (repo / "src/a.py").write_text("after\n")
    candidate = CandidateConstructor().seal(
        ApprovedClosure(closure, locator, oracle, "d" * 64, contract),
        repo,
        {"src/a.py"},
    )
    base = str(contract["repository"]["base-revision"]).split(":", 1)[1]
    final = finalize_candidate(
        repo,
        candidate=candidate,
        base=base,
        authorized_paths={locator, oracle, "src/a.py"},
        target_ref="refs/heads/master",
        contract_locator=locator,
    )
    _git(repo, "branch", "published", base)
    forged = _forged_commit(
        repo,
        tree=_git(repo, "rev-parse", f"{final.commit}^{{tree}}"),
        parent=base,
        name="octocat",
        email="bad",
        message="chore(des): finalize delivery",
    )
    _git(repo, "update-ref", "refs/heads/published", forged, base)

    with pytest.raises(ValueError, match="target ref changed before final projection"):
        finalize_candidate(
            repo,
            candidate=candidate,
            base=base,
            authorized_paths={locator, oracle, "src/a.py"},
            target_ref="refs/heads/published",
            contract_locator=locator,
        )


def test_finalizer_refuses_before_cas_when_cleanup_is_indeterminate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, contract, locator, contents, oracle, oracle_bytes = _repo(tmp_path)
    closure = construct_closure(
        repo,
        contract=contract,
        contract_locator=locator,
        contract_bytes=contents,
        oracle_locator=oracle,
        oracle_bytes=oracle_bytes,
        supporting=(),
        constructor_root=repo,
    )
    (repo / "src/a.py").write_text("after\n")
    candidate = CandidateConstructor().seal(
        ApprovedClosure(closure, locator, oracle, "d" * 64, contract),
        repo,
        {"src/a.py"},
    )
    base = str(contract["repository"]["base-revision"]).split(":", 1)[1]
    _git(repo, "branch", "published", base)
    original_cleanup = delivery_snapshot._remove_worktree
    leaked: list[Path] = []

    def cleanup_failure(_repo: Path, root: Path) -> None:
        leaked.append(root)
        raise RuntimeError("synthetic cleanup failure")

    monkeypatch.setattr(delivery_snapshot, "_remove_worktree", cleanup_failure)
    with pytest.raises(RuntimeError, match="cleanup failure"):
        finalize_candidate(
            repo,
            candidate=candidate,
            base=base,
            authorized_paths={locator, oracle, "src/a.py"},
            target_ref="refs/heads/published",
            contract_locator=locator,
        )
    assert _git(repo, "rev-parse", "refs/heads/published") == base
    assert len(leaked) == 1
    original_cleanup(repo, leaked[0])


def test_finalizer_reports_post_cas_cleanup_failure_then_retries_idempotently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, contract, locator, contents, oracle, oracle_bytes = _repo(tmp_path)
    closure = construct_closure(
        repo,
        contract=contract,
        contract_locator=locator,
        contract_bytes=contents,
        oracle_locator=oracle,
        oracle_bytes=oracle_bytes,
        supporting=(),
        constructor_root=repo,
    )
    (repo / "src/a.py").write_text("after\n")
    candidate = CandidateConstructor().seal(
        ApprovedClosure(closure, locator, oracle, "d" * 64, contract),
        repo,
        {"src/a.py"},
    )
    base = str(contract["repository"]["base-revision"]).split(":", 1)[1]
    _git(repo, "branch", "published", base)
    original_cleanup = delivery_snapshot._remove_worktree
    calls = 0
    leaked: list[Path] = []

    def fail_after_cas(repo_arg: Path, root: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            leaked.append(root)
            raise RuntimeError("synthetic post-CAS cleanup failure")
        original_cleanup(repo_arg, root)

    monkeypatch.setattr(delivery_snapshot, "_remove_worktree", fail_after_cas)
    with pytest.raises(RuntimeError, match="post-CAS cleanup"):
        finalize_candidate(
            repo,
            candidate=candidate,
            base=base,
            authorized_paths={locator, oracle, "src/a.py"},
            target_ref="refs/heads/published",
            contract_locator=locator,
        )
    final = _git(repo, "rev-parse", "refs/heads/published")
    assert final != base
    assert len(leaked) == 1
    original_cleanup(repo, leaked[0])
    monkeypatch.setattr(delivery_snapshot, "_remove_worktree", original_cleanup)
    replay = finalize_candidate(
        repo,
        candidate=candidate,
        base=base,
        authorized_paths={locator, oracle, "src/a.py"},
        target_ref="refs/heads/published",
        contract_locator=locator,
    )
    assert replay.commit == final


def test_finalizer_refuses_hook_residue_before_admission_or_cas(tmp_path: Path) -> None:
    repo, contract, locator, contents, oracle, oracle_bytes = _repo(tmp_path)
    closure = construct_closure(
        repo,
        contract=contract,
        contract_locator=locator,
        contract_bytes=contents,
        oracle_locator=oracle,
        oracle_bytes=oracle_bytes,
        supporting=(),
        constructor_root=repo,
    )
    (repo / "src/a.py").write_text("after\n")
    candidate = CandidateConstructor().seal(
        ApprovedClosure(closure, locator, oracle, "d" * 64, contract),
        repo,
        {"src/a.py"},
    )
    base = str(contract["repository"]["base-revision"]).split(":", 1)[1]
    _git(repo, "branch", "published", base)
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(
        "#!/bin/sh\nprintf residue > final-untracked\nprintf changed > src/a.py\n"
    )
    hook.chmod(0o755)
    with pytest.raises(
        ValueError, match="constructor hook left index or worktree dirt"
    ):
        finalize_candidate(
            repo,
            candidate=candidate,
            base=base,
            authorized_paths={locator, oracle, "src/a.py"},
            target_ref="refs/heads/published",
            contract_locator=locator,
        )
    assert _git(repo, "rev-parse", "refs/heads/published") == base


def test_finalizer_refuses_candidate_supplied_unauthorized_argv_before_cas(
    tmp_path: Path,
) -> None:
    repo, contract, locator, contents, oracle, oracle_bytes = _repo(tmp_path)
    closure = construct_closure(
        repo,
        contract=contract,
        contract_locator=locator,
        contract_bytes=contents,
        oracle_locator=oracle,
        oracle_bytes=oracle_bytes,
        supporting=(),
        constructor_root=repo,
    )
    (repo / "src/a.py").write_text("after\n")
    candidate = CandidateConstructor().seal(
        ApprovedClosure(closure, locator, oracle, "d" * 64, contract),
        repo,
        {"src/a.py"},
    )
    base = str(contract["repository"]["base-revision"]).split(":", 1)[1]
    _git(repo, "branch", "published", base)
    unauthorized = PreservationVector(
        argv=((sys.executable, "-c", "raise SystemExit(0)"),),
        sources=(("verify.sh", hashlib.sha256(b"#!/bin/sh\nexit 0\n").hexdigest()),),
    )
    with pytest.raises(ValueError, match="candidate preservation differs"):
        finalize_candidate(
            repo,
            candidate=replace(candidate, preservation=unauthorized),
            base=base,
            authorized_paths={locator, oracle, "src/a.py"},
            target_ref="refs/heads/published",
            contract_locator=locator,
        )
    assert _git(repo, "rev-parse", "refs/heads/published") == base


def test_finalizer_refuses_f_when_b_owned_vector_source_digest_changed(
    tmp_path: Path,
) -> None:
    repo, contract, locator, contents, oracle, oracle_bytes = _repo(tmp_path)
    contract["verification-scope"] = {
        "commands": [
            {
                "executable": {"kind": "toolchain", "name": "sh"},
                "arguments": ["verify.sh"],
            }
        ]
    }
    contents = json.dumps(contract, sort_keys=True).encode()
    closure = construct_closure(
        repo,
        contract=contract,
        contract_locator=locator,
        contract_bytes=contents,
        oracle_locator=oracle,
        oracle_bytes=oracle_bytes,
        supporting=(),
        constructor_root=repo,
    )
    (repo / "src/a.py").write_text("after\n")
    (repo / "verify.sh").write_text("#!/bin/sh\n# candidate mutation\nexit 0\n")
    candidate = CandidateConstructor().seal(
        ApprovedClosure(closure, locator, oracle, "d" * 64, contract),
        repo,
        {"src/a.py", "verify.sh"},
    )
    base = str(contract["repository"]["base-revision"]).split(":", 1)[1]
    _git(repo, "branch", "published", base)
    with pytest.raises(ValueError, match="digest differs"):
        finalize_candidate(
            repo,
            candidate=candidate,
            base=base,
            authorized_paths={locator, oracle, "src/a.py", "verify.sh"},
            target_ref="refs/heads/published",
            contract_locator=locator,
        )
    assert _git(repo, "rev-parse", "refs/heads/published") == base


def test_finalizer_refuses_an_unadmitted_candidate(tmp_path: Path) -> None:
    repo, contract, locator, contents, oracle, oracle_bytes = _repo(tmp_path)
    closure = construct_closure(
        repo,
        contract=contract,
        contract_locator=locator,
        contract_bytes=contents,
        oracle_locator=oracle,
        oracle_bytes=oracle_bytes,
        supporting=(),
    )
    with pytest.raises(ValueError, match="candidate"):
        finalize_candidate(
            repo,
            candidate=closure,
            base=closure.base or "",
            authorized_paths=set(),
            target_ref="refs/heads/master",
            contract_locator=locator,
        )


def test_closure_correction_cannot_promote_prior_c_authority_into_b_vector(
    tmp_path: Path,
) -> None:
    repo, contract, locator, _contents, oracle, oracle_bytes = _repo(tmp_path)
    prior_base = b"#!/bin/sh\nexit 0\n"
    (repo / "prior.py").write_bytes(prior_base)
    (repo / "prior.py").chmod(0o755)
    _git(repo, "add", "prior.py")
    _git(repo, "commit", "-qm", "prior base")
    base = _git(repo, "rev-parse", "HEAD")
    contract["schema-version"] = "1.4"
    contract["repository"]["base-revision"] = f"git-sha1:{base}"
    contract["acceptance-tests"]["supporting-locators"] = ["prior.py"]
    contents = json.dumps(contract, sort_keys=True).encode()
    closure = construct_closure(
        repo,
        contract=contract,
        contract_locator=locator,
        contract_bytes=contents,
        oracle_locator=oracle,
        oracle_bytes=oracle_bytes,
        supporting=(("prior.py", b"#!/bin/sh\n# closure authority\nexit 0\n"),),
    )
    corrected = json.loads(json.dumps(contract))
    corrected["schema-version"] = "1.3"
    corrected["acceptance-tests"].pop("supporting-locators")
    corrected["verification-scope"] = {
        "commands": [
            {
                "executable": {"kind": "toolchain", "name": "sh"},
                "arguments": ["prior.py"],
            }
        ]
    }
    with pytest.raises(ValueError, match="no base-owned preservation command"):
        construct_closure_correction(
            closure.root,
            cited=closure,
            contract=corrected,
            contract_locator=locator,
            contract_bytes=json.dumps(corrected, sort_keys=True).encode(),
            oracle_locator=oracle,
            oracle_bytes=b"assert True  # corrected\n",
            supporting=(),
        )


def test_delivery_paths_normalize_and_reject_role_overlap() -> None:
    with pytest.raises(ValueError, match="delivery path roles overlap"):
        _DeliveryPaths.build(
            authority={"docs/brief.md"},
            oracle_dependencies={"docs/./brief.md"},
            crafter_writable={"src/a.py"},
        )


def test_crafter_expected_delta_refuses_pending_path_outside_writable() -> None:
    paths = _DeliveryPaths.build(
        authority={"docs/brief.md"},
        oracle_dependencies={"oracle.py"},
        crafter_writable={"src/a.py"},
    )

    with pytest.raises(ValueError, match="outside CrafterWritableTargets"):
        paths.crafter_expected_delta({"docs/brief.md"})
