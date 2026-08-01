"""Regression (feature-delta ``fix-shipped-regression-file-backfill``, gap
#1 -- the ``@prefactoring`` half): ``des commit-slice`` for a NEW entering
slice must not be permanently blocked by an EARLIER shipped
``@prefactoring`` slice that legitimately never had a regression file.

RCA (confirmed, both code locations exist on this branch): the
``@prefactoring``/``@infrastructure`` AT-exemption already exists at the
EARLIER E1 (AT-completeness) gate via ``_is_at_exempt_lane``
(``verify_slice_commit_completeness.py:478-497``, reads the feature-delta's
Slice Plan Annotation column) -- but it is NEVER consulted by
``_shipped_and_entering_regression_files``
(``verify_slice_commit_completeness.py:793-848``), the resolver the LATER
E2 regression-gate leg uses to re-verify every already-SHIPPED slice's
regression file when a NEW slice commits. That resolver tries (1) the
slice's own STORED ``SliceCommitVerified.regression_test_file`` declaration,
then (2) a naming-convention glob -- and when a ``@prefactoring`` slice
genuinely has NEITHER (by design: it is a behavior-preserving
restructuring, not new-behavior work), both miss. ``_run_regression_gate_
shipped_and_entering`` (:851-921) then treats the slice as ``unresolved``
and degrades the ENTIRE commit -- including the perfectly legitimate new
entering slice -- to ``SliceCommitIndeterminate`` (reason
``shipped_regression_file_unresolvable``), even though the ``@prefactoring``
slice was never supposed to own a regression file at all.

Charter: docs/product/expectations/fix-shipped-regression-file-backfill/
a-developer-unblocks-commit-slice-past-an-earlier-shipped-slices-
regression-gap.md (Fixture B -- the prefactoring half).

THE FIX (crafter's job, NOT implemented by this AT -- test-authoring only,
zero ``src/`` edits): ``_shipped_and_entering_regression_files`` gains an
``_is_at_exempt_lane`` check for each SHIPPED slice, run BEFORE the
stored-declaration/glob resolution -- an exempt shipped slice is skipped
entirely: never added to ``resolved``, never counted as ``unresolved``. The
final ``SliceCommitVerified`` JSON verdict gains a NEW field
``"prefactoring_exempt_shipped_slices"``: a list of ``{"slice_id": ...,
"reason": ...}`` objects naming every shipped slice skipped this way -- the
machine-readable, never-silent observable this AT asserts on.

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process): the REAL
``des.cli.commit_slice.main()`` CLI driver, in-process with ``capsys`` --
verbatim shape reused from
``tests/bugs/des/test_commit_slice_reverify_uses_stored_regression_file.py``
(this file's primary precedent).

GIT SAFETY: every git call below targets the DISPOSABLE ``tmp_path`` fixture
only (``cwd``/``--repo`` always the scratch fixture, never the real project
repo). No git WRITE ever touches this repository.

THIS FILE IS TEST-ONLY. No production code is touched by this authoring
pass. A crafter fixes ``_shipped_and_entering_regression_files`` against
this test; this test must NEVER be weakened or skipped to reach GREEN.

RED-for-right-reason: scenario 1 below is a genuine ``AssertionError`` on
observed CLI behaviour (exit code / ledger content), NEVER an
``ImportError`` -- every name this file imports already exists on this
branch (``_is_at_exempt_lane``, ``_shipped_and_entering_regression_files``,
``commit_slice.main`` are all real, already-shipped production code; only
their COMPOSITION is missing the fix).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.commit_slice import main as commit_slice_main
from des.cli.verify_slice_commit_completeness import _GATE_INDETERMINATE_EXIT_CODE


# ---------------------------------------------------------------------------
# fixture builders (disposable git repos; every git write targets `root` only)
# ---------------------------------------------------------------------------


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _init_scratch_repo(root: Path) -> Path:
    """A minimal, disposable git repo -- baseline commit only."""
    fixture = root / "repo"
    fixture.mkdir(parents=True)
    (fixture / "README.md").write_text("# scratch fixture\n", encoding="utf-8")
    _git(fixture, "init", "-q")
    _git(fixture, "config", "user.email", "atdd@nwave.ai")
    _git(fixture, "config", "user.name", "atdd")
    _git(fixture, "add", "-A")
    _git(fixture, "commit", "-q", "-m", "chore: scratch fixture baseline")
    return fixture


def _write_trivial_regression_file(
    fixture: Path, rel_path: str, feature_id: str, slice_id: str, marker: int
) -> None:
    """A self-contained, tagged, trivially-passing pytest regression file."""
    target = fixture / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"# @feature-{feature_id}\n# @{slice_id}\n"
        f"def test_{slice_id.replace('-', '_')}_thing():\n"
        f"    assert {marker} + {marker} == {marker * 2}\n",
        encoding="utf-8",
    )


def _write_slice_plan(
    fixture: Path, feature_id: str, rows: list[tuple[str, str, str, str, str]]
) -> None:
    """A `[REF] Slice Plan` table -- `rows` is
    `(slice_id, value_statement, status, annotation, justification)`."""
    delta_dir = fixture / "docs" / "feature" / feature_id
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


# ---------------------------------------------------------------------------
# observables
# ---------------------------------------------------------------------------


def _run_commit_slice(
    repo: Path, argv_tail: list[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, str]:
    """Drive the REAL ``des commit-slice`` CLI (``main()``) in-process,
    returning ``(exit_code, combined_captured_output)``."""
    exit_code = commit_slice_main(["--repo", str(repo), *argv_tail])
    captured = capsys.readouterr()
    return exit_code, captured.out + "\n" + captured.err


def _diag(exit_code: int, output: str) -> str:
    return f"\nexit_code={exit_code!r}\noutput={output!r}"


def _last_json_event(output: str) -> dict[str, object]:
    json_lines = [line for line in output.splitlines() if line.strip().startswith("{")]
    assert json_lines, f"expected a JSON diagnostic line -- got none in {output!r}"
    payload = json.loads(json_lines[-1])
    assert isinstance(payload, dict)
    return payload


def _indeterminate_reasons(feature_id: str, repo: Path, slice_id: str) -> list[object]:
    """Every recorded ``SliceCommitIndeterminate`` ledger ``reason`` for ``slice_id``."""
    records = AtCompletionLedger(feature_id, repo).read_records(
        slice_id=slice_id, event_type="SliceCommitIndeterminate"
    )
    return [record.get("reason") for record in records]


# ===========================================================================
# Scenario 1 -- RED-today core: an earlier SHIPPED `@prefactoring` slice with
# NO regression file at all must never block a later entering slice.
# ===========================================================================


def test_entering_slice_commit_succeeds_past_a_prefactoring_shipped_slice_with_no_regression_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """slice-01 ships `@prefactoring` (a behavior-preserving restructuring,
    zero AT of any kind -- no `.feature` file, no regression file, by
    design). slice-02, a genuinely new observable slice, must still commit
    cleanly afterward, and its `SliceCommitVerified` verdict must NAME
    slice-01 as an exempt shipped slice via the new
    `prefactoring_exempt_shipped_slices` field.

    Active-RED at HEAD (empirically reasoned from the confirmed RCA):
    slice-02's commit degrades to `SliceCommitIndeterminate` (reason
    `shipped_regression_file_unresolvable`) because
    `_shipped_and_entering_regression_files` never consults
    `_is_at_exempt_lane` -- it tries slice-01's stored declaration (none,
    `@prefactoring` never declared one) then the naming-convention glob
    (zero matches, none exists), and degrades LOUD.
    """
    fixture = _init_scratch_repo(tmp_path)
    feature_id = "fix-shipped-regression-gap-prefactoring"
    _write_slice_plan(
        fixture,
        feature_id,
        rows=[
            (
                "slice-01",
                "as an architect I can trust the base is clean before slice-02 lands",
                "planned",
                "@prefactoring",
                "Behavior-preserving restructuring, no regression file by design",
            ),
            (
                "slice-02",
                "as a user I get the new observable behaviour",
                "planned",
                "",
                "",
            ),
        ],
    )

    # slice-01: @prefactoring, ships with ZERO AT of any kind (no --at-kind,
    # no --regression-test-file -- the default gherkin path, short-circuited
    # by the exempt-lane carve-out already proven in
    # test_prefactoring_slice_examine_exempt_not_deferred.py).
    exit_code_1, output_1 = _run_commit_slice(
        fixture,
        [
            "--all",
            "--feature-id",
            feature_id,
            "--slice-id",
            "slice-01",
            "--message",
            "refactor(slice): slice-01 is a prefactoring precondition, no AT",
        ],
        capsys,
    )
    assert exit_code_1 == 0, (
        "reproduction precondition: an @prefactoring slice with zero AT "
        "must ship cleanly on its own." + _diag(exit_code_1, output_1)
    )
    assert "slice-01" in AtCompletionLedger(feature_id, fixture).verified_slices(), (
        "reproduction precondition: slice-01 must earn a SliceCommitVerified "
        "ledger record." + _diag(exit_code_1, output_1)
    )

    # slice-02: a genuinely new, independent, passing regression file.
    _write_trivial_regression_file(
        fixture,
        "tests/bugs/repro/test_slice_02_behaviour.py",
        feature_id,
        "slice-02",
        2,
    )
    exit_code_2, output_2 = _run_commit_slice(
        fixture,
        [
            "--all",
            "--feature-id",
            feature_id,
            "--slice-id",
            "slice-02",
            "--message",
            "feat(slice): slice-02 delivers the new observable behaviour",
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            "tests/bugs/repro/test_slice_02_behaviour.py",
        ],
        capsys,
    )

    assert exit_code_2 == 0, (
        "committing slice-02 must clear des commit-slice end-to-end -- an "
        "earlier @prefactoring shipped slice with NO regression file by "
        "design must be EXEMPTED from the shipped-regression-file "
        "re-check, never treated as an unresolved gap. At HEAD this "
        f"degrades to SliceCommitIndeterminate (exit "
        f"{_GATE_INDETERMINATE_EXIT_CODE}), reason "
        "'shipped_regression_file_unresolvable'." + _diag(exit_code_2, output_2)
    )
    verified_slices = AtCompletionLedger(feature_id, fixture).verified_slices()
    assert "slice-02" in verified_slices, (
        "slice-02 must earn a SliceCommitVerified ledger record -- observed "
        f"verified_slices={sorted(verified_slices)!r}." + _diag(exit_code_2, output_2)
    )
    reasons = _indeterminate_reasons(feature_id, fixture, "slice-02")
    assert "shipped_regression_file_unresolvable" not in reasons, (
        "slice-02 must NEVER mint a SliceCommitIndeterminate reasoning "
        "'shipped_regression_file_unresolvable' when slice-01 is a genuinely "
        f"exempt @prefactoring slice -- observed ledger reasons={reasons!r}."
        + _diag(exit_code_2, output_2)
    )

    verified_event = _last_json_event(output_2)
    assert verified_event.get("event") == "SliceCommitVerified", (
        f"expected the final event to be SliceCommitVerified -- got "
        f"{verified_event!r}." + _diag(exit_code_2, output_2)
    )
    exempt_list = verified_event.get("prefactoring_exempt_shipped_slices")
    assert isinstance(exempt_list, list) and exempt_list, (
        "the SliceCommitVerified verdict must carry a NEW, non-empty "
        "'prefactoring_exempt_shipped_slices' field naming every shipped "
        "slice that was skipped via the @prefactoring exemption -- observed "
        f"verified_event={verified_event!r}." + _diag(exit_code_2, output_2)
    )
    exempt_slice_ids = {
        entry.get("slice_id") for entry in exempt_list if isinstance(entry, dict)
    }
    assert "slice-01" in exempt_slice_ids, (
        f"'prefactoring_exempt_shipped_slices' must name slice-01 specifically "
        f"-- observed exempt_list={exempt_list!r}." + _diag(exit_code_2, output_2)
    )
    exempt_entry = next(
        entry
        for entry in exempt_list
        if isinstance(entry, dict) and entry.get("slice_id") == "slice-01"
    )
    assert isinstance(exempt_entry.get("reason"), str) and exempt_entry["reason"], (
        "each prefactoring_exempt_shipped_slices entry must carry a non-empty "
        f"human 'reason' -- observed entry={exempt_entry!r}."
        + _diag(exit_code_2, output_2)
    )


# ===========================================================================
# Scenario 7 -- negative overcorrection guard: a shipped slice with NEITHER
# a @prefactoring exemption NOR any backfill record NOR a resolvable file
# (stored or convention) must STILL degrade LOUD -- the fix must never
# generalize into "any unresolved shipped slice is silently waved through".
# ===========================================================================


@pytest.mark.negative_at
def test_genuinely_unresolvable_non_exempt_shipped_slice_still_degrades_loud(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """slice-01 is recorded as SHIPPED via a hand-injected `SliceCommitVerified`
    ledger record simulating a HISTORICAL (pre-#59) record -- carrying NO
    `regression_test_file` field -- for a slice that owns NO annotation at
    all (fully observable, not `@prefactoring`/`@infrastructure`) and for
    which NO file anywhere on the tree matches the naming convention, and
    for which NO backfill record has ever been recorded. slice-02's commit
    must STILL degrade LOUD `SliceCommitIndeterminate` (reason
    `shipped_regression_file_unresolvable`) -- the @prefactoring exemption
    and the historical-backfill mechanism (this feature's OTHER fix) must
    never generalize into unblocking a slice that has none of the three
    legitimate resolution paths (stored declaration, backfill record,
    convention match).

    This pins the SAME invariant
    `test_commit_slice_reverify_uses_stored_regression_file.py::
    test_slice_two_commit_still_degrades_when_shipped_file_is_genuinely_
    deleted` already pins for the convention-match-then-deleted case; this
    variant covers the DISTINCT case of a file that never existed anywhere
    resolvable in the first place (no prior convention match to delete).
    """
    fixture = _init_scratch_repo(tmp_path)
    feature_id = "fix-shipped-regression-gap-neg-unresolvable"
    _write_slice_plan(
        fixture,
        feature_id,
        rows=[
            (
                "slice-01",
                "as a user I got some earlier observable behaviour",
                "shipped",
                "",
                "",
            ),
            (
                "slice-02",
                "as a user I get the new observable behaviour",
                "planned",
                "",
                "",
            ),
        ],
    )
    historical_sha = _git(fixture, "rev-parse", "HEAD").strip()
    # Hand-inject a historical SliceCommitVerified record for slice-01 --
    # NO regression_test_file field (simulates a pre-#59 record), and
    # slice-01 owns NO file anywhere matching the naming convention on this
    # tree (never written at all).
    AtCompletionLedger(feature_id, fixture).append_gate_event(
        "SliceCommitVerified", "slice-01", commit_sha=historical_sha
    )
    assert "slice-01" in AtCompletionLedger(feature_id, fixture).verified_slices(), (
        "test-setup precondition: the hand-injected historical record must "
        "register slice-01 as shipped."
    )

    _write_trivial_regression_file(
        fixture,
        "tests/bugs/repro/test_slice_02_behaviour_unresolvable.py",
        feature_id,
        "slice-02",
        3,
    )
    exit_code_2, output_2 = _run_commit_slice(
        fixture,
        [
            "--all",
            "--feature-id",
            feature_id,
            "--slice-id",
            "slice-02",
            "--message",
            "feat(slice): slice-02 lands after slice-01's genuine gap",
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            "tests/bugs/repro/test_slice_02_behaviour_unresolvable.py",
        ],
        capsys,
    )

    assert exit_code_2 != 0, (
        "a shipped slice with NO stored declaration, NO backfill record, NO "
        "convention match, and NO @prefactoring/@infrastructure exemption "
        "must STILL degrade LOUD (never a clean exit 0) -- never silently "
        f"unblocked. observed exit_code={exit_code_2!r}." + _diag(exit_code_2, output_2)
    )
    verified_slices = AtCompletionLedger(feature_id, fixture).verified_slices()
    assert "slice-02" not in verified_slices, (
        "slice-02 must never earn a SliceCommitVerified record while "
        f"slice-01's gap is genuinely unresolvable -- observed "
        f"verified_slices={sorted(verified_slices)!r}." + _diag(exit_code_2, output_2)
    )
    reasons = _indeterminate_reasons(feature_id, fixture, "slice-02")
    assert "shipped_regression_file_unresolvable" in reasons, (
        "a genuinely unresolvable shipped slice must degrade LOUD naming "
        f"'shipped_regression_file_unresolvable' -- observed ledger "
        f"reasons={reasons!r}." + _diag(exit_code_2, output_2)
    )
