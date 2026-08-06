"""slice-04 (gate-outcome-record-seam): `validate-feature-delta` writes a
per-run outcome record.

DDD-5 named `validate-feature-delta` a first-population target ("449
invocations measured, 0 `log_events`"). Its CLI entry (`main`) validates one
`feature-delta.md` file (a bare positional path -- no `--feature-id` /
`--repo-root` flags exist on this gate) and prints/returns 0 or 1; it never
calls `AtCompletionLedger.append_gate_event(..., gate="validate-feature-delta",
outcome=<GateVerdict>)`.

This gate is feature-scoped implicitly (the target path is conventionally
`docs/feature/{feature_id}/feature-delta.md`) but has no explicit repo-root
argument at all -- the singleton-shape ledger
(`AtCompletionLedger(project_root=...)`) is the reuse target, same as
`run-contract-gate` and other ledger-producing commands. The target's own PARENT repo root
is resolved by walking up from the target file (the fixture below plants the
target at that exact conventional path so the eventual production code can
resolve both the repo root and, best-effort, the feature id from the path
shape without inventing a second CLI flag this DISTILL pass does not own).

`validate_feature_delta`'s own docstring names a strictly BINARY contract
("0 on success, 1 on any malformed ... error") -- no third INDETERMINATE
state exists in its current verdict vocabulary, so only PASS/FAIL are
exercised here (a genuine gate-scope boundary, not an omission: DDD-5's
per-gate criterion is satisfied by "every terminating path this gate
actually has", and this gate actually has exactly two).

Driving surface (Mandate 16): the REAL `validate_feature_delta.main()` CLI
edge, driven in-process via `run_cli_in_process`.
"""

from __future__ import annotations

from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.validate_feature_delta import main as _validate_feature_delta_main
from des.domain.gate_outcome import GateVerdict
from tests.common.in_process_cli import run_cli_in_process


_GATE_NAME = "validate-feature-delta"
_FEATURE_ID = "outcome-record-fixture-feature"


def _plant_feature_delta(repo_root: Path, *, well_formed: bool) -> Path:
    """A `feature-delta.md` at the conventional `docs/feature/{id}/` path."""
    feature_dir = repo_root / "docs" / "feature" / _FEATURE_ID
    feature_dir.mkdir(parents=True, exist_ok=True)
    target = feature_dir / "feature-delta.md"
    if well_formed:
        target.write_text("## Wave: DISCUSS / [REF] Persona\n", encoding="utf-8")
    else:
        # Malformed: a "Wave:" heading with an unrecognized type token.
        target.write_text("## Wave: DISCUSS / [BOGUS] Persona\n", encoding="utf-8")
    return target


def _outcome_records(repo_root: Path) -> list[dict[str, object]]:
    ledger = AtCompletionLedger(project_root=repo_root)
    return [
        record
        for record in ledger.read_records(event_type="GateOutcomeRecorded")
        if record.get("gate") == _GATE_NAME
    ]


# =============================================================================
# POSITIVE ATs -- active-RED today
# =============================================================================


def test_well_formed_feature_delta_records_pass_outcome(tmp_path: Path) -> None:
    """A well-formed `feature-delta.md` validates clean (exit 0, unchanged)
    AND appends a GateOutcomeRecorded record with outcome=PASS."""
    target = _plant_feature_delta(tmp_path, well_formed=True)

    exit_code, _stdout, _stderr = run_cli_in_process(
        [str(target)], cwd=tmp_path, main=_validate_feature_delta_main
    )

    assert exit_code == 0, (
        f"expected a well-formed feature-delta to validate, got {exit_code}"
    )

    records = _outcome_records(tmp_path)
    assert len(records) == 1, (
        f"expected exactly one GateOutcomeRecorded record for {_GATE_NAME!r} "
        f"after a PASS run -- got {records!r}"
    )
    assert records[0].get("outcome") == GateVerdict.PASS.value, records[0]


def test_malformed_feature_delta_records_fail_outcome(tmp_path: Path) -> None:
    """A malformed `feature-delta.md` (unrecognized wave-heading type token)
    is REJECTED (exit 1, unchanged -- floor intact) AND appends a
    GateOutcomeRecorded record with outcome=FAIL."""
    target = _plant_feature_delta(tmp_path, well_formed=False)

    exit_code, _stdout, _stderr = run_cli_in_process(
        [str(target)], cwd=tmp_path, main=_validate_feature_delta_main
    )

    assert exit_code == 1, (
        f"expected a malformed feature-delta to be rejected, got {exit_code}"
    )

    records = _outcome_records(tmp_path)
    assert len(records) == 1, (
        f"expected exactly one GateOutcomeRecorded record for {_GATE_NAME!r} "
        f"after a FAIL run -- got {records!r}"
    )
    assert records[0].get("outcome") == GateVerdict.FAIL.value, records[0]
