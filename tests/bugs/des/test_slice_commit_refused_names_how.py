"""Regression (GDP-3/GDP-4): `des verify-slice-commit`'s `SliceCommitRefused`
verdict must carry a `how` field naming the producing tool, not ONLY
``{event, refused_half, slice_ids, commit, ..., error}`` (WHAT+WHY, no HOW).

Charter: ``docs/product/expectations/fix-slice-commit-refused-names-how/
the-slice-commit-refusal-names-how-to-fix.md``.

Found in ``src/des/cli/verify_slice_commit_completeness.py``
``_run_verify_then_record()``:
  * ``:516`` -- the E1 refusal (the slice commit omits one or more of the
    slice's declared ``.feature`` AT files) emits
    ``{event, refused_half, slice_ids, commit, missing_feature_files_by_slice,
    error}`` with NO ``how``.
  * ``:553`` -- the E2 refusal (a slice failed the feature-scoped contract
    gate) emits ``{event, refused_half, slice_ids, commit, failed_slice,
    contract_gate_exit_code, error}``, likewise with no ``how``.

The fix direction (charter, NOT implemented here): E1 -> HOW routes to
``des commit-slice`` (stages + lands the missing ``.feature`` files into the
slice commit); E2 -> HOW routes to greening the failing feature-scoped ATs
then re-committing through ``des commit-slice`` (inspect with
``run_contract_gate --repo .``).

Scope: this AT pins the E1 path only (the easiest reliable reject to drive --
mirrors the proven sibling fixture shape,
``tests/bugs/des/test_slice_at_completeness_incomplete_names_how.py``). E2
carries the identical defect shape (no ``how``) and is fixed by the same code
change, but is not independently pinned by a second AT here (dispatch scope:
1 positive + 1 negative).

CRITICAL CONSTRAINT (preserved, do NOT change): the check stays intact -- a
deficient slice commit is STILL refused (exit 1), no ``SliceCommitVerified``
record is minted. A verified slice commit still clears (exit 0) with no
spurious ``how``.

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process default):
the REAL ``des.cli.verify_slice_commit_completeness.main()`` CLI driver,
captured via ``capsys`` -- mirrors the sibling regression ATs
(``test_slice_at_completeness_incomplete_names_how.py``,
``test_run_contract_gate_scope_unverified_names_how.py``), the GDP-3/GDP-4
pattern this one follows.

Fixtures:
  * POSITIVE -- a real tmp git repo. A commit carries a ``Slice-Id:``
    trailer but the slice's ``@feature-{feature_id}``/``@slice-NN``-tagged
    ``.feature`` AT file is authored on disk and deliberately never
    staged/committed -- the RCA Branch-A defect this gate exists to catch
    (mirrors ``_make_repo_missing_feature_file`` in the sibling AT).
  * NEGATIVE -- mirrors the proven GREEN precedent
    ``tests/des/integration/test_verify_slice_commit_examine_gate.py::
    test_verify_slice_commit_unarmed_without_charter``: E2 (the
    feature-scoped contract-gate subprocess) is monkeypatched to PASS so the
    negative isolates the E1/E3 legs without spawning the real contract
    gate; the slice's ``.feature`` file IS committed (E1 clears); no charter
    exists under ``docs/product/expectations/{feature_id}/`` so E3 is
    UNARMED (green-to-green suffices) -- the commit reaches the true
    ``SliceCommitVerified`` exit-0 path.

fix-null-gate-scope-exit-gate fixture-realism update: `des verify-slice-
commit`'s `_run_verify_then_record` now carries a seal-integrity leg -- a
slice commit whose `Gate-Scope:` trailer is absent/malformed/the all-zero
placeholder is refused (`SliceCommitIndeterminate reason=gate_scope_
unsealed`), never fabricated into `SliceCommitVerified`. No real `des
commit-slice` ever produces a trailer-less commit, so
`_make_repo_fully_verified` (the NEGATIVE fixture, the only caller reaching
the VERIFIED exit-0 path) now also stamps a REAL, well-formed `Gate-Scope:`
trailer -- derived through the shipped CLI (`run_contract_gate
--committed-scope-digest`), never fabricated -- via
`_stamp_genuine_gate_scope_trailer`, mirroring the pattern in
`test_run_contract_gate_scope_unverified_names_how.py`. The POSITIVE fixture
(`_make_repo_missing_feature_file`) refuses at E1, well before the
seal-integrity leg is ever reached, so it is untouched.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from des.cli import verify_slice_commit_completeness as vscc
from tests.common.gate_scope_fixtures import (
    stamp_genuine_gate_scope_trailer as _stamp_genuine_gate_scope_trailer,
)


_FEATURE_ID = "slice-commit-refused-how-fixture"
_SLICE_ID = "slice-01"

_FEATURE_FILE_TEXT = (
    f"@feature-{_FEATURE_ID}\n"
    "Feature: fixture feature\n\n"
    f"  @{_SLICE_ID}\n"
    "  Scenario: fixture scenario\n"
    "    Given a fixture precondition\n"
    "    When the fixture action occurs\n"
    "    Then the fixture outcome holds\n"
)

_FEATURE_REL_PATH = "tests/acceptance/fixture_slice.feature"


def _git(repo: Path, *args: str) -> str:
    """Run a git command in ``repo`` (raises on non-zero), return stdout."""
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _git_init(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "atdd@nwave.ai")
    _git(repo, "config", "user.name", "atdd")


def _feature_path(repo: Path) -> Path:
    path = repo / _FEATURE_REL_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _make_repo_missing_feature_file(tmp_path: Path) -> tuple[Path, str]:
    """A slice commit carrying a ``Slice-Id:`` trailer that OMITS the
    slice's declared ``.feature`` AT file.

    The commit's message carries the trailer, but the ``.feature`` file is
    written to disk -- found by the ``@feature-{feature_id}`` working-tree
    walk -- AFTER the commit and deliberately never staged: authored, never
    persisted (RCA Branch-A).
    """
    repo = tmp_path / "e1_refused_repo"
    _git_init(repo)
    (repo / "README.md").write_text("fixture repo\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(
        repo,
        "commit",
        "-qm",
        f"feat(slice): behaviour\n\nSlice-Id: {_SLICE_ID}",
    )
    commit = _git(repo, "rev-parse", "HEAD").strip()

    _feature_path(repo).write_text(_FEATURE_FILE_TEXT, encoding="utf-8")
    # Deliberately NOT git-added / committed.
    return repo, commit


def _make_repo_fully_verified(tmp_path: Path) -> Path:
    """A slice commit that carries its ``.feature`` AT file, with no charter
    (E3 unarmed) -- reaches the true ``SliceCommitVerified`` exit-0 path once
    E2 is monkeypatched to PASS (mirrors
    ``test_verify_slice_commit_unarmed_without_charter``). Also carries a
    REAL, well-formed ``Gate-Scope:`` trailer (fix-null-gate-scope-exit-gate
    fixture-realism update) -- no real ``des commit-slice`` commit is ever
    trailer-less, and the exit gate's seal-integrity leg now refuses one.
    """
    repo = tmp_path / "verified_repo"
    _git_init(repo)
    _feature_path(repo).write_text(_FEATURE_FILE_TEXT, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(
        repo,
        "commit",
        "-qm",
        f"feat(slice): behaviour\n\nSlice-Id: {_SLICE_ID}",
    )
    _stamp_genuine_gate_scope_trailer(repo)
    return repo


def _run_verify_slice_commit(
    repo: Path, commit: str, capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, object]]:
    """Drive the REAL ``des verify-slice-commit`` CLI (``main()``) in-process
    with ``--feature-id`` (the verify-then-record exit gate), capturing its
    single-line JSON payload via ``capsys``. Returns the LAST JSON line
    (the verdict event; the human-readable summary line is not JSON and is
    skipped by the ``{``-prefix filter).
    """
    exit_code = vscc.main(
        [
            "--repo",
            str(repo),
            "--commit",
            commit,
            "--feature-id",
            _FEATURE_ID,
        ]
    )
    stdout = capsys.readouterr().out
    lines = [ln for ln in stdout.splitlines() if ln.strip().startswith("{")]
    assert lines, f"expected a JSON payload line on stdout, got: {stdout!r}"
    payload: dict[str, object] = json.loads(lines[-1])
    return exit_code, payload


# ===========================================================================
# POSITIVE AT -- active-RED today
# ===========================================================================


def test_e1_refused_verdict_names_a_how_routing_to_the_producing_tool(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A slice commit missing its declared ``.feature`` AT file is REJECTED
    (floor intact -- exit 1, ``event='SliceCommitRefused'``,
    ``refused_half='E1'``) -- already true today. The payload must ALSO
    carry a ``how`` field routing to the producing tool that lands the
    missing file into the slice commit (``des commit-slice``) -- this is
    MISSING today (RED for the right reason: a semantic assertion on the
    absent ``how``, not a crash or collection error).
    """
    repo, commit = _make_repo_missing_feature_file(tmp_path)

    exit_code, payload = _run_verify_slice_commit(repo, commit, capsys)

    # Floor intact -- already passing today, must stay true after the fix.
    assert exit_code == 1, (
        "a slice commit missing a declared .feature AT file must still be "
        f"REFUSED (exit 1) -- got exit_code={exit_code}; payload={payload!r}"
    )
    assert payload.get("event") == "SliceCommitRefused", payload
    assert payload.get("refused_half") == "E1", payload
    missing = payload.get("missing_feature_files_by_slice")
    assert missing, f"expected a non-empty missing map, got payload={payload!r}"

    # HOW -- MISSING today. verify_slice_commit_completeness.py:516 emits
    # only {event, refused_half, slice_ids, commit,
    # missing_feature_files_by_slice, error}; no `how` key exists.
    how = payload.get("how")
    assert how, (
        "the E1 'SliceCommitRefused' verdict must carry a `how` field "
        "routing to the producing tool that lands the missing .feature "
        f"files into the slice commit -- payload carries no `how`: {payload!r}"
    )
    assert isinstance(how, str) and "commit-slice" in how, (
        "the `how` for an E1 refusal must route to `des commit-slice` "
        f"(stages + lands the missing .feature files) -- got how={how!r}"
    )


# ===========================================================================
# NEGATIVE AT -- control, green today AND after the fix
# ===========================================================================


@pytest.mark.negative_at
def test_verified_verdict_never_carries_a_how(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A slice commit that carries its declared ``.feature`` AT file (E1
    clears), whose contract gate passes (E2 monkeypatched to PASS -- mirrors
    the proven precedent ``test_verify_slice_commit_unarmed_without_charter``,
    isolating this AT from spawning a real contract-gate subprocess), and
    that carries no examine charter (E3 unarmed) reaches the true
    ``SliceCommitVerified`` exit-0 path with NO spurious ``how`` in the
    payload -- the ``how`` remediation belongs only to the reject path,
    never leaking into a passing verdict. Must stay green both BEFORE and
    AFTER the fix.
    """
    monkeypatch.setattr(vscc, "_run_contract_gate", lambda *a, **k: 0)
    repo = _make_repo_fully_verified(tmp_path)

    exit_code, payload = _run_verify_slice_commit(repo, "HEAD", capsys)

    assert exit_code == 0, (
        "a slice commit carrying every declared .feature AT file, a passing "
        "contract gate, and no examine charter must clear (exit 0) -- got "
        f"exit_code={exit_code}; payload={payload!r}"
    )
    assert payload.get("event") == "SliceCommitVerified", payload
    assert "how" not in payload, (
        f"a 'SliceCommitVerified' verdict must never carry a spurious `how` "
        f"field: {payload!r}"
    )
