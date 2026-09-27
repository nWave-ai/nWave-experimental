"""Native execution comes only from typed design facts, never Request prose."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from des.application.delivery_continuation import (
    AuthorityFacts,
    DeliveryContinuationRunner,
    DeliveryOutcome,
    NativeEvidence,
)
from des.application.handover import StoredHandover


def test_a_request_mentioning_des_project_cannot_add_a_native_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Candidate verification executes design argv, even with command-like prose."""
    root = tmp_path / "root"
    candidate_directory = tmp_path / "candidate"
    root.mkdir()
    candidate_directory.mkdir()
    declared = ("python", "-c", "print('declared')")
    narrative_des_project = ("des", "project")
    runner = DeliveryContinuationRunner()
    executed: list[tuple[tuple[str, ...], ...]] = []
    prepared = [
        (
            "the declared vector is the only verification",
            AuthorityFacts(
                locator="docs/architecture.md#Verification",
                modified_authority_paths=(),
                target_decisions=(("src/value.py", "CREATE_NEW"),),
                paradigm="object_oriented",
                decisions=(),
                obligations=(),
                acceptance_oracle_locator="tests/acceptance/test_value.py",
                acceptance_paths=("tests/acceptance/test_value.py",),
                native_verification_argvs=(declared,),
                oracle_verification_index=0,
            ),
        )
    ]
    from des.domain.document_scope import Project

    stored = StoredHandover(
        "The Request narrative mentions `des project`, but does not declare it.",
        (),
        b"handover",
        Project(),
    )

    monkeypatch.setattr(
        "des.application.delivery_continuation.tempfile.mkdtemp",
        lambda **_kwargs: str(candidate_directory),
    )
    monkeypatch.setattr(
        runner,
        "_git",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )
    monkeypatch.setattr(runner, "_candidate", lambda *_args: ("candidate", "diff"))
    monkeypatch.setattr(runner, "_refresh_turn_records", lambda *_args: None)
    monkeypatch.setattr(runner, "_changed_paths", lambda *_args: ("src/value.py",))
    monkeypatch.setattr(runner, "_retain_native_failure_evidence", lambda *_args: None)
    monkeypatch.setattr(runner, "_remove_candidate_worktree", lambda *_args: None)

    def native(
        directory: Path,
        commands: tuple[tuple[str, ...], ...],
        subject: Path,
        **_kwargs: object,
    ) -> tuple[NativeEvidence, ...]:
        assert directory == candidate_directory
        assert subject == root
        executed.append(commands)
        return (NativeEvidence(declared, 1, "declared\n", "failed"),)

    monkeypatch.setattr(runner, "_native", native)

    result = runner._verified_candidate(root, prepared, stored, "base")

    assert executed == [(declared,)]
    assert narrative_des_project not in executed[0]
    assert isinstance(result, DeliveryOutcome)
