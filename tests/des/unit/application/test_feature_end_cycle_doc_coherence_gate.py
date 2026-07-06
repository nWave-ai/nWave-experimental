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
``CycleSuccess`` regardless of the planted defect --
``test_doc_overstating_absent_code_refuses_feature_end`` fails with a
genuine ``AssertionError`` (expected ``CycleRefusal``, got ``CycleSuccess``),
not a setup/import error. The other two tests are REGRESSION/GENERICITÀ
guards (already green -- they pin the unchanged/NA behaviour the new leg
must preserve once wired).

Requirement coverage markers (R5/R6/R7/R8) are placed per-TEST-FUNCTION below
(the ``verify-spec-coverage`` gate's marker scan is function-scoped -- a
module-level docstring marker is invisible to it; see DISTILL FRICTIONS).
"""

from __future__ import annotations

import json
from pathlib import Path

from des.application import feature_end_cycle_service as svc
from des.application.feature_end_cycle_service import (
    CycleRefusal,
    CycleSuccess,
    FullSuiteLegNotApplicable,
    run_feature_end_cycle,
)


_FEATURE_ID = "feat-doc-coherence-gate"
_OVERSTATING_README = (
    "# Demo\n\n"
    "Run `npm run e2e:golden` to verify.\n\n"
    "The reconciler lives in `src/reconciler.ts`.\n"
)
_HONEST_README = "# Demo\n\nThis project has no scripted demo yet.\n"


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


def _assert_no_signed_verdict(repo_root: Path, feature_id: str) -> None:
    ledger_path = (
        repo_root / ".nwave" / "telemetry" / "atdd-pure" / f"{feature_id}.jsonl"
    )
    if ledger_path.is_file():
        text = ledger_path.read_text(encoding="utf-8")
        assert "FeatureEndReviewVerdict" not in text
        assert "EBatchRefactorCompleted" not in text


def test_doc_overstating_absent_code_refuses_feature_end(
    tmp_path: Path, monkeypatch
) -> None:
    """NEGATIVE (R6): the README claims an npm script absent from
    package.json AND a file path absent from the tree -- the exact
    docs-overstate-the-code class ``verify-doc-coherence`` catches
    standalone. Once wired, ``run_feature_end_cycle`` must refuse and emit
    no signed verdict.

    # covers: R5, R6
    """
    _stub_non_doc_coherence_legs(monkeypatch)
    repo_root = tmp_path / "planted"
    repo_root.mkdir(parents=True)
    (repo_root / "README.md").write_text(_OVERSTATING_README)
    (repo_root / "src").mkdir()
    (repo_root / "src" / "index.ts").write_text("export {};\n")
    (repo_root / "package.json").write_text(json.dumps({"scripts": {"build": "tsc"}}))
    feature_dir = _seed_feature_dir(repo_root)

    result = _run_cycle(repo_root, feature_dir)

    assert isinstance(result, CycleRefusal)
    assert "doc-coherence" in result.error
    assert "e2e:golden" in result.error or "reconciler.ts" in result.error
    _assert_no_signed_verdict(repo_root, _FEATURE_ID)
    print(f"VERBATIM (doc-overstatement): {result!r}")


def test_honest_docs_still_reach_done(tmp_path: Path, monkeypatch) -> None:
    """REGRESSION GUARD (R7): docs make no false claims -- the existing
    green path stays green once the new leg is wired."""
    _stub_non_doc_coherence_legs(monkeypatch)
    repo_root = tmp_path / "clean"
    repo_root.mkdir(parents=True)
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


def test_no_docs_at_all_proceeds_not_applicable(tmp_path: Path, monkeypatch) -> None:
    """GENERICITÀ GUARDRAIL (R8): a target repo shipping NO docs at all (no
    README, no docs/) has nothing honest for the doc-coherence gate to check
    -- the gate's OWN contract degrades to INDETERMINATE (exit 2) on this
    precondition. Per the feature-delta's L-4 default (a candidate NA
    condition named 1:1 with the gate's own indeterminate trigger), the
    cycle must treat this as NOT_APPLICABLE and PROCEED -- never a false
    hard-block on a repo that ships no docs claims at all."""
    _stub_non_doc_coherence_legs(monkeypatch)
    repo_root = tmp_path / "no-docs"
    repo_root.mkdir(parents=True)
    (repo_root / "src").mkdir()
    (repo_root / "src" / "index.ts").write_text("export {};\n")
    # Deliberately NO README* and NO docs/ directory anywhere under repo_root.
    feature_dir = _seed_feature_dir(repo_root)

    result = _run_cycle(repo_root, feature_dir)

    assert isinstance(result, CycleSuccess)
    print(f"VERBATIM (no-docs-NA): {result!r}")
