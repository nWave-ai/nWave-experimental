"""Regression (GDP-3/GDP-4): `run_contract_gate --verify-gate-scope`'s
``GateScopeUnverified`` rejection must carry a ``how`` field naming the
producing tool, not ONLY ``{event, commit, reason, error}`` (WHAT+WHY, no HOW).

Charter: ``docs/product/expectations/fix-run-contract-gate-scope-how/
the-gate-scope-unverified-reject-names-how.md``.

Found in ``src/des/cli/run_contract_gate.py`` `_mode_verify_gate_scope`:
  * ``:1226`` -- ``reason="absent"`` (commit carries no ``Gate-Scope:``
    trailer) emits ``{event, commit, reason, error}`` with no ``how``.
  * ``:1240`` -- ``reason="mismatch"`` (declared digest != a fresh
    ``--collect-only`` digest) emits the same shape, no ``how``.

The fix direction (charter, NOT implemented here): ``absent`` -> HOW routes to
``des commit-slice`` (stamps the ``Gate-Scope:`` trailer mechanically);
``mismatch`` -> HOW routes to ``run_contract_gate --repo .`` (re-run the FULL
gate so the terminating run covers the whole contract, then re-commit).

Scope: the positive AT below pins the ``absent`` reason (``:1226``) -- the
``mismatch`` reason (``:1240``) carries the IDENTICAL defect shape (no ``how``)
and is fixed by the same code change, but is not independently pinned by a
second AT here (dispatch scope: 1 positive + 1 negative).

CRITICAL CONSTRAINT (preserved, do NOT change): the check stays intact -- an
unverified gate scope is STILL rejected, exit 1. The positive AT below pins
``exit_code == 1`` for the reject path; a fix that flips the exit code must be
rejected.

Driving surface (Mandate-13 driving-port-only, Layer 3 subprocess-in-process
default): the REAL ``des.cli.run_contract_gate.main()`` CLI driver, called via
``run_cli_in_process`` (no interpreter fork) -- the SAME entry point the
G_COMMIT exit-gate hook invokes as ``--verify-gate-scope``. No direct import of
``_mode_verify_gate_scope`` / ``extract_gate_scope`` -- only the CLI edge.

Fixture shape mirrored from the proven, GREEN precedent
``tests/des/acceptance/fix_gcommit_exit_gate_scoping/steps/composition_slice_02.py``
(``GcommitVerifyComposition``): a real git repo, a committed contract suite, a
HEAD commit whose message carries (or omits) a ``Gate-Scope:`` trailer built
from the slice-01 ``--committed-scope-digest`` mode.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

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


def _write_committed_contract(root: Path) -> None:
    """Write a minimal, marker-tagged contract suite into ``root``."""
    (root / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\nmarkers = ["unit", "integration", "acceptance"]\n'
    )
    (root / "test_committed_contract.py").write_text(
        "import pytest\n\n"
        "@pytest.mark.unit\ndef test_a():\n    assert True\n\n"
        "@pytest.mark.acceptance\ndef test_b():\n    assert True\n"
    )


def _git_init_commit(root: Path, message: str) -> None:
    """Init a repo in ``root`` and commit everything with ``message``."""
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "atdd@nwave.ai")
    _git(root, "config", "user.name", "atdd")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", message)


def _committed_scope_digest(root: Path) -> str:
    """Return the slice-01 committed-scope digest of ``root`` at HEAD.

    Driven through the shipped ``--committed-scope-digest`` CLI mode
    (in-process), not an import of the digest function itself.
    """
    exit_code, stdout, _stderr = run_cli_in_process(
        ["--repo", str(root), "--committed-scope-digest"],
        cwd=root,
        main=_run_contract_gate_main,
    )
    for line in (ln.strip() for ln in stdout.splitlines()):
        if len(line) == 64 and all(c in "0123456789abcdef" for c in line):
            return line
    raise AssertionError(
        "could not derive a committed-scope digest to build the trailer "
        f"(exit {exit_code}); stdout={stdout!r}"
    )


def _amend_with_trailer(root: Path, digest: str) -> None:
    """Amend HEAD so its message carries the ``Gate-Scope:`` trailer."""
    original = _git(root, "log", "-1", "--format=%B", "HEAD").strip()
    _git(
        root,
        "commit",
        "-q",
        "--amend",
        "-m",
        f"{original}\n\nGate-Scope: {digest}",
    )


def _make_commit_with_no_trailer(root: Path) -> str:
    """A HEAD commit whose message carries NO ``Gate-Scope:`` trailer (absent)."""
    _write_committed_contract(root)
    _git_init_commit(root, "committed contract suite, no trailer")
    return _git(root, "rev-parse", "HEAD").strip()


def _make_commit_with_matching_trailer(root: Path) -> str:
    """A HEAD commit whose trailer pins its OWN committed-scope digest (VERIFIED)."""
    _write_committed_contract(root)
    _git_init_commit(root, "committed contract suite, matching trailer")
    _amend_with_trailer(root, _committed_scope_digest(root))
    return _git(root, "rev-parse", "HEAD").strip()


def _run_verify_gate_scope(repo: Path, commit: str) -> tuple[int, str, str]:
    """Drive the REAL ``run_contract_gate --verify-gate-scope`` CLI, in-process."""
    return run_cli_in_process(
        ["--repo", str(repo), "--commit", commit, "--verify-gate-scope"],
        cwd=repo,
        main=_run_contract_gate_main,
    )


def _first_event(combined: str, event_name: str) -> dict[str, Any]:
    """Parse the first single-line JSON event whose ``event`` field matches."""
    for line in combined.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("event") == event_name:
            return payload
    raise AssertionError(
        f"no {event_name!r} JSON event found in the verify output; "
        f"combined stream was:\n{combined}"
    )


# ===========================================================================
# POSITIVE AT -- active-RED today
# ===========================================================================


def test_gate_scope_unverified_absent_reason_names_a_how(tmp_path: Path) -> None:
    """A commit with NO ``Gate-Scope:`` trailer is REJECTED (floor intact,
    exit 1, ``reason="absent"``) -- already true today. The payload must ALSO
    carry a ``how`` field routing to the producing tool that stamps the
    trailer mechanically (``des commit-slice``) -- this is MISSING today
    (RED for the right reason: a semantic assertion on the absent ``how``,
    not a crash / collection error).
    """
    repo = tmp_path / "absent_trailer_repo"
    repo.mkdir()
    commit = _make_commit_with_no_trailer(repo)

    exit_code, stdout, stderr = _run_verify_gate_scope(repo, commit)
    combined = stdout + stderr

    # Floor intact -- already passing today, must stay true after the fix.
    assert exit_code == 1, (
        "a commit with no Gate-Scope: trailer must still be REJECTED "
        f"(exit 1) -- got exit_code={exit_code}; combined={combined!r}"
    )

    payload = _first_event(combined, "GateScopeUnverified")
    assert payload.get("reason") == "absent", (
        f"expected reason='absent', got {payload.get('reason')!r}: {payload!r}"
    )

    # HOW -- MISSING today. run_contract_gate.py:1226 emits only
    # {event, commit, reason, error}; no `how` key exists in that dict.
    how = payload.get("how")
    assert how, (
        "GateScopeUnverified (reason='absent') must carry a `how` field "
        "routing to the producing tool that stamps the Gate-Scope: trailer "
        f"mechanically -- payload carries no `how`: {payload!r}"
    )
    assert "commit-slice" in how, (
        "the `how` for reason='absent' must route to `des commit-slice` "
        f"(stamps the Gate-Scope: trailer mechanically) -- got how={how!r}"
    )


# ===========================================================================
# NEGATIVE AT -- control, green today AND after the fix
# ===========================================================================


@pytest.mark.negative_at
def test_gate_scope_matching_trailer_never_emits_a_how(tmp_path: Path) -> None:
    """A commit whose Gate-Scope digest MATCHES a fresh run is VERIFIED (no
    rejection, ``GateScopeVerified``) and carries no spurious ``how`` -- the
    ``how`` field belongs only to the reject path, never leaking into a
    passing verdict. This must stay green both BEFORE and AFTER the fix.
    """
    repo = tmp_path / "matching_trailer_repo"
    repo.mkdir()
    commit = _make_commit_with_matching_trailer(repo)

    exit_code, stdout, stderr = _run_verify_gate_scope(repo, commit)
    combined = stdout + stderr

    assert exit_code == 0, (
        "a commit whose Gate-Scope: digest matches a fresh run must be "
        f"VERIFIED (exit 0) -- got exit_code={exit_code}; combined={combined!r}"
    )

    payload = _first_event(combined, "GateScopeVerified")
    assert "how" not in payload, (
        f"a VERIFIED verdict must never carry a spurious `how` field: {payload!r}"
    )
    assert "GateScopeUnverified" not in combined, (
        f"a matching commit must not emit GateScopeUnverified at all: {combined!r}"
    )
