"""Regression (fix-at-review-verdict-charter-form): `des record-at-review-
verdict` refuses EVERY `atdd_pure` bugfix-lane slice, because its feature/
slice resolution (`at_review_verdict.py::_verify_feature_slice_exists`,
~lines 434-475) recognizes EXACTLY ONE evidence form -- a
`docs/feature/{feature_id}/feature-delta.md` carrying `slice_id` as a row in
its `[REF] Slice Plan` table.

DEFECT (measured, reproduced by the orchestrator -- see dispatch RCA): a
`/nw-bugfix` lane on the `atdd_pure` path NEVER produces a feature-delta; it
produces an expectation charter under
`docs/product/expectations/{feature_id}/*.md` (`des charter-scaffold`, filled
by a fresh `nw-product-owner` dispatch). `_verify_feature_slice_exists` does
not consult that directory at all, so a real bugfix slice with a genuine,
filled expectation charter is refused exactly like an imaginary feature that
was never designed -- `ATReviewVerdictRefused` / `unresolvable-feature-slice`,
exit 2, NOTHING appended to the ledger. The whole bugfix class is
structurally unreachable through this CLI.

THE FIX (crafter's job, NOT implemented here -- test-authoring only, zero
`src/` edits): extend `_verify_feature_slice_exists` so an expectation
charter is ALSO a valid resolution source -- reusing the existing predicate
`_has_expectation_charter` (`src/des/cli/verify_readiness_pre_dispatch.py:
1047`, already the bugfix lane's evidence-floor check: `charter_dir.is_dir()
and any(charter_dir.glob("*.md"))`) rather than inventing a third parallel
shape (a sibling already exists at `commit_slice.py:1457`,
`_charter_dir_to_stage`). The feature-delta branch must stay byte-for-byte
behaviourally unchanged.

Driving surface (Mandate 13 driving-port-only, Layer 3 in-process default):
the REAL `des.cli.at_review_verdict.main(argv)` CLI EDGE, driven in-process
via `tests.common.in_process_cli.run_cli_in_process`, under an isolated
`tmp_path` repo -- never the real `.nwave/telemetry/`. `--at-kind
pytest-regression` is used throughout so AT derivation depends only on a
small `.py` fixture this module writes, never on `.feature` files.

RED-for-right-reason: scenarios 1 (both verdict values) are active-RED today
-- the CLI runs to completion, refuses with `unresolvable-feature-slice`
(exit 2), and writes NOTHING to the ledger, even though a real, filled
expectation charter is present. Scenarios 2-6 pin behaviour that is already
correct today (the imaginary-feature refusal, the empty-charter-dir
non-acceptance, the feature-delta form untouched) and must stay GREEN once
the fix lands.

ROUND 2 (Vera's real-surface EXAMINE, bounded re-loop after the slice-01 fix
landed): the fix above shipped using the bare `has_expectation_charter`
presence check (`repo_path_resolver.has_expectation_charter` -- charter
directory exists AND has >=1 `*.md`), which is GREEN on scenario 1 but opens
two new holes Vera caught driving the REAL CLI:

FLAG 1 -- the door has no lock on the slice axis: with a charter present for
the feature, ANY `--slice-id` is accepted, even one no charter maps at all.
The feature-delta form already refuses a `slice_id` absent from its Slice
Plan; the charter form must close the SAME hole via
`des.domain.expectation_charter_mapping.resolve_slice_charter(repo_root,
feature_id, slice_id)` -- `ARMED` only when `slice_id` is one of the
charter's comma-separated `Spec rows:` tokens, `UNMAPPED` when charters exist
but none maps this slice.

FLAG 2 -- an unfilled scaffold passes for a charter: a file `des
charter-scaffold` produced and nobody ever filled in (scaffold placeholder
tokens like `<start recipe: how to run the system from a clean state, seed
state>` still verbatim) satisfies the bare presence check and arms a
verdict. `des.cli.verify_charter_filled.charter_missing_sections(content) ->
list[str]` (pure) already computes FILLED-ness; the fix must consult it (or
an equivalent) before treating a charter as adopted practice.

Canonical-form regression guard: `resolve_slice_charter`'s own
`_classify_spec_rows_value` already recognizes the two first-class
feature-level `Spec rows:` tokens (`bug-observable`, `brownfield-discovery`)
-- the tokens `des charter-scaffold --seed-mode bug-observable/
brownfield-discovery` stamps, which by construction map NO specific slice.
But its ARMED-matching loop only checks `slice_id in mapped_tokens`, which
never matches a concrete `slice_id` against a feature-level token verbatim --
so routing `_verify_feature_slice_exists` through `resolve_slice_charter`
AS-IS would silently break the canonical bugfix lane (a `bug-observable`
charter must arm ANY `--slice-id` the operator passes). The crafter must
extend that domain to special-case feature-level tokens as matching any
slice -- the AT below pins the OBSERVABLE CLI behaviour that must survive,
not the enum's internal shape.

(The third flag Vera raised -- two identical invocations write two ledger
records -- is PRE-EXISTING, append-only-by-design behaviour (DD-1), identical
on the feature-delta form. Named here as a disposed residual, NOT pinned.)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.at_review_verdict import main as record_at_review_verdict_main
from des.cli.charter_scaffold import main as charter_scaffold_main
from tests.common.in_process_cli import run_cli_in_process


_REVIEWER_AGENT_ID = "nw-acceptance-designer-reviewer"


def _run_record_at_review_verdict(
    repo_root: Path, argv: list[str]
) -> tuple[int, str, str]:
    """Drive the REAL `des record-at-review-verdict` CLI EDGE in-process."""
    return run_cli_in_process(argv, cwd=repo_root, main=record_at_review_verdict_main)


def _base_argv(
    *,
    feature_id: str,
    slice_id: str,
    repo_root: Path,
    regression_test_file_rel: str,
    verdict: str = "APPROVED",
) -> list[str]:
    return [
        "--feature-id",
        feature_id,
        "--slice-id",
        slice_id,
        "--verdict",
        verdict,
        "--reviewer-agent-id",
        _REVIEWER_AGENT_ID,
        "--repo-root",
        str(repo_root),
        "--at-kind",
        "pytest-regression",
        "--regression-test-file",
        regression_test_file_rel,
    ]


def _read_verdict_records(
    repo_root: Path, feature_id: str, slice_id: str
) -> list[dict[str, object]]:
    ledger_path = (
        repo_root / ".nwave" / "telemetry" / "atdd-pure" / f"{feature_id}.jsonl"
    )
    if not ledger_path.exists():
        return []
    return AtCompletionLedger(feature_id, repo_root).read_records(
        event_type="ATReviewVerdict", slice_id=slice_id
    )


def _write_pytest_regression_fixture(path: Path) -> None:
    """A controlled, single-AT pytest-regression fixture -- one `test_*`
    function so `--at-kind pytest-regression` derives `at_ids == ["AT-1"]`
    with no predecessor-attested-total complications (fresh feature, no
    prior ledger entries to subtract)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "def test_charter_only_bugfix_slice_regression_holds():\n    assert True\n",
        encoding="utf-8",
    )


def _write_filled_charter(
    repo_root: Path,
    feature_id: str,
    *,
    spec_rows_value: str,
    filename: str = "some-intent.md",
) -> Path:
    """A genuine, FULLY-FILLED expectation-charter file under
    `docs/product/expectations/{feature_id}/` -- the atdd_pure bugfix lane's
    OWN evidence artifact (`des charter-scaffold` + a filled `nw-product-
    owner` pass), never a feature-delta.

    Mirrors the canonical template's ID line (`nWave/templates/expectation-
    charter.md`, "Example (filled)") -- a real `Spec rows:` field
    (`spec_rows_value`, either a comma-separated `slice-NN` list or one of
    the two first-class feature-level tokens `bug-observable` /
    `brownfield-discovery`), a non-placeholder `## Preconditions` body, and
    a `## Expected observations (oracle)` body carrying >=1 `Negative:`
    line -- so it satisfies BOTH `des.cli.verify_charter_filled.
    charter_missing_sections` (FILLED) and `des.domain.
    expectation_charter_mapping.resolve_slice_charter`'s `Spec rows:` parse
    (round-2 FLAG 1/FLAG 2 fixes), not merely `has_expectation_charter`'s
    bare presence check (the round-1 fix).

    Returns the written charter path.
    """
    charter_dir = repo_root / "docs" / "product" / "expectations" / feature_id
    charter_dir.mkdir(parents=True, exist_ok=True)
    charter_path = charter_dir / filename
    charter_path.write_text(
        "# Fix at-review-verdict for a charter-only bugfix slice\n"
        f"ID: EXP-{feature_id}-1 · Spec rows: {spec_rows_value} · "
        "Persona: the nWave maintainer running an atdd_pure bugfix\n\n"
        "## Intent\n"
        "Fix `des record-at-review-verdict` so a charter-only bugfix slice "
        "can record a verdict.\n\n"
        "## Preconditions\n"
        "Run `des record-at-review-verdict` against a repo with an "
        "expectation charter and no feature-delta.\n\n"
        "## Charter\n"
        "Drive the CLI to verify the verdict records for a charter-only "
        "bugfix slice.\n\n"
        "## Expected observations (oracle)\n"
        "- The verdict records successfully (exit 0, one ledger record).\n"
        "- Negative: an imaginary feature/slice with no evidence at all "
        "must still be refused.\n\n"
        "## Session log (append-only)\n"
        "| date | examiner | verdict | observations |\n"
        "|------|----------|---------|--------------|\n",
        encoding="utf-8",
    )
    return charter_path


def _write_empty_expectation_charter_dir(repo_root: Path, feature_id: str) -> None:
    """The charter directory exists but holds ZERO `*.md` files -- must NOT
    read as an adopted charter (mirrors `_has_expectation_charter`'s own
    `any(charter_dir.glob("*.md"))` check)."""
    charter_dir = repo_root / "docs" / "product" / "expectations" / feature_id
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "README.txt").write_text(
        "not a charter -- wrong extension\n", encoding="utf-8"
    )


def _write_feature_delta_with_slice_row(
    repo_root: Path, feature_id: str, present_slice_id: str
) -> None:
    """A minimal, realistic feature-delta.md staging a genuine Slice Plan
    row for `present_slice_id` -- mirrors the canonical 5-column shape
    `carpaccio_format` / sibling regression tests use."""
    feature_delta_path = (
        repo_root / "docs" / "feature" / feature_id / "feature-delta.md"
    )
    feature_delta_path.parent.mkdir(parents=True, exist_ok=True)
    feature_delta_path.write_text(
        f"# Feature Delta: {feature_id}\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|---|---|---|---|---|\n"
        f"| {present_slice_id} | some real value statement | done | | |\n",
        encoding="utf-8",
    )


def _refusal_payload(stdout: str) -> dict[str, object]:
    stdout_lines = [line for line in stdout.splitlines() if line.strip()]
    assert stdout_lines, (
        f"expected a JSON diagnostic line on stdout, got EMPTY: {stdout!r}"
    )
    return json.loads(stdout_lines[-1])


def _assert_names_actionable_charter_guidance(payload: dict[str, object]) -> None:
    """Shared self-explaining check (WHAT/WHY/HOW) for a charter-route
    refusal: `how` must be a non-empty, actionable string that mentions the
    charter route -- never a bare non-zero exit with no guidance."""
    how = payload.get("how")
    assert isinstance(how, str) and how.strip(), (
        f"the refusal must carry a non-empty, executable 'how' -- got payload={payload!r}"
    )
    assert payload.get("error"), (
        f"the refusal must carry a non-empty 'error' explaining WHAT/WHY "
        f"failed -- got payload={payload!r}"
    )
    assert "charter" in how.lower(), (
        "the 'how' must name the charter route (e.g. `des charter-scaffold` "
        f"/ `des verify-charter-filled`) -- got how={how!r}"
    )


# ===========================================================================
# 1. POSITIVE (the fix) -- a charter-only bugfix slice (no feature-delta,
#    real expectation charter) must record BOTH verdict values.
# ===========================================================================


@pytest.mark.parametrize("verdict", ["APPROVED", "NEEDS_REVISION"])
def test_expectation_charter_alone_lets_the_verdict_record(
    tmp_path: Path, verdict: str
) -> None:
    """A repo with NO `docs/feature/{feature_id}/feature-delta.md` but WITH a
    real, non-empty, FILLED `docs/product/expectations/{feature_id}/*.md`
    (mapped to the requested slice) must record the requested verdict --
    exit 0, exactly one `ATReviewVerdict` ledger record carrying `verdict`.

    Today: `_verify_feature_slice_exists` looks ONLY at feature-delta.md,
    finds none, and refuses (exit 2, `unresolvable-feature-slice`) even
    though a genuine expectation charter is present -- the whole atdd_pure
    bugfix class is structurally unreachable through this CLI.
    """
    repo = tmp_path / "repo"
    feature_id = "charter-only-bugfix-slice"
    slice_id = "slice-01"
    _write_filled_charter(repo, feature_id, spec_rows_value=slice_id)
    regression_rel = "tests/regression/test_charter_only_fixture.py"
    _write_pytest_regression_fixture(repo / regression_rel)

    exit_code, stdout, stderr = _run_record_at_review_verdict(
        repo,
        _base_argv(
            feature_id=feature_id,
            slice_id=slice_id,
            repo_root=repo,
            regression_test_file_rel=regression_rel,
            verdict=verdict,
        ),
    )

    assert exit_code == 0, (
        f"a charter-only bugfix slice ({verdict=}) with a real expectation "
        f"charter mapped to {slice_id!r} and NO feature-delta must record "
        f"successfully (exit 0) -- got exit_code={exit_code}, "
        f"stdout={stdout!r}, stderr={stderr!r}. `_verify_feature_slice_"
        "exists` refuses whenever feature-delta.md is absent, regardless of "
        "an expectation charter -- see this module's docstring for the fix "
        "direction."
    )

    records = _read_verdict_records(repo, feature_id, slice_id)
    assert len(records) == 1, (
        f"expected exactly one ATReviewVerdict record for {slice_id} -- got {records!r}"
    )
    record = records[0]
    assert record.get("verdict") == verdict, (
        f"expected the recorded verdict to be {verdict!r} -- got "
        f"{record.get('verdict')!r} (record={record!r})"
    )
    at_ids = record.get("at_ids")
    assert isinstance(at_ids, list) and len(at_ids) == 1, (
        f"expected exactly one net-new AT id from the single-test fixture -- "
        f"got at_ids={at_ids!r}"
    )


# ===========================================================================
# 2. NEGATIVE -- no lock removed: neither a feature-delta NOR an expectation
#    charter must STILL refuse, exactly as today.
# ===========================================================================


@pytest.mark.negative_at
def test_neither_feature_delta_nor_charter_still_refuses(tmp_path: Path) -> None:
    """A repo with NEITHER `docs/feature/{feature_id}/feature-delta.md` NOR
    `docs/product/expectations/{feature_id}/` must be refused exactly as
    today -- exit 2, `ATReviewVerdictRefused` / `unresolvable-feature-slice`,
    and NOTHING written to the ledger. The fix widens acceptance to a real
    charter; it must never accept an imaginary feature/slice with neither
    evidence form.
    """
    repo = tmp_path / "repo"
    feature_id = "ghost-no-delta-no-charter"
    slice_id = "slice-01"
    regression_rel = "tests/regression/test_ghost_fixture.py"
    _write_pytest_regression_fixture(repo / regression_rel)

    assert not (repo / "docs" / "feature" / feature_id).exists()
    assert not (repo / "docs" / "product" / "expectations" / feature_id).exists()

    exit_code, stdout, stderr = _run_record_at_review_verdict(
        repo,
        _base_argv(
            feature_id=feature_id,
            slice_id=slice_id,
            repo_root=repo,
            regression_test_file_rel=regression_rel,
        ),
    )

    assert exit_code == 2, (
        "an imaginary feature/slice with neither a feature-delta nor an "
        f"expectation charter must be refused (exit 2) -- got "
        f"exit_code={exit_code}, stdout={stdout!r}, stderr={stderr!r}"
    )
    payload = _refusal_payload(stdout)
    assert payload.get("event") == "ATReviewVerdictRefused"
    assert payload.get("reason") == "unresolvable-feature-slice"

    records = _read_verdict_records(repo, feature_id, slice_id)
    assert records == [], (
        "an imaginary feature/slice must NEVER produce an ATReviewVerdict "
        f"ledger record -- got {records!r}"
    )


# ===========================================================================
# 3. NEGATIVE -- an empty charter directory is not adopted practice.
# ===========================================================================


@pytest.mark.negative_at
def test_empty_charter_directory_is_not_treated_as_a_charter(tmp_path: Path) -> None:
    """`docs/product/expectations/{feature_id}/` existing but holding ZERO
    `*.md` files must STILL refuse -- a bare, empty (or wrong-extension-only)
    directory must never read as an adopted expectation charter.
    """
    repo = tmp_path / "repo"
    feature_id = "empty-charter-dir"
    slice_id = "slice-01"
    regression_rel = "tests/regression/test_empty_charter_fixture.py"
    _write_pytest_regression_fixture(repo / regression_rel)
    _write_empty_expectation_charter_dir(repo, feature_id)

    exit_code, stdout, stderr = _run_record_at_review_verdict(
        repo,
        _base_argv(
            feature_id=feature_id,
            slice_id=slice_id,
            repo_root=repo,
            regression_test_file_rel=regression_rel,
        ),
    )

    assert exit_code == 2, (
        "an expectation-charter directory with ZERO *.md files must be "
        f"refused exactly like an absent one -- got exit_code={exit_code}, "
        f"stdout={stdout!r}, stderr={stderr!r}"
    )
    payload = _refusal_payload(stdout)
    assert payload.get("event") == "ATReviewVerdictRefused"
    assert payload.get("reason") == "unresolvable-feature-slice"

    records = _read_verdict_records(repo, feature_id, slice_id)
    assert records == [], (
        f"an empty charter directory must never produce a ledger record -- got {records!r}"
    )


# ===========================================================================
# 4. NEGATIVE -- the feature-delta form is NOT regressed.
# ===========================================================================


@pytest.mark.negative_at
def test_feature_delta_present_but_slice_missing_from_plan_still_refuses(
    tmp_path: Path,
) -> None:
    """A feature-delta.md WHOSE `[REF] Slice Plan` table does NOT contain the
    requested `slice_id` must still refuse -- exit 2,
    `unresolvable-feature-slice` -- exactly as today, unaffected by the
    charter-acceptance fix.
    """
    repo = tmp_path / "repo"
    feature_id = "feature-delta-wrong-slice"
    requested_slice_id = "slice-01"
    regression_rel = "tests/regression/test_wrong_slice_fixture.py"
    _write_pytest_regression_fixture(repo / regression_rel)
    # The Slice Plan carries a DIFFERENT slice than the one requested.
    _write_feature_delta_with_slice_row(repo, feature_id, present_slice_id="slice-02")

    exit_code, stdout, stderr = _run_record_at_review_verdict(
        repo,
        _base_argv(
            feature_id=feature_id,
            slice_id=requested_slice_id,
            repo_root=repo,
            regression_test_file_rel=regression_rel,
        ),
    )

    assert exit_code == 2, (
        "a feature-delta whose Slice Plan lacks the requested slice_id must "
        f"still be refused (exit 2) -- got exit_code={exit_code}, "
        f"stdout={stdout!r}, stderr={stderr!r}"
    )
    payload = _refusal_payload(stdout)
    assert payload.get("event") == "ATReviewVerdictRefused"
    assert payload.get("reason") == "unresolvable-feature-slice"

    records = _read_verdict_records(repo, feature_id, requested_slice_id)
    assert records == [], (
        f"a feature/slice not in the Slice Plan must never produce a ledger record -- got {records!r}"
    )


def test_feature_delta_with_matching_slice_and_no_charter_still_records(
    tmp_path: Path,
) -> None:
    """POSITIVE guard: the happy feature-delta path (slice_id IS a Slice Plan
    row, NO expectations directory at all) must still return 0 and write a
    record -- the charter-acceptance fix must be additive, never a
    replacement for the existing feature-delta resolution.
    """
    repo = tmp_path / "repo"
    feature_id = "feature-delta-happy-path"
    slice_id = "slice-01"
    regression_rel = "tests/regression/test_feature_delta_happy_fixture.py"
    _write_pytest_regression_fixture(repo / regression_rel)
    _write_feature_delta_with_slice_row(repo, feature_id, present_slice_id=slice_id)

    assert not (repo / "docs" / "product" / "expectations" / feature_id).exists()

    exit_code, stdout, stderr = _run_record_at_review_verdict(
        repo,
        _base_argv(
            feature_id=feature_id,
            slice_id=slice_id,
            repo_root=repo,
            regression_test_file_rel=regression_rel,
        ),
    )

    assert exit_code == 0, (
        "a real feature-delta with slice_id present in its Slice Plan must "
        f"still record successfully (no expectations dir at all) -- got "
        f"exit_code={exit_code}, stdout={stdout!r}, stderr={stderr!r}"
    )
    records = _read_verdict_records(repo, feature_id, slice_id)
    assert len(records) == 1, f"expected exactly one ledger record -- got {records!r}"


# ===========================================================================
# 5. NEGATIVE -- the refusal still self-explains (WHAT/WHY/HOW), never a bare
#    non-zero exit.
# ===========================================================================


def test_refusal_still_self_explains_with_an_actionable_how(tmp_path: Path) -> None:
    """The refusal payload for an unresolvable feature/slice must carry an
    executable `how` naming a producing action -- never a bare non-zero
    exit code with no guidance.
    """
    repo = tmp_path / "repo"
    feature_id = "ghost-self-explain-check"
    slice_id = "slice-01"
    regression_rel = "tests/regression/test_self_explain_fixture.py"
    _write_pytest_regression_fixture(repo / regression_rel)

    exit_code, stdout, _stderr = _run_record_at_review_verdict(
        repo,
        _base_argv(
            feature_id=feature_id,
            slice_id=slice_id,
            repo_root=repo,
            regression_test_file_rel=regression_rel,
        ),
    )

    assert exit_code == 2
    payload = _refusal_payload(stdout)
    assert payload.get("event") == "ATReviewVerdictRefused"
    how = payload.get("how")
    assert isinstance(how, str) and how.strip(), (
        f"the refusal must carry a non-empty, executable 'how' -- got payload={payload!r}"
    )
    assert payload.get("error"), (
        f"the refusal must carry a non-empty 'error' explaining WHAT/WHY failed -- got payload={payload!r}"
    )


# ===========================================================================
# 6. NEGATIVE (round 2, FLAG 1) -- a charter mapping ONLY a different slice
#    must NOT arm the requested one. Active-RED today: the naive
#    `has_expectation_charter` presence check accepts ANY --slice-id once
#    ANY *.md exists under the feature's charter directory.
# ===========================================================================


@pytest.mark.negative_at
def test_charter_mapped_to_a_different_slice_refuses_the_requested_slice(
    tmp_path: Path,
) -> None:
    """FLAG 1 (Vera): a charter whose `Spec rows:` maps ONLY `slice-01` must
    refuse an unrelated `--slice-id slice-99` -- exit 2,
    `ATReviewVerdictRefused` / `unresolvable-feature-slice`, ledger
    UNCHANGED. Reproduces Vera's own repro shape
    (`--feature-id fix-login-button-does-nothing --slice-id 999` against a
    charter that names a different slice).

    Reuse point (do not reinvent): `des.domain.expectation_charter_mapping.
    resolve_slice_charter(repo_root, feature_id, slice_id)` already computes
    exactly this -- `ARMED` only when `slice_id` is one of the charter's
    `Spec rows:` tokens, `UNMAPPED` when charters exist but none maps this
    slice. `_verify_feature_slice_exists` must route through it instead of
    the bare `has_expectation_charter` presence check.
    """
    repo = tmp_path / "repo"
    feature_id = "fix-login-button-does-nothing"
    mapped_slice_id = "slice-01"
    requested_slice_id = "slice-99"
    regression_rel = "tests/regression/test_flag1_mismatch_fixture.py"
    _write_pytest_regression_fixture(repo / regression_rel)
    _write_filled_charter(repo, feature_id, spec_rows_value=mapped_slice_id)

    exit_code, stdout, stderr = _run_record_at_review_verdict(
        repo,
        _base_argv(
            feature_id=feature_id,
            slice_id=requested_slice_id,
            repo_root=repo,
            regression_test_file_rel=regression_rel,
        ),
    )

    assert exit_code == 2, (
        f"a charter mapping ONLY {mapped_slice_id!r} must refuse an unrelated "
        f"--slice-id {requested_slice_id!r} -- got exit_code={exit_code}, "
        f"stdout={stdout!r}, stderr={stderr!r}. Today `_verify_feature_"
        "slice_exists` accepts ANY --slice-id once the charter directory "
        "has ANY *.md file, regardless of which slice(s) it actually maps."
    )
    payload = _refusal_payload(stdout)
    assert payload.get("event") == "ATReviewVerdictRefused"
    assert payload.get("reason") == "unresolvable-feature-slice"
    _assert_names_actionable_charter_guidance(payload)

    records = _read_verdict_records(repo, feature_id, requested_slice_id)
    assert records == [], (
        "a slice_id no charter maps must never produce a ledger record -- "
        f"got {records!r}"
    )


def test_charter_mapped_to_the_requested_slice_still_records(tmp_path: Path) -> None:
    """POSITIVE (no-overcorrection guard): a charter whose `Spec rows:`
    genuinely maps the REQUESTED slice must still record -- exit 0, one
    ledger record. The FLAG 1 fix (slice-mapping check) must not become a
    blanket rejection of the correctly-mapped case.
    """
    repo = tmp_path / "repo"
    feature_id = "fix-mapped-slice-still-records"
    slice_id = "slice-02"
    regression_rel = "tests/regression/test_mapped_slice_fixture.py"
    _write_pytest_regression_fixture(repo / regression_rel)
    _write_filled_charter(repo, feature_id, spec_rows_value=slice_id)

    exit_code, stdout, stderr = _run_record_at_review_verdict(
        repo,
        _base_argv(
            feature_id=feature_id,
            slice_id=slice_id,
            repo_root=repo,
            regression_test_file_rel=regression_rel,
        ),
    )

    assert exit_code == 0, (
        f"a charter whose Spec rows: genuinely maps the requested "
        f"{slice_id!r} must still record -- got exit_code={exit_code}, "
        f"stdout={stdout!r}, stderr={stderr!r}"
    )
    records = _read_verdict_records(repo, feature_id, slice_id)
    assert len(records) == 1, f"expected exactly one ledger record -- got {records!r}"


# ===========================================================================
# 7. POSITIVE (round 2, canonical-form regression guard) -- a feature-level
#    `Spec rows:` token (`bug-observable` / `brownfield-discovery`) must arm
#    ANY --slice-id the operator passes. Already GREEN today (the naive
#    presence check does not look at Spec rows: at all); this pins the FLAG
#    1 fix from silently breaking the canonical bugfix-lane charter shape.
# ===========================================================================


@pytest.mark.parametrize(
    "feature_level_token", ["bug-observable", "brownfield-discovery"]
)
def test_feature_level_charter_token_arms_any_requested_slice(
    tmp_path: Path, feature_level_token: str
) -> None:
    """A charter whose `Spec rows:` is exactly one of the two first-class
    feature-level tokens (`bug-observable` / `brownfield-discovery` --
    stamped by `des charter-scaffold --seed-mode {bug-observable,
    brownfield-discovery}`, which by construction never map a specific
    slice) must arm ANY `--slice-id` the operator passes -- exit 0, one
    ledger record.

    REGRESSION GUARD for the FLAG 1 fix: `resolve_slice_charter`'s own
    `_classify_spec_rows_value` recognizes these two tokens as
    `feature-level`, but its ARMED-matching loop only checks `slice_id in
    mapped_tokens` -- a bare slice_id never equals the feature-level token
    string, so `resolve_slice_charter` AS-IS classifies this as `UNMAPPED`
    for ANY concrete slice_id. Routing `_verify_feature_slice_exists`
    through `resolve_slice_charter` unchanged would therefore silently
    break the canonical bugfix lane this feature exists to unblock. The
    crafter must extend the domain (special-case feature-level tokens as
    matching any slice) -- this AT pins the OBSERVABLE CLI outcome that
    must hold, not the enum's internal shape.
    """
    repo = tmp_path / "repo"
    feature_id = f"fix-feature-level-{feature_level_token}"
    # Arbitrary and unrelated to the token -- the whole point of a
    # feature-level charter is that it arms ANY slice_id the operator names.
    requested_slice_id = "slice-07"
    regression_rel = "tests/regression/test_feature_level_fixture.py"
    _write_pytest_regression_fixture(repo / regression_rel)
    _write_filled_charter(repo, feature_id, spec_rows_value=feature_level_token)

    exit_code, stdout, stderr = _run_record_at_review_verdict(
        repo,
        _base_argv(
            feature_id=feature_id,
            slice_id=requested_slice_id,
            repo_root=repo,
            regression_test_file_rel=regression_rel,
        ),
    )

    assert exit_code == 0, (
        f"a canonical bugfix-lane charter (Spec rows: {feature_level_token!r}) "
        f"must arm ANY --slice-id the operator passes -- got "
        f"exit_code={exit_code}, stdout={stdout!r}, stderr={stderr!r}. See "
        "this module's docstring (canonical-form regression guard) for why "
        "a naive slice-mapping fix would silently break this shape."
    )
    records = _read_verdict_records(repo, feature_id, requested_slice_id)
    assert len(records) == 1, f"expected exactly one ledger record -- got {records!r}"


# ===========================================================================
# 8. NEGATIVE (round 2, FLAG 2) -- an unfilled `des charter-scaffold`
#    scaffold must NOT arm a verdict. Active-RED today: the naive
#    `has_expectation_charter` presence check accepts ANY *.md, filled or
#    not.
# ===========================================================================


def test_unfilled_charter_scaffold_refuses_despite_the_charter_file_existing(
    tmp_path: Path,
) -> None:
    """FLAG 2 (Vera): a charter FILE produced by the REAL `des
    charter-scaffold` tool and NEVER filled in (scaffold placeholder tokens
    still verbatim in `## Preconditions` / `## Expected observations`) must
    NOT arm a verdict -- an empty vessel is not adopted practice. Exit 2,
    `ATReviewVerdictRefused` / `unresolvable-feature-slice`, ledger
    UNCHANGED. Reproduces Vera's own repro shape (`des charter-scaffold
    --feature-id totally-imaginary-work --seed-mode bug-observable
    --observable "..."` followed by `at_review_verdict` on that feature_id).

    Reuse point (do not reinvent): `des.cli.verify_charter_filled.
    charter_missing_sections(content) -> list[str]` (pure) already computes
    FILLED-ness -- non-empty iff the oracle/preconditions sections still
    carry a scaffold placeholder marker or the oracle lacks a negative
    observation. The fix should consult this (or an equivalent FILLED
    check) in ADDITION to the FLAG 1 slice-mapping check.
    """
    repo = tmp_path / "repo"
    feature_id = "totally-imaginary-work"
    slice_id = "slice-01"
    regression_rel = "tests/regression/test_flag2_unfilled_fixture.py"
    _write_pytest_regression_fixture(repo / regression_rel)

    scaffold_exit, scaffold_stdout, scaffold_stderr = run_cli_in_process(
        [
            "--feature-id",
            feature_id,
            "--seed-mode",
            "bug-observable",
            "--observable",
            "the login button does nothing when clicked",
            "--repo-root",
            str(repo),
        ],
        cwd=repo,
        main=charter_scaffold_main,
    )
    assert scaffold_exit == 0, (
        "the real `des charter-scaffold` tool must succeed for this "
        f"fixture -- exit_code={scaffold_exit}, stdout={scaffold_stdout!r}, "
        f"stderr={scaffold_stderr!r}"
    )
    scaffold_payload = json.loads(
        next(
            line
            for line in scaffold_stdout.splitlines()
            if line.strip().startswith("{")
        )
    )
    created = scaffold_payload.get("created") or []
    assert created, (
        f"expected charter-scaffold to create exactly one charter -- got "
        f"payload={scaffold_payload!r}"
    )
    charter_path = repo / "docs" / "product" / "expectations" / feature_id / created[0]
    assert charter_path.is_file(), (
        f"expected the scaffolded charter at {charter_path} to exist"
    )
    # Deliberately never filled in -- this pins the EXACT repro Vera and the
    # orchestrator confirmed: a fresh scaffold, untouched.

    exit_code, stdout, stderr = _run_record_at_review_verdict(
        repo,
        _base_argv(
            feature_id=feature_id,
            slice_id=slice_id,
            repo_root=repo,
            regression_test_file_rel=regression_rel,
        ),
    )

    assert exit_code == 2, (
        "an unfilled des charter-scaffold scaffold must NOT arm a verdict "
        f"-- got exit_code={exit_code}, stdout={stdout!r}, stderr={stderr!r}. "
        "Today the naive `has_expectation_charter` presence check accepts "
        "ANY *.md file regardless of whether it was ever filled in."
    )
    payload = _refusal_payload(stdout)
    assert payload.get("event") == "ATReviewVerdictRefused"
    assert payload.get("reason") == "unresolvable-feature-slice"
    _assert_names_actionable_charter_guidance(payload)

    records = _read_verdict_records(repo, feature_id, slice_id)
    assert records == [], (
        f"an unfilled charter scaffold must never produce a ledger record -- got {records!r}"
    )
