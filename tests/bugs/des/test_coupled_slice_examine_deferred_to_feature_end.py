"""Regression (GDP-1/GDP-3): a `@coupled` slice must commit on its own green
AT with its real-product examine DEFERRED to feature-end -- not refused
`ExamineVerdictMissing` for lacking evidence that cannot exist in isolation.

RCA: docs/analysis/root-cause-analysis-coupled-slice-examine-deferred-to-
feature-end.md
Charter: docs/product/expectations/fix-coupled-slice-examine-deferred-to-
feature-end/coupled-slice-commits-examine-deferred.md

THE DEFECT (RED today): `check_examine_verdict` (`src/des/cli/commit_slice.py:
584-723`), armed by `_examine_gate_armed` (`:509-522`), demands a fresh PASS
`ExamineVerdict` keyed to the entering `slice_id` for EVERY armed commit --
it never reads the Slice-Plan `Annotation` cell, so a `@coupled` slice (whose
guarantee is only observable through the ASSEMBLED feature, never in
isolation) has no per-slice record to find and is refused
`ExamineVerdictMissing` (exit 2), even with a green AT. The carpaccio ENTRY
gate already forgives `@coupled` (`CoupledSliceAccepted`,
`carpaccio_format.py:1093`) -- the E3 examine/commit gate does not (RCA
Branch A).

THE FIX (not implemented here -- test-authoring only, zero `src/` edits): a
`@coupled` slice's examine is DEFERRED to feature-end. It commits on its own
green AT, an `ExamineDeferredToFeatureEnd` record is written (single-sited,
mirroring `_run_verify_then_record`'s `SliceCommitVerified` write discipline
-- `verify_slice_commit_completeness.py:1546`), and feature-end still runs
its unconditional per-charter examine leg
(`feature_end_cycle_service._run_feature_end_examine_leg`, already armed and
unmodified by this fix).

Driving surface (Mandate-16 driving-port-only, Layer 3 in-process default):
the REAL `des.cli.commit_slice.main()` CLI driver (captured via `capsys`) for
the commit-time constraints, and the REAL
`des.application.feature_end_cycle_service.run_feature_end_cycle` for the
feature-end constraint -- the SAME production entry points the RCA's call-
site table names, never a direct-domain unit call into a smaller helper.

Fixture reuse (per dispatch instruction -- do NOT hand-roll a new harness):
`_init_repo` is the exact pytest-collectible git work-tree shape proven GREEN
by `tests/bugs/des/test_commit_slice_writes_verified_record.py` /
`test_commit_slice_forwards_at_kind_and_earns_verified_record_end_to_end.py`.
The entering slice's AT is a real, pytest-collectible `--at-kind
pytest-regression --regression-test-file <path>` file (the SAME already-
shipped forwarding path proven GREEN by
`test_commit_slice_forwards_at_kind_and_earns_verified_record_end_to_end`) --
chosen because it earns a genuinely GREEN AT for the entering slice without
needing pytest-bdd step-bindings, exactly like that proven precedent. The
feature-end constraint reuses the stub-upstream-legs shape proven GREEN by
`tests/des/unit/application/test_feature_end_cycle_examine_gate.py`.

Constraint coverage (RCA section 7, charter oracle):
  1 (POSITIVE)  -- `test_coupled_slice_commits_on_green_at_and_attests_deferred_examine`
  2 (ATTESTED)  -- `test_coupled_slice_commits_on_green_at_and_attests_deferred_examine`
  a (NEGATIVE)  -- `test_non_coupled_sibling_slice_still_requires_its_own_examine_verdict`
  b (NEGATIVE)  -- `test_feature_end_examine_still_required_after_a_coupled_slice_deferred`,
                   `test_feature_end_examine_fail_blocks_done_even_after_coupled_slice_committed`
  d (NEGATIVE)  -- `test_coupled_status_is_never_granted_without_the_trusted_slice_plan_row`
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.application import feature_end_cycle_service as svc
from des.application.feature_end_cycle_service import (
    CycleRefusal,
    FullSuiteLegRan,
    run_feature_end_cycle,
)
from des.cli.commit_slice import main as commit_slice_main
from des.cli.record_examine_verdict import record_examine_verdict
from tests.charter_fixtures import filled_charter


_COUPLED_JUSTIFICATION = (
    "the length-invariance guarantee is only observable through the "
    "assembled coin-flip product, never by driving this one slice alone"
)


# ---------------------------------------------------------------------------
# Shared fixture builders
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
    """Init a real pytest-collectible git work-tree (mirrors the proven GREEN
    precedent `_init_repo` in `test_commit_slice_writes_verified_record.py`
    verbatim -- the exact shape that already makes `des commit-slice`'s
    whole-tree committed-scope digest + `run_contract_gate
    --verify-gate-scope` succeed today).
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


def _write_slice_plan(
    repo: Path, feature_id: str, rows: list[tuple[str, str, str, str, str]]
) -> None:
    """A `[REF] Slice Plan` table -- `rows` is
    `(slice_id, value_statement, status, annotation, justification)`."""
    delta_dir = repo / "docs" / "feature" / feature_id
    delta_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Feature Delta: {feature_id}\n\n",
        "## Wave: DISCUSS / [REF] Slice Plan\n\n",
        "| Slice | Value statement | Status | Annotation | Justification |\n",
        "|-------|-----------------|--------|------------|---------------|\n",
    ]
    for slice_id, value_statement, status, annotation, justification in rows:
        lines.append(
            f"| {slice_id} | {value_statement} | {status} | {annotation} | "
            f"{justification} |\n"
        )
    (delta_dir / "feature-delta.md").write_text("".join(lines), encoding="utf-8")


def _write_charter(
    root: Path,
    feature_id: str,
    name: str = "main",
    body: str = filled_charter("Do the thing."),
) -> Path:
    """A charter under `docs/product/expectations/{feature_id}/` -- ARMS the
    examine-verdict commit gate (`_examine_gate_armed`) and the feature-end
    examine leg (`_run_feature_end_examine_leg`) alike."""
    charter_dir = root / "docs" / "product" / "expectations" / feature_id
    charter_dir.mkdir(parents=True, exist_ok=True)
    charter_path = charter_dir / f"{name}.md"
    charter_path.write_text(body, encoding="utf-8")
    return charter_path


def _write_regression_test(
    repo: Path,
    feature_id: str,
    slice_id: str,
    rel_path: str,
    *,
    passing: bool = True,
    extra_comment: str | None = None,
) -> Path:
    """A real, pytest-collectible regression test file, head-tagged for the
    SAME `feature_id`/`slice_id` E1 discovers via `# @feature-{id}` /
    `# @{slice-id}` head-comment tags (mirrors `_write_regression_test` in
    `test_commit_slice_forwards_at_kind_and_earns_verified_record_end_to_end.py`
    verbatim). `extra_comment` optionally injects a STRAY, untrusted claim of
    coupling that carries no structural weight -- used by the fail-closed
    guard (constraint d) to prove the deferral is never granted from it."""
    path = repo / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    header = f"# @feature-{feature_id}\n# @{slice_id}\n"
    if extra_comment:
        header += f"# {extra_comment}\n"
    if passing:
        body = "def test_the_slice_behaviour_holds():\n    assert 1 + 1 == 2\n"
    else:
        body = (
            "def test_the_slice_behaviour_is_broken():\n"
            "    assert 1 + 1 == 3, 'the behaviour is NOT correct'\n"
        )
    path.write_text(header + body, encoding="utf-8")
    return path


def _last_json_event_or_empty(stdout: str) -> dict[str, object]:
    json_lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    return json.loads(json_lines[-1]) if json_lines else {}


def _run_commit(
    repo: Path,
    feature_id: str,
    slice_id: str,
    regression_test_file_rel: str,
    capsys: pytest.CaptureFixture[str],
    *,
    message: str = "feat(slice): ships the slice behaviourally",
) -> tuple[int, dict[str, object]]:
    """Drive the REAL `des commit-slice` CLI in-process, capturing its
    single-line JSON payload via `capsys` (mirrors `_run_commit_slice_with_
    at_kind` in the proven GREEN `--at-kind` forwarding precedent)."""
    try:
        exit_code = commit_slice_main(
            [
                "--repo",
                str(repo),
                "--all",
                "--feature-id",
                feature_id,
                "--slice-id",
                slice_id,
                "--message",
                message,
                "--at-kind",
                "pytest-regression",
                "--regression-test-file",
                regression_test_file_rel,
            ]
        )
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 1
    stdout = capsys.readouterr().out
    return exit_code, _last_json_event_or_empty(stdout)


def _iter_ledger_records(repo: Path):
    """Every JSON record under `.nwave/**/*.jsonl` -- deliberately NOT pinned
    to one specific ledger file, since the fix's exact landing locus for the
    deferral attestation is a DESIGN decision this AT does not presume; it
    only asserts the record is somewhere VISIBLE under the repo's telemetry
    substrate, per the charter's oracle ("something in the commit's own
    record or output names that the examine was deferred")."""
    telemetry_root = repo / ".nwave"
    if not telemetry_root.is_dir():
        return
    for jsonl_path in sorted(telemetry_root.rglob("*.jsonl")):
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                yield record


def _deferral_record(
    repo: Path, feature_id: str, slice_id: str
) -> dict[str, object] | None:
    for record in _iter_ledger_records(repo):
        if record.get("event") != "ExamineDeferredToFeatureEnd":
            continue
        if record.get("feature_id") not in (None, feature_id):
            continue
        if record.get("slice_id") != slice_id:
            continue
        return record
    return None


# ===========================================================================
# 1 + 2 -- POSITIVE + ATTESTED (active-RED today)
# ===========================================================================


def test_coupled_slice_commits_on_green_at_and_attests_deferred_examine(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A `@coupled` Slice-Plan row (with a recorded justification) whose
    entering slice carries a genuinely GREEN pytest-regression AT, and NO
    per-slice examine verdict, must COMMIT (constraint 1) -- and the commit
    must leave a VISIBLE `ExamineDeferredToFeatureEnd` attestation
    (constraint 2), never a silent bypass indistinguishable from "nobody
    checked".

    RED for the right reason today: `check_examine_verdict` has zero
    `@coupled`-awareness (`commit_slice.py:584-625`) -- the direct examine
    guard in `main()` (`:1561-1568`) refuses with `ExamineVerdictMissing`
    (exit 2) BEFORE the commit lands, so BOTH constraint (1)'s exit_code/
    event assertion and constraint (2)'s ledger-record assertion fail with a
    genuine `AssertionError` -- never an import/collection error.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id = "fix-coupled-defer-pos"
    _write_slice_plan(
        repo,
        feature_id,
        rows=[
            (
                "slice-01",
                "the product answers every time (length-invariance)",
                "pending",
                "@coupled",
                _COUPLED_JUSTIFICATION,
            ),
            (
                "slice-02",
                "the product accepts a fair coin-flip call",
                "pending",
                "",
                "",
            ),
        ],
    )
    _write_charter(repo, feature_id)  # ARMS the E3 examine gate
    regression_rel = "tests/bugs/fixture/test_fix_coupled_defer_pos_slice_01.py"
    _write_regression_test(repo, feature_id, "slice-01", regression_rel, passing=True)
    # Deliberately NO per-slice ExamineVerdict recorded for slice-01 -- the
    # exact shape a @coupled slice can never independently produce.

    exit_code, event = _run_commit(repo, feature_id, "slice-01", regression_rel, capsys)

    # --- constraint (1) POSITIVE ------------------------------------------
    assert exit_code == 0 and event.get("event") == "SliceCommitted", (
        "a @coupled slice (Slice-Plan row annotated @coupled with a recorded "
        "justification) whose OWN AT is green must commit on the strength of "
        "that green test alone -- it has no independently-observable "
        "surface, so demanding a per-slice ExamineVerdict asks for evidence "
        f"that cannot exist. observed exit_code={exit_code!r} event={event!r} "
        "(today check_examine_verdict refuses ExamineVerdictMissing "
        "unconditionally -- commit_slice.py:584-625, armed by "
        "_examine_gate_armed at :509-522)"
    )

    verified = AtCompletionLedger(feature_id, repo).verified_slices()
    assert "slice-01" in verified, (
        "the coupled slice's commit must still earn SliceCommitVerified -- "
        f"observed verified_slices={sorted(verified)!r}"
    )

    # --- constraint (2) ATTESTED -------------------------------------------
    record = _deferral_record(repo, feature_id, "slice-01")
    assert record is not None, (
        "a @coupled slice that commits with NO per-slice examine-verdict "
        "must leave a DISTINCT ExamineDeferredToFeatureEnd ledger record "
        "naming the deferral -- an auditor must be able to tell 'deferred on "
        "purpose' apart from 'nobody checked' (RCA section 7, constraint c). "
        "observed no such record anywhere under .nwave/ after the commit"
    )


# ===========================================================================
# a -- NEGATIVE: the deferral is @coupled-ONLY, never a universal bypass
# ===========================================================================


@pytest.mark.negative_at
def test_non_coupled_sibling_slice_still_requires_its_own_examine_verdict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """constraint (a): a NON-`@coupled` sibling slice, in the SAME feature as
    a `@coupled` slice, with a green AT and NO per-slice examine verdict,
    must still be REFUSED `ExamineVerdictMissing` -- the defer must gate
    STRICTLY on the entering slice's OWN row annotation, never on any slice
    in the feature being armed. Pin: green today (the gate already refuses
    unconditionally) and MUST stay green after the fix.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id = "fix-coupled-defer-neg-noncoupled"
    _write_slice_plan(
        repo,
        feature_id,
        rows=[
            (
                "slice-01",
                "the product answers every time (length-invariance)",
                "pending",
                "@coupled",
                _COUPLED_JUSTIFICATION,
            ),
            (
                "slice-02",
                "the product accepts a fair coin-flip call",
                "pending",
                "",
                "",
            ),
        ],
    )
    _write_charter(repo, feature_id)
    regression_rel = (
        "tests/bugs/fixture/test_fix_coupled_defer_neg_noncoupled_slice_02.py"
    )
    _write_regression_test(repo, feature_id, "slice-02", regression_rel, passing=True)

    exit_code, event = _run_commit(repo, feature_id, "slice-02", regression_rel, capsys)

    assert exit_code == 2 and event.get("event") == "ExamineVerdictMissing", (
        "a NON-coupled slice must still require its own isolated real-"
        "product examine, even though its sibling slice-01 in the SAME "
        "feature is @coupled -- the deferral must never generalize into "
        f"'any slice's own-examine can be skipped'. observed "
        f"exit_code={exit_code!r} event={event!r}"
    )


# ===========================================================================
# b -- NEGATIVE: feature-end examine is DEFERRED, never DROPPED
# ===========================================================================


def _seed_feature_dir(root: Path, feature_id: str) -> Path:
    feature_dir = root / "docs" / "feature" / feature_id
    feature_dir.mkdir(parents=True, exist_ok=True)
    return feature_dir


def _stub_upstream_legs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Short-circuit every leg that runs BEFORE the feature-end examine leg
    (mirrors `_stub_upstream_legs` in
    `tests/des/unit/application/test_feature_end_cycle_examine_gate.py`)."""
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
    monkeypatch.setattr(
        svc,
        "_run_full_suite_leg",
        lambda *, repo_root, feature_id=None: FullSuiteLegRan(pytest_exit_code=0),
    )


def _run_feature_end(tmp_path: Path, feature_dir: Path, feature_id: str):
    return run_feature_end_cycle(
        repo_root=tmp_path,
        feature_id=feature_id,
        feature_dir=feature_dir,
        reviewer_agent_id="nw-software-crafter-reviewer",
        verdict="APPROVED",
    )


@pytest.mark.negative_at
def test_feature_end_examine_still_required_after_a_coupled_slice_deferred(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """constraint (b), half 1: a @coupled slice's earlier SliceCommitVerified
    (simulating the deferred commit the fix will grant) must NEVER stand in
    for the feature-end examine -- deferred means checked LATER, never
    checked NEVER. This leg (`_run_feature_end_examine_leg`,
    `feature_end_cycle_service.py:1710-1735`) already runs unconditionally
    per-charter TODAY -- this AT pins that it is not weakened by the fix.
    """
    feature_id = "fix-coupled-defer-feature-end-missing"
    _stub_upstream_legs(monkeypatch)
    feature_dir = _seed_feature_dir(tmp_path, feature_id)
    _write_charter(tmp_path, feature_id, "main")
    AtCompletionLedger(feature_id, tmp_path).append_gate_event(
        event="SliceCommitVerified", slice_id="slice-01"
    )
    # Deliberately no ExamineVerdictRecorded anywhere -- neither per-slice
    # nor feature-end-scoped.

    result = _run_feature_end(tmp_path, feature_dir, feature_id)

    assert isinstance(result, CycleRefusal), (
        "a @coupled slice's earlier SliceCommitVerified must never substitute "
        "for the feature-end examine -- the feature-end cycle must refuse to "
        f"certify done. observed {result!r}"
    )
    assert "no recorded FEATURE-END examine-verdict" in result.error, result.error


@pytest.mark.negative_at
def test_feature_end_examine_fail_blocks_done_even_after_coupled_slice_committed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """constraint (b), half 2 (the sharper one): if the feature-end examine
    LATER FAILS, the feature must NOT have already been reported done on the
    strength of the coupled slice's earlier commit alone.
    """
    feature_id = "fix-coupled-defer-feature-end-fail"
    _stub_upstream_legs(monkeypatch)
    feature_dir = _seed_feature_dir(tmp_path, feature_id)
    charter_path = _write_charter(tmp_path, feature_id, "main")
    AtCompletionLedger(feature_id, tmp_path).append_gate_event(
        event="SliceCommitVerified", slice_id="slice-01"
    )
    record_examine_verdict(
        repo=tmp_path,
        feature_id=feature_id,
        slice_id="feature-end",
        charter_path=charter_path,
        verdict="FAIL",
        observations=(
            "the assembled product does not honor the length-invariance "
            "guarantee the coupled slice-01/slice-02 group promised"
        ),
        examiner="nw-user-examiner",
        timestamp="2026-07-17T00:00:00Z",
    )

    result = _run_feature_end(tmp_path, feature_dir, feature_id)

    assert isinstance(result, CycleRefusal), (
        "a FAILED feature-end examine must refuse done even though the "
        f"coupled slice already committed. observed {result!r}"
    )
    assert "FAILED" in result.error, result.error


# ===========================================================================
# d -- NEGATIVE: fail-closed to "not coupled" -- never a stray/wrong claim
# ===========================================================================


def _delta_absent(repo: Path, feature_id: str) -> None:
    """No `docs/feature/{feature_id}/feature-delta.md` at all."""


def _delta_row_absent(repo: Path, feature_id: str) -> None:
    """A feature-delta exists, but carries NO row for the entering slice-01
    -- only an unrelated slice-99 row, itself (irrelevantly) `@coupled`."""
    _write_slice_plan(
        repo,
        feature_id,
        rows=[
            (
                "slice-99",
                "an unrelated slice in the same feature",
                "pending",
                "@coupled",
                _COUPLED_JUSTIFICATION,
            )
        ],
    )


def _delta_row_not_annotated_coupled(repo: Path, feature_id: str) -> None:
    """A feature-delta exists WITH a slice-01 row, but its Annotation cell is
    empty -- the row itself says "not coupled", regardless of any stray claim
    elsewhere (the regression file's extra_comment)."""
    _write_slice_plan(
        repo,
        feature_id,
        rows=[
            (
                "slice-01",
                "the product accepts a fair coin-flip call",
                "pending",
                "",
                "",
            )
        ],
    )


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "delta_writer",
    [
        pytest.param(_delta_absent, id="feature-delta-entirely-absent"),
        pytest.param(_delta_row_absent, id="entering-slice-row-absent-from-plan"),
        pytest.param(
            _delta_row_not_annotated_coupled, id="row-present-but-not-annotated-coupled"
        ),
    ],
)
def test_coupled_status_is_never_granted_without_the_trusted_slice_plan_row(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    delta_writer,
) -> None:
    """constraint (d): the deferral predicate must read the SAME
    feature-delta.md Slice-Plan row the carpaccio entry gate already trusts
    -- never a stray/informal claim of coupling (a comment in the AT file),
    and never a wrong/missing/absent source. Every case here must fail
    CLOSED to "not coupled" (still refused `ExamineVerdictMissing`), never
    fail OPEN to a false deferral. Pin: green today (no coupled-detection
    exists at all yet, so every entering slice is uniformly refused) and
    MUST stay green after the fix -- the exact regression the fix's write-up
    (RCA constraint d) warns against.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id = "fix-coupled-defer-neg-failclosed"
    delta_writer(repo, feature_id)
    _write_charter(repo, feature_id)
    regression_rel = (
        "tests/bugs/fixture/test_fix_coupled_defer_neg_failclosed_slice_01.py"
    )
    _write_regression_test(
        repo,
        feature_id,
        "slice-01",
        regression_rel,
        passing=True,
        extra_comment=(
            "informal note: this slice is coupled to its sibling (NOT a "
            "real @coupled signal -- the Slice-Plan row is the only trusted "
            "source)"
        ),
    )

    exit_code, event = _run_commit(repo, feature_id, "slice-01", regression_rel, capsys)

    assert exit_code == 2 and event.get("event") == "ExamineVerdictMissing", (
        "a slice must NEVER be granted the deferral except through the SAME "
        "trusted Slice-Plan row source the entry gate already reads -- an "
        "absent/wrong/malformed feature-delta, or a stray claim of coupling "
        "anywhere else (a comment, a passing remark), must fail CLOSED to "
        f"'not coupled'. observed exit_code={exit_code!r} event={event!r}"
    )
