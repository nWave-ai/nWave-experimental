"""Regression (#59): ``des commit-slice`` re-verifies EARLIER shipped slices
via a NAMING-CONVENTION GLOB instead of the file that slice actually declared
and passed at its own commit time.

RCA (Rex, CONFIRMED): ``_shipped_and_entering_regression_files``
(``verify_slice_commit_completeness.py:670-708``) resolves every SHIPPED
slice's regression file via ``_regression_file_glob_candidates`` --
``tests/**/{feature_dir}/test_{slice_us}_*.py`` -- a pure naming-convention
guess. The ``SliceCommitVerified`` ledger record
(``_append_slice_commit_verified``, ``verify_slice_commit_completeness.py:
852-883`` -> ``AtCompletionLedger.append_gate_event``) never persists a
``regression_test_file`` field, so there is no STORED value to read instead.
When a shipped slice's regression file happens to live somewhere the
convention does not predict (e.g. ``tests/bugs/repro/test_weird_name.py``
instead of ``tests/**/{feature_dir}/test_slice_01_*.py``), the glob resolves
to ZERO candidates -- ``_run_regression_gate_shipped_and_entering`` treats
that as ``unresolved`` and degrades the ENTIRE run to
``SliceCommitIndeterminate`` (reason ``shipped_regression_file_unresolvable``,
``verify_slice_commit_completeness.py:750-765``), even though the earlier
slice genuinely shipped and passed.

Empirically verified (2026-07-18, scratch git repos, in-process
``des.cli.commit_slice.main``): committing slice-01 with a non-convention
``--regression-test-file`` seals ``SliceCommitVerified`` cleanly. Committing
slice-02 immediately afterward -- ANY ``--at-kind pytest-regression`` slice,
regardless of its OWN file's name -- lands its commit (Step 2 already ran
before the degrade is discovered) but seals ``verified: false`` / exit 1,
with TWO ``SliceCommitIndeterminate`` ledger records (one from the Step-1.5
shadow-commit preflight, one from the Step-6 post-commit fold-in -- both
independently hit the same unresolved-glob path), reason
``shipped_regression_file_unresolvable`` on both. ``slice-02`` never earns a
``SliceCommitVerified`` record even though its OWN regression test passed.

Charter: docs/product/expectations/fix-commit-slice-reverify-uses-stored-file/
later-slice-commit-honors-earlier-slice-declared-test.md

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process): the REAL
``des.cli.commit_slice.main()`` CLI driver, in-process with ``capsys`` --
verbatim shape reused from
``tests/bugs/des/test_commit_slice_pytest_regression_ignores_cargo_digest_route.py``.

GIT SAFETY: every git call below targets the DISPOSABLE ``tmp_path`` fixture
only (``cwd``/``--repo`` always the scratch fixture, never the real project
repo). No git WRITE ever touches this repository.

THIS FILE IS TEST-ONLY. No production code is touched by this authoring pass.
A crafter fixes ``_shipped_and_entering_regression_files`` (or the
``SliceCommitVerified`` record shape it should read from) against this test;
this test must NEVER be weakened or skipped to reach GREEN.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.commit_slice import main as commit_slice_main
from des.cli.verify_slice_commit_completeness import canonical_regression_test_path


# ---------------------------------------------------------------------------
# fixture builders (disposable git repos; every git write targets `root` only)
# ---------------------------------------------------------------------------


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _init_scratch_repo(root: Path) -> Path:
    """A minimal, disposable git repo -- baseline commit only."""
    fixture = root / "repo"
    fixture.mkdir(parents=True)
    (fixture / "README.md").write_text("# scratch fixture\n", encoding="utf-8")
    _git(fixture, "init", "-q")
    _git(fixture, "config", "user.email", "atdd@nwave.ai")
    _git(fixture, "config", "user.name", "atdd")
    _git(fixture, "add", "-A")
    _git(fixture, "commit", "-q", "-m", "chore: scratch fixture baseline")
    return fixture


def _write_trivial_regression_file(
    fixture: Path, rel_path: str, feature_id: str, slice_id: str, marker: int
) -> None:
    """A self-contained, tagged, trivially-passing pytest regression file."""
    target = fixture / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"# @feature-{feature_id}\n# @{slice_id}\n"
        f"def test_{slice_id.replace('-', '_')}_thing():\n"
        f"    assert {marker} + {marker} == {marker * 2}\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# observables
# ---------------------------------------------------------------------------


def _run_commit_slice(
    repo: Path, argv_tail: list[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, str]:
    """Drive the REAL ``des commit-slice`` CLI (``main()``) in-process,
    returning ``(exit_code, combined_captured_output)``."""
    exit_code = commit_slice_main(["--repo", str(repo), *argv_tail])
    captured = capsys.readouterr()
    return exit_code, captured.out + "\n" + captured.err


def _behavioral_argv(
    feature_id: str, slice_id: str, regression_test_file: str, *, message: str
) -> list[str]:
    return [
        "--feature-id",
        feature_id,
        "--slice-id",
        slice_id,
        "--all",
        "--message",
        message,
        "--at-kind",
        "pytest-regression",
        "--regression-test-file",
        regression_test_file,
    ]


def _diag(exit_code: int, output: str) -> str:
    return f"\nexit_code={exit_code!r}\noutput={output!r}"


def _indeterminate_reasons(feature_id: str, repo: Path, slice_id: str) -> list[object]:
    """Every recorded ``SliceCommitIndeterminate`` ledger ``reason`` for ``slice_id``."""
    records = AtCompletionLedger(feature_id, repo).read_records(
        slice_id=slice_id, event_type="SliceCommitIndeterminate"
    )
    return [record.get("reason") for record in records]


# ===========================================================================
# Scenario 1 -- RED-today core: a LATER slice's commit must honor the
# EARLIER shipped slice's OWN declared regression file, not a
# naming-convention guess.
# ===========================================================================


def test_slice_two_commit_honors_slice_one_stored_regression_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Slice-01 ships with a NON-convention-named ``--regression-test-file``
    (neither its directory nor its filename matches
    ``tests/**/{feature_dir}/test_{slice_id}_*.py``). Committing slice-02
    afterward must still reach ``SliceCommitVerified`` with a real,
    non-vacuous Gate-Scope digest -- the re-check of slice-01 performed as
    part of slice-02's commit must use slice-01's own STORED regression
    file, never a naming-convention guess that finds nothing.

    Active-RED at HEAD (empirically confirmed): slice-02's commit LANDS
    (Step 2 already ran) but seals with ``verified: false`` / exit 1 --
    ``_shipped_and_entering_regression_files`` globs
    ``tests/**/fix_commit_slice_reverify/test_slice_01_*.py``, finds ZERO
    matches for slice-01's non-convention file, and degrades the ENTIRE run
    to ``SliceCommitIndeterminate`` (reason
    ``shipped_regression_file_unresolvable``) -- twice (once from the
    Step-1.5 shadow-commit preflight, once from the Step-6 post-commit
    fold-in) -- even though slice-01 genuinely shipped and passed.
    """
    fixture = _init_scratch_repo(tmp_path)
    feature_id = "fix-commit-slice-reverify"

    # slice-01: a regression file whose path matches NEITHER the directory
    # NOR the filename half of the naming convention.
    _write_trivial_regression_file(
        fixture, "tests/bugs/repro/test_weird_name.py", feature_id, "slice-01", 1
    )
    exit_code_1, output_1 = _run_commit_slice(
        fixture,
        _behavioral_argv(
            feature_id,
            "slice-01",
            "tests/bugs/repro/test_weird_name.py",
            message="feat(slice): slice-01 ships a non-convention regression file",
        ),
        capsys,
    )
    assert exit_code_1 == 0, (
        "reproduction precondition: slice-01 (a non-convention-named "
        "regression file) must ship cleanly." + _diag(exit_code_1, output_1)
    )
    assert "slice-01" in AtCompletionLedger(feature_id, fixture).verified_slices(), (
        "reproduction precondition: slice-01 must earn a SliceCommitVerified "
        "ledger record." + _diag(exit_code_1, output_1)
    )

    # slice-02: its OWN independent regression file, genuinely passing.
    _write_trivial_regression_file(
        fixture,
        "tests/bugs/repro/test_slice_02_behaviour.py",
        feature_id,
        "slice-02",
        2,
    )
    exit_code_2, output_2 = _run_commit_slice(
        fixture,
        _behavioral_argv(
            feature_id,
            "slice-02",
            "tests/bugs/repro/test_slice_02_behaviour.py",
            message="feat(slice): slice-02 lands after slice-01's non-convention file",
        ),
        capsys,
    )

    assert exit_code_2 == 0, (
        "committing slice-02 must clear des commit-slice end-to-end -- the "
        "re-check of slice-01 performed as part of slice-02's commit must "
        "use slice-01's own STORED --regression-test-file, never a "
        "naming-convention glob that finds nothing for a legitimately "
        "non-convention-named file. At HEAD this seals verified: false / "
        "exit 1, with a SliceCommitIndeterminate ledger record reasoning "
        "'shipped_regression_file_unresolvable' -- slice-01 genuinely "
        "shipped and passed; only its FILE NAME is unconventional."
        + _diag(exit_code_2, output_2)
    )
    verified_slices = AtCompletionLedger(feature_id, fixture).verified_slices()
    assert "slice-02" in verified_slices, (
        "slice-02 must earn a SliceCommitVerified ledger record -- observed "
        f"verified_slices={sorted(verified_slices)!r}." + _diag(exit_code_2, output_2)
    )
    reasons = _indeterminate_reasons(feature_id, fixture, "slice-02")
    assert "shipped_regression_file_unresolvable" not in reasons, (
        "slice-02 must NEVER mint a SliceCommitIndeterminate reasoning "
        "'shipped_regression_file_unresolvable' when slice-01 genuinely "
        f"shipped and passed -- observed ledger reasons={reasons!r}."
        + _diag(exit_code_2, output_2)
    )

    # No fabricated pass: the sealed Gate-Scope digest must be REAL.
    digest_line = next(
        (line for line in output_2.splitlines() if '"event": "SliceCommitted"' in line),
        "",
    )
    assert '"gate_scope_digest"' in digest_line and '"verified": true' in digest_line, (
        "a genuinely sealed slice-02 must carry a SliceCommitted event with "
        f"verified: true and a real gate_scope_digest -- got {digest_line!r}."
        + _diag(exit_code_2, output_2)
    )


# ===========================================================================
# Scenario 2 -- over-correction guard (negative): a shipped slice's
# regression file that is GENUINELY deleted must still degrade LOUD, even at
# a CONVENTION-matching path -- the fix is "use the stored path", never
# "skip the re-check entirely".
# ===========================================================================


@pytest.mark.negative_at
def test_slice_two_commit_still_degrades_when_shipped_file_is_genuinely_deleted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Slice-01 ships with a CONVENTION-matching ``--regression-test-file``
    (so a stored-path fix would resolve it identically to today's glob).
    Before slice-02 commits, slice-01's file is genuinely deleted from the
    working tree. Slice-02's commit must STILL degrade LOUD
    (``SliceCommitIndeterminate``, reason
    ``shipped_regression_file_unresolvable``) -- the fix must never make
    slice-02 silently PASS by skipping or short-circuiting the re-check of
    slice-01. This pins BOTH before and after the fix.
    """
    fixture = _init_scratch_repo(tmp_path)
    feature_id = "fix-commit-slice-reverify-neg"
    slice_one_path = canonical_regression_test_path(feature_id, "slice-01")

    _write_trivial_regression_file(fixture, slice_one_path, feature_id, "slice-01", 1)
    exit_code_1, output_1 = _run_commit_slice(
        fixture,
        _behavioral_argv(
            feature_id,
            "slice-01",
            slice_one_path,
            message="feat(slice): slice-01 ships a convention-named regression file",
        ),
        capsys,
    )
    assert (
        exit_code_1 == 0
        and "slice-01" in AtCompletionLedger(feature_id, fixture).verified_slices()
    ), (
        "reproduction precondition: slice-01 (convention-named) must ship "
        "cleanly." + _diag(exit_code_1, output_1)
    )

    # Genuinely delete the shipped file -- no re-write, no substitute.
    (fixture / slice_one_path).unlink()

    _write_trivial_regression_file(
        fixture,
        "tests/fixture/fix_commit_slice_reverify_neg/test_slice_02_behaviour.py",
        feature_id,
        "slice-02",
        2,
    )
    exit_code_2, output_2 = _run_commit_slice(
        fixture,
        _behavioral_argv(
            feature_id,
            "slice-02",
            "tests/fixture/fix_commit_slice_reverify_neg/test_slice_02_behaviour.py",
            message="feat(slice): slice-02 lands after slice-01's file is deleted",
        ),
        capsys,
    )

    assert exit_code_2 != 0, (
        "slice-02's commit must NOT clear when slice-01's genuinely shipped "
        "regression file no longer exists on the tree -- a fabricated pass "
        "here would mean the fix skipped the re-check entirely instead of "
        "resolving the STORED path and finding it missing."
        + _diag(exit_code_2, output_2)
    )
    verified_slices = AtCompletionLedger(feature_id, fixture).verified_slices()
    assert "slice-02" not in verified_slices, (
        "slice-02 must never earn a SliceCommitVerified record while "
        f"slice-01's declared file is genuinely missing -- observed "
        f"verified_slices={sorted(verified_slices)!r}." + _diag(exit_code_2, output_2)
    )
    reasons = _indeterminate_reasons(feature_id, fixture, "slice-02")
    assert "shipped_regression_file_unresolvable" in reasons, (
        "a genuinely missing shipped regression file must degrade LOUD "
        "naming 'shipped_regression_file_unresolvable' -- observed ledger "
        f"reasons={reasons!r}." + _diag(exit_code_2, output_2)
    )
