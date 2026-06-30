"""Composition root for the oss-review-verdict-demotion S3 acceptance slice.

Mandate 13 (Driving-Port-Only Boundary) + Mandate-12 (Pillar 3). Wires the
PRODUCTION DISCUSS PO-review veto-gate through ONE driving surface:

  * the REAL ``SubagentStopService.validate`` built via the production
    composition root ``des.adapters.drivers.hooks.service_factory
    .create_subagent_stop_service`` -- the DISCUSS gate-OUT entry point.

The service is the SUT. The arranged precondition state is (a) a ``discuss``
wave-active floor under ``project_root`` so the gate-OUT runs, (b) a
VALUE-BEARING feature-delta so the slice-07 STRUCTURAL gate-OUT PASSES and the
review-gate branch is what decides, and (c) the DiscussReviewVerdict ledger
record in the S3 shape under test -- or no record at all (the escape). NO
signing key is provisioned for any state; the post-demotion gate must decide
without one. The assertion is on the service's ``HookDecision`` (allow vs block
+ the ``DISCUSS_PO_REVIEW_*`` reason token).

This mirrors the established ``composition_slice_07b.py`` driving-port shape
(``create_subagent_stop_service`` + ``service.validate(SubagentStopContext)``)
but is KEYLESS: no signing key is seeded and no arrange-side HMAC is computed --
the S3 contract is "the record IS the control, the key is not". NO direct-domain
import of ``DiscussReviewGate.evaluate`` or ``_evaluate_discuss_po_review`` -- the
slice drives the gate through the production service ``validate`` entry.

Layer 3 (subprocess/FS acceptance): the service is the driving port; the only
driven port is the real filesystem (tmp_path) -> @real-io. No PBT machinery
(Mandate 9 v2 / 11).

S3 RED note (fail-for-right-reason): on the pre-demotion tree (tip a77815c3e)
``_evaluate_discuss_po_review`` resolves a signing key (``load_signing_key``)
and carries the line-372 escape ``if record is None and key is None: return
None``. The S3 fixtures provision NO key anywhere, so:

  * KEYLESS_ABSENT -- with no record and no key the today-gate takes the
    line-372 escape and returns None (the DISCUSS branch falls through, the
    atdd_pure return ALLOWS) -> the handoff is ALLOWED where the scenario
    expects a BLOCK -> AssertionError (missing functionality: the escape must
    close -- record-absence ALWAYS blocks, key absence disarms nothing);
  * KEYLESS_APPROVED_CURRENT -- with an approved keyless record and no key the
    today-gate resolves the key FIRST; ``DiscussReviewGate.evaluate`` returns
    INDETERMINATE("key-absent") -> the handoff is BLOCKED where the scenario
    expects ALLOW -> AssertionError (the demotion must drop the key check);
  * KEYLESS_NEEDS_REVISION -- with a needs-revision keyless record and no key
    the today-gate again returns INDETERMINATE("key-absent"), an indeterminate
    cause, not the reviewer veto -> the veto-naming assertion fails ->
    AssertionError (the demotion must read the keyless record and honor the
    veto).

All three are deliberate missing-functionality REDs, not test bugs: every
dependency (state-delta port, pytest-bdd, the production service composition
root) resolves cleanly (Mandate 7: RED, not BROKEN). The crafter greens them by
deleting the line-372 escape + the ``key`` resolution from
``_evaluate_discuss_po_review`` and dropping the ``key`` param + key-absent +
hmac-mismatch legs from ``DiscussReviewGate.evaluate`` (feature-delta S3
ADD/REMOVE), keeping record-absent -> INDETERMINATE("absent") and the
VETOED/PASS legs.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types_slice_03 import (
    DiscussGateDecision,
    DiscussReviewVerdictState,
    FeatureId,
)


_FEATURE_ID = "oss-review-verdict-demotion"
_FLOOR_FILE_REL = ".nwave/wave-active/active.json"
_FEATURE_DELTA_REL = f"docs/feature/{_FEATURE_ID}/feature-delta.md"
_LEDGER_REL = f".nwave/telemetry/atdd-pure/{_FEATURE_ID}.jsonl"

# Signing-key env / file -- referenced ONLY to guarantee they stay ABSENT. S3
# never provisions a key; the env var is scrubbed around the service run.
_SIGNING_KEY_ENV = "NWAVE_REVIEWER_SIGNING_KEY"
_SIGNING_KEY_FILE = ".nwave/secrets/reviewer-signing.key"

_DISCUSS_REVIEW_EVENT = "DiscussReviewVerdict"
_SCHEMA_VERSION = "1.0.0"
_REVIEWER_AGENT_ID = "nw-product-owner-reviewer"
_VERDICT_APPROVED = "approved"
_VERDICT_NEEDS_REVISION = "needs-revision"

# A value-bearing slice-plan table so the slice-07 STRUCTURAL gate-OUT PASSES
# and the NEW review-gate branch is the deciding check.
_VALUE_BEARING_SLICE_PLAN = """\
## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|---|---|---|---|---|
| slice-01 | A user can run the thing and see a confirmation | pending | @walking-skeleton | the thinnest e2e |
| slice-02 | A user gets a clear error when the input is malformed | pending | | the first error path |
"""

_FEATURE_DELTA_CONTENT = (
    f"# Feature Delta: {_FEATURE_ID}\n\n" + _VALUE_BEARING_SLICE_PLAN
)


@dataclass
class DiscussDecision:
    """Observable outcome of one SubagentStopService.validate invocation."""

    action: str
    reason: str | None

    @property
    def decision(self) -> DiscussGateDecision:
        return (
            DiscussGateDecision.ALLOWED
            if self.action == "allow"
            else DiscussGateDecision.BLOCKED
        )


@dataclass
class DiscussVetoComposition:
    """Production-wired composition root for the S3 keyless DISCUSS-veto slice.

    ``repo_dir`` is a real tmp_path directory acting as the repository root.
    The discuss wave-active floor, the value-bearing feature-delta and the
    DiscussReviewVerdict ledger record are provisioned via dedicated methods. NO
    reviewer signing key is ever written -- the post-demotion gate must decide
    without one. This is the chained-narrative baseline (Pillar 2): every S3
    scenario starts from this keyless discuss-wave return.
    """

    repo_dir: Path
    feature_id: FeatureId = field(default=FeatureId(_FEATURE_ID))

    # --- paths ---------------------------------------------------------------

    @property
    def _floor_path(self) -> Path:
        return self.repo_dir / _FLOOR_FILE_REL

    @property
    def feature_delta_path(self) -> Path:
        return self.repo_dir / _FEATURE_DELTA_REL

    @property
    def ledger_path(self) -> Path:
        return self.repo_dir / _LEDGER_REL

    @property
    def _signing_key_path(self) -> Path:
        return self.repo_dir / _SIGNING_KEY_FILE

    # --- Given: keyless discuss-wave return ----------------------------------

    def arm_keyless_discuss_return(self, feature_id: FeatureId) -> None:
        """Arm a discuss-wave return: floor + value-bearing delta, NO key.

        Writes the discuss wave-active floor (so the gate-OUT runs) and the
        value-bearing feature-delta (so the structural gate-OUT PASSES and the
        review-gate branch decides). Provisions no signing key; the env var is
        scrubbed at gate-run time.
        """
        self.feature_id = feature_id
        self._floor_path.parent.mkdir(parents=True, exist_ok=True)
        self._floor_path.write_text(
            json.dumps({"wave": "discuss", "provenance": "command"}),
            encoding="utf-8",
        )
        self.feature_delta_path.parent.mkdir(parents=True, exist_ok=True)
        self.feature_delta_path.write_text(_FEATURE_DELTA_CONTENT, encoding="utf-8")

    # --- Given: review verdict record ----------------------------------------

    def provision_review_verdict(self, state: DiscussReviewVerdictState) -> None:
        """Provision the DISCUSS review verdict ledger for the requested state.

        No signing key is written for any state -- the post-demotion gate must
        not need one. KEYLESS_ABSENT writes nothing (the reader returns None);
        the wired-reader / no-record / no-key combination IS the line-372 escape.
        """
        provisioner = _RECORD_PROVISIONERS[state]
        provisioner(self)

    def _current_feature_delta_hash(self) -> str:
        import hashlib

        return hashlib.sha256(self.feature_delta_path.read_bytes()).hexdigest()

    def _keyless_record(self, verdict: str) -> dict[str, object]:
        """A well-formed keyless DiscussReviewVerdict (no ``hmac_sha256`` field).

        Carries every present field the post-demotion gate reads -- schema, the
        feature-delta artefact seal (keyless SHA-256), the reviewer identity and
        the verdict -- and NO signature. The artefact seal matches the seeded
        value-bearing feature-delta, so a post-demotion gate that drops only the
        keyed checks finds the record current.
        """
        return {
            "event": _DISCUSS_REVIEW_EVENT,
            "schema_version": _SCHEMA_VERSION,
            "feature_id": str(self.feature_id),
            "verdict": verdict,
            "reviewer_agent_id": _REVIEWER_AGENT_ID,
            "feature_delta_hash": self._current_feature_delta_hash(),
            "timestamp": "2026-06-11T00:00:00+00:00",
        }

    def _write_ledger_record(self, record: dict[str, object]) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

    # --- When: run the gate --------------------------------------------------

    def run_discuss_gate(self) -> DiscussDecision:
        """Drive the REAL SubagentStopService.validate via the production root.

        Runs an atdd_pure discuss-wave return (execution-log-free path). The
        discuss floor + value-bearing delta + (optional) keyless verdict record
        under ``repo_dir`` are the arranged preconditions the review-gate branch
        reads. The signing-key env var is scrubbed for the duration AND no key
        file is written, so the gate runs entirely keyless -- the S3 contract.
        """
        from des.adapters.drivers.hooks import service_factory
        from des.ports.driver_ports.subagent_stop_port import SubagentStopContext

        prev_cwd = Path.cwd()
        env_key = os.environ.pop(_SIGNING_KEY_ENV, None)
        try:
            os.chdir(self.repo_dir)
            service = service_factory.create_subagent_stop_service()
            decision = service.validate(
                SubagentStopContext(
                    execution_log_path="",
                    project_id=str(self.feature_id),
                    step_id="",
                    cwd=str(self.repo_dir),
                    mode="atdd_pure",
                    slice_id="slice-03",
                    atdd_pure_phase="D_REFACTOR_COMMIT",
                )
            )
        finally:
            os.chdir(prev_cwd)
            if env_key is not None:
                os.environ[_SIGNING_KEY_ENV] = env_key
        return DiscussDecision(action=decision.action, reason=decision.reason)

    def no_signing_key_provisioned(self) -> bool:
        """True iff no signing key file exists and the env var is unset.

        The observable backing hard contract (a): the gate decided with NO key
        present, so key absence cannot have disarmed it.
        """
        return (
            not self._signing_key_path.exists()
            and os.environ.get(_SIGNING_KEY_ENV) is None
        )

    # --- universe ------------------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for assert_state_delta (Mandate 8).

        The DISCUSS gate is a DECISION over read state -- it mutates no file. The
        universe is every artefact the gate reads (the floor, the feature-delta,
        the ledger) plus the keyless invariant (no signing-key file may appear).
        The state-delta guard proves the gate reads without writing AND never
        materializes a key. The decision itself (allow/block) is asserted by the
        Then steps off the returned HookDecision, not via the universe.
        """
        return {
            "floor.bytes": _read_bytes_or_none(self._floor_path),
            "feature_delta.bytes": _read_bytes_or_none(self.feature_delta_path),
            "ledger.exists": self.ledger_path.exists(),
            "ledger.bytes": _read_bytes_or_none(self.ledger_path),
            "signing_key.exists": self._signing_key_path.exists(),
        }


def _read_bytes_or_none(path: Path) -> object:
    return path.read_bytes() if path.exists() else None


# --- review-record provisioners ---------------------------------------------
# Module-level dispatch keeps each Given step body a single typed lookup + a
# single composition call (Mandate-12 criterion 3: no control flow in steps).


def _provision_keyless_absent(comp: DiscussVetoComposition) -> None:
    # The ledger exists but carries a non-verdict record only -- no
    # DiscussReviewVerdict for the feature. The reader returns None; combined
    # with no key, this is the line-372 escape (today: pass blind).
    comp.ledger_path.parent.mkdir(parents=True, exist_ok=True)
    comp.ledger_path.write_text(
        json.dumps({"event": "PhaseBoundary", "slice_id": "slice-99", "phase": "A"})
        + "\n",
        encoding="utf-8",
    )


def _provision_keyless_approved_current(comp: DiscussVetoComposition) -> None:
    comp._write_ledger_record(comp._keyless_record(_VERDICT_APPROVED))


def _provision_keyless_needs_revision(comp: DiscussVetoComposition) -> None:
    comp._write_ledger_record(comp._keyless_record(_VERDICT_NEEDS_REVISION))


_RECORD_PROVISIONERS: dict[
    DiscussReviewVerdictState, Callable[[DiscussVetoComposition], None]
] = {
    DiscussReviewVerdictState.KEYLESS_ABSENT: _provision_keyless_absent,
    DiscussReviewVerdictState.KEYLESS_APPROVED_CURRENT: (
        _provision_keyless_approved_current
    ),
    DiscussReviewVerdictState.KEYLESS_NEEDS_REVISION: _provision_keyless_needs_revision,
}
