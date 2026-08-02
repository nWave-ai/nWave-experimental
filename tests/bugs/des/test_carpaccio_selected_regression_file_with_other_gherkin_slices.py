"""Regression: an explicit pytest-regression selection owns only its slice.

The carpaccio CLI reads all of a feature's Gherkin scenarios before it invokes
``check_carpaccio``.  That helper currently treats any non-empty scenario list
as malformed mixed mode, including when those scenarios belong to another
slice.  An operator who explicitly selects a valid regression file for one
slice must instead have that selected file assessed.  A missing or malformed
selected file remains a fail-closed input error, and the Gherkin route remains
unchanged.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from des.cli.carpaccio_slice_gate import main as carpaccio_slice_gate_main
from des.cli.verify_red_green import _seal_path


_FEATURE_ID = "selected-regression-file-with-other-slices"
_PYTEST_REGRESSION_REL = "tests/regression/test_selected_check.py"
_VALID_REGRESSION = "def test_selected_check_rejects_bad_input():\n    assert True\n"
_NATIVE_REGRESSION_REL = "tests/regression/selected_check.rs"
_VALID_NATIVE_REGRESSION = (
    "#[test]\n"
    "fn selected_check_rejects_bad_input() {\n"
    "    assert!(true);\n"
    "}\n"
)


def _make_repo(
    tmp_path: Path,
    regression_source: str | None,
    *,
    regression_file: str = _PYTEST_REGRESSION_REL,
    gherkin_slice: str = "slice-01",
) -> Path:
    repo = tmp_path / "repo"
    feature_dir = repo / "docs" / "feature" / _FEATURE_ID
    feature_dir.mkdir(parents=True)
    (feature_dir / "feature-delta.md").write_text(
        "# Feature Delta: selected regression file\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
        "| slice-01 | Earlier Gherkin journey remains available | pending | | |\n"
        "| slice-04 | Selected regression check is assessed | pending | | |\n",
        encoding="utf-8",
    )
    feature_file = repo / "tests" / "acceptance" / "other_slices.feature"
    feature_file.parent.mkdir(parents=True)
    feature_file.write_text(
        f"@feature-{_FEATURE_ID}\n"
        "Feature: Earlier journey\n\n"
        f"  @{gherkin_slice}\n"
        "  Scenario: Earlier journey remains available\n"
        "    Given a maintainer has an earlier journey\n"
        "    When the maintainer checks that journey\n"
        "    Then the journey remains available\n",
        encoding="utf-8",
    )
    if regression_source is not None:
        regression_path = repo / regression_file
        regression_path.parent.mkdir(parents=True)
        regression_path.write_text(regression_source, encoding="utf-8")
    return repo


def _write_fresh_red_seal(repo: Path, regression_file: str) -> None:
    regression_path = (repo / regression_file).resolve()
    seal = _seal_path(repo.resolve(), regression_path)
    seal.parent.mkdir(parents=True, exist_ok=True)
    seal.write_text(
        json.dumps(
            {
                "test_file": regression_file,
                "content_sha256": hashlib.sha256(regression_path.read_bytes()).hexdigest(),
                "outcomes": {"selected::test_selected_check_rejects_bad_input": "fail"},
            }
        ),
        encoding="utf-8",
    )


def _write_approved_native_verdict(repo: Path, regression_file: str) -> None:
    regression_path = repo / regression_file
    ledger = repo / ".nwave" / "telemetry" / "atdd-pure" / f"{_FEATURE_ID}.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(
        json.dumps(
            {
                "event": "ATReviewVerdict",
                "slice_id": "slice-04",
                "verdict": "APPROVED",
                "at_ids": ["AT-1"],
                "at_content_hash": hashlib.sha256(regression_path.read_bytes()).hexdigest(),
            }
        ),
        encoding="utf-8",
    )


def _run_gate(
    repo: Path, capsys: pytest.CaptureFixture[str], *, at_kind: str, regression_file: str | None
) -> tuple[int, dict[str, object]]:
    argv = [
        "--feature-id",
        _FEATURE_ID,
        "--entering-slice",
        "slice-04"
        if at_kind in ("pytest-regression", "native-regression")
        else "slice-01",
        "--repo-root",
        str(repo),
        "--at-kind",
        at_kind,
    ]
    if regression_file is not None:
        argv.extend(["--regression-test-file", regression_file])
    exit_code = carpaccio_slice_gate_main(argv)
    stdout = capsys.readouterr().out
    payload = next(
        (json.loads(line) for line in stdout.splitlines() if line.startswith("{")),
        {},
    )
    return exit_code, payload


@pytest.mark.negative_at
@pytest.mark.parametrize(
    (
        "regression_source",
        "regression_file",
        "at_kind",
        "gherkin_slice",
        "expected",
    ),
    [
        (
            _VALID_REGRESSION,
            _PYTEST_REGRESSION_REL,
            "pytest-regression",
            "slice-01",
            (0, "SliceCleared", None),
        ),
        (
            _VALID_NATIVE_REGRESSION,
            _NATIVE_REGRESSION_REL,
            "native-regression",
            "slice-01",
            (0, "SliceCleared", None),
        ),
        (
            _VALID_NATIVE_REGRESSION,
            _NATIVE_REGRESSION_REL,
            "native-regression",
            "slice-04",
            (2, "MalformedInput", "mixed AT-discovery mode"),
        ),
        (
            _VALID_REGRESSION,
            _PYTEST_REGRESSION_REL,
            "pytest-regression",
            "slice-04",
            (2, "MalformedInput", "mixed AT-discovery mode"),
        ),
        (
            None,
            _PYTEST_REGRESSION_REL,
            "pytest-regression",
            "slice-01",
            (2, "MalformedInput", "the pytest regression-test file"),
        ),
        (
            "def test_selected_check(:\n",
            _PYTEST_REGRESSION_REL,
            "pytest-regression",
            "slice-01",
            (2, "MalformedInput", "the pytest regression-test file"),
        ),
        (
            _VALID_REGRESSION,
            None,
            "gherkin",
            "slice-01",
            (45, "ATReviewGateRejected", "absent"),
        ),
    ],
    ids=(
        "pytest-with-other-journey",
        "native-with-other-journey",
        "native-with-same-journey",
        "pytest-with-same-journey",
        "missing-selected-file",
        "malformed-selected-file",
        "gherkin-route",
    ),
)
def test_selected_regression_file_respects_gherkin_discovery_boundaries(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    regression_source: str | None,
    regression_file: str | None,
    at_kind: str,
    gherkin_slice: str,
    expected: tuple[int, str, str | None],
) -> None:
    """A selected regression file ignores only another journey's Gherkin ATs.

    A same-journey Gherkin AT remains a fail-closed mixed discovery error;
    invalid selected files and the independent Gherkin route also still refuse.

    CONTRACT_SHAPE: bounded-change
    """
    repo = _make_repo(
        tmp_path,
        regression_source,
        regression_file=regression_file or _PYTEST_REGRESSION_REL,
        gherkin_slice=gherkin_slice,
    )
    if regression_source == _VALID_REGRESSION and at_kind == "pytest-regression":
        _write_fresh_red_seal(repo, regression_file or _PYTEST_REGRESSION_REL)
    if at_kind == "native-regression":
        assert regression_file is not None
        _write_approved_native_verdict(repo, regression_file)

    exit_code, payload = _run_gate(
        repo, capsys, at_kind=at_kind, regression_file=regression_file
    )
    expected_exit, expected_event, expected_reason = expected

    assert (exit_code, payload.get("event"), payload.get("cause") or payload.get("reason")) == (
        expected_exit,
        expected_event,
        expected_reason,
    ), (
        "the explicit pytest/native regression file must be assessed when another "
        "slice owns Gherkin scenarios, but must refuse mixed discovery when its own "
        "slice has a Gherkin AT; missing or malformed selected files must remain "
        "unusable and the Gherkin route must keep its review behaviour. The observed "
        "gate result was "
        f"exit={exit_code}, payload={payload!r}; make the explicit regression path "
        "ignore unrelated Gherkin scenarios without weakening file validation."
    )
