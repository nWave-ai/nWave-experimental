"""Feature `certification-legs-observe-real-execution`, slice-02 (DDD-CERT-2/3).

Value statement (feature-delta.md [REF] Slice Plan, slice-02): a `des
feature-end run` on a foreign repo whose tests carry NO unit/integration/
acceptance pytest marks but are otherwise fully runnable gets
``CycleIndeterminate``, never a silent ``FeatureEndCycleComplete`` over zero
observed legs.

Found in ``src/des/application/feature_end_cycle_service.py::
_repo_has_contract_suite`` (:610-633) and ``_run_full_suite_leg`` (:572-607):
the presence-probe collects node-ids through ``run_contract_gate.
_collect_node_ids`` -> ``_collect_scope`` -> the ``_collect_scope_worker.py``
subprocess, which ALWAYS applies ``-m "unit or integration or acceptance"``
(``_collect_scope_worker.py:54,196,235`` -- both the ``--collect-only`` branch
and the ``--run`` branch pass the SAME ``_CONTRACT_MARKER``, no override
parameter exists yet). A foreign repo whose tests carry none of the three
nWave contract marks collects **zero** node-ids under that filter EVEN WHEN
the suite is fully runnable -- ``_repo_has_contract_suite`` returns ``False``,
``_run_full_suite_leg`` returns ``FullSuiteLegNotApplicable`` (an *epistemic*
"I did not observe this" mislabeled as an *ontological* "there is nothing to
observe"), and the cycle PROCEEDS past it to a full ``CycleSuccess`` /
``FeatureEndCycleComplete`` -- the exact #126/#179 false-green this feature
closes (DDD-CERT-1/2/3, ADR-GV-002 D1/D3).

DDD-CERT-3's fix (a future slice, not authored here): ``_run_full_suite_leg``
gains a marker-agnostic secondary collect; when the marker-filtered collect is
empty AND the unmarked collect is non-empty, the leg returns the (not-yet-
existing) ``FullSuiteLegIndeterminate`` and the cycle's aggregate (DDD-CERT-2)
widens to ``CycleSuccess | CycleIndeterminate | CycleRefusal`` -- ``des
feature-end run`` maps ``CycleIndeterminate`` to exit 3 (ADR-GV-002 D4,
mirroring ``run_contract_gate.py:113-116``'s existing local
``_GATE_INDETERMINATE_EXIT_CODE = 3`` pattern -- never a repurposed exit
value).

Driving surface (Mandate-13 driving-port-only, Layer 3 composition,
IN-PROCESS default): the REAL ``des.cli.feature_end.main(["run", ...])`` CLI
driver, captured via ``capsys`` -- observes the JSON verdict + exit code, the
SAME in-process pattern slice-01's AT uses. Per the Test Reuse & Consolidation
Analysis row ("Feature-end cycle fixture harness ... EXTEND ... slice-02/03's
CycleIndeterminate/LegCensus ATs reuse the SAME tmp-target-repo +
subprocess-dispatch fixture shape the existing feature-end cycle ATs already
use"), the sibling legs this slice does not touch (walking-skeleton,
environmental-e2e, coverage-map) are stubbed via monkeypatch -- mirrors
``tests/des/unit/application/test_feature_end_cycle_execution_reach_gate.py``
's ``_stub_non_execution_reach_legs`` pattern -- so only the REAL, unstubbed
``_run_full_suite_leg`` (and its real ``_collect_scope_worker.py`` subprocess
dispatch) determines the cycle's outcome. The remaining legs (doc-coherence,
execution-reach, fresh-clone, feature-end-examine) resolve to their genuine
NOT_APPLICABLE arm on the minimal fixture tree (no README/docs, no
coverage.xml, no demo-recipe, no charter dir) -- unchanged, real preconditions,
never stubbed.

Active-RED today (real assertion failures, never an import/collection error):
the fixture's suite is genuinely runnable (a real ``def test_...(): assert
...`` collected by a real pytest subprocess) but carries none of the three
contract marks, so ``_repo_has_contract_suite`` observes zero node-ids and the
cycle proceeds all the way to a genuine, unstubbed ``CycleSuccess`` ->
``FeatureEndCycleComplete`` (exit 0) today. ``CycleIndeterminate`` does not
exist yet in ``feature_end_cycle_service`` -- the positive AT below asserts via
``getattr`` (never a bare ``from ... import CycleIndeterminate``, which would
be an import error, not a real assertion) so the failure is a genuine
``AssertionError`` on the observed exit code / outcome type, exactly as this
task requires.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from des.application import feature_end_cycle_service as svc
from des.cli import feature_end as feature_end_cli


_FEATURE_ID = "fixture-feature"

# ADR-GV-002 D4: `des feature-end run` gains exit 3 for CycleIndeterminate,
# mirroring `run_contract_gate.py:113-116`'s existing local
# `_GATE_INDETERMINATE_EXIT_CODE = 3` pattern. Not yet implemented today --
# `feature_end._run_cycle` has no such branch (only CycleRefusal -> 2 and the
# success path -> 0), so this literal is the PINNED target, not an assumption.
_EXPECTED_INDETERMINATE_EXIT = 3


def _seed_feature_dir(repo_root: Path, feature_id: str = _FEATURE_ID) -> Path:
    """A minimal feature-dir with NO feature-delta.md (no Slice-Plan -> no
    undelivered-slice truncation refusal -- mirrors
    ``test_feature_end_cycle_execution_reach_gate.py::_seed_feature_dir``,
    keeping the fixture focused on the full-suite leg alone)."""
    feature_dir = repo_root / "docs" / "feature" / feature_id
    feature_dir.mkdir(parents=True)
    return feature_dir


_RUNNABLE_TEST_BODY = "def test_widget_behaves():\n    assert 1 + 1 == 2\n"


def _seed_unmarked_runnable_suite(repo_root: Path) -> None:
    """A genuinely runnable pytest suite carrying NONE of the three nWave
    contract marks (unit/integration/acceptance) at the CONVENTIONAL top-level
    ``tests/`` root -- the exact shape of a foreign, unmarked-but-runnable
    target repo (DDD-CERT-3). A real pytest subprocess collects this file
    without error; it is simply excluded by the marker filter, never by a
    genuine absence of tests.
    """
    tests_dir = repo_root / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_widget.py").write_text(_RUNNABLE_TEST_BODY, encoding="utf-8")


def _seed_unmarked_runnable_suite_nonstandard_location(repo_root: Path) -> None:
    """The SAME genuinely-runnable, unmarked suite, but at a NON-STANDARD
    repo-level location -- ``custom_tests/`` at the repo root, NOT under the
    conventional ``tests/``/``test/`` roots and NOT under ``src/`` (Vera's
    examine gap). A fix that scopes the marker-agnostic secondary collect to
    only the conventional top-level test roots MISSES this suite entirely, so
    the FullSuiteLeg falls to NotApplicable -> FeatureEndCycleComplete --
    IDENTICAL to the genuinely-absent case, the #126 false-green surviving for
    non-standard test locations. The correct scope is repo-level tests ANYWHERE
    outside ``src/``.
    """
    tests_dir = repo_root / "custom_tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_widget.py").write_text(_RUNNABLE_TEST_BODY, encoding="utf-8")


def _seed_unmarked_runnable_suite_nonstandard_location_with_root_manifest(
    repo_root: Path,
) -> None:
    """The SAME non-standard-location suite as
    ``_seed_unmarked_runnable_suite_nonstandard_location``, but with a
    REALISTIC top-level manifest FILE (``pyproject.toml``) sitting beside
    ``custom_tests/`` -- the shape of an ACTUAL foreign repo, which always
    carries at least one top-level file (manifest, README, lockfile, ...),
    not just directories.

    This is the fixture-realism gap: ``_repo_has_contract_suite``'s
    marker-agnostic secondary-collect scope
    (``feature_end_cycle_service.py:801-805``) builds ``secondary_scope`` from
    ``repo_root.iterdir()`` filtering out only ``src/`` and the prune-dirs
    denylist -- it does NOT filter ``entry.is_dir()``, so this top-level FILE
    lands in ``secondary_scope`` too. Passing a non-test file to
    ``_collect_node_ids(..., paths=secondary_scope, markers=None)`` makes the
    pytest collection subprocess exit non-zero -> ``_CollectionError`` ->
    caught by the broad ``except`` -> ``_repo_has_contract_suite`` returns
    ``False`` -> ``FullSuiteLegNotApplicable`` -> ``FeatureEndCycleComplete``
    (exit 0), even though the repo DOES carry a real, runnable,
    non-standard-location suite. The sibling case above (no top-level file)
    happens to dodge this exact defect because ``secondary_scope`` contains
    only the ``custom_tests/`` directory -- this fixture closes that gap by
    mirroring what every real repo actually looks like.
    """
    tests_dir = repo_root / "custom_tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_widget.py").write_text(_RUNNABLE_TEST_BODY, encoding="utf-8")
    (repo_root / "pyproject.toml").write_text(
        '[project]\nname = "foreign-repo"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )


def _seed_no_tests_at_all(repo_root: Path) -> None:
    """A repo with production source but GENUINELY ZERO test files anywhere --
    the ontological-absence case that must stay NotApplicable -> Complete. Its
    marker-filtered AND marker-agnostic collects are BOTH empty (there is
    nothing to observe), so the fix must NOT flip this to Indeterminate --
    otherwise the fix would be the vacuous "everything is Indeterminate."
    """
    src = repo_root / "src" / "widgetpkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "core.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")


_MARKED_RUNNABLE_TEST_BODY = (
    "import pytest\n\n\n@pytest.mark.unit\ndef test_widget_behaves():\n"
    "    assert 1 + 1 == 2\n"
)


def _seed_marked_runnable_suite_with_manifest(repo_root: Path) -> None:
    """A genuinely-runnable, MARKED pytest suite (``@pytest.mark.unit``) at the
    conventional ``tests/`` root, PLUS a realistic top-level ``pyproject.toml``
    -- the shape of an actual foreign repo whose full-suite leg genuinely RUNS
    (never NotApplicable, never Indeterminate). The marker-filtered collect
    finds >=1 node-id, so ``_repo_has_contract_suite`` returns True and the
    REAL (unstubbed) full-suite leg genuinely DISPATCHES ``des
    run-contract-gate`` -- an actual pytest subprocess over this fixture --
    yielding a genuine ``FullSuiteLegRan``. This is the "ran real tests and
    they passed" half of the leg_census-distinguishability AT below; the
    "genuinely no tests to run" half reuses ``_seed_no_tests_at_all`` above.
    """
    tests_dir = repo_root / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_widget.py").write_text(
        _MARKED_RUNNABLE_TEST_BODY, encoding="utf-8"
    )
    (repo_root / "pyproject.toml").write_text(
        '[project]\nname = "foreign-repo"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )


def _seed_unmarked_runnable_suite_under_src(repo_root: Path) -> None:
    """A genuinely-runnable, unmarked suite bundled UNDER ``src/<pkg>/tests/``
    -- the installable package's OWN fixtures, observed by the env-e2e leg, NOT
    the repo's contract suite (the boundary the fix must respect). The
    marker-agnostic secondary collect MUST exclude ``src/`` so this does NOT
    trigger Indeterminate -- it stays NotApplicable -> Complete. This pins the
    exact scope: repo-level tests outside ``src/`` count; tests under ``src/``
    do not.
    """
    tests_dir = repo_root / "src" / "widgetpkg" / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_internal.py").write_text(
        "def test_internal():\n    assert True\n", encoding="utf-8"
    )


def _stub_non_full_suite_legs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Short-circuit every OTHER leg so only the REAL (unstubbed) full-suite
    leg -- and its real marker-filtered collection -- can determine the
    cycle's outcome. Mirrors
    ``test_feature_end_cycle_execution_reach_gate.py::
    _stub_non_execution_reach_legs``, minus the full-suite stub (this slice's
    target, deliberately left REAL)."""
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


def _run_cycle_cli(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    *,
    planter: Callable[[Path], None] = _seed_unmarked_runnable_suite,
) -> tuple[int, dict[str, object]]:
    """Stage a foreign target fixture (via ``planter``) and drive the REAL
    ``des feature-end run`` CLI in-process (Layer 3 composition). Returns
    ``(exit_code, parsed_json_payload)`` -- the command's real observables.
    """
    _stub_non_full_suite_legs(monkeypatch)
    repo_root = tmp_path / "foreign-repo"
    repo_root.mkdir()
    planter(repo_root)
    feature_dir = _seed_feature_dir(repo_root)

    exit_code = feature_end_cli.main(
        [
            "run",
            "--repo",
            str(repo_root),
            "--feature-id",
            _FEATURE_ID,
            "--feature-dir",
            str(feature_dir),
            "--reviewer-agent-id",
            "nw-software-crafter-reviewer",
            "--verdict",
            "APPROVED",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out.strip().splitlines()[-1])
    return exit_code, payload


def test_marker_filtered_collect_miss_on_runnable_suite_yields_cycle_indeterminate(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """POSITIVE AT (active-RED today): a foreign repo whose tests are fully
    runnable but carry no unit/integration/acceptance marks must yield
    ``CycleIndeterminate`` (exit 3, ADR-GV-002 D4) -- never a silent
    ``CycleSuccess`` over the un-observed full-suite leg. Today the
    marker-filtered collect returns empty, ``_repo_has_contract_suite``
    reports False, and the cycle proceeds to a genuine ``CycleSuccess`` (exit
    0) -- these assertions are what fails.
    """
    exit_code, payload = _run_cycle_cli(monkeypatch, capsys, tmp_path)

    assert exit_code == _EXPECTED_INDETERMINATE_EXIT, (
        "a foreign repo with a fully-runnable-but-unmarked contract suite "
        f"must exit {_EXPECTED_INDETERMINATE_EXIT} (CycleIndeterminate, "
        "ADR-GV-002 D4) -- the marker-filtered collect found zero node-ids "
        "but the suite genuinely runs, so this leg was NEVER OBSERVED, not "
        f"genuinely absent. Got exit {exit_code}, payload={payload!r}"
    )
    assert payload.get("event") != "FeatureEndCycleComplete", (
        "the cycle must NEVER emit FeatureEndCycleComplete while the "
        f"full-suite leg went unobserved: {payload!r}"
    )
    payload_text = json.dumps(payload).lower()
    assert "full-suite" in payload_text or "full_suite" in payload_text, (
        "the INDETERMINATE verdict must NAME the un-observed FullSuiteLeg "
        f"(DDD-CERT-2/3) so a crafter knows WHICH leg went unobserved -- "
        f"got: {payload!r}"
    )
    # If the aggregate carries a leg census (DDD-CERT-2), it must show zero
    # legs ran -- this slice's fixture stubs every OTHER leg, so the ONLY leg
    # that could have genuinely run (the full-suite leg) is the one this AT
    # proves was never observed.
    leg_census = payload.get("leg_census")
    if isinstance(leg_census, dict):
        assert leg_census.get("ran") == 0, (
            f"leg_census must show zero legs genuinely ran: {leg_census!r}"
        )


@pytest.mark.negative_at
def test_marker_filtered_collect_miss_never_emits_cycle_complete_over_unobserved_suite(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """NEGATIVE AT (anti-recurrence, active-RED today): given the SAME
    foreign, unmarked-but-runnable fixture, the cycle must NEVER emit
    ``FeatureEndCycleComplete`` (a done/green verdict) over zero observed
    legs, and must NEVER exit 0. Today the cycle DOES emit
    ``FeatureEndCycleComplete`` at exit 0 (the exact #126/#179 silent
    false-green this feature closes) -- these assertions are what fails.
    """
    exit_code, payload = _run_cycle_cli(monkeypatch, capsys, tmp_path)

    assert exit_code != 0, (
        "a cycle whose only non-stubbed leg (full-suite) never actually "
        f"observed the genuine contract suite must never exit 0: {payload!r}"
    )
    assert payload.get("event") != "FeatureEndCycleComplete", (
        "FeatureEndCycleComplete must never be emitted over zero observed "
        f"legs (the #126/#179 silent false-green): {payload!r}"
    )


def test_nonstandard_location_runnable_suite_yields_cycle_indeterminate(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """POSITIVE AT (Vera examine gap, active-RED today): a foreign repo whose
    runnable-but-unmarked contract suite lives at a NON-STANDARD repo-level
    location (``custom_tests/`` -- NOT under ``tests/``/``test/``, NOT under
    ``src/``) must still yield ``CycleIndeterminate`` (exit 3), NEVER a silent
    ``FeatureEndCycleComplete``. A fix that scopes the marker-agnostic
    secondary collect to only the conventional top-level ``tests/`` root MISSES
    this suite -> FullSuiteLegNotApplicable -> Complete, IDENTICAL to the
    genuinely-absent case: the #126 false-green surviving for non-standard test
    locations. The correct scope is repo-level tests ANYWHERE outside ``src/``.
    Today the marker filter finds zero and the cycle reaches Complete (exit 0)
    -- these assertions are what fails.
    """
    exit_code, payload = _run_cycle_cli(
        monkeypatch,
        capsys,
        tmp_path,
        planter=_seed_unmarked_runnable_suite_nonstandard_location,
    )

    assert exit_code == _EXPECTED_INDETERMINATE_EXIT, (
        "a runnable-but-unmarked contract suite at a NON-STANDARD repo-level "
        "location (custom_tests/, outside tests/ and outside src/) must exit "
        f"{_EXPECTED_INDETERMINATE_EXIT} (CycleIndeterminate) -- it is a real "
        "suite this leg did not observe, never genuinely absent. Got exit "
        f"{exit_code}, payload={payload!r}"
    )
    assert payload.get("event") != "FeatureEndCycleComplete", (
        "the cycle must NEVER emit FeatureEndCycleComplete over an unobserved "
        f"non-standard-location suite: {payload!r}"
    )
    leg_census = payload.get("leg_census")
    if isinstance(leg_census, dict):
        assert int(leg_census.get("indeterminate", 0)) >= 1, (
            "the leg census must record at least one INDETERMINATE leg for the "
            f"un-observed non-standard-location suite: {leg_census!r}"
        )


def test_nonstandard_location_with_root_manifest_yields_indeterminate(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """POSITIVE AT (fixture-realism strengthening, active-RED today): a
    real-shaped foreign repo -- non-standard-location runnable-but-unmarked
    suite (``custom_tests/``) PLUS a realistic top-level manifest file
    (``pyproject.toml``, as every real repo has) -- must still yield
    ``CycleIndeterminate`` (exit 3), never a silent
    ``FeatureEndCycleComplete``.

    The sibling case above (``test_nonstandard_location_runnable_suite_
    yields_cycle_indeterminate``) uses a fixture whose repo root contains
    ONLY the ``custom_tests/`` directory, no top-level file -- it therefore
    does NOT reproduce the #126 defect actually observed on a real ``des
    feature-end run`` surface: ``_repo_has_contract_suite``'s secondary-scope
    comprehension (``feature_end_cycle_service.py:801-805``) filters
    ``repo_root.iterdir()`` by name only (excludes ``src/`` and the
    prune-dirs denylist) and NEVER checks ``entry.is_dir()`` -- so a
    top-level FILE (here ``pyproject.toml``) is included in
    ``secondary_scope`` and handed to
    ``_collect_node_ids(..., paths=secondary_scope, markers=None)``. Pytest
    cannot collect a non-test file as a collection root; the collection
    subprocess exits non-zero, ``_CollectionError`` is raised, the broad
    ``except`` in ``_repo_has_contract_suite`` catches it and returns
    ``False`` -- masking the genuinely-runnable ``custom_tests/`` suite
    behind an unrelated collection failure. Today this repo (real suite +
    real top-level file) reaches a genuine, unstubbed
    ``FeatureEndCycleComplete`` (exit 0) -- these assertions are what fails.
    """
    exit_code, payload = _run_cycle_cli(
        monkeypatch,
        capsys,
        tmp_path,
        planter=_seed_unmarked_runnable_suite_nonstandard_location_with_root_manifest,
    )

    assert exit_code == _EXPECTED_INDETERMINATE_EXIT, (
        "a real-shaped foreign repo (non-standard-location runnable suite "
        "PLUS a top-level pyproject.toml manifest, as every real repo has) "
        f"must exit {_EXPECTED_INDETERMINATE_EXIT} (CycleIndeterminate) -- "
        "the top-level manifest file must not derail the secondary collect "
        "into a masked _CollectionError. Got exit "
        f"{exit_code}, payload={payload!r}"
    )
    assert payload.get("event") != "FeatureEndCycleComplete", (
        "the cycle must NEVER emit FeatureEndCycleComplete over an "
        "unobserved non-standard-location suite merely because the repo "
        f"root also carries a top-level manifest file: {payload!r}"
    )


def test_genuinely_absent_suite_leg_is_not_applicable_but_cycle_is_indeterminate(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """CORRECTED 2026-07-13 (Vera real-surface examine caught this test
    ENSHRINING a declared-behaviour violation): a repo with production source
    but GENUINELY ZERO test files anywhere has nothing to observe -- the
    full-suite LEG legitimately resolves ``FullSuiteLegNotApplicable`` (there
    is nothing to run here). That LEG-level verdict was always correct and
    stays so -- this is NOT the vacuous "everything is Indeterminate" fix.

    What was WRONG (the defect this correction fixes): the PRIOR version of
    this test additionally asserted the CYCLE reaches
    ``FeatureEndCycleComplete`` (exit 0) over that NotApplicable leg --
    CONFLATING the leg-level "nothing to run here" with the cycle-level "I
    verified nothing at all." Per the Ale-ratified 2026-07-13 charter
    (``docs/product/expectations/certification-legs-observe-real-execution/
    feature-end-does-not-certify-done-over-zero-observed-checks.md``), the
    cycle reports done IF AND ONLY IF it observed >=1 leg genuinely RUN
    (``leg_census.ran >= 1``). A genuinely-empty repo (``leg_census.ran ==
    0``) must ALSO report ``FeatureEndCycleIndeterminate`` (exit 3, ADR-GV-002
    D4) -- for the exact same reason a never-observed-but-real suite must:
    neither is "verified done." Special-casing "genuine absence -> Complete"
    is the vacuous INVERSE bug: it still fabricates a done-verdict over zero
    observation, merely for a different reason than the marker-miss cases
    above.

    Today (before the crafter's production fix) ``run_feature_end_cycle``
    (``feature_end_cycle_service.py:396-399,459``) proceeds straight to a
    signed ``CycleSuccess`` whenever every leg is NotApplicable-or-Ran, with
    NO final ``census.ran >= 1`` guard -- these assertions are what fails.
    """
    exit_code, payload = _run_cycle_cli(
        monkeypatch, capsys, tmp_path, planter=_seed_no_tests_at_all
    )

    assert exit_code == _EXPECTED_INDETERMINATE_EXIT, (
        "a repo with GENUINELY zero test files anywhere observed ZERO legs "
        "genuinely running -- the cycle must refuse to certify done "
        f"(CycleIndeterminate, exit {_EXPECTED_INDETERMINATE_EXIT}): "
        f"payload={payload!r}"
    )
    assert payload.get("event") == "FeatureEndCycleIndeterminate", (
        "a genuinely-absent suite must NEVER reach FeatureEndCycleComplete "
        f"-- zero legs observed running is never 'done': {payload!r}"
    )
    leg_census = payload.get("leg_census")
    assert isinstance(leg_census, dict), (
        f"the Indeterminate verdict must carry a leg_census dict: {payload!r}"
    )
    assert leg_census.get("ran") == 0, (
        f"a genuinely-absent suite genuinely ran zero legs: {leg_census!r}"
    )
    assert leg_census.get("not_applicable", 0) >= 1, (
        "the full-suite LEG itself is legitimately NotApplicable (nothing to "
        f"run) -- that leg-level verdict stays correct: {leg_census!r}"
    )


@pytest.mark.negative_at
def test_cycle_complete_requires_at_least_one_leg_genuinely_ran(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """NEGATIVE AT (anti-recurrence, active-RED today, Ale-ratified 2026-07-13
    charter -- the feature's central promise): ``FeatureEndCycleComplete``
    must be emitted ONLY when ``leg_census.ran >= 1``. ANY run whose
    leg_census shows ``ran == 0`` -- for ANY reason, including a
    genuinely-empty repo with no tests at all -- must report
    ``FeatureEndCycleIndeterminate`` (exit 3), NEVER ``FeatureEndCycleComplete``.
    "Done" means "observed", uniformly -- independent of WHICH leg (or how
    many legs) resolved NotApplicable. Today ``run_feature_end_cycle``
    (``feature_end_cycle_service.py:396-399,459``) has no final
    ``census.ran >= 1`` guard before signing and returning ``CycleSuccess`` --
    these assertions are what fails.
    """
    exit_code, payload = _run_cycle_cli(
        monkeypatch, capsys, tmp_path, planter=_seed_no_tests_at_all
    )

    leg_census = payload.get("leg_census")
    assert isinstance(leg_census, dict), (
        f"every cycle outcome must carry a leg_census dict: payload={payload!r}"
    )
    assert leg_census.get("ran") == 0, (
        "this fixture genuinely ran zero legs (nothing observable exists) -- "
        f"leg_census={leg_census!r}"
    )
    assert payload.get("event") != "FeatureEndCycleComplete", (
        "FeatureEndCycleComplete must NEVER be emitted when leg_census.ran "
        f"== 0 ('done' means 'observed', uniformly): {payload!r}"
    )
    assert payload.get("event") == "FeatureEndCycleIndeterminate", (
        "zero legs genuinely ran -- the cycle must report "
        f"FeatureEndCycleIndeterminate, never a fabricated verdict: {payload!r}"
    )
    assert exit_code == _EXPECTED_INDETERMINATE_EXIT, (
        f"expected exit {_EXPECTED_INDETERMINATE_EXIT} (CycleIndeterminate, "
        f"ADR-GV-002 D4); got exit {exit_code}, payload={payload!r}"
    )


def test_unmarked_suite_under_src_keeps_the_leg_not_applicable_not_indeterminate(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """BOUNDARY GUARD -- leg-vs-cycle distinction (CORRECTED 2026-07-13, Vera
    real-surface examine caught the PRIOR version of this test conflating the
    LEG verdict with the CYCLE verdict -- the exact conflation this whole
    slice exists to kill). A runnable-but-unmarked suite bundled UNDER
    ``src/<pkg>/tests/`` is the installable package's OWN fixtures -- observed
    by the env-e2e leg, NOT the repo's contract suite. This test pins TWO
    DIFFERENT invariants at the TWO DIFFERENT altitudes they actually live at:

    1. LEG level (the guard this test exists to preserve): the
       marker-agnostic secondary collect MUST exclude ``src/``, so the
       FULL-SUITE LEG itself resolves ``FullSuiteLegNotApplicable`` -- NEVER
       ``FullSuiteLegIndeterminate`` -- for a suite that lives only under
       ``src/``. An over-broad fix that forgot to exclude ``src/`` would flip
       this leg to Indeterminate; asserted directly against the real,
       unstubbed leg function so this guard cannot be satisfied by accident
       via the cycle-level aggregate.
    2. CYCLE level (Ale-ratified 2026-07-13 charter -- NOT a violation of the
       leg guard above): because no leg genuinely RAN on this minimal fixture
       (the full-suite leg is NotApplicable, and every other leg on this tree
       also resolves NotApplicable -- ``leg_census.ran == 0``), the CYCLE
       correctly reports ``FeatureEndCycleIndeterminate`` (exit 3). This is
       the SAME "done means observed, uniformly" rule every other zero-ran
       fixture in this file is held to -- the src/-only suite earns no
       special-cased Complete verdict; the cycle is Indeterminate for the
       honest reason "nothing was observed", never because the src/ suite was
       misread as the repo's contract suite.

    What was WRONG (the defect this correction fixes): the PRIOR version of
    this test asserted the CYCLE reaches ``FeatureEndCycleComplete`` (exit 0)
    merely because the LEG correctly resolved NotApplicable -- but a
    NotApplicable leg still contributes zero to ``leg_census.ran``, so per the
    charter's blanket "ran >= 1" rule the cycle must be Indeterminate here
    too. Splitting the assertion into its two altitudes preserves the real
    regression guard (src/ exclusion, leg level) without punching a hole in
    the blanket cycle-level invariant (no src/-only carve-out).
    """
    leg_probe_root = tmp_path / "leg-probe"
    leg_probe_root.mkdir()
    repo_root = leg_probe_root / "foreign-repo"
    repo_root.mkdir()
    _seed_unmarked_runnable_suite_under_src(repo_root)

    leg_outcome = svc._run_full_suite_leg(repo_root=repo_root)
    assert isinstance(leg_outcome, svc.FullSuiteLegNotApplicable), (
        "a suite that lives ONLY under src/<pkg>/tests/ must resolve the "
        "FULL-SUITE LEG to NotApplicable -- NEVER Indeterminate -- else the "
        "marker-agnostic secondary collect has stopped excluding src/ (an "
        f"over-broad fix): got {leg_outcome!r}"
    )

    cycle_root = tmp_path / "cycle-drive"
    cycle_root.mkdir()
    exit_code, payload = _run_cycle_cli(
        monkeypatch,
        capsys,
        cycle_root,
        planter=_seed_unmarked_runnable_suite_under_src,
    )

    assert payload.get("event") == "FeatureEndCycleIndeterminate", (
        "zero legs genuinely ran on this fixture (the full-suite leg is "
        "NotApplicable, not Ran, and every sibling leg on this minimal tree "
        "is also NotApplicable) -- the cycle must report "
        "FeatureEndCycleIndeterminate, per the same 'done means observed, "
        f"uniformly' rule every other zero-ran fixture in this file is held "
        f"to: {payload!r}"
    )
    assert exit_code == _EXPECTED_INDETERMINATE_EXIT, (
        f"expected exit {_EXPECTED_INDETERMINATE_EXIT} (CycleIndeterminate, "
        f"ADR-GV-002 D4); got exit {exit_code}, payload={payload!r}"
    )
    leg_census = payload.get("leg_census")
    if isinstance(leg_census, dict):
        assert leg_census.get("ran") == 0, (
            "no leg genuinely ran on this fixture -- the src/-only suite "
            f"correctly contributes NotApplicable, never Ran: {leg_census!r}"
        )
        assert leg_census.get("indeterminate", 0) == 0, (
            "the src/-only suite must NOT itself contribute an Indeterminate "
            "leg -- the cycle-level Indeterminate verdict here is caused "
            "SOLELY by 'nothing ran', never by the src/ suite being misread "
            f"as the repo's contract suite: {leg_census!r}"
        )


def test_complete_verdict_surfaces_leg_census_distinguishing_ran_from_absent(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """POSITIVE AT (active-RED today, DDD-CERT-2 leg_census gap; STRENGTHENED
    2026-07-13 alongside the genuine-absence correction above): the charter
    (``docs/product/expectations/certification-legs-observe-real-execution/
    feature-end-does-not-certify-done-over-zero-observed-checks.md``) demands
    a project with a genuinely-run real test suite and a project with NO
    tests at all get DIFFERENT, DISTINGUISHABLE verdicts -- "those are
    different situations and must produce different, distinguishable
    verdicts." Per the Ale-ratified 2026-07-13 charter they are now
    distinguished at the STRONGEST possible level -- a different EVENT
    entirely, not merely a different leg_census hiding behind the same
    event: Fixture A (genuinely ran >=1 leg) reaches
    ``FeatureEndCycleComplete`` WITH ``leg_census.ran >= 1``; Fixture C
    (genuinely zero legs ran) reaches ``FeatureEndCycleIndeterminate`` (exit
    3) WITH ``leg_census.ran == 0`` -- never a shared ``Complete`` verdict
    papering over the difference (the #126/#179 silent false-green this
    feature closes).

    Fixture A (genuinely RAN): a real, MARKED (``@pytest.mark.unit``) pytest
    suite at the conventional ``tests/`` root, plus a realistic top-level
    ``pyproject.toml`` -- the marker-filtered collect finds >=1 node-id, so
    the REAL, unstubbed full-suite leg genuinely DISPATCHES ``des
    run-contract-gate`` (an actual pytest subprocess) and observes
    ``FullSuiteLegRan``.

    Fixture C (genuinely ABSENT): a repo with production source but ZERO
    test files anywhere -- nothing to observe, ``FullSuiteLegNotApplicable``
    at the leg level, which now correctly escalates the CYCLE to
    Indeterminate (never Complete).

    Today ``run_feature_end_cycle`` has no final ``census.ran >= 1`` guard --
    both reach the byte-identical ``CycleSuccess`` -> ``FeatureEndCycleComplete``
    (exit 0), indistinguishable at the observable CLI surface. These
    assertions are what fails.
    """
    (tmp_path / "ran").mkdir()
    (tmp_path / "absent").mkdir()
    exit_ran, payload_ran = _run_cycle_cli(
        monkeypatch,
        capsys,
        tmp_path / "ran",
        planter=_seed_marked_runnable_suite_with_manifest,
    )
    exit_absent, payload_absent = _run_cycle_cli(
        monkeypatch,
        capsys,
        tmp_path / "absent",
        planter=_seed_no_tests_at_all,
    )

    assert exit_ran == 0, (
        f"a genuinely-run marked suite must reach exit 0: payload={payload_ran!r}"
    )
    assert payload_ran.get("event") == "FeatureEndCycleComplete", (
        f"a genuinely-run marked suite must reach Complete: payload={payload_ran!r}"
    )
    assert exit_absent == _EXPECTED_INDETERMINATE_EXIT, (
        "a genuinely-absent suite observed zero legs running -- it must "
        f"exit {_EXPECTED_INDETERMINATE_EXIT} (CycleIndeterminate), never "
        f"Complete: payload={payload_absent!r}"
    )
    assert payload_absent.get("event") == "FeatureEndCycleIndeterminate", (
        "a genuinely-absent suite must NEVER share the Complete verdict with "
        f"a genuinely-run suite: payload={payload_absent!r}"
    )

    leg_census_ran = payload_ran.get("leg_census")
    assert isinstance(leg_census_ran, dict), (
        "the Complete verdict over a suite the full-suite leg genuinely RAN "
        f"must carry a leg_census dict (DDD-CERT-2): payload={payload_ran!r}"
    )
    assert int(leg_census_ran.get("ran", 0)) >= 1, (
        "Fixture A's leg_census must show at least one leg genuinely RAN "
        f"(the full-suite leg observed a real, marked, passing suite): "
        f"leg_census={leg_census_ran!r}"
    )

    leg_census_absent = payload_absent.get("leg_census")
    assert isinstance(leg_census_absent, dict), (
        "the Indeterminate verdict over a GENUINELY absent suite must ALSO "
        f"carry a leg_census dict: payload={payload_absent!r}"
    )
    assert int(leg_census_absent.get("ran", 0)) == 0, (
        "Fixture C never genuinely ran a full suite -- its leg_census must "
        f"show zero legs ran: leg_census={leg_census_absent!r}"
    )

    assert leg_census_ran != leg_census_absent, (
        "a genuinely-run real suite and a genuinely-absent suite are "
        "DIFFERENT situations (the charter's own words) and must produce "
        "DISTINGUISHABLE leg_census verdicts -- got IDENTICAL leg_census "
        f"for both: {leg_census_ran!r}"
    )


@pytest.mark.negative_at
def test_complete_verdict_never_omits_leg_census(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """NEGATIVE AT (anti-recurrence, active-RED today; CORRECTED 2026-07-13,
    Vera real-surface examine caught the PRIOR version of this test
    ENSHRINING a declared-behaviour violation): a verdict must NEVER omit
    ``leg_census`` -- independent of WHICH verdict the cycle reaches, dropping
    the census is exactly the #126/#179-adjacent regression this feature
    closes (a reader can no longer tell what the cycle actually observed).
    That substantive claim is CORRECT and survives unweakened here; only the
    fixture-to-verdict pairing was wrong (see below).

    Pinned at its STRONGEST form: BOTH verdict shapes a real cycle can reach
    carry a leg_census --
    - Fixture A (a real, marked, genuinely-run suite): reaches
      ``FeatureEndCycleComplete`` WITH ``leg_census.ran >= 1``;
    - Fixture C (a genuinely-empty repo, nothing to observe): reaches
      ``FeatureEndCycleIndeterminate`` WITH ``leg_census.ran == 0``.
    A reader must never lose the census, whichever verdict is emitted.

    What was WRONG (the defect this correction fixes): the PRIOR version of
    this test used the genuinely-empty fixture (``_seed_no_tests_at_all``,
    ``leg_census.ran == 0``) yet still asserted ``exit_code == 0`` /
    ``FeatureEndCycleComplete`` -- its SIBLING test on the IDENTICAL fixture
    (``test_genuinely_absent_suite_leg_is_not_applicable_but_cycle_is_
    indeterminate``) was already corrected to expect Indeterminate on the SAME
    date; the correction was simply never propagated here. Per the
    Ale-ratified 2026-07-13 charter (``docs/product/expectations/
    certification-legs-observe-real-execution/
    feature-end-does-not-certify-done-over-zero-observed-checks.md``),
    ``leg_census.ran == 0`` -- for ANY reason, including genuine absence --
    is ALWAYS Indeterminate, never Complete. This corrected version keeps the
    "never omits leg_census" claim but checks it on the verdict each fixture
    ACTUALLY produces.
    """
    (tmp_path / "complete").mkdir()
    (tmp_path / "indeterminate").mkdir()
    exit_complete, payload_complete = _run_cycle_cli(
        monkeypatch,
        capsys,
        tmp_path / "complete",
        planter=_seed_marked_runnable_suite_with_manifest,
    )
    assert exit_complete == 0, (
        f"a genuinely-run marked suite must reach exit 0: {payload_complete!r}"
    )
    assert payload_complete.get("event") == "FeatureEndCycleComplete", (
        f"expected FeatureEndCycleComplete: {payload_complete!r}"
    )
    assert "leg_census" in payload_complete, (
        "FeatureEndCycleComplete must NEVER omit leg_census (DDD-CERT-2): "
        f"got payload={payload_complete!r}"
    )
    complete_census = payload_complete["leg_census"]
    assert isinstance(complete_census, dict) and complete_census.get("ran", 0) >= 1, (
        "the Complete verdict's leg_census must show >=1 leg genuinely ran: "
        f"{complete_census!r}"
    )

    exit_indeterminate, payload_indeterminate = _run_cycle_cli(
        monkeypatch,
        capsys,
        tmp_path / "indeterminate",
        planter=_seed_no_tests_at_all,
    )
    assert exit_indeterminate == _EXPECTED_INDETERMINATE_EXIT, (
        "a genuinely-empty repo must reach exit "
        f"{_EXPECTED_INDETERMINATE_EXIT} (CycleIndeterminate): "
        f"{payload_indeterminate!r}"
    )
    assert payload_indeterminate.get("event") == "FeatureEndCycleIndeterminate", (
        f"expected FeatureEndCycleIndeterminate: {payload_indeterminate!r}"
    )
    assert "leg_census" in payload_indeterminate, (
        "FeatureEndCycleIndeterminate must NEVER omit leg_census (DDD-CERT-2): "
        f"got payload={payload_indeterminate!r}"
    )
    indeterminate_census = payload_indeterminate["leg_census"]
    assert (
        isinstance(indeterminate_census, dict) and indeterminate_census.get("ran") == 0
    ), (
        "the Indeterminate verdict's leg_census must show zero legs ran: "
        f"{indeterminate_census!r}"
    )


def test_found_and_excluded_suite_indeterminate_payload_names_what_was_found(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """POSITIVE AT (active-RED today, Vera real-surface examine 2026-07-13 --
    ``docs/product/expectations/certification-legs-observe-real-execution/
    feature-end-does-not-certify-done-over-zero-observed-checks.md``): a repo
    whose ONLY tests live under ``src/<pkg>/tests/`` (the installable
    package's own fixtures, correctly excluded from the repo's contract
    suite -- see ``test_unmarked_suite_under_src_keeps_the_leg_not_applicable_
    not_indeterminate`` above, which pins that LEG-level exclusion and must
    stay unchanged) reaches ``FeatureEndCycleIndeterminate`` for the SAME
    surface reason a repo with GENUINELY ZERO tests anywhere does
    (``leg_census.ran == 0``) -- but on the REAL CLI surface Vera walked, the
    two cases emit a BYTE-IDENTICAL ``error`` string ("the feature-end cycle
    observed zero legs genuinely run ... every leg resolved NOT_APPLICABLE"),
    so a reader cannot tell "you have tests, but they live under src/ (the
    package's own fixtures, not the repo's contract suite) -- put a suite at
    the repo root" from "you have no tests at all". The charter's own words:
    "the certification must NOT silently substitute 'nothing was applicable'
    for 'I could not reach/run what was there' -- an unreached-but-real suite
    is a failure to verify, not an absence of anything to verify."

    This AT pins the found-and-excluded payload's ``error`` text NAMES what
    it saw (a suite exists) and WHY it was excluded (not the repo's contract
    suite) -- the self-explaining WHAT/WHY/HOW contract
    ([[feedback_every_failure_explains_what_why_how_to_fix_2026_06_26]]).
    Today the ``error`` text is the generic, fixture-independent boilerplate
    at ``feature_end_cycle_service.py:457-465`` -- this assertion is what
    fails.
    """
    exit_code, payload = _run_cycle_cli(
        monkeypatch,
        capsys,
        tmp_path,
        planter=_seed_unmarked_runnable_suite_under_src,
    )

    assert exit_code == _EXPECTED_INDETERMINATE_EXIT, (
        "a src/-only suite genuinely runs zero cycle legs (the leg itself is "
        f"correctly NotApplicable) -- the cycle must exit "
        f"{_EXPECTED_INDETERMINATE_EXIT}: payload={payload!r}"
    )
    assert payload.get("event") == "FeatureEndCycleIndeterminate", (
        f"expected FeatureEndCycleIndeterminate: {payload!r}"
    )
    error_text = str(payload.get("error", "")).lower()
    found_something = any(
        marker in error_text for marker in ("found", "discovered", "detected", "saw")
    )
    excluded_something = any(
        marker in error_text
        for marker in ("exclud", "not the", "contract suite", "package", "src")
    )
    assert found_something and excluded_something, (
        "the found-and-excluded payload's 'error' text must NAME what was "
        "found (a real suite exists) and WHY it was excluded (not the "
        "repo's contract suite) -- a reader must be able to act on it "
        f"without investigating source: error={payload.get('error')!r}"
    )


@pytest.mark.negative_at
def test_found_and_excluded_payload_never_matches_genuinely_absent_payload(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """NEGATIVE AT (anti-recurrence, active-RED today, Vera real-surface
    examine 2026-07-13): the found-and-excluded case (real tests under
    ``src/<pkg>/tests/``) and the genuinely-absent case (zero test files
    anywhere) must NEVER emit the same undifferentiated ``error`` text --
    "those are different situations and must produce different,
    distinguishable verdicts" (the charter's own words,
    ``docs/product/expectations/certification-legs-observe-real-execution/
    feature-end-does-not-certify-done-over-zero-observed-checks.md``). Today
    BOTH reach the byte-identical static string at
    ``feature_end_cycle_service.py:457-465`` -- this assertion is what fails.
    """
    (tmp_path / "found-excluded").mkdir()
    (tmp_path / "genuinely-absent").mkdir()
    _, payload_found = _run_cycle_cli(
        monkeypatch,
        capsys,
        tmp_path / "found-excluded",
        planter=_seed_unmarked_runnable_suite_under_src,
    )
    _, payload_absent = _run_cycle_cli(
        monkeypatch,
        capsys,
        tmp_path / "genuinely-absent",
        planter=_seed_no_tests_at_all,
    )

    assert payload_found.get("event") == "FeatureEndCycleIndeterminate", (
        f"expected FeatureEndCycleIndeterminate for the found-and-excluded "
        f"fixture: {payload_found!r}"
    )
    assert payload_absent.get("event") == "FeatureEndCycleIndeterminate", (
        f"expected FeatureEndCycleIndeterminate for the genuinely-absent "
        f"fixture: {payload_absent!r}"
    )

    error_found = payload_found.get("error")
    error_absent = payload_absent.get("error")
    assert error_found != error_absent, (
        "a repo with real tests found-and-excluded (src/-only) and a repo "
        "with GENUINELY zero tests anywhere are different situations and "
        "must never emit the same undifferentiated 'error' text -- got "
        f"IDENTICAL text for both: {error_found!r}"
    )
