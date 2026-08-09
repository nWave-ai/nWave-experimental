"""Composition root for the carpaccio-slice-gate acceptance slice.

ADR-028 D2-bis + ADR-029 D5 / slice-03 (Mandate-12, Pillar 3). Wires the
PRODUCTION carpaccio-slice-gate CLI entry point
(``des.cli.carpaccio_slice_gate.main``) against a tmp_path repo fixture.
Business logic lives here as the single source of truth; step bodies delegate
to ``CarpaccioGateComposition`` methods and never inline logic.

Layer 3 (subprocess/FS acceptance): the gate CLI is the driving port; the only
driven port is the real filesystem (tmp_path). No PBT machinery (Mandate 9/11).

Pure-function contract (ADR-028 D2-bis): the gate reads the feature-delta +
``.feature`` files + the AT-completion ledger and returns a verdict (exit code
+ JSON); it performs NO filesystem mutation. The composition's
``capture_universe`` snapshots the files the gate could be tempted to touch so
the When-step state-delta guard proves the read-only contract (Mandate 8).
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

from des.cli.carpaccio_slice_gate import main as carpaccio_gate_main

from .domain_types import (
    ATReviewRecordState,
    FeatureId,
    GateVerdict,
    SliceId,
    SlicePlanShape,
)


# Carpaccio slice-size ceiling for the fixture repo's config
# (.nwave/config.yaml:atdd_pure.carpaccio_slice_max). Slice-03's own AT group
# is a coupled group of 4 > N=3, so the fixtures must exercise both the N
# ceiling and the @coupled escape against this value.
_CARPACCIO_SLICE_MAX = 3

# Signing-key env / file names -- referenced ONLY to guarantee they are ABSENT
# after the demotion. No key is provisioned for any fixture state.
_SIGNING_KEY_ENV = "NWAVE_REVIEWER_SIGNING_KEY"
_SIGNING_KEY_FILE = ".nwave/secrets/reviewer-signing.key"


@dataclass
class GateResult:
    """Observable outcome of one carpaccio-slice-gate invocation."""

    exit_code: int
    output: str

    @property
    def verdict(self) -> GateVerdict:
        """Map the gate CLI exit code onto the user-observable verdict."""
        return {
            0: GateVerdict.CLEARED,
            1: GateVerdict.SLICE_PLAN_MISSING,
            2: GateVerdict.MALFORMED_INPUT,
            44: GateVerdict.SLICE_TOO_LARGE,
            45: GateVerdict.AT_REVIEW_REJECTED,
        }.get(self.exit_code, GateVerdict.MALFORMED_INPUT)

    @property
    def payload(self) -> dict[str, object]:
        """The single-line JSON object the gate emits to stdout.

        Returns an empty dict if no JSON line was produced (kept side-effect
        free so a malformed-output assertion can be made by the step).
        """
        for line in self.output.splitlines():
            stripped = line.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                with contextlib.suppress(json.JSONDecodeError):
                    return json.loads(stripped)
        return {}


@dataclass
class CarpaccioGateComposition:
    """Production-wired composition root for the carpaccio-slice-gate slice.

    ``repo_dir`` is a real tmp_path directory acting as the repository root.
    The feature-delta slice plan, the slice's ``.feature`` AT files, the
    AT-completion ledger, the workflow-mode config, and the reviewer signing
    key are provisioned via dedicated methods so each scenario builds exactly
    the project state it needs. The gate CLI is then invoked through its argv
    entry point against this repo.
    """

    repo_dir: Path
    feature_id: FeatureId = field(default=FeatureId("atdd-pure-demo"))
    entering_slice: SliceId = field(default=SliceId("slice-01"))
    _slice_at_count: int = field(default=1)

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
        """AT-completion ledger for this feature (ADR-028 D3)."""
        return self._nwave_dir / "telemetry" / "atdd-pure" / f"{self.feature_id}.jsonl"

    @property
    def _signing_key_path(self) -> Path:
        return self.repo_dir / _SIGNING_KEY_FILE

    # --- Given: repo + config ------------------------------------------------

    def create_repo(self, feature_id: FeatureId) -> None:
        """Create the repo skeleton: feature dir, acceptance dir, config."""
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

    # --- Given: slice plan ---------------------------------------------------

    def provision_slice_plan(self, shape: SlicePlanShape) -> None:
        """Write the feature-delta with a slice plan of the requested shape.

        The shape selects both the entering slice's AT count and the table
        well-formedness; the matching ``.feature`` file is written so the gate
        sees a consistent (or, for ORPHAN_FEATURE_TAG, deliberately
        inconsistent) tag set.
        """
        builder = _SLICE_PLAN_BUILDERS[shape]
        builder(self)

    def _write_feature_delta(self, slice_rows: str) -> None:
        """Write a feature-delta carrying the given slice-plan table rows."""
        self.feature_delta_path.write_text(
            "# Feature Delta: carpaccio gate fixture\n\n"
            "## Wave: DISCUSS / [REF] Slice Plan\n\n"
            "| Slice | Value statement | Status | Annotation | Justification |\n"
            "|-------|-----------------|--------|------------|---------------|\n"
            f"{slice_rows}\n",
            encoding="utf-8",
        )

    def _write_feature_file(self, slice_tag: str, scenario_count: int) -> None:
        """Write a ``.feature`` file with ``scenario_count`` tagged scenarios."""
        blocks = [
            f"@{slice_tag}\n"
            f"Scenario: fixture scenario {n}\n"
            "  Given a fixture precondition\n"
            "  When the fixture action occurs\n"
            "  Then the fixture outcome holds\n"
            for n in range(1, scenario_count + 1)
        ]
        self.feature_file_path.write_text(
            "Feature: carpaccio gate fixture\n\n" + "\n".join(blocks),
            encoding="utf-8",
        )

    def _write_coupled_feature_file(self, scenario_count: int) -> None:
        """Write a ``.feature`` file whose scenarios all carry @coupled tags."""
        blocks = [
            f"@slice-01 @coupled:fixture-group\n"
            f"Scenario: coupled fixture scenario {n}\n"
            "  Given a fixture precondition\n"
            "  When the fixture action occurs\n"
            "  Then the fixture outcome holds\n"
            for n in range(1, scenario_count + 1)
        ]
        self.feature_file_path.write_text(
            "Feature: carpaccio gate fixture\n\n" + "\n".join(blocks),
            encoding="utf-8",
        )

    # --- Given: AT-review verdict record ------------------------------------

    def provision_at_review_record(self, state: ATReviewRecordState) -> None:
        """Provision the AT-completion ledger for assertion 5.

        Each state isolates exactly one assertion-5 outcome (the APPROVED
        happy path or one of the four closed rejection reasons). No signing
        key is provisioned for any state -- the post-demotion gate is keyless.
        """
        provisioner = _AT_REVIEW_PROVISIONERS[state]
        provisioner(self)

    def _current_at_ids(self) -> list[str]:
        """The @slice-NN scenario id set the gate computes for the slice."""
        return [f"AT-{n}" for n in range(1, self._slice_at_count + 1)]

    def _normalized_at_bodies_hash(self) -> str:
        """SHA-256 over the slice's normalized AT bodies (ADR-029 D5 Hole-fix)."""
        bodies = sorted(
            "given a fixture precondition\n"
            "when the fixture action occurs\n"
            "then the fixture outcome holds"
            for _ in self._current_at_ids()
        )
        return hashlib.sha256("".join(bodies).encode("utf-8")).hexdigest()

    def _build_record(
        self,
        verdict: str,
        at_ids: list[str],
        at_content_hash: str,
    ) -> dict[str, object]:
        """Build a keyless ATReviewVerdict record for the slice."""
        return {
            "event": "ATReviewVerdict",
            "schema_version": "1.0.0",
            "slice_id": str(self.entering_slice),
            "verdict": verdict,
            "reviewer_agent_id": "nw-acceptance-designer-reviewer",
            "at_ids": at_ids,
            "at_content_hash": at_content_hash,
            "timestamp": "2026-05-20T00:00:00Z",
            "findings_summary": [],
        }

    def _write_ledger_record(self, record: dict[str, object]) -> None:
        """Append one ATReviewVerdict record to the AT-completion ledger."""
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

    # --- When: run the gate --------------------------------------------------

    def run_gate(self) -> GateResult:
        """Invoke the production carpaccio-slice-gate CLI via its argv entry.

        The signing-key env var is scrubbed so no key leaks in from the test
        runner's environment. The post-demotion gate never resolves a key.
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

    # --- universe ------------------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for assert_state_delta (Mandate 8).

        The carpaccio gate has a pure-function contract (ADR-028 D2-bis): it
        MUST NOT mutate any file. The universe is the set of files the gate
        reads and could be tempted to write -- the state-delta guard proves the
        gate reads without writing.
        """
        return {
            "feature_delta.exists": self.feature_delta_path.exists(),
            "feature_delta.bytes": _read_bytes_or_none(self.feature_delta_path),
            "feature_file.exists": self.feature_file_path.exists(),
            "feature_file.bytes": _read_bytes_or_none(self.feature_file_path),
            "ledger.exists": self.ledger_path.exists(),
            "ledger.bytes": _read_bytes_or_none(self.ledger_path),
            "config.bytes": _read_bytes_or_none(self.config_path),
        }


def _read_bytes_or_none(path: Path) -> object:
    """Return the file's bytes, or None when the file is absent."""
    return path.read_bytes() if path.exists() else None


# --- slice-plan fixture builders --------------------------------------------
# Module-level dispatch keeps each Given step body a single typed lookup + a
# single composition call (Mandate-12 criterion 3: no control flow in steps).


def _build_valid_in_size(comp: CarpaccioGateComposition) -> None:
    comp._slice_at_count = 2
    comp._write_feature_delta(
        "| slice-01 | Operator previews a plan | pending | @walking-skeleton | "
        "thinnest end-to-end vertical |"
    )
    comp._write_feature_file("slice-01", 2)


def _build_over_n_unannotated(comp: CarpaccioGateComposition) -> None:
    comp._slice_at_count = 5
    comp._write_feature_delta(
        "| slice-01 | Operator previews a plan | pending | @walking-skeleton | "
        "thinnest end-to-end vertical |"
    )
    comp._write_feature_file("slice-01", 5)


def _build_over_n_coupled(comp: CarpaccioGateComposition) -> None:
    comp._slice_at_count = 4
    comp._write_feature_delta(
        "| slice-01 | Operator previews a plan | pending | @walking-skeleton | "
        "indivisible coupled gate contract -- four ATs assert one behaviour |"
    )
    comp._write_coupled_feature_file(4)


def _build_malformed_table(comp: CarpaccioGateComposition) -> None:
    comp._slice_at_count = 1
    # A well-formed table whose lone data row carries NO cell matching the
    # slice-NN identifier pattern -- the row is unresolvable to any slice.
    # Under the column-count-tolerant parser (C10) a 4-column table is now
    # VALID, so column count no longer signals malformedness; a row with no
    # resolvable slice-id is the input that the tolerant parser STILL rejects
    # (carpaccio_format._build_slice_rows: slice_index is None -> exit 2,
    # cause "the slice-plan table").
    comp.feature_delta_path.write_text(
        "# Feature Delta: carpaccio gate fixture\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
        "| not-a-slice | Operator previews a plan | pending | | |\n",
        encoding="utf-8",
    )
    comp._write_feature_file("slice-01", 1)


def _build_ordered_before_ws(comp: CarpaccioGateComposition) -> None:
    # Carpaccio assertion 3: the @walking-skeleton slice must be ordered first.
    # Here slice-02 is the entering slice and is listed BEFORE the
    # @walking-skeleton slice-01 -- a walking-skeleton-first ordering violation.
    comp.entering_slice = SliceId("slice-02")
    comp._slice_at_count = 1
    comp._write_feature_delta(
        "| slice-02 | Operator applies a plan | pending | | |\n"
        "| slice-01 | Operator previews a plan | pending | @walking-skeleton | "
        "thinnest end-to-end vertical |"
    )
    comp._write_feature_file("slice-02", 1)


def _build_untagged_scenario(comp: CarpaccioGateComposition) -> None:
    # Carpaccio assertion 2: every authored .feature scenario must carry exactly
    # one @slice-NN tag. Here the entering slice is correctly tagged but a
    # SECOND authored scenario carries no @slice-NN tag at all -- an incremental
    # total-coverage violation (an orphan, un-sliced AT).
    comp._slice_at_count = 1
    comp._write_feature_delta(
        "| slice-01 | Operator previews a plan | pending | @walking-skeleton | "
        "thinnest end-to-end vertical |"
    )
    comp.feature_file_path.write_text(
        "Feature: carpaccio gate fixture\n\n"
        "@slice-01\n"
        "Scenario: a tagged authored scenario\n"
        "  Given a fixture precondition\n"
        "  When the fixture action occurs\n"
        "  Then the fixture outcome holds\n\n"
        "Scenario: an untagged authored scenario\n"
        "  Given a fixture precondition\n"
        "  When the fixture action occurs\n"
        "  Then the fixture outcome holds\n",
        encoding="utf-8",
    )


def _build_orphan_feature_tag(comp: CarpaccioGateComposition) -> None:
    comp._slice_at_count = 1
    # The plan declares only slice-01, but the .feature tags scenarios @slice-02.
    comp._write_feature_delta(
        "| slice-01 | Operator previews a plan | pending | @walking-skeleton | "
        "thinnest end-to-end vertical |"
    )
    comp._write_feature_file("slice-02", 1)


def _build_section_absent(comp: CarpaccioGateComposition) -> None:
    comp._slice_at_count = 1
    comp.feature_delta_path.write_text(
        "# Feature Delta: carpaccio gate fixture\n\n"
        "## Wave: DISCUSS / [REF] Inherited commitments\n\n"
        "No slice plan section in this feature-delta.\n",
        encoding="utf-8",
    )
    comp._write_feature_file("slice-01", 1)


_SLICE_PLAN_BUILDERS: dict[
    SlicePlanShape, callable[[CarpaccioGateComposition], None]
] = {
    SlicePlanShape.VALID_IN_SIZE: _build_valid_in_size,
    SlicePlanShape.OVER_N_UNANNOTATED: _build_over_n_unannotated,
    SlicePlanShape.OVER_N_COUPLED: _build_over_n_coupled,
    SlicePlanShape.ORDERED_BEFORE_WS: _build_ordered_before_ws,
    SlicePlanShape.UNTAGGED_SCENARIO: _build_untagged_scenario,
    SlicePlanShape.MALFORMED_TABLE: _build_malformed_table,
    SlicePlanShape.ORPHAN_FEATURE_TAG: _build_orphan_feature_tag,
    SlicePlanShape.SECTION_ABSENT: _build_section_absent,
}


# --- AT-review record provisioners ------------------------------------------
# No signing key is provisioned for any state -- the post-demotion gate is
# keyless (D-tolerate-old: a stray hmac_sha256 field is ignored, not verified).


def _provision_approved_valid(comp: CarpaccioGateComposition) -> None:
    comp._write_ledger_record(
        comp._build_record(
            verdict="APPROVED",
            at_ids=comp._current_at_ids(),
            at_content_hash=comp._normalized_at_bodies_hash(),
        )
    )


def _provision_no_record(comp: CarpaccioGateComposition) -> None:
    # The ledger exists but carries no ATReviewVerdict for the entering slice.
    comp.ledger_path.parent.mkdir(parents=True, exist_ok=True)
    comp.ledger_path.write_text(
        json.dumps({"event": "PhaseBoundary", "slice_id": "slice-99", "phase": "A"})
        + "\n",
        encoding="utf-8",
    )


def _provision_needs_revision(comp: CarpaccioGateComposition) -> None:
    comp._write_ledger_record(
        comp._build_record(
            verdict="NEEDS_REVISION",
            at_ids=comp._current_at_ids(),
            at_content_hash=comp._normalized_at_bodies_hash(),
        )
    )


def _provision_stale_at_ids(comp: CarpaccioGateComposition) -> None:
    # The record's at_ids no longer match the slice's scenario set.
    comp._write_ledger_record(
        comp._build_record(
            verdict="APPROVED",
            at_ids=["AT-1", "AT-99"],
            at_content_hash=comp._normalized_at_bodies_hash(),
        )
    )


def _provision_stale_body_hash(comp: CarpaccioGateComposition) -> None:
    # The record's at_content_hash no longer matches the slice's AT bodies.
    comp._write_ledger_record(
        comp._build_record(
            verdict="APPROVED",
            at_ids=comp._current_at_ids(),
            at_content_hash="f" * 64,
        )
    )


_AT_REVIEW_PROVISIONERS: dict[
    ATReviewRecordState, callable[[CarpaccioGateComposition], None]
] = {
    ATReviewRecordState.APPROVED_VALID: _provision_approved_valid,
    ATReviewRecordState.NO_RECORD: _provision_no_record,
    ATReviewRecordState.NEEDS_REVISION: _provision_needs_revision,
    ATReviewRecordState.STALE_AT_IDS: _provision_stale_at_ids,
    ATReviewRecordState.STALE_BODY_HASH: _provision_stale_body_hash,
}
