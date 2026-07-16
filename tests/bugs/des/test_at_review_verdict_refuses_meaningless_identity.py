"""Regression -- `des record-at-review-verdict` seals a review verdict under
an identity that IS PRESENT (argparse-wise) but names NO REAL THING -- a
placeholder token (`<id>`), an empty string, a whitespace-only string. The
CLI accepts it, writes it VERBATIM into the AT-completion truth-ledger,
exits 0, and prints `✅ PASS` as if a real reviewer had approved the slice.

RCA (grounded, empirically reproduced):
`docs/feature/fix-at-review-verdict-surface/deliver/rca.md`.

  * Defect 2 (CONFIRMED) -- `--reviewer-agent-id '<id>'` / `''` / `'   '` are
    all accepted, sealed into the ledger, exit 0, `✅ PASS`. `<id>` is the
    LITERAL placeholder token this codebase's OWN remediation strings print
    (`commit_slice.py:243,1174`: `--reviewer-agent-id <id>`) -- a developer
    copy-pasting our own remediation corrupts the truth-ledger and is told it
    worked.
  * Defect 3 (CONFIRMED) -- `--feature-id ''` passes the existence check via
    `pathlib`'s empty-path-segment collapse
    (`Path('docs')/'feature'/''/'feature-delta.md' ==
    Path('docs/feature/feature-delta.md')`) whenever a file happens to sit
    at the COLLAPSED parent path -- a false PASS for a feature identity that
    names nothing.

Both defects are ONE bug class: `main()`'s own argparse layer treats "a
string was supplied" as "a real identity was supplied." The same class
`commit_slice.py`'s `_meaningful_or_absent` closed hours earlier the same
night (`commit_slice.py:717-743`) -- "a value that cannot name a real thing
must be treated as no value" -- was never propagated to this sibling CLI.

INVARIANT this file pins: no `ATReviewVerdict` record may ever be sealed
into the AT-completion ledger under an identity (reviewer, feature, or
slice) that names no real thing -- regardless of how the "nothing" is
spelled (blank, whitespace, or a placeholder token), and regardless of
whether a decoy file happens to sit at a collapsed path.

THE FIX (crafter's job, NOT implemented here -- test-authoring only, zero
`src/` edits): apply a shared meaningful-identity normalizer to
`--reviewer-agent-id`, `--feature-id`, `--slice-id` at the `argparse` parse
boundary in `at_review_verdict.py:_parse_args`, refusing before any ledger
write.

Driving surface (Mandate 13 driving-port-only, Layer 3 in-process default):
the REAL `des.cli.at_review_verdict.main(argv)` CLI EDGE, driven in-process
via `tests.common.in_process_cli.run_cli_in_process` -- mirrors the idiom in
`test_record_at_review_verdict_refuses_imaginary_slice.py`.

OUT OF SCOPE (per dispatch): Defect 1 (the 2 spine-triple human-surface
tests under `tests/scripts/cli/fix_d1_human_readable_gate_surfaces/`) is a
fixture-staging gap the crafter fixes directly -- its own regression net
already exists (those 2 tests). This file is Defect 2/3 only.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.at_review_verdict import main as record_at_review_verdict_main
from tests.common.in_process_cli import run_cli_in_process


_SLICE_ID = "slice-01"
_REAL_REVIEWER = "nw-acceptance-designer-reviewer"

# The class of spellings-of-nothing this file pins -- blank/whitespace (any
# way of spelling nothing) PLUS the placeholder shape `<...>` (a value that
# LOOKS like it names something and does not). Parametrized so the next
# spelling nobody anticipated is caught by the SAME assertion rather than
# needing a bespoke test written after the fact.
_MEANINGLESS_IDENTITY_SPELLINGS = (
    "",
    "   ",
    "\t",
    "\n",
    " \t\n ",
    "<id>",
    "<placeholder>",
)


# ---------------------------------------------------------------------------
# Shared fixture builders -- mirrors
# test_record_at_review_verdict_refuses_imaginary_slice.py's idiom.
# ---------------------------------------------------------------------------


def _run_record_at_review_verdict(
    repo_root: Path, argv: list[str]
) -> tuple[int, str, str]:
    """Drive the REAL `des record-at-review-verdict` CLI EDGE in-process."""
    return run_cli_in_process(argv, cwd=repo_root, main=record_at_review_verdict_main)


def _argv(
    *, feature_id: str, slice_id: str, reviewer_agent_id: str, repo_root: Path
) -> list[str]:
    return [
        "--feature-id",
        feature_id,
        "--slice-id",
        slice_id,
        "--verdict",
        "APPROVED",
        "--reviewer-agent-id",
        reviewer_agent_id,
        "--repo-root",
        str(repo_root),
    ]


def _records(
    repo_root: Path, feature_id: str, slice_id: str
) -> list[dict[str, object]]:
    """Every `ATReviewVerdict` record on the ledger for `feature_id`/`slice_id`.

    Reads the ledger itself (rather than only checking file-existence) so a
    fix that creates the ledger file but still writes a hollow record cannot
    slip past a bare "file absent" check.
    """
    ledger_path = (
        repo_root / ".nwave" / "telemetry" / "atdd-pure" / f"{feature_id}.jsonl"
    )
    if not ledger_path.exists():
        return []
    return AtCompletionLedger(feature_id, repo_root).read_records(
        event_type="ATReviewVerdict", slice_id=slice_id
    )


def _write_feature_delta_with_slice_01(
    feature_delta_path: Path, feature_name: str
) -> None:
    """Minimal, realistic `feature-delta.md`: a `[REF] Slice Plan` table
    carrying a genuine `slice-01` row.
    """
    feature_delta_path.parent.mkdir(parents=True, exist_ok=True)
    feature_delta_path.write_text(
        f"# Feature Delta: {feature_name}\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|---|---|---|---|---|\n"
        "| slice-01 | customer sees confirmation | done | | |\n",
        encoding="utf-8",
    )


def _write_feature_scenario(feature_file_path: Path, feature_id: str) -> None:
    """A real `.feature` file self-identifying with `@feature-{feature_id}`
    and carrying one `@slice-01`-tagged scenario -- what the default
    `at_kind="gherkin"` derivation actually reads.
    """
    feature_file_path.parent.mkdir(parents=True, exist_ok=True)
    feature_file_path.write_text(
        f"@feature-{feature_id}\n"
        "Feature: Customer checkout\n\n"
        "  @slice-01 @walking_skeleton @driving_port\n"
        "  Scenario: Customer completes checkout and sees confirmation\n"
        "    Given customer has a valid payment method on file\n"
        "    When customer completes checkout\n"
        "    Then customer sees order confirmation\n",
        encoding="utf-8",
    )


def _stage_real_feature(repo: Path, feature_id: str) -> None:
    """Stage a REAL feature-delta.md + Slice Plan row + tagged .feature
    scenario for `feature_id`, so `_verify_feature_slice_exists` (a separate,
    correct existence check) is always satisfied and the ONLY thing under
    test in a scenario using this helper is the identity-meaningfulness
    guard. Also creates `repo` itself (via `mkdir(parents=True)`).
    """
    _write_feature_delta_with_slice_01(
        repo / "docs" / "feature" / feature_id / "feature-delta.md", feature_id
    )
    _write_feature_scenario(
        repo / "tests" / "acceptance" / feature_id / "slice-01.feature", feature_id
    )


# ===========================================================================
# 1. THE DURABLE PLACEHOLDER (RCA Defect 2) -- a developer copy-pasting this
#    codebase's OWN remediation string (`--reviewer-agent-id <id>`) must be
#    refused, not sealed into the truth-ledger as a real reviewer.
# ===========================================================================


@pytest.mark.negative_at
def test_reviewer_agent_id_placeholder_literal_is_refused_ledger_untouched(
    tmp_path: Path,
) -> None:
    """`--reviewer-agent-id '<id>'` -- the LITERAL placeholder token this
    codebase's own remediation strings print -- must REFUSE (non-zero exit),
    write NOTHING to the ledger, and never print the PASS face.

    RED today (RCA Defect 2, reproduced verbatim on the real CLI): the
    placeholder is accepted, sealed (`reviewer_agent_id: "<id>"`), exit 0,
    `✅ PASS`.
    """
    repo = tmp_path / "repo"
    feature_id = "placeholder-reviewer-durable"
    _stage_real_feature(repo, feature_id)

    exit_code, stdout, stderr = _run_record_at_review_verdict(
        repo,
        _argv(
            feature_id=feature_id,
            slice_id=_SLICE_ID,
            reviewer_agent_id="<id>",
            repo_root=repo,
        ),
    )

    assert exit_code != 0, (
        "a copy-pasted placeholder reviewer id ('<id>', the exact token this "
        "codebase's own remediation strings print) must REFUSE, not seal a "
        f"fake reviewer into the ledger. got exit_code={exit_code!r} "
        f"stdout={stdout!r} stderr={stderr!r}"
    )
    records = _records(repo, feature_id, _SLICE_ID)
    assert records == [], (
        "a placeholder reviewer id must NEVER produce an ATReviewVerdict "
        f"ledger record -- got {records!r} (exit_code={exit_code!r}, "
        f"stdout={stdout!r}, stderr={stderr!r}). A refusal that still "
        "records a fake reviewer is the disease this test pins against."
    )
    assert "✅ PASS" not in stdout + stderr, (
        "a refused verdict must never print the PASS face -- "
        f"stdout={stdout!r} stderr={stderr!r}"
    )


# ===========================================================================
# 2. THE CLASS, PER FLAG -- "a value that cannot name a real thing" applies
#    identically to every identity-bearing flag on this CLI. Parametrized
#    over blank/whitespace spellings PLUS the placeholder shape `<...>`.
# ===========================================================================


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "meaningless_reviewer_id", _MEANINGLESS_IDENTITY_SPELLINGS, ids=repr
)
def test_reviewer_agent_id_meaningless_spellings_never_seal_a_verdict(
    tmp_path: Path, meaningless_reviewer_id: str
) -> None:
    """Every way of spelling "not a real reviewer" (blank, whitespace, a
    placeholder token) must REFUSE identically -- exit non-zero, write NO
    ledger record, print no PASS face.

    RED today for the whole class (RCA Defect 2): `--reviewer-agent-id` has
    zero validation beyond argparse's bare `required=True` (presence, not
    meaning), so every spelling in this class is currently accepted and
    sealed.
    """
    repo = tmp_path / "repo"
    feature_id = "meaningless-reviewer-class"
    _stage_real_feature(repo, feature_id)

    exit_code, stdout, stderr = _run_record_at_review_verdict(
        repo,
        _argv(
            feature_id=feature_id,
            slice_id=_SLICE_ID,
            reviewer_agent_id=meaningless_reviewer_id,
            repo_root=repo,
        ),
    )

    assert exit_code != 0, (
        f"--reviewer-agent-id={meaningless_reviewer_id!r} (a value that "
        "cannot name a real reviewer) must REFUSE. got "
        f"exit_code={exit_code!r} stdout={stdout!r} stderr={stderr!r}"
    )
    records = _records(repo, feature_id, _SLICE_ID)
    assert records == [], (
        f"--reviewer-agent-id={meaningless_reviewer_id!r} must never "
        f"produce an ATReviewVerdict ledger record -- got {records!r}"
    )
    assert "✅ PASS" not in stdout + stderr, (
        f"--reviewer-agent-id={meaningless_reviewer_id!r} must never print "
        f"the PASS face -- stdout={stdout!r} stderr={stderr!r}"
    )


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "meaningless_feature_id", _MEANINGLESS_IDENTITY_SPELLINGS, ids=repr
)
def test_feature_id_meaningless_spellings_never_seal_a_verdict(
    tmp_path: Path, meaningless_feature_id: str
) -> None:
    """`--feature-id` spelled as any blank/whitespace/placeholder value must
    REFUSE -- exit non-zero, write NO ledger record under that spelling.

    Mostly already GREEN today: `_verify_feature_slice_exists` already
    refuses a nonexistent `docs/feature/{feature_id}/feature-delta.md` for
    any non-empty meaningless spelling (no decoy sits at that path in this
    scenario). The empty-string case (`''`) is the one exception -- see
    `test_feature_id_empty_string_refuses_even_when_decoy_collapses_to_a_real_file`
    below for the pathlib-collapse variant that IS red today (Defect 3).
    This test pins the class as a durable invariant regardless of which
    mechanism currently refuses it, so the fix cannot regress any spelling.
    """
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    # Deliberately NO feature-delta staged under the meaningless spelling --
    # only a sibling real feature would exist in a real run, so a
    # false-positive existence match is structurally impossible here (the
    # decoy-collapse variant is pinned separately below).

    exit_code, stdout, stderr = _run_record_at_review_verdict(
        repo,
        _argv(
            feature_id=meaningless_feature_id,
            slice_id=_SLICE_ID,
            reviewer_agent_id=_REAL_REVIEWER,
            repo_root=repo,
        ),
    )

    assert exit_code != 0, (
        f"--feature-id={meaningless_feature_id!r} (a value that cannot name "
        f"a real feature) must REFUSE. got exit_code={exit_code!r} "
        f"stdout={stdout!r} stderr={stderr!r}"
    )
    records = _records(repo, meaningless_feature_id, _SLICE_ID)
    assert records == [], (
        f"--feature-id={meaningless_feature_id!r} must never produce an "
        f"ATReviewVerdict ledger record -- got {records!r}"
    )
    assert "✅ PASS" not in stdout + stderr, (
        f"--feature-id={meaningless_feature_id!r} must never print the "
        f"PASS face -- stdout={stdout!r} stderr={stderr!r}"
    )


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "meaningless_slice_id", _MEANINGLESS_IDENTITY_SPELLINGS, ids=repr
)
def test_slice_id_meaningless_spellings_never_seal_a_verdict(
    tmp_path: Path, meaningless_slice_id: str
) -> None:
    """`--slice-id` spelled as any blank/whitespace/placeholder value must
    REFUSE -- exit non-zero, write NO ledger record under that spelling.

    Already GREEN today (RCA: "swept and found clean") via the Slice Plan
    row lookup (`slice_plan.row_for(slice_id)` returns `None` for any of
    these spellings) -- pinned here as a durable class invariant, not
    because it is red, so the fix cannot regress it.
    """
    repo = tmp_path / "repo"
    feature_id = "slice-id-class-control"
    _stage_real_feature(repo, feature_id)

    exit_code, stdout, stderr = _run_record_at_review_verdict(
        repo,
        _argv(
            feature_id=feature_id,
            slice_id=meaningless_slice_id,
            reviewer_agent_id=_REAL_REVIEWER,
            repo_root=repo,
        ),
    )

    assert exit_code != 0, (
        f"--slice-id={meaningless_slice_id!r} (a value that cannot name a "
        f"real slice) must REFUSE. got exit_code={exit_code!r} "
        f"stdout={stdout!r} stderr={stderr!r}"
    )
    records = _records(repo, feature_id, meaningless_slice_id)
    assert records == [], (
        f"--slice-id={meaningless_slice_id!r} must never produce an "
        f"ATReviewVerdict ledger record -- got {records!r}"
    )
    assert "✅ PASS" not in stdout + stderr, (
        f"--slice-id={meaningless_slice_id!r} must never print the PASS "
        f"face -- stdout={stdout!r} stderr={stderr!r}"
    )


# ===========================================================================
# 3. THE EMPTY-FEATURE-ID EXISTENCE-COLLAPSE (RCA Defect 3) -- an empty
#    --feature-id must refuse REGARDLESS of whether a decoy file sits at the
#    pathlib-collapsed path. The fix must not depend on the decoy's absence.
# ===========================================================================


@pytest.mark.negative_at
def test_feature_id_empty_string_refuses_even_when_decoy_collapses_to_a_real_file(
    tmp_path: Path,
) -> None:
    """`pathlib.Path` silently collapses an empty path segment --
    `docs/feature/''/feature-delta.md` resolves to
    `docs/feature/feature-delta.md` (the PARENT directory's file), not to a
    nonexistent path. If a decoy happens to sit there, an empty
    `--feature-id` spuriously PASSES the existence check and the ledger
    silently gains a record under `feature_id=""`.

    This test constructs EXACTLY the decoy the RCA describes and proves the
    fix must refuse REGARDLESS of the decoy's presence -- unlike the
    class-pinning tests above (which rely on no decoy existing), this one
    proves the fix does not merely get lucky on an empty repo.

    RED today: reproduced verbatim on the real CLI (RCA Defect 3, Run 4) --
    exit 0, `✅ PASS`, a ledger record written to a file literally named
    `.jsonl` (feature_id="" in the path template).
    """
    repo = tmp_path / "repo"
    decoy = repo / "docs" / "feature" / "feature-delta.md"
    decoy.parent.mkdir(parents=True, exist_ok=True)
    decoy.write_text(
        "# empty-feature-id decoy\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|---|---|---|---|---|\n"
        "| slice-01 | a stub value | pending | | stub justification |\n",
        encoding="utf-8",
    )

    exit_code, stdout, stderr = _run_record_at_review_verdict(
        repo,
        _argv(
            feature_id="",
            slice_id=_SLICE_ID,
            reviewer_agent_id=_REAL_REVIEWER,
            repo_root=repo,
        ),
    )

    assert exit_code != 0, (
        "an empty --feature-id must REFUSE even when a decoy file happens "
        "to sit at the pathlib-collapsed path "
        f"docs/feature/feature-delta.md -- got exit_code={exit_code!r} "
        f"stdout={stdout!r} stderr={stderr!r}"
    )
    records = _records(repo, "", _SLICE_ID)
    assert records == [], (
        "an empty --feature-id must NEVER seal a verdict, even when the "
        f"existence check spuriously matches a decoy file -- got {records!r} "
        f"(exit_code={exit_code!r}, stdout={stdout!r}, stderr={stderr!r})"
    )
    assert "✅ PASS" not in stdout + stderr, (
        "a refused verdict must never print the PASS face -- "
        f"stdout={stdout!r} stderr={stderr!r}"
    )


# ===========================================================================
# 4. THE POSITIVE CONTROLS (load-bearing) -- a GENUINE reviewer id with a
#    real feature/slice must STILL record normally. A fix that refuses
#    everything blocks every real review -- worse than the bug it closes.
# ===========================================================================


def test_real_reviewer_and_real_feature_slice_still_records_approved(
    tmp_path: Path,
) -> None:
    """A GENUINE, non-empty, non-placeholder reviewer id
    (`nw-acceptance-designer-reviewer`) with a real feature/slice must
    record normally: exit 0, exactly one ledger record, `✅ PASS` printed.

    GREEN today and must STAY green after the fix -- the fix narrows the
    accepted input space, it must never reject a meaningful identity.
    Before believing the NO, prove it still says YES.
    """
    repo = tmp_path / "repo"
    feature_id = "real-control-feature"
    _stage_real_feature(repo, feature_id)

    exit_code, stdout, stderr = _run_record_at_review_verdict(
        repo,
        _argv(
            feature_id=feature_id,
            slice_id=_SLICE_ID,
            reviewer_agent_id=_REAL_REVIEWER,
            repo_root=repo,
        ),
    )

    assert exit_code == 0, (
        "a real reviewer id with a real feature/slice must record "
        f"successfully -- got exit_code={exit_code!r} stdout={stdout!r} "
        f"stderr={stderr!r}"
    )
    records = _records(repo, feature_id, _SLICE_ID)
    assert len(records) == 1, (
        f"expected exactly one ATReviewVerdict record for the real "
        f"feature/slice -- got {records!r}"
    )
    assert records[0].get("reviewer_agent_id") == _REAL_REVIEWER, records[0]
    assert records[0].get("verdict") == "APPROVED", records[0]
    assert "✅ PASS" in stdout + stderr, (
        "a genuinely approved verdict must print the PASS face -- "
        f"stdout={stdout!r} stderr={stderr!r}"
    )


def test_real_reviewer_needs_revision_still_skips_ledger_write(
    tmp_path: Path,
) -> None:
    """A genuine reviewer id recording NEEDS_REVISION must still skip the
    ledger write (existing, unaffected behaviour) -- exit 0, zero records.
    Guards the fix does not accidentally start treating NEEDS_REVISION as a
    refusal (a different, unrelated exit-code family) once identity
    validation is added.
    """
    repo = tmp_path / "repo"
    feature_id = "real-needs-revision-control"
    _stage_real_feature(repo, feature_id)

    exit_code, stdout, stderr = _run_record_at_review_verdict(
        repo,
        [
            "--feature-id",
            feature_id,
            "--slice-id",
            _SLICE_ID,
            "--verdict",
            "NEEDS_REVISION",
            "--reviewer-agent-id",
            _REAL_REVIEWER,
            "--repo-root",
            str(repo),
        ],
    )

    assert exit_code == 0, (
        "a real reviewer's NEEDS_REVISION verdict must still exit 0 (soft "
        f"refusal, not a hard gate error) -- got exit_code={exit_code!r} "
        f"stdout={stdout!r} stderr={stderr!r}"
    )
    records = _records(repo, feature_id, _SLICE_ID)
    assert records == [], (
        f"NEEDS_REVISION must never write an ATReviewVerdict record -- got {records!r}"
    )
