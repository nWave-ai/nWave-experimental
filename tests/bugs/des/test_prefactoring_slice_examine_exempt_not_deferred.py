"""Regression (GDP-8 -- decide on the PROPERTY, never the DESIGNATION): an
`@infrastructure`/`@prefactoring` Slice-Plan row has NO observable surface at
ALL, in a feature that DOES carry expectation charters (for its OTHER,
observable rows). `check_examine_verdict` must EXEMPT it from the per-slice
examine requirement -- never refuse `ExamineVerdictMissing` with a
remediation that instructs dispatching `nw-user-examiner` against a charter
DISTILL's own `des charter-scaffold` tool will NEVER create for this row
(`nw-distill/SKILL.md`: "@infrastructure/@prefactoring rows are correctly
skipped by the tool -- no scaffold -> no charter -> EXAMINE unarmed -- by
design, not a gap").

RCA: measured on the `unified-event-store` feature (lane-store, slice-01,
`@infrastructure`) -- `_examine_gate_armed` (`commit_slice.py:723-736`) arms
on the FEATURE carrying >=1 charter file, ANY charter, regardless of which
slice it names (a DESIGNATION test). The only escape from the subsequent
`ExamineVerdictMissing` refusal was `_slice_is_coupled` (`:701-720`), keyed
on the single `@coupled` annotation -- `@infrastructure` and `@prefactoring`
were never consulted, even though the exact rationale the `@coupled` branch
already states verbatim ("has no independently-observable surface ... so
demanding a per-slice PASS asks for evidence that cannot exist") applies
just as literally to them. Confirmed reproducing against this worktree's
checkout of `docs/feature/unified-event-store/feature-delta.md` (slice-01
row: `| slice-01 | ... | planned | @infrastructure | Prefactoring
precondition for slice-02..04 |`) with the feature's 3 real charters (none
of them for slice-01): `check_examine_verdict` returned
`ExamineVerdictMissing` naming the impossible remediation "dispatch
nw-user-examiner with the slice's charter" for a slice that has none and
never will.

THE FIX (test-authoring only prior to GREEN): `check_examine_verdict` gains a
SECOND escape, `_slice_has_no_observable_surface`, keyed on the SAME
`_is_observable` predicate DISTILL's `charter_scaffold` tool already uses to
decide whether a row EVER gets a charter -- imported, not re-derived, so the
gate's notion of "no surface" can never drift from DISTILL's. Deliberately a
DIFFERENT ledger event (`ExamineExemptNonObservableSlice`) from the
`@coupled` escape's `ExamineDeferredToFeatureEnd`: a `@coupled` slice's
guarantee IS eventually examined, at feature-end, through a real charter: an
`@infrastructure`/`@prefactoring` slice's is not, ever, at any scope --
"deferred" would misstate that as a promise nothing keeps.

Driving surface (Mandate-16 driving-port-only): the REAL
`des.cli.commit_slice.main()` CLI driver (captured via `capsys`), mirroring
the proven-GREEN `@coupled` regression precedent
(`test_coupled_slice_examine_deferred_to_feature_end.py`) whose fixture
shapes (`_init_repo`, slice-plan writer, charter writer, pytest-regression AT
writer) this file duplicates rather than imports (matching that file's own
stated convention -- each bug regression owns its fixture copy).

Constraint coverage:
  1 (POSITIVE)  -- test_infrastructure_slice_commits_on_green_at_and_is_exempt
  1 (POSITIVE)  -- test_prefactoring_slice_commits_on_green_at_and_is_exempt
                   (parametrized twin: the OTHER non-observable annotation)
  2 (ATTESTED)  -- both POSITIVE tests: a DISTINCT `ExamineExemptNonObservableSlice`
                   record, never `ExamineDeferredToFeatureEnd`
  a (NEGATIVE)  -- test_observable_sibling_slice_still_requires_its_own_examine_verdict
  b (NEGATIVE)  -- test_exempt_status_is_never_granted_without_the_trusted_slice_plan_row
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.commit_slice import main as commit_slice_main
from tests.charter_fixtures import filled_charter


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
    precedent `_init_repo` in `test_coupled_slice_examine_deferred_to_feature_
    end.py` verbatim)."""
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
    body: str = filled_charter("Do the observable thing."),
) -> Path:
    """A charter under `docs/product/expectations/{feature_id}/` -- ARMS the
    examine-verdict commit gate (`_examine_gate_armed`), same as the real
    `unified-event-store` shape: the charter names an OBSERVABLE sibling
    slice, never the non-observable slice under test here."""
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
) -> Path:
    """A real, pytest-collectible regression test file, head-tagged for the
    SAME `feature_id`/`slice_id` E1 discovers via `# @feature-{id}` /
    `# @{slice-id}` head-comment tags."""
    path = repo / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    header = f"# @feature-{feature_id}\n# @{slice_id}\n"
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
    single-line JSON payload via `capsys`."""
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


def _ledger_record(
    repo: Path, feature_id: str, slice_id: str, event: str
) -> dict[str, object] | None:
    for record in _iter_ledger_records(repo):
        if record.get("event") != event:
            continue
        if record.get("feature_id") not in (None, feature_id):
            continue
        if record.get("slice_id") != slice_id:
            continue
        return record
    return None


# ===========================================================================
# 1 + 2 -- POSITIVE + ATTESTED
# ===========================================================================


@pytest.mark.parametrize("annotation", ["@infrastructure", "@prefactoring"])
def test_non_observable_slice_commits_on_green_at_and_is_exempt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], annotation: str
) -> None:
    """An `@infrastructure`/`@prefactoring` Slice-Plan row, in a feature that
    DOES carry a charter (for its observable sibling, never this slice), with
    a green pytest-regression AT and NO per-slice examine verdict, must
    COMMIT (constraint 1) -- and leave a DISTINCT `ExamineExemptNonObservable
    Slice` ledger record (constraint 2), never `ExamineVerdictMissing` and
    never `ExamineDeferredToFeatureEnd` (that event promises a LATER
    examine that will never happen for this row).
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id = f"fix-nonobs-defer-pos-{annotation.lstrip('@')}"
    _write_slice_plan(
        repo,
        feature_id,
        rows=[
            (
                "slice-01",
                "as an architect I can trust the base is clean before slice-02 lands",
                "planned",
                annotation,
                "Prefactoring precondition for slice-02",
            ),
            (
                "slice-02",
                "as a user I get the observable feature behaviour",
                "planned",
                "",
                "",
            ),
        ],
    )
    # ARMS the gate for the FEATURE -- names the OBSERVABLE sibling, never
    # slice-01: the exact shape measured on unified-event-store.
    _write_charter(repo, feature_id)
    regression_rel = f"tests/bugs/fixture/test_fix_nonobs_defer_pos_slice_01_{annotation.lstrip('@')}.py"
    _write_regression_test(repo, feature_id, "slice-01", regression_rel, passing=True)

    exit_code, event = _run_commit(repo, feature_id, "slice-01", regression_rel, capsys)

    assert exit_code == 0 and event.get("event") == "SliceCommitted", (
        f"a {annotation} slice (no observable surface -- DISTILL's own "
        "charter-scaffold tool never creates a charter for this row) whose "
        "OWN AT is green must commit on the strength of that green test "
        "alone. observed exit_code={exit_code!r} event={event!r}".format(
            exit_code=exit_code, event=event
        )
    )

    verified = AtCompletionLedger(feature_id, repo).verified_slices()
    assert "slice-01" in verified, f"observed verified_slices={sorted(verified)!r}"

    exempt_record = _ledger_record(
        repo, feature_id, "slice-01", "ExamineExemptNonObservableSlice"
    )
    assert exempt_record is not None, (
        f"a {annotation} slice that commits with no per-slice examine-"
        "verdict must leave a DISTINCT ExamineExemptNonObservableSlice "
        "ledger record -- an auditor must be able to tell 'permanently "
        "exempt, no oracle can exist' apart from 'nobody checked'. observed "
        "no such record anywhere under .nwave/ after the commit"
    )

    deferred_record = _ledger_record(
        repo, feature_id, "slice-01", "ExamineDeferredToFeatureEnd"
    )
    assert deferred_record is None, (
        f"a {annotation} slice's examine is NEVER 'deferred to feature-end' "
        "-- no charter will EVER exist for this row at ANY scope, so that "
        "event would promise a later examine that never happens. observed "
        f"{deferred_record!r}"
    )


# ===========================================================================
# a -- NEGATIVE: the exemption is non-observable-ONLY, never a universal bypass
# ===========================================================================


@pytest.mark.negative_at
def test_observable_sibling_slice_still_requires_its_own_examine_verdict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """constraint (a): an OBSERVABLE sibling slice (no annotation), in the
    SAME feature as an `@infrastructure` slice, with a green AT and NO
    per-slice examine verdict, must still be REFUSED `ExamineVerdictMissing`
    -- the exemption must gate STRICTLY on the entering slice's OWN row
    annotation, never on any slice in the feature being armed.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id = "fix-nonobs-defer-neg-observable"
    _write_slice_plan(
        repo,
        feature_id,
        rows=[
            (
                "slice-01",
                "as an architect I can trust the base is clean before slice-02 lands",
                "planned",
                "@infrastructure",
                "Prefactoring precondition for slice-02",
            ),
            (
                "slice-02",
                "as a user I get the observable feature behaviour",
                "planned",
                "",
                "",
            ),
        ],
    )
    _write_charter(repo, feature_id)
    regression_rel = (
        "tests/bugs/fixture/test_fix_nonobs_defer_neg_observable_slice_02.py"
    )
    _write_regression_test(repo, feature_id, "slice-02", regression_rel, passing=True)

    exit_code, event = _run_commit(repo, feature_id, "slice-02", regression_rel, capsys)

    assert exit_code == 2 and event.get("event") == "ExamineVerdictMissing", (
        "an OBSERVABLE slice must still require its own real-product "
        "examine, even though its sibling slice-01 in the SAME feature is "
        "@infrastructure -- the exemption must never generalize into 'any "
        f"slice in an armed feature can skip its own examine'. observed "
        f"exit_code={exit_code!r} event={event!r}"
    )


# ===========================================================================
# b -- NEGATIVE: fail-closed -- never a stray/wrong claim of non-observability
# ===========================================================================


def _delta_absent(repo: Path, feature_id: str) -> None:
    """No `docs/feature/{feature_id}/feature-delta.md` at all."""


def _delta_row_absent(repo: Path, feature_id: str) -> None:
    """A feature-delta exists, but carries NO row for the entering slice-01
    -- only an unrelated slice-99 row, itself (irrelevantly) `@infrastructure`."""
    _write_slice_plan(
        repo,
        feature_id,
        rows=[
            (
                "slice-99",
                "an unrelated slice in the same feature",
                "planned",
                "@infrastructure",
                "unrelated",
            )
        ],
    )


def _delta_row_not_annotated_non_observable(repo: Path, feature_id: str) -> None:
    """A feature-delta exists WITH a slice-01 row, but its Annotation cell is
    empty -- the row itself says "observable", regardless of any stray claim
    elsewhere."""
    _write_slice_plan(
        repo,
        feature_id,
        rows=[
            (
                "slice-01",
                "as a user I get the observable feature behaviour",
                "planned",
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
            _delta_row_not_annotated_non_observable,
            id="row-present-but-annotated-observable",
        ),
    ],
)
def test_exempt_status_is_never_granted_without_the_trusted_slice_plan_row(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    delta_writer,
) -> None:
    """constraint (b): the exemption predicate must read the SAME
    feature-delta.md Slice-Plan row the entry gate + DISTILL's own
    charter-scaffold tool already trust -- never a wrong/missing/absent
    source. Every case here must fail CLOSED to "observable" (still refused
    `ExamineVerdictMissing`), never fail OPEN to a false exemption.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id = "fix-nonobs-defer-neg-failclosed"
    delta_writer(repo, feature_id)
    _write_charter(repo, feature_id)
    regression_rel = (
        "tests/bugs/fixture/test_fix_nonobs_defer_neg_failclosed_slice_01.py"
    )
    _write_regression_test(repo, feature_id, "slice-01", regression_rel, passing=True)

    exit_code, event = _run_commit(repo, feature_id, "slice-01", regression_rel, capsys)

    assert exit_code == 2 and event.get("event") == "ExamineVerdictMissing", (
        "a slice must NEVER be granted the exemption except through the "
        "SAME trusted Slice-Plan row source the entry gate + DISTILL's "
        "charter-scaffold tool already read -- an absent/wrong/malformed "
        "feature-delta, or a row that is not annotated non-observable, must "
        f"fail CLOSED to 'observable'. observed exit_code={exit_code!r} "
        f"event={event!r}"
    )
