# @feature-wire-p0-gates-at-feature-end
# @slice-02
"""Feature-end execution-reach gate: wires ``des verify-execution-reach``.

wire-p0-gates-at-feature-end slice-02. ``run_feature_end_cycle`` must invoke
the REAL ``des verify-execution-reach`` gate (evolution-plan P0.4) and derive
its verdict from the REAL exit code -- a feature shipping a production file
with ZERO recorded executions across its verification (a never-run scaffold)
must be refused (``CycleRefusal``), never silently signed done.

Unit-level, hermetic: sibling legs (walking-skeleton, env-e2e, coverage-map,
full-suite) are stubbed to PASS/NOT_APPLICABLE (mirrors
``test_feature_end_cycle_examine_gate.py``'s ``_stub_upstream_legs`` pattern)
so the test isolates the NEW execution-reach leg. The execution-reach gate
itself is NEVER stubbed: the fixture plants a REAL Cobertura coverage XML
(same shape as ``tests/des/unit/cli/test_verify_execution_reach.py``) with a
zero-hit production file, so once wired the leg's real subprocess dispatch
genuinely observes the planted defect.

Active-RED today (impl missing): ``run_feature_end_cycle`` does not yet call
``verify-execution-reach`` at all, so every fixture below reaches
``CycleSuccess`` regardless of the planted defect --
``test_never_executed_file_refuses_feature_end`` fails with a genuine
``AssertionError`` (expected ``CycleRefusal``, got ``CycleSuccess``), not a
setup/import error. The other two tests are REGRESSION/GENERICITÀ guards
(already green -- they pin the unchanged/NA behaviour the new leg must
preserve once wired).

Requirement coverage markers (R3/R4/R7/R8) are placed per-TEST-FUNCTION below
(the ``verify-spec-coverage`` gate's marker scan is function-scoped -- a
module-level docstring marker is invisible to it; see DISTILL FRICTIONS).
"""

from __future__ import annotations

from pathlib import Path

from des.application import feature_end_cycle_service as svc
from des.application.feature_end_cycle_service import (
    CycleRefusal,
    CycleSuccess,
    FullSuiteLegNotApplicable,
    run_feature_end_cycle,
)


_FEATURE_ID = "feat-execution-reach-gate"


def _cobertura(src_abs: Path, classes: str) -> str:
    return (
        '<?xml version="1.0" ?>\n'
        '<coverage version="7.0">\n'
        f"  <sources><source>{src_abs}</source></sources>\n"
        '  <packages><package name="."><classes>\n'
        f"{classes}"
        "  </classes></package></packages>\n"
        "</coverage>\n"
    )


def _cls(filename: str, hits: int, n_lines: int = 2) -> str:
    lines = "".join(
        f'      <line number="{i + 1}" hits="{hits}"/>\n' for i in range(n_lines)
    )
    return (
        f'    <class name="{filename}" filename="{filename}">'
        f"<methods/><lines>\n{lines}    </lines></class>\n"
    )


def _seed_feature_dir(repo_root: Path, feature_id: str = _FEATURE_ID) -> Path:
    """A minimal feature-dir with NO feature-delta.md (no Slice-Plan -> no
    undelivered-slice truncation refusal -- keeps the fixture focused on the
    execution-reach leg alone)."""
    feature_dir = repo_root / "docs" / "feature" / feature_id
    feature_dir.mkdir(parents=True)
    return feature_dir


def _stub_non_execution_reach_legs(monkeypatch) -> None:
    """Short-circuit every OTHER leg so only the (not-yet-wired)
    execution-reach leg can determine the cycle's outcome."""
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


def test_never_executed_file_refuses_feature_end(tmp_path: Path, monkeypatch) -> None:
    """NEGATIVE (R4): a shipped production file (``dead_scaffold.py``) shows
    ZERO hits in the feature's own coverage run -- the exact never-run
    scaffold class ``verify-execution-reach`` catches standalone. Once wired,
    ``run_feature_end_cycle`` must refuse and emit no signed verdict.

    # covers: R3, R4
    """
    _stub_non_execution_reach_legs(monkeypatch)
    repo_root = tmp_path / "planted"
    src = repo_root / "src"
    src.mkdir(parents=True)
    (src / "used.py").write_text("def greet():\n    return 'ok'\n")
    (src / "dead_scaffold.py").write_text(
        "def reconcile():\n    raise RuntimeError('x')\n"
    )
    xml = repo_root / "coverage.xml"
    xml.write_text(
        _cobertura(src, _cls("used.py", hits=3) + _cls("dead_scaffold.py", hits=0))
    )
    feature_dir = _seed_feature_dir(repo_root)

    result = _run_cycle(repo_root, feature_dir)

    assert isinstance(result, CycleRefusal)
    assert "execution-reach" in result.error
    assert "dead_scaffold.py" in result.error  # names the unreached file
    _assert_no_signed_verdict(repo_root, _FEATURE_ID)
    print(f"VERBATIM (never-executed): {result!r}")


def test_fully_reached_tree_still_reaches_done(tmp_path: Path, monkeypatch) -> None:
    """REGRESSION GUARD (R7): every production file has >0 hits -- the
    existing green path stays green once the new leg is wired."""
    _stub_non_execution_reach_legs(monkeypatch)
    repo_root = tmp_path / "clean"
    src = repo_root / "src"
    src.mkdir(parents=True)
    (src / "used.py").write_text("def greet():\n    return 'ok'\n")
    (src / "reached.py").write_text("def run():\n    return 1\n")
    xml = repo_root / "coverage.xml"
    xml.write_text(
        _cobertura(src, _cls("used.py", hits=3) + _cls("reached.py", hits=1))
    )
    feature_dir = _seed_feature_dir(repo_root)

    result = _run_cycle(repo_root, feature_dir)

    assert isinstance(result, CycleSuccess)
    print(f"VERBATIM (clean): {result!r}")


def test_no_coverage_xml_proceeds_not_applicable(tmp_path: Path, monkeypatch) -> None:
    """GENERICITÀ GUARDRAIL (R8): a target repo that never produced a
    Cobertura coverage report (opted out of coverage instrumentation) has
    nothing honest for the execution-reach gate to judge -- the gate's OWN
    contract degrades to INDETERMINATE (exit 2) on this precondition. Per
    the feature-delta's L-4 default (a candidate NA condition named 1:1 with
    the gate's own indeterminate trigger), the cycle must treat this as
    NOT_APPLICABLE and PROCEED -- never a false hard-block on a repo that
    never opted into coverage instrumentation."""
    _stub_non_execution_reach_legs(monkeypatch)
    repo_root = tmp_path / "no-coverage"
    src = repo_root / "src"
    src.mkdir(parents=True)
    (src / "used.py").write_text("def greet():\n    return 'ok'\n")
    # Deliberately NO coverage.xml anywhere under repo_root.
    feature_dir = _seed_feature_dir(repo_root)

    result = _run_cycle(repo_root, feature_dir)

    assert isinstance(result, CycleSuccess)
    print(f"VERBATIM (no-coverage-NA): {result!r}")


def test_src_dir_missing_proceeds_not_applicable(tmp_path: Path, monkeypatch) -> None:
    """REGRESSION-CLASS GUARDRAIL (R8, sibling-gate parity, deep-review D2): a
    target repo whose production code lives under a non-conventional root
    (e.g. ``lib/`` instead of the hardcoded ``src/``) HAS a valid Cobertura
    ``coverage.xml`` -- the precondition-check (:730 ``coverage_xml_path.
    is_file()``) passes and the gate is genuinely dispatched -- but the REAL
    ``des verify-execution-reach`` gate exits 2 (``ExecutionReachIndeterminate``:
    "src-dir src is not a directory under <repo>", ``verify_execution_reach.py``
    :189-194) because it cannot find the hardcoded ``src/`` root
    (``_EXECUTION_REACH_SRC_DIR = "src"``, :698).

    Per the sibling legs' contract -- ``_run_doc_coherence_gate`` (:675) and
    ``_run_fresh_clone_gate`` (:793) both special-case ``returncode == 2`` into
    their own ``...LegNotApplicable`` so the cycle PROCEEDS -- an INDETERMINATE
    gate verdict must NEVER become a false hard-block (R8 genericita
    guardrail): a repo the gate cannot judge is NOT_APPLICABLE, never refused.

    ACTIVE-RED today: ``_run_execution_reach_gate`` (:749) checks only
    ``completed.returncode != 0`` with no ``== 2`` branch, so this genuinely
    reaches ``CycleRefusal`` today -- a genuine ``AssertionError`` (expected
    ``CycleSuccess``, got ``CycleRefusal``), not a setup/import error.

    # covers: R8
    """
    _stub_non_execution_reach_legs(monkeypatch)
    repo_root = tmp_path / "nonstandard-layout"
    lib = repo_root / "lib"
    lib.mkdir(parents=True)
    (lib / "used.py").write_text("def greet():\n    return 'ok'\n")
    # Deliberately NO `src/` directory anywhere under repo_root -- the gate's
    # hardcoded --src-dir "src" cannot resolve, forcing its own exit 2.
    xml = repo_root / "coverage.xml"
    xml.write_text(_cobertura(lib, _cls("used.py", hits=3)))
    feature_dir = _seed_feature_dir(repo_root)

    result = _run_cycle(repo_root, feature_dir)

    assert isinstance(result, CycleSuccess)
    print(f"VERBATIM (src-dir-missing-NA): {result!r}")
