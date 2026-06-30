"""Composition root for the oss-review-verdict-demotion S2 acceptance slice.

Mandate 13 (Driving-Port-Only Boundary) + Mandate-12 (Pillar 3). Wires the
PRODUCTION at-review-verdict producer through TWO driving surfaces:

  * the producer's own argv entry ``des.cli.at_review_verdict.main`` (DIRECT),
  * the ``des`` single-entry dispatcher ``des.cli.__main__.main`` invoked with
    ``record-at-review-verdict ...`` (DISPATCHER -- the D-register seam).

Both are Layer-3 composition-root driving ports invoked via their argv ``main``
entries -- NO direct-domain call of ``record_at_review_verdict`` and NO
direct-domain call of ``check_at_review``. Business logic lives here as the
single source of truth; step bodies delegate to ``ProducerComposition`` methods.

Layer 3 (subprocess/FS acceptance): the producer + dispatcher are the driving
ports; the only driven port is the real filesystem (tmp_path) -> @real-io. No
PBT machinery (Mandate 9 v2 / 11): the producer's observable effect is one
appended ledger line, asserted as a named example, not a Hypothesis @given.

S2 RED note (fail-for-right-reason): on the pre-demotion tree
``record_at_review_verdict`` (at_review_verdict.py:95) writes ``hmac_sha256``
via ``compute_verdict_hmac(record, require_signing_key(repo_root))``.
``require_signing_key`` raises ``AssertionError`` when no key is resolvable.
The S2 fixtures provision NO key, so:

  * the KEYLESS-WRITE round-trip scenario runs the producer keyless -> the
    pre-demotion producer raises ``AssertionError`` ("reviewer signing key
    unresolvable") before any record is written -> the producer never exits 0
    and the ledger gains no record -> the "recorded" assertion fails
    (AssertionError -- missing functionality: the keyless write path);
  * the NO-SIGNATURE-FIELD scenario asserts the written record has NO
    ``hmac_sha256`` field; pre-demotion the producer either raises (keyless) or
    -- if a key were present -- would write the field, so the field-absence
    assertion fails (AssertionError -- the demotion must drop the field write);
  * the DISCOVERABLE scenario runs ``des record-at-review-verdict``; the
    dispatcher ``_REGISTRY`` does NOT carry that row pre-D-register, so the
    dispatcher exits non-zero (argparse: invalid choice) and writes no record
    -> the "recorded" assertion fails (AssertionError -- the demotion must
    register the subcommand).

All three are deliberate missing-functionality REDs, not test bugs: every
dependency (state-delta port, pytest-bdd, production producer + dispatcher
imports) resolves cleanly. The crafter greens them by dropping the
``hmac_sha256`` write + the key import (S2 ADD/REMOVE) and adding the
``record-at-review-verdict`` ``_REGISTRY`` row + its mirror.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Production driving ports (the producer + the des dispatcher). Imported as the
# composition-root driving surfaces, invoked via their argv ``main`` entries --
# NOT direct-domain calls.
from des.cli.__main__ import main as des_dispatcher_main
from des.cli.at_review_verdict import main as producer_main

# The already-keyless consumer gate (slice-01 shipped) is invoked through its
# OWN argv entry for the round-trip witness -- again via ``main``, never a
# direct ``check_at_review`` import.
from des.cli.carpaccio_slice_gate import main as carpaccio_gate_main

from .domain_types_slice_02 import (
    FeatureId,
    ProducerEntryPoint,
    SliceId,
)


_CARPACCIO_SLICE_MAX = 3

# Signing-key env / file -- referenced ONLY to guarantee they stay ABSENT.
# S2 never provisions a key; the env var is scrubbed at producer-run time.
_SIGNING_KEY_ENV = "NWAVE_REVIEWER_SIGNING_KEY"
_SIGNING_KEY_FILE = ".nwave/secrets/reviewer-signing.key"

_REVIEWER_AGENT_ID = "nw-acceptance-designer-reviewer"
_DISPATCHER_SUBCOMMAND = "record-at-review-verdict"


@dataclass
class ProducerRun:
    """Observable outcome of one producer (or dispatcher) invocation."""

    exit_code: int
    output: str


@dataclass
class GateRun:
    """Observable outcome of the round-trip carpaccio-gate invocation."""

    exit_code: int
    output: str

    @property
    def cleared(self) -> bool:
        return self.exit_code == 0

    @property
    def payload(self) -> dict[str, object]:
        for line in self.output.splitlines():
            stripped = line.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                with contextlib.suppress(json.JSONDecodeError):
                    return json.loads(stripped)
        return {}


@dataclass
class ProducerComposition:
    """Production-wired composition root for the S2 keyless-producer slice.

    ``repo_dir`` is a real tmp_path directory acting as the repository root.
    The feature-delta slice plan, the slice's ``.feature`` AT file, and the
    workflow-mode config are provisioned so the producer's own
    ``_slice_at_derivation`` (which reuses the carpaccio gate's scenario
    parser) resolves the entering slice's ``at_ids`` + ``at_content_hash``. NO
    reviewer signing key is ever written -- the post-demotion producer must
    write a well-formed record without one.
    """

    repo_dir: Path
    feature_id: FeatureId = field(default=FeatureId("oss-review-verdict-demotion"))
    entering_slice: SliceId = field(default=SliceId("slice-02"))
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

    # --- Given: repo + slice plan + scenarios + empty ledger -----------------

    def create_keyless_repo(self, feature_id: FeatureId) -> None:
        """Create the repo skeleton with a valid in-size slice plan and NO key.

        Writes the feature-delta slice plan + the matching 2-scenario
        ``.feature`` file + the atdd_pure config + an empty AT-completion
        ledger. Provisions no signing key; the env var is scrubbed at
        producer-run time. This is the chained-narrative baseline (Pillar 2):
        every S2 scenario starts from this keyless repo with no recorded
        verdict yet.
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
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.ledger_path.write_text("", encoding="utf-8")

    def _write_feature_delta(self) -> None:
        self.feature_delta_path.write_text(
            "# Feature Delta: oss-review-verdict-demotion fixture\n\n"
            "## Wave: DISCUSS / [REF] Slice Plan\n\n"
            "| Slice | Value statement | Status | Annotation | Justification |\n"
            "|-------|-----------------|--------|------------|---------------|\n"
            "| slice-02 | Operator records a keyless reviewed verdict | pending | "
            "(none) | producer closes the gate round-trip |\n",
            encoding="utf-8",
        )

    def _write_feature_file(self) -> None:
        blocks = [
            f"@feature-{self.feature_id} @slice-02\n"
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

    # --- When: run the producer ----------------------------------------------

    def record_approved_verdict(self, via: ProducerEntryPoint) -> ProducerRun:
        """Record an APPROVED verdict keyless via the chosen driving surface.

        DIRECT     -> ``des.cli.at_review_verdict.main`` argv entry.
        DISPATCHER -> ``des.cli.__main__.main`` with ``record-at-review-verdict``
                      as the first positional (the D-register discoverable path).

        The signing-key env var is scrubbed for the duration and no key file is
        written, so the producer runs entirely keyless -- the S2 contract.
        """
        producer_args = [
            "--feature-id",
            str(self.feature_id),
            "--slice-id",
            str(self.entering_slice),
            "--verdict",
            "APPROVED",
            "--reviewer-agent-id",
            _REVIEWER_AGENT_ID,
            "--repo-root",
            str(self.repo_dir),
        ]
        argv, entry = _RESOLVE_ENTRY[via](producer_args)
        buffer = io.StringIO()
        env_key = os.environ.pop(_SIGNING_KEY_ENV, None)
        try:
            with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
                exit_code = _invoke_entry(entry, argv)
        finally:
            if env_key is not None:
                os.environ[_SIGNING_KEY_ENV] = env_key
        return ProducerRun(exit_code=exit_code, output=buffer.getvalue())

    # --- When (round-trip witness): run the already-keyless gate -------------

    def run_consumer_gate(self) -> GateRun:
        """Invoke the slice-01 keyless carpaccio gate over the written record.

        The walking-skeleton round-trip: the producer wrote the verdict, the
        already-keyless gate (slice-01, HEAD) reads it on its present fields and
        clears the slice -- proving producer and consumer agree on the keyless
        record shape end-to-end.
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
        return GateRun(exit_code=exit_code, output=buffer.getvalue())

    # --- Then: observe the ledger --------------------------------------------

    def recorded_verdicts(self) -> list[dict[str, object]]:
        """All ATReviewVerdict records in the ledger for the entering slice."""
        records: list[dict[str, object]] = []
        if not self.ledger_path.is_file():
            return records
        for line in self.ledger_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            record = json.loads(stripped)
            if record.get("event") == "ATReviewVerdict" and record.get(
                "slice_id"
            ) == str(self.entering_slice):
                records.append(record)
        return records

    def recorded_verdict_count(self) -> int:
        return len(self.recorded_verdicts())

    def latest_record_carries_signature_field(self) -> bool:
        """True iff the latest recorded verdict still carries ``hmac_sha256``.

        Hard contract: the keyless producer drops the field. The S2 assertion
        is that this returns False -- the written record has no signature field
        at all (not an empty one, ABSENT).
        """
        verdicts = self.recorded_verdicts()
        if not verdicts:
            return False
        return "hmac_sha256" in verdicts[-1]

    def latest_record_binds_reviewer_and_seal(self) -> bool:
        """True iff the latest record carries the veto-relevant present fields.

        The demotion DROPS the signature but KEEPS every veto field: reviewer
        identity, the AT-set binding, and the content seal. This proves the
        record is still a well-formed APPROVED verdict the gate will trust.
        """
        verdicts = self.recorded_verdicts()
        if not verdicts:
            return False
        record = verdicts[-1]
        return (
            record.get("verdict") == "APPROVED"
            and bool(record.get("reviewer_agent_id"))
            and isinstance(record.get("at_ids"), list)
            and bool(record.get("at_content_hash"))
            and bool(record.get("timestamp"))
        )

    def no_signing_key_provisioned(self) -> bool:
        """True iff no signing key file exists and the env var is unset."""
        return (
            not self._signing_key_path.exists()
            and os.environ.get(_SIGNING_KEY_ENV) is None
        )

    # --- universe ------------------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for assert_state_delta (Mandate 8).

        The producer's observable effect is one new keyless verdict line in the
        ledger; nothing else may move, and NO signing-key file may appear. The
        universe is the verdict count, the signature-presence boolean on the
        latest recorded verdict (so the no-signature contract is delta-visible
        without coupling to the ledger's full key schema), and the keyless
        invariant (no signing-key file). All three are port-exposed observables.
        """
        return {
            "ledger.verdict_count": self.recorded_verdict_count(),
            "ledger.latest_record_has_signature": (
                self.latest_record_carries_signature_field()
            ),
            "signing_key.exists": self._signing_key_path.exists(),
        }


# --- entry-point invocation --------------------------------------------------


def _invoke_entry(entry: object, argv: list[str]) -> int:
    """Invoke a CLI ``main`` entry and capture its exit code.

    The des dispatcher rejects an UNREGISTERED subcommand by calling
    ``sys.exit(2)`` (argparse ``invalid choice``) -- the observable signal that
    the D-register seam is absent pre-demotion. Capturing the ``SystemExit``
    here turns it into a plain exit code so the Then-step's verdict-count
    assertion fires as a clean ``AssertionError`` (missing functionality: the
    subcommand is not registered), never a raw ``SystemExit`` escaping the
    step (matches the slice-01 gate-run capture pattern). A ``SystemExit`` with
    no code is normalized to 0.
    """
    try:
        return entry(argv)  # type: ignore[operator,no-any-return]
    except SystemExit as exc:  # argparse invalid-choice on an unregistered row
        return (
            int(exc.code)
            if isinstance(exc.code, int)
            else (0 if exc.code is None else 1)
        )


# --- entry-point resolution --------------------------------------------------
# Module-level dispatch keeps each When step body a single typed lookup + a
# single composition call (Mandate-12 criterion 3: no control flow in steps).


def _direct_entry(producer_args: list[str]) -> tuple[list[str], object]:
    return producer_args, producer_main


def _dispatcher_entry(producer_args: list[str]) -> tuple[list[str], object]:
    # The des dispatcher consumes the subcommand as the first positional and
    # passes the remaining argv through verbatim (DDD-6 passthrough).
    return [_DISPATCHER_SUBCOMMAND, *producer_args], des_dispatcher_main


_RESOLVE_ENTRY: dict[ProducerEntryPoint, object] = {
    ProducerEntryPoint.DIRECT: _direct_entry,
    ProducerEntryPoint.DISPATCHER: _dispatcher_entry,
}
