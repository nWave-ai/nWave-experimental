"""Composition-root EXTENSION for many-features-close-for-one-full-suite
slice-02 (batch-eligibility precheck -- charter
`a-batch-with-one-not-ready-feature-refuses-as-a-whole.md`, feature-delta
Slice Plan row slice-02, Locked Decision D-5, D-D7).

Per feature-delta `Test Reuse & Consolidation Analysis` (slice-01's own
forward-looking note): "`BatchFixture` is designed as the single composition
root future slices EXTEND (new methods for eligibility-state seeding /
cause-diagnosis assertions), never a competing fixture class." This module
EXTENDS `BatchFixture` (slice-01, `composition_slice_01.py`) via subclassing
-- it does NOT duplicate the shared-repo/manifest/observation machinery.

-- WHAT D-5 NAMES, AND HOW THIS FIXTURE GROUNDS EACH CHECK IN REAL SUBSTRATE --
D-5 (Locked Decisions): "every batch member's Slice-Plan slices are
SliceCommitVerified, its deep-review is APPROVED, and its critical charters
are EXAMINE-PASSed at run start." Three independent ineligibility signals,
each grounded in an EXISTING, already-shipped ledger substrate/producer (no
new ledger format invented):

  1. SliceCommitVerified -- the existing truncation oracle
     (`des.cli.verify_deliver_integrity._undelivered_slice_plan_slices`,
     REUSED by `_run_feature_end_member_cycle` already) reads a
     `SliceCommitVerified` record from
     `.nwave/telemetry/atdd-pure/{feature_id}.jsonl`. `seed_truncated_feature`
     (slice-01, inherited) already produces the NEGATIVE case (a declared
     Slice-Plan slice with NEITHER a delivered `.feature` file NOR a
     `SliceCommitVerified` record). `seed_attested_ready_feature` (below)
     produces the POSITIVE case: a REAL `SliceCommitVerified` record written
     to that exact ledger path -- proving the precheck reads genuine
     attestation, not merely a vacuously-absent Slice Plan.

  2. deep-review APPROVED -- `FeatureEndBatchSpec.verdict` (the SAME field
     `des.application.feature_end_sign_service.sign_feature_end_review`
     already treats as "the real deep-review verdict", DDD-7) is the
     manifest entry's OWN declared verdict. Today a structurally-valid
     manifest entry accepts ANY known verdict value (APPROVED or REJECTED --
     `_KNOWN_VERDICTS`) and completes its cycle regardless: a REJECTED
     verdict is a genuinely SIGNED rejection, not itself blocked (the sign
     step's anti-theater invariant only refuses a NON-real verdict, never a
     negative one). Slice-02 elevates "APPROVED specifically" to a
     RUN-START eligibility precondition -- this fixture's
     `write_manifest_with_verdicts` lets a scenario declare a non-APPROVED
     verdict for exactly one member.

  3. critical charter EXAMINE-PASSed -- the existing User-Examiner producer
     (`des.cli.record_examine_verdict.record_examine_verdict`) appends an
     `ExamineVerdictRecorded` record to
     `.nwave/telemetry/examine/{feature_id}.jsonl`. This fixture seeds a
     charter file under `docs/product/expectations/{feature_id}/` PLUS a
     REAL `ExamineVerdictRecorded` record (PASS or FAIL) via the SAME
     producer Vera runs -- never a hand-rolled ledger shape.

DISTILL-interim wire contract (nothing exists yet to reverse-engineer,
mirrors slice-01's own precedent): the batch-eligibility precheck emits
exactly ONE terminal JSON line when ANY member is ineligible --

    {"event": "FeatureEndBatchIneligible", "verb": "run-batch",
     "feature_id": <the ineligible member>, "error": <WHAT+WHY+HOW,
     naming the feature_id AND the failed check>}

-- and exits 2, with ZERO member lines printed and ZERO gates dispatched
(GDP-1, mirrors AT-BATCH-3's malformed-manifest zero-gates guarantee) --
this is a NEW terminal event `_BATCH_TERMINAL_EVENTS` (slice-01,
`composition_slice_01.py`) does not yet recognize, so this module reads the
RAW json-lines directly (`run_batch_and_collect_lines`) rather than routing
through slice-01's `BatchRunOutcome`/`_interpret` (whose event allowlist is
slice-01's own scope, not slice-02's to silently widen).

-- GHERKIN SEEDING (slice-02, converted from an initial pytest-only draft
per the carpaccio gate's mutually-exclusive-AT-discovery-mode rule: slice-01
already SHIPPED a `.feature`, so this feature is Gherkin-mode and slice-02
must be too) -- `seed_mixed_eligibility_batch` is the ONE per-scenario
seeding call the negative `Given` steps delegate to (Mandate-12 criterion 3:
the step body stays a 1-statement fixture-method call; the typed dispatch
tables in `steps/domain_types_slice_02.py` decide WHICH fixture method to
call, never a raw string/`if` branch inside the step).

Pillar 3 / Mandate-13: the driving port stays the REAL `des feature-end
run-batch` CLI, in-process via `run_cli_in_process` (inherited machinery) --
never a direct import of the not-yet-existing precheck function.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import (
    SLICE_COMMIT_VERIFIED,
    AtCompletionLedger,
)
from des.cli.record_examine_verdict import record_examine_verdict
from tests.common.in_process_cli import run_cli_in_process

from .composition_slice_01 import BatchFixture, _all_json_lines
from .steps.domain_types_slice_02 import (
    CHECK_SUBSTRINGS_BY_MODE,
    INELIGIBLE_ID_BY_MODE,
    INELIGIBLE_VERDICT_BY_MODE,
    SEED_METHOD_BY_MODE,
    EligibilityFailureMode,
    MixedBatchSeed,
)


_ATTESTED_SLICE_PLAN = """# Feature Delta: {fid}

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|---|---|---|---|---|
| slice-01 | first | shipped | | j |
"""

_EXAMINER = "nw-user-examiner"
_EXAMINE_TIMESTAMP = "2026-07-20T00:00:00Z"

#: Fixed co-member id every negative scenario's "otherwise ready" feature
#: uses -- shared across scenarios (Pillar 2 chained narrative).
_READY_CO_MEMBER = "feature-ready"


class EligibilityBatchFixture(BatchFixture):
    """EXTENDS `BatchFixture` (slice-01) with the 3 eligibility-precheck
    fixtures D-5 names, plus a raw json-lines driving method that does not
    depend on slice-01's own terminal-event allowlist.
    """

    # --- eligibility-state seeding (the 3 D-5 checks) -----------------------

    def seed_attested_ready_feature(self, feature_id: str) -> Path:
        """POSITIVE control: a REAL `SliceCommitVerified` record for the
        feature's sole Slice-Plan slice, plus a REAL `ExamineVerdictRecorded`
        PASS for its critical charter -- proves the precheck reads genuine
        attestations, not merely a vacuously-absent Slice Plan/charter."""
        feature_dir = self._repo / "docs" / "feature" / feature_id
        feature_dir.mkdir(parents=True)
        (feature_dir / "feature-delta.md").write_text(
            _ATTESTED_SLICE_PLAN.format(fid=feature_id), encoding="utf-8"
        )
        self._known_feature_ids.append(feature_id)
        self._feature_dirs[feature_id] = feature_dir
        self._write_slice_commit_verified(feature_id, "slice-01")
        self._write_examine_verdict(feature_id, "PASS")
        return feature_dir

    def seed_feature_with_rejected_verdict(self, feature_id: str) -> Path:
        """A structurally-ready feature (D-D7 vacuous: no Slice-Plan => not
        truncated) whose ONLY ineligibility signal is its manifest entry's
        own non-APPROVED verdict (paired with `write_manifest_with_verdicts`)."""
        return self.seed_ready_feature(feature_id)

    def seed_feature_with_failed_charter(self, feature_id: str) -> Path:
        """A structurally-ready, deep-review-clean feature whose ONLY
        ineligibility signal is a REAL `ExamineVerdictRecorded` FAIL for its
        critical charter."""
        feature_dir = self.seed_ready_feature(feature_id)
        self._write_examine_verdict(feature_id, "FAIL")
        return feature_dir

    def _write_slice_commit_verified(self, feature_id: str, slice_id: str) -> None:
        """Appends via the SAME producer surface every shipped
        `SliceCommitVerified` writer uses (`AtCompletionLedger.
        append_gate_event`, M7 write contract: gap-free `seq` + `record_hash`
        + timestamp) -- never a hand-rolled JSON line. A hand-written record
        missing those M7 fields breaks `AtCompletionLedger.read_records()`'s
        own integrity contract (`LedgerIntegrityViolation`), which
        `feature_end_records_for`'s `except Exception: return 0` then
        silently swallows -- a fixture bug this producer-reuse avoids by
        construction.
        """
        AtCompletionLedger(feature_id, self._repo).append_gate_event(
            SLICE_COMMIT_VERIFIED, slice_id, feature_id=feature_id
        )

    def _charter_path(self, feature_id: str) -> Path:
        charter_dir = self._repo / "docs" / "product" / "expectations" / feature_id
        charter_dir.mkdir(parents=True, exist_ok=True)
        charter_path = charter_dir / "the-critical-charter.md"
        if not charter_path.is_file():
            charter_path.write_text(
                "# The critical charter\n\nIntent.\n", encoding="utf-8"
            )
        return charter_path

    def _write_examine_verdict(self, feature_id: str, verdict: str) -> None:
        """`slice_id="feature-end"` -- FEATURE scope, matching the EXISTING
        per-member charter-examine gate's own expectation exactly (empirically
        confirmed: `ExamineVerdictMissing` names "a fresh PASS ExamineVerdict
        recorded at feature scope (slice=feature-end)"), never a per-slice
        scope a real attestation would not satisfy.
        """
        record_examine_verdict(
            repo=self._repo,
            feature_id=feature_id,
            slice_id="feature-end",
            charter_path=self._charter_path(feature_id),
            verdict=verdict,
            observations=f"the critical charter {verdict.lower()}ed EXAMINE",
            examiner=_EXAMINER,
            timestamp=_EXAMINE_TIMESTAMP,
        )

    # --- manifest authoring with a per-entry verdict override ---------------

    def write_manifest_with_verdicts(self, entries: list[tuple[str, str]]) -> Path:
        """`entries` is a list of (feature_id, verdict) pairs -- lets a
        scenario declare a NON-APPROVED verdict for exactly one member while
        every other member keeps its own genuinely-declared verdict."""
        manifest_entries = []
        for feature_id, verdict in entries:
            spec = self._spec_for(feature_id)
            spec["verdict"] = verdict
            manifest_entries.append(spec)
        return self._write_manifest(manifest_entries)

    # --- Gherkin-facing composed seeding (one call per Given step) ----------

    def seed_mixed_eligibility_batch(
        self, mode: EligibilityFailureMode
    ) -> MixedBatchSeed:
        """One ready co-member (`feature-ready`) + one feature carrying
        EXACTLY the ONE ineligibility signal `mode` names -- the single
        per-scenario seeding call every negative `Given` step delegates to
        (Mandate-12 criterion 3: the step body stays a 1-statement fixture-
        method call; all dispatch logic lives here, driven by the typed
        tables in `steps/domain_types_slice_02.py`)."""
        ineligible_id = INELIGIBLE_ID_BY_MODE[mode]
        self.seed_ready_feature(_READY_CO_MEMBER)
        seed_method = getattr(self, SEED_METHOD_BY_MODE[mode])
        seed_method(ineligible_id)
        manifest_path = self.write_manifest_with_verdicts(
            [
                (_READY_CO_MEMBER, "APPROVED"),
                (ineligible_id, INELIGIBLE_VERDICT_BY_MODE[mode]),
            ]
        )
        return MixedBatchSeed(
            manifest_path=manifest_path,
            ineligible_feature_id=ineligible_id,
            check_substrings=CHECK_SUBSTRINGS_BY_MODE[mode],
        )

    def seed_fully_eligible_batch(self, feature_id: str) -> Path:
        """A single member carrying REAL positive attestations for all 3
        D-5 checks -- the no-regression pin's ONE seeding call."""
        self.seed_attested_ready_feature(feature_id)
        return self.write_manifest_for([feature_id])

    # --- raw json-lines driving (independent of slice-01's terminal allowlist)

    def run_batch_and_collect_lines(
        self, manifest_path: Path
    ) -> tuple[int, list[dict]]:
        """Drive `feature-end run-batch` in-process; return
        `(exit_code, json_lines)` -- EVERY json-line emitted, untouched by
        slice-01's own `_BATCH_TERMINAL_EVENTS` allowlist (slice-02
        introduces a NEW terminal event that allowlist does not yet name)."""
        exit_code, stdout, _stderr = run_cli_in_process(
            ["feature-end", "run-batch", str(manifest_path), "--repo", str(self._repo)],
            cwd=str(self._repo),
        )
        return exit_code, _all_json_lines(stdout)

    def junit_artifact_count(self) -> int:
        """Public wrapper over the inherited (protected) real-filesystem
        JUnit-artifact count -- the expensive whole-tree check's own
        observable footprint (Mandate 8 Universe)."""
        return self._junit_artifact_count()


@pytest.fixture
def eligibility_fixture(tmp_path, monkeypatch) -> EligibilityBatchFixture:
    """The single composition-root service every slice-02 scenario delegates to."""
    return EligibilityBatchFixture(tmp_path, monkeypatch)


@pytest.fixture
def state_02() -> dict:
    """Per-scenario scratchpad: `seed` (a `MixedBatchSeed`, negative
    scenarios only), `manifest_path`, `exit_code`, `lines`."""
    return {}


__all__ = ["EligibilityBatchFixture"]
