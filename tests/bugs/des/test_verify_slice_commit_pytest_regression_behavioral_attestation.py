"""Regression (#13, Ale-ratified: "behavioral-attestation path"): `des
verify-slice-commit --feature-id`'s E2 leg (the feature-scoped contract gate)
cannot attest a pytest-regression bugfix slice, so genuine shipped fixes
never earn `SliceCommitVerified` -- audit-core false-negative, not a
correctness bug (the honesty direction that matters here is "never falsely
GREEN", not "never falsely RED", but a systematically unattestable class of
real, tested, clean commits erodes the ledger's value as an audit trail).

Charter: task #13, `docs/product/expectations/behavioral-attestation-verify-
slice-commit/` (if/when a charter exists for this fix).

Found in `src/des/cli/verify_slice_commit_completeness.py`
`_run_verify_then_record()` E2 leg (`:537-577`): for EVERY listed slice it
unconditionally spawns `_run_contract_gate` -- the feature-scoped Gherkin/
pytest contract-gate subprocess (`run_contract_gate --feature-id`). A
pytest-regression bugfix slice (marked at ENTRY via the `DES-AT-KIND: pytest-
regression` / `DES-REGRESSION-TEST-FILE` dispatch markers,
`src/des/cli/dispatch.py:174-176`) has no feature contract structure for that
gate to resolve -- it exits non-zero -> `SliceCommitRefused` -- even when the
slice's OWN regression test genuinely, verifiably passes on the committed
tree. 7 real shipped fixes (session tasks #41/#42/#38/#43 + 3 sister fixes)
never earned `SliceCommitVerified` for exactly this reason.

The fix direction (this AT's contract, NOT implemented here -- test-authoring
only, zero `src/` edits): add an ADDITIVE `--at-kind {gherkin,pytest-
regression}` (default `gherkin`, byte-identical for every existing caller)
plus `--regression-test-file <path>` CLI pair to `verify_slice_commit_
completeness._build_parser()`, mirroring the SAME flag names/choices already
shipped on `carpaccio_slice_gate.py` / `at_review_verdict.py` /
`dispatch.py`. When `at_kind == "pytest-regression"`, the E2 leg of
`_run_verify_then_record` REPLACES the `_run_contract_gate` subprocess with a
BEHAVIORAL attestation: it actually RUNS the declared `regression_test_file`
(e.g. `sys.executable -m pytest <file> -q`, mirroring the execution-observing
pattern already proven in `verify_red_green.py`'s `_run_and_collect`) on the
committed tree and uses ITS exit code as the E2 result. A file that does not
exist, or that cannot be collected/run, must degrade LOUD (refused or
indeterminate) -- NEVER a silent `SliceCommitVerified` on presence alone
(the false-green class this audit-core change must not introduce). The
existing Gherkin/default `_run_contract_gate` path is UNCHANGED for every
caller that omits `--at-kind` or passes `--at-kind gherkin` -- purely
additive, low blast-radius. E1 (completeness) needs NO change: the pytest
head-comment-tag discovery (`# @feature-{id}` / `# @{slice-NN}`,
F-FEATURE-END-COMPLETENESS-ORACLE-PYTEST-BLIND, already shipped in
`des.application.slice_at_completeness.feature_files_for_slice`) already
recognizes a head-tagged regression test file as the slice's delivered AT,
so the SAME regression file doubles as both the E1 artifact and the E2
behavioral witness.

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process default):
the REAL `des.cli.verify_slice_commit_completeness.main()` CLI driver,
captured via `capsys` -- mirrors every sibling regression AT in this
directory (`test_slice_commit_refused_names_how.py`,
`test_commit_slice_writes_verified_record.py`). Because the new
`--at-kind`/`--regression-test-file` flags do not exist on `main()` today,
driving them pre-fix raises `SystemExit(2)` (argparse "unrecognized
arguments") BEFORE any repo/ledger access -- `_run_behavioral_verify_slice_
commit` below catches that `SystemExit` and folds its code into the SAME
`(exit_code, payload)` shape the post-fix call returns, so every assertion is
a genuine, semantic comparison against the verdict/ledger, never an
uncaught-exception "pass".

Fixtures: real tmp git repos (raw `git` subprocess, no mocking of git). The
regression test file IS the AT (pytest-regression convention) -- a real,
collectible `test_*.py` module head-tagged `# @feature-{id}` / `# @{slice-
NN}`, containing a genuinely passing or genuinely failing `test_*` function
so the E2 behavioral run is execution-observed, not asserted.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli import verify_slice_commit_completeness as vscc


_SLICE_ID = "slice-01"
_REGRESSION_FILE_REL = "tests/bugs/fixture/test_pytest_regression_fixture.py"

_FEATURE_ID_POS = "vscc-pytest-regression-attestation-pos"
_FEATURE_ID_FAIL = "vscc-pytest-regression-attestation-fail"
_FEATURE_ID_MISSING = "vscc-pytest-regression-attestation-missing"
_FEATURE_ID_ADDITIVITY = "vscc-pytest-regression-attestation-additivity"


# ---------------------------------------------------------------------------
# Shared fixture builders
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
    repo: Path, feature_id: str, slice_id: str, *, passing: bool
) -> Path:
    """A real, pytest-collectible regression test file, head-tagged for the
    SAME `feature_id`/`slice_id` E1 already discovers via `# @feature-{id}` /
    `# @{slice-NN}` head-comment tags -- the fixture doubles as both the E1
    delivered-AT artifact and the E2 behavioral witness.
    """
    path = repo / _REGRESSION_FILE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    if passing:
        body = "def test_the_regression_stays_fixed():\n    assert 1 + 1 == 2\n"
    else:
        body = (
            "def test_the_regression_is_still_broken():\n"
            "    assert 1 + 1 == 3, 'the regression is NOT fixed'\n"
        )
    path.write_text(
        f"# @feature-{feature_id}\n# @{slice_id}\n{body}",
        encoding="utf-8",
    )
    return path


def _commit_regression_file(repo: Path, slice_id: str) -> None:
    _git(repo, "add", "-A")
    _git(
        repo,
        "commit",
        "-q",
        "-m",
        f"fix(slice): pytest-regression fix\n\nSlice-Id: {slice_id}",
    )


def _run_behavioral_verify_slice_commit(
    repo: Path,
    feature_id: str,
    regression_test_file_rel: str,
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, dict[str, object]]:
    """Drive the REAL `des verify-slice-commit` CLI (`main()`) in-process with
    the NEW `--at-kind pytest-regression --regression-test-file <path>` pair,
    capturing its single-line JSON payload via `capsys`.

    Today (pre-fix) these flags are unrecognized -- argparse raises
    `SystemExit(2)` before any repo access. That `SystemExit` is caught here
    and its code folded into the SAME `(exit_code, payload)` return shape the
    post-fix call produces (`payload={}` when nothing was ever emitted), so
    every caller's assertion is a genuine comparison against the verdict, not
    a crash masquerading as a failing test.
    """
    try:
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
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 1
    stdout = capsys.readouterr().out
    json_lines = [ln for ln in stdout.splitlines() if ln.strip().startswith("{")]
    payload: dict[str, object] = json.loads(json_lines[-1]) if json_lines else {}
    return exit_code, payload


# ===========================================================================
# 1. POSITIVE -- active-RED today
# ===========================================================================


def test_pytest_regression_slice_with_passing_regression_test_is_verified_behaviorally(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A pytest-regression slice whose regression test PASSES on the
    committed tree must earn `SliceCommitVerified` via the E2 BEHAVIORAL
    attestation path -- the gate actually runs the regression test and
    observes the pass, in place of the feature-scoped contract gate that
    cannot resolve a pytest-regression bugfix's structure.

    RED for the right reason today: `--at-kind pytest-regression` does not
    exist on `verify-slice-commit` yet, so the call raises `SystemExit(2)`
    (folded to `exit_code=2`, `payload={}`) -- a semantic mismatch against
    the expected `exit_code == 0` / `SliceCommitVerified` verdict, not a
    collection or import error.
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    _write_regression_test(repo, _FEATURE_ID_POS, _SLICE_ID, passing=True)
    _commit_regression_file(repo, _SLICE_ID)

    exit_code, payload = _run_behavioral_verify_slice_commit(
        repo, _FEATURE_ID_POS, _REGRESSION_FILE_REL, capsys
    )

    assert exit_code == 0, (
        "a pytest-regression slice whose regression test genuinely PASSES on "
        "the committed tree must clear the E2 behavioral attestation path -- "
        f"got exit_code={exit_code!r}, payload={payload!r}"
    )
    assert payload.get("event") == "SliceCommitVerified", payload

    verified = AtCompletionLedger(_FEATURE_ID_POS, repo).verified_slices()
    assert _SLICE_ID in verified, (
        "the E2 behavioral-attestation path must record a `SliceCommitVerified` "
        "ledger entry for a pytest-regression slice whose regression test "
        f"genuinely passes -- observed verified_slices={sorted(verified)!r}"
    )


# ===========================================================================
# 2. HONESTY (negative, CRITICAL) -- must hold BEFORE and AFTER the fix
# ===========================================================================


@pytest.mark.negative_at
def test_a_failing_regression_slice_is_never_verified_behaviorally(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The false-green guard: a pytest-regression slice whose regression test
    genuinely FAILS on the committed tree must NEVER earn `SliceCommitVerified`
    -- neither today (the flags don't exist, so nothing can verify) nor after
    the fix (the behavioral run observes the failure and refuses). This is
    the single most important assertion in this AT set -- a broken slice
    reaching the audit ledger as verified would be a false-green in the audit
    core itself.
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    _write_regression_test(repo, _FEATURE_ID_FAIL, _SLICE_ID, passing=False)
    _commit_regression_file(repo, _SLICE_ID)

    exit_code, payload = _run_behavioral_verify_slice_commit(
        repo, _FEATURE_ID_FAIL, _REGRESSION_FILE_REL, capsys
    )

    assert exit_code != 0, (
        "a pytest-regression slice whose regression test FAILS on the "
        f"committed tree must never clear -- got exit_code={exit_code!r}, "
        f"payload={payload!r}"
    )
    assert payload.get("event") != "SliceCommitVerified", (
        "a broken pytest-regression slice earned `SliceCommitVerified` -- "
        f"the exact false-green the honesty invariant exists to prevent: "
        f"payload={payload!r}"
    )

    verified = AtCompletionLedger(_FEATURE_ID_FAIL, repo).verified_slices()
    assert _SLICE_ID not in verified, (
        "a pytest-regression slice whose regression test genuinely fails must "
        "NEVER earn a fabricated `SliceCommitVerified` ledger record -- "
        f"observed verified_slices={sorted(verified)!r}"
    )


# ===========================================================================
# 3. HONESTY (negative) -- execution-observing, not presence-trusting
# ===========================================================================


@pytest.mark.negative_at
def test_a_declared_but_missing_regression_test_file_is_never_verified_behaviorally(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A pytest-regression slice that DECLARES a `--regression-test-file`
    which does not exist on the committed tree must NEVER earn
    `SliceCommitVerified` -- it must degrade LOUD (refused or indeterminate),
    never a silent pass. This guards against a marker/presence-trust
    implementation shortcut (e.g. "the flag was given, so trust it") in place
    of the mandated execution-observing behavior (actually RUN the file).

    Green both BEFORE (the flags don't exist yet) and AFTER (a correct
    implementation cannot run a nonexistent file and must refuse) the fix.
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    (repo / "README.md").write_text("fixture repo\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(
        repo,
        "commit",
        "-q",
        "-m",
        f"fix(slice): pytest-regression fix\n\nSlice-Id: {_SLICE_ID}",
    )
    missing_rel_path = "tests/bugs/fixture/test_never_written.py"

    exit_code, payload = _run_behavioral_verify_slice_commit(
        repo, _FEATURE_ID_MISSING, missing_rel_path, capsys
    )

    assert exit_code != 0, (
        "a pytest-regression slice declaring a `--regression-test-file` that "
        "does not exist on the committed tree must never clear -- got "
        f"exit_code={exit_code!r}, payload={payload!r}"
    )
    assert payload.get("event") != "SliceCommitVerified", payload

    verified = AtCompletionLedger(_FEATURE_ID_MISSING, repo).verified_slices()
    assert _SLICE_ID not in verified, (
        "a declared-but-absent regression-test-file must degrade LOUD "
        "(refused/indeterminate), never a silent `SliceCommitVerified` -- "
        f"observed verified_slices={sorted(verified)!r}"
    )


# ===========================================================================
# 4. ADDITIVITY guard -- NO-REGRESSION, must stay green before AND after
# ===========================================================================


def test_non_pytest_regression_feature_still_clears_via_the_feature_scoped_contract_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A feature that never passes `--at-kind` (the default, Gherkin path)
    must keep clearing through the EXISTING `_run_contract_gate` subprocess
    path, byte-identical -- the behavioral-attestation addition must not
    touch this path. Mirrors the proven GREEN precedent
    `tests/des/integration/test_verify_slice_commit_examine_gate.py::
    test_verify_slice_commit_unarmed_without_charter`. Must stay green both
    BEFORE and AFTER the fix.
    """
    monkeypatch.setattr(vscc, "_run_contract_gate", lambda *a, **k: 0)
    repo = tmp_path / "repo"
    _git_init(repo)
    feature_id = _FEATURE_ID_ADDITIVITY
    feat_path = repo / "tests" / "acceptance" / "fixture_slice.feature"
    feat_path.parent.mkdir(parents=True, exist_ok=True)
    feat_path.write_text(
        f"@feature-{feature_id}\n"
        "Feature: fixture feature\n\n"
        f"  @{_SLICE_ID}\n"
        "  Scenario: fixture scenario\n"
        "    Given a fixture precondition\n"
        "    When the fixture action occurs\n"
        "    Then the fixture outcome holds\n",
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(
        repo,
        "commit",
        "-q",
        "-m",
        f"feat(slice): behaviour\n\nSlice-Id: {_SLICE_ID}",
    )

    exit_code = vscc.main(
        ["--repo", str(repo), "--commit", "HEAD", "--feature-id", feature_id]
    )
    stdout = capsys.readouterr().out
    json_lines = [ln for ln in stdout.splitlines() if ln.strip().startswith("{")]
    assert json_lines, f"expected a JSON payload line on stdout, got: {stdout!r}"
    payload = json.loads(json_lines[-1])

    assert exit_code == 0, (
        "a NON-pytest-regression feature (default at_kind, no new flags "
        "involved) must still clear via the pre-existing feature-scoped "
        f"contract-gate path -- exit_code={exit_code!r}, payload={payload!r}"
    )
    assert payload.get("event") == "SliceCommitVerified", payload

    verified = AtCompletionLedger(feature_id, repo).verified_slices()
    assert _SLICE_ID in verified, (
        "the existing Gherkin/default verify-then-record path must keep "
        f"recording SliceCommitVerified unchanged -- verified={sorted(verified)!r}"
    )
