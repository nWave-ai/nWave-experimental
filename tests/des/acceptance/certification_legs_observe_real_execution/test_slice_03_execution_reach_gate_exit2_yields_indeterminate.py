"""Feature `certification-legs-observe-real-execution`, slice-03 (DDD-CERT-4).

Value statement (feature-delta.md [REF] Slice Plan, slice-03): a `des
feature-end run` where the execution-reach/doc-coherence/fresh-clone gate
degrades to its OWN exit-2 (e.g. a present-but-malformed ``coverage.xml``)
gets ``CycleIndeterminate``, never a silently-recycled ``NotApplicable``.

Found in ``src/des/application/feature_end_cycle_service.py::
_run_execution_reach_gate`` (:891-894, and the identical-FORM siblings
``_run_doc_coherence_gate`` :813-816 and ``_run_fresh_clone_gate``
:939-942): all three legs share the SAME branch --

    if completed.returncode == 2:
        return ExecutionReachLegNotApplicable(
            "the execution-reach gate degraded to INDETERMINATE; not applicable"
        )

The STANDALONE gate's own exit-2 ("I cannot judge" -- here, a malformed
Cobertura ``coverage.xml`` the real ``des verify-execution-reach`` subprocess
cannot parse, ``verify_execution_reach.py::_parse_report`` ``ElementTree.
ParseError`` branch, :119-124) is mapped to ``*LegNotApplicable`` ("there is
nothing to judge"). This is a DISTINCT branch from the PRECONDITION-FIRST
absence check (``coverage_xml_path.is_file()``, :873-877, run BEFORE any
subprocess) -- that check legitimately stays NA when the artifact genuinely
does not exist. The aggregate (today: ``CycleSuccess``, no escalation) cannot
distinguish "the gate genuinely had nothing to check" from "the gate WAS
invoked and could not judge" -- exactly the epistemic-failure ->
ontological-absence conflation DDD-CERT-1 names, generalized here across the
3 sibling legs (DDD-CERT-4).

This slice reuses slice-02's ``CycleIndeterminate`` + ``LegCensus`` aggregate
(already landed, C4/C5) -- no new aggregate type, only the 3 sibling legs'
``== 2`` branch changes from ``*LegNotApplicable`` to a NEW ``*LegIndeterminate``
(not yet defined in ``feature_end_cycle_service`` -- this AT drives the
CLI-level ``des feature-end run`` observable per the task, never the
not-yet-existing class name directly).

Driving surface (Mandate-13 driving-port-only, Layer 3 composition,
IN-PROCESS default): the REAL ``des.cli.feature_end.main(["run", ...])`` CLI
driver, captured via ``capsys`` -- the SAME in-process pattern slice-01/02's
ATs use. Per the Test Reuse & Consolidation Analysis row ("slice-02/03's
CycleIndeterminate/LegCensus ATs reuse the SAME tmp-target-repo +
subprocess-dispatch fixture shape"), the sibling legs this slice does not
target (walking-skeleton, environmental-e2e, coverage-map) are stubbed via
monkeypatch -- mirrors ``test_feature_end_cycle_execution_reach_gate.py``'s
``_stub_non_execution_reach_legs`` pattern -- so only the REAL, unstubbed
execution-reach leg (and its real ``des verify-execution-reach`` subprocess
dispatch) determines the cycle's outcome. Full-suite, doc-coherence, and
fresh-clone are left REAL and resolve to their genuine NOT_APPLICABLE arm on
the minimal fixture tree used by the two exit-2 scenarios above (no
marked/unmarked tests, no README/docs, no demo-recipe) -- unchanged, real
preconditions, never stubbed. The genuinely-absent-coverage regression-guard
fixture (below, corrected 2026-07-14) is the one exception: it ALSO seeds a
real, marked, genuinely-running full-suite leg so the CYCLE-level Complete
verdict it asserts stays coherent with slice-02's ``leg_census.ran >= 1``
charter, never touching the doc-coherence/fresh-clone NOT_APPLICABLE arms.

Active-RED today (real assertion failures, never an import/collection
error): the fixture plants a REAL ``coverage.xml`` that is present but not
well-formed XML, so the real ``des verify-execution-reach`` subprocess
genuinely exits 2 (``ExecutionReachIndeterminate``) -- but
``_run_execution_reach_gate`` today maps that exit-2 to
``ExecutionReachLegNotApplicable`` (silently recycled), the cycle proceeds
unescalated, and reaches a genuine, unstubbed ``CycleSuccess`` ->
``FeatureEndCycleComplete`` (exit 0) today. The positive AT below asserts the
observable exit-3 / ``CycleIndeterminate`` contract, so the failure is a
genuine ``AssertionError`` on the observed exit code / payload, exactly as
this task requires.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.application import feature_end_cycle_service as svc
from des.cli import feature_end as feature_end_cli


_FEATURE_ID = "fixture-feature-slice03"

# ADR-GV-002 D4 (already wired at the CLI shim, `feature_end.py:195-213`,
# landed in slice-02): `des feature-end run` maps `CycleIndeterminate` to
# exit 3, mirroring `run_contract_gate.py:113-116`'s existing local
# `_GATE_INDETERMINATE_EXIT_CODE = 3` pattern. What is NOT yet wired is the
# PRODUCER: the execution-reach leg's exit-2 branch never constructs an
# Indeterminate leg today, so this exit is the PINNED target, not an
# assumption already satisfied end-to-end.
_EXPECTED_INDETERMINATE_EXIT = 3

_MALFORMED_COVERAGE_XML = "<coverage><packages><unclosed></coverage>\n"


def _seed_feature_dir(repo_root: Path, feature_id: str = _FEATURE_ID) -> Path:
    """A minimal feature-dir with NO feature-delta.md (no Slice-Plan -> no
    undelivered-slice truncation refusal -- mirrors
    ``test_feature_end_cycle_execution_reach_gate.py::_seed_feature_dir``,
    keeping the fixture focused on the execution-reach leg alone)."""
    feature_dir = repo_root / "docs" / "feature" / feature_id
    feature_dir.mkdir(parents=True)
    return feature_dir


def _seed_present_but_malformed_coverage_xml(repo_root: Path) -> None:
    """A ``coverage.xml`` that IS present (the precondition-first check
    passes, the real gate subprocess is genuinely dispatched) but is NOT
    well-formed XML -- the exact shape the real ``des verify-execution-reach``
    gate's own ``ElementTree.ParseError`` branch (``verify_execution_reach.py``
    :119-124) turns into its OWN honest exit-2 INDETERMINATE. Distinct from a
    genuinely-ABSENT ``coverage.xml`` (the regression-guard case below), which
    never reaches a subprocess at all.
    """
    src = repo_root / "src"
    src.mkdir(parents=True)
    (src / "widget.py").write_text("def greet():\n    return 'ok'\n", encoding="utf-8")
    (repo_root / "coverage.xml").write_text(_MALFORMED_COVERAGE_XML, encoding="utf-8")


_MARKED_RUNNABLE_TEST_BODY = (
    "import pytest\n\n\n@pytest.mark.unit\ndef test_widget_behaves():\n"
    "    assert 1 + 1 == 2\n"
)


def _seed_genuinely_absent_coverage(repo_root: Path) -> None:
    """No ``coverage.xml`` anywhere under ``repo_root`` -- the PRECONDITION
    check (``coverage_xml_path.is_file()``) fails BEFORE any subprocess is
    spawned, so the execution-reach LEG stays legitimately NOT_APPLICABLE
    (regression-guard: the fix must be scoped to the POST-subprocess exit-2
    case only, never to every absence).

    CORRECTED 2026-07-14 (mis-specification against slice-02's ratified
    charter, ``docs/product/expectations/certification-legs-observe-real-
    execution/feature-end-does-not-certify-done-over-zero-observed-checks.md``):
    the PRIOR version of this fixture seeded ONLY ``src/widget.py`` -- no
    tests, no coverage.xml, no docs, no demo -- so EVERY feature-end leg
    resolved NOT_APPLICABLE (``leg_census.ran == 0``) and the cycle's OWN
    ``census.ran == 0`` guard (``feature_end_cycle_service.py:551``, shipped
    by slice-02) correctly refused with ``CycleIndeterminate``. That guard
    must never be reverted -- it is the fix for the #126/#179 silent
    false-green. Per charter EXP-1 (``could-not-judge-is-not-not-
    applicable.md``), the genuine-absence scenario this test pins is an
    "ordinary, presumably-passing nWave feature (tests green, code
    committed)" -- i.e. it HAS a genuinely-running leg. This fixture now
    ALSO seeds a real, marked (``@pytest.mark.unit``), runnable pytest suite
    at the conventional ``tests/`` root plus a realistic top-level
    ``pyproject.toml`` manifest -- mirrors slice-02's own
    ``_seed_marked_runnable_suite_with_manifest`` -- so the full-suite leg
    genuinely RUNS and passes (``leg_census.ran >= 1``), while
    ``coverage.xml`` stays genuinely ABSENT. The cycle legitimately reaches
    ``FeatureEndCycleComplete`` because a real leg ran; the fact this test
    actually pins is the LEG-LEVEL distinction (execution-reach resolves
    NOT_APPLICABLE, never Indeterminate, on genuine absence) -- not
    "Complete over all-NA", which belongs to slice-02 and stays
    Indeterminate there.
    """
    src = repo_root / "src"
    src.mkdir(parents=True)
    (src / "widget.py").write_text("def greet():\n    return 'ok'\n", encoding="utf-8")
    tests_dir = repo_root / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_widget.py").write_text(
        _MARKED_RUNNABLE_TEST_BODY, encoding="utf-8"
    )
    (repo_root / "pyproject.toml").write_text(
        '[project]\nname = "fixture-feature-slice03"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )


def _stub_non_execution_reach_legs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Short-circuit every OTHER leg so only the REAL (unstubbed)
    execution-reach leg -- and its real ``des verify-execution-reach``
    subprocess dispatch -- can determine the cycle's outcome. Mirrors
    ``test_feature_end_cycle_execution_reach_gate.py::
    _stub_non_execution_reach_legs``; the full-suite leg is left REAL (it
    naturally resolves NotApplicable on this empty-of-tests fixture, no
    stub needed, mirrors slice-02's own fixture shape)."""
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
    seed: object,
) -> tuple[int, dict[str, object]]:
    """Stage a fixture (via ``seed``) and drive the REAL ``des feature-end
    run`` CLI in-process (Layer 3 composition). Returns ``(exit_code,
    parsed_json_payload)`` -- the command's real observables.
    """
    _stub_non_execution_reach_legs(monkeypatch)
    repo_root = tmp_path / "target-repo"
    repo_root.mkdir()
    seed(repo_root)
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


def test_execution_reach_gate_exit2_yields_cycle_indeterminate(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """POSITIVE AT (active-RED today): a present-but-malformed ``coverage.xml``
    makes the real ``des verify-execution-reach`` gate genuinely exit 2
    (INDETERMINATE -- it could not judge, never a pass). The feature-end
    cycle must escalate to ``CycleIndeterminate`` (exit 3, ADR-GV-002 D4) --
    never silently recycle the gate's own "I cannot judge" into
    ``ExecutionReachLegNotApplicable`` and proceed. Today the leg's
    ``returncode == 2`` branch maps to NotApplicable and the cycle proceeds
    to a genuine ``CycleSuccess`` (exit 0) -- these assertions are what
    fails.
    """
    exit_code, payload = _run_cycle_cli(
        monkeypatch, capsys, tmp_path, _seed_present_but_malformed_coverage_xml
    )

    assert exit_code == _EXPECTED_INDETERMINATE_EXIT, (
        "a target repo whose coverage.xml IS present but the real "
        "verify-execution-reach gate genuinely exits 2 (malformed XML, "
        "could-not-judge) must exit "
        f"{_EXPECTED_INDETERMINATE_EXIT} (CycleIndeterminate, ADR-GV-002 D4) "
        "-- the gate's own epistemic failure must never be silently recycled "
        f"into NotApplicable. Got exit {exit_code}, payload={payload!r}"
    )
    assert payload.get("event") != "FeatureEndCycleComplete", (
        "the cycle must NEVER emit FeatureEndCycleComplete while the "
        f"execution-reach leg's own gate-degrade went unobserved: {payload!r}"
    )
    payload_text = json.dumps(payload).lower()
    assert "execution-reach" in payload_text or "execution_reach" in payload_text, (
        "the INDETERMINATE verdict must NAME the un-observed "
        f"ExecutionReachLeg (DDD-CERT-4) so a crafter knows WHICH leg's "
        f"own gate degraded -- got: {payload!r}"
    )
    leg_census = payload.get("leg_census")
    if isinstance(leg_census, dict):
        assert leg_census.get("indeterminate", 0) >= 1, (
            "leg_census must record >=1 indeterminate leg (the execution-"
            f"reach leg's own gate-degrade): {leg_census!r}"
        )


@pytest.mark.negative_at
def test_execution_reach_gate_exit2_never_recycles_to_not_applicable_then_complete(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """NEGATIVE AT (anti-recurrence, active-RED today): given the SAME
    present-but-malformed ``coverage.xml`` fixture, the cycle must NEVER
    recycle the gate's own exit-2 into ``ExecutionReachLegNotApplicable``
    and proceed to a signed, green verdict -- it must never exit 0 and must
    never emit ``FeatureEndCycleComplete``. Today the cycle DOES exactly
    that (the exit-2 -> NotApplicable conflation this feature closes) --
    these assertions are what fails.
    """
    exit_code, payload = _run_cycle_cli(
        monkeypatch, capsys, tmp_path, _seed_present_but_malformed_coverage_xml
    )

    assert exit_code != 0, (
        "a cycle whose execution-reach leg's own gate genuinely could not "
        f"judge (exit 2) must never exit 0: {payload!r}"
    )
    assert payload.get("event") != "FeatureEndCycleComplete", (
        "FeatureEndCycleComplete must never be emitted over an execution-"
        f"reach leg the gate itself could not judge: {payload!r}"
    )


def test_genuinely_absent_coverage_xml_stays_not_applicable_regression(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """REGRESSION-GUARD (C6, DDD-CERT-4 "regression"): a target repo that
    NEVER produced a ``coverage.xml`` at all (the PRECONDITION-FIRST check
    fails BEFORE any subprocess is spawned) keeps the execution-reach LEG
    legitimately ``ExecutionReachLegNotApplicable`` -- NEVER
    ``ExecutionReachLegIndeterminate`` -- this is the genuinely-ontological-
    absence case DDD-CERT-1 distinguishes from the epistemic-failure case
    above, and it must NOT flip to Indeterminate when the fix lands (the
    crafter cannot satisfy this slice by making EVERY exit-2-shaped case
    Indeterminate).

    CORRECTED 2026-07-14 (mis-specification against slice-02's ratified
    charter caught pre-GREEN): the PRIOR version of this test drove a
    fixture with NO genuinely-running leg at all (only ``src/widget.py``,
    no tests) and asserted the CYCLE reaches ``FeatureEndCycleComplete`` --
    that directly contradicts slice-02's shipped ``census.ran == 0`` guard
    (``feature_end_cycle_service.py:551``, commit ``4c976e0a3``): an all-NA
    repo correctly yields ``CycleIndeterminate`` (exit 3) per the
    Ale-ratified charter ``feature-end-does-not-certify-done-over-zero-
    observed-checks.md`` ("the certification must NOT report 'complete /
    done' ... on any run where the number of checks actually observed
    running is ZERO"). That guard must never be reverted.

    This corrected version asserts the TRUE intent at TWO altitudes (mirrors
    slice-02's own leg-vs-cycle split,
    ``test_unmarked_suite_under_src_keeps_the_leg_not_applicable_not_
    indeterminate``):

    1. LEG level (the regression guard this test exists to preserve): call
       the REAL, unstubbed ``_run_execution_reach_gate`` directly on the
       genuinely-absent-coverage fixture and assert it resolves
       ``ExecutionReachLegNotApplicable`` -- never ``*Indeterminate``.
    2. CYCLE level (now legitimate, not a charter violation): the fixture
       ALSO seeds a real, marked, genuinely-running full-suite leg
       (``_seed_genuinely_absent_coverage``, corrected above), so
       ``leg_census.ran >= 1`` and the cycle rightfully reaches
       ``FeatureEndCycleComplete`` (exit 0) -- this is NOT "Complete over
       all-NA" (that scenario is slice-02's, and its answer stays
       Indeterminate); it is "Complete because a real leg ran, AND the
       execution-reach leg specifically stayed NA rather than flipping to
       Indeterminate on genuine absence."
    """
    leg_probe_root = tmp_path / "leg-probe" / "target-repo"
    leg_probe_root.mkdir(parents=True)
    _seed_genuinely_absent_coverage(leg_probe_root)
    leg_outcome = svc._run_execution_reach_gate(
        ledger=AtCompletionLedger(_FEATURE_ID, leg_probe_root),
        repo_root=leg_probe_root,
        feature_id=_FEATURE_ID,
    )
    assert isinstance(leg_outcome, svc.ExecutionReachLegNotApplicable), (
        "a target repo that never produced a coverage.xml at all (genuine "
        "ontological absence, precondition-first, no subprocess spawned) "
        "must resolve the EXECUTION-REACH LEG to NotApplicable -- NEVER "
        f"Indeterminate: got {leg_outcome!r}"
    )

    exit_code, payload = _run_cycle_cli(
        monkeypatch, capsys, tmp_path, _seed_genuinely_absent_coverage
    )

    assert exit_code == 0, (
        "the fixture ALSO seeds a real, marked, genuinely-running full-suite "
        "leg, so the cycle legitimately observes >=1 leg genuinely run and "
        f"must reach exit 0 (FeatureEndCycleComplete): {payload!r}"
    )
    assert payload.get("event") == "FeatureEndCycleComplete", (
        "a genuinely-absent coverage.xml, alongside a genuinely-running "
        f"full-suite leg, must still reach FeatureEndCycleComplete: {payload!r}"
    )
    leg_census = payload.get("leg_census")
    assert isinstance(leg_census, dict), (
        f"the Complete verdict must carry a leg_census dict: {payload!r}"
    )
    assert leg_census.get("ran", 0) >= 1, (
        "the Complete verdict is legitimate ONLY because >=1 leg genuinely "
        f"ran (the marked full-suite leg) -- never over zero observation: "
        f"{leg_census!r}"
    )
