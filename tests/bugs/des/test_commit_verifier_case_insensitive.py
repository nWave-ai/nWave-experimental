"""Regression -- ``GitCommitVerifier.verify_commit`` misses a matching commit
when the ``Step-Id:``/``Task-Id:`` trailer casing differs from the exact
search string it builds for ``git log --grep``.

``git log --grep`` defaults to CASE-SENSITIVE matching. The verifier builds
``--grep=Step-Id: {step_id}`` (and, when a feature filter is supplied,
``--grep=Task-Id: {feature_id_filter}``) with no ``-i`` flag
(``src/des/adapters/driven/git/git_commit_verifier.py`` around line 57). A
commit whose trailer is written with different letter-casing (e.g.
``step-id: 42-01`` or ``STEP-ID: 42-01`` instead of exactly ``Step-Id:
42-01``) is therefore invisible to the search: ``verify_commit`` reports
``verified=False`` even though a genuinely matching commit exists in
history.

Driving surface (Layer 3 composition, real git subprocess): ``verify_commit``
is the composition-root driven-port adapter method itself -- the smallest
unit that owns the ``git log --grep`` command construction under test. Git
operations are real (subprocess against a temp repo), mirroring the fixture
idiom in ``tests/des/acceptance/test_git_commit_verification.py``.
"""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

from des.adapters.driven.git.git_commit_verifier import GitCommitVerifier


def _init_git_repo(path: Path) -> None:
    """Initialize a git repository with minimal configuration and one commit."""
    subprocess.run(["git", "init"], cwd=str(path), capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    initial_file = path / ".gitkeep"
    initial_file.write_text("")
    subprocess.run(
        ["git", "add", ".gitkeep"], cwd=str(path), capture_output=True, check=True
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )


def _commit_with_trailer(path: Path, commit_message: str) -> str:
    """Create a commit with an arbitrary message body and return its hash."""
    change_file = path / f"change-{uuid.uuid4().hex[:8]}.txt"
    change_file.write_text("some content")
    subprocess.run(
        ["git", "add", str(change_file.name)],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", commit_message],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    result = subprocess.run(
        ["git", "log", "--format=%H", "-1"],
        cwd=str(path),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_verify_commit_finds_lowercase_trailer_for_exact_case_search(
    tmp_path: Path,
) -> None:
    """BUG observable: a commit trailer written as ``step-id: 42-01``
    (lowercase) must still be found when searching for ``Step-Id: 42-01``
    (the exact casing the production code always searches for). Today this
    fails because ``git log --grep`` is case-sensitive with no ``-i`` flag.
    """
    _init_git_repo(tmp_path)
    _commit_with_trailer(
        tmp_path,
        "Implement feature\n\nstep-id: 42-01\ntask-id: test-project",
    )

    verifier = GitCommitVerifier()
    result = verifier.verify_commit(
        step_id="42-01", cwd=str(tmp_path), feature_id_filter="test-project"
    )

    assert result.verified is True, (
        f"Expected the lowercase-trailer commit to be found case-insensitively, "
        f"got verified=False, error_reason={result.error_reason!r}"
    )


def test_verify_commit_finds_uppercase_trailer_for_exact_case_search(
    tmp_path: Path,
) -> None:
    """BUG observable variant: fully upper-cased trailer ``STEP-ID: 42-01``
    must also be found when searching for ``Step-Id: 42-01``.
    """
    _init_git_repo(tmp_path)
    _commit_with_trailer(tmp_path, "Implement feature\n\nSTEP-ID: 42-01")

    verifier = GitCommitVerifier()
    result = verifier.verify_commit(step_id="42-01", cwd=str(tmp_path))

    assert result.verified is True, (
        f"Expected the uppercase-trailer commit to be found case-insensitively, "
        f"got verified=False, error_reason={result.error_reason!r}"
    )


def test_verify_commit_rejects_wrong_step_id_even_case_insensitively(
    tmp_path: Path,
) -> None:
    """Negative/safety oracle: case-insensitive matching must NOT become
    over-permissive. A commit carrying trailer ``Step-Id: 99-99`` must
    still be reported as NOT FOUND when searching for a genuinely different
    step id ``42-01`` -- the case-insensitive fix must not accidentally
    match by prefix or blur step-id boundaries. This case passes both
    before and after the fix; it pins behavior the fix must preserve.
    """
    _init_git_repo(tmp_path)
    _commit_with_trailer(tmp_path, "Implement feature\n\nStep-Id: 99-99")

    verifier = GitCommitVerifier()
    result = verifier.verify_commit(step_id="42-01", cwd=str(tmp_path))

    assert result.verified is False, (
        "A commit with an unrelated Step-Id must not be matched by a "
        "case-insensitive search for a different step id"
    )
    assert "42-01" in (result.error_reason or "")
