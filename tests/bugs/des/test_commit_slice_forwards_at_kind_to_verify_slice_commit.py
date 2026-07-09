"""Regression (#13 slice-02, Ale-gated): ``des commit-slice`` must FORWARD the
behavioral-attestation flags (``--at-kind pytest-regression
--regression-test-file <path>``) to its Step-6 fold-in call into
``verify_slice_commit_completeness.main()``, so a real pytest-regression
commit earns ``SliceCommitVerified`` end-to-end through ``commit-slice``
itself -- not only through a standalone ``des verify-slice-commit`` call.

Charter: task #13 slice-02 (behavioral-attestation-verify-slice-commit
forwarding).

Context (slice-01 shipped, ``src/des/cli/verify_slice_commit_completeness.py``):
``des verify-slice-commit --at-kind pytest-regression --regression-test-file
<path>`` now RUNS the declared regression test on the committed tree and
attests E2 only on an observed pass (the honesty invariant -- a failing/
missing test never verifies). Found in ``src/des/cli/commit_slice.py``
``_build_parser()`` (``:437-496``): it defines NO ``--at-kind``/
``--regression-test-file`` flags at all, and its Step-6 fold-in call
(``:878-885``) invokes ``verify_slice_commit_completeness.main(["--repo",
..., "--feature-id", ..., "--commit", "HEAD"])`` with NEITHER flag -- so a
pytest-regression slice committed via ``des commit-slice`` still runs the
fold-in's DEFAULT (gherkin) E2 leg, which cannot resolve a pytest-regression
bugfix's structure and refuses (``SliceCommitRefused``), even when the
slice's own regression test genuinely, verifiably passes.

The fix direction (this AT's contract, NOT implemented here -- test-authoring
only, zero ``src/`` edits): add the SAME ``--at-kind {gherkin,pytest-
regression}`` (default ``gherkin``, byte-identical for every existing caller)
plus ``--regression-test-file <path>`` pair to ``commit_slice._build_parser()``
(mirroring ``dispatch.py``/``carpaccio_slice_gate.py``/
``verify_slice_commit_completeness.py``), and FORWARD them into the Step-6
fold-in's ``verify_slice_commit_completeness.main([...])`` argv when given.

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process default):
the REAL ``des.cli.commit_slice.main()`` CLI driver, captured via ``capsys``
-- the whole point of this AT is to prove the forwarding happens INSIDE
``commit-slice`` itself, not via a separate ``des verify-slice-commit`` call.

Fixture reuse (per dispatch instruction -- do NOT hand-roll a new harness):
  * ``_init_repo`` -- the exact pytest-collectible git work-tree shape from
    the proven GREEN precedent ``tests/bugs/des/
    test_commit_slice_writes_verified_record.py`` (pytest.ini + conftest.py +
    ``tests/unit/test_base.py`` + pinned ``core.hooksPath``) -- the shape
    that already makes ``des commit-slice``'s whole-tree committed-scope
    digest + ``run_contract_gate --verify-gate-scope`` succeed today,
    independent of ``--at-kind``.
  * ``_write_regression_test`` -- the head-tagged (``# @feature-{id}`` /
    ``# @{slice-NN}``) pytest regression-file convention from the proven
    GREEN precedent ``tests/bugs/des/
    test_verify_slice_commit_pytest_regression_behavioral_attestation.py``:
    the SAME file doubles as both the E1 delivered-AT artifact (pytest-tag
    discovery, ``des.application.slice_at_completeness.feature_files_for_
    slice``) and the E2 behavioral witness (``_run_regression_gate`` actually
    runs it).
  * The AT-EXEMPT ``@prefactoring`` lane fixture (feature-delta ``[REF] Slice
    Plan`` table + predecessor commit) from
    ``test_commit_slice_writes_verified_record.py`` -- reused LOCALLY for the
    additivity guard, which must keep clearing via the pre-existing DEFAULT
    (gherkin) fold-in path with NO ``--at-kind``/``--regression-test-file``
    involved at all.

GIT SAFETY: every throwaway repo below is built with ``git -C <tmp_path>
...`` EXPLICIT-target invocations only (via ``subprocess.run(["git", *args],
cwd=root, ...)``) -- never a bare ``git config`` and never any git write
against the real project repo.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.commit_slice import main as commit_slice_main


_SLICE_ID = "slice-02"
_PREDECESSOR = "slice-01"
_ENTERING = "slice-02"

_REGRESSION_FILE_REL = "tests/bugs/fixture/test_commit_slice_at_kind_forward_fixture.py"

_FEATURE_ID_POS = "commit-slice-at-kind-forward-pos"
_FEATURE_ID_HONESTY = "commit-slice-at-kind-forward-honesty"
_FEATURE_ID_ADDITIVITY = "commit-slice-at-kind-forward-additivity"


# ---------------------------------------------------------------------------
# Shared fixture builders
# ---------------------------------------------------------------------------


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _init_repo(root: Path) -> None:
    """Init a real pytest-collectible git work-tree (mirrors
    ``test_commit_slice_writes_verified_record.py``'s ``_init_repo``
    verbatim -- the exact shape that already makes ``des commit-slice``'s
    whole-tree committed-scope digest + ``run_contract_gate
    --verify-gate-scope`` succeed today, independent of ``--at-kind``).
    """
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    # Pin the hooks dir to the repo's own .git/hooks so a global/user-level
    # core.hooksPath in the environment cannot leak into the hook-count tests.
    _git(root, "config", "--local", "core.hooksPath", ".git/hooks")
    tests_dir = root / "tests" / "unit"
    tests_dir.mkdir(parents=True)
    (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")
    (root / "conftest.py").write_text(
        "import pytest\n\n\n"
        "def pytest_collection_modifyitems(items):\n"
        "    for item in items:\n"
        "        item.add_marker(pytest.mark.unit)\n",
        encoding="utf-8",
    )
    (root / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n"
        "    unit: unit tests\n"
        "    integration: integration tests\n"
        "    acceptance: acceptance tests\n",
        encoding="utf-8",
    )
    (tests_dir / "test_base.py").write_text(
        "def test_base():\n    assert True\n", encoding="utf-8"
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base: walking skeleton")


def _write_regression_test(
    repo: Path, feature_id: str, slice_id: str, *, passing: bool
) -> Path:
    """A real, pytest-collectible regression test file, head-tagged for the
    SAME ``feature_id``/``slice_id`` E1 already discovers via
    ``# @feature-{id}`` / ``# @{slice-NN}`` head-comment tags -- the fixture
    doubles as both the E1 delivered-AT artifact and the E2 behavioral
    witness (mirrors ``test_verify_slice_commit_pytest_regression_
    behavioral_attestation.py``'s ``_write_regression_test`` verbatim).
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


def _last_json_event(stdout: str) -> dict[str, object]:
    json_lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    assert json_lines, f"expected a JSON payload line on stdout, got: {stdout!r}"
    return json.loads(json_lines[-1])


def _last_json_event_or_empty(stdout: str) -> dict[str, object]:
    json_lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    return json.loads(json_lines[-1]) if json_lines else {}


def _run_commit_slice_with_at_kind(
    repo: Path,
    feature_id: str,
    slice_id: str,
    regression_test_file_rel: str,
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, dict[str, object]]:
    """Drive the REAL ``des commit-slice`` CLI (``main()``) in-process with
    the NEW ``--at-kind pytest-regression --regression-test-file <path>``
    pair, capturing its single-line JSON payload via ``capsys``.

    Today (pre-fix) ``commit_slice._build_parser()`` recognizes neither flag
    -- argparse raises ``SystemExit(2)`` (unrecognized arguments) BEFORE any
    staging/commit happens. That ``SystemExit`` is caught here and its code
    folded into the SAME ``(exit_code, payload)`` return shape the post-fix
    call produces (``payload={}`` when nothing was ever emitted), so every
    caller's assertion is a genuine comparison against the verdict/ledger,
    never a crash masquerading as a failing test (mirrors ``test_verify_
    slice_commit_pytest_regression_behavioral_attestation.py``'s
    ``_run_behavioral_verify_slice_commit``).
    """
    try:
        exit_code = commit_slice_main(
            [
                "--repo",
                str(repo),
                "--all",
                "--feature-id",
                feature_id,
                "--slice-id",
                slice_id,
                "--message",
                "fix(slice): pytest-regression fix verified behaviorally",
                "--at-kind",
                "pytest-regression",
                "--regression-test-file",
                regression_test_file_rel,
            ]
        )
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 1
    stdout = capsys.readouterr().out
    return exit_code, _last_json_event_or_empty(stdout)


# --- additivity fixture (the AT-EXEMPT @prefactoring lane, DEFAULT path) ---


def _write_feature_delta_with_prefactoring_entering_slice(
    repo: Path, feature_id: str
) -> None:
    """A minimal feature-delta carrying the ``[REF] Slice Plan`` table --
    mirrors ``test_commit_slice_writes_verified_record.py``'s ``_write_
    feature_delta_with_prefactoring_entering_slice`` verbatim: ``_PREDECESSOR``
    is an ordinary AT-bearing row, ``_ENTERING`` is annotated
    ``@prefactoring`` (EXEMPT).
    """
    delta_dir = repo / "docs" / "feature" / feature_id
    delta_dir.mkdir(parents=True, exist_ok=True)
    (delta_dir / "feature-delta.md").write_text(
        f"# Feature Delta: {feature_id}\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
        f"| {_PREDECESSOR} | the predecessor slice ships a real scenario | "
        "pending | | a real AT-bearing slice |\n"
        f"| {_ENTERING} | a behavior-preserving refactor introduces the seam | "
        "pending | @prefactoring | a green-to-green prefactoring |\n",
        encoding="utf-8",
    )


def _commit_predecessor_with_at(repo: Path, feature_id: str) -> None:
    feat_dir = repo / "tests" / "acceptance" / feature_id.replace("-", "_")
    feat_dir.mkdir(parents=True, exist_ok=True)
    (feat_dir / f"{_PREDECESSOR}.feature").write_text(
        f"@feature-{feature_id}\n"
        "Feature: the predecessor slice's behaviour\n\n"
        f"  @{_PREDECESSOR}\n"
        "  Scenario: the predecessor delivers its observable outcome\n"
        "    Given a precondition\n"
        "    When the action happens\n"
        "    Then the outcome holds\n",
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(
        repo,
        "commit",
        "-q",
        "-m",
        f"feat(slice): predecessor behaviour\n\nSlice-Id: {_PREDECESSOR}",
    )


def _mark_predecessor_verified(repo: Path, feature_id: str) -> None:
    AtCompletionLedger(feature_id, repo).append_gate_event(
        event="SliceCommitVerified", slice_id=_PREDECESSOR
    )


def _author_entering_slice_production_change(repo: Path) -> None:
    """The ``_ENTERING`` slice's behavior-preserving production-only change
    -- NO new ``.feature`` file, mirroring the real 0-AT prefactoring shape.
    """
    prod_file = repo / "src" / "app" / "module.py"
    prod_file.parent.mkdir(parents=True, exist_ok=True)
    prod_file.write_text(
        "def helper() -> str:\n    return 'refactored, same behaviour'\n",
        encoding="utf-8",
    )


# ===========================================================================
# 1. POSITIVE (end-to-end) -- active-RED today
# ===========================================================================


def test_commit_slice_forwards_at_kind_and_earns_verified_record_end_to_end(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``des commit-slice --at-kind pytest-regression --regression-test-file
    <passing-test> ...`` must land the commit AND earn a ``SliceCommitVerified``
    ledger record -- the fold-in must forward the flags so its Step-6 call
    into ``verify_slice_commit_completeness.main()`` uses the BEHAVIORAL
    (not the gherkin/feature-scoped-contract) E2 path.

    RED for the right reason today: ``commit_slice._build_parser()`` defines
    neither ``--at-kind`` nor ``--regression-test-file`` -- driving them
    raises ``SystemExit(2)`` (folded to ``exit_code=2``, ``event={}``), a
    semantic mismatch against the expected ``exit_code == 0`` /
    ``SliceCommitVerified`` verdict, not a collection or import error.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_regression_test(repo, _FEATURE_ID_POS, _SLICE_ID, passing=True)

    exit_code, event = _run_commit_slice_with_at_kind(
        repo, _FEATURE_ID_POS, _SLICE_ID, _REGRESSION_FILE_REL, capsys
    )

    assert exit_code == 0, (
        "a pytest-regression slice committed via `des commit-slice --at-kind "
        "pytest-regression --regression-test-file <passing-test>` whose "
        "regression test genuinely PASSES on the committed tree must clear "
        f"end-to-end -- got exit_code={exit_code!r}, event={event!r}"
    )
    assert event.get("event") == "SliceCommitted", event

    verified = AtCompletionLedger(_FEATURE_ID_POS, repo).verified_slices()
    assert _SLICE_ID in verified, (
        "`des commit-slice` must FORWARD --at-kind/--regression-test-file "
        "into its Step-6 verify-then-record fold-in, so a real pytest-"
        "regression commit earns SliceCommitVerified via the E2 BEHAVIORAL "
        "attestation path -- today the fold-in call omits both flags, so "
        "the fold-in runs the default gherkin path and never mints the "
        f"record. observed verified_slices={sorted(verified)!r}"
    )


# ===========================================================================
# 2. HONESTY (end-to-end, CRITICAL, negative) -- green now AND after the fix
# ===========================================================================


@pytest.mark.negative_at
def test_commit_slice_never_forwards_a_verified_record_for_a_failing_regression_test(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The false-green guard, through the forwarding path: a pytest-
    regression slice whose regression test genuinely FAILS on the committed
    tree must NEVER earn ``SliceCommitVerified`` via ``des commit-slice`` --
    neither today (the flags don't exist, so nothing can verify) nor after
    the fix (the forwarded behavioral run observes the failure and the
    fold-in refuses). The honesty invariant must hold THROUGH the wiring --
    a broken slice never earns the attestation even via `commit-slice`.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_regression_test(repo, _FEATURE_ID_HONESTY, _SLICE_ID, passing=False)

    _run_commit_slice_with_at_kind(
        repo, _FEATURE_ID_HONESTY, _SLICE_ID, _REGRESSION_FILE_REL, capsys
    )

    verified = AtCompletionLedger(_FEATURE_ID_HONESTY, repo).verified_slices()
    assert _SLICE_ID not in verified, (
        "a pytest-regression slice whose regression test genuinely FAILS on "
        "the committed tree must NEVER earn a fabricated SliceCommitVerified "
        "record through `des commit-slice`'s forwarding -- the exact "
        "false-green the honesty invariant exists to prevent. observed "
        f"verified_slices={sorted(verified)!r}"
    )


# ===========================================================================
# 3. ADDITIVITY guard -- NO-REGRESSION, must stay green before AND after
# ===========================================================================


def test_commit_slice_default_gherkin_path_still_earns_verified_record_without_at_kind(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``des commit-slice`` WITHOUT ``--at-kind`` (the default, unchanged
    gherkin fold-in path) must keep behaving byte-identically -- the flag-
    forwarding addition must not touch this path. Must stay green both
    BEFORE and AFTER the fix (mirrors the proven GREEN precedent
    ``test_commit_slice_writes_verified_record.py::test_commit_slice_writes_
    slice_commit_verified_record``).
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_feature_delta_with_prefactoring_entering_slice(repo, _FEATURE_ID_ADDITIVITY)
    _commit_predecessor_with_at(repo, _FEATURE_ID_ADDITIVITY)
    _mark_predecessor_verified(repo, _FEATURE_ID_ADDITIVITY)
    _author_entering_slice_production_change(repo)

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--all",
            "--feature-id",
            _FEATURE_ID_ADDITIVITY,
            "--slice-id",
            _ENTERING,
            "--message",
            "refactor(slice): behavior-preserving seam stays wired",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 0, (
        "the default (no --at-kind) fold-in path must keep clearing "
        f"unchanged -- exit_code={exit_code!r}, event={event!r}"
    )
    assert event.get("event") == "SliceCommitted", event

    verified = AtCompletionLedger(_FEATURE_ID_ADDITIVITY, repo).verified_slices()
    assert _ENTERING in verified, (
        "the pre-existing DEFAULT (gherkin) verify-then-record fold-in path "
        "must keep recording SliceCommitVerified unchanged after the "
        "--at-kind forwarding wiring lands -- observed "
        f"verified_slices={sorted(verified)!r}"
    )
