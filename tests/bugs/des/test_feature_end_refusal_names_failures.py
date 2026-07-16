"""Regression (GDP-3 gap, task #106): ``FeatureEndCycleRefused`` on a RED
full-suite leg carries only the bare ``ContractGateResult`` (pytest exit 1)
-- NO failing test names, NO persisted junit artifact. The operator must
re-run the whole suite in a diagnostic worktree (25-30 min of box time) just
to learn WHICH tests are red. Empirical anchor: three occurrences on
2026-07-12 alone. The standing what/why/how mandate (2026-06-26) calls a
refusal that forces investigation a defect in itself.

Design reference: docs/feature/fix-feature-end-refusal-names-failing-tests/
feature-delta.md. Bug observable (the oracle): a feature-end run against a
repo whose suite has failing tests refuses (as today, anti-theater
preserved) AND the refusal event NAMES the failing tests (their node ids,
bounded) AND carries the filesystem path of a persisted junit XML artifact
that outlives the run. A green-suite feature-end is unchanged.

Driving surface (Mandate-13/16 driving-port-only, Layer 3 in-process
default): the REAL ``des feature-end run`` CLI (``feature_end.main()``),
captured via ``capsys`` -- the bug is literally about the shape of the
``FeatureEndCycleRefused`` JSON payload the CLI emits, so the CLI is the
faithful driving port.

Fixture reuse (per dispatch instruction -- do NOT invent a new harness):
  * ``_init_repo`` -- the exact pytest-collectible git work-tree shape
    (pytest.ini registering unit/integration/acceptance + a
    ``pytest_collection_modifyitems`` auto-marker + a base passing test)
    proven GREEN for ``run_contract_gate``'s full-suite invocation by
    ``test_commit_slice_forwards_at_kind_to_verify_slice_commit.py::_init_repo``.
  * The sibling-leg stubbing idiom (``_stub_pre_full_suite_legs``) from
    ``tests/des/unit/application/test_feature_end_cycle_execution_reach_gate.py::
    _stub_non_execution_reach_legs`` -- every OTHER leg (walking-skeleton,
    env-e2e, coverage-map) is short-circuited to PASS so only the full-suite
    leg under test can determine the cycle's outcome. UNLIKE every existing
    sibling test, this file does NOT stub ``_run_full_suite_leg`` itself --
    it is the first AT to let that leg run for REAL against a hermetic
    RED/GREEN suite (no existing test exercises its genuine subprocess path).

GIT SAFETY: every throwaway repo below is built with ``git -C <tmp_path>
...`` EXPLICIT-target invocations only -- never a bare ``git config`` and
never any git write against the real project repo.

Harness scaling: the hermetic repo's "full suite" is a handful of trivial
``assert False`` functions (milliseconds each) -- never the real repo's
suite, never a path outside ``tmp_path``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from xml.etree import ElementTree

import pytest

from des.application import feature_end_cycle_service as svc
from des.cli.feature_end import main as feature_end_main


_FAILING_TEST_NAME = "test_widget_computes_correctly"


# ---------------------------------------------------------------------------
# Shared fixture builders (reused verbatim-in-spirit from the proven idioms)
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
    ``test_commit_slice_forwards_at_kind_to_verify_slice_commit.py``'s
    ``_init_repo`` verbatim) -- the exact shape that already makes
    ``des run-contract-gate``'s full-suite marker selection
    (``-m "unit or integration or acceptance"``) collect a real, tiny,
    self-contained suite, independent of the live project's own suite.
    """
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    # Pin the hooks dir to the repo's own .git/hooks so a global/user-level
    # core.hooksPath in the environment cannot leak into the run.
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


def _plant_failing_test(repo: Path) -> None:
    """One deliberately RED test alongside the passing ``test_base`` -- the
    minimal precise fixture: exactly one failing node-id to name."""
    (repo / "tests" / "unit" / "test_widget.py").write_text(
        f"def {_FAILING_TEST_NAME}():\n"
        "    assert 1 + 1 == 3, 'deliberately red witness'\n",
        encoding="utf-8",
    )


def _plant_many_failing_tests(repo: Path, count: int) -> None:
    """``count`` trivially-red parametrized cases in ONE file -- cheap
    (milliseconds) even nested inside a subprocess, for the bounded-list
    pin (dispatch scenario 2)."""
    (repo / "tests" / "unit" / "test_bulk_fail.py").write_text(
        "import pytest\n\n\n"
        f"@pytest.mark.parametrize('n', range({count}))\n"
        "def test_bulk_fail(n):\n"
        "    assert False, f'deliberately red bulk case #{n}'\n",
        encoding="utf-8",
    )


def _init_repo_without_auto_marker(root: Path) -> None:
    """A git work-tree that registers the unit/integration/acceptance markers
    (so an EXPLICITLY-tagged test is marker-visible) but carries NO
    ``pytest_collection_modifyitems`` auto-marker -- an UNTAGGED test in this
    repo is invisible to the marker-scoped run/collection, exactly the
    real-world toy-project shape Vera's examine reproduced (task #106 reloop).
    """
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "--local", "core.hooksPath", ".git/hooks")
    tests_dir = root / "tests" / "unit"
    tests_dir.mkdir(parents=True)
    (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")
    (root / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n"
        "    unit: unit tests\n"
        "    integration: integration tests\n"
        "    acceptance: acceptance tests\n",
        encoding="utf-8",
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base: walking skeleton")


def _plant_tagged_pass_and_untagged_fail(repo: Path) -> None:
    """One EXPLICITLY-``@pytest.mark.unit``-tagged passing test, alongside an
    UNTAGGED genuinely-failing test in the SAME suite.

    This is the empirically-confirmed reproduction of the false-zero defect
    (task #106 reloop, Vera's examine FAIL): the marker-scoped run/junit
    (``-m "unit or integration or acceptance"``) sees ONLY the tagged test
    and reports it clean, while the registered contract-gate ADAPTER
    (``PythonContractGateAdapter.run_suite``, which runs the suite WITHOUT
    any marker filter -- ``src/des/adapters/driven/contract_gate/
    pytest_contract_gate_adapter.py``) sees BOTH tests and genuinely finds
    the untagged one failing, driving a real refusal. The two scopes
    disagree -- the refusal is genuine but the marker-scoped junit the
    enrichment reads from never ran the actual failing test.
    """
    (repo / "tests" / "unit" / "test_tagged.py").write_text(
        "import pytest\n\n\n"
        "@pytest.mark.unit\n"
        "def test_tagged_pass():\n"
        "    assert True\n",
        encoding="utf-8",
    )
    (repo / "tests" / "unit" / "test_untagged.py").write_text(
        "def test_untagged_fail():\n    assert False, 'untagged genuine failure'\n",
        encoding="utf-8",
    )


def _assert_no_false_zero_or_dangling_junit(
    payload: dict[str, object], repo: Path
) -> None:
    """The false-zero / dangling-junit observable contract (Vera's examine
    FAIL, task #106 reloop): a genuine refusal must never (a) reference a
    ``junit_artifact`` path that does NOT exist on disk, nor (b) claim
    ``failing_count == 0`` / ``failing_tests == []`` WHILE ALSO pointing at
    a ``junit_artifact`` -- either the artifact genuinely accounts for the
    refusal's cause (a non-empty ``failing_tests``), or the report must be
    declared UNAVAILABLE (``junit_artifact`` absent/``None``) rather than
    silently emitting a numeric zero that reads as "nothing failed".

    Bound to the OBSERVABLE structure only (presence/absence + on-disk
    existence) -- no exact wording of any "reason" field is prescribed.
    """
    failing_tests = payload.get("failing_tests")
    failing_count = payload.get("failing_count")
    junit_artifact = payload.get("junit_artifact")

    if junit_artifact is not None:
        assert isinstance(junit_artifact, str) and junit_artifact, payload
        junit_path = Path(junit_artifact)
        if not junit_path.is_absolute():
            junit_path = repo / junit_path
        assert junit_path.is_file(), (
            "no dangling junit_artifact: a referenced path must EXIST on "
            f"disk -- {junit_path}, payload={payload!r}"
        )

    is_false_zero = failing_count == 0 and failing_tests == []
    assert not is_false_zero or junit_artifact is None, (
        "no false zero: a genuine refusal must never claim "
        "failing_count==0 / failing_tests==[] WHILE ALSO pointing at a "
        "junit_artifact -- either the artifact genuinely covers the "
        "refusal's cause (a non-empty failing_tests naming it) or the "
        "report must be declared UNAVAILABLE (junit_artifact=None). "
        f"payload={payload!r}"
    )


def _seed_feature_dir(repo_root: Path, feature_id: str) -> Path:
    """A minimal feature-dir with NO feature-delta.md (no Slice-Plan -> no
    undelivered-slice truncation refusal -- keeps the fixture focused on the
    full-suite leg alone, mirrors the sibling gate tests' ``_seed_feature_dir``)."""
    feature_dir = repo_root / "docs" / "feature" / feature_id
    feature_dir.mkdir(parents=True)
    return feature_dir


def _stub_pre_full_suite_legs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Short-circuit every leg BEFORE the full-suite leg to PASS, so only the
    (genuinely-run) full-suite leg can determine the cycle's outcome.

    Deliberately does NOT stub ``_run_full_suite_leg`` -- that is the leg
    under test; every existing sibling gate test stubs it away, so this is
    the first AT to exercise its real subprocess dispatch.
    """
    monkeypatch.setattr(
        svc,
        "_run_walking_skeleton_gate",
        lambda *, repo_root, feature_dir: repo_root,
    )
    monkeypatch.setattr(
        svc,
        "_run_environmental_e2e_gate",
        lambda *, ledger, repo_root, feature_id, feature_dir, walking_skeleton: None,
    )
    monkeypatch.setattr(
        svc,
        "_run_coverage_map_verify_leg",
        lambda *, ledger, repo_root, feature_id, feature_dir: None,
    )


def _last_json_event_or_empty(stdout: str) -> dict[str, object]:
    json_lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    return json.loads(json_lines[-1]) if json_lines else {}


def _run_feature_end_cli(
    repo: Path,
    feature_id: str,
    feature_dir: Path,
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, dict[str, object]]:
    """Drive the REAL ``des feature-end run`` CLI (``main()``) in-process,
    capturing its single-line JSON ``FeatureEndCycleRefused`` /
    ``FeatureEndCycleComplete`` payload via ``capsys``."""
    exit_code = feature_end_main(
        [
            "run",
            "--repo",
            str(repo),
            "--feature-id",
            feature_id,
            "--feature-dir",
            str(feature_dir),
            "--reviewer-agent-id",
            "nw-software-crafter-reviewer",
            "--verdict",
            "APPROVED",
        ]
    )
    stdout = capsys.readouterr().out
    return exit_code, _last_json_event_or_empty(stdout)


# ===========================================================================
# 1. NEGATIVE witness -- active-RED today (the core bug observable)
# ===========================================================================


def test_feature_end_refusal_never_hides_failing_test_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A feature-end run against a repo whose full suite has ONE failing test
    must still refuse (anti-theater preserved) AND the refusal payload must
    NAME the failing test node-id(s) AND carry a ``junit_artifact`` path that
    EXISTS on disk after the run and parses as JUnit XML containing the
    failure.

    RED today for the right reason (semantic, not a crash): the current
    ``FeatureEndCycleRefused`` payload carries only ``event`` / ``verb`` /
    ``feature_id`` / ``error`` -- neither ``failing_tests`` nor
    ``junit_artifact`` exist, so ``payload.get(...)`` returns ``None`` and
    the presence assertions fail with a genuine ``AssertionError``.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    _plant_failing_test(repo)
    feature_id = "fix-feature-end-refusal-names-failing-tests"
    feature_dir = _seed_feature_dir(repo, feature_id)
    _stub_pre_full_suite_legs(monkeypatch)

    exit_code, payload = _run_feature_end_cli(repo, feature_id, feature_dir, capsys)

    # (c) anti-theater is preserved -- a red full suite still refuses. This
    # part is ALREADY true today; it pins the invariant the fix must not break.
    assert exit_code == 2, (
        "a RED full-suite leg must still refuse the feature-end cycle "
        f"(anti-theater) -- exit_code={exit_code!r}, payload={payload!r}"
    )
    assert payload.get("event") == "FeatureEndCycleRefused", payload

    # (a) the refusal NAMES the failing test node-id(s).
    failing_tests = payload.get("failing_tests")
    assert isinstance(failing_tests, list) and failing_tests, (
        "FeatureEndCycleRefused on a full-suite failure must carry a non-empty "
        "`failing_tests` list naming the failing node-id(s) -- today the "
        "payload carries only the bare ContractGateResult with NO referents, "
        "forcing a 25-30 min diagnostic re-run to learn which tests are red "
        f"(GDP-3 gap). payload={payload!r}"
    )
    assert any(_FAILING_TEST_NAME in node_id for node_id in failing_tests), (
        f"the planted failing node-id ({_FAILING_TEST_NAME}) must appear in "
        f"`failing_tests` -- got {failing_tests!r}"
    )
    assert payload.get("failing_count") == 1, (
        "`failing_count` must report the TRUE number of failing tests -- got "
        f"{payload.get('failing_count')!r}, payload={payload!r}"
    )

    # (b) the refusal carries a junit_artifact path that EXISTS and parses.
    junit_artifact = payload.get("junit_artifact")
    assert isinstance(junit_artifact, str) and junit_artifact, (
        "FeatureEndCycleRefused must carry a `junit_artifact` filesystem path "
        f"referencing a persisted JUnit XML report -- payload={payload!r}"
    )
    junit_path = Path(junit_artifact)
    if not junit_path.is_absolute():
        junit_path = repo / junit_path
    assert junit_path.is_file(), (
        "the referenced `junit_artifact` must EXIST on disk after the run "
        f"(outlive the run, per the design contract) -- {junit_path}"
    )
    tree = ElementTree.parse(junit_path)
    failure_nodes = tree.getroot().findall(".//testcase[failure]")
    assert failure_nodes, (
        "the persisted junit_artifact must record at least one <testcase> "
        f"with a <failure> child -- {junit_path}"
    )
    assert any(
        _FAILING_TEST_NAME in (node.get("name") or "") for node in failure_nodes
    ), (
        "the junit_artifact must record the SAME failing test named in "
        f"`failing_tests` -- {junit_path}"
    )


# ===========================================================================
# 2. Bounded-list pin -- MANY failing tests never flood the payload
# ===========================================================================


def test_feature_end_refusal_bounds_the_named_failing_tests_when_many_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """With MANY failing tests the refusal's `failing_tests` list is BOUNDED
    (strictly fewer entries than the true total) while `failing_count` still
    reports the true total -- the refusal never silently drops the overflow
    (the total is still counted) but also never floods the payload with an
    unbounded list.

    The exact ceiling and the human-readable "+N more" wording are LEFT to
    the implementation (the design doc only suggests "e.g. first 20"); this
    AT pins only the STRUCTURAL contract -- bounded list + accurate total --
    not a specific ceiling number, per the dispatch's documented-contract
    escape for a disproportionate exact-bound pin.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    _plant_many_failing_tests(repo, count=25)
    feature_id = "fix-feature-end-refusal-names-failing-tests-bulk"
    feature_dir = _seed_feature_dir(repo, feature_id)
    _stub_pre_full_suite_legs(monkeypatch)

    exit_code, payload = _run_feature_end_cli(repo, feature_id, feature_dir, capsys)

    assert exit_code == 2, (
        f"25 failing tests must still refuse -- exit_code={exit_code!r}, "
        f"payload={payload!r}"
    )
    failing_tests = payload.get("failing_tests")
    assert isinstance(failing_tests, list) and failing_tests, (
        f"expected a non-empty `failing_tests` list -- payload={payload!r}"
    )
    failing_count = payload.get("failing_count")
    assert failing_count == 25, (
        "`failing_count` must report the TRUE total of failing tests even "
        f"when the named list is bounded -- got failing_count={failing_count!r}, "
        f"len(failing_tests)={len(failing_tests)}"
    )
    assert len(failing_tests) < failing_count, (
        "with 25 failing tests the named list must be BOUNDED (strictly "
        f"fewer entries than the true total) -- got {len(failing_tests)} of "
        f"{failing_count}, payload={payload!r}"
    )


# ===========================================================================
# 3. Green-path invariance -- must stay green BEFORE and AFTER the fix
# ===========================================================================


def test_feature_end_green_suite_proceeds_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A GREEN full suite must proceed through the feature-end cycle exactly
    as today -- no refusal, no behavioral change, no `failing_tests` /
    `junit_artifact` noise on a genuine pass. Must stay green both BEFORE
    and AFTER the fix (this is the enrichment's no-regression guard)."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    # No additional test files planted: `tests/unit/test_base.py` (from
    # `_init_repo`) is the full-suite leg's only collectable test, and it
    # passes -- a genuinely GREEN suite, not a stub.
    feature_id = "fix-feature-end-refusal-names-failing-tests-green"
    feature_dir = _seed_feature_dir(repo, feature_id)
    _stub_pre_full_suite_legs(monkeypatch)

    exit_code, payload = _run_feature_end_cli(repo, feature_id, feature_dir, capsys)

    assert exit_code == 0, (
        "a GREEN full suite must proceed through the feature-end cycle "
        f"exactly as today -- exit_code={exit_code!r}, payload={payload!r}"
    )
    assert payload.get("event") == "FeatureEndCycleComplete", payload
    assert "failing_tests" not in payload, payload
    assert "junit_artifact" not in payload, payload


# ===========================================================================
# 4. NEGATIVE witness (reloop, task #106) -- never emit a false zero or a
#    dangling junit_artifact when the marker-scoped report cannot honestly
#    account for the refusal (Vera's examine FAIL on the installed runtime).
# ===========================================================================


def test_refusal_never_emits_false_zero_or_dangling_junit_when_no_report_produced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Vera's examine (installed runtime, real-world toy project) found every
    probe -- 1 red test, 3 red tests, all-green -- produced the SAME refusal
    shape: ``failing_tests=[]``, ``failing_count=0``, and a ``junit_artifact``
    that in her environment did not exist on disk. Root shape (reproduced
    hermetically here): the registered contract-gate ADAPTER
    (``PythonContractGateAdapter.run_suite``) runs the suite WITHOUT any
    marker filter and genuinely finds a failure, driving a real refusal --
    but the marker-scoped run/junit (``-m "unit or integration or
    acceptance"``) the enrichment reads from never even SAW the failing
    test (it is not marker-visible), so the enrichment silently reports
    ZERO failures instead of declaring the report unavailable.

    RED today for the right reason (semantic, not a crash): today's payload
    genuinely carries ``failing_count=0`` / ``failing_tests=[]`` alongside a
    ``junit_artifact`` that DOES point at a report -- a report that exists
    but cannot honestly account for the refusal. The correct contract (per
    Vera + the dispatch reloop) is: either the artifact's ``failing_tests``
    genuinely names the real failing test, or the report is declared
    UNAVAILABLE (``junit_artifact=None``) -- never a numeric zero that reads
    as "nothing failed" while a refusal genuinely happened.

    STRENGTHENED (task #106 re-strengthening, 2026-07-13): the WEAK
    ``_assert_no_false_zero_or_dangling_junit`` guard below passes VACUOUSLY
    against today's payload -- neither ``failing_count`` nor ``failing_tests``
    key exists at all, so ``payload.get(...)`` returns ``None``, ``None == 0``
    is ``False``, ``is_false_zero`` is ``False``, and the guard never fires.
    It is kept (it is a genuine no-regression invariant once the fields DO
    exist) but it is NOT the oracle for this defect. The POSITIVE assertions
    below are the real oracle, and they pin the ONE dangerous failure mode a
    naive fix can reproduce: sourcing the junit report from the WRONG pytest
    invocation. There are two pytest runs inside one full-suite leg --
    ``facet.run_suite(repo)`` (unmarked, whole-suite, drives the refusal
    verdict) and ``_run_contract_suite(repo)`` (marker-scoped
    ``-m "unit or integration or acceptance"``, a second parity-only run). The
    untagged failing test planted below is REAL to the first run and
    INVISIBLE to the second (it carries no marker and this repo has no
    auto-marker conftest) -- a fix that reads its junit from the
    marker-scoped run will report ``failing_count=0`` / empty
    ``failing_tests`` / a junit with no failing testcase, exactly like
    today's bug, and these positive assertions will catch that just as they
    catch today's total absence of the fields.
    """
    repo = tmp_path / "repo"
    _init_repo_without_auto_marker(repo)
    _plant_tagged_pass_and_untagged_fail(repo)
    feature_id = "fix-feature-end-refusal-names-failing-tests-mismatch"
    feature_dir = _seed_feature_dir(repo, feature_id)
    _stub_pre_full_suite_legs(monkeypatch)

    exit_code, payload = _run_feature_end_cli(repo, feature_id, feature_dir, capsys)

    # The refusal itself is genuine (an untagged test really failed) -- this
    # part is ALREADY true today; it pins the invariant the fix must not break.
    assert exit_code == 2, (
        "a genuine untagged test failure must still refuse the feature-end "
        f"cycle (anti-theater) -- exit_code={exit_code!r}, payload={payload!r}"
    )
    assert payload.get("event") == "FeatureEndCycleRefused", payload

    # Weak structural no-regression guard (kept, but NOT the oracle -- see
    # docstring: it passes vacuously against a totally-absent field set).
    _assert_no_false_zero_or_dangling_junit(payload, repo)

    # POSITIVE oracle (the real trap): the refusal must name the UNTAGGED
    # failing test -- a fix sourcing junit from the marker-scoped second run
    # cannot produce this, because that run never even collects the untagged
    # test, so `failing_count` would stay 0 and the node-id absent.
    failing_count = payload.get("failing_count")
    assert isinstance(failing_count, int) and failing_count >= 1, (
        "the refusal must report the TRUE count of the untagged failing test "
        "-- a naive fix that sources junit from the marker-scoped "
        "`_run_contract_suite` run would report 0 (that run never collects "
        f"the untagged test). got failing_count={failing_count!r}, "
        f"payload={payload!r}"
    )
    failing_tests = payload.get("failing_tests")
    assert isinstance(failing_tests, list) and any(
        "test_untagged_fail" in node_id for node_id in failing_tests
    ), (
        "the planted UNTAGGED failing node-id (test_untagged_fail) must "
        "appear in `failing_tests` -- a marker-scoped-run-sourced junit "
        f"would never name it. got failing_tests={failing_tests!r}, "
        f"payload={payload!r}"
    )
    junit_artifact = payload.get("junit_artifact")
    assert isinstance(junit_artifact, str) and junit_artifact, (
        "the refusal must carry a `junit_artifact` filesystem path -- "
        f"payload={payload!r}"
    )
    junit_path = Path(junit_artifact)
    if not junit_path.is_absolute():
        junit_path = repo / junit_path
    assert junit_path.is_file() and junit_path.stat().st_size > 0, (
        "the referenced `junit_artifact` must EXIST on disk and be "
        f"non-empty -- {junit_path}"
    )
    tree = ElementTree.parse(junit_path)
    failure_nodes = tree.getroot().findall(".//testcase[failure]")
    assert any(
        "test_untagged_fail" in (node.get("name") or "") for node in failure_nodes
    ), (
        "the persisted junit_artifact must record the UNTAGGED failing test "
        "-- a report sourced from the marker-scoped run would carry ZERO "
        f"<failure> testcases (it never saw the untagged test) -- {junit_path}"
    )
