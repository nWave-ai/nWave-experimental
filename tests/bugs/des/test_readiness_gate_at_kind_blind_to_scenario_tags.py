"""Regression: `des verify-readiness-pre-dispatch` is structurally BLIND to
`at_kind` -- it can never clear a pytest-regression slice on its mechanical
RED->GREEN seal, and its own rejection HOW advertises flags the CLI does not
accept.

RCA (done -- not re-derived here):

  1. `_check_scenario_slice_tags` (`src/des/cli/verify_readiness_pre_dispatch.py`
     ~line 395) has two legs. Leg (a) is the Gherkin tag-HYGIENE scan (kept,
     correct, kind-independent). Leg (b) (~lines 445-459) delegates to
     `read_feature_files` / `parse_scenarios` / `_slice_scenarios` and REFUSES
     whenever the entering slice owns no matching Gherkin scenario -- with NO
     at_kind escape whatsoever. The vacuous-truth branch only fires when the
     FEATURE owns zero `.feature` files anywhere, so a pytest-regression slice
     living beside ANY Gherkin-tagged sibling slice is falsely refused.
  2. `_build_parser()` (~line 1100) defines NO `--at-kind` / no
     `--regression-test-file` option at all -- the gate cannot even be TOLD
     the entering slice is pytest-regression.
  3. `carpaccio_intercept._real_readiness_runner` (~line 353) closes over only
     `lane` / `lane_justification`; its sibling `_real_carpaccio_runner`
     (~line 231) already accepts + forwards `at_kind` / `regression_test_file`.
     The dispatch-prompt marker IS already parsed (`_parse_at_kind_from_prompt`,
     ~line 332) and threaded into the carpaccio runner (~line 1150-1153) but
     NEVER into the readiness runner (~line 1155-1157).
  4. The `scenario_slice_tags` rejection HOW is copied verbatim from
     `carpaccio_format._no_scenarios_rejection`, which correctly advertises
     `--at-kind pytest-regression --regression-test-file <path>` for
     `des carpaccio-slice-gate` (a real option there) but INEXPRESSIBLE for
     `des verify-readiness-pre-dispatch`, which accepts neither flag -- a
     lying rejection message (GDP-3/GDP-4).

Driving port (Mandate 16): every AT below drives
`des.cli.verify_readiness_pre_dispatch.main(argv)` (the real
`des verify-readiness-pre-dispatch` composition root) in-process, tolerating
today's `SystemExit` from argparse rejecting the not-yet-existent flags, plus
`des.adapters.drivers.hooks.carpaccio_intercept._real_readiness_runner` (the
real runner-builder the intercept invokes) for the wiring fact. The RED seal
fixture is hand-crafted in the P0.2 producer's own record shape via its
`_seal_path` helper (mirrors `tests/des/unit/cli/test_carpaccio_mechanical_seal.py`)
-- hermetic, no pytest-in-pytest.

RED-for-right-reason: every core assertion below fails today with a genuine
semantic `AssertionError` tied to one of the four RCA facts above -- never an
import/collection error.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from des.adapters.drivers.hooks import carpaccio_intercept as ci
from des.cli import verify_readiness_pre_dispatch as readiness_gate
from des.cli.verify_red_green import _seal_path


_FEATURE_ID = "fix-readiness-gate-at-kind-blind-scenario-tags-fixture"
_SLICE_GHERKIN_WITH_SCENARIO = "slice-01"
_SLICE_GHERKIN_WITHOUT_SCENARIO = "slice-02"
_SLICE_PYTEST_REGRESSION = "slice-03"
_REGRESSION_REL = "tests/regression/test_fix_at_kind.py"
_INV_SCENARIO_TAGS = "scenario_slice_tags"

_REGRESSION_SRC = "def test_fix_applies():\n    assert True\n"


# --- fixture builders --------------------------------------------------------


def _author_feature_delta(repo_root: Path, feature_id: str) -> None:
    """Three Slice-Plan rows: a Gherkin slice WITH its scenario (slice-01), a
    Gherkin slice owning NONE (slice-02, the leg-(b) guard), and a
    pytest-regression slice (slice-03) evidenced by a mechanical RED seal."""
    workspace = repo_root / "docs" / "feature" / feature_id
    workspace.mkdir(parents=True)
    (workspace / "feature-delta.md").write_text(
        f"# Feature Delta: {feature_id}\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement |\n"
        "|---|---|\n"
        f"| {_SLICE_GHERKIN_WITH_SCENARIO} | owns the only authored Gherkin scenario |\n"
        f"| {_SLICE_GHERKIN_WITHOUT_SCENARIO} | Gherkin slice owning zero scenarios |\n"
        f"| {_SLICE_PYTEST_REGRESSION} | pytest-regression slice, mechanical-seal evidenced |\n\n"
        "## Reuse Analysis\n\n"
        "Reuse-Analysis: no-overlap\n\n"
        "## Test Reuse & Consolidation Analysis\n\n"
        "Test-Reuse-Analysis: methodology-exempt\n"
    )


def _author_gherkin_scenario_tagged_slice_01(repo_root: Path, feature_id: str) -> None:
    """ONE `.feature` file, self-identifying via `@feature-{feature_id}` AND
    living under `tests/` with `feature_id` in its path -- discoverable by
    BOTH the legacy hygiene leg and the per-slice ownership leg. Its ONE
    Scenario carries `@slice-01` only -- `slice-02` owns zero matching."""
    acceptance_dir = repo_root / "tests" / "bugs" / "des" / "acceptance" / feature_id
    acceptance_dir.mkdir(parents=True)
    (acceptance_dir / "only_slice_01.feature").write_text(
        f"@feature-{feature_id}\n"
        "Feature: Only slice-01 owns an authored scenario\n\n"
        f"  @{_SLICE_GHERKIN_WITH_SCENARIO}\n"
        "  Scenario: A scenario belonging exclusively to slice-01\n"
        "    Given a precondition slice-01 sets up\n"
        "    When the slice-01 behavior runs\n"
        "    Then the slice-01 outcome is observed\n"
    )


def _author_regression_test_file(repo_root: Path) -> Path:
    regression = repo_root / _REGRESSION_REL
    regression.parent.mkdir(parents=True, exist_ok=True)
    regression.write_text(_REGRESSION_SRC, encoding="utf-8")
    return regression


def _write_fresh_red_seal(repo_root: Path, regression_file: Path) -> None:
    """Craft the RedObserved seal in the P0.2 producer's exact record shape
    (mirrors `test_carpaccio_mechanical_seal.py::_write_red_seal`) --
    content_sha256 matching the file's CURRENT bytes."""
    seal = _seal_path(repo_root.resolve(), regression_file.resolve())
    seal.parent.mkdir(parents=True, exist_ok=True)
    seal.write_text(
        json.dumps(
            {
                "test_file": _REGRESSION_REL,
                "content_sha256": hashlib.sha256(
                    regression_file.read_bytes()
                ).hexdigest(),
                "outcomes": {"t::test_fix_applies": "fail"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )


@pytest.fixture
def hermetic_repo(tmp_path: Path) -> Path:
    """A hermetic repo_root: a bare `.git` marker (both gates are git-free)
    plus a mixed-kind feature-delta, ONE Gherkin `.feature` file, and a
    regression test file (seal written per-test, not pre-baked here since
    (a) needs it fresh and (c) needs it absent/stale)."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    _author_feature_delta(repo_root, _FEATURE_ID)
    _author_gherkin_scenario_tagged_slice_01(repo_root, _FEATURE_ID)
    _author_regression_test_file(repo_root)
    return repo_root


def _run_readiness(
    repo_root: Path, feature_id: str, slice_id: str, *extra_args: str
) -> tuple[int, dict]:
    """Invoke the gate's `main(argv)` in-process, tolerating today's
    `SystemExit` from argparse rejecting not-yet-existent flags (RCA fact 2)
    -- a real, diagnosed-cause exit, never an import/collection error."""
    argv = [
        "--feature-id",
        feature_id,
        "--slice-id",
        slice_id,
        "--repo-root",
        str(repo_root),
        *extra_args,
    ]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            code = readiness_gate.main(argv)
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 2
    line = next(
        (
            ln
            for ln in reversed(out.getvalue().splitlines())
            if ln.strip().startswith("{")
        ),
        "{}",
    )
    return code, json.loads(line)


def _invariant(report: dict, invariant_id: str) -> dict:
    for inv in report.get("invariants", []):
        if inv["id"] == invariant_id:
            return inv
    raise AssertionError(
        f"invariant {invariant_id!r} missing from report entirely -- the "
        f"gate must always emit every invariant it evaluates. observed "
        f"report={report}"
    )


# --- AT-1 (core, RED today -- the defect itself) -----------------------------


def test_pytest_regression_slice_with_fresh_red_seal_clears_scenario_tags(
    hermetic_repo: Path,
) -> None:
    """A pytest-regression slice (slice-03) whose regression test file carries
    a FRESH content-matching RED seal must CLEAR `scenario_slice_tags` --
    readiness must not force a `.feature` file onto a slice that legitimately
    proves itself via the mechanical seal.

    RED today: `_build_parser()` defines no `--at-kind` /
    `--regression-test-file` option at all (RCA fact 2), so this invocation
    cannot even reach `_check_scenario_slice_tags` -- argparse rejects the
    unrecognized flags and the gate exits non-zero without a verdict.

    CONTRACT_SHAPE: bounded-change
    """
    regression_file = hermetic_repo / _REGRESSION_REL
    _write_fresh_red_seal(hermetic_repo, regression_file)

    code, report = _run_readiness(
        hermetic_repo,
        _FEATURE_ID,
        _SLICE_PYTEST_REGRESSION,
        "--at-kind",
        "pytest-regression",
        "--regression-test-file",
        _REGRESSION_REL,
    )

    assert code == 0 and report.get("verdict") == "cleared", (
        "a pytest-regression slice with a FRESH content-matching RED seal "
        "must CLEAR readiness. THE BUG: verify_readiness_pre_dispatch's "
        "argparse has no --at-kind/--regression-test-file option at all, so "
        f"this invocation cannot even reach the invariant. observed "
        f"code={code}, report={report}"
    )
    scenario_tags_inv = _invariant(report, _INV_SCENARIO_TAGS)
    assert scenario_tags_inv["satisfied"] is True, (
        "scenario_slice_tags must be satisfied for a pytest-regression slice "
        f"evidenced by a fresh RED seal. observed={scenario_tags_inv}"
    )


# --- AT-2 (negative guard -- leg (b) must not be blanket-disabled) ----------


def test_gherkin_slice_without_its_tag_still_refused_beside_a_regression_slice(
    hermetic_repo: Path,
) -> None:
    """slice-02 (Gherkin) owns ZERO scenarios tagged `@slice-02` -- it must
    still be REFUSED even though the SAME feature also carries a legitimate
    pytest-regression slice (slice-03). The fix must be at_kind-conditional
    PER SLICE ("this slice declares pytest-regression AND proves it"), never
    "this feature has mixed kinds, skip the Gherkin check everywhere."

    CONTRACT_SHAPE: bounded-change
    """
    code, report = _run_readiness(
        hermetic_repo, _FEATURE_ID, _SLICE_GHERKIN_WITHOUT_SCENARIO
    )

    assert report.get("verdict") != "cleared" and code != 0, (
        "slice-02 owns zero scenarios tagged @slice-02 -- it must be refused "
        "regardless of a sibling pytest-regression slice existing in the "
        f"same feature. observed verdict={report.get('verdict')!r}, "
        f"code={code}, invariants={report.get('invariants')}"
    )
    scenario_tags_inv = _invariant(report, _INV_SCENARIO_TAGS)
    assert scenario_tags_inv["satisfied"] is False, (
        "scenario_slice_tags must stay satisfied: false for slice-02 -- a "
        "correct at_kind-conditional fix scopes the escape to the DECLARING "
        f"slice, never the whole feature. observed={scenario_tags_inv}"
    )


# --- AT-3 (negative -- the escape is earned by evidence, not a label) ------


@pytest.mark.negative_at
def test_declaring_pytest_regression_without_a_fresh_seal_never_clears(
    hermetic_repo: Path,
) -> None:
    """Declaring `--at-kind pytest-regression` is not, by itself, sufficient
    evidence. Two failing sub-cases: (1) no RED seal recorded at all, and
    (2) a RED seal recorded for OLDER content, invalidated by a subsequent
    edit (the crafter-touched-the-test class). Both must be REFUSED --
    claiming the kind never substitutes for the mechanical proof.

    CONTRACT_SHAPE: bounded-change
    """
    # Sub-case 1: no seal recorded at all.
    code, report = _run_readiness(
        hermetic_repo,
        _FEATURE_ID,
        _SLICE_PYTEST_REGRESSION,
        "--at-kind",
        "pytest-regression",
        "--regression-test-file",
        _REGRESSION_REL,
    )
    assert report.get("verdict") != "cleared" and code != 0, (
        "a pytest-regression slice with NO recorded RED seal must be "
        f"refused, not cleared on the bare claim. observed verdict="
        f"{report.get('verdict')!r}, code={code}"
    )

    # Sub-case 2: a seal exists but for STALE (pre-edit) content.
    regression_file = hermetic_repo / _REGRESSION_REL
    _write_fresh_red_seal(hermetic_repo, regression_file)
    regression_file.write_text(
        regression_file.read_text(encoding="utf-8") + "\n# tampered after RED\n",
        encoding="utf-8",
    )
    stale_code, stale_report = _run_readiness(
        hermetic_repo,
        _FEATURE_ID,
        _SLICE_PYTEST_REGRESSION,
        "--at-kind",
        "pytest-regression",
        "--regression-test-file",
        _REGRESSION_REL,
    )
    assert stale_report.get("verdict") != "cleared" and stale_code != 0, (
        "a RED seal for content that no longer matches the current test "
        "file must not clear the slice -- the crafter-touched-the-test "
        f"class. observed verdict={stale_report.get('verdict')!r}, "
        f"code={stale_code}"
    )


# --- AT-4 (core, RED today -- the HOW must be executable, not decorative) --


_CODE_SPAN_RE = re.compile(r"`([^`]*)`")
_FLAG_RE = re.compile(r"--[a-z][a-z-]*")
_NAMES_OTHER_DES_COMMAND_RE = re.compile(
    r"^des\s+(?!verify-readiness-pre-dispatch\b)\S+"
)


def _flags_claimed_for_this_command(remediation: str) -> set[str]:
    """Extract flags the remediation claims are usable on THIS invocation.

    Scoped to backtick code-spans (the remediation's own convention for
    "run this"). A span explicitly naming a DIFFERENT `des <subcommand>`
    (e.g. `` `des verify-red-green --record-red` ``) is a legitimately
    different tool's flag and is excluded -- only a bare-flag span with no
    such prefix reads as "pass this to the command that just rejected you."
    """
    claimed: set[str] = set()
    for span in _CODE_SPAN_RE.findall(remediation):
        if _NAMES_OTHER_DES_COMMAND_RE.match(span.strip()):
            continue
        claimed.update(_FLAG_RE.findall(span))
    return claimed


def test_scenario_tags_remediation_names_only_flags_this_cli_accepts(
    hermetic_repo: Path,
) -> None:
    """The scenario_slice_tags remediation must name ONLY flags THIS CLI's own
    argparse parser accepts. THE BUG (RCA fact 4): the remediation is copied
    verbatim from carpaccio's `_no_scenarios_rejection`, which advertises
    `--at-kind pytest-regression --regression-test-file <path>` -- real
    options of `des carpaccio-slice-gate`, but `_build_parser()`
    (verify_readiness_pre_dispatch.py) defines neither. A maintainer
    following the HOW literally gets the identical rejection back (a lying
    rejection message, GDP-3/GDP-4).

    CONTRACT_SHAPE: bounded-change
    """
    code, report = _run_readiness(
        hermetic_repo, _FEATURE_ID, _SLICE_GHERKIN_WITHOUT_SCENARIO
    )
    assert code != 0  # control: this is the leg-(b) rejection path
    scenario_tags_inv = _invariant(report, _INV_SCENARIO_TAGS)
    remediation = scenario_tags_inv.get("remediation") or ""
    assert remediation, (
        "the scenario_slice_tags refusal must carry a remediation string to "
        f"mechanically scan. observed={scenario_tags_inv}"
    )

    claimed = _flags_claimed_for_this_command(remediation)
    assert claimed, (
        "expected the remediation to claim >=1 flag as usable on THIS "
        f"command's own invocation. remediation={remediation!r}"
    )

    parser = readiness_gate._build_parser()
    real_options = {opt for action in parser._actions for opt in action.option_strings}

    unreal = sorted(claimed - real_options)
    assert not unreal, (
        "the remediation must name ONLY flags this CLI's OWN parser accepts "
        f"-- THE BUG: it advertises {unreal}, which `des "
        "verify-readiness-pre-dispatch` rejects outright (a lying rejection "
        f"message, GDP-3/GDP-4). claimed={sorted(claimed)}, "
        f"real_options={sorted(real_options)}"
    )


# --- AT-5 (core, RED today -- the intercept wiring gap) ---------------------


def test_readiness_runner_threads_at_kind_args(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mirrors `test_readiness_runner_threads_lane_args`
    (test_carpaccio_intercept_bugfix_lane_wiring.py) for the at_kind axis.

    THE BUG (RCA fact 3): `_real_readiness_runner` closes over only `lane` /
    `lane_justification` -- it has NO `at_kind`/`regression_test_file`
    parameter at all, unlike its sibling `_real_carpaccio_runner` (which
    already accepts + forwards them). This call raises `TypeError` today --
    a real, diagnosed-cause failure (the exact missing parameter RCA fact 3
    names), never an import/collection error.

    CONTRACT_SHAPE: bounded-change
    """
    recorded: dict[str, tuple] = {}

    def fake_spawn(*args, **kwargs):
        recorded["args"] = args
        completed = MagicMock()
        completed.returncode = 0
        completed.stdout = '{"event": "ReadinessVerified", "verdict": "cleared"}'
        return completed

    monkeypatch.setattr(ci, "des_spawn", fake_spawn)

    runner = ci._real_readiness_runner(
        tmp_path, at_kind="pytest-regression", regression_test_file=_REGRESSION_REL
    )
    runner("synthetic-feature", _SLICE_PYTEST_REGRESSION)

    args = list(recorded["args"])
    assert "--at-kind" in args and "pytest-regression" in args, (
        "a readiness runner built with at_kind='pytest-regression' must pass "
        "`--at-kind pytest-regression` to the gate subprocess. des_spawn "
        f"args={args}"
    )
    assert "--regression-test-file" in args and _REGRESSION_REL in args, (
        "the runner must forward the regression test file path to the gate "
        f"subprocess too. des_spawn args={args}"
    )
