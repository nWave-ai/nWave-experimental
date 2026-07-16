"""Acceptance test (pytest-regression, active-RED): `des commit-slice`
appends a `FeatureEndPending` ledger marker + a LOUD stdout notice when the
LAST declared Slice-Plan slice of a feature ships.

Feature: deliver-finalize-unmissable, slice-01 (FIX-A).
Charter: docs/feature/deliver-finalize-unmissable/feature-delta.md
  `## Wave: DESIGN / [REF] Architecture & Contract`.

Root cause this AT pins the fix for: "done" is a CLAIM decoupled from the
mechanical `FeatureEnd` attestation -- a per-slice `commit-slice` succeeds
individually and creates a done-illusion. The fix (purely additive, byte-
unchanged commit itself): after a successful slice commit, IF every declared
Slice-Plan row for the feature is now shipped (this was the LAST slice),
`commit-slice` APPENDS a durable `FeatureEndPending` record to the
AT-completion ledger AND emits a LOUD self-explaining stdout notice naming
`des feature-end run` as the HOW -- idempotent (at most once per feature),
degrade-LOUD without ever crashing the commit.

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process default):
the REAL `des.cli.commit_slice.main()` CLI driver, captured via `capsys` --
NOT a direct import of the (not-yet-existing) marker-append helper. Real seams
exercised: `AtCompletionLedger.append_gate_event` (the ledger-append seam, per
the Reuse Analysis) and the `[REF] Slice Plan` table `des commit-slice`
already reads (declared-slices / shipped-slices).

Fixture reuse (per dispatch instruction -- do NOT hand-roll a new harness):
  * `_init_repo` -- the exact pytest-collectible git work-tree shape from the
    proven GREEN precedent `tests/des/integration/test_commit_slice.py`.
  * The `@prefactoring` AT-EXEMPT lane (`LANE_PROFILES["prefactoring"]`,
    `AtRequirement.EXEMPT`) -- the proven GREEN precedent
    `tests/bugs/des/test_commit_slice_writes_verified_record.py` -- the
    cheapest reliable fixture that makes a real `--feature-id` commit-slice
    run land + verify cleanly (E1 trivially clears, E2 short-circuits on the
    EXEMPT lane) without materializing a genuine `.feature` scenario.

Real seams to read (do NOT invent a new ledger format or Slice-Plan parser):
  * src/des/adapters/driven/logging/at_completion_ledger.py
    (`AtCompletionLedger` + `append_gate_event`, `read_records`)
  * src/des/cli/verify_deliver_integrity.py
    (`_declared_slice_plan_slice_ids`, `_shipped_slices` -- the last-slice
    detection readers the crafter reuses per the Reuse Analysis)
  * src/des/cli/commit_slice.py (`main(argv)` -- the entry point under test)
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.commit_slice import main as commit_slice_main
from des.cli.verify_slice_commit_completeness import canonical_regression_test_path


_FEATURE_END_PENDING_EVENT = "FeatureEndPending"
_FEATURE_END_RUN_HOW = "des feature-end run"


# ---------------------------------------------------------------------------
# Shared fixture builders (mirrors tests/bugs/des/test_commit_slice_writes_
# verified_record.py verbatim -- proven GREEN shape for a real --feature-id
# commit-slice run).
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
    precedent's `_init_repo` verbatim)."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    # Pin the hooks dir to the repo's own .git/hooks so a global/user-level
    # core.hooksPath in the environment cannot leak into the hook-count tests.
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


def _last_json_event(stdout: str) -> dict:
    json_lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    assert json_lines, f"expected a JSON payload line on stdout, got: {stdout!r}"
    return json.loads(json_lines[-1])


def _write_two_slice_feature_delta(repo: Path, feature_id: str) -> None:
    """A minimal two-slice `[REF] Slice Plan` -- BOTH rows `@prefactoring`
    (AT-EXEMPT), the cheapest reliable shape a real `--feature-id` commit-
    slice run clears through end to end (E1 trivially clears -- nothing
    declared to be missing; E2 short-circuits on the EXEMPT lane)."""
    delta_dir = repo / "docs" / "feature" / feature_id
    delta_dir.mkdir(parents=True, exist_ok=True)
    (delta_dir / "feature-delta.md").write_text(
        f"# Feature Delta: {feature_id}\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
        "| slice-01 | a behavior-preserving refactor introduces the first "
        "seam | pending | @prefactoring | a green-to-green prefactoring |\n"
        "| slice-02 | a behavior-preserving refactor introduces the second "
        "seam | pending | @prefactoring | a green-to-green prefactoring |\n",
        encoding="utf-8",
    )


def _author_production_change(repo: Path, rel_path: str, content: str) -> None:
    target = repo / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _commit_slice(
    repo: Path,
    feature_id: str,
    slice_id: str,
    message: str,
    rel_path: str,
) -> int:
    """Author a production-only change and drive the REAL commit-slice CLI."""
    _author_production_change(
        repo,
        rel_path,
        f"def {slice_id.replace('-', '_')}_helper() -> str:\n"
        f"    return 'behaviour for {slice_id}'\n",
    )
    return commit_slice_main(
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
        ]
    )


def _feature_end_pending_records(repo: Path, feature_id: str) -> list[dict]:
    ledger = AtCompletionLedger(feature_id=feature_id, project_root=repo)
    return [
        record
        for record in ledger.read_records()
        if record.get("event") == _FEATURE_END_PENDING_EVENT
    ]


# ===========================================================================
# Scenario 1 -- LAST-slice commit: marker appended + loud notice emitted.
# ===========================================================================


def test_last_slice_commit_appends_feature_end_pending_and_emits_loud_notice(
    tmp_path: Path, capsys
) -> None:
    """Committing the LAST declared Slice-Plan slice of a 2-slice feature
    (both rows now shipped) appends a `FeatureEndPending` ledger record AND
    emits a LOUD self-explaining stdout notice naming `des feature-end run`.

    RED for the right reason: `commit-slice.main()` today never inspects the
    Slice Plan for last-slice-shipped detection and never appends a
    `FeatureEndPending` record -- a semantic `AssertionError` on the absent
    record/notice, not a crash or collection error.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id = "fixture-deliver-finalize-last-slice"
    _write_two_slice_feature_delta(repo, feature_id)

    exit_1 = _commit_slice(
        repo,
        feature_id,
        "slice-01",
        "refactor(slice): first slice introduces a behavior-preserving seam",
        "src/app/slice_01.py",
    )
    assert exit_1 == 0, "the predecessor slice-01 commit must land cleanly"
    capsys.readouterr()  # drain slice-01's own stdout before the assertion

    exit_2 = _commit_slice(
        repo,
        feature_id,
        "slice-02",
        "refactor(slice): second slice introduces a behavior-preserving seam",
        "src/app/slice_02.py",
    )
    captured = capsys.readouterr()

    assert exit_2 == 0, (
        "committing the LAST declared slice must still land the commit "
        "cleanly (the marker append is additive, never blocking)"
    )

    pending_records = _feature_end_pending_records(repo, feature_id)
    assert len(pending_records) == 1, (
        "expected exactly ONE FeatureEndPending ledger record after the last "
        "declared Slice-Plan slice (slice-02) shipped -- every declared row "
        "(slice-01, slice-02) is now shipped, so commit-slice must append the "
        f"durable marker. Found {len(pending_records)} records: "
        f"{pending_records!r}"
    )
    assert pending_records[0].get("feature_id") == feature_id

    assert _FEATURE_END_RUN_HOW in captured.out, (
        "expected a LOUD self-explaining stdout notice naming "
        f"{_FEATURE_END_RUN_HOW!r} as the HOW after the last slice shipped -- "
        f"got stdout: {captured.out!r}"
    )


# ===========================================================================
# Scenario 2 -- NON-last slice commit: NO marker appended (NEGATIVE).
# ===========================================================================


def test_non_last_slice_does_not_append_feature_end_pending(
    tmp_path: Path, capsys
) -> None:
    """Committing only slice-01 of a 2-slice feature (slice-02 still pending)
    must NOT append a `FeatureEndPending` record -- the feature is not
    finished yet."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id = "fixture-deliver-finalize-non-last-slice"
    _write_two_slice_feature_delta(repo, feature_id)

    exit_1 = _commit_slice(
        repo,
        feature_id,
        "slice-01",
        "refactor(slice): only the first slice ships in this scenario",
        "src/app/slice_01.py",
    )
    captured = capsys.readouterr()

    assert exit_1 == 0

    pending_records = _feature_end_pending_records(repo, feature_id)
    assert pending_records == [], (
        "slice-02 is still declared and NOT shipped -- committing only "
        "slice-01 must NEVER append a FeatureEndPending record. Found: "
        f"{pending_records!r}"
    )
    assert _FEATURE_END_RUN_HOW not in captured.out, (
        "the loud last-slice notice must not fire when the feature is not "
        f"yet fully shipped -- got stdout: {captured.out!r}"
    )


# ===========================================================================
# Scenario 3 -- idempotent: a pre-existing marker is never duplicated.
# ===========================================================================


def test_idempotent_last_slice_commit_never_duplicates_feature_end_pending(
    tmp_path: Path, capsys
) -> None:
    """A `FeatureEndPending` record already present for the feature (e.g. a
    prior last-slice commit, or a `FeatureEnd` that already cleared it) means
    the last-slice commit must NOT append a second one -- idempotent, at most
    once per feature."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id = "fixture-deliver-finalize-idempotent"
    _write_two_slice_feature_delta(repo, feature_id)

    # Pre-seed the marker via the SAME ledger-append seam the Reuse Analysis
    # names (`AtCompletionLedger.append_gate_event`) -- mirrors an already-
    # pending finalize obligation for this feature.
    ledger = AtCompletionLedger(feature_id=feature_id, project_root=repo)
    ledger.append_gate_event(_FEATURE_END_PENDING_EVENT, "", feature_id=feature_id)
    assert len(_feature_end_pending_records(repo, feature_id)) == 1

    exit_1 = _commit_slice(
        repo,
        feature_id,
        "slice-01",
        "refactor(slice): first slice ships after the marker pre-exists",
        "src/app/slice_01.py",
    )
    capsys.readouterr()
    assert exit_1 == 0

    exit_2 = _commit_slice(
        repo,
        feature_id,
        "slice-02",
        "refactor(slice): second (last) slice ships after the marker pre-exists",
        "src/app/slice_02.py",
    )
    capsys.readouterr()
    assert exit_2 == 0

    pending_records = _feature_end_pending_records(repo, feature_id)
    assert len(pending_records) == 1, (
        "a FeatureEndPending record already existed for this feature before "
        "the last slice shipped -- the last-slice commit must NOT append a "
        f"second one (idempotent, at most once per feature). Found "
        f"{len(pending_records)} records: {pending_records!r}"
    )


# ===========================================================================
# Scenario 4 -- degrade-LOUD, never block: absent Slice Plan.
# ===========================================================================


def test_absent_slice_plan_commit_still_succeeds_without_crash(
    tmp_path: Path, capsys
) -> None:
    """When the feature has NO feature-delta.md (Slice Plan unreadable /
    absent), the slice commit must still SUCCEED (exit unchanged) and stdout
    must still carry the well-formed `SliceCommitted` event -- never an
    unhandled traceback. The last-slice marker is best-effort-loud only; it
    must never crash or block the commit."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id = "fixture-deliver-finalize-no-slice-plan"
    # Deliberately NOT calling _write_two_slice_feature_delta -- no
    # docs/feature/{feature_id}/feature-delta.md exists at all: the
    # slice-plan-absent condition this scenario exercises MUST stay, so
    # Step 7's degrade-LOUD marker path is what runs.
    #
    # STALE-FIXTURE RECONCILIATION (2026-07-15): seed ONE convention-matching
    # pytest-regression file so the commit-slice E2 pre-flight routes to the
    # pytest-regression path instead of the gherkin default. WHY this is
    # required for the test to reach its OWN intent: with ZERO .feature files
    # AND zero convention-matching regression files, commit-slice Step 1.5's
    # `_infer_pytest_regression_at_kind` (RC1 Fix B) conservatively KEEPS the
    # gherkin default -> E2 dispatches `run_contract_gate --feature-id`, which
    # trips the load-bearing M-1 non-vacuity floor (a feature with no .feature
    # file "would pass vacuously" -> exit 2) BEFORE the commit ever lands, so
    # Step 7 (the FeatureEndPending degrade-LOUD marker, `commit_slice.py`)
    # never runs -- Step 7 executes only AFTER a successful commit. The M-1
    # floor is a 7-week-predating anti-gaming invariant and is NOT weakened
    # here; the fix is fixture-side only: ONE positive-evidence regression file
    # routes E2 to the pytest-regression path (no gherkin, no M-1 floor), the
    # commit lands, and Step 7 genuinely exercises the degrade-LOUD path on the
    # STILL-absent feature-delta.md (the actual behaviour this test proves).
    # Path derived via the production `canonical_regression_test_path` (never
    # hand-matching the private glob) -- the same anti-drift discipline the
    # gate's own naming convention mandates.
    regression_rel = canonical_regression_test_path(feature_id, "slice-01")
    _author_production_change(
        repo,
        regression_rel,
        "def test_no_slice_plan_regression_behaviour() -> None:\n    assert True\n",
    )

    _author_production_change(
        repo, "src/app/no_plan.py", "def helper() -> str:\n    return 'no plan'\n"
    )
    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--all",
            "--feature-id",
            feature_id,
            "--slice-id",
            "slice-01",
            "--message",
            "feat(slice): behaviour committed with no Slice Plan on disk",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0, (
        "an absent/unreadable Slice-Plan must NEVER block or crash the "
        f"commit -- the last-slice marker is best-effort-loud only. Got "
        f"exit_code={exit_code!r}, stdout={captured.out!r}, "
        f"stderr={captured.err!r}"
    )

    event = _last_json_event(captured.out)
    assert event.get("event") == "SliceCommitted", (
        "expected the commit itself to still succeed (SliceCommitted) even "
        f"though the Slice-Plan is absent; got event={event!r}"
    )
