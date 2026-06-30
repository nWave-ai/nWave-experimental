"""Composition root for the oss-review-verdict-demotion S1 acceptance slice.

Mandate 13 (Driving-Port-Only Boundary) + Mandate-12 (Pillar 3). Wires the
PRODUCTION carpaccio-slice-gate CLI entry point
(``des.cli.carpaccio_slice_gate.main``) against a tmp_path repo fixture. The
gate is the Layer-3 composition-root driving port; business logic lives here as
the single source of truth and step bodies delegate to ``DemotionGateComposition``
methods. NO direct-domain import of ``check_at_review`` -- the slice drives the
gate through its argv ``main`` entry, exactly as the established carpaccio-gate
acceptance neighbour does (tests/scripts/cli/atdd_pure_carpaccio_slice_gate).

Layer 3 (subprocess/FS acceptance): the gate CLI is the driving port; the only
driven port is the real filesystem (tmp_path) -> @real-io. No PBT machinery
(Mandate 9 v2 / 11).

S1 RED note (fail-for-right-reason): on the pre-demotion tree
``check_at_review`` resolves a signing key FIRST and raises ``key-absent`` when
none is found (carpaccio_slice_gate.py:378-380). The S1 fixtures provision NO
key anywhere, so:
  * the KEYLESS_APPROVED scenario expects CLEARED but the pre-demotion gate
    rejects with reason ``key-absent`` -> the slice clear assertion fails
    (AssertionError -- missing functionality: the keyless path);
  * the LEGACY_WITH_HMAC scenario expects CLEARED but is likewise rejected
    ``key-absent`` -> AssertionError.
  * the ABSENT scenario expects reason ``absent``; pre-demotion the gate
    rejects ``key-absent`` FIRST (key resolution precedes record lookup), so
    the reason assertion fails (AssertionError -- the demotion must move the
    record-presence check ahead of -- and instead of -- the key check).
All three are deliberate missing-functionality REDs, not test bugs: every
dependency (state-delta port, pytest-bdd, production gate import) resolves
cleanly. The crafter greens them by removing the key resolution + ``_hmac_verifies``
and keeping the record checks (feature-delta S1 ADD/REMOVE).
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Production driving port (the DES entry gate). Imported as the composition-root
# driving surface, invoked via its argv ``main`` -- NOT a direct-domain call.
from des.cli.carpaccio_slice_gate import main as carpaccio_gate_main

from .domain_types import (
    FeatureId,
    GateVerdict,
    ReviewVerdictRecordState,
    SliceId,
)


# The carpaccio slice-size ceiling for the fixture repo's config. The S1 slice
# carries 2 ATs (within the N=3 ceiling) so the carpaccio decomposition half
# always clears and the AT-review half is exercised in isolation.
_CARPACCIO_SLICE_MAX = 3

# Signing-key env / file names -- referenced ONLY to guarantee they are ABSENT.
# S1 never provisions a key; these constants exist so ``run_gate`` can scrub the
# env var and assert no key file was written.
_SIGNING_KEY_ENV = "NWAVE_REVIEWER_SIGNING_KEY"
_SIGNING_KEY_FILE = ".nwave/secrets/reviewer-signing.key"

_REVIEWER_AGENT_ID = "nw-acceptance-designer-reviewer"


@dataclass
class GateResult:
    """Observable outcome of one carpaccio-slice-gate invocation."""

    exit_code: int
    output: str

    @property
    def verdict(self) -> GateVerdict:
        """Map the gate CLI exit code onto the user-observable S1 verdict."""
        if self.exit_code == 0:
            return GateVerdict.CLEARED
        return GateVerdict.AT_REVIEW_REJECTED

    @property
    def payload(self) -> dict[str, object]:
        """The single-line JSON object the gate emits (empty dict if none)."""
        for line in self.output.splitlines():
            stripped = line.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                with contextlib.suppress(json.JSONDecodeError):
                    return json.loads(stripped)
        return {}


@dataclass
class DemotionGateComposition:
    """Production-wired composition root for the S1 keyless-veto slice.

    ``repo_dir`` is a real tmp_path directory acting as the repository root.
    The feature-delta slice plan, the slice's ``.feature`` AT file, the
    AT-completion ledger and the workflow-mode config are provisioned via
    dedicated methods. NO reviewer signing key is ever written -- the
    post-demotion gate must clear a well-formed record without one.
    """

    repo_dir: Path
    feature_id: FeatureId = field(default=FeatureId("oss-review-verdict-demotion"))
    entering_slice: SliceId = field(default=SliceId("slice-01"))
    _slice_at_count: int = field(default=2)

    # --- paths ---------------------------------------------------------------

    @property
    def _feature_dir(self) -> Path:
        return self.repo_dir / "docs" / "feature" / self.feature_id

    @property
    def feature_delta_path(self) -> Path:
        return self._feature_dir / "feature-delta.md"

    @property
    def _acceptance_dir(self) -> Path:
        return (
            self.repo_dir / "tests" / "scripts" / "cli" / self.feature_id / "acceptance"
        )

    @property
    def feature_file_path(self) -> Path:
        return self._acceptance_dir / "slice.feature"

    @property
    def _nwave_dir(self) -> Path:
        return self.repo_dir / ".nwave"

    @property
    def config_path(self) -> Path:
        return self._nwave_dir / "config.yaml"

    @property
    def ledger_path(self) -> Path:
        return self._nwave_dir / "telemetry" / "atdd-pure" / f"{self.feature_id}.jsonl"

    @property
    def _signing_key_path(self) -> Path:
        return self.repo_dir / _SIGNING_KEY_FILE

    # --- Given: repo + slice plan + scenarios --------------------------------

    def create_keyless_repo(self, feature_id: FeatureId) -> None:
        """Create the repo skeleton with a valid in-size slice plan and NO key.

        Writes the feature-delta slice plan + the matching 2-scenario
        ``.feature`` file + the atdd_pure config. Provisions no signing key; the
        env var is scrubbed at gate-run time. This is the chained-narrative
        baseline (Pillar 2): every S1 scenario starts from this keyless repo.
        """
        self.feature_id = feature_id
        self._acceptance_dir.mkdir(parents=True, exist_ok=True)
        self._feature_dir.mkdir(parents=True, exist_ok=True)
        self._nwave_dir.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            yaml.safe_dump(
                {
                    "workflow": {"mode": "atdd_pure"},
                    "atdd_pure": {"carpaccio_slice_max": _CARPACCIO_SLICE_MAX},
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        self._write_feature_delta()
        self._write_feature_file()

    def _write_feature_delta(self) -> None:
        self.feature_delta_path.write_text(
            "# Feature Delta: oss-review-verdict-demotion fixture\n\n"
            "## Wave: DISCUSS / [REF] Slice Plan\n\n"
            "| Slice | Value statement | Status | Annotation | Justification |\n"
            "|-------|-----------------|--------|------------|---------------|\n"
            "| slice-01 | Operator clears a reviewed slice | pending | "
            "@walking-skeleton | thinnest end-to-end vertical |\n",
            encoding="utf-8",
        )

    def _write_feature_file(self) -> None:
        blocks = [
            f"@feature-{self.feature_id} @slice-01\n"
            f"Scenario: fixture scenario {n}\n"
            "  Given a fixture precondition\n"
            "  When the fixture action occurs\n"
            "  Then the fixture outcome holds\n"
            for n in range(1, self._slice_at_count + 1)
        ]
        self.feature_file_path.write_text(
            "Feature: oss-review-verdict-demotion fixture\n\n" + "\n".join(blocks),
            encoding="utf-8",
        )

    # --- Given: review verdict record ----------------------------------------

    def provision_review_record(self, state: ReviewVerdictRecordState) -> None:
        """Provision the AT-completion ledger for the requested S1 state.

        No signing key is written for any state -- the post-demotion gate must
        not need one.
        """
        provisioner = _RECORD_PROVISIONERS[state]
        provisioner(self)

    def _current_at_ids(self) -> list[str]:
        return [f"AT-{n}" for n in range(1, self._slice_at_count + 1)]

    def _normalized_at_bodies_hash(self) -> str:
        """SHA-256 over the slice's normalized AT bodies (content seal, keyless)."""
        bodies = sorted(
            "given a fixture precondition\n"
            "when the fixture action occurs\n"
            "then the fixture outcome holds"
            for _ in self._current_at_ids()
        )
        return hashlib.sha256("".join(bodies).encode("utf-8")).hexdigest()

    def _approved_record(self) -> dict[str, object]:
        """A well-formed keyless APPROVED record (no ``hmac_sha256`` field)."""
        return {
            "event": "ATReviewVerdict",
            "schema_version": "1.0.0",
            "slice_id": str(self.entering_slice),
            "verdict": "APPROVED",
            "reviewer_agent_id": _REVIEWER_AGENT_ID,
            "at_ids": self._current_at_ids(),
            "at_content_hash": self._normalized_at_bodies_hash(),
            "timestamp": "2026-06-11T00:00:00Z",
            "findings_summary": [],
        }

    def _write_ledger_record(self, record: dict[str, object]) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

    # --- When: run the gate --------------------------------------------------

    def run_gate(self) -> GateResult:
        """Invoke the production carpaccio-slice-gate CLI via its argv entry.

        The signing-key env var is scrubbed for the duration so NO key is
        resolvable from env. No key file is written by any S1 fixture, so the
        gate runs entirely keyless -- the S1 contract.
        """
        argv = [
            "--feature-id",
            str(self.feature_id),
            "--entering-slice",
            str(self.entering_slice),
            "--repo-root",
            str(self.repo_dir),
        ]
        buffer = io.StringIO()
        env_key = os.environ.pop(_SIGNING_KEY_ENV, None)
        try:
            with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
                exit_code = carpaccio_gate_main(argv)
        finally:
            if env_key is not None:
                os.environ[_SIGNING_KEY_ENV] = env_key
        return GateResult(exit_code=exit_code, output=buffer.getvalue())

    def no_signing_key_provisioned(self) -> bool:
        """True iff no signing key file exists and the env var is unset.

        The observable that backs hard contract (a)/(c): the gate cleared a
        record with NO key present, so it can have attempted no keyed
        verification. Asserted in the When-step universe and the legacy-tolerance
        Then-step.
        """
        return (
            not self._signing_key_path.exists()
            and os.environ.get(_SIGNING_KEY_ENV) is None
        )

    # --- universe ------------------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for assert_state_delta (Mandate 8).

        The carpaccio gate has a pure-function contract: it MUST mutate no file.
        The universe is every file the gate reads and could be tempted to write,
        plus the keyless invariant (no signing-key file may appear). The
        state-delta guard proves the gate reads without writing AND never
        materializes a key.
        """
        return {
            "feature_delta.bytes": _read_bytes_or_none(self.feature_delta_path),
            "feature_file.bytes": _read_bytes_or_none(self.feature_file_path),
            "ledger.exists": self.ledger_path.exists(),
            "ledger.bytes": _read_bytes_or_none(self.ledger_path),
            "config.bytes": _read_bytes_or_none(self.config_path),
            "signing_key.exists": self._signing_key_path.exists(),
        }


def _read_bytes_or_none(path: Path) -> object:
    return path.read_bytes() if path.exists() else None


# --- review-record provisioners ---------------------------------------------
# Module-level dispatch keeps each Given step body a single typed lookup + a
# single composition call (Mandate-12 criterion 3: no control flow in steps).


def _provision_keyless_approved(comp: DemotionGateComposition) -> None:
    comp._write_ledger_record(comp._approved_record())


def _provision_absent(comp: DemotionGateComposition) -> None:
    # The ledger exists but carries a non-verdict record only -- no
    # ATReviewVerdict for the entering slice.
    comp.ledger_path.parent.mkdir(parents=True, exist_ok=True)
    comp.ledger_path.write_text(
        json.dumps({"event": "PhaseBoundary", "slice_id": "slice-99", "phase": "A"})
        + "\n",
        encoding="utf-8",
    )


def _provision_legacy_with_hmac(comp: DemotionGateComposition) -> None:
    # A well-formed keyless APPROVED record that ALSO still carries the stray
    # pre-demotion ``hmac_sha256`` field (a record written by an older signing
    # producer, now operational). The post-demotion gate reads its present
    # fields and IGNORES the stray field -- no key resolution, no verify, no
    # parse error. The signature value here is deliberately a constant that
    # would NOT verify under any key, so a gate that DID attempt verification
    # would reject -- the PASS proves no verification was attempted.
    record = comp._approved_record()
    record["hmac_sha256"] = "0" * 64
    comp._write_ledger_record(record)


_RECORD_PROVISIONERS: dict[
    ReviewVerdictRecordState, callable[[DemotionGateComposition], None]
] = {
    ReviewVerdictRecordState.KEYLESS_APPROVED: _provision_keyless_approved,
    ReviewVerdictRecordState.ABSENT: _provision_absent,
    ReviewVerdictRecordState.LEGACY_WITH_HMAC: _provision_legacy_with_hmac,
}
