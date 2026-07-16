"""Regression-pin acceptance suite for the DISTILL->DELIVER carpaccio handoff.

Feature: carpaccio-handoff-no-manual-steps (epic consolidation-for-wider-beta-
testing, member C11). The member's done_signature is exactly "the 3 handoff
frictions (file-tag discovery, slice-tag inheritance, verdict auto-record) each
have a closing AT". `F-CARPACCIO-DISTILL-DELIVER-HANDOFF-FRICTION` named three
friction points, each historically worked around by hand:

  (1) discovery-tag gap  -- the gate discovered `.feature` files by a file-level
      `@feature-{feature_id}` tag; a missing tag silently returned 0 scenarios.
  (2) slice-tag contract -- the per-scenario `@slice-NN` mandate (the DECIDED
      contract, NOT file-level inheritance) that rejects an untagged scenario.
  (3) verdict auto-record -- a Sentinel APPROVED verdict recorded to the ledger
      via `record-at-review-verdict`, read back by the gate's AT-review check,
      with NO manual ledger hand-edit.

INVESTIGATION (this slice, verified empirically against HEAD):

  F1 CLOSED -- `des.application.feature_at_files.feature_tag_files` resolves a
     `.feature` file by its file-level `@feature-{id}` tag (rglob over tests/);
     `carpaccio_format.read_feature_files` reads them. (feature_at_files.py:52-58)
  F2 CLOSED -- `carpaccio_format._parse_scenarios_in_text` clears pending tags at
     the `Feature:` line (no inheritance); `_check_total_coverage` REJECTS a
     scenario with tag_count == 0 with exit 44. (carpaccio_format.py:393-395,
     470-483)
  F3 CLOSED -- `at_review_verdict.main` (the `record-at-review-verdict` CLI)
     derives `at_ids` + `at_content_hash` from the slice's scenarios and appends
     an `ATReviewVerdict` ledger record; `carpaccio_slice_gate.check_at_review`
     reads it back and accepts the slice when verdict == APPROVED with a matching
     AT set + content hash. (at_review_verdict.py:55-98, 197-324;
     carpaccio_slice_gate.py:357-390)

All three ACs are therefore LIVE-GREEN preservation guards
(`@contract-shape:unbounded-preservation`). No active-RED, no
AT_INSUFFICIENT_FOR_GREEN escalation -- the empirical HEAD check governs and
HEAD has all three closed.

RECORDING INTEGRITY: every AC drives the REAL production carpaccio surfaces
(`feature_at_files`, `carpaccio_format`, the `at_review_verdict` recorder,
`carpaccio_slice_gate.check_at_review`) over a hermetic `tmp_path` feature tree
+ ledger -- never this repo's own deltas, never a hand-crafted ledger record.
The driving surface is the production composition root (the CLI `main` and the
gate's public functions), port-to-port, no fixture theater. The Given steps set
up PRECONDITIONS only (a tmp feature tree); the production code does the work.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Production driving surfaces -- the REAL carpaccio handoff machinery. These are
# composition-root CLI / gate functions (Layer-3 driving ports), exercised, not
# mutated, over hermetic trees.
from des.application.feature_at_files import feature_tag_files
from des.cli import at_review_verdict, carpaccio_format, carpaccio_slice_gate


_FEATURE_ID = "demo-handoff-feature"
_SLICE_ID = "slice-01"


def _write_feature(
    repo: Path,
    *,
    feature_tag: str | None,
    scenario_slice_tag: str | None,
) -> Path:
    """Author a hermetic `.feature` file under a tmp repo's tests/ tree.

    `feature_tag`         -- the file-level tag preceding `Feature:` (e.g.
                             "@feature-demo-handoff-feature"); None => omitted.
    `scenario_slice_tag`  -- the per-scenario tag (e.g. "@slice-01"); None =>
                             the scenario carries no slice tag (friction-2 probe).
    """
    at_dir = repo / "tests" / "des" / "acceptance" / _FEATURE_ID
    at_dir.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if feature_tag is not None:
        lines.append(feature_tag)
    lines.append("Feature: Demo handoff feature")
    lines.append("")
    if scenario_slice_tag is not None:
        lines.append(f"  {scenario_slice_tag}")
    lines.append("  Scenario: The customer completes the demo journey")
    lines.append("    Given the customer has started")
    lines.append("    When the customer finishes")
    lines.append("    Then the journey is complete")
    lines.append("")
    feature_file = at_dir / "slice-01-demo.feature"
    feature_file.write_text("\n".join(lines), encoding="utf-8")
    return feature_file


def _single_slice_plan(repo: Path) -> carpaccio_format.SlicePlan:
    """A minimal one-row slice plan whose only row is the entering slice."""
    row = carpaccio_format.SlicePlanRow(
        slice_id=_SLICE_ID,
        value_statement="The customer completes the demo journey end to end",
        status="pending",
        annotation="",
        justification="",
    )
    return carpaccio_format.SlicePlan(rows=(row,))


# ---------------------------------------------------------------------------
# AC-1 -- feature-tag discovery (friction-1 pinned closed)
# Classification: live-green preservation guard.
# ---------------------------------------------------------------------------
def test_ac1_feature_tag_discovery_finds_scenarios(tmp_path: Path) -> None:
    """A `@feature-{id}`-tagged `.feature` is DISCOVERED by the real gate.

    Drives `feature_tag_files` (the discovery SSOT) + `read_feature_files` +
    `parse_scenarios` over a hermetic tmp tree. Pins friction-1: the
    discovery-by-feature-tag path returns >= 1 scenario; it cannot silently
    regress to the 0-scenarios / exit-45 gap.
    """
    repo = tmp_path
    _write_feature(
        repo,
        feature_tag=f"@feature-{_FEATURE_ID}",
        scenario_slice_tag=f"@{_SLICE_ID}",
    )

    # Friction-1 surface: file-level @feature-{id} tag resolution.
    discovered_files = feature_tag_files(repo, _FEATURE_ID)
    assert discovered_files, (
        "friction-1 REOPENED: a @feature-{id}-tagged .feature was not "
        "discovered by feature_tag_files"
    )

    # The gate's own discovery+parse path over the discovered files.
    scenarios = carpaccio_format.parse_scenarios(
        carpaccio_format.read_feature_files(repo, _FEATURE_ID)
    )
    assert len(scenarios) >= 1, (
        "friction-1 REOPENED: gate discovery returned 0 scenarios for a "
        "feature-tagged .feature file"
    )


# ---------------------------------------------------------------------------
# AC-2 -- slice-tag mandate (friction-2 pinned closed)
# Classification: live-green preservation guard.
# ---------------------------------------------------------------------------
def test_ac2_missing_slice_tag_is_rejected(tmp_path: Path) -> None:
    """A scenario with NO per-scenario `@slice-NN` tag is REJECTED.

    Drives the real `_check_total_coverage` (carpaccio Assertion-2) over a
    hermetic scenario that carries the file-level feature tag but NO
    per-scenario slice tag. Pins friction-2: the per-scenario-slice-tag
    mandate is enforced (file-level tags do NOT inherit), so the contract
    cannot silently weaken.
    """
    repo = tmp_path
    _write_feature(
        repo,
        feature_tag=f"@feature-{_FEATURE_ID}",
        scenario_slice_tag=None,  # the friction-2 probe: no per-scenario slice tag
    )
    scenarios = carpaccio_format.parse_scenarios(
        carpaccio_format.read_feature_files(repo, _FEATURE_ID)
    )
    # Sanity: the scenario WAS parsed (so the rejection is about the missing
    # slice tag, not about the scenario being invisible).
    assert scenarios, "precondition failed: the scenario was not parsed at all"
    assert scenarios[0].slice_tags == (), (
        "precondition failed: the probe scenario unexpectedly carries a slice tag"
    )

    plan = _single_slice_plan(repo)
    with pytest.raises(carpaccio_format.GateError) as excinfo:
        carpaccio_format._check_total_coverage(plan, scenarios)

    payload = excinfo.value.payload
    assert "@slice-NN" in str(payload.get("error", "")), (
        "friction-2 REOPENED: a slice-tag-less scenario was not rejected with "
        f"the missing-slice-tag mandate message (payload={payload!r})"
    )


# ---------------------------------------------------------------------------
# AC-3 -- verdict round-trip (friction-3 pinned closed)
# Classification: live-green preservation guard.
# ---------------------------------------------------------------------------
def test_ac3_approved_verdict_round_trips(tmp_path: Path) -> None:
    """An APPROVED verdict recorded via the CLI is read back as approved.

    Drives the REAL `record-at-review-verdict` recorder (`at_review_verdict.main`)
    end-to-end over a hermetic tmp repo + ledger, then `check_at_review` reads
    it back. The recorder DERIVES `at_ids` + `at_content_hash` itself from the
    slice's scenarios -- there is NO manual ledger hand-edit anywhere in this
    test. Pins friction-3: the verdict-record path round-trips automatically.

    Transitively also exercises friction-1 (the recorder + gate both discover
    the hermetic `.feature` via `read_feature_files`).
    """
    repo = tmp_path
    _write_feature(
        repo,
        feature_tag=f"@feature-{_FEATURE_ID}",
        scenario_slice_tag=f"@{_SLICE_ID}",
    )
    # Defect-1 sweep tail (fix-at-review-verdict-surface, slice-01): the
    # APPROVED recorder path runs `_verify_feature_slice_exists` (added by
    # commit 40dd29414), which refuses when
    # `docs/feature/{feature_id}/feature-delta.md` is absent. Stage a real one
    # with a Slice Plan row for the driven feature/slice so the precondition
    # passes and the round-trip reaches the behaviour this test proves.
    feature_delta = repo / "docs" / "feature" / _FEATURE_ID / "feature-delta.md"
    feature_delta.parent.mkdir(parents=True, exist_ok=True)
    feature_delta.write_text(
        f"# Feature Delta: {_FEATURE_ID}\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|---|---|---|---|---|\n"
        f"| {_SLICE_ID} | the customer completes the demo journey | done | | |\n",
        encoding="utf-8",
    )
    ledger = repo / ".nwave" / "telemetry" / "atdd-pure" / f"{_FEATURE_ID}.jsonl"
    assert not ledger.exists(), "precondition failed: ledger pre-exists"

    # Drive the REAL recorder CLI -- it derives at_ids + at_content_hash itself
    # and appends the ATReviewVerdict record. No hand-crafted ledger line.
    exit_code = at_review_verdict.main(
        [
            "--feature-id",
            _FEATURE_ID,
            "--slice-id",
            _SLICE_ID,
            "--verdict",
            "APPROVED",
            "--reviewer-agent-id",
            "nw-acceptance-designer-reviewer",
            "--repo-root",
            str(repo),
        ]
    )
    assert exit_code == 0, "the recorder CLI did not exit 0 on an APPROVED verdict"
    assert ledger.is_file(), (
        "friction-3 REOPENED: the recorder wrote no ledger record (a manual "
        "ledger edit would be required)"
    )

    # The gate reads the SAME hermetic ledger back. check_at_review raises
    # GateError on absent / not-approved / stale-at-set / stale-at-content;
    # a clean return == the slice is accepted as approved.
    scenarios = carpaccio_format.parse_scenarios(
        carpaccio_format.read_feature_files(repo, _FEATURE_ID)
    )
    carpaccio_slice_gate.check_at_review(repo, _FEATURE_ID, _SLICE_ID, scenarios)
    # Reaching here == the round-trip is accepted (no GateError raised).
