# @feature-fix-doc-coherence-gate-warns-not-blocks
"""Doc-coherence findings warn loud, never block feature-end (regression AT).

Charter: ``docs/product/expectations/fix-doc-coherence-gate-warns-not-blocks/
doc-coherence-findings-warn-loud-never-block-feature-end.md`` (human directive,
verbatim). Ratified behavior change to ``run_feature_end_cycle``'s
``_run_doc_coherence_gate`` leg (``src/des/application/feature_end_cycle_service.py``
~:1032-1089):

TODAY: when the REAL ``des verify-doc-coherence`` gate exits 1 (>=1 doc claim is
false of the actual tree), ``_run_doc_coherence_gate`` returns
``_gate_failure_refusal(...)`` -> a ``CycleRefusal`` -> ``run_feature_end_cycle``
(~:511-512) HARD-REFUSES the WHOLE feature-end cycle. A team with one honest-but-
stale doc reference is stuck: certification cannot complete until every doc claim
is hand-fixed.

THE FIX (not implemented here -- this AT only specifies + pins it): on exit 1 the
doc-coherence leg must (a) surface the violating gate's own diagnostic LOUDLY --
persisted where a human reads it, never swallowed into a bare boolean; (b) return a
NEW non-blocking leg outcome (``DocCoherenceLegWarned``) that folds into
``LegCensus`` (a new ``warned`` counter, parallel to ``ran`` /``not_applicable`` /
``indeterminate``); (c) record a NEW ``DocCoherenceWarned`` ledger event -- DISTINCT
from ``DocCoherenceVerified`` (the completion record must never read as "doc-
coherence passed clean" when it did not); (d) let the cycle PROCEED to
``CycleSuccess``. Exit 2 (INDETERMINATE, DDD-CERT-4) and the precondition-first
NotApplicable path (D-2, no docs at all) are UNCHANGED -- only the exit-1 HARD
REFUSAL becomes advisory. Every OTHER feature-end leg keeps its full teeth (no
scope creep, charter negative oracle #4).

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process default): the
REAL ``run_feature_end_cycle`` composition-root entry, in-process, with sibling
legs stubbed PASS/NA (mirrors ``test_feature_end_cycle_doc_coherence_gate.py``'s
``_stub_upstream_legs`` pattern -- same established harness, not invented here).
The doc-coherence leg itself is NEVER stubbed: each fixture plants a REAL
README/.gitignore shape and the leg's real subprocess dispatch (``des
verify-doc-coherence``) genuinely observes it.

Active-RED today (impl missing): ``_run_doc_coherence_gate`` still returns
``_gate_failure_refusal(...)`` on exit 1, so ``test_doc_coherence_violations_
no_longer_refuse_feature_end`` fails with a genuine ``AssertionError`` (expected
``CycleSuccess``, got ``CycleRefusal``) -- not a setup/import/collection error.
``test_doc_coherence_warning_is_recorded_not_swallowed`` and
``test_doc_coherence_warned_record_never_reads_as_verified_clean`` fail the same
way (no ``DocCoherenceWarned`` ledger record exists yet). The three
``*_regression`` / ``*_scope_creep_guard`` tests are PIN guards -- already GREEN
today, they pin the UNCHANGED behavior the fix must preserve verbatim.
"""

from __future__ import annotations

import json
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.application import feature_end_cycle_service as svc
from des.application.feature_end_cycle_service import (
    CycleIndeterminate,
    CycleRefusal,
    CycleSuccess,
    FullSuiteLegNotApplicable,
    FullSuiteLegRan,
    run_feature_end_cycle,
)


_FEATURE_ID = "feat-doc-coherence-warns-not-blocks"

# Same overstating-doc shape as test_feature_end_cycle_doc_coherence_gate.py's
# _OVERSTATING_README -- the exact docs-overstate-the-code class
# verify-doc-coherence catches standalone: an npm script and a file path that
# do not exist in the committed tree.
_OVERSTATING_README = (
    "# Demo\n\n"
    "Run `npm run e2e:golden` to verify.\n\n"
    "The reconciler lives in `src/reconciler.ts`.\n"
)

# A README with a doc claim (so `_repo_has_doc_claims` is True and the gate is
# genuinely dispatched) but NO `.gitignore` at all -- the real gate's own
# `_resolve_runtime_state_top_level` returns None on an absent/unreadable
# .gitignore, so it exits 2 (INDETERMINATE), deterministically and without any
# chmod/symlink trickery.
_HONEST_README_NO_GITIGNORE = "# Demo\n\nThis project has a build step.\n"

_MARKED_RUNNABLE_PASSING_TEST_BODY = (
    "import pytest\n\n\n@pytest.mark.unit\ndef test_widget_behaves():\n"
    "    assert 1 + 1 == 2\n"
)
_MARKED_RUNNABLE_FAILING_TEST_BODY = (
    "import pytest\n\n\n@pytest.mark.unit\ndef test_widget_is_broken():\n"
    "    assert False, 'seeded regression -- an unrelated gate must still refuse'\n"
)


def _seed_feature_dir(repo_root: Path, feature_id: str = _FEATURE_ID) -> Path:
    """A minimal feature-dir with NO feature-delta.md (no Slice-Plan -> no
    undelivered-slice truncation refusal), mirroring the sibling doc-coherence
    gate test's fixture builder."""
    feature_dir = repo_root / "docs" / "feature" / feature_id
    feature_dir.mkdir(parents=True)
    return feature_dir


def _seed_pytest_project(repo_root: Path, test_body: str) -> None:
    """A real, marked (``@pytest.mark.unit``), runnable pytest suite at the
    conventional ``tests/`` root plus a top-level ``pyproject.toml`` manifest --
    mirrors the sibling doc-coherence gate test's ``_seed_marked_runnable_suite``.
    """
    tests_dir = repo_root / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_widget.py").write_text(test_body, encoding="utf-8")
    (repo_root / "pyproject.toml").write_text(
        f'[project]\nname = "{_FEATURE_ID}"\nversion = "0.1.0"\n', encoding="utf-8"
    )


def _stub_non_doc_coherence_legs(monkeypatch) -> None:
    """Short-circuit walking-skeleton / environmental-e2e / coverage-map so
    only the doc-coherence leg (plus full-suite, controlled per-test) can
    determine the cycle's outcome. Byte-identical to the established
    ``test_feature_end_cycle_doc_coherence_gate.py::_stub_non_doc_coherence_legs``
    pattern (same harness, not reinvented)."""
    monkeypatch.setattr(
        svc, "_run_walking_skeleton_gate", lambda *, repo_root, feature_dir: repo_root
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


def _stub_full_suite_ran(monkeypatch) -> None:
    """Force the full-suite leg to a genuine ``FullSuiteLegRan`` so
    ``leg_census.ran >= 1`` REGARDLESS of how the doc-coherence WARN outcome
    folds into the census -- isolates these tests from the unrelated
    ``leg_census.ran == 0`` -> ``CycleIndeterminate`` charter
    (ADR-GV-002 D1/D3, already pinned elsewhere)."""
    monkeypatch.setattr(
        svc,
        "_run_full_suite_leg",
        lambda *, repo_root: FullSuiteLegRan(pytest_exit_code=0),
    )


def _stub_full_suite_not_applicable(monkeypatch) -> None:
    """Force the full-suite leg NA -- used by the exit-2 pin, where the
    cycle-level outcome (``CycleIndeterminate``) is asserted directly and does
    not depend on ``leg_census.ran``."""
    monkeypatch.setattr(
        svc,
        "_run_full_suite_leg",
        lambda *, repo_root: FullSuiteLegNotApplicable(
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


def _ledger_path(repo_root: Path, feature_id: str = _FEATURE_ID) -> Path:
    return repo_root / ".nwave" / "telemetry" / "atdd-pure" / f"{feature_id}.jsonl"


def _ledger_records(repo_root: Path, feature_id: str = _FEATURE_ID) -> list[dict]:
    ledger_path = _ledger_path(repo_root, feature_id)
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


def _build_overstating_repo(tmp_path: Path, name: str) -> tuple[Path, Path]:
    """A repo whose README overstates the tree (npm script + file path absent)
    -- the fixture shape shared by every "core RED" scenario below."""
    repo_root = tmp_path / name
    repo_root.mkdir(parents=True)
    (repo_root / ".gitignore").write_text("node_modules/\n")
    (repo_root / "README.md").write_text(_OVERSTATING_README)
    (repo_root / "src").mkdir()
    (repo_root / "src" / "index.ts").write_text("export {};\n")
    (repo_root / "package.json").write_text(json.dumps({"scripts": {"build": "tsc"}}))
    feature_dir = _seed_feature_dir(repo_root)
    return repo_root, feature_dir


def test_doc_coherence_violations_no_longer_refuse_feature_end(
    tmp_path: Path, monkeypatch
) -> None:
    """CORE (RED today): a feature-end cycle whose doc-coherence gate reports
    real violations (exit 1) must PROCEED to ``CycleSuccess`` -- never a
    doc-coherence-caused ``CycleRefusal`` -- and the outcome must fold the
    new WARN leg into ``leg_census.warned`` (parallel to ``ran`` /
    ``not_applicable`` / ``indeterminate``)."""
    _stub_non_doc_coherence_legs(monkeypatch)
    _stub_full_suite_ran(monkeypatch)
    repo_root, feature_dir = _build_overstating_repo(tmp_path, "planted")

    result = _run_cycle(repo_root, feature_dir)

    assert isinstance(result, CycleSuccess), (
        "doc-coherence violations must WARN, not hard-refuse the feature-end "
        f"cycle (anti-blocking, per the ratified charter): {result!r}"
    )
    assert result.leg_census.warned == 1, (
        "the doc-coherence WARN outcome must fold into leg_census.warned "
        f"exactly once: {result.leg_census!r}"
    )


def test_doc_coherence_warning_is_recorded_not_swallowed(
    tmp_path: Path, monkeypatch
) -> None:
    """LOUD, NOT SILENT (negative): the surfaced warning must carry the
    violation's own detail (which claim, e.g. the npm script or file path
    name) -- never a bare "warned" flag with the disclosure dropped. Mirrors
    charter negative oracle #1 (findings absent/buried/reduced to a vague
    line counts as FAIL)."""
    _stub_non_doc_coherence_legs(monkeypatch)
    _stub_full_suite_ran(monkeypatch)
    repo_root, feature_dir = _build_overstating_repo(tmp_path, "loud")

    _run_cycle(repo_root, feature_dir)

    warned_record = _find_ledger_record(repo_root, "DocCoherenceWarned")
    assert warned_record is not None, (
        "expected a DocCoherenceWarned ledger record after a doc-coherence "
        f"violation; ledger contents: {_ledger_records(repo_root)!r}"
    )
    serialized = json.dumps(warned_record)
    assert "e2e:golden" in serialized or "reconciler.ts" in serialized, (
        "the DocCoherenceWarned record must name the actual violation (the "
        "gate's own diagnostic), not swallow it into a bare boolean: "
        f"{warned_record!r}"
    )


def test_doc_coherence_warned_record_never_reads_as_verified_clean(
    tmp_path: Path, monkeypatch
) -> None:
    """HONEST COMPLETION (negative): the ledger must record doc-coherence as
    WARNED, NOT as ``DocCoherenceVerified`` -- a clean-looking pass badge next
    to actual disagreements is charter negative oracle #2 (FAIL)."""
    _stub_non_doc_coherence_legs(monkeypatch)
    _stub_full_suite_ran(monkeypatch)
    repo_root, feature_dir = _build_overstating_repo(tmp_path, "honest-completion")

    _run_cycle(repo_root, feature_dir)

    assert _find_ledger_record(repo_root, "DocCoherenceWarned") is not None, (
        "a warned completion must leave a DocCoherenceWarned record: "
        f"{_ledger_records(repo_root)!r}"
    )
    assert _find_ledger_record(repo_root, "DocCoherenceVerified") is None, (
        "a feature-end completed WITH doc-coherence warnings must never ALSO "
        "carry a DocCoherenceVerified (clean-pass) record for the same run: "
        f"{_ledger_records(repo_root)!r}"
    )


def test_doc_coherence_exit2_indeterminate_still_escalates_regression(
    tmp_path: Path, monkeypatch
) -> None:
    """PIN (already GREEN, unchanged): the gate's OWN exit-2 INDETERMINATE
    (an epistemic "I could not judge" -- here, an undeterminable runtime-state
    boundary: docs exist but no .gitignore) must still escalate to
    ``CycleIndeterminate`` -- it must NEVER be folded into the new advisory
    WARN outcome (DDD-CERT-4: epistemic gap, not a resolvable finding)."""
    _stub_non_doc_coherence_legs(monkeypatch)
    _stub_full_suite_not_applicable(monkeypatch)
    repo_root = tmp_path / "gitignore-missing"
    repo_root.mkdir(parents=True)
    (repo_root / "README.md").write_text(_HONEST_README_NO_GITIGNORE)
    feature_dir = _seed_feature_dir(repo_root)

    result = _run_cycle(repo_root, feature_dir)

    assert isinstance(result, CycleIndeterminate), (
        "an undeterminable doc-coherence runtime-state boundary (no "
        ".gitignore) must stay CycleIndeterminate, never silently recycled "
        f"into the new advisory WARN path: {result!r}"
    )
    assert "doc-coherence" in result.reason


def test_doc_coherence_no_docs_at_all_stays_not_applicable_regression(
    tmp_path: Path,
) -> None:
    """PIN (already GREEN, unchanged): a target repo shipping NO docs at all
    (no README, no docs/) has nothing honest to check -- the leg must stay
    ``DocCoherenceLegNotApplicable`` (precondition-first, no subprocess
    spawned) -- never escalated into the new WARN outcome. Leg-level, mirrors
    ``test_feature_end_cycle_doc_coherence_gate.py::
    test_no_docs_at_all_stays_leg_not_applicable_regression`` (that file also
    pins the cycle-level all-NA outcome; this file adds only the leg-level
    guard local to the doc-coherence-warns-not-blocks change)."""
    repo_root = tmp_path / "no-docs"
    repo_root.mkdir(parents=True)
    (repo_root / "src").mkdir()
    (repo_root / "src" / "index.ts").write_text("export {};\n")

    leg_outcome = svc._run_doc_coherence_gate(
        ledger=AtCompletionLedger(_FEATURE_ID, repo_root),
        repo_root=repo_root,
        feature_id=_FEATURE_ID,
    )

    assert isinstance(leg_outcome, svc.DocCoherenceLegNotApplicable), (
        "a repo with zero docs claims must resolve NotApplicable (genuine "
        f"ontological absence), never the new advisory WARN outcome: "
        f"{leg_outcome!r}"
    )


def test_other_leg_refusal_still_hard_refuses_cycle_scope_creep_guard(
    tmp_path: Path, monkeypatch
) -> None:
    """PIN (already GREEN, unchanged) -- SCOPE CREEP GUARD: a genuinely
    different, unrelated feature-end gate (here: the full-suite leg, on a
    seeded FAILING marked test) must still hard-refuse the cycle exactly as
    before. Only the doc-coherence leg became advisory; every other leg keeps
    its full teeth (charter negative oracle #4)."""
    _stub_non_doc_coherence_legs(monkeypatch)
    repo_root = tmp_path / "other-leg-fails"
    repo_root.mkdir(parents=True)
    _seed_pytest_project(repo_root, _MARKED_RUNNABLE_FAILING_TEST_BODY)
    feature_dir = _seed_feature_dir(repo_root)

    result = _run_cycle(repo_root, feature_dir)

    assert isinstance(result, CycleRefusal), (
        "a genuinely failing, UNRELATED gate (full-suite) must still "
        f"hard-refuse the cycle -- doc-coherence going advisory must not "
        f"leak into any other leg: {result!r}"
    )
    assert "full-suite" in result.error
