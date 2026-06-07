"""AtCompletionLedger -- the M7 integrity-checked atdd_pure audit substrate.

slice-03 of F-DES-ATDD-PURE-HOOK-GATES (U3 -- ADR-030 D3 / M7). The single
CREATE the feature-delta Reuse Analysis authorises: a small pure-function
module (writer + integrity-read validator), not a handler or an engine.

The AT-completion ledger is an append-only JSONL substrate. Two construction
shapes co-exist during the SSOT consolidation rollout:

  (1) Per-feature shape (legacy callers) -- ``AtCompletionLedger(feature_id,
      project_root)``. Writes to
      ``{project_root}/.nwave/telemetry/atdd-pure/{feature_id}.jsonl``.
      Pre-slice-02 callers stay on this path until slice-02 migrates them.

  (2) Singleton shape (slice-01 target) -- ``AtCompletionLedger(project_root=
      ...)``. Writes to ``{project_root}/.nwave/audit/atdd-pure-events.jsonl``
      -- ONE common log shared across features. Each ``append_*`` method takes
      a ``feature_id=`` kw-only argument and a ``correlation_id`` is derived
      from ``(feature_id, slice_id, dispatch_seq)``. The reader
      (``read_records``) accepts a ``feature_id=`` / ``slice_id=`` /
      ``event_type=`` filter so cross-feature audit queries become trivial.

A plain `.jsonl` appended by multiple processes with no locking is NOT a
trustworthy SSOT -- "append-only" is a discipline, not an enforced property.
M7 gives the ledger three hook-only integrity measures (REUSED as-is across
both construction shapes):

  (a) Append under an OS file lock. Every append acquires an advisory
      `fcntl.flock` for the write duration, so concurrent appends serialise
      rather than interleave bytes (S19).
  (b) Per-record monotonic `seq` + per-record `record_hash`. Each record
      carries a gap-free monotonic `seq` (per-feature in the legacy shape,
      global in the singleton shape) and a `record_hash` (SHA-256 over the
      record's own integrity-bearing fields). A killed append leaves a short
      / unparseable final line (S17 -- detectable); a hand-edit breaks the
      `record_hash` or `seq` monotonicity (S21 -- detectable).
  (c) Fail-closed read contract. `read_records` raises `LedgerIntegrityViolation`
      on a malformed line, a short final line, a `record_hash` mismatch, or a
      `seq` gap -- never a silent undercount. The exception carries the
      offending line number and a pointer to ``docs/operations/repair-
      instructions.md`` so the operator sees a recoverable diagnostic, never
      an opaque stack trace.

References:
- ADR-030 D3: docs/architecture/adrs/adr-030-hook-enforced-atdd-pure-spine-gates.md
- Feature-delta U3: docs/feature/atdd-pure-spine-hardening/feature-delta.md
- F-AUDIT-LOG-SSOT (slice-01): docs/feature/fix-atdd-pure-common-audit-log-ssot/feature-delta.md
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from des.ports.driven_ports.at_completion_ledger_port import (
    COVERAGE_MAP_NOT_APPLICABLE_AT_DELIVER_EXIT,
    COVERAGE_MAP_NOT_APPLICABLE_AT_DISTILL_EXIT,
    ENVIRONMENTAL_E2E_GATE_RAN,
    ENVIRONMENTAL_E2E_NOT_APPLICABLE,
    ENVIRONMENTAL_E2E_VERIFIED,
    AtCompletionLedgerPort,
    LedgerFactoryPort,
)


# The required integrity-bearing fields every record carries. `record_hash`
# itself is excluded (it is the digest). `seq` IS hashed -- a reordered record
# then fails the hash as well as the gap check. A record MAY also carry
# optional extra fields (e.g. `verdict_hash` on a `FeatureEndReviewVerdict`
# record); every non-`record_hash` field is hashed (see `_record_hash`), so an
# optional field is tamper-evident exactly like a required one.
_HASHED_FIELDS = ("seq", "event", "feature_id", "slice_id", "timestamp")

# The feature-end cycle event names (F1 -- slice-05 revision). These records
# are feature-scoped (`slice_id == ""`); they prove the feature-end cycle ran.
EBATCH_REFACTOR_COMPLETED = "EBatchRefactorCompleted"
FEATURE_END_REVIEW_VERDICT = "FeatureEndReviewVerdict"
_FEATURE_END_EVENTS = frozenset({EBATCH_REFACTOR_COMPLETED, FEATURE_END_REVIEW_VERDICT})

# Walking-skeleton-production-like-gate event names (slice-01). The gate
# appends a `WalkingSkeletonGateRan` heartbeat BEFORE it knows the verdict
# (RM-1 -- absence is then representable as an integrity FAIL) and a
# `WalkingSkeletonTierVerified` positive-proof record on a green tier run
# (RM-3 -- the done-gate's trust anchor; presence-of-proof, not
# marker-absence). Both are feature-scoped (`slice_id == ""`).
WALKING_SKELETON_GATE_RAN = "WalkingSkeletonGateRan"
WALKING_SKELETON_TIER_VERIFIED = "WalkingSkeletonTierVerified"

# Environmental-e2e gate event names (fix-oss-environmental-e2e-gate slice-02).
# The gate appends an `EnvironmentalE2eGateRan` heartbeat record BEFORE the
# verdict (RM-1) and an `EnvironmentalE2eVerified` positive-proof record on a
# green `--mode run` verdict (presence-of-proof, principle 13: a hand-deleted
# unverified marker satisfies "no block" but not "proof exists", so done still
# blocks). Both records are feature-scoped (`slice_id == ""`).
#
# AD-02 DIP fix: these two constants are now defined in the driven port
# (`des.ports.driven_ports.at_completion_ledger_port`) as the SSOT so the
# domain done-gate can read them without a domain->adapter import edge. The
# adapter re-imports + re-exports them (above + via `__all__`) so every caller
# that reads them off the adapter stays unbroken.

# Coverage-map touchpoint event names (fix-distill-human-signoff slice-06). The
# `verify_coverage_map verify --touchpoint <name>` gate appends one heartbeat
# record per passing touchpoint -- DISTILL-exit or DELIVER-exit. The U4
# SubagentStop enforcer (and its verify_deliver_integrity CLI mirror) is the
# consumer that turns a missing heartbeat into a feature-end block (5th-sibling
# of the env-e2e + walking-skeleton heartbeat pattern; ADR-030 hook-only).
COVERAGE_MAP_VERIFIED_AT_DISTILL_EXIT = "CoverageMapVerifiedAtDistillExit"
COVERAGE_MAP_VERIFIED_AT_DELIVER_EXIT = "CoverageMapVerifiedAtDeliverExit"

# The AT-review verdict event name (F-13 closure -- slice-02). The
# `at_review_verdict` producer appends one such record per APPROVED slice
# through `append_review_verdict`, so the record carries `seq` + `record_hash`
# exactly like a gate event and the M7 fail-closed read accepts the ledger.
_AT_REVIEW_VERDICT = "ATReviewVerdict"
_WALKING_SKELETON_EVENTS = frozenset(
    {WALKING_SKELETON_GATE_RAN, WALKING_SKELETON_TIER_VERIFIED}
)

# The G-DISTILL-EXIT success terminal (oss-hook-side-phase-injection slice-01).
# The SubagentStop G-DISTILL-EXIT gate appends this record when every planned
# slice carries a signed ATReviewVerdict -- the symmetric SUCCESS terminal (SF
# ADR-016) that leaves the same kind of evidence a blocked feature does. The
# phase is encoded in the event NAME, so the record carries only the five
# `_HASHED_FIELDS` + `record_hash` -- zero new read-contract field.
# Feature-scoped (`slice_id == ""`).
WORKFLOW_PHASE_COMPLETED_DISTILL = "WorkflowPhaseCompletedDistill"

# The G-DELIVER-EXIT success terminal (oss-hook-side-phase-injection slice-02).
# The SubagentStop G_COMMIT exit gate appends this record ALONGSIDE the existing
# `SliceCommitVerified` when a slice commit passes both exit gates -- the
# DELIVER-exit half of the SF ADR-016 success-terminal symmetry (the DISTILL-exit
# half being `WorkflowPhaseCompletedDistill`). The phase is encoded in the event
# NAME, so the record carries only the five `_HASHED_FIELDS` + `record_hash` --
# zero new read-contract field. Slice-scoped (`slice_id == "slice-N"`) -- unlike
# the per-feature DISTILL terminal -- because DELIVER-exit fires once per slice.
WORKFLOW_PHASE_COMPLETED_G_COMMIT = "WorkflowPhaseCompletedGCommit"

# Operator-recoverable diagnostic anchor (slice-01 AT-3). The repair-instructions
# document lives at `docs/operations/repair-instructions.md`; the
# `LedgerIntegrityViolation` exception carries this pointer so the operator
# sees a recoverable diagnostic, never an opaque stack trace.
_REPAIR_INSTRUCTIONS_PATH = "docs/operations/repair-instructions.md"

# Migration quiesce env-var (slice-01 F-AUDIT-MIGRATION-DISPATCH-QUIESCE-
# MECHANISM). When set to "1" the singleton-shape writer refuses to append
# and records a `MigrationQuiesced` diagnostic record instead. The legacy
# per-feature shape is unaffected (it migrates in slice-02).
_QUIESCE_ENV = "NWAVE_AUDIT_LOG_MIGRATING"


class LedgerIntegrityViolation(Exception):
    """Raised when the AT-completion ledger fails its M7 integrity contract.

    Fail-closed: the U1 order check and the U4 feature-end gate surface this as
    a `{"decision": "block", "event": "LedgerIntegrityViolation"}` -- never a
    silent undercount that would close an incomplete feature or block a
    complete one.

    The `detail` attribute carries the violation class for the hook block
    payload: one of `malformed-line`, `truncated-tail`, `hash-mismatch`,
    `seq-gap`.

    The `line_number` attribute carries the offending JSONL line number (1-
    indexed) for the operator-recoverable diagnostic; ``None`` for whole-file
    violations (e.g. seq-gap detected after the full sweep). The
    `repair_instructions` attribute is a pointer to the repair doc.
    """

    def __init__(
        self,
        detail: str,
        message: str,
        *,
        line_number: int | None = None,
        repair_instructions: str = _REPAIR_INSTRUCTIONS_PATH,
    ) -> None:
        self.detail = detail
        self.line_number = line_number
        self.repair_instructions = repair_instructions
        super().__init__(message)


def derive_correlation_id(feature_id: str, slice_id: str, dispatch_seq: int) -> str:
    """Derive the 16-hex correlation identifier for a ledger record.

    Pure function (no I/O, no side effects). The identifier is the first 16
    hex characters of ``sha256(f"{feature_id}/{slice_id}/{dispatch_seq}")``.

    - Determinism: the same input triple always produces the same digest.
    - Collision-freedom: the 64-bit truncated space is birthday-bounded at
      ~4 billion entries; slice-01's PBT sweeps 10 000 triples and asserts no
      collision. The production SLO measures actual collision rate post-
      slice-05 over the full common-log volume.

    The composition is ``feature_id/slice_id/dispatch_seq`` joined by ``/``
    so the hash domain stays unambiguous for adjacent values (e.g. ``("a",
    "b/c", 1)`` and ``("a/b", "c", 1)`` hash to distinct digests).
    """
    payload = f"{feature_id}/{slice_id}/{dispatch_seq}".encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def _record_hash(record: dict[str, Any]) -> str:
    """SHA-256 digest over every integrity-bearing field of a record.

    Deterministic: the hashed payload is every field EXCEPT `record_hash`
    itself, serialised with sorted keys, so the digest is stable regardless of
    dict insertion order. A hand-edit to ANY field -- a required `_HASHED_FIELDS`
    entry or an optional one such as `verdict_hash` -- breaks the digest (S21).

    Backward-compatible: a record carrying exactly the five `_HASHED_FIELDS`
    (the pre-revision shape) hashes to the identical digest as before.
    """
    payload = {key: value for key, value in record.items() if key != "record_hash"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class AtCompletionLedger(AtCompletionLedgerPort):
    """Integrity-checked writer/reader for the atdd_pure audit substrate.

    Two construction shapes co-exist during the SSOT consolidation rollout:

    - Legacy per-feature: ``AtCompletionLedger(feature_id, project_root)``.
      Writes to ``.nwave/telemetry/atdd-pure/{feature_id}.jsonl``. Pre-slice-
      02 callers stay on this path until slice-02 migrates them.
    - Singleton (slice-01 target): ``AtCompletionLedger(project_root=...)``.
      Writes to ``.nwave/audit/atdd-pure-events.jsonl`` -- ONE common log.
      Each ``append_*`` method takes a ``feature_id=`` kw-only argument; the
      reader (``read_records``) accepts a ``feature_id=`` filter.

    The driving port is this class. The observable surface is the appended
    records (each carrying `seq` + `record_hash` + `correlation_id`) and the
    integrity-checked read verdict.
    """

    def __init__(
        self,
        feature_id: str | None = None,
        project_root: Path | None = None,
    ) -> None:
        """Construct in either legacy per-feature or singleton-shape mode.

        Legacy: ``AtCompletionLedger("my-feature", Path("/repo"))`` -- both
        positional, ``feature_id`` is a non-empty string.
        Singleton: ``AtCompletionLedger(project_root=Path("/repo"))`` --
        ``feature_id`` omitted (None); each write call takes a per-call
        ``feature_id=`` kw-only argument.
        """
        if project_root is None:
            raise TypeError(
                "AtCompletionLedger requires a project_root (Path); pass it "
                "positionally as the second argument (legacy per-feature "
                "shape) or as a keyword (singleton shape)."
            )
        self._feature_id = feature_id
        self._project_root = Path(project_root)
        self._is_singleton = feature_id is None

    # --- path resolution -----------------------------------------------------

    def ledger_dir(self) -> Path:
        """The telemetry / audit directory holding the JSONL substrate.

        Singleton shape -> ``.nwave/audit/``. Legacy per-feature shape ->
        ``.nwave/telemetry/atdd-pure/``.
        """
        if self._is_singleton:
            return self._project_root / ".nwave" / "audit"
        return self._project_root / ".nwave" / "telemetry" / "atdd-pure"

    def ledger_path(self) -> Path:
        """The JSONL file path for the audit substrate.

        Singleton shape -> ``.nwave/audit/atdd-pure-events.jsonl`` (one common
        log for all features). Legacy per-feature shape ->
        ``.nwave/telemetry/atdd-pure/{feature_id}.jsonl``.
        """
        if self._is_singleton:
            return self.ledger_dir() / "atdd-pure-events.jsonl"
        return self.ledger_dir() / f"{self._feature_id}.jsonl"

    # --- write surface (M4 emission + M7 integrity + M11 provisioning) ------

    def append_gate_event(
        self,
        event: str,
        slice_id: str,
        *,
        feature_id: str | None = None,
    ) -> dict[str, Any]:
        """Append one slice gate-boundary audit record under the M7 write contract.

        M11: the ledger directory is provisioned with `mkdir(parents=True,
        exist_ok=True)` -- idempotent, so two concurrent hooks both creating it
        do not crash. Writability is EAFP -- the append attempt itself surfaces
        an `OSError`, never a separate `os.access` probe (which would be a
        TOCTOU pair).

        M7(a): the append holds an advisory `fcntl.flock` for the write
        duration so concurrent appends serialise.

        M7(b): the appended record carries a gap-free monotonic `seq` (one
        past the current terminal `seq`), a `record_hash`, and -- in the
        singleton shape -- a derived `correlation_id`.

        Returns the appended record.
        """
        return self._append_record(
            {"event": event, "slice_id": slice_id},
            feature_id=feature_id,
        )

    def append_feature_end_event(
        self,
        event: str,
        verdict_hash: str | None = None,
        *,
        feature_id: str | None = None,
    ) -> dict[str, Any]:
        """Append one feature-end cycle record under the M7 write contract (F1).

        slice-05 revision (Finding 1): the feature-end cycle must leave a
        machine trace that it ran -- an `EBatchRefactorCompleted` record for the
        E_BATCH_REFACTOR phase and a `FeatureEndReviewVerdict` record carrying
        the reviewer `verdict_hash`. U4 asserts both are present before
        feature-end passes.

        Feature-end records are feature-scoped, not slice-scoped: `slice_id` is
        the empty string. `verdict_hash`, when supplied, is an extra field --
        hashed into `record_hash` like every other field, so a forged verdict
        is tamper-evident.
        """
        extra: dict[str, Any] = {"event": event, "slice_id": ""}
        if verdict_hash is not None:
            extra["verdict_hash"] = verdict_hash
        return self._append_record(extra, feature_id=feature_id)

    def append_workflow_phase_completed_distill(
        self, *, feature_id: str | None = None
    ) -> dict[str, Any]:
        """Append the `WorkflowPhaseCompletedDistill` success terminal record.

        oss-hook-side-phase-injection slice-01: the SubagentStop G-DISTILL-EXIT
        gate emits this record when every planned slice carries a signed
        `ATReviewVerdict` -- the symmetric SUCCESS terminal (SF ADR-016) that
        leaves the same kind of durable evidence a blocked feature does.

        The phase is encoded in the event NAME, so the record carries only the
        five `_HASHED_FIELDS` + `record_hash` -- it round-trips `read_records`
        with no M7 read-contract change. Feature-scoped (`slice_id == ""`),
        mirroring `append_feature_end_event`.
        """
        return self._append_record(
            {"event": WORKFLOW_PHASE_COMPLETED_DISTILL, "slice_id": ""},
            feature_id=feature_id,
        )

    def append_workflow_phase_completed_g_commit(
        self, slice_id: str, *, feature_id: str | None = None
    ) -> dict[str, Any]:
        """Append the `WorkflowPhaseCompletedGCommit` success terminal record.

        oss-hook-side-phase-injection slice-02: the SubagentStop G_COMMIT exit
        gate emits this record ALONGSIDE the existing `SliceCommitVerified` when
        a slice commit passes both exit gates -- the DELIVER-exit half of the SF
        ADR-016 success-terminal symmetry (mirror of
        `append_workflow_phase_completed_distill`).

        The phase is encoded in the event NAME, so the record carries only the
        five `_HASHED_FIELDS` + `record_hash` -- it round-trips `read_records`
        with no M7 read-contract change. Unlike the per-feature DISTILL terminal,
        the DELIVER-exit terminal is slice-scoped: it carries the verified
        `slice_id`, because the G_COMMIT exit gate fires once per slice.
        """
        return self._append_record(
            {"event": WORKFLOW_PHASE_COMPLETED_G_COMMIT, "slice_id": slice_id},
            feature_id=feature_id,
        )

    def append_review_verdict(
        self,
        slice_id: str,
        verdict_fields: dict[str, Any],
        *,
        feature_id: str | None = None,
    ) -> dict[str, Any]:
        """Append one ATReviewVerdict record under the M7 write contract (F-13).

        F-13 closure: the `at_review_verdict` producer used to hand-write a
        JSONL line carrying neither `seq` nor `record_hash`, so the M7
        fail-closed read (`read_records`) rejected it as a `malformed-line`
        the moment a verdict record interleaved with gate events. Routing the
        verdict through this method gives it the same `seq` + `record_hash`
        every gate event carries -- the ledger becomes a single uniform schema
        the carpaccio-order read consumes without raising.

        ``verdict_fields`` carries the verdict's own keys -- the seven HMAC-
        signed fields (`schema_version`, `verdict`, `reviewer_agent_id`,
        `at_ids`, `at_content_hash`, plus the producer-chosen `timestamp`),
        the `hmac_sha256` signature and `findings_summary`. `event` is forced
        to `ATReviewVerdict` and `slice_id` is taken from the argument.

        The producer signs its own `timestamp` (the HMAC covers it), so the
        M7 critical section honours a `timestamp` already present in
        ``verdict_fields`` rather than overwriting it -- it assigns only the
        monotonic `seq`, the `feature_id` and the `record_hash`. The
        `record_hash` covers every field, so the signed verdict is tamper-
        evident under BOTH the HMAC and the M7 hash.
        """
        return self._append_record(
            {"event": _AT_REVIEW_VERDICT, "slice_id": slice_id, **verdict_fields},
            feature_id=feature_id,
        )

    def append_walking_skeleton_gate_ran(
        self, *, feature_id: str | None = None, slice_id: str = ""
    ) -> dict[str, Any]:
        """Append the `WalkingSkeletonGateRan` heartbeat record (RM-1).

        Emitted by the walking-skeleton gate on entry, BEFORE the verdict is
        known -- a "the gate was reached" attestation. The feature-end
        integrity check asserts this record is present; its absence means no
        gate ran -> integrity FAIL, never a silent proceed.

        Feature-scoped by default (`slice_id == ""`); singleton-shape callers
        may pass an explicit `slice_id=` so group-by-correlation surfaces the
        record under the right slice cluster (per design D3).
        """
        return self._append_record(
            {"event": WALKING_SKELETON_GATE_RAN, "slice_id": slice_id},
            feature_id=feature_id,
        )

    def append_walking_skeleton_tier_verified(
        self,
        tier_of_record: str,
        artifact_hash: str | None = None,
        *,
        feature_id: str | None = None,
    ) -> dict[str, Any]:
        """Append the `WalkingSkeletonTierVerified` positive-proof record (RM-3).

        Written by the gate on a green tier run. The done-gate's trust anchor:
        "feature done" requires this record present (presence-of-proof), so a
        hand-`rm` of a deferral marker cannot unblock done. Carries the tier
        of record and, optionally, the artifact hash it was verified against.

        Feature-scoped (`slice_id == ""`).
        """
        extra: dict[str, Any] = {
            "event": WALKING_SKELETON_TIER_VERIFIED,
            "slice_id": "",
            "tier_of_record": tier_of_record,
        }
        if artifact_hash is not None:
            extra["artifact_hash"] = artifact_hash
        return self._append_record(extra, feature_id=feature_id)

    def append_environmental_e2e_gate_ran(
        self, *, feature_id: str | None = None
    ) -> dict[str, Any]:
        """Append the `EnvironmentalE2eGateRan` heartbeat record (RM-1).

        Emitted by the DELIVER feature-end orchestration step BEFORE
        `verify_environmental_e2e --mode run` returns its verdict -- a "the
        gate was reached" attestation. The U4 feature-end enforcer asserts
        this record is present; its absence means no gate ran -> missing-
        record block, never a silent proceed.

        Feature-scoped (`slice_id == ""`).
        """
        return self._append_record(
            {"event": ENVIRONMENTAL_E2E_GATE_RAN, "slice_id": ""},
            feature_id=feature_id,
        )

    def append_environmental_e2e_verified(
        self, *, feature_id: str | None = None
    ) -> dict[str, Any]:
        """Append the `EnvironmentalE2eVerified` positive-proof record.

        Written by the DELIVER feature-end orchestration step AFTER
        `verify_environmental_e2e --mode run` exits 0 (verdict=pass). The
        done-gate's trust anchor: "feature done" requires this record present
        (presence-of-proof, principle 13), so a hand-`rm` of the unverified
        deferral marker cannot unblock done.

        Feature-scoped (`slice_id == ""`).
        """
        return self._append_record(
            {"event": ENVIRONMENTAL_E2E_VERIFIED, "slice_id": ""},
            feature_id=feature_id,
        )

    def append_environmental_e2e_not_applicable(
        self, *, feature_id: str | None = None
    ) -> dict[str, Any]:
        """Append the `EnvironmentalE2eNotApplicable` NA-marker record (slice-04).

        Minted by the feature-end cycle when the walking-skeleton floor granted
        NOT_APPLICABLE -- the feature ships no installable artifact, so the
        env-e2e leg is inapplicable by the SAME mechanical delta cross-check. The
        DISTINCT marker reconciles the env-e2e leg in the downstream done-gate IN
        PLACE OF a verified record; minting `EnvironmentalE2eVerified` on an
        un-run leg would be theater (DDD-2), so this path NEVER appends it.

        Feature-scoped (`slice_id == ""`).
        """
        return self._append_record(
            {"event": ENVIRONMENTAL_E2E_NOT_APPLICABLE, "slice_id": ""},
            feature_id=feature_id,
        )

    def environmental_e2e_events(
        self, *, feature_id: str | None = None
    ) -> frozenset[str]:
        """The set of environmental-e2e gate event names recorded.

        The done-gate (`evaluate_done_gate`) consumes this set: a verdict of
        `PERMITTED` requires BOTH the heartbeat (`EnvironmentalE2eGateRan`)
        AND the positive proof (`EnvironmentalE2eVerified`). The slice-04
        applicability reconciliation also accepts the
        `EnvironmentalE2eNotApplicable` NA marker in place of the verified
        record. Read under the M7 fail-closed integrity contract.

        Optional `feature_id=` filter (slice-02b) scopes the read to one
        feature in the singleton-shape substrate; ``None`` retains the
        cross-feature aggregate semantics.
        """
        env_events = {
            ENVIRONMENTAL_E2E_GATE_RAN,
            ENVIRONMENTAL_E2E_VERIFIED,
            ENVIRONMENTAL_E2E_NOT_APPLICABLE,
        }
        return frozenset(
            str(record["event"])
            for record in self.read_records(feature_id=feature_id)
            if record["event"] in env_events
        )

    def append_coverage_map_verified_at_distill_exit(
        self, *, feature_id: str | None = None
    ) -> dict[str, Any]:
        """Append the `CoverageMapVerifiedAtDistillExit` heartbeat record (slice-06).

        Emitted by `verify_coverage_map verify --touchpoint distill_exit` after
        the gate accepts the coverage-map at the DISTILL-exit handoff. Its
        absence from the ledger means the DISTILL-exit touchpoint was skipped
        (or refused) -- the U4 enforcer can then surface a missing-record block
        independent of whether the gate itself ran.

        Feature-scoped (`slice_id == ""`).
        """
        return self._append_record(
            {"event": COVERAGE_MAP_VERIFIED_AT_DISTILL_EXIT, "slice_id": ""},
            feature_id=feature_id,
        )

    def append_coverage_map_verified_at_deliver_exit(
        self, *, feature_id: str | None = None
    ) -> dict[str, Any]:
        """Append the `CoverageMapVerifiedAtDeliverExit` heartbeat record (slice-06).

        Emitted by `verify_coverage_map verify --touchpoint deliver_exit` after
        the gate accepts the coverage-map at the DELIVER-exit re-check (no
        post-signoff body edit AND no `.feature` AT-population change that
        uncovers a manifest domain). Same RM-1 heartbeat pattern as the
        env-e2e and walking-skeleton gates.

        Feature-scoped (`slice_id == ""`).
        """
        return self._append_record(
            {"event": COVERAGE_MAP_VERIFIED_AT_DELIVER_EXIT, "slice_id": ""},
            feature_id=feature_id,
        )

    def append_coverage_map_not_applicable_at_distill_exit(
        self, *, feature_id: str | None = None
    ) -> dict[str, Any]:
        """Append the `CoverageMapNotApplicableAtDistillExit` NA marker (slice-04).

        Minted by the feature-end cycle when coverage-map adoption is inactive
        repo-wide AND the feature produced no `distill/coverage-map.md` -- the
        DISTINCT NA marker that reconciles the distill-exit coverage requirement
        IN PLACE OF the verified record. NEVER minted when a map is present (a
        present map is always really verified) nor under active adoption.

        Feature-scoped (`slice_id == ""`).
        """
        return self._append_record(
            {"event": COVERAGE_MAP_NOT_APPLICABLE_AT_DISTILL_EXIT, "slice_id": ""},
            feature_id=feature_id,
        )

    def append_coverage_map_not_applicable_at_deliver_exit(
        self, *, feature_id: str | None = None
    ) -> dict[str, Any]:
        """Append the `CoverageMapNotApplicableAtDeliverExit` NA marker (slice-04).

        The deliver-exit sibling of
        `append_coverage_map_not_applicable_at_distill_exit`; minted on the same
        inactive-adoption + genuine-absence NA signal so the downstream done-gate
        reconciles the deliver-exit coverage requirement via the NA marker.

        Feature-scoped (`slice_id == ""`).
        """
        return self._append_record(
            {"event": COVERAGE_MAP_NOT_APPLICABLE_AT_DELIVER_EXIT, "slice_id": ""},
            feature_id=feature_id,
        )

    def coverage_map_touchpoint_events(
        self, *, feature_id: str | None = None
    ) -> frozenset[str]:
        """The set of coverage-map touchpoint event names recorded (slice-06).

        The U4 SubagentStop enforcer (and its `verify_deliver_integrity` CLI
        mirror) reads this set under the M7 fail-closed integrity contract; a
        missing `CoverageMapVerifiedAtDeliverExit` heartbeat surfaces as a
        FeatureEndCycleIncomplete block at feature-end. The slice-04
        applicability reconciliation also accepts the
        `CoverageMapNotApplicableAt{Distill,Deliver}Exit` NA markers in place of
        the verified records.

        Optional `feature_id=` filter (slice-02b) scopes the read to one
        feature in the singleton-shape substrate; ``None`` retains the
        cross-feature aggregate semantics.
        """
        touchpoint_events = {
            COVERAGE_MAP_VERIFIED_AT_DISTILL_EXIT,
            COVERAGE_MAP_VERIFIED_AT_DELIVER_EXIT,
            COVERAGE_MAP_NOT_APPLICABLE_AT_DISTILL_EXIT,
            COVERAGE_MAP_NOT_APPLICABLE_AT_DELIVER_EXIT,
        }
        return frozenset(
            str(record["event"])
            for record in self.read_records(feature_id=feature_id)
            if record["event"] in touchpoint_events
        )

    def walking_skeleton_events(
        self, *, feature_id: str | None = None
    ) -> frozenset[str]:
        """The set of walking-skeleton gate event names recorded (slice-01).

        The feature-end integrity check asserts `WalkingSkeletonGateRan` is
        present (RM-1 heartbeat) and the done-gate asserts
        `WalkingSkeletonTierVerified` is present (RM-3 positive proof).

        Read under the M7 fail-closed integrity contract.

        Optional `feature_id=` filter (slice-02b) scopes the read to one
        feature in the singleton-shape substrate; ``None`` retains the
        cross-feature aggregate semantics.
        """
        return frozenset(
            str(record["event"])
            for record in self.read_records(feature_id=feature_id)
            if record["event"] in _WALKING_SKELETON_EVENTS
        )

    def append_coverage_map_signed_off(
        self,
        reviewed_content_digest: str,
        signer_name: str,
        signer_date: str,
        *,
        feature_id: str | None = None,
    ) -> dict[str, Any]:
        """Append a ``CoverageMapSignedOff`` record under the M7 write contract.

        F-DISTILL-HUMAN-SIGNOFF slice-04: the deterministic-engine ledger
        writer binds the ``## Signoff`` block, the projected git trailer, and
        this ledger record to ONE identity -- the §5.3 canonical-content
        digest the block carries. Feature-scoped (``slice_id == ""``).

        Hook-invoked only via
        ``src.des.adapters.driven.ledger.coverage_map_signoff_writer``; the
        G5 closed-world allowlist enforces this at the AST level.
        """
        return self._append_record(
            {
                "event": "CoverageMapSignedOff",
                "slice_id": "",
                "reviewed_content_digest": reviewed_content_digest,
                "signer_name": signer_name,
                "signer_date": signer_date,
            },
            feature_id=feature_id,
        )

    def _resolve_feature_id(self, call_feature_id: str | None) -> str:
        """Pick the effective feature_id for one append call.

        Singleton shape -- the per-call argument is REQUIRED (the ledger holds
        no construction-time feature_id). Legacy per-feature shape -- the
        per-call argument is ignored when not provided; when provided it must
        match the construction-time feature_id (defensive, not enforced as
        crash today -- the per-call arg simply overrides, mirroring callsite
        intent).
        """
        if self._is_singleton:
            if call_feature_id is None:
                raise TypeError(
                    "Singleton-shape AtCompletionLedger(project_root=...) "
                    "requires feature_id= on every append_* call."
                )
            return call_feature_id
        # Legacy per-feature shape: construction-time feature_id wins when no
        # per-call override; per-call override honoured when supplied.
        assert self._feature_id is not None
        return call_feature_id if call_feature_id is not None else self._feature_id

    def _append_record(
        self, fields: dict[str, Any], *, feature_id: str | None = None
    ) -> dict[str, Any]:
        """The shared M7 append critical section -- one flock-serialised write.

        ``fields`` carries the record-specific keys (`event`, `slice_id`, and
        any optional extras such as `verdict_hash` or a producer-chosen
        `timestamp`); this method assigns the monotonic `seq`, the
        `feature_id`, the `record_hash`, the `correlation_id` (singleton
        shape) and -- unless ``fields`` already carries one -- the `timestamp`.

        F-13: a `timestamp` already present in ``fields`` is honoured (the
        spread below overrides the default), so the `at_review_verdict`
        producer's HMAC, computed over its own chosen timestamp, stays valid
        once the record is routed through this critical section.

        Migration quiesce (slice-01 singleton shape only): when env var
        ``NWAVE_AUDIT_LOG_MIGRATING=1`` is set, the singleton-shape writer
        appends a ``MigrationQuiesced`` diagnostic record in place of the
        caller-requested record. The diagnostic carries the would-be event +
        slice_id + feature_id so a post-migration audit can replay the
        attempted-but-quiesced writes. Legacy callers (slice-02 migrates them)
        are unaffected.
        """
        resolved_feature_id = self._resolve_feature_id(feature_id)

        if self._is_singleton and os.environ.get(_QUIESCE_ENV) == "1":
            # Migration-quiesce: refuse the caller-requested record AND
            # record the refusal as a diagnostic so a post-migration audit
            # can see what was attempted while the substrate was off-line.
            fields = {
                "event": "MigrationQuiesced",
                "slice_id": str(fields.get("slice_id", "")),
                "quiesced_event": str(fields.get("event", "")),
            }

        self.ledger_dir().mkdir(parents=True, exist_ok=True)
        path = self.ledger_path()

        # Open in append+read mode; the flock serialises the whole
        # read-seq -> append critical section against concurrent appenders.
        with open(path, "a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                handle.seek(0)
                next_seq = self._next_seq(handle.read())
                record: dict[str, Any] = {
                    "seq": next_seq,
                    "feature_id": resolved_feature_id,
                    "timestamp": datetime.now(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                    **fields,
                }
                # Singleton-shape records carry a derived correlation_id so
                # cross-feature audit queries can group adjacent records by
                # (feature, slice, dispatch). Legacy per-feature records do
                # NOT carry it -- backward-compat hash domain unchanged.
                if self._is_singleton:
                    record["correlation_id"] = derive_correlation_id(
                        resolved_feature_id,
                        str(record.get("slice_id", "")),
                        next_seq,
                    )
                record["record_hash"] = _record_hash(record)
                handle.write(
                    json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n"
                )
                handle.flush()
                return record
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _next_seq(existing_text: str) -> int:
        """The next monotonic `seq` -- one past the current terminal record.

        The first record gets `seq = 1`. A non-empty ledger whose final record
        is unparseable does not crash the writer here -- the integrity read
        (`read_records`) is the contract that fails closed on corruption; the
        writer keeps appending so the truncated tail stays detectable.
        """
        max_seq = 0
        for line in existing_text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            seq = record.get("seq") if isinstance(record, dict) else None
            if isinstance(seq, int) and seq > max_seq:
                max_seq = seq
        return max_seq + 1

    # --- read surface (M7(c) fail-closed integrity contract) ----------------

    def read_records(
        self,
        *,
        feature_id: str | None = None,
        slice_id: str | None = None,
        event_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Read every ledger record under the M7 fail-closed integrity contract.

        Raises `LedgerIntegrityViolation` -- never returns a silent undercount --
        when the ledger is:
          * `malformed-line`  -- a non-JSON or non-object line;
          * `truncated-tail`  -- a short / partial final line (a killed append);
          * `hash-mismatch`   -- a record whose `record_hash` does not match;
          * `seq-gap`         -- a gap in the gap-free monotonic `seq` sequence.

        An absent ledger file is NOT an integrity violation -- it returns an
        empty list (a feature with no recorded gates yet). The U4 markdown
        fallback keys on "ledger absent", distinct from "ledger corrupt".

        Optional filters (singleton shape -- ignored on the legacy per-feature
        substrate but harmless): records are post-filtered after the integrity
        sweep -- corruption is surfaced even when the offending record would
        have been filtered out, so a fail-closed read stays fail-closed.
        """
        path = self.ledger_path()
        if not path.is_file():
            return []

        raw = path.read_text(encoding="utf-8")
        records: list[dict[str, Any]] = []
        lines = raw.splitlines(keepends=True)

        for index, raw_line in enumerate(lines):
            is_final = index == len(lines) - 1
            stripped = raw_line.strip()
            if not stripped:
                continue

            line_number = index + 1
            # A final line lacking its newline terminator is a truncated tail
            # (a killed append, S17) -- unless the file as a whole ends in a
            # newline, in which case even the final content line is complete.
            if is_final and not raw_line.endswith("\n"):
                raise LedgerIntegrityViolation(
                    "truncated-tail",
                    f"AT-completion ledger has a truncated final line at "
                    f"line {line_number} (no newline terminator): {path}. "
                    f"See {_REPAIR_INSTRUCTIONS_PATH} for recovery steps.",
                    line_number=line_number,
                )

            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                detail = "truncated-tail" if is_final else "malformed-line"
                raise LedgerIntegrityViolation(
                    detail,
                    f"AT-completion ledger line {line_number} is not valid "
                    f"JSON ({exc}): {path}. See {_REPAIR_INSTRUCTIONS_PATH} "
                    f"for recovery steps.",
                    line_number=line_number,
                ) from exc

            if not isinstance(record, dict):
                raise LedgerIntegrityViolation(
                    "malformed-line",
                    f"AT-completion ledger line {line_number} is not a JSON "
                    f"object: {path}. See {_REPAIR_INSTRUCTIONS_PATH} for "
                    f"recovery steps.",
                    line_number=line_number,
                )

            self._verify_record_shape(record, line_number, path)
            self._verify_record_hash(record, line_number, path)
            records.append(record)

        self._verify_seq_monotonic(records, path)
        return self._apply_filters(
            records,
            feature_id=feature_id,
            slice_id=slice_id,
            event_type=event_type,
        )

    @staticmethod
    def _apply_filters(
        records: list[dict[str, Any]],
        *,
        feature_id: str | None,
        slice_id: str | None,
        event_type: str | None,
    ) -> list[dict[str, Any]]:
        """Post-integrity filter pass; preserves fail-closed semantics."""
        if feature_id is None and slice_id is None and event_type is None:
            return records
        filtered: list[dict[str, Any]] = []
        for record in records:
            if feature_id is not None and record.get("feature_id") != feature_id:
                continue
            if slice_id is not None and record.get("slice_id") != slice_id:
                continue
            if event_type is not None and record.get("event") != event_type:
                continue
            filtered.append(record)
        return filtered

    def records_by_correlation(self, correlation_id: str) -> list[dict[str, Any]]:
        """Every record sharing one correlation identifier (singleton shape).

        Group-by-correlation surfaces the slice's bracketing events (e.g. a
        carpaccio gate clear + the slice's verify event) as one cluster --
        the compounding capability the SSOT consolidation delivers.
        """
        return [
            record
            for record in self.read_records()
            if record.get("correlation_id") == correlation_id
        ]

    def all_feature_ids(self) -> frozenset[str]:
        """Every feature_id that has at least one record in the substrate.

        Convenience surface for cross-feature audit queries (singleton shape).
        Read under the M7 fail-closed integrity contract.
        """
        return frozenset(
            str(record.get("feature_id", ""))
            for record in self.read_records()
            if record.get("feature_id")
        )

    @staticmethod
    def _verify_record_shape(
        record: dict[str, Any], line_number: int, path: Path
    ) -> None:
        """Every record MUST carry the integrity-bearing fields + `record_hash`."""
        for field in (*_HASHED_FIELDS, "record_hash"):
            if field not in record:
                raise LedgerIntegrityViolation(
                    "malformed-line",
                    f"AT-completion ledger line {line_number} is missing the "
                    f"required '{field}' field: {path}. See "
                    f"{_REPAIR_INSTRUCTIONS_PATH} for recovery steps.",
                    line_number=line_number,
                )
        if not isinstance(record["seq"], int):
            raise LedgerIntegrityViolation(
                "malformed-line",
                f"AT-completion ledger line {line_number} has a non-integer "
                f"'seq': {path}. See {_REPAIR_INSTRUCTIONS_PATH} for "
                f"recovery steps.",
                line_number=line_number,
            )

    @staticmethod
    def _verify_record_hash(
        record: dict[str, Any], line_number: int, path: Path
    ) -> None:
        """A record whose `record_hash` mismatches its fields is a hand-edit."""
        if _record_hash(record) != record["record_hash"]:
            raise LedgerIntegrityViolation(
                "hash-mismatch",
                f"AT-completion ledger line {line_number} has a record_hash "
                f"that does not match its fields (tamper detected): {path}. "
                f"See {_REPAIR_INSTRUCTIONS_PATH} for recovery steps.",
                line_number=line_number,
            )

    @staticmethod
    def _verify_seq_monotonic(records: list[dict[str, Any]], path: Path) -> None:
        """The `seq` sequence MUST be gap-free monotonic (1, 2, 3, ...)."""
        for offset, record in enumerate(records):
            expected = offset + 1
            if record["seq"] != expected:
                # Offending line number = offset + 1 in the *records* list,
                # which corresponds to the line after `offset` non-blank
                # entries; the operator-readable diagnostic anchors on the
                # canonical 1-indexed record position.
                raise LedgerIntegrityViolation(
                    "seq-gap",
                    "AT-completion ledger has a gap in its monotonic seq "
                    f"sequence at line {offset + 1}: expected seq={expected}, "
                    f"found seq={record['seq']}: {path}. See "
                    f"{_REPAIR_INSTRUCTIONS_PATH} for recovery steps.",
                    line_number=offset + 1,
                )

    # --- reconciliation surface (M4 dispatch-count reconciliation) ----------

    def carpaccio_gate_slices(self) -> frozenset[str]:
        """The set of slice ids carrying a carpaccio gate event (M4 signal).

        Exactly one carpaccio gate event (`CarpaccioGateCleared` |
        `CarpaccioGateRejected`) is emitted per atdd_pure dispatch U1
        intercepts. The `/nw-deliver` phase-entry diagnostic counts these
        against the set of slices the plan expects to have been entered: a
        slice that was entered but has NO carpaccio gate event is a positive,
        mechanically-detectable "this slice was not gated" signal (M4 -- closes
        R3's invisible silent fall-through).

        Read under the M7 fail-closed integrity contract -- a corrupt ledger
        raises `LedgerIntegrityViolation` rather than yielding an undercount.
        """
        carpaccio_events = {
            "CarpaccioGateCleared",
            "CarpaccioGateRejected",
        }
        return frozenset(
            str(record["slice_id"])
            for record in self.read_records()
            if record["event"] in carpaccio_events
        )

    def verified_slices(self, *, feature_id: str | None = None) -> frozenset[str]:
        """The set of slice ids carrying a terminal `SliceCommitVerified` record.

        Consumed by the U1 carpaccio-order check (slice-(N-1) must be verified)
        and the U4 feature-end gate ("all slices shipped"). Read under the M7
        fail-closed integrity contract.

        Optional `feature_id=` filter (slice-02b) scopes the read to one
        feature in the singleton-shape substrate; ``None`` retains the
        cross-feature aggregate semantics.
        """
        return frozenset(
            str(record["slice_id"])
            for record in self.read_records(feature_id=feature_id)
            if record["event"] == "SliceCommitVerified"
        )

    def count_slice_commit_blocked(
        self,
        slice_id: str,
        pinned_commit_sha: str,
        block_reason: str,
        *,
        feature_id: str | None = None,
    ) -> int:
        """Count prior `SliceCommitBlocked` records identical on the bound key.

        The bounded-block terminal (oss-spine-watchdog slice-02, RCA root #68)
        counts how many times the G_COMMIT exit gate has ALREADY blocked this
        exact `(slice_id, pinned_commit_sha, block_reason)` so the handler can
        terminate on the Nth identical block instead of re-firing forever.

        Identity is keyed on all THREE fields (DISCUSS D-8 / D-4): a NEW commit
        SHA or a DIFFERENT block reason is genuine progress and RESETS the count
        (it does not match this key), so a working agent is never punished.

        Reason back-compat: a prior record that pre-dates the `block_reason`
        field (it carries no reason) is counted as matching ANY incoming reason
        -- the field-absent legacy record is reason-agnostic substrate, so the
        bound stays effective across the field's introduction. A prior carrying
        an EXPLICIT, DIFFERENT reason does NOT match (the reset axis of D-4).

        Read under the M7 fail-closed integrity contract -- a corrupt ledger
        raises `LedgerIntegrityViolation` rather than yielding an undercount
        that would let the re-fire loop run unbounded.
        """
        return sum(
            1
            for record in self.read_records(feature_id=feature_id)
            if record.get("event") == "SliceCommitBlocked"
            and str(record.get("slice_id")) == slice_id
            and record.get("pinned_commit_sha") == pinned_commit_sha
            and record.get("block_reason") in (None, block_reason)
        )

    def review_verdict_slices(self, *, feature_id: str | None = None) -> frozenset[str]:
        """The set of slice ids carrying a signed `ATReviewVerdict` record.

        The NUMERATOR of the G-DISTILL-EXIT gate completeness check
        (oss-hook-side-phase-injection slice-01): the gate allows the
        DISTILL->DELIVER transition only when every slice the feature-delta
        `[REF] Slice Plan` declares (the denominator =
        `_slice_plan_slice_ids`) appears in this set. Read under the M7
        fail-closed integrity contract -- a corrupt ledger raises
        `LedgerIntegrityViolation` rather than yielding an undercount that
        would close an incomplete feature.

        Optional `feature_id=` filter scopes the read to one feature in the
        singleton-shape substrate; ``None`` retains cross-feature semantics.
        """
        return frozenset(
            str(record["slice_id"])
            for record in self.read_records(feature_id=feature_id)
            if record["event"] == _AT_REVIEW_VERDICT
        )

    def feature_end_events(self, *, feature_id: str | None = None) -> frozenset[str]:
        """The set of feature-end cycle event names recorded for this feature (F1).

        slice-05 revision (Finding 1): the U4 feature-end gate asserts this set
        contains BOTH `EBatchRefactorCompleted` and `FeatureEndReviewVerdict`
        before the feature is closeable -- otherwise the feature-end cycle
        (batch refactor + deep review) never ran and feature-end blocks
        `FeatureEndCycleIncomplete`.

        Read under the M7 fail-closed integrity contract.

        Optional `feature_id=` filter (slice-02b) scopes the read to one
        feature in the singleton-shape substrate; ``None`` retains the
        cross-feature aggregate semantics.
        """
        return frozenset(
            str(record["event"])
            for record in self.read_records(feature_id=feature_id)
            if record["event"] in _FEATURE_END_EVENTS
        )

    def reconcile_dispatch_count(
        self, entered_slices: frozenset[str]
    ) -> frozenset[str]:
        """Slices entered by the plan but missing a carpaccio gate event.

        The M4 dispatch-count reconciliation: a non-empty result is the set of
        slices the `/nw-deliver` phase-entry diagnostic must block on -- they
        were entered but never gated (R3 silent fall-through made visible).
        """
        return entered_slices - self.carpaccio_gate_slices()

    def iter_records(self) -> Iterator[dict[str, Any]]:
        """Iterator alias for `read_records()` -- caller-readability surface."""
        yield from self.read_records()


class AtCompletionLedgerFactory(LedgerFactoryPort):
    """Concrete `LedgerFactoryPort` -- builds the per-feature `AtCompletionLedger`.

    AD-02 DIP fix: the conversion planner accepts this factory as an injected
    collaborator and calls `create_for_seeding` at ledger-seed time, so the
    domain never imports or constructs the concrete adapter. Constructed at the
    composition root (`des.cli.convert_to_atdd_pure`) and threaded down.
    """

    def create_for_seeding(
        self, feature_id: str, project_root: Path
    ) -> AtCompletionLedger:
        """Build the legacy per-feature ledger writer rooted at ``project_root``.

        Mirrors the prior in-domain construction verbatim
        (``AtCompletionLedger(feature_id=..., project_root=...)``) so the
        seeded JSONL records are byte-identical -- behaviour-preserving.
        """
        return AtCompletionLedger(feature_id=feature_id, project_root=project_root)


__all__ = [
    "EBATCH_REFACTOR_COMPLETED",
    "ENVIRONMENTAL_E2E_GATE_RAN",
    "ENVIRONMENTAL_E2E_VERIFIED",
    "FEATURE_END_REVIEW_VERDICT",
    "WALKING_SKELETON_GATE_RAN",
    "WALKING_SKELETON_TIER_VERIFIED",
    "WORKFLOW_PHASE_COMPLETED_DISTILL",
    "WORKFLOW_PHASE_COMPLETED_G_COMMIT",
    "AtCompletionLedger",
    "AtCompletionLedgerFactory",
    "LedgerIntegrityViolation",
    "derive_correlation_id",
]
