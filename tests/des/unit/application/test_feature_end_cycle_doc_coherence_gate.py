# @feature-wire-p0-gates-at-feature-end
# @slice-03
"""Feature-end doc-coherence gate: wires ``des verify-doc-coherence``.

wire-p0-gates-at-feature-end slice-03. ``run_feature_end_cycle`` must invoke
the REAL ``des verify-doc-coherence`` gate (evolution-plan P0.5) and derive
its verdict from the REAL exit code -- a feature whose shipped docs claim an
npm script, file path, or ``python -m`` module that does not exist in the
committed tree must be refused (``CycleRefusal``), never silently signed
done.

Unit-level, hermetic: sibling legs (walking-skeleton, env-e2e, coverage-map,
full-suite) are stubbed to PASS/NOT_APPLICABLE (mirrors
``test_feature_end_cycle_examine_gate.py``'s ``_stub_upstream_legs`` pattern)
so the test isolates the NEW doc-coherence leg. The doc-coherence gate itself
is NEVER stubbed: the fixture plants a REAL README (same shape as
``tests/des/unit/cli/test_verify_doc_coherence.py``) claiming an absent npm
script and an absent file path, so once wired the leg's real subprocess
dispatch genuinely observes the planted defect.

Active-RED today (impl missing): ``run_feature_end_cycle`` does not yet call
``verify-doc-coherence`` at all, so every fixture below reaches
``CycleSuccess`` regardless of the planted defect. The other two tests are
REGRESSION/GENERICITÀ guards (already green -- they pin the unchanged/NA
behaviour the new leg must preserve once wired).

SUPERSEDED (2026-07-16, ratified by
``docs/product/expectations/fix-doc-coherence-gate-warns-not-blocks/
doc-coherence-findings-warn-loud-never-block-feature-end.md``):
``test_doc_overstating_absent_code_refuses_feature_end`` originally pinned a
HARD-REFUSAL (``CycleRefusal``) on doc-coherence violations. That behavior is
intentionally superseded -- doc-coherence findings now WARN LOUD and let the
cycle PROCEED to ``CycleSuccess`` (a new ``DocCoherenceWarned`` ledger event,
folded into ``leg_census.warned``), never a hard block. Renamed to
``test_doc_overstating_absent_code_warns_but_does_not_refuse_feature_end`` and
updated to assert the new contract; the superseded HARD-REFUSAL behavior
remains in git history. This is the canonical, exhaustively-specified pin for
the new contract (see also the regression AT,
``tests/bugs/des/test_doc_coherence_gate_warns_not_blocks_feature_end.py``,
whose harness/assertion style this test mirrors).

Requirement coverage markers (R5/R6/R7/R8) are placed per-TEST-FUNCTION below
(the ``verify-spec-coverage`` gate's marker scan is function-scoped -- a
module-level docstring marker is invisible to it; see DISTILL FRICTIONS).
"""

from __future__ import annotations

import json
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.application import feature_end_cycle_service as svc
from des.application.feature_end_cycle_service import (
    CycleSuccess,
    FullSuiteLegNotApplicable,
    FullSuiteLegRan,
    run_feature_end_cycle,
)


_FEATURE_ID = "feat-doc-coherence-gate"
_OVERSTATING_README = (
    "# Demo\n\n"
    "Run `npm run e2e:golden` to verify.\n\n"
    "The reconciler lives in `src/reconciler.ts`.\n"
)
_HONEST_README = "# Demo\n\nThis project has no scripted demo yet.\n"

_MARKED_RUNNABLE_TEST_BODY = (
    "import pytest\n\n\n@pytest.mark.unit\ndef test_widget_behaves():\n"
    "    assert 1 + 1 == 2\n"
)


def _seed_marked_runnable_suite(repo_root: Path) -> None:
    """A real, marked (``@pytest.mark.unit``), runnable pytest suite at the
    conventional ``tests/`` root plus a realistic top-level ``pyproject.toml``
    manifest -- mirrors
    ``test_slice_03_execution_reach_gate_exit2_yields_indeterminate.py``'s
    ``_seed_genuinely_absent_coverage`` full-suite seed. Makes the full-suite
    leg genuinely RUN (``FullSuiteLegRan``), so ``leg_census.ran >= 1`` and the
    all-other-legs-NA regression fixture below stays coherent with slice-02's
    ratified ``census.ran == 0`` -> ``CycleIndeterminate`` charter (it is
    legitimately ``ran == 1``, not ``ran == 0``)."""
    tests_dir = repo_root / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_widget.py").write_text(
        _MARKED_RUNNABLE_TEST_BODY, encoding="utf-8"
    )
    (repo_root / "pyproject.toml").write_text(
        '[project]\nname = "feat-doc-coherence-gate"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )


def _seed_feature_dir(repo_root: Path, feature_id: str = _FEATURE_ID) -> Path:
    """A minimal feature-dir with NO feature-delta.md (no Slice-Plan -> no
    undelivered-slice truncation refusal -- keeps the fixture focused on the
    doc-coherence leg alone)."""
    feature_dir = repo_root / "docs" / "feature" / feature_id
    feature_dir.mkdir(parents=True)
    return feature_dir


def _stub_non_doc_coherence_legs(monkeypatch) -> None:
    """Short-circuit every OTHER leg so only the (not-yet-wired)
    doc-coherence leg can determine the cycle's outcome."""
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
    monkeypatch.setattr(
        svc,
        "_run_full_suite_leg",
        lambda *, repo_root, feature_id=None: FullSuiteLegNotApplicable(
            "stubbed: no contract suite in this hermetic fixture"
        ),
    )


def _run_cycle(repo_root: Path, feature_dir: Path, feature_id: str = _FEATURE_ID):
    return run_feature_end_cycle(
        repo_root=repo_root,
        feature_id=feature_id,
        feature_dir=feature_dir,
        reviewer_agent_id="nw-software-crafter-reviewer",
        verdict="APPROVED",
    )


def _assert_no_signed_verdict(repo_root: Path, feature_id: str) -> None:
    ledger_path = (
        repo_root / ".nwave" / "telemetry" / "atdd-pure" / f"{feature_id}.jsonl"
    )
    if ledger_path.is_file():
        text = ledger_path.read_text(encoding="utf-8")
        assert "FeatureEndReviewVerdict" not in text
        assert "EBatchRefactorCompleted" not in text


def _ledger_records(repo_root: Path, feature_id: str = _FEATURE_ID) -> list[dict]:
    ledger_path = (
        repo_root / ".nwave" / "telemetry" / "atdd-pure" / f"{feature_id}.jsonl"
    )
    if not ledger_path.is_file():
        return []
    records: list[dict] = []
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def _find_ledger_record(
    repo_root: Path, event: str, feature_id: str = _FEATURE_ID
) -> dict | None:
    matches = [
        r for r in _ledger_records(repo_root, feature_id) if r.get("event") == event
    ]
    return matches[-1] if matches else None


def test_doc_overstating_absent_code_warns_but_does_not_refuse_feature_end(
    tmp_path: Path, monkeypatch
) -> None:
    """NEGATIVE-BECOME-ADVISORY (R6): the README claims an npm script absent
    from package.json AND a file path absent from the tree -- the exact
    docs-overstate-the-code class ``verify-doc-coherence`` catches
    standalone. Per the ratified charter
    (``fix-doc-coherence-gate-warns-not-blocks``), this must WARN LOUD --
    fold into ``leg_census.warned`` and leave a ``DocCoherenceWarned``
    ledger record naming the actual violation -- but must NEVER hard-refuse
    the cycle, and must NEVER also carry a ``DocCoherenceVerified``
    (clean-pass) record for the same run.

    # covers: R5, R6
    """
    _stub_non_doc_coherence_legs(monkeypatch)
    # A WARN outcome folds into leg_census.warned, NOT leg_census.ran (only
    # DocCoherenceLegRan does) -- force full-suite to a genuine
    # FullSuiteLegRan so leg_census.ran >= 1 and the cycle does not ALSO trip
    # the unrelated zero-observed-checks charter (leg_census.ran == 0 ->
    # CycleIndeterminate, ADR-GV-002 D1/D3, pinned elsewhere). Mirrors
    # the regression AT's ``_stub_full_suite_ran``.
    monkeypatch.setattr(
        svc,
        "_run_full_suite_leg",
        lambda *, repo_root, feature_id=None: FullSuiteLegRan(0),
    )
    repo_root = tmp_path / "planted"
    repo_root.mkdir(parents=True)
    # .gitignore is the runtime-state boundary the real gate now derives
    # per-target (fix-doc-coherence-target-runtime-dir); unrelated to this
    # doc-overstatement scenario, so a plain entry suffices.
    (repo_root / ".gitignore").write_text("node_modules/\n")
    (repo_root / "README.md").write_text(_OVERSTATING_README)
    (repo_root / "src").mkdir()
    (repo_root / "src" / "index.ts").write_text("export {};\n")
    (repo_root / "package.json").write_text(json.dumps({"scripts": {"build": "tsc"}}))
    feature_dir = _seed_feature_dir(repo_root)

    result = _run_cycle(repo_root, feature_dir)

    assert isinstance(result, CycleSuccess), (
        "doc-coherence violations must WARN, not hard-refuse the feature-end "
        f"cycle (superseded contract, ratified fix-doc-coherence-gate-warns-"
        f"not-blocks charter): {result!r}"
    )
    assert result.leg_census.warned == 1, (
        "the doc-coherence WARN outcome must fold into leg_census.warned "
        f"exactly once: {result.leg_census!r}"
    )

    warned_record = _find_ledger_record(repo_root, "DocCoherenceWarned")
    assert warned_record is not None, (
        "expected a DocCoherenceWarned ledger record after a doc-coherence "
        f"violation; ledger contents: {_ledger_records(repo_root)!r}"
    )
    serialized = json.dumps(warned_record)
    assert "e2e:golden" in serialized or "reconciler.ts" in serialized, (
        "the DocCoherenceWarned record must name the actual violation (the "
        f"gate's own diagnostic), not swallow it into a bare boolean: "
        f"{warned_record!r}"
    )
    assert _find_ledger_record(repo_root, "DocCoherenceVerified") is None, (
        "a run completed WITH doc-coherence warnings must never ALSO carry a "
        f"DocCoherenceVerified (clean-pass) record: {_ledger_records(repo_root)!r}"
    )
    print(f"VERBATIM (doc-overstatement, warn-not-block): {result!r}")


def test_honest_docs_still_reach_done(tmp_path: Path, monkeypatch) -> None:
    """REGRESSION GUARD (R7): docs make no false claims -- the existing
    green path stays green once the new leg is wired."""
    _stub_non_doc_coherence_legs(monkeypatch)
    repo_root = tmp_path / "clean"
    repo_root.mkdir(parents=True)
    (repo_root / ".gitignore").write_text("node_modules/\n")
    (repo_root / "README.md").write_text(
        "# Demo\n\nRun `npm run e2e:golden` to verify.\n\n"
        "The reconciler lives in `src/reconciler.ts`.\n"
    )
    (repo_root / "src").mkdir()
    (repo_root / "src" / "index.ts").write_text("export {};\n")
    (repo_root / "src" / "reconciler.ts").write_text("export {};\n")
    (repo_root / "package.json").write_text(
        json.dumps({"scripts": {"build": "tsc", "e2e:golden": "node e2e.js"}})
    )
    feature_dir = _seed_feature_dir(repo_root)

    result = _run_cycle(repo_root, feature_dir)

    assert isinstance(result, CycleSuccess)
    print(f"VERBATIM (clean): {result!r}")


def test_no_docs_at_all_stays_leg_not_applicable_regression(
    tmp_path: Path, monkeypatch
) -> None:
    """GENERICITÀ GUARDRAIL (R8) + STALE-RECORD RECONCILIATION (2026-07-15): a
    target repo shipping NO docs at all (no README, no docs/) has nothing
    honest for the doc-coherence gate to check -- the LEG resolves
    ``DocCoherenceLegNotApplicable`` (the PRECONDITION-FIRST absence check,
    no subprocess spawned) -- never a false hard-block on a repo that ships
    no docs claims at all.

    RECONCILED to the ratified charter
    (``docs/product/expectations/certification-legs-observe-real-execution/
    feature-end-does-not-certify-done-over-zero-observed-checks.md``,
    slice-02, commit ``4c976e0a3``): a cycle where EVERY leg resolves
    NOT_APPLICABLE (``leg_census.ran == 0``) must yield
    ``CycleIndeterminate``, never ``CycleSuccess`` -- "done means observed,
    never done over zero observed checks." The PRIOR version of this test
    drove an all-NA fixture (this leg NA + full-suite/execution-reach/
    fresh-clone all NA too, ``leg_census = {ran:0, not_applicable:4}``) and
    asserted ``CycleSuccess`` -- that directly contradicts the charter
    (mirrors the execution-reach sibling's stale-record reconciliation,
    ``test_feature_end_cycle_execution_reach_gate.py``'s superseded
    ``test_no_coverage_xml_proceeds_not_applicable``, removed there since
    already pinned finer/broader elsewhere; here the LEG-level distinction
    adds genuine value not pinned elsewhere, so this test is UPDATED rather
    than removed).

    Asserts the TRUE intent at TWO altitudes (mirrors
    ``test_slice_03_execution_reach_gate_exit2_yields_indeterminate.py::
    test_genuinely_absent_coverage_xml_stays_not_applicable_regression``):

    1. LEG level (the regression guard this test exists to preserve): call
       the REAL, unstubbed ``_run_doc_coherence_gate`` directly on the
       no-docs-at-all fixture and assert it resolves
       ``DocCoherenceLegNotApplicable`` -- never ``*Indeterminate``.
    2. CYCLE level (now legitimate, not a charter violation): the fixture
       ALSO seeds a real, marked, genuinely-running full-suite leg
       (``_seed_marked_runnable_suite``), so ``leg_census.ran >= 1`` and the
       cycle rightfully reaches ``CycleSuccess`` -- this is NOT "Complete
       over all-NA" (that stays ``CycleIndeterminate``, pinned generically
       by slice-02's census-guard ATs,
       ``test_slice_02_full_suite_leg_marker_miss_yields_indeterminate.py``);
       it is "Complete because a real leg ran, AND the doc-coherence leg
       specifically stayed NA rather than flipping to Indeterminate on
       genuine absence."
    """
    repo_root = tmp_path / "no-docs"
    repo_root.mkdir(parents=True)
    (repo_root / "src").mkdir()
    (repo_root / "src" / "index.ts").write_text("export {};\n")
    # Deliberately NO README* and NO docs/ directory anywhere under repo_root.
    _seed_marked_runnable_suite(repo_root)  # census.ran >= 1 (full-suite REAL)
    feature_dir = _seed_feature_dir(repo_root)

    # Sibling legs OTHER than doc-coherence and full-suite are still
    # short-circuited; full-suite is intentionally LEFT REAL (not stubbed)
    # -- it is the genuinely-running leg that makes census.ran >= 1
    # legitimate.
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

    leg_outcome = svc._run_doc_coherence_gate(
        ledger=AtCompletionLedger(_FEATURE_ID, repo_root),
        repo_root=repo_root,
        feature_id=_FEATURE_ID,
    )
    assert isinstance(leg_outcome, svc.DocCoherenceLegNotApplicable), (
        "a target repo shipping no docs at all (genuine ontological absence, "
        "precondition-first, no subprocess spawned) must resolve the "
        "DOC-COHERENCE LEG to NotApplicable -- never Indeterminate: "
        f"{leg_outcome!r}"
    )

    result = _run_cycle(repo_root, feature_dir)

    assert isinstance(result, CycleSuccess), (
        "the fixture ALSO seeds a real, marked, genuinely-running full-suite "
        "leg (census.ran >= 1) so the cycle legitimately reaches "
        "CycleSuccess -- this is NOT 'Complete over all-NA' (that stays "
        f"CycleIndeterminate): {result!r}"
    )
    print(f"VERBATIM (no-docs-NA): {result!r}")
