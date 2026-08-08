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

SHIPPED (``run_feature_end_cycle`` now wires ``verify-execution-reach`` for
real): ``test_never_executed_file_refuses_feature_end`` pins the refusal on
a genuinely never-run production file;
``test_fully_reached_tree_still_reaches_done`` is the REGRESSION guard for
the clean/fully-reached path; ``test_src_dir_missing_execution_reach_gate_
exit2_yields_cycle_indeterminate`` is the GENERICITÀ guard pinning that the
gate's own exit-2 (regardless of root cause) escalates to
``CycleIndeterminate`` (DDD-CERT-4, reconciled 2026-07-14 -- see the
stale-record reconciliation note further below in this file for the
superseded ``CycleSuccess``/NOT_APPLICABLE contract this file used to pin).

Requirement coverage markers (R3/R4/R7/R8) are placed per-TEST-FUNCTION below
(the ``verify-spec-coverage`` gate's marker scan is function-scoped -- a
module-level docstring marker is invisible to it; see DISTILL FRICTIONS).
"""

from __future__ import annotations

from pathlib import Path

from des.application import feature_end_cycle_service as svc
from des.application.feature_end_cycle_service import (
    CycleIndeterminate,
    CycleRefusal,
    CycleSuccess,
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


# NOTE (2026-07-14 stale-record reconciliation): a
# `test_no_coverage_xml_proceeds_not_applicable` unit test previously lived
# here, pinning `CycleSuccess` for a minimal repo with no coverage.xml at
# all. That contract was superseded by TWO ratified charters under
# `docs/product/expectations/certification-legs-observe-real-execution/`:
# zero-observation (`feature-end-does-not-certify-done-over-zero-observed-
# checks.md`, slice-02) means a cycle where every leg -- including this one
# -- resolves NOT_APPLICABLE must yield `CycleIndeterminate`, never
# `CycleSuccess`. The unit test's two facts are now pinned at finer/broader
# granularity by the shipped acceptance suite: the LEG-level fact (missing
# coverage.xml -> `ExecutionReachLegNotApplicable`, never `*Indeterminate`)
# is asserted directly via `svc._run_execution_reach_gate` in
# `test_genuinely_absent_coverage_xml_stays_not_applicable_regression`
# (test_slice_03_execution_reach_gate_exit2_yields_indeterminate.py); the
# CYCLE-level "zero legs ran -> CycleIndeterminate" fact is asserted
# generically (multiple fixture shapes) in
# test_slice_02_full_suite_leg_marker_miss_yields_indeterminate.py. Removed
# as a redundant stale record rather than updated (git keeps history).


def test_src_dir_missing_execution_reach_gate_exit2_yields_cycle_indeterminate(
    tmp_path: Path, monkeypatch
) -> None:
    """REGRESSION-CLASS GUARDRAIL (R8, sibling-gate parity, deep-review D2,
    RECONCILED 2026-07-14 to DDD-CERT-4): a target repo whose production
    code lives under a non-conventional root (e.g. ``lib/`` instead of the
    hardcoded ``src/``) HAS a valid Cobertura ``coverage.xml`` -- the
    precondition-check (``coverage_xml_path.is_file()``) passes and the gate
    is genuinely dispatched -- but the REAL ``des verify-execution-reach``
    gate exits 2 (``ExecutionReachIndeterminate``: "src-dir src is not a
    directory under <repo>") because it cannot find the hardcoded ``src/``
    root (``_EXECUTION_REACH_SRC_DIR = "src"``).

    SUPERSEDES the pre-2026-07-14 contract this test used to pin
    (``CycleSuccess`` / NOT_APPLICABLE): per
    ``could-not-judge-is-not-not-applicable.md`` (DDD-CERT-4, ratified),
    the gate's OWN exit-2 ("I could not judge") is an epistemic gap that
    must NEVER be silently recycled into NOT_APPLICABLE -- it escalates to
    ``CycleIndeterminate``. ``_run_execution_reach_gate`` maps
    ``returncode == 2`` to ``ExecutionReachLegIndeterminate``, and the cycle
    escalates that immediately to ``CycleIndeterminate`` (never proceeding
    to sign a verdict).

    This test's continuing value beyond slice-03's own exit-2 AT
    (``test_execution_reach_gate_exit2_yields_cycle_indeterminate``, which
    triggers exit-2 via a present-but-*malformed* coverage.xml): it pins a
    SECOND, structurally distinct root cause reaching the SAME exit-2 path
    -- a missing/non-conventional ``src/`` layout, not a parse failure --
    proving the escalation is genuinely decoupled from WHY the gate could
    not judge (R8 genericità: any exit-2, for any reason, escalates
    uniformly).

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

    assert isinstance(result, CycleIndeterminate), (
        "the gate's own exit-2 (src-dir does not resolve) must escalate to "
        f"CycleIndeterminate, never a silently-recycled CycleSuccess: {result!r}"
    )
    assert "execution-reach" in result.reason
    assert "src-dir" in result.reason
    _assert_no_signed_verdict(repo_root, _FEATURE_ID)
    print(f"VERBATIM (src-dir-missing-indeterminate): {result!r}")
