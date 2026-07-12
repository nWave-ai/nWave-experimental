"""Regression: `des dispatch` (feature lane) GENERATES a crafter envelope on
stdout WITHOUT ever checking whether the target feature's feature-delta is
readiness-ready (e.g. missing `## Reuse Analysis`, malformed Slice Plan, or a
missing delta entirely). An operator generates the envelope, dispatches the
crafter, and ONLY THEN does the separate readiness gate
(`des verify-readiness-pre-dispatch`) reject it -- a wasted round trip.
GDP-1/2: the check should surface at GENERATION time (inline-at-authoring),
as a proactive ADVISORY, not after the crafter has already been dispatched.

THE FIX this test targets (NOT implemented here -- crafter's job): for a
FEATURE-phase dispatch (e.g. `--phase A_GREEN` WITHOUT `--lane bugfix`),
`des dispatch` runs `validate_feature_delta`-family checks against
`docs/feature/{project-id}/feature-delta.md` BEFORE rendering the envelope;
on failure (missing Reuse Analysis / malformed Slice Plan / missing delta) it
prints a proactive ADVISORY on STDERR naming what's missing. The advisory is
ADVISORY-ONLY -- the envelope is STILL generated on stdout, exit code stays
0. The bugfix lane is EXEMPT (a bugfix dispatch has no feature-delta to
check -- mirrors the existing bugfix-lane exemption in
`verify_readiness_pre_dispatch._run_bugfix_lane`).

Driving surface (Mandate 16 -- driving-port-only, default IN-PROCESS): the
REAL `des dispatch` CLI, driven in-process via
`tests/common/in_process_cli.run_cli_in_process`, against a tmp repo-root
carrying a COPY of the real `nWave/dispatch/{atdd_pure.yaml,vendors.yaml}`
SSOT (so section-rendering succeeds unmodified) plus a fixture
`docs/feature/{id}/feature-delta.md` that is well-formed EXCEPT it omits
`## Reuse Analysis` entirely.

RED-for-right-reason: the positive AT below asserts stderr carries a
proactive readiness advisory naming "Reuse Analysis" -- this FAILS today
with a genuine semantic `AssertionError` (stderr is empty of any such text;
`des dispatch` never reads the feature-delta at all today), never an
import/collection error.

covers: F-des-dispatch-readiness-advisory (bugfix)
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tests.common.in_process_cli import run_cli_in_process


# tests/bugs/des/<this file> -> parents[3] is the checkout root.
_REPO_ROOT = Path(__file__).resolve().parents[3]

_DES_VALIDATION_MARKER_PREFIX = "<!-- DES-VALIDATION"

_MARKER_KEYS = (
    "DES-VALIDATION",
    "DES-PROJECT-ID",
    "DES-MODE",
    "DES-PHASE",
    "DES-SLICE",
    "DES-WAVE",
)

#: Well-formed EXCEPT it has no `## Reuse Analysis` section (nor an
#: exemption marker) -- isolates exactly the one gap this test targets.
_FEATURE_DELTA_MISSING_REUSE_ANALYSIS = """\
## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|---|---|---|---|---|
| slice-01 | user sees the readiness advisory before dispatching the crafter | pending | | |
"""

_ADVISORY_FRAMING_WORDS = ("advisory", "Advisory", "ADVISORY", "warning", "Warning")


def _make_repo_root(
    tmp_path: Path, *, feature_id: str, feature_delta: str | None
) -> Path:
    """Build a tmp repo-root carrying a COPY of the real dispatch SSOT plus
    an optional fixture `feature-delta.md` -- mirrors the tmp-repo-root
    pattern `test_dispatch_section_set_changes_when_the_ssot_yaml_gains_a_
    section` (tests/des/unit/cli/test_des_dispatch_generator.py) already
    established for this CLI.
    """
    dispatch_dir = tmp_path / "nWave" / "dispatch"
    dispatch_dir.mkdir(parents=True)
    for name in ("atdd_pure.yaml", "vendors.yaml"):
        shutil.copyfile(_REPO_ROOT / "nWave" / "dispatch" / name, dispatch_dir / name)
    if feature_delta is not None:
        feature_dir = tmp_path / "docs" / "feature" / feature_id
        feature_dir.mkdir(parents=True)
        (feature_dir / "feature-delta.md").write_text(feature_delta, encoding="utf-8")
    return tmp_path


def _run_dispatch(argv: list[str], *, cwd: Path) -> tuple[int, str, str]:
    """Drive the REAL `des dispatch` CLI in-process (Layer-2 default)."""
    return run_cli_in_process(["dispatch", *argv], cwd=cwd)


def _feature_argv(*, project_id: str, repo_root: Path) -> list[str]:
    return [
        "--mode",
        "atdd_pure",
        "--project-id",
        project_id,
        "--slice",
        "slice-01",
        "--phase",
        "A_GREEN",
        "--repo-root",
        str(repo_root),
    ]


def test_feature_dispatch_emits_readiness_advisory_for_missing_reuse_analysis(
    tmp_path: Path,
) -> None:
    """POSITIVE (active-RED today): a feature-lane `--phase A_GREEN` dispatch
    (no `--lane bugfix`) for a project whose feature-delta LACKS
    `## Reuse Analysis` must print a proactive readiness ADVISORY on STDERR
    naming the gap, while STILL emitting the valid envelope on STDOUT with
    exit code 0 -- advisory-only, never a hard block.
    """
    repo_root = _make_repo_root(
        tmp_path,
        feature_id="probe-readiness",
        feature_delta=_FEATURE_DELTA_MISSING_REUSE_ANALYSIS,
    )

    exit_code, stdout, stderr = _run_dispatch(
        _feature_argv(project_id="probe-readiness", repo_root=repo_root),
        cwd=repo_root,
    )

    assert exit_code == 0, (
        "the readiness advisory must be advisory-ONLY -- exit code must stay "
        f"0 even when the Reuse Analysis is missing. got exit_code={exit_code}, "
        f"stdout={stdout!r}, stderr={stderr!r}"
    )
    assert "Reuse Analysis" in stderr, (
        "expected a proactive readiness advisory on STDERR naming the "
        "missing '## Reuse Analysis' section (GDP-1/2: catch it at "
        "generation time, before the crafter is dispatched and the separate "
        "readiness gate rejects it). `des dispatch` today never reads the "
        f"feature-delta at all before rendering. stderr={stderr!r}"
    )
    assert any(word in stderr for word in _ADVISORY_FRAMING_WORDS), (
        "the readiness message must be framed as an ADVISORY (proactive, "
        f"non-blocking), not a bare error -- stderr={stderr!r}"
    )
    assert _DES_VALIDATION_MARKER_PREFIX in stdout, (
        "the crafter envelope must STILL be generated on stdout even when "
        f"the readiness advisory fires -- stdout={stdout!r}"
    )


@pytest.mark.negative_at
def test_bugfix_lane_dispatch_emits_no_readiness_advisory(tmp_path: Path) -> None:
    """NEGATIVE AT (critical -- must stay GREEN before AND after the fix):
    the bugfix lane is EXEMPT from the feature-delta readiness check (a
    bugfix dispatch has no feature-delta to check, mirroring the existing
    bugfix-lane exemption in `verify_readiness_pre_dispatch._run_bugfix_
    lane`) -- no readiness advisory on stderr, exit 0, valid envelope on
    stdout, even though this project's feature-delta.md does not exist at
    all.
    """
    repo_root = _make_repo_root(tmp_path, feature_id="probe-bugfix", feature_delta=None)

    exit_code, stdout, stderr = _run_dispatch(
        [
            "--mode",
            "atdd_pure",
            "--project-id",
            "probe-bugfix",
            "--slice",
            "slice-01",
            "--phase",
            "A_GREEN",
            "--lane",
            "bugfix",
            "--defect",
            "off-by-one in _resolve_head_sha returns the parent commit",
            "--regression-test",
            "test_resolve_head_sha_returns_head",
            "--repo-root",
            str(repo_root),
        ],
        cwd=repo_root,
    )

    assert exit_code == 0, (
        "expected the bugfix-lane dispatch to succeed -- got "
        f"exit_code={exit_code}, stdout={stdout!r}, stderr={stderr!r}"
    )
    assert "Reuse Analysis" not in stderr, (
        "the bugfix lane must NOT emit a feature-delta readiness advisory "
        f"-- it is exempt from the readiness check. stderr={stderr!r}"
    )
    assert _DES_VALIDATION_MARKER_PREFIX in stdout, (
        "the bugfix-lane envelope must still be generated on stdout -- "
        f"stdout={stdout!r}"
    )


@pytest.mark.negative_at
def test_advisory_does_not_corrupt_stdout_envelope(tmp_path: Path) -> None:
    """NEGATIVE AT (must stay GREEN before AND after the fix): the readiness
    advisory must land on STDERR only -- the STDOUT envelope stays fully
    parseable (the full marker triple present, no advisory text leaking in)
    even when the advisory fires alongside it.
    """
    repo_root = _make_repo_root(
        tmp_path,
        feature_id="probe-readiness-2",
        feature_delta=_FEATURE_DELTA_MISSING_REUSE_ANALYSIS,
    )

    exit_code, stdout, stderr = _run_dispatch(
        _feature_argv(project_id="probe-readiness-2", repo_root=repo_root),
        cwd=repo_root,
    )

    assert exit_code == 0, (
        f"expected exit 0 -- got exit_code={exit_code}, stderr={stderr!r}"
    )
    for marker_key in _MARKER_KEYS:
        assert f"<!-- {marker_key}" in stdout, (
            f"stdout envelope must carry the {marker_key!r} marker undisturbed "
            f"by the readiness advisory -- stdout={stdout!r}"
        )
    assert "Reuse Analysis" not in stdout, (
        "the readiness advisory text must go to STDERR ONLY -- it must "
        f"never pollute STDOUT. stdout={stdout!r}"
    )
