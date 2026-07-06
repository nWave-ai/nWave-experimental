# @feature-wire-p0-gates-at-feature-end
# @slice-01
"""Feature-end fresh-clone gate: wires ``des verify-fresh-clone`` as a new leg.

wire-p0-gates-at-feature-end slice-01. ``run_feature_end_cycle`` must invoke the
REAL ``des verify-fresh-clone`` gate (evolution-plan P0.1) and derive its
verdict from the REAL exit code -- a feature whose committed tree fails a
fresh-clone build (works only in the warm working tree that built it) must be
refused (``CycleRefusal``), never silently signed done.

Unit-level, hermetic: the upstream/sibling legs (walking-skeleton, env-e2e,
coverage-map, full-suite) are stubbed to PASS/NOT_APPLICABLE (mirrors
``test_feature_end_cycle_examine_gate.py``'s ``_stub_upstream_legs`` pattern)
so the test isolates the NEW fresh-clone leg. The fresh-clone gate itself is
NEVER stubbed: ``repo_root`` is a REAL git repository carrying a REAL
``.nwave/demo-recipe.json`` (same fixture shape as
``tests/des/unit/cli/test_verify_fresh_clone.py``), so once wired the leg's
real subprocess dispatch (``des verify-fresh-clone``) genuinely observes the
planted defect (an uncommitted dependency the recipe's build step needs) --
the anti-theater invariant this whole cycle is built on.

Active-RED today (impl missing): ``run_feature_end_cycle`` does not yet call
``verify-fresh-clone`` at all, so every fixture below reaches
``CycleSuccess`` regardless of the planted defect --
``test_fresh_clone_broken_build_refuses_feature_end`` fails with a genuine
``AssertionError`` (expected ``CycleRefusal``, got ``CycleSuccess``), not a
setup/import error. The other two tests are REGRESSION/GENERICITÀ guards
(already green -- they pin the unchanged/NA behaviour the new leg must
preserve once wired).

Requirement coverage markers (R1/R2/R7/R8) are placed per-TEST-FUNCTION below
(the ``verify-spec-coverage`` gate's marker scan is function-scoped -- a
module-level docstring marker is invisible to it; see DISTILL FRICTIONS).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from des.application import feature_end_cycle_service as svc
from des.application.feature_end_cycle_service import (
    CycleRefusal,
    CycleSuccess,
    FullSuiteLegNotApplicable,
    run_feature_end_cycle,
)


_FEATURE_ID = "feat-fresh-clone-gate"
_RECIPE = '{"steps": [{"name": "build", "cmd": ["python3", "main.py"]}]}\n'


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")


def _seed_feature_dir(repo_root: Path, feature_id: str = _FEATURE_ID) -> Path:
    """A minimal feature-dir with NO feature-delta.md (no Slice-Plan -> no
    undelivered-slice truncation refusal -- keeps the fixture focused on the
    fresh-clone leg alone)."""
    feature_dir = repo_root / "docs" / "feature" / feature_id
    feature_dir.mkdir(parents=True)
    return feature_dir


def _stub_non_fresh_clone_legs(monkeypatch) -> None:
    """Short-circuit every OTHER leg so only the (not-yet-wired) fresh-clone
    leg can determine the cycle's outcome."""
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


def test_fresh_clone_broken_build_refuses_feature_end(
    tmp_path: Path, monkeypatch
) -> None:
    """NEGATIVE (R2): committed tree depends on an UNTRACKED file -- the exact
    works-only-on-my-machine class ``verify-fresh-clone`` catches standalone.
    Once wired, ``run_feature_end_cycle`` must refuse and emit no signed
    verdict.

    # covers: R1, R2
    """
    _stub_non_fresh_clone_legs(monkeypatch)
    repo_root = tmp_path / "planted"
    _init_repo(repo_root)
    (repo_root / "main.py").write_text("import helper\nprint(helper.GREETING)\n")
    (repo_root / "helper.py").write_text('GREETING = "ok"\n')
    (repo_root / ".nwave").mkdir()
    (repo_root / ".nwave" / "demo-recipe.json").write_text(_RECIPE)
    _git(repo_root, "add", "main.py", ".nwave/demo-recipe.json")  # NOT helper.py
    _git(repo_root, "commit", "-qm", "planted: depends on untracked helper")
    feature_dir = _seed_feature_dir(repo_root)

    result = _run_cycle(repo_root, feature_dir)

    assert isinstance(result, CycleRefusal)
    assert "fresh-clone" in result.error
    assert "build" in result.error  # names the failing recipe step
    _assert_no_signed_verdict(repo_root, _FEATURE_ID)
    print(f"VERBATIM (fresh-clone-broken): {result!r}")


def test_clean_committed_tree_still_reaches_done(tmp_path: Path, monkeypatch) -> None:
    """REGRESSION GUARD (R7): a fully-committed tree (no fresh-clone defect)
    must still reach a signed ``CycleSuccess`` -- the existing green path
    stays green once the new leg is wired."""
    _stub_non_fresh_clone_legs(monkeypatch)
    repo_root = tmp_path / "clean"
    _init_repo(repo_root)
    (repo_root / "main.py").write_text("import helper\nprint(helper.GREETING)\n")
    (repo_root / "helper.py").write_text('GREETING = "ok"\n')
    (repo_root / ".nwave").mkdir()
    (repo_root / ".nwave" / "demo-recipe.json").write_text(_RECIPE)
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", "complete committed project")
    feature_dir = _seed_feature_dir(repo_root)

    result = _run_cycle(repo_root, feature_dir)

    assert isinstance(result, CycleSuccess)
    print(f"VERBATIM (clean): {result!r}")


def test_no_demo_recipe_proceeds_not_applicable(tmp_path: Path, monkeypatch) -> None:
    """GENERICITÀ GUARDRAIL (R8): a target repo that never declared
    ``.nwave/demo-recipe.json`` has nothing honest for the fresh-clone gate to
    execute -- the gate's OWN contract degrades to INDETERMINATE (exit 2) on
    this precondition. Per the feature-delta's L-4 default (a candidate NA
    condition named 1:1 with the gate's own indeterminate trigger), the cycle
    must treat this as NOT_APPLICABLE and PROCEED -- never a false
    hard-block on a repo that was never asked to have a demo recipe."""
    _stub_non_fresh_clone_legs(monkeypatch)
    repo_root = tmp_path / "no-recipe"
    _init_repo(repo_root)
    (repo_root / "f.txt").write_text("x")
    _git(repo_root, "add", "f.txt")
    _git(repo_root, "commit", "-qm", "no demo recipe declared")
    feature_dir = _seed_feature_dir(repo_root)

    result = _run_cycle(repo_root, feature_dir)

    assert isinstance(result, CycleSuccess)
    print(f"VERBATIM (no-recipe-NA): {result!r}")
