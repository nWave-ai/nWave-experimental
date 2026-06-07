"""Composition root for the fix-carpaccio-distill-authoring-ergonomics AT set.

Mandate-13 (driving-port-only boundary) + Pillar 3 (app as in production): the
SUT is driven EXCLUSIVELY through the real `des` CLIs invoked as Layer-3
subprocesses. No production module is imported here -- the only seam is the
process boundary + the filesystem. Two driving ports:
  * `des carpaccio-slice-gate`  -- the enforcing entry GATE (slices 01/02),
    invoked via the `des` dispatcher subcommand (`python -m des.cli carpaccio-
    slice-gate ...`).
  * `python -m des.cli.carpaccio_precheck`  -- the NEW read-only advisory
    pre-check (slice 03), a NON-GATE designer tool invoked MODULE-DIRECT. It is
    NOT a `des` dispatcher subcommand: the dispatcher `_REGISTRY` is parity-pinned
    to the 19-row gate catalog (tests/build/d4_phase_1_catalog_files), so adding
    a non-gate tool would break that parity AT. The module-direct surface mirrors
    the at_review_verdict precedent; the operator-ergonomic subcommand is deferred
    to F-DES-AT-REVIEW-VERDICT-SUBCOMMAND-SURFACE.

Business logic lives here as the single source of truth; step bodies delegate to
``CarpaccioErgonomicsComposition`` methods and never inline logic (Mandate-12
criterion 3). The composition provisions a tmp_path repository fixture (feature-
delta slice plan, `.feature` files, AT-completion ledger, signing key, config),
invokes the CLI as a subprocess, and exposes the observable outcome (exit code,
stdout machine JSON, stderr human + diagnostic lines).

RED scaffold note (ADR-025 / ADR-028):
  * slice-01 -- the gate EXISTS on master; the human-surface line is WRONG today
    (prints the refusal marker for an exit-0 coupled clear). The AT reds on the
    human-surface assertion (semantic AssertionError), not on import/collection.
  * slice-02 -- `des.cli.carpaccio_format` does NOT exist on master; the AT reds
    because the shared-format-checks assertion finds the module absent.
  * slice-03 -- the `des.cli.carpaccio_precheck` module does NOT exist on master;
    the module-direct subprocess (`python -m des.cli.carpaccio_precheck`) fails
    with ModuleNotFoundError and emits no precheck diagnostics; the AT reds
    because the expected diagnostics are absent (semantic AssertionError), never
    a collection/import error of this test module itself.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types import (
    FeatureId,
    GateVerdict,
    HumanVerdictClass,
    PrecheckFeatureShape,
    SliceId,
    SlicePlanShape,
)


# Repo root: this file is tests/des/acceptance/<feature>/steps/composition.py.
_REPO_ROOT = Path(__file__).resolve().parents[5]

# Carpaccio ceiling for the fixture repo's .nwave/config.yaml.
_CARPACCIO_SLICE_MAX = 3

# Reviewer signing-key precedence mirrors the gate (env first, file fallback).
_SIGNING_KEY_FILE = ".nwave/secrets/reviewer-signing.key"
_FIXTURE_SIGNING_KEY = b"fix-carpaccio-ergonomics-fixture-signing-key"

# The seven HMAC-signed fields of an ATReviewVerdict record (ADR-029 D5 / B1).
_SIGNED_FIELDS = (
    "schema_version",
    "slice_id",
    "verdict",
    "reviewer_agent_id",
    "at_ids",
    "at_content_hash",
    "timestamp",
)

# The human-surface markers emitted by human_surface.print_human_summary.
_PASS_MARKER = "✅ PASS"
_FAIL_MARKER = "❌ FAIL"
_DEGRADED_MARKER = "⚠️ DEGRADED"

# One normalized scenario body for the fixture .feature scenarios.
_FIXTURE_BODY = (
    "given a fixture precondition\n"
    "when the fixture action occurs\n"
    "then the fixture outcome holds"
)


@dataclass
class CliResult:
    """Observable outcome of one `des` CLI subprocess invocation."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def gate_verdict(self) -> GateVerdict:
        """Map the gate CLI exit code onto the user-observable verdict."""
        return {
            0: GateVerdict.CLEARED,
            1: GateVerdict.SLICE_PLAN_MISSING,
            2: GateVerdict.MALFORMED_INPUT,
            44: GateVerdict.SLICE_TOO_LARGE,
            45: GateVerdict.AT_REVIEW_REJECTED,
        }.get(self.exit_code, GateVerdict.MALFORMED_INPUT)

    @property
    def machine_events(self) -> list[dict[str, object]]:
        """Every single-line JSON object the CLI emitted across stdout+stderr."""
        events: list[dict[str, object]] = []
        for stream in (self.stdout, self.stderr):
            for line in stream.splitlines():
                stripped = line.strip()
                if stripped.startswith("{") and stripped.endswith("}"):
                    with contextlib.suppress(json.JSONDecodeError):
                        loaded = json.loads(stripped)
                        if isinstance(loaded, dict):
                            events.append(loaded)
        return events

    def has_event(self, event_name: str) -> bool:
        """True iff any emitted JSON object carries ``event == event_name``."""
        return any(e.get("event") == event_name for e in self.machine_events)

    @property
    def human_verdict_class(self) -> HumanVerdictClass | None:
        """Classify the human-readable summary line on stderr, or None.

        The summary line is the LAST stderr line carrying a verdict marker; the
        machine JSON event lines are excluded. Returns None when no human line
        was emitted (e.g. the subcommand does not exist).
        """
        found: HumanVerdictClass | None = None
        for line in self.stderr.splitlines():
            if _PASS_MARKER in line:
                found = HumanVerdictClass.PASS_CLASS
            elif _FAIL_MARKER in line:
                found = HumanVerdictClass.FAIL_CLASS
            elif _DEGRADED_MARKER in line:
                found = HumanVerdictClass.DEGRADED_CLASS
        return found

    @property
    def human_summary_text(self) -> str:
        """The full text of the human-readable summary line(s) on stderr."""
        return "\n".join(
            line
            for line in self.stderr.splitlines()
            if _PASS_MARKER in line or _FAIL_MARKER in line or _DEGRADED_MARKER in line
        )

    @property
    def combined_text(self) -> str:
        """All emitted text across stdout+stderr (for diagnostic-content scans)."""
        return self.stdout + "\n" + self.stderr


@dataclass
class CarpaccioErgonomicsComposition:
    """Production-wired composition over a tmp_path repository fixture.

    ``repo_dir`` is a real tmp_path directory acting as the repository root. Each
    Given method provisions exactly the project state a scenario needs; the When
    methods invoke the real `des` CLI subcommands as subprocesses against it.
    """

    repo_dir: Path
    feature_id: FeatureId = field(default=FeatureId("demo-feature"))
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
        return self.repo_dir / "tests" / "des" / "acceptance" / self.feature_id

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

    # --- Given: repo skeleton ------------------------------------------------

    def create_repo(self) -> None:
        """Create the repo skeleton: feature dir, acceptance dir, config."""
        self._acceptance_dir.mkdir(parents=True, exist_ok=True)
        self._feature_dir.mkdir(parents=True, exist_ok=True)
        self._nwave_dir.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            "workflow:\n"
            "  mode: atdd_pure\n"
            "atdd_pure:\n"
            f"  carpaccio_slice_max: {_CARPACCIO_SLICE_MAX}\n",
            encoding="utf-8",
        )

    # --- Given: unified phrase dispatch --------------------------------------

    def provision_by_phrase(self, feature_phrase: str) -> None:
        """Provision the repository fixture for one Gherkin feature-phrase.

        One dispatch over the merged gate-shape + pre-check-shape phrase map so a
        single ``the feature carries {feature_phrase}`` Given covers both driving
        ports (S1: one step template, one body) -- no duplicate-template shadow.
        """
        _PHRASE_BUILDERS[feature_phrase](self)

    # --- Given: slice-plan shapes (gate, slices 01/02) -----------------------

    def provision_slice_plan(self, shape: SlicePlanShape) -> None:
        """Provision the feature-delta + .feature for one gate-fixture shape."""
        _SLICE_PLAN_BUILDERS[shape](self)

    def _write_feature_delta(self, slice_rows: str) -> None:
        self.feature_delta_path.write_text(
            "# Feature Delta: carpaccio ergonomics fixture\n\n"
            "## Wave: DISCUSS / [REF] Slice Plan\n\n"
            "| Slice | Value statement | Status | Annotation | Justification |\n"
            "|-------|-----------------|--------|------------|---------------|\n"
            f"{slice_rows}\n",
            encoding="utf-8",
        )

    def _scenario_block(self, tags: str, index: int) -> str:
        return (
            f"{tags}\n"
            f"Scenario: fixture scenario {index}\n"
            "  Given a fixture precondition\n"
            "  When the fixture action occurs\n"
            "  Then the fixture outcome holds\n"
        )

    def _write_feature_file(self, blocks: list[str], *, bind: bool = True) -> None:
        binding = f"@feature-{self.feature_id}\n" if bind else ""
        self._acceptance_dir.mkdir(parents=True, exist_ok=True)
        (self._acceptance_dir / "slice.feature").write_text(
            binding + "Feature: carpaccio ergonomics fixture\n\n" + "\n".join(blocks),
            encoding="utf-8",
        )

    # --- Given: AT-review ledger (gate, slices 01/02) ------------------------

    def provision_approved_at_review_record(self) -> None:
        """Write a correctly-signed APPROVED ledger record for the slice."""
        self._signing_key_path.parent.mkdir(parents=True, exist_ok=True)
        self._signing_key_path.write_bytes(_FIXTURE_SIGNING_KEY)
        record = self._build_signed_record()
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

    def _build_signed_record(self) -> dict[str, object]:
        at_ids = [f"AT-{n}" for n in range(1, self._slice_at_count + 1)]
        bodies = sorted(_FIXTURE_BODY for _ in at_ids)
        at_content_hash = hashlib.sha256("".join(bodies).encode("utf-8")).hexdigest()
        record: dict[str, object] = {
            "event": "ATReviewVerdict",
            "schema_version": "1.0.0",
            "slice_id": str(self.entering_slice),
            "verdict": "APPROVED",
            "reviewer_agent_id": "nw-acceptance-designer-reviewer",
            "at_ids": at_ids,
            "at_content_hash": at_content_hash,
            "timestamp": "2026-05-29T00:00:00Z",
            "findings_summary": [],
        }
        signed = {k: record[k] for k in _SIGNED_FIELDS}
        canon = json.dumps(signed, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        record["hmac_sha256"] = hmac.new(
            _FIXTURE_SIGNING_KEY, canon, hashlib.sha256
        ).hexdigest()
        return record

    # --- Given: pre-check feature shapes (slice 03) --------------------------

    def provision_precheck_feature(self, shape: PrecheckFeatureShape) -> None:
        """Provision a feature whose format the pre-check is asked to report on."""
        _PRECHECK_FEATURE_BUILDERS[shape](self)

    # --- shared format-checks module presence (slice 02) ---------------------

    def shared_format_checks_available(self) -> bool:
        """True iff the shared `des.cli.carpaccio_format` module is importable.

        Mandate-13: this is a presence probe, NOT a behavioral driving-port call
        -- it asserts the extraction target module ships, the new contract
        slice-02 introduces. Resolved via importlib.util.find_spec so no
        production symbol is imported into the step composition.
        """
        return importlib.util.find_spec("des.cli.carpaccio_format") is not None

    # --- When: run the CLIs as subprocesses ----------------------------------

    def run_gate(self) -> CliResult:
        """Invoke the real `des carpaccio-slice-gate` CLI as a subprocess."""
        return self._run_des(
            "carpaccio-slice-gate",
            "--feature-id",
            str(self.feature_id),
            "--entering-slice",
            str(self.entering_slice),
            "--repo-root",
            str(self.repo_dir),
        )

    def run_precheck(self) -> CliResult:
        """Invoke the real `python -m des.cli.carpaccio_precheck` CLI module-direct.

        The pre-check is a NON-GATE designer tool, so it is invoked MODULE-DIRECT
        (`python -m des.cli.carpaccio_precheck`), NOT via the `des` dispatcher
        subcommand. The dispatcher's `_REGISTRY` is parity-pinned to the 19-row
        gate catalog (tests/build/d4_phase_1_catalog_files), so a non-gate tool
        cannot be a `des` subcommand without first introducing a gate-vs-tool
        distinction in the registry -- deferred to
        F-DES-AT-REVIEW-VERDICT-SUBCOMMAND-SURFACE. This mirrors the
        at_review_verdict precedent (non-gate `des.cli` tools run module-direct).
        """
        return self._run_module(
            "des.cli.carpaccio_precheck",
            "--feature-id",
            str(self.feature_id),
            "--repo-root",
            str(self.repo_dir),
        )

    def _run_des(self, *args: str) -> CliResult:
        proc = subprocess.run(
            [sys.executable, "-m", "des.cli", *args],
            capture_output=True,
            text=True,
            cwd=_REPO_ROOT,
        )
        return CliResult(
            exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr
        )

    def _run_module(self, module: str, *args: str) -> CliResult:
        proc = subprocess.run(
            [sys.executable, "-m", module, *args],
            capture_output=True,
            text=True,
            cwd=_REPO_ROOT,
        )
        return CliResult(
            exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr
        )

    # --- universe (Mandate 8) ------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed filesystem snapshot proving the read-only contract.

        Both CLIs (gate + pre-check) have a pure-function read-only contract:
        they MUST NOT mutate any repository file. The universe is the set of
        files they read and could be tempted to write; the When-step state-delta
        guard proves they read without writing (Principle 12 read/write split).
        """
        return {
            "feature_delta.bytes": _read_or_none(self.feature_delta_path),
            "ledger.bytes": _read_or_none(self.ledger_path),
            "config.bytes": _read_or_none(self.config_path),
            "feature_files.bytes": self._acceptance_files_snapshot(),
        }

    def _acceptance_files_snapshot(self) -> object:
        if not self._acceptance_dir.is_dir():
            return None
        return {
            str(p.relative_to(self.repo_dir)): p.read_bytes()
            for p in sorted(self._acceptance_dir.rglob("*.feature"))
        }


def _read_or_none(path: Path) -> object:
    return path.read_bytes() if path.exists() else None


# --- gate slice-plan fixture builders ---------------------------------------


def _build_coupled_over_ceiling(comp: CarpaccioErgonomicsComposition) -> None:
    comp.entering_slice = SliceId("slice-01")
    comp._slice_at_count = 4
    comp._write_feature_delta(
        "| slice-01 | Operator previews a plan | pending | @walking-skeleton | "
        "indivisible coupled gate contract -- four ATs assert one behaviour |"
    )
    comp._write_feature_file(
        [comp._scenario_block("@slice-01 @coupled:grp", n) for n in range(1, 5)]
    )


def _build_valid_in_size(comp: CarpaccioErgonomicsComposition) -> None:
    comp.entering_slice = SliceId("slice-01")
    comp._slice_at_count = 2
    comp._write_feature_delta(
        "| slice-01 | Operator previews a plan | pending | @walking-skeleton | "
        "thinnest end-to-end vertical |"
    )
    comp._write_feature_file(
        [comp._scenario_block("@slice-01", n) for n in range(1, 3)]
    )


def _build_over_ceiling_uncoupled(comp: CarpaccioErgonomicsComposition) -> None:
    comp.entering_slice = SliceId("slice-01")
    comp._slice_at_count = 5
    comp._write_feature_delta(
        "| slice-01 | Operator previews a plan | pending | @walking-skeleton | "
        "thinnest end-to-end vertical |"
    )
    comp._write_feature_file(
        [comp._scenario_block("@slice-01", n) for n in range(1, 6)]
    )


_SLICE_PLAN_BUILDERS: dict[SlicePlanShape, object] = {
    SlicePlanShape.COUPLED_OVER_CEILING_JUSTIFIED: _build_coupled_over_ceiling,
    SlicePlanShape.VALID_IN_SIZE: _build_valid_in_size,
    SlicePlanShape.OVER_CEILING_UNCOUPLED: _build_over_ceiling_uncoupled,
}


# --- pre-check feature fixture builders -------------------------------------


def _build_missing_binding(comp: CarpaccioErgonomicsComposition) -> None:
    # A well-formed slice plan, but the .feature file carries NO file-level
    # @feature-{id} binding tag and lives outside the legacy directory -> the
    # gate would resolve zero scenarios (no-scenarios-for-slice precursor).
    comp.entering_slice = SliceId("slice-01")
    comp._slice_at_count = 1
    comp._write_feature_delta(
        "| slice-01 | Operator previews a plan | pending | @walking-skeleton | "
        "thinnest end-to-end vertical |"
    )
    comp._write_feature_file([comp._scenario_block("@slice-01", 1)], bind=False)


def _build_over_ceiling_pair(comp: CarpaccioErgonomicsComposition) -> None:
    # Two over-ceiling slices: slice-01 WITHOUT the coupled escape (flagged) and
    # slice-02 WITH the coupled escape satisfied (reported as cleared by escape).
    comp.entering_slice = SliceId("slice-01")
    comp._slice_at_count = 5
    comp._write_feature_delta(
        "| slice-01 | Operator previews a plan | pending | @walking-skeleton | "
        "thinnest end-to-end vertical |\n"
        "| slice-02 | Operator applies a plan | pending | @coupled | "
        "indivisible coupled gate contract -- four ATs assert one behaviour |"
    )
    blocks = [comp._scenario_block("@slice-01", n) for n in range(1, 6)]
    blocks += [comp._scenario_block("@slice-02 @coupled:grp", n) for n in range(1, 5)]
    comp._write_feature_file(blocks)


def _build_multiple_defects(comp: CarpaccioErgonomicsComposition) -> None:
    # THREE defects at once: (1) no file-level @feature-{id} binding tag,
    # (2) a scenario tagged @slice-99 with no matching plan row (tag mismatch),
    # (3) slice-01 over the ceiling without the coupled escape.
    comp.entering_slice = SliceId("slice-01")
    comp._slice_at_count = 5
    comp._write_feature_delta(
        "| slice-01 | Operator previews a plan | pending | @walking-skeleton | "
        "thinnest end-to-end vertical |"
    )
    blocks = [comp._scenario_block("@slice-01", n) for n in range(1, 6)]
    blocks += [comp._scenario_block("@slice-99", 1)]
    comp._write_feature_file(blocks, bind=False)


_PRECHECK_FEATURE_BUILDERS: dict[PrecheckFeatureShape, object] = {
    PrecheckFeatureShape.MISSING_BINDING_TAG: _build_missing_binding,
    PrecheckFeatureShape.OVER_CEILING_PAIR: _build_over_ceiling_pair,
    PrecheckFeatureShape.MULTIPLE_DEFECTS: _build_multiple_defects,
}


# --- unified Gherkin-phrase dispatch ----------------------------------------
# Keys are the substring captured by the {feature_phrase} parser placeholder
# (the text AFTER "the feature carries " / "the feature's scenario files carry ").
# One merged map so a single Given template covers both driving ports (S1).

_PHRASE_BUILDERS: dict[str, object] = {
    # gate slice-plan shapes (slices 01/02)
    "an over-ceiling slice that is fully coupled with a recorded justification": (
        _build_coupled_over_ceiling
    ),
    "a well-formed in-size slice plan": _build_valid_in_size,
    "an over-ceiling slice that is not coupled": _build_over_ceiling_uncoupled,
    # pre-check feature shapes (slice 03)
    "no feature-binding tag": _build_missing_binding,
    "an over-ceiling slice without the coupled escape": _build_over_ceiling_pair,
    "a missing feature-binding tag, a slice-tag mismatch, and an over-ceiling slice": (
        _build_multiple_defects
    ),
}
