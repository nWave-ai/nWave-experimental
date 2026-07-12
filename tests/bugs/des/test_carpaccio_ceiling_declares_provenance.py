"""Regression -- the carpaccio too-large rejection names the ceiling's VALUE
but discards its PROVENANCE.

DEFECT (GDP-3/GDP-6 message-provenance): ``_config_slice_max(repo)``
(``src/des/cli/carpaccio_format.py:165``) reads ``atdd_pure.carpaccio_slice_max``
from ``.nwave/config.yaml`` OR falls back to ``_DEFAULT_SLICE_MAX`` (line 63 =
7, Ale-ratified), but returns a BARE ``int`` -- the caller has no way to know
whether the value came from a repo override or the framework default. When
``_check_slice_size_count`` (``carpaccio_format.py:994-1019``) raises
``CARPACCIO_SLICE_TOO_LARGE``, the rejection text says only "exceeding the
carpaccio ceiling of {slice_max}" -- a repo whose (often gitignored)
``.nwave/config.yaml`` sets ``carpaccio_slice_max: 3`` silently LOWERS the
framework default 7, and the operator sees "ceiling of 3" with no clue that a
higher default (7) exists or that a repo file is overriding it. Same defect
family as issue #180 (untracked recipe): a local override is invisible in the
loud diagnostic that is supposed to explain itself (every-failure-explains-
what-why-how mandate).

Sibling emission sites carrying the SAME bare ``{slice_max}`` interpolation
(not exercised by this AT, same defect class): ``carpaccio_format.py`` lines
799 (`entering_row is None`), 870/884 (`_check_total_coverage` -- these two
do NOT interpolate ``slice_max`` at all, so are unaffected), 913
(`_check_walking_skeleton_first` -- no ``slice_max``), 930
(`_check_value_annotation` -- no ``slice_max``). Only the size-ceiling
rejection at line ~994-1019 actually names ``slice_max`` in its text, which is
why it is the one under test here.

The fix (crafter's job, NOT implemented by this AT -- test-authoring only,
zero ``src/`` edits): ``_config_slice_max`` (or a sibling helper) must also
surface the ceiling's SOURCE, and ``_check_slice_size_count``'s rejection text
must declare it -- e.g. ``"ceiling of 3 (from repo .nwave/config.yaml;
framework default is 7)"`` when the repo config overrides, or ``"ceiling of 7
(framework default)"`` when no override exists. This AT pins the OUTCOME (the
rejection text names the source), never the mechanism.

Driving port (Mandate 16, no-direct-domain-testing): every AT below drives the
REAL ``des carpaccio-slice-gate`` CLI EDGE (``des.cli.carpaccio_slice_gate.main``)
in-process via ``tests.common.in_process_cli.run_cli_in_process`` -- the SAME
entry point ``des carpaccio-slice-gate --feature-id ... --entering-slice ...``
invokes, so ``_config_slice_max(repo)`` is exercised for REAL against an
on-disk ``.nwave/config.yaml`` (or its absence), never called directly as a
unit-level shortcut. ``at_kind="pytest-regression"`` mode is used (a real,
AST-counted ``.py`` regression-test fixture on disk) to avoid the extra
``.feature``-tagging machinery the gherkin path requires -- irrelevant to the
provenance defect under test, which lives entirely in the size-ceiling
rejection shared by both ``at_kind`` modes (``_check_slice_size_count``).

RED-for-right-reason: today's rejection text is
``f"slice {entering_slice} has {at_count} ATs, exceeding the carpaccio "
f"ceiling of {slice_max}"`` -- a bare integer, no source. Both scenarios below
assert a genuine semantic ``AssertionError`` (the expected provenance
substrings are ABSENT from the real rejection text), never an import or
collection error.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli.carpaccio_slice_gate import main as carpaccio_slice_gate_main
from tests.common.in_process_cli import run_cli_in_process


_FEATURE_ID = "carpaccio-ceiling-provenance"
_ENTERING_SLICE = "slice-01"
_FRAMEWORK_DEFAULT = 7
_REPO_OVERRIDE = 3


def _write_feature_delta(repo: Path, *, feature_id: str) -> None:
    """A minimal one-row Slice Plan -- no annotation/justification, so
    assertions 3 (walking-skeleton-first) and 4 (value-annotation) pass
    trivially and the size-ceiling check (assertion 1) is the only gate that
    can fire."""
    path = repo / "docs" / "feature" / feature_id / "feature-delta.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|---|---|---|---|---|\n"
        "| slice-01 | a cohesive regression AT group | pending | | |\n",
        encoding="utf-8",
    )


def _write_regression_file(repo: Path, *, count: int) -> str:
    """A real pytest regression file with `count` module-level `test_*`
    functions -- AST-counted for real by `count_net_new_pytest_regression_ats`
    (never mocked), so the AT count driving the ceiling comparison is the
    true count."""
    rel = "tests/regression/test_ceiling_fixture.py"
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    functions = "\n\n".join(
        f"def test_case_{i}():\n    assert {i} == {i}" for i in range(count)
    )
    path.write_text(functions + "\n", encoding="utf-8")
    return rel


def _write_repo_config_override(repo: Path, *, ceiling: int) -> None:
    path = repo / ".nwave" / "config.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"atdd_pure:\n  carpaccio_slice_max: {ceiling}\n",
        encoding="utf-8",
    )


def _run_carpaccio_slice_gate(
    repo: Path, *, feature_id: str, regression_test_file_rel: str
) -> tuple[int, str, str]:
    """Drive the REAL `des carpaccio-slice-gate` CLI EDGE in-process."""
    return run_cli_in_process(
        [
            "--feature-id",
            feature_id,
            "--entering-slice",
            _ENTERING_SLICE,
            "--repo-root",
            str(repo),
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            regression_test_file_rel,
        ],
        cwd=repo,
        main=carpaccio_slice_gate_main,
    )


def _rejection_text(stdout: str) -> str:
    """Extract the JSON diagnostic's `error` + `instruction` fields as one
    lowercased blob -- the rejection text the operator actually reads."""
    stdout_lines = [line for line in stdout.splitlines() if line.strip()]
    assert stdout_lines, "expected a JSON diagnostic line on stdout -- got EMPTY stdout"
    diagnostic = json.loads(stdout_lines[0])
    assert diagnostic.get("event") == "CARPACCIO_SLICE_TOO_LARGE", (
        f"expected the too-large rejection to fire -- got diagnostic={diagnostic!r}"
    )
    return (
        str(diagnostic.get("error", "")) + " " + str(diagnostic.get("instruction", ""))
    ).lower()


# ===========================================================================
# POSITIVE -- repo .nwave/config.yaml override must be NAMED as the source
# ===========================================================================


def test_carpaccio_ceiling_rejection_names_repo_config_source(tmp_path: Path) -> None:
    """A repo whose `.nwave/config.yaml` lowers `carpaccio_slice_max` to 3
    (below the framework default 7) must have its too-large rejection
    declare BOTH the literal `.nwave/config.yaml` (naming the repo-config
    source) AND the framework default `7` (so the operator sees the override
    lowered it) -- not just the bare number "3".
    """
    repo = tmp_path / "repo"
    _write_feature_delta(repo, feature_id=_FEATURE_ID)
    _write_repo_config_override(repo, ceiling=_REPO_OVERRIDE)
    regression_test_file_rel = _write_regression_file(repo, count=_REPO_OVERRIDE + 1)

    exit_code, stdout, stderr = _run_carpaccio_slice_gate(
        repo, feature_id=_FEATURE_ID, regression_test_file_rel=regression_test_file_rel
    )

    assert exit_code != 0, (
        "an over-ceiling pytest-regression slice must be rejected (non-zero "
        f"exit) -- got exit_code={exit_code}, stdout={stdout!r}, stderr={stderr!r}"
    )
    text = _rejection_text(stdout)

    assert ".nwave/config.yaml" in text, (
        "the too-large rejection must NAME the repo config file as the "
        "ceiling's source when .nwave/config.yaml overrides the default -- "
        f"got rejection text={text!r} (bare 'ceiling of 3' today, no "
        "provenance)"
    )
    assert "7" in text, (
        "the too-large rejection must surface the framework default (7) "
        "alongside the repo override (3) so the operator sees the override "
        f"LOWERED it -- got rejection text={text!r}"
    )


# ===========================================================================
# NEGATIVE (no-overcorrection guard) -- the framework default must NEVER be
# mislabeled as coming from repo config
# ===========================================================================


@pytest.mark.negative_at
def test_carpaccio_ceiling_rejection_default_not_mislabeled_as_repo_config(
    tmp_path: Path,
) -> None:
    """A repo with NO `.nwave/config.yaml` override (the framework default 7
    is in effect) must have its too-large rejection NEVER falsely claim
    `.nwave/config.yaml` as the ceiling's source -- the fix must not
    overcorrect by unconditionally naming a repo-config file that does not
    exist / was never consulted.
    """
    repo = tmp_path / "repo"
    _write_feature_delta(repo, feature_id=_FEATURE_ID)
    assert not (repo / ".nwave" / "config.yaml").exists(), (
        "test setup invariant: no .nwave/config.yaml must exist so the "
        "framework default (7) is genuinely in effect, unresolved by any "
        "repo override"
    )
    regression_test_file_rel = _write_regression_file(
        repo, count=_FRAMEWORK_DEFAULT + 1
    )

    exit_code, stdout, stderr = _run_carpaccio_slice_gate(
        repo, feature_id=_FEATURE_ID, regression_test_file_rel=regression_test_file_rel
    )

    assert exit_code != 0, (
        "an over-ceiling pytest-regression slice must be rejected (non-zero "
        f"exit) -- got exit_code={exit_code}, stdout={stdout!r}, stderr={stderr!r}"
    )
    text = _rejection_text(stdout)

    assert ".nwave/config.yaml" not in text, (
        "the too-large rejection must NEVER claim .nwave/config.yaml as the "
        "ceiling's source when no such file exists -- the fix must not lie "
        f"that the framework default came from repo config -- got rejection "
        f"text={text!r}"
    )
    assert "framework default" in text, (
        "the too-large rejection must positively label the ceiling as the "
        f"framework default when no repo override exists -- got rejection "
        f"text={text!r}"
    )
