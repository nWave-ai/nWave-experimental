"""Unit tests for GitCommittedScopeAdapter's failure handling.

Regression coverage for techdebt.md
`unhandled-exception-oserror-from-subprocess-run-committed-scop`:
``committed_contract_files`` called ``subprocess.run(["git", ...])`` with no
guard against ``OSError``/``subprocess.SubprocessError``. If ``git`` is not on
PATH (or another OS-level spawn failure occurs), the exception used to
propagate uncaught and crash the gate with a traceback instead of degrading
to the port's own ``Indeterminate`` signal (GDP-6: no silent-wrong, but also
no *unguarded* wrong -- a driven-port adapter should be self-protecting).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from des.adapters.driven.git.committed_scope_adapter import GitCommittedScopeAdapter
from des.ports.driven_ports.committed_scope_port import CommittedFileSet, Indeterminate


def test_git_binary_missing_degrades_to_indeterminate_not_a_crash() -> None:
    adapter = GitCommittedScopeAdapter()
    with patch(
        "subprocess.run",
        side_effect=FileNotFoundError("[Errno 2] No such file or directory: 'git'"),
    ):
        result = adapter.committed_contract_files(Path("/repo"), "HEAD")
    assert isinstance(result, Indeterminate)
    assert "git" in result.reason.lower()


def test_nonzero_exit_still_yields_indeterminate() -> None:
    """Unchanged behavior: a clean non-zero exit is still Indeterminate."""
    from unittest.mock import MagicMock

    adapter = GitCommittedScopeAdapter()
    failed = MagicMock()
    failed.returncode = 128
    failed.stdout = ""
    failed.stderr = "fatal: not a git repository\n"
    with patch("subprocess.run", return_value=failed):
        result = adapter.committed_contract_files(Path("/repo"), "HEAD")
    assert isinstance(result, Indeterminate)


def test_successful_listing_still_returns_committed_file_set() -> None:
    """Unchanged behavior: a clean success path is unaffected by the guard."""
    from unittest.mock import MagicMock

    adapter = GitCommittedScopeAdapter()
    ok = MagicMock()
    ok.returncode = 0
    ok.stdout = "tests/des/unit/test_foo.py\nsrc/des/domain/foo.py\n"
    ok.stderr = ""
    with patch("subprocess.run", return_value=ok):
        result = adapter.committed_contract_files(Path("/repo"), "HEAD")
    assert isinstance(result, CommittedFileSet)
    assert result.paths == ("tests/des/unit/test_foo.py",)
