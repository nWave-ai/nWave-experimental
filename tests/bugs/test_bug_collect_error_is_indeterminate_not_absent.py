"""Regression: a genuine pytest COLLECTION ERROR must never be read as
NOT_APPLICABLE (ontological absence) by the feature-end full-suite leg.

RCA (already diagnosed, this file does not re-derive it):
``src/des/application/feature_end_cycle_service.py::_repo_has_contract_suite``'s
PRIMARY collect attempt does::

    try:
        if bool(_collect_node_ids(repo_root)):
            return True
    except (_CollectionError, OSError, InterpreterUnavailable):
        return False

collapsing THREE different situations into one bare ``False``:

* ``InterpreterUnavailable`` -- the repo genuinely carries no pytest
  interpreter (e.g. a Rust-only ``cargo`` project). Ontological absence.
  ``False`` (-> NOT_APPLICABLE) is CORRECT here.
* ``OSError`` -- a genuine filesystem-level failure to even spawn the
  collect worker. Arguably also a "cannot observe" case, unchanged by this
  bug report.
* ``_CollectionError`` -- pytest DID run and FAILED TO COLLECT (a crashing
  test module: an import error, a syntax error, a fixture blow-up at
  collection time). The suite EXISTS; the leg simply could not observe it.
  This is an EPISTEMIC gap ("I could not observe"), never an ONTOLOGICAL
  absence ("nothing exists") -- ``False`` is WRONG here.

Exactly this same function, ~30 lines below the primary try/except, already
encodes the epistemic-vs-ontological distinction CORRECTLY for the
marker-agnostic secondary collect (DDD-CERT-3): a marker-filtered miss with a
marker-agnostic hit returns :class:`FullSuiteLegIndeterminate`, carrying a
DDD-CERT-3 comment stating verbatim that "epistemic absence ('I did not
observe this') is never conflated with ontological absence ('nothing
exists')." The primary handler above violates the very rule the rest of the
function states.

CONSEQUENCE at the cycle level: because ``_repo_has_contract_suite`` returns
bare ``False``, ``_run_full_suite_leg`` falls through to
:class:`FullSuiteLegNotApplicable` (or, absent a ``src/``-only suite, the
generic "no collectable contract suite" NA). The feature-end cycle then
PROCEEDS -- and, if any OTHER leg genuinely observes something real (e.g. the
repo ships a plain ``README.md``, so the doc-coherence leg genuinely RUNS),
the cycle SIGNS a verdict and emits ``FeatureEndCycleComplete`` WITHOUT EVER
HAVING RUN THE SUITE. A repo whose tests genuinely crash on import looks,
from the observable CLI surface, identical to a repo with a clean full-suite
pass.

Reproduced in this file with a synthetic ``tests/test_boom.py`` that raises
``ModuleNotFoundError`` at import time -- a real pytest subprocess collection
that exits 2 (not 0/5), confirmed empirically against this worktree's own
pytest before authoring this file.

Driving surface (Mandate-13 driving-port-only, Layer 3 composition,
IN-PROCESS default): the primary consequence AT drives the REAL ``des
feature-end run`` CLI in-process (``des.cli.feature_end.main``, captured via
``capsys``) -- the same pattern the sibling slice-02 AT in
``tests/des/acceptance/certification_legs_observe_real_execution/
test_slice_02_full_suite_leg_marker_miss_yields_indeterminate.py`` already
uses for this exact leg family. The leg-level tests call
``feature_end_cycle_service._run_full_suite_leg`` / ``_repo_has_contract_suite``
directly -- the SAME boundary-guard pattern that sibling file's
``test_unmarked_suite_under_src_keeps_the_leg_not_applicable_not_indeterminate``
already establishes in this codebase: the dispatch envelope for this bugfix
explicitly requires asserting on the diagnosed function's OWN return type, in
addition to (never instead of) the cycle-level consequence.

Active-RED today (real assertion failures on the defect's observable, never
an import/collection error): ``FullSuiteLegIndeterminate`` already exists as
a class (a prior slice, DDD-CERT-3, shipped it for the marker-mismatch
route) -- so importing it is safe. What fails today is that the COLLECT-ERROR
route never PRODUCES it: today's code returns ``FullSuiteLegNotApplicable``
(or a genuine ``CycleSuccess``) where this file asserts
``FullSuiteLegIndeterminate`` / ``CycleIndeterminate``.

THIS FILE IS TEST-ONLY. No production code is touched by this authoring pass.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import FEATURE_END_REVIEW_VERDICT
from des.application import feature_end_cycle_service as svc
from des.cli import feature_end as feature_end_cli


_FEATURE_ID = "collect-error-fixture"

# ADR-GV-002 D4: `des feature-end run` exit 3 == CycleIndeterminate, mirroring
# `run_contract_gate.py`'s existing local `_GATE_INDETERMINATE_EXIT_CODE = 3`
# pattern (already shipped and exercised by the slice-02 sibling AT).
_EXPECTED_INDETERMINATE_EXIT = 3


def _seed_feature_dir(repo_root: Path, feature_id: str = _FEATURE_ID) -> Path:
    """A minimal feature-dir with NO feature-delta.md (no Slice-Plan -> no
    undelivered-slice truncation refusal) -- mirrors the sibling slice-02 AT's
    ``_seed_feature_dir``, keeping the fixture focused on the full-suite leg
    alone."""
    feature_dir = repo_root / "docs" / "feature" / feature_id
    feature_dir.mkdir(parents=True)
    return feature_dir


_COLLECT_ERROR_TEST_BODY = (
    "import totally_nonexistent_module_xyz_zzz\n\n\n"
    "def test_never_reached():\n    assert True\n"
)


def _seed_collect_error_suite(repo_root: Path) -> None:
    """A ``tests/`` root carrying ONE module that raises ``ModuleNotFoundError``
    at import time -- a genuine pytest COLLECTION ERROR (empirically confirmed
    exit code 2, never 0 or 5), never a genuine absence of tests. This is the
    exact epistemic-gap shape ``_CollectionError`` exists to carry (the worker
    captures the crashing module's nodeid via ``pytest_collectreport``)."""
    tests_dir = repo_root / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_boom.py").write_text(_COLLECT_ERROR_TEST_BODY, encoding="utf-8")


def _seed_collect_error_suite_with_doc_claim(repo_root: Path) -> None:
    """The SAME collect-error suite, PLUS a plain ``README.md`` carrying no
    verifiable (hence never-false) doc claims -- confirmed empirically
    against this worktree's own ``des verify-doc-coherence`` to exit 0
    (``DocCoherenceLegRan``). This makes the doc-coherence leg genuinely RUN
    for real, which is exactly what surfaces the cycle-level consequence:
    without a second leg genuinely observing something, TODAY's cycle would
    reach ``CycleIndeterminate`` anyway via the UNRELATED "zero legs ran"
    catch-all -- masking the collect-error-specific defect behind a
    coincidentally-correct-looking exit code. WITH the doc-coherence leg
    genuinely running, TODAY's cycle proceeds all the way to a genuine,
    unstubbed ``CycleSuccess`` -- signing a verdict over a full-suite leg
    that never observed its own collection error."""
    _seed_collect_error_suite(repo_root)
    (repo_root / "README.md").write_text(
        "# Fixture Repo\n\nA minimal repo used to reproduce the collect-error "
        "defect.\n",
        encoding="utf-8",
    )


def _seed_no_tests_at_all(repo_root: Path) -> None:
    """A repo with production source but GENUINELY ZERO test files anywhere
    -- the ontological-absence case that must stay NOT_APPLICABLE. Its
    marker-filtered collect exits 5 (no tests collected), never raising
    ``_CollectionError`` -- this fixture must NOT regress to Indeterminate."""
    src = repo_root / "src" / "widgetpkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "core.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")


_MARKED_RUNNABLE_TEST_BODY = (
    "import pytest\n\n\n@pytest.mark.unit\ndef test_widget_behaves():\n"
    "    assert 1 + 1 == 2\n"
)


def _seed_marked_runnable_suite_with_manifest(repo_root: Path) -> None:
    """A genuinely-runnable, MARKED pytest suite at the conventional
    ``tests/`` root, plus a realistic top-level ``pyproject.toml`` -- the
    healthy-repo baseline the fix must not regress: the marker-filtered
    collect finds >=1 node-id, so the leg genuinely RUNS the real suite."""
    tests_dir = repo_root / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_widget.py").write_text(
        _MARKED_RUNNABLE_TEST_BODY, encoding="utf-8"
    )
    (repo_root / "pyproject.toml").write_text(
        '[project]\nname = "foreign-repo"\nversion = "0.1.0"\n', encoding="utf-8"
    )


def _stub_non_full_suite_legs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Short-circuit every OTHER leg so only the REAL (unstubbed) full-suite
    leg -- and its real collection subprocess -- can determine the cycle's
    outcome up to the batch's shared-leg checkpoint. Mirrors the sibling
    slice-02 AT's ``_stub_non_full_suite_legs`` verbatim."""
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
    planter: Callable[[Path], None],
    feature_id: str = _FEATURE_ID,
) -> tuple[int, dict[str, object]]:
    """Stage a target-repo fixture (via ``planter``) and drive the REAL ``des
    feature-end run`` CLI in-process (Layer 3 composition). Returns
    ``(exit_code, parsed_json_payload)`` -- the command's real observables."""
    _stub_non_full_suite_legs(monkeypatch)
    repo_root = tmp_path / "target-repo"
    repo_root.mkdir()
    planter(repo_root)
    feature_dir = _seed_feature_dir(repo_root, feature_id)

    exit_code = feature_end_cli.main(
        [
            "run",
            "--repo",
            str(repo_root),
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
    captured = capsys.readouterr()
    payload = json.loads(captured.out.strip().splitlines()[-1])
    return exit_code, payload


def _feature_end_review_verdict_recorded(repo_root: Path, feature_id: str) -> bool:
    """Whether the legacy per-feature ledger
    (``.nwave/telemetry/atdd-pure/{feature_id}.jsonl``, the shape
    ``_run_feature_end_member_cycle`` writes via
    ``AtCompletionLedger(feature_id, repo_root)``) carries a
    ``FeatureEndReviewVerdict`` record -- the SIGNED-verdict observable this
    bug report demands stays ABSENT for a repo whose full-suite leg never
    genuinely observed its own collection error."""
    ledger_path = (
        repo_root / ".nwave" / "telemetry" / "atdd-pure" / f"{feature_id}.jsonl"
    )
    if not ledger_path.is_file():
        return False
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (
            isinstance(record, dict)
            and record.get("event") == FEATURE_END_REVIEW_VERDICT
        ):
            return True
    return False


# ---------------------------------------------------------------------------
# 1. POSITIVE (the defect) -- leg-level return type.
# ---------------------------------------------------------------------------


def test_collect_error_suite_yields_full_suite_leg_indeterminate_not_absent(
    tmp_path: Path,
) -> None:
    """POSITIVE AT (active-RED today): a repo whose pytest COLLECTION
    genuinely ERRORS (a real ``ModuleNotFoundError`` at import time, exit
    code 2) must yield :class:`FullSuiteLegIndeterminate` -- an EPISTEMIC "I
    could not observe this" -- never :class:`FullSuiteLegNotApplicable` (an
    ONTOLOGICAL "nothing exists here", the exact conflation this bug report
    closes). Today ``_repo_has_contract_suite``'s primary ``except
    (_CollectionError, OSError, InterpreterUnavailable): return False``
    swallows the ``_CollectionError`` and the leg falls through to
    ``FullSuiteLegNotApplicable`` -- this assertion is what fails.
    """
    repo_root = tmp_path / "collect-error-repo"
    repo_root.mkdir()
    _seed_collect_error_suite(repo_root)

    outcome = svc._run_full_suite_leg(repo_root=repo_root)

    assert isinstance(outcome, svc.FullSuiteLegIndeterminate), (
        "a repo whose pytest COLLECTION genuinely errors (a crashing test "
        "module) must yield FullSuiteLegIndeterminate, never "
        f"FullSuiteLegNotApplicable/False: got {outcome!r}"
    )


def test_collect_error_indeterminate_reason_names_exit_code_and_crashing_module(
    tmp_path: Path,
) -> None:
    """POSITIVE AT (active-RED today, GDP-3/GDP-4): the INDETERMINATE
    reason must surface the diagnostics the collect worker ALREADY produces
    and today's code throws away -- the pytest exit code
    (``_CollectionError``'s message already embeds it: "pytest collection
    exited 2") and the crashing module's nodeid (``_CollectionError.
    crashing_module``, already populated by ``_collect_scope_worker.py``'s
    ``pytest_collectreport`` hook via ``NWAVE_COLLECT_SCOPE_ERROR``). Today
    the leg never even reaches ``FullSuiteLegIndeterminate`` for this route
    -- this assertion is what fails.
    """
    repo_root = tmp_path / "collect-error-repo"
    repo_root.mkdir()
    _seed_collect_error_suite(repo_root)

    outcome = svc._run_full_suite_leg(repo_root=repo_root)

    assert isinstance(outcome, svc.FullSuiteLegIndeterminate), (
        f"expected FullSuiteLegIndeterminate to assert its reason text "
        f"against (GDP-3 self-explaining WHAT/WHY/HOW); got {outcome!r}"
    )
    reason = outcome.reason
    assert "test_boom" in reason, (
        "the INDETERMINATE reason must NAME the crashing module (the "
        "worker's own NWAVE_COLLECT_SCOPE_ERROR payload already carries "
        f"'crashing_module' -- today's broad except discards it): "
        f"reason={reason!r}"
    )
    assert re.search(r"exit\w*\D{0,10}\b2\b", reason, re.IGNORECASE), (
        "the INDETERMINATE reason must surface the pytest collection exit "
        "code (2, already embedded in _CollectionError's own message -- "
        f"today's broad except discards it): reason={reason!r}"
    )


# ---------------------------------------------------------------------------
# 2. POSITIVE (the defect) -- cycle-level consequence.
# ---------------------------------------------------------------------------


def test_collect_error_repo_never_signs_a_verdict_it_never_ran(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """POSITIVE AT (active-RED today) -- the CONSEQUENCE at the cycle level:
    a repo whose full-suite leg genuinely collect-errors, but whose
    doc-coherence leg genuinely RUNS (a plain README with no false claims,
    confirmed to exit 0 for ``des verify-doc-coherence``), must NEVER reach a
    signed ``CycleSuccess`` -- the cycle must escalate to
    ``CycleIndeterminate`` (exit 3) BEFORE the doc-coherence leg is even
    reached (the shared full-suite leg is checked once, batch-wide, ahead of
    every per-feature leg).

    Today: ``_repo_has_contract_suite`` swallows the ``_CollectionError`` and
    returns ``False`` -> ``FullSuiteLegNotApplicable`` -> the batch does NOT
    short-circuit -> the per-member cycle runs -> doc-coherence genuinely
    RUNS (``DocCoherenceLegRan``, ``leg_census.ran == 1``) -> the cycle's
    final "zero-ran" guard does not fire (``ran != 0``) -> the cycle SIGNS a
    verdict and emits ``FeatureEndCycleComplete`` (exit 0) -- a repo whose
    tests genuinely crash on import is CERTIFIED DONE without the full suite
    ever having been observed. These assertions are what fails.
    """
    exit_code, payload = _run_cycle_cli(
        monkeypatch,
        capsys,
        tmp_path,
        planter=_seed_collect_error_suite_with_doc_claim,
    )
    repo_root = tmp_path / "target-repo"

    assert exit_code == _EXPECTED_INDETERMINATE_EXIT, (
        "a repo whose full-suite leg genuinely collect-errors must exit "
        f"{_EXPECTED_INDETERMINATE_EXIT} (CycleIndeterminate) -- the full "
        "suite was never observed, so the cycle must never certify done, "
        f"regardless of what any OTHER leg genuinely observed. Got exit "
        f"{exit_code}, payload={payload!r}"
    )
    assert payload.get("event") == "FeatureEndCycleIndeterminate", (
        f"expected FeatureEndCycleIndeterminate: payload={payload!r}"
    )
    assert payload.get("event") != "FeatureEndCycleComplete", (
        "the cycle must NEVER sign a verdict over a full-suite leg that "
        f"never observed its own collection error: payload={payload!r}"
    )
    assert "verdict_hash" not in payload, (
        "no signed verdict may be produced for a repo whose full-suite leg "
        f"collect-errors: payload={payload!r}"
    )
    assert not _feature_end_review_verdict_recorded(repo_root, _FEATURE_ID), (
        "no FeatureEndReviewVerdict ledger record may be emitted for a repo "
        "whose full-suite leg genuinely collect-errors -- the anti-theater "
        "invariant: a failed/un-observed leg yields no fake 'feature-end "
        "complete'."
    )
    leg_census = payload.get("leg_census")
    if isinstance(leg_census, dict):
        assert leg_census.get("ran", 0) == 0, (
            "the shared full-suite leg short-circuits the WHOLE batch "
            "BEFORE any per-member leg (including doc-coherence) runs -- "
            f"leg_census must show zero legs genuinely ran: {leg_census!r}"
        )


# ---------------------------------------------------------------------------
# 3. NEGATIVE ORACLE A -- genuine absence must stay NOT_APPLICABLE, and the
#    cycle must not turn graceful degradation into a hard block.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_genuinely_absent_suite_does_not_regress_to_hard_refusal(
    tmp_path: Path,
) -> None:
    """NEGATIVE AT (must not regress): a repo with production source but
    GENUINELY ZERO test files anywhere has nothing to observe -- the leg must
    stay :class:`FullSuiteLegNotApplicable`, NEVER
    :class:`FullSuiteLegIndeterminate` and NEVER a raised exception /
    ``CycleRefusal``-causing failure. This fixture's marker-filtered collect
    exits 5 (no tests collected) -- never raising ``_CollectionError`` -- so
    it never even reaches the handler this bug report touches; this AT pins
    that the fix does not widen the exception mapping so far that genuine
    absence starts masquerading as a collection error too.
    """
    repo_root = tmp_path / "no-suite-repo"
    repo_root.mkdir()
    _seed_no_tests_at_all(repo_root)

    outcome = svc._run_full_suite_leg(repo_root=repo_root)

    assert isinstance(outcome, svc.FullSuiteLegNotApplicable), (
        "a repo with genuinely zero test files anywhere must stay "
        f"FullSuiteLegNotApplicable: got {outcome!r}"
    )
    assert not isinstance(outcome, svc.FullSuiteLegIndeterminate), (
        "graceful degradation over genuine absence must never be turned "
        f"into a hard block / INDETERMINATE: got {outcome!r}"
    )


# ---------------------------------------------------------------------------
# 4. NEGATIVE ORACLE B -- a healthy, normally-marked suite must still run.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_healthy_marked_suite_is_not_regressed_to_indeterminate(
    tmp_path: Path,
) -> None:
    """NEGATIVE AT (must not regress): a repo carrying a normally-marked,
    genuinely-runnable contract suite must still yield ``True`` from the
    presence probe and :class:`FullSuiteLegRan` from the leg -- the fix must
    not widen the exception handling so broadly that a healthy suite stops
    being collected/run.
    """
    repo_root = tmp_path / "healthy-repo"
    repo_root.mkdir()
    _seed_marked_runnable_suite_with_manifest(repo_root)

    presence = svc._repo_has_contract_suite(repo_root)
    assert presence is True, (
        f"a healthy, marked, genuinely-runnable suite must report presence "
        f"True: got {presence!r}"
    )

    outcome = svc._run_full_suite_leg(repo_root=repo_root)
    assert isinstance(outcome, svc.FullSuiteLegRan), (
        f"a healthy, marked suite must still genuinely RUN: got {outcome!r}"
    )
