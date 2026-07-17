"""Regression: `des dispatch` must be usable from a CONSUMING repo -- a
project that has nWave INSTALLED into it but does not itself carry
`nWave/dispatch/*.yaml` (that SSOT ships with the nWave runtime, not with a
user's project).

DEFECT (RCA: docs/feature/fix-dispatch-ssot-consuming-repo/deliver/rca.md):
`--repo-root` does DOUBLE DUTY in `src/des/cli/dispatch.py::main` -- it
resolves BOTH (a) the dispatch SSOT (a RUNTIME/install concern -- the
existing installed-runtime fallback, `_INSTALLED_DISPATCH_ASSETS_DIR`,
dispatch.py:74-76, already covers this axis when `--repo-root` is OMITTED)
and (b) the project's `feature-delta.md` (a PROJECT concern, resolved by
`_feature_delta_readiness_advisory`, dispatch.py:194/611). Two independent,
RCA-confirmed-live consequences of that conflation:

  * Branch A (dispatch.py:560-568): an EXPLICIT `--repo-root` unconditionally
    wins over the installed-runtime fallback (`args.repo_root is not None`
    short-circuits the `elif`/`else` chain that consults
    `_INSTALLED_DISPATCH_ASSETS_DIR`) -- so a developer following the CLI's
    own `--help` text (`--repo-root .`, the exact reported reproduction)
    from their OWN project (no `nWave/dispatch/` under it) gets "cannot read
    dispatch SSOT" even though the SSOT IS shipped in the installed runtime.
  * Branch B: the ONLY way around Branch A today (omit `--repo-root`) reuses
    the SAME resolved `repo_root` for the feature-delta advisory
    (dispatch.py:611) -- when that value falls back to the installed-runtime
    dir, the advisory looks for `docs/feature/<id>/feature-delta.md` under
    the INSTALLED dir, not the caller's project, producing a FALSE "no
    feature-delta.md found" even when a real, complete one exists in the
    project.

Fix direction (RCA "Proposed minimal fix", not implemented by this AT):
separate the two axes -- the SSOT axis keeps consulting
`_INSTALLED_DISPATCH_ASSETS_DIR` regardless of `--repo-root`; the project
axis (feature-delta lookup) adopts
`des.domain.repo_path_resolver.resolve_repo_root`/`feature_delta_path` (the
existing, already-16-times-reused project-root SSOT) instead of the ad-hoc
`repo_root` local `dispatch.py` currently double-duties.

Driving surface (Mandate 16 -- driving-port-only, default IN-PROCESS):
`tests/common/in_process_cli.run_cli_in_process` against the REAL `des
dispatch` CLI (`des.cli.dispatch.main`, reached via `des.cli.__main__`'s
subcommand registry) -- the in-process analogue of `python -m
des.cli.__main__ dispatch ...`, `cwd=` reproducing the reported command's
directory faithfully. Mirrors the established
`test_dispatch_ssot_installed_runtime_fallback.py` sibling in this same
directory (same monkeypatch seam, `dispatch._INSTALLED_DISPATCH_ASSETS_DIR`,
`raising=False` since only the resolution ORDER changes, not the constant's
existence).

RED-for-right-reason: `test_explicit_repo_root_pointing_at_a_consuming_project_still_generates_a_dispatch`
and `test_feature_delta_advisory_resolves_under_the_project_root_not_the_installed_dir`
FAIL today with a genuine semantic `AssertionError` (refusal / false
advisory), never an import or collection error -- both reproduced live in
the RCA against a real installed runtime, and reproduced HERE (deterministically,
hermetically) via the monkeypatched installed-assets seam.

covers: fix-dispatch-ssot-consuming-repo
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.cli import dispatch
from tests.common.in_process_cli import run_cli_in_process


# tests/bugs/des/<this file> -> parents[3] is the checkout root (mirrors
# test_dispatch_ssot_installed_runtime_fallback.py in this same directory).
_REPO_ROOT = Path(__file__).resolve().parents[3]
_REAL_ATDD_PURE_YAML = _REPO_ROOT / "nWave" / "dispatch" / "atdd_pure.yaml"
_REAL_VENDORS_YAML = _REPO_ROOT / "nWave" / "dispatch" / "vendors.yaml"

#: A feature id guaranteed ABSENT from this checkout's own docs/feature/ tree
#: -- so any advisory this checkout's SSOT/project resolution accidentally
#: points at (a mis-resolved "wrong axis" path) is provably empty too,
#: keeping the negative-AT pins honest regardless of which directory a given
#: assertion targets.
_ABSENT_FEATURE_ID = "consuming-repo-probe-zzq7"

_READY_FEATURE_DELTA = "## Reuse Analysis\n\nReuse-Analysis: no-overlap\n"

_MISSING_FEATURE_DELTA_SIGNAL = "no feature-delta.md found"


def _copy_real_dispatch_ssot(dst_dir: Path) -> None:
    """Copy THIS checkout's real dispatch SSOT into ``dst_dir`` verbatim."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    (dst_dir / "atdd_pure.yaml").write_text(
        _REAL_ATDD_PURE_YAML.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (dst_dir / "vendors.yaml").write_text(
        _REAL_VENDORS_YAML.read_text(encoding="utf-8"), encoding="utf-8"
    )


def _write_ready_feature_delta(project_root: Path, feature_id: str) -> Path:
    delta_path = project_root / "docs" / "feature" / feature_id / "feature-delta.md"
    delta_path.parent.mkdir(parents=True, exist_ok=True)
    delta_path.write_text(_READY_FEATURE_DELTA, encoding="utf-8")
    return delta_path


def _base_argv(
    *,
    project_id: str = _ABSENT_FEATURE_ID,
    slice_id: str = "slice-01",
    repo_root: str | None = None,
) -> list[str]:
    argv = [
        "--mode",
        "atdd_pure",
        "--project-id",
        project_id,
        "--slice",
        slice_id,
        "--phase",
        "A_GREEN",
        "--intent",
        "verify consuming-repo dispatch",
    ]
    if repo_root is not None:
        argv += ["--repo-root", repo_root]
    return argv


def _run_dispatch(argv: list[str], *, cwd: Path) -> tuple[int, str, str]:
    return run_cli_in_process(["dispatch", *argv], cwd=cwd)


# ---------------------------------------------------------------------------
# POSITIVE CASE 1 (the core defect, Branch A) -- an explicit --repo-root
# pointing at a genuine consuming project (no nWave/dispatch/ under it) must
# still GENERATE a dispatch skeleton via the installed-runtime fallback, not
# refuse "cannot read dispatch SSOT". This is the EXACT reported reproduction
# command shape: `des dispatch ... --repo-root .` run from inside the
# consuming project.
# ---------------------------------------------------------------------------


def test_explicit_repo_root_pointing_at_a_consuming_project_still_generates_a_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A developer's own project (no `nWave/dispatch/` under it) passed
    explicitly via `--repo-root .` must still get a real, GENERATED dispatch
    skeleton -- the whole point of `des dispatch` is that the system produces
    the artifact so the operator never hand-assembles it.

    FAILS TODAY: `main()`'s SSOT-resolution order (dispatch.py:563-564) takes
    `args.repo_root is not None` as an UNCONDITIONAL, first-priority branch --
    it never falls through to the installed-runtime fallback
    (`_INSTALLED_DISPATCH_ASSETS_DIR`) even when the fallback IS armed and the
    explicit `--repo-root` has no SSOT of its own. Reads
    `<consuming_project>/nWave/dispatch/atdd_pure.yaml`, gets `OSError`, exits
    2 with "cannot read dispatch SSOT" -- never reaching exit 0.
    """
    consuming_project = tmp_path / "consuming-project"
    consuming_project.mkdir()

    installed_assets_dir = tmp_path / "installed" / "nWave" / "dispatch"
    _copy_real_dispatch_ssot(installed_assets_dir)
    monkeypatch.setattr(
        dispatch, "_INSTALLED_DISPATCH_ASSETS_DIR", installed_assets_dir, raising=False
    )

    # `--repo-root .` -- the literal flag value the CLI's own --help text
    # tells a consuming-repo operator to pass, resolved against `cwd` (set to
    # the consuming project below, matching the RCA's reported `cd
    # <project> && des dispatch ... --repo-root .`).
    exit_code, stdout, stderr = _run_dispatch(
        _base_argv(repo_root="."), cwd=consuming_project
    )

    assert exit_code == 0, (
        "expected `des dispatch --repo-root .` from a consuming project "
        "(no nWave/dispatch/ of its own) to GENERATE a dispatch skeleton via "
        f"the installed-runtime fallback; got exit {exit_code} instead -- "
        "the explicit --repo-root defeated the fallback. "
        f"stdout={stdout!r} stderr={stderr!r}"
    )
    assert f"<!-- DES-PROJECT-ID : {_ABSENT_FEATURE_ID} -->" in stdout, (
        "expected a compliant, marker-carrying dispatch skeleton in stdout -- "
        f"got stdout={stdout!r} stderr={stderr!r}"
    )
    assert "<!-- DES-MODE : atdd_pure -->" in stdout, (
        f"expected the DES-MODE marker in the generated skeleton. "
        f"stdout={stdout!r} stderr={stderr!r}"
    )
    assert "# DES_METADATA" in stdout, (
        "expected the full, standard section set (not a truncated stub) -- "
        f"e.g. the DES_METADATA header. stdout={stdout!r}"
    )


# ---------------------------------------------------------------------------
# POSITIVE CASE 2 (Branch B) -- the ONLY way around Branch A today (omit
# --repo-root, letting the installed fallback resolve the SSOT) must NOT
# reuse that same installed-dir path for the project's feature-delta lookup.
# A genuinely present, readiness-ready feature-delta.md in the consuming
# project must be found there -- never falsely reported missing.
# ---------------------------------------------------------------------------


def test_feature_delta_advisory_resolves_under_the_project_root_not_the_installed_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real, readiness-ready `docs/feature/<id>/feature-delta.md` living in
    the consuming project must be found there -- the readiness advisory must
    never conflate the installed-runtime SSOT directory with the caller's
    own project directory.

    FAILS TODAY: omitting `--repo-root` (the only workaround for Branch A)
    makes `main()` resolve `repo_root` to the installed-runtime fallback dir
    for BOTH the SSOT read (line 570) AND the feature-delta advisory (line
    611, `_feature_delta_readiness_advisory(repo_root, project_id)`) -- so the
    advisory looks for `<installed_dir>/docs/feature/<id>/feature-delta.md`
    instead of `<consuming_project>/docs/feature/<id>/feature-delta.md`,
    printing a FALSE "no feature-delta.md found" even though the real file
    exists exactly where the developer put it.
    """
    consuming_project = tmp_path / "consuming-project"
    consuming_project.mkdir()
    feature_id = "genuinely-ready-feature"
    delta_path = _write_ready_feature_delta(consuming_project, feature_id)
    assert delta_path.is_file()  # fixture sanity

    installed_assets_dir = tmp_path / "installed" / "nWave" / "dispatch"
    _copy_real_dispatch_ssot(installed_assets_dir)
    monkeypatch.setattr(
        dispatch, "_INSTALLED_DISPATCH_ASSETS_DIR", installed_assets_dir, raising=False
    )

    # --repo-root OMITTED (the RCA's second repro command) -- cwd IS the
    # consuming project, which carries no nWave/dispatch/ of its own, so SSOT
    # resolution falls to the installed fallback.
    exit_code, stdout, stderr = _run_dispatch(
        _base_argv(project_id=feature_id), cwd=consuming_project
    )

    assert exit_code == 0, (
        f"expected the omitted-`--repo-root` workaround to still succeed via "
        f"the installed fallback; got exit {exit_code}. "
        f"stdout={stdout!r} stderr={stderr!r}"
    )
    assert _MISSING_FEATURE_DELTA_SIGNAL not in stderr, (
        "the readiness advisory falsely reported the feature-delta missing "
        f"even though a real, readiness-ready one exists at {delta_path} -- "
        "the advisory resolved the PROJECT axis under the installed-runtime "
        f"dir instead of the caller's own project. stderr={stderr!r}"
    )
    assert "advisory:" not in stderr, (
        "a genuinely readiness-ready feature-delta must produce NO readiness "
        f"advisory at all. stderr={stderr!r}"
    )


# ---------------------------------------------------------------------------
# NEGATIVE-AT PINS -- the cure must not become a disease. Each of these stays
# GREEN both BEFORE and AFTER the fix; none exercises the repo-root/project
# axis conflation this AT's positive cases target.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_bogus_mode_still_refuses_honestly(tmp_path: Path) -> None:
    """A genuinely bogus `--mode` must still be refused -- the fix must never
    fabricate a skeleton for a mode it does not recognize just because it
    stopped falsely refusing valid ones. Unaffected by the repo-root fix:
    `--mode`'s `choices=("atdd_pure",)` is a pure argparse-level guard, never
    touches SSOT/project resolution -- stable before and after."""
    consuming_project = tmp_path / "consuming-project"
    consuming_project.mkdir()

    argv = [
        "--mode",
        "does-not-exist",
        "--project-id",
        _ABSENT_FEATURE_ID,
        "--slice",
        "slice-01",
        "--phase",
        "A_GREEN",
    ]
    exit_code, stdout, stderr = _run_dispatch(argv, cwd=consuming_project)

    assert exit_code != 0, (
        f"a bogus --mode must be refused, not silently accepted. "
        f"exit={exit_code} stdout={stdout!r} stderr={stderr!r}"
    )
    assert "DES-PROJECT-ID" not in stdout, (
        f"a bogus --mode must NEVER fabricate a dispatch skeleton. stdout={stdout!r}"
    )


@pytest.mark.negative_at
def test_genuinely_missing_feature_delta_is_still_reported_missing(
    tmp_path: Path,
) -> None:
    """A project whose feature-delta genuinely does NOT exist must still be
    told so -- the fix must not silence a true 'not found' into false
    readiness. Deliberately DECOUPLED from the repo-root/installed-dir axis
    conflation: the consuming project carries ITS OWN real `nWave/dispatch/`
    tree (mirrors `test_repo_root_flag_wins_over_installed_fallback`'s
    precedent shape), so `--repo-root` resolves BOTH axes to the SAME
    directory both before and after the fix -- this pin is stable across the
    fix by construction, isolating "true absence is still reported" from the
    axis-separation defect the positive cases above target."""
    consuming_project = tmp_path / "consuming-project"
    _copy_real_dispatch_ssot(consuming_project / "nWave" / "dispatch")
    # deliberately NO docs/feature/<id>/feature-delta.md written.

    exit_code, stdout, stderr = _run_dispatch(
        _base_argv(repo_root=str(consuming_project)), cwd=consuming_project
    )

    assert exit_code == 0, (
        f"the SSOT is genuinely present -- dispatch must still succeed. "
        f"exit={exit_code} stdout={stdout!r} stderr={stderr!r}"
    )
    assert _MISSING_FEATURE_DELTA_SIGNAL in stderr, (
        "a genuinely absent feature-delta.md must still be reported missing "
        f"-- got stderr={stderr!r} (must not be silently suppressed into "
        "false readiness)"
    )


@pytest.mark.negative_at
def test_ssot_absent_everywhere_still_refuses_honestly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the dispatch SSOT is absent BOTH in the target repo AND the
    installed-runtime fallback dir, `des dispatch` must still refuse honestly
    -- the fallback is a fallback, never a fabrication. Mirrors the
    established `test_dispatch_refuses_with_both_cures_when_neither_ssot_
    source_exists` precedent in the sibling
    `test_dispatch_ssot_installed_runtime_fallback.py` file; pinned here too
    so this file's own fix does not accidentally weaken that guarantee while
    separating the SSOT/project axes."""
    consuming_project = tmp_path / "consuming-project"
    consuming_project.mkdir()

    absent_installed_dir = tmp_path / "not-installed" / "nWave" / "dispatch"
    monkeypatch.setattr(
        dispatch, "_INSTALLED_DISPATCH_ASSETS_DIR", absent_installed_dir, raising=False
    )

    exit_code, stdout, stderr = _run_dispatch(
        _base_argv(repo_root="."), cwd=consuming_project
    )

    assert exit_code == dispatch._EXIT_USAGE_ERROR, (
        "expected the LOUD refusal exit when the SSOT resolves nowhere -- "
        f"got {exit_code}. stdout={stdout!r} stderr={stderr!r}"
    )
    assert "DES-PROJECT-ID" not in stdout, (
        f"a fully-absent SSOT must never fabricate a skeleton. stdout={stdout!r}"
    )
    assert "cannot read dispatch SSOT" in stderr, (
        f"expected the honest SSOT-unreadable refusal. stderr={stderr!r}"
    )
