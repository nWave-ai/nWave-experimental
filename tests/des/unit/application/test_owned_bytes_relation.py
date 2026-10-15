"""Finite owned-byte outcomes over authentic authority, Git and filesystem state."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from des.adapters.driven.git.git_observation import observe_bytes
from des.application.delivery_continuation import (
    DeliveryContinuationRunner,
    DeliveryOutcome,
    OwnedBytesCovered,
    OwnedBytesDrifted,
    OwnedBytesUnobservable,
)
from des.application.handover import HandoverValue, StoredHandover
from des.domain.document_scope import Project
from des.ports.driven_ports.task_invocation_port import DesignTarget
from tests.des.unit.application.test_delivery_continuation import _typed, git, repo
from tests.des.unit.application.test_runner_git_and_fs_seam_totality import without_git


TARGET = "owned/value.bin"
ORACLE = "tests/acceptance/test_value.py"
AUTHORITY = "notes/any.md"
ORIGINAL = b"\x00original\xff\n"


def _repository(
    tmp_path: Path,
    targets: tuple[str, ...] = (TARGET,),
    *,
    absent: tuple[str, ...] = (),
    supports: tuple[str, ...] = (),
) -> tuple[Path, StoredHandover, str]:
    """Reuse the real-Git and typed DESIGN fixtures, without running verification."""
    root = repo(tmp_path, AUTHORITY, text="## Value 1\n")
    git(root, "config", "core.filemode", "true")
    design = _typed(supports)
    design = replace(
        design,
        targets=tuple(
            DesignTarget(path, "EXTEND", design.targets[0].reason) for path in targets
        ),
        authority_locator=f"{AUTHORITY}#Value 1",
        verification=((sys.executable, "-m", "pytest", ORACLE),),
    )
    for relative in (ORACLE, *supports, *targets):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if relative in absent:
            continue
        path.write_bytes(
            b"def test_value():\n    assert 1 + 1 == 2\n"
            if relative == ORACLE
            else ORIGINAL
        )
        path.chmod(0o644)
    git(root, "add", ".")
    git(root, "commit", "-qm", "Owned byte baseline")
    candidate = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    stored = StoredHandover(
        "Observe the owned byte relation",
        (HandoverValue("the owned bytes agree with the candidate", (), design),),
        b"{}",
        Project(),
    )
    selected = DeliveryContinuationRunner().selected_authority(root, stored, 1)
    assert not isinstance(selected, DeliveryOutcome), selected
    return root, stored, candidate


def _relation(
    root: Path, stored: StoredHandover, candidate: str
) -> OwnedBytesCovered | OwnedBytesDrifted | OwnedBytesUnobservable:
    runner = DeliveryContinuationRunner()
    result = runner._owned_bytes_relation(root, stored, candidate)
    assert runner._candidate_covers_current_owned_bytes(
        root, stored, candidate
    ) is isinstance(result, OwnedBytesCovered)
    return result


@pytest.mark.parametrize("state", ("regular", "executable", "absent-in-both"))
def test_equal_regular_bytes_and_modes_or_shared_absence_are_covered(
    tmp_path: Path, state: str
) -> None:
    root, stored, candidate = _repository(
        tmp_path, absent=(TARGET,) if state == "absent-in-both" else ()
    )
    if state == "executable":
        (root / TARGET).chmod(0o755)
        git(root, "add", TARGET)
        git(root, "commit", "-qm", "Executable owned file")
        candidate = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    assert isinstance(_relation(root, stored, candidate), OwnedBytesCovered)


@pytest.mark.parametrize("kind", ("content", "mode", "added", "deleted", "symlink"))
def test_each_observable_mismatch_names_its_owned_path_and_kind(
    tmp_path: Path, kind: str
) -> None:
    root, stored, candidate = _repository(
        tmp_path, absent=(TARGET,) if kind == "added" else ()
    )
    path = root / TARGET
    if kind == "content":
        path.write_bytes(b"\x00modified\xff\n")
    elif kind == "mode":
        path.chmod(0o755)
    elif kind == "added":
        path.write_bytes(ORIGINAL)
    elif kind == "deleted":
        path.unlink()
    else:
        # A readable referent with identical bytes is still not a regular file.
        referent = root / "same-bytes.bin"
        referent.write_bytes(ORIGINAL)
        path.unlink()
        path.symlink_to(referent)

    result = _relation(root, stored, candidate)

    assert isinstance(result, OwnedBytesDrifted), result
    assert result.paths == ((TARGET, kind),)


def test_losing_the_executable_bit_is_mode_drift(tmp_path: Path) -> None:
    root, stored, _ = _repository(tmp_path)
    path = root / TARGET
    path.chmod(0o755)
    git(root, "add", TARGET)
    git(root, "commit", "-qm", "Executable owned file")
    candidate = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    path.chmod(0o644)

    result = _relation(root, stored, candidate)

    assert isinstance(result, OwnedBytesDrifted), result
    assert result.paths == ((TARGET, "mode"),)


def test_all_drifted_paths_in_the_owned_union_are_reported_in_sorted_order(
    tmp_path: Path,
) -> None:
    targets = (
        "owned/z-deleted.bin",
        "owned/m-symlink.bin",
        "owned/y-mode.bin",
        "owned/a-added.bin",
        "owned/b-content.bin",
    )
    support = "tests/acceptance/support.bin"
    root, stored, candidate = _repository(
        tmp_path, targets, absent=("owned/a-added.bin",), supports=(support,)
    )
    (root / targets[0]).unlink()
    (root / targets[1]).unlink()
    (root / targets[1]).symlink_to(root / targets[4])
    (root / targets[2]).chmod(0o755)
    (root / targets[3]).write_bytes(ORIGINAL)
    (root / targets[4]).write_bytes(b"different target bytes")
    (root / ORACLE).write_text("def test_value():\n    assert 2 + 2 == 4\n")
    (root / support).write_bytes(b"different support bytes")
    with (root / AUTHORITY).open("a") as document:
        document.write("\nOwned byte observation note.\n")

    result = _relation(root, stored, candidate)

    assert isinstance(result, OwnedBytesDrifted), result
    assert result.paths == (
        (AUTHORITY, "content"),
        ("owned/a-added.bin", "added"),
        ("owned/b-content.bin", "content"),
        ("owned/m-symlink.bin", "symlink"),
        ("owned/y-mode.bin", "mode"),
        ("owned/z-deleted.bin", "deleted"),
        ("tests/acceptance/support.bin", "content"),
        (ORACLE, "content"),
    )


@pytest.mark.parametrize("order", ("alone", "drift-first", "unreadable-first"))
def test_real_unreadable_file_overrides_any_partial_drift(
    tmp_path: Path, order: str
) -> None:
    assert os.geteuid() != 0, "This permission observation requires a non-root host."
    unreadable = "owned/z-unreadable.bin"
    drifted = "owned/a-drift.bin"
    targets = {
        "alone": (unreadable,),
        "drift-first": (drifted, unreadable),
        "unreadable-first": (unreadable, drifted),
    }[order]
    root, stored, candidate = _repository(tmp_path, targets)
    if drifted in targets:
        (root / drifted).write_bytes(b"measurable content drift")
    path = root / unreadable
    original_mode = stat.S_IMODE(path.stat().st_mode)
    try:
        path.chmod(0)
        # Refuse a privileged false proof: this must really fail on this host.
        with pytest.raises(PermissionError) as refused:
            path.read_bytes()

        result = _relation(root, stored, candidate)

        assert isinstance(result, OwnedBytesUnobservable), result
        assert unreadable in result.what
        assert type(refused.value).__name__ in result.why
    finally:
        path.chmod(original_mode)


def test_unanswerable_candidate_sha_carries_the_actual_ls_tree_failure(
    tmp_path: Path,
) -> None:
    root, stored, candidate = _repository(tmp_path)
    unknown = "0" * len(candidate)
    primitive = observe_bytes(root, "ls-tree", "-z", unknown, "--", ORACLE)
    assert primitive.returncode != 0
    assert primitive.stderr, primitive

    result = _relation(root, stored, unknown)

    assert isinstance(result, OwnedBytesUnobservable), result
    detail = f"{result.what}\n{result.why}"
    assert ORACLE in detail
    assert unknown in detail
    assert "ls-tree" in detail
    assert primitive.stderr.decode(errors="replace").strip() in result.why


def test_unanswerable_blob_carries_the_actual_show_failure(tmp_path: Path) -> None:
    root, stored, candidate = _repository(tmp_path)
    blob = subprocess.run(
        ["git", "-C", str(root), "rev-parse", f"{candidate}:{TARGET}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    # A fresh repository has loose objects. Lose this blob, not the tree: ls-tree
    # can still name it while show cannot read it, just as an incomplete store can.
    (root / ".git/objects" / blob[:2] / blob[2:]).unlink()
    listed = observe_bytes(root, "ls-tree", "-z", candidate, "--", TARGET)
    assert listed.returncode == 0 and listed.stdout
    primitive = observe_bytes(root, "show", f"{candidate}:{TARGET}")
    assert primitive.returncode != 0
    assert primitive.stderr, primitive

    result = _relation(root, stored, candidate)

    assert isinstance(result, OwnedBytesUnobservable), result
    detail = f"{result.what}\n{result.why}"
    assert TARGET in detail
    assert f"{candidate}:{TARGET}" in detail
    assert "show" in detail
    assert primitive.stderr.decode(errors="replace").strip() in result.why


def test_absent_git_carries_the_primitives_unanswered_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, stored, candidate = _repository(tmp_path / "repo")
    without_git(monkeypatch, tmp_path / "empty-bin")
    primitive = observe_bytes(root, "ls-tree", "-z", candidate, "--", ORACLE)
    assert primitive.unanswered is not None

    result = _relation(root, stored, candidate)

    assert isinstance(result, OwnedBytesUnobservable), result
    detail = f"{result.what}\n{result.why}"
    assert ORACLE in detail
    assert "ls-tree" in detail
    assert primitive.unanswered.why in result.why


def test_a_file_lost_between_byte_and_mode_observation_is_unobservable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, stored, candidate = _repository(tmp_path)
    path = root / TARGET
    original_mode = stat.S_IMODE(path.stat().st_mode)

    def observe_then_lose_file(root: Path, *args: str, **kwargs):
        observed = observe_bytes(root, *args, **kwargs)
        if args == ("show", f"{candidate}:{TARGET}") and observed.returncode == 0:
            path.unlink()
        return observed

    # Synchronize the real filesystem race at the Git port; no fabricated Git
    # outcome or mocked stat replaces either primitive observation.
    monkeypatch.setattr(
        "des.application.delivery_continuation.observe_bytes", observe_then_lose_file
    )
    try:
        result = _relation(root, stored, candidate)

        with pytest.raises(FileNotFoundError) as refused:
            path.stat()
        assert isinstance(result, OwnedBytesUnobservable), result
        assert TARGET in result.what
        assert type(refused.value).__name__ in result.why
    finally:
        path.write_bytes(ORIGINAL)
        path.chmod(original_mode)


def test_snapshot_value_without_authority_is_unobservable(tmp_path: Path) -> None:
    root, stored, candidate = _repository(tmp_path)
    stored = replace(stored, values=(replace(stored.values[0], authority=None),))

    result = _relation(root, stored, candidate)

    assert isinstance(result, OwnedBytesUnobservable), result
    assert "authority" in f"{result.what} {result.why}".lower()
    assert result.what and result.why


def test_selected_authority_failure_keeps_its_actual_what_and_why(
    tmp_path: Path,
) -> None:
    root, stored, candidate = _repository(tmp_path)
    stored = replace(
        stored,
        values=(replace(stored.values[0], authority="notes/missing.md#Value"),),
    )
    selected = DeliveryContinuationRunner().selected_authority(root, stored, 1)
    assert isinstance(selected, DeliveryOutcome), selected
    assert selected.failure is not None

    result = _relation(root, stored, candidate)

    assert isinstance(result, OwnedBytesUnobservable), result
    assert selected.failure.what in result.what
    assert selected.failure.why in result.why


def test_empty_owned_union_is_unobservable_not_vacuously_covered(
    tmp_path: Path,
) -> None:
    root, stored, candidate = _repository(tmp_path)
    stored = replace(stored, values=())

    result = _relation(root, stored, candidate)

    assert isinstance(result, OwnedBytesUnobservable), result
    assert result.what and result.why
    assert "owned" in f"{result.what} {result.why}".lower()
