"""Regression (RCA confirmed independently by two lanes and re-reproduced):
`src/des/cli/verify_slice_commit_completeness.py:500` has `except GateError:`
inside `_is_at_exempt_lane` (defined at `:478`) -- but `GateError` is NOT
among the names imported at `:80-84`
(`from des.cli.carpaccio_format import (_feature_tag_files,
_lane_profile_for_slice, parse_slice_plan)`). `GateError` is defined at
`src/des/cli/carpaccio_format.py:118`.

Consequence: `parse_slice_plan` raises `GateError` (exit 1,
`SlicePlanSectionMissing`) whenever the feature-delta carries no
`[REF] Slice Plan` section. Evaluating the `except GateError:` clause then
raises `NameError: name 'GateError' is not defined` -- an UNHANDLED crash
replacing the graceful degrade-to-``False`` that commit ``9b1d9fe63``
("degrade gracefully when a feature-delta has no Slice Plan") intended. This
hits exactly the case that commit meant to cure: every feature-delta without
a `[REF] Slice Plan` section -- i.e. every ``/nw-bugfix`` lane -- once its
commit reaches a `des verify-slice-commit`/`des commit-slice` invocation.
``ruff check --select F821`` also flags the bare name.

Verbatim reproduction (this worktree, in-process, no CLI subprocess):

    _is_at_exempt_lane(repo, "fix-demo", "slice-01") on a feature-delta with
    no Slice Plan section
    -> REPRODUCED NameError: name 'GateError' is not defined

`_is_at_exempt_lane` is reached UNCONDITIONALLY, once per listed slice, in
`_run_verify_checks`'s E2 loop (`:1712-1713`) -- so any
`des verify-slice-commit --feature-id ...` call against a feature-delta
lacking a `[REF] Slice Plan` section crashes with an unhandled `NameError`
before it can emit ANY verdict, in place of the intended
"not exempt -- proceed normally" (``False``) degrade.

THE FIX (crafter's job, NOT implemented by this AT -- test-authoring only,
zero ``src/`` edits): add ``GateError`` to the existing import tuple at
`carpaccio_format.py` lines 80-84.

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process): the REAL
``des.cli.verify_slice_commit_completeness.main()`` CLI driver, in-process
with ``capsys`` -- the outermost practical surface (chosen over
``des.cli.commit_slice.main()``: that CLI also composes this exact same
``_run_verify_checks`` preflight, but additionally requires staging/gitlint/
``--all`` machinery this defect has nothing to do with). Fixture shape
verbatim-reused from this directory's own precedent,
``test_verify_slice_commit_pytest_regression_behavioral_attestation.py``
(git-init + head-tagged regression file + ``Slice-Id:`` trailer +
``stamp_genuine_gate_scope_trailer``) and
``test_prefactoring_exempt_shipped_slice_unblocks_commit.py`` (the
``[REF] Slice Plan`` table writer, for the negative oracle below).

GIT SAFETY: every git call below targets the DISPOSABLE ``tmp_path`` fixture
only (``--repo`` always the scratch fixture, never the real project repo).
No git WRITE ever touches this repository.

THIS FILE IS TEST-ONLY. No production code is touched by this authoring
pass. A crafter fixes the import against this test; this test must NEVER be
weakened or skipped to reach GREEN.

RED-for-right-reason: scenario 1 below raises a genuine, unhandled
``NameError`` DURING test-body execution (the real defect, observed live) --
never an ``ImportError``/collection error. Every name this file imports
already exists on this branch.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli import verify_slice_commit_completeness as vscc
from tests.common.gate_scope_fixtures import (
    stamp_genuine_gate_scope_trailer as _stamp_genuine_gate_scope_trailer,
)


# ---------------------------------------------------------------------------
# fixture builders (disposable git repos; every git write targets `repo` only)
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
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


def _write_regression_test(
    repo: Path, feature_id: str, slice_id: str, marker: int
) -> Path:
    """A real, pytest-collectible, genuinely-passing regression test file,
    head-tagged for E1's `# @feature-{id}` / `# @{slice-NN}` discovery
    convention (doubles as the E1 delivered-AT artifact and the E2
    behavioral witness -- same convention as every sibling AT in this dir)."""
    rel_path = f"tests/bugs/fixture/test_pytest_regression_fixture_{slice_id.replace('-', '_')}.py"
    path = repo / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# @feature-{feature_id}\n# @{slice_id}\n"
        f"def test_{slice_id.replace('-', '_')}_stays_fixed():\n"
        f"    assert {marker} + {marker} == {marker * 2}\n",
        encoding="utf-8",
    )
    return Path(rel_path)


def _write_feature_delta_without_slice_plan(repo: Path, feature_id: str) -> None:
    """A feature-delta.md that EXISTS but carries NO `[REF] Slice Plan`
    section -- the exact shape a `/nw-bugfix` lane leaves behind (a Charter
    describing the bug, never a multi-slice plan)."""
    delta_dir = repo / "docs" / "feature" / feature_id
    delta_dir.mkdir(parents=True, exist_ok=True)
    (delta_dir / "feature-delta.md").write_text(
        f"# Feature Delta: {feature_id}\n\n"
        "## Wave: DISCUSS / [REF] Charter\n\n"
        "A bugfix lane's feature-delta -- describes the observed defect, "
        "never authors a `[REF] Slice Plan` section.\n",
        encoding="utf-8",
    )


def _write_feature_delta_with_slice_plan(
    repo: Path, feature_id: str, rows: list[tuple[str, str, str, str, str]]
) -> None:
    """A well-formed `[REF] Slice Plan` table -- `rows` is
    `(slice_id, value_statement, status, annotation, justification)`."""
    delta_dir = repo / "docs" / "feature" / feature_id
    delta_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Feature Delta: {feature_id}\n\n",
        "## Wave: DISCUSS / [REF] Slice Plan\n\n",
        "| Slice | Value statement | Status | Annotation | Justification |\n",
        "|-------|-----------------|--------|------------|---------------|\n",
    ]
    for slice_id, value_statement, status, annotation, justification in rows:
        lines.append(
            f"| {slice_id} | {value_statement} | {status} | {annotation} | "
            f"{justification} |\n"
        )
    (delta_dir / "feature-delta.md").write_text("".join(lines), encoding="utf-8")


def _commit_all(repo: Path, subject: str, slice_ids: list[str]) -> None:
    trailers = "\n".join(f"Slice-Id: {sid}" for sid in slice_ids)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"{subject}\n\n{trailers}")


def _run_verify_slice_commit(
    repo: Path,
    feature_id: str,
    regression_test_file_rel: str,
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, dict[str, object]]:
    """Drive the REAL `des verify-slice-commit` CLI (`main()`) in-process,
    capturing its single-line JSON verdict via `capsys`."""
    exit_code = vscc.main(
        [
            "--repo",
            str(repo),
            "--commit",
            "HEAD",
            "--feature-id",
            feature_id,
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            regression_test_file_rel,
        ]
    )
    stdout = capsys.readouterr().out
    json_lines = [ln for ln in stdout.splitlines() if ln.strip().startswith("{")]
    payload: dict[str, object] = json.loads(json_lines[-1]) if json_lines else {}
    return exit_code, payload


_FEATURE_ID_MISSING_PLAN = "gateerror-import-missing-slice-plan"
_FEATURE_ID_WELL_FORMED_PLAN = "gateerror-import-well-formed-slice-plan"


# ===========================================================================
# Scenario 1 -- RED today: a feature-delta with NO `[REF] Slice Plan` section
# must never crash `_is_at_exempt_lane` with a NameError -- it must degrade
# to "not exempt" and let the slice verify normally.
# ===========================================================================


def test_missing_slice_plan_section_still_verifies_the_slice_instead_of_crashing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A `/nw-bugfix`-shaped feature-delta (a Charter section, no
    `[REF] Slice Plan`) must let `des verify-slice-commit` clear normally --
    the entering slice is genuinely, verifiably passing, so exemption
    resolution must degrade to ``False`` (not exempt) and the slice must
    still earn `SliceCommitVerified`.

    RED today for the diagnosed reason: `_is_at_exempt_lane` calls
    `parse_slice_plan`, which raises `GateError` because the section is
    absent, and `except GateError:` itself raises `NameError` (the name is
    not imported) -- an unhandled crash escapes this test's call to
    `vscc.main(...)` before ANY verdict is produced.
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    slice_id = "slice-01"
    regression_rel = _write_regression_test(
        repo, _FEATURE_ID_MISSING_PLAN, slice_id, marker=7
    )
    _write_feature_delta_without_slice_plan(repo, _FEATURE_ID_MISSING_PLAN)
    _commit_all(repo, "fix(slice): repair the observed defect", [slice_id])
    _stamp_genuine_gate_scope_trailer(repo)

    exit_code, payload = _run_verify_slice_commit(
        repo, _FEATURE_ID_MISSING_PLAN, str(regression_rel), capsys
    )

    assert exit_code == 0, (
        "a slice whose regression test genuinely passes, under a "
        "feature-delta with no `[REF] Slice Plan` section, must clear -- "
        "exemption resolution must degrade to 'not exempt' and let E2 run "
        f"normally, never crash. got exit_code={exit_code!r}, "
        f"payload={payload!r}"
    )
    assert payload.get("event") == "SliceCommitVerified", payload

    verified = AtCompletionLedger(_FEATURE_ID_MISSING_PLAN, repo).verified_slices()
    assert slice_id in verified, (
        "the slice must earn a SliceCommitVerified ledger record -- observed "
        f"verified_slices={sorted(verified)!r}"
    )


# ===========================================================================
# Scenario 2 -- NEGATIVE oracle: a feature-delta that DOES carry a
# well-formed `[REF] Slice Plan` must keep resolving BOTH lane shapes
# exactly as before the fix -- an `@prefactoring` shipped-in-this-commit
# slice still resolves EXEMPT, a plain slice still resolves not-exempt and
# is behaviorally verified. Guards the cure from becoming a disease: the
# import fix must never widen or narrow exemption when the section IS
# present.
# ===========================================================================


@pytest.mark.negative_at
def test_well_formed_slice_plan_lane_resolution_never_regresses(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One commit lists TWO slices via two `Slice-Id:` trailers: `slice-01`
    is `@prefactoring`-annotated (zero AT by design, must resolve EXEMPT and
    be skipped by E2 entirely) and `slice-02` carries no annotation (must
    resolve NOT exempt and be verified behaviorally via its own regression
    test). Both outcomes must hold BEFORE and AFTER the import fix -- this
    pins the sibling behavior the fix must not disturb.
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    exempt_slice_id = "slice-01"
    plain_slice_id = "slice-02"
    regression_rel = _write_regression_test(
        repo, _FEATURE_ID_WELL_FORMED_PLAN, plain_slice_id, marker=9
    )
    _write_feature_delta_with_slice_plan(
        repo,
        _FEATURE_ID_WELL_FORMED_PLAN,
        rows=[
            (
                exempt_slice_id,
                "as an architect I can trust the base is clean before slice-02 lands",
                "planned",
                "@prefactoring",
                "Behavior-preserving restructuring, no AT by design",
            ),
            (
                plain_slice_id,
                "as a user I get the new observable behaviour",
                "planned",
                "",
                "",
            ),
        ],
    )
    _commit_all(
        repo,
        "feat(slice): deliver the new observable behaviour",
        [exempt_slice_id, plain_slice_id],
    )
    _stamp_genuine_gate_scope_trailer(repo)

    exit_code, payload = _run_verify_slice_commit(
        repo, _FEATURE_ID_WELL_FORMED_PLAN, str(regression_rel), capsys
    )

    assert exit_code == 0, (
        "a well-formed `[REF] Slice Plan` section must keep clearing exactly "
        f"as before the import fix -- got exit_code={exit_code!r}, "
        f"payload={payload!r}"
    )
    assert payload.get("event") == "SliceCommitVerified", payload

    verified = AtCompletionLedger(_FEATURE_ID_WELL_FORMED_PLAN, repo).verified_slices()
    assert exempt_slice_id in verified, (
        "the @prefactoring-annotated slice must still resolve EXEMPT and "
        f"still earn SliceCommitVerified -- observed verified={sorted(verified)!r}"
    )
    assert plain_slice_id in verified, (
        "the plain (unannotated) slice must still resolve NOT exempt and be "
        f"verified behaviorally -- observed verified={sorted(verified)!r}"
    )
