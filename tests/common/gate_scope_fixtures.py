"""Shared ``Gate-Scope:`` trailer fixture helpers (fix-null-gate-scope-exit-gate).

``des verify-slice-commit``'s ``_run_verify_then_record`` carries a
seal-integrity leg: before it appends ``SliceCommitVerified``, the target
commit's ``Gate-Scope:`` trailer must be present and a well-formed,
non-placeholder 64-hex digest (``src/des/cli/verify_slice_commit_completeness.py``).
No real ``des commit-slice`` commit is ever trailer-less -- it always stamps
one (the all-zero placeholder first, a real digest after the amend) -- so any
test fixture whose commit is meant to reach the verified/exit-0 outcome must
carry a REAL, well-formed trailer too. This module is the single reusable
pair every such fixture calls, extracted from the identical local copies
proven in ``test_slice_commit_refused_names_how.py`` and
``test_verify_slice_commit_pytest_regression_behavioral_attestation.py``.

Fixture-setup realism only -- these helpers never touch an assertion.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from des.cli.run_contract_gate import main as _run_contract_gate_main
from tests.common.in_process_cli import run_cli_in_process


def _git(repo: Path, *args: str) -> str:
    """Run a git command in ``repo`` (raises on non-zero), return stdout."""
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def committed_scope_digest(repo: Path) -> str:
    """Return the REAL, correctly-computed committed-scope digest of ``repo``
    at HEAD -- derived through the shipped CLI (``--committed-scope-digest``),
    never fabricated.
    """
    exit_code, stdout, _stderr = run_cli_in_process(
        ["--repo", str(repo), "--committed-scope-digest"],
        cwd=repo,
        main=_run_contract_gate_main,
    )
    for line in (ln.strip() for ln in stdout.splitlines()):
        if len(line) == 64 and all(c in "0123456789abcdef" for c in line):
            return line
    raise AssertionError(
        "could not derive a committed-scope digest to build the trailer "
        f"(exit {exit_code}); stdout={stdout!r}"
    )


def stamp_genuine_gate_scope_trailer(repo: Path) -> None:
    """Reseal HEAD with a REAL, well-formed ``Gate-Scope:`` trailer.

    fix-null-gate-scope-exit-gate: production ``des commit-slice`` ALWAYS
    stamps a ``Gate-Scope:`` trailer -- a trailer-less fixture commit does
    not occur in production, and the exit gate's seal-integrity leg
    correctly refuses it. Fixture-realism fix ONLY -- no assertion changed.
    """
    digest = committed_scope_digest(repo)
    original = _git(repo, "log", "-1", "--format=%B", "HEAD").strip()
    _git(
        repo,
        "commit",
        "-q",
        "--amend",
        "-m",
        f"{original}\n\nGate-Scope: {digest}",
    )
