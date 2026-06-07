"""Conftest for fix-mandate-9-v2-rollout slice-01 + slice-02 acceptance tests.

Composition root for slices 01 and 02 — six driving-port surfaces tested via
one `MandateNineRolloutComposition` per the Mandate-12 SSOT discipline.

Slice-01 surfaces (SHIPPED, GREEN):
  1. `slice_kinds` enum reader -- reads `framework-catalog.yaml` and queries
     the registered slice-kind vocabulary. Driving entry exposed by the
     production carpaccio gate (the gate is the closest existing reader of
     the catalog; the slice-01 reader function is a new public surface in
     `carpaccio_slice_gate.py`).
  2. `MandateNineTagMismatch` detector -- analyses a (scenario_tag,
     composition_evidence) pair and emits a structured stderr event per
     DD-4 contract when the pair is inconsistent. Non-blocking on exit code
     (the gate stays exit 0); slice-03 promotes to BLOCKING.
  3. Retro-audit artifact reader -- reads
     `docs/architecture/at-real-io-audit-2026-05-27.md` and verifies its
     5-column table header per DD-3.

Slice-02 surfaces (RED scaffold this DISTILL; A_GREEN_ATS populates the
documents in DELIVER):
  4. nw-distill skill document reader -- reads
     `nWave/skills/nw-distill/SKILL.md` and verifies the "Adapter Integration
     Slice Authoring" section heading, the 10-property matrix enumeration,
     and the EXERCISED/N/A/DEFERRED verdict vocabulary tokens (spike v2 §6
     surface #2).
  5. nw-acceptance-designer-reviewer agent document reader -- reads
     `nWave/agents/nw-acceptance-designer-reviewer.md` and verifies the new
     critique vectors "S3 mock-tag consistency" + "adapter-criticality
     coverage check", plus the 4-step mechanical checklist per spike v2
     §5 AUTH-2.
  6. nw-tdd-methodology skill document reader -- reads
     `nWave/skills/nw-tdd-methodology/SKILL.md` and verifies the "Adapter
     Integration Slice RED-Phase Semantics" section + the acceptance-vs-
     adapter-integration RED distinction (spike v2 §6 surface #10).

Mandate-13 (driving-port-only) attestation:
  Step modules import ONLY this composition + `domain_types`. The composition
  imports from `des.cli.carpaccio_slice_gate` (the driving-port public
  surface for slice_kinds catalog reading + the new MandateNineTagMismatch
  detector) -- carpaccio_slice_gate is the production CLI entry, a driving
  port per the Architecture of Reference. ZERO imports from `des.domain.*`,
  `des.application.*`, or `des.adapters.*`. Slice-02 skill/agent document
  surfaces are read via `pathlib.Path.read_text(...)` -- the filesystem is
  the driving surface for documentation contracts (precedent: slice-01
  audit-doc reader).

Pillar-3 (app as in production):
  The composition wires the real on-disk `framework-catalog.yaml` (the
  catalog SSOT, written and read by the production gate). Slice-01 reads
  it via `composition.query_slice_kind(...)`; the production carpaccio gate
  reads the same file from the same path.

  The retro-audit artifact path is the real `docs/architecture/` location.
  The composition reads it as production downstream tooling will.

  The detector is a pure function on (tag, composition_evidence) -- no
  Port double needed; the composition wraps the call and captures the
  emitted structured-event payload from stderr.

  Slice-02 reads the REAL `nWave/skills/<skill>/SKILL.md` + agent file paths
  that the agent harness loads at session start. Documentation is the SUT;
  the composition just observes its contents via the filesystem.
"""

from __future__ import annotations

import io
from contextlib import redirect_stderr
from dataclasses import dataclass
from pathlib import Path

import pytest

# slice-03 — BLOCKING-mode detector is a new public surface on the gate
# module; the composition reaches it via `getattr` so DISTILL scaffold-RED
# tolerates the symbol's absence and A_GREEN_ATS lands it without breaking
# the conftest import graph (precedent: slice-02 .md-doc readers also
# tolerate file-absence at scaffold time).
import des.cli.carpaccio_slice_gate as _gate_module
from des.cli.carpaccio_slice_gate import (
    GateError,
    MandateNineTagMismatchEvent,
    detect_mandate_nine_tag_mismatch,
    read_slice_kinds_from_catalog,
)

from .m9v2_rollout_steps.domain_types import (
    ATDD_INFRASTRUCTURE_POLICY_PATH,
    RETRO_AUDIT_ARTIFACT_PATH,
    SKILL_AGENT_DOC_PATHS,
    AdapterCriticalityColumn,
    AdapterCriticalityLevel,
    AdapterCtorName,
    AssertedTag,
    AuditRowVerdict,
    AuditTableColumn,
    SkillAgentDoc,
    SliceKindId,
    TagCompositionVerdict,
)


# Repo root resolved once per session — points to the live nwave-dev tree so
# the slice-01 + slice-02 + slice-03 ATs read the REAL `framework-catalog.yaml`,
# REAL audit doc, REAL `nWave/skills/<skill>/SKILL.md` + agent .md files, and
# REAL `docs/architecture/atdd-infrastructure-policy.md`. This is Pillar-3
# "app as in production" — the rollout ships infrastructure whose correctness
# can only be observed against the real on-disk SSOT.
_REPO_ROOT = Path(__file__).resolve().parents[4]


def _read_skill_agent_doc_body(repo_root: Path, doc: SkillAgentDoc) -> str:
    """Read the live body of a skill/agent document by SkillAgentDoc enum.

    Module-scoped helper (NOT inside a step body) so step bodies stay at <=2
    statements per Mandate-12 criterion 3. Resolves the enum to the
    repo-relative path via the SKILL_AGENT_DOC_PATHS SSOT lookup, then reads
    the file. Returns empty string if the file is absent so absence-of-token
    fail-for-right-reason reds the AT (precedent: slice-01 audit doc reader).
    """
    rel = SKILL_AGENT_DOC_PATHS[doc]
    target = repo_root / rel
    if not target.is_file():
        return ""
    return target.read_text(encoding="utf-8")


def _read_markdown_table_rows(
    path: Path, section_heading: str | None = None
) -> tuple[tuple[str, ...], list[tuple[str, ...]]]:
    """Parse a Markdown file and return (header_cells, data_rows) of one table.

    Module-scoped helper (NOT inside a step body) so step bodies stay at <=2
    statements per Mandate-12 criterion 3.

    When `section_heading` is supplied, locates the first `## <heading>` line
    and scopes table parsing to its section (until the next `## ` heading).
    When `section_heading` is None, returns the first table found in the file.

    Returns:
        (header_cells, data_rows) tuple. `header_cells` is the first table-row
        cells (the column-header row). `data_rows` is the list of data rows
        AFTER the markdown separator line `|---|---|...`. Returns
        (empty-tuple, empty-list) on file absence or section absence.
    """
    if not path.is_file():
        return ((), [])
    lines = path.read_text(encoding="utf-8").splitlines()
    start_idx = 0
    end_idx = len(lines)
    if section_heading is not None:
        target = f"## {section_heading}"
        located = False
        for idx, raw in enumerate(lines):
            if raw.strip() == target:
                start_idx = idx + 1
                located = True
                continue
            if located and raw.startswith("## "):
                end_idx = idx
                break
        if not located:
            return ((), [])
    header: tuple[str, ...] = ()
    rows: list[tuple[str, ...]] = []
    separator_seen = False
    for raw in lines[start_idx:end_idx]:
        stripped = raw.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            if header:
                # Table block ended.
                break
            continue
        cells = tuple(c.strip() for c in stripped.strip("|").split("|"))
        non_empty_cells = tuple(c for c in cells if c)
        if not header:
            header = non_empty_cells
            continue
        if not separator_seen and all(set(c) <= set("-: ") for c in cells if c):
            separator_seen = True
            continue
        rows.append(cells)
    return (header, rows)


@dataclass
class MandateNineRolloutComposition:
    """Production composition root for slice-01 + slice-02 + slice-03 ATs.

    Owns nine driving-port entries (slice-01 catalog reader + detector +
    audit reader, slice-02 distill skill / reviewer agent / TDD-methodology
    skill document readers, slice-03 audit body row counter + BLOCKING
    detector + adapter criticality table reader) plus the captured-output
    state each step asserts against. Step bodies invoke one composition
    method per Mandate-12 criterion 3 (<=2 statements, ending in
    `composition.<method>(...)`, no control flow).
    """

    repo_root: Path
    _last_slice_kinds: tuple[SliceKindId, ...] | None = None
    _staged_tag: AssertedTag | None = None
    _staged_evidence: tuple[AdapterCtorName, ...] | None = None
    _staged_file: str | None = None
    _staged_line: int | None = None
    _last_detector_event: MandateNineTagMismatchEvent | None = None
    _last_detector_stderr: str = ""
    _last_audit_header_columns: tuple[str, ...] | None = None
    # slice-02 — skill / agent / methodology document body capture
    _last_distill_skill_body: str = ""
    _last_reviewer_agent_body: str = ""
    _last_tdd_methodology_body: str = ""
    # slice-03 — audit body rows + BLOCKING-mode detector + criticality table
    _last_audit_data_rows: list[tuple[str, ...]] | None = None
    _last_audit_verdict_column_index: int | None = None
    _blocking_mode_on: bool = False
    _last_blocking_gate_error: GateError | None = None
    _last_blocking_event_payload: dict[str, object] | None = None
    _last_criticality_header: tuple[str, ...] | None = None
    _last_criticality_rows: list[tuple[str, ...]] | None = None
    _last_atdd_policy_body: str = ""

    # --- (1) slice_kinds catalog reader -----------------------------------

    def load_slice_kinds_from_framework_catalog(self) -> None:
        """Read `framework-catalog.yaml` and capture the `slice_kinds` vocabulary.

        Invokes the new public reader on `carpaccio_slice_gate` -- the gate
        is the closest existing consumer of the catalog and owns the typed
        reader for the new `slice_kinds:` section.
        """
        self._last_slice_kinds = read_slice_kinds_from_catalog(self.repo_root)

    def slice_kind_is_registered(self, kind_id: SliceKindId) -> bool:
        """Query whether the loaded slice-kinds vocabulary contains `kind_id`."""
        assert self._last_slice_kinds is not None, "load_slice_kinds_... must run first"
        return kind_id in self._last_slice_kinds

    # --- (2) MandateNineTagMismatch detector -----------------------------

    def stage_detector_input(
        self,
        scenario_tag: AssertedTag,
        scenario_file: str,
        scenario_line: int,
    ) -> None:
        """Stage the scenario-side detector input (tag + location)."""
        self._staged_tag = scenario_tag
        self._staged_file = scenario_file
        self._staged_line = scenario_line

    def stage_composition_evidence(
        self, composition_evidence: tuple[AdapterCtorName, ...]
    ) -> None:
        """Stage the composition-evidence side of the detector input."""
        self._staged_evidence = composition_evidence

    def run_staged_detector(self) -> None:
        """Invoke the detector against staged inputs; capture event + stderr.

        The detector is non-blocking (exit code unaffected); the captured
        stderr is the observable per DD-4 contract.
        """
        buf = io.StringIO()
        with redirect_stderr(buf):
            self._last_detector_event = detect_mandate_nine_tag_mismatch(
                scenario_tag=self._staged_tag,
                composition_evidence=self._staged_evidence,
                scenario_file=self._staged_file,
                scenario_line=self._staged_line,
            )
        self._last_detector_stderr = buf.getvalue()

    def last_detector_verdict(self) -> TagCompositionVerdict:
        """Read the detector's verdict on the (tag, composition) pair."""
        assert self._last_detector_event is not None, "run_detector must run first"
        return (
            TagCompositionVerdict.MISMATCH
            if self._last_detector_event.is_mismatch
            else TagCompositionVerdict.CONSISTENT
        )

    def last_detector_event_name(self) -> str:
        """Read the structured `event` field per DD-4 contract."""
        assert self._last_detector_event is not None, "run_detector must run first"
        return self._last_detector_event.event_name

    def last_detector_severity_phrase(self) -> str:
        """Read the structured `severity` field per DD-4 contract."""
        assert self._last_detector_event is not None, "run_detector must run first"
        return self._last_detector_event.severity

    def last_detector_stderr_mentions(self, token: str) -> bool:
        """Predicate: stderr capture contains `token` (DD-4 stderr emission)."""
        return token in self._last_detector_stderr

    # --- (3) Retro-audit artifact reader ----------------------------------

    def load_retro_audit_header(self) -> None:
        """Read `docs/architecture/at-real-io-audit-2026-05-27.md` header row.

        Slice-01 scaffold ships header row only (DD-3); row population is
        slice-03 scope. The reader extracts the column header tuple for the
        scaffold-schema assertion.
        """
        audit_path = (
            self.repo_root / "docs" / "architecture" / "at-real-io-audit-2026-05-27.md"
        )
        self._last_audit_header_columns = _extract_table_header(audit_path)

    def retro_audit_carries_column(self, column: AuditTableColumn) -> bool:
        """Predicate: loaded header row contains `column` literal."""
        assert self._last_audit_header_columns is not None, (
            "load_retro_audit_header must run first"
        )
        return column.value in self._last_audit_header_columns

    # --- (4) nw-distill skill document reader (slice-02) -----------------

    def load_distill_skill_doc(self) -> None:
        """Read `nWave/skills/nw-distill/SKILL.md` body for slice-02 token checks.

        Production document is the SUT; filesystem is the driving surface.
        Empty string capture if absent so absence-of-token fails the AT for
        the right reason (precedent: slice-01 audit doc reader).
        """
        self._last_distill_skill_body = _read_skill_agent_doc_body(
            self.repo_root, SkillAgentDoc.NW_DISTILL
        )

    def distill_skill_carries_section_heading(self, heading: str) -> bool:
        """Predicate: distill skill body contains the section heading."""
        return f"## {heading}" in self._last_distill_skill_body

    def distill_skill_enumerates_property(self, property_name: str) -> bool:
        """Predicate: distill skill body enumerates a property-matrix row."""
        return property_name in self._last_distill_skill_body

    def distill_skill_declares_verdict_vocabulary(self, token: str) -> bool:
        """Predicate: distill skill body declares the per-property verdict token."""
        return token in self._last_distill_skill_body

    # --- (5) nw-acceptance-designer-reviewer agent doc reader (slice-02) -

    def load_reviewer_agent_doc(self) -> None:
        """Read `nWave/agents/nw-acceptance-designer-reviewer.md` body."""
        self._last_reviewer_agent_body = _read_skill_agent_doc_body(
            self.repo_root, SkillAgentDoc.NW_ACCEPTANCE_DESIGNER_REVIEWER
        )

    def reviewer_agent_declares_critique_vector(self, vector_name: str) -> bool:
        """Predicate: reviewer agent body declares the critique vector name."""
        return vector_name in self._last_reviewer_agent_body

    def reviewer_agent_enumerates_checklist_step(self, phrase: str) -> bool:
        """Predicate: reviewer agent body enumerates the mechanical step phrase."""
        return phrase in self._last_reviewer_agent_body

    # --- (6) nw-tdd-methodology skill doc reader (slice-02) --------------

    def load_tdd_methodology_doc(self) -> None:
        """Read `nWave/skills/nw-tdd-methodology/SKILL.md` body."""
        self._last_tdd_methodology_body = _read_skill_agent_doc_body(
            self.repo_root, SkillAgentDoc.NW_TDD_METHODOLOGY
        )

    def tdd_methodology_carries_section_heading(self, heading: str) -> bool:
        """Predicate: TDD methodology body contains the section heading."""
        return f"## {heading}" in self._last_tdd_methodology_body

    def tdd_methodology_mentions_red_phase_mode(self, mode: str) -> bool:
        """Predicate: TDD methodology body mentions the RED-phase mode token."""
        return mode in self._last_tdd_methodology_body

    def tdd_methodology_distinguishes_red_phase_by(self, token: str) -> bool:
        """Predicate: TDD methodology body carries the distinguishing token."""
        return token in self._last_tdd_methodology_body

    # --- (7) Retro-audit body row counter (slice-03) ---------------------
    #
    # Slice-03 promotes the audit doc from header-only scaffold (slice-01) to
    # body-populated artifact: ≥1 data row with verdict literal from the
    # closed AuditRowVerdict vocabulary. The reader extracts data rows AFTER
    # the markdown separator line; placeholder text (e.g. "_populated in
    # slice-03_") is observed as a data row but its verdict column carries
    # no AuditRowVerdict literal -- the AT then reds for the right reason
    # (MISSING_FUNCTIONALITY: scaffold not yet populated by A_GREEN_ATS).

    def load_retro_audit_body(self) -> None:
        """Read the retro-audit doc + capture data rows + verdict column index."""
        audit_path = self.repo_root / RETRO_AUDIT_ARTIFACT_PATH
        header, rows = _read_markdown_table_rows(audit_path)
        self._last_audit_data_rows = rows
        self._last_audit_verdict_column_index = (
            header.index("verdict") if "verdict" in header else None
        )

    def count_populated_audit_rows_with_valid_verdict(self) -> int:
        """Count audit data rows whose verdict cell is a typed AuditRowVerdict."""
        assert self._last_audit_data_rows is not None, "load_retro_audit_body first"
        assert self._last_audit_verdict_column_index is not None, (
            "load_retro_audit_body must find a 'verdict' column"
        )
        idx = self._last_audit_verdict_column_index
        return sum(
            1
            for row in self._last_audit_data_rows
            if idx < len(row) and row[idx] in {v.value for v in AuditRowVerdict}
        )

    def first_populated_audit_row_verdict(self) -> AuditRowVerdict:
        """Read the typed verdict of the first row carrying a closed-vocab literal."""
        assert self._last_audit_data_rows is not None, "load_retro_audit_body first"
        assert self._last_audit_verdict_column_index is not None, (
            "verdict column missing"
        )
        idx = self._last_audit_verdict_column_index
        valid = {v.value: v for v in AuditRowVerdict}
        for row in self._last_audit_data_rows:
            if idx < len(row) and row[idx] in valid:
                return valid[row[idx]]
        raise AssertionError(
            "no populated row with closed-vocabulary verdict found (scaffold-RED)"
        )

    def retro_audit_header_still_carries(self, column: AuditTableColumn) -> bool:
        """Slice-03 convenience wrapper: load header lazily + check column.

        Keeps the step body at one composition invocation per Mandate-12
        criterion 3 (no control flow, <=2 statements) by lazily loading the
        header columns when not yet present. The header SSOT is the slice-01
        AuditTableColumn enum -- the slice-03 closure surface only populates
        rows; the header invariance from slice-01 is re-asserted here.
        """
        if self._last_audit_header_columns is None:
            self.load_retro_audit_header()
        return self.retro_audit_carries_column(column)

    # --- (8) MandateNineTagMismatch BLOCKING-mode detector (slice-03) ----
    #
    # Slice-03 promotion target: the detector raises `GateError(exit_code=44)`
    # with severity=BLOCKING when (a) the existing non-blocking mismatch
    # predicate fires AND (b) blocking mode is on. Until A_GREEN_ATS ships
    # the new public function `detect_mandate_nine_tag_mismatch_blocking`,
    # the composition falls back to a stub raising AssertionError so the AT
    # reds for the right reason. The driving-port shape is module-attribute
    # access (Mandate-13 — `des.cli.carpaccio_slice_gate` is the production
    # CLI entry; the gate module is the driving port for this surface).

    def enable_blocking_mode(self) -> None:
        """Stage the BLOCKING-mode flag for the next detector invocation."""
        self._blocking_mode_on = True

    def run_blocking_detector(self) -> None:
        """Invoke the BLOCKING-mode detector and capture any GateError raised.

        Reaches the new public function via `getattr` on the carpaccio gate
        module so the composition tolerates the symbol's absence at slice-03
        DISTILL RED -- A_GREEN_ATS lands `detect_mandate_nine_tag_mismatch_blocking`
        as a new public surface. The composition stores the raised GateError
        for downstream step-body assertions.
        """
        blocking_fn = getattr(
            _gate_module, "detect_mandate_nine_tag_mismatch_blocking", None
        )
        assert blocking_fn is not None, (
            "detect_mandate_nine_tag_mismatch_blocking not yet implemented "
            "(slice-03 A_GREEN_ATS scope -- scaffold RED)"
        )
        try:
            blocking_fn(
                scenario_tag=self._staged_tag,
                composition_evidence=self._staged_evidence,
                scenario_file=self._staged_file,
                scenario_line=self._staged_line,
                blocking_mode=self._blocking_mode_on,
            )
            self._last_blocking_gate_error = None
        except GateError as exc:
            self._last_blocking_gate_error = exc
            self._last_blocking_event_payload = dict(exc.payload)

    def last_blocking_exit_code(self) -> int:
        """Read the captured GateError exit code (44 on BLOCKING mismatch)."""
        assert self._last_blocking_gate_error is not None, (
            "run_blocking_detector must raise GateError (none captured)"
        )
        return self._last_blocking_gate_error.exit_code

    def last_blocking_event_name(self) -> str:
        """Read the captured GateError payload `event` field."""
        assert self._last_blocking_event_payload is not None, "no payload captured"
        return str(self._last_blocking_event_payload.get("event", ""))

    def last_blocking_severity(self) -> str:
        """Read the captured GateError payload `severity` field."""
        assert self._last_blocking_event_payload is not None, "no payload captured"
        return str(self._last_blocking_event_payload.get("severity", ""))

    # --- (9) Project Adapter Criticality table reader (slice-03) ---------
    #
    # Slice-03 initialises the project-local Adapter Criticality table inside
    # `docs/architecture/atdd-infrastructure-policy.md`. The composition
    # parses the `## Adapter Criticality` section's table and exposes the
    # header columns + data rows for the AT-3 assertions.

    def load_atdd_infrastructure_policy(self) -> None:
        """Read the policy doc body + capture criticality table header + rows."""
        policy_path = self.repo_root / ATDD_INFRASTRUCTURE_POLICY_PATH
        self._last_atdd_policy_body = (
            policy_path.read_text(encoding="utf-8") if policy_path.is_file() else ""
        )
        header, rows = _read_markdown_table_rows(
            policy_path, section_heading="Adapter Criticality"
        )
        self._last_criticality_header = header
        self._last_criticality_rows = rows

    def atdd_policy_carries_section_heading(self, heading: str) -> bool:
        """Predicate: policy doc body carries the section heading."""
        return f"## {heading}" in self._last_atdd_policy_body

    def criticality_table_carries_column(
        self, column: AdapterCriticalityColumn
    ) -> bool:
        """Predicate: criticality header row carries the typed column literal."""
        assert self._last_criticality_header is not None, (
            "load_atdd_infrastructure_policy first"
        )
        return column in self._last_criticality_header

    def count_classified_criticality_rows(self) -> int:
        """Count criticality rows whose criticality cell is a typed level literal."""
        assert self._last_criticality_rows is not None, "load policy first"
        assert self._last_criticality_header is not None, "load policy first"
        if "Criticality" not in self._last_criticality_header:
            return 0
        idx = self._last_criticality_header.index("Criticality")
        return sum(
            1
            for row in self._last_criticality_rows
            if idx < len(row) and row[idx] in {c.value for c in AdapterCriticalityLevel}
        )

    def first_classified_criticality_row_level(self) -> AdapterCriticalityLevel:
        """Read the typed criticality of the first row carrying a typed level."""
        assert self._last_criticality_rows is not None, "load policy first"
        assert self._last_criticality_header is not None, "load policy first"
        assert "Criticality" in self._last_criticality_header, (
            "criticality table missing 'Criticality' column"
        )
        idx = self._last_criticality_header.index("Criticality")
        valid = {c.value: c for c in AdapterCriticalityLevel}
        for row in self._last_criticality_rows:
            if idx < len(row) and row[idx] in valid:
                return valid[row[idx]]
        raise AssertionError(
            "no row with closed-vocabulary criticality literal found (scaffold-RED)"
        )


def _extract_table_header(path: Path) -> tuple[str, ...]:
    """Parse a Markdown file and return the first table's header row cells.

    Module-scoped helper (NOT inside a step body) so step bodies stay at <=2
    statements per Mandate-12 criterion 3. Looks for the first line matching
    `| ... | ... |` shape, splits on `|`, strips whitespace, returns the
    non-empty cells as a tuple.
    """
    if not path.is_file():
        return ()
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            return tuple(c for c in cells if c)
    return ()


@pytest.fixture
def composition() -> MandateNineRolloutComposition:
    """Composition-root fixture wiring the real repo-root path."""
    return MandateNineRolloutComposition(repo_root=_REPO_ROOT)


# ---------------------------------------------------------------------------
# DISTILL author-ahead RED scaffold marking (precedent: atdd_pure_common_audit_log_ssot/conftest.py)
# ---------------------------------------------------------------------------
#
# Per ADR-025 + Mandate-7 RED contract: DISTILL ships the .feature + step
# bindings + composition root + production scaffolds (raising AssertionError)
# AHEAD of A_GREEN_ATS implementation. Slice-01 + slice-02 GREEN; slice-03
# scenarios red for the RIGHT reason today -- MISSING_FUNCTIONALITY:
#   - slice-03 AT-1: retro-audit body carries 0 populated rows with closed-
#                    vocabulary verdict (only the placeholder text row);
#                    composition.count_populated_audit_rows... returns 0;
#                    assertion ≥1 fails (scaffold-RED).
#   - slice-03 AT-2: `detect_mandate_nine_tag_mismatch_blocking` symbol is
#                    absent from carpaccio_slice_gate module; composition
#                    getattr returns None; AssertionError raised in the
#                    blocking-detector step (scaffold-RED).
#   - slice-03 AT-3: `## Adapter Criticality` section absent from policy doc
#                    (or empty table); section-heading assertion fails OR
#                    criticality-row count is 0 (scaffold-RED).
#
# xfail(strict=False) so the pre-commit pytest gate (which runs the full
# suite) sees these as expected-failures while remaining vigilant: when
# A_GREEN_ATS lands the scenario organically passes, the slice tag is
# removed from `_RED_SCAFFOLD_SLICES` below, and the gate re-arms.
_SUITE_DIR = Path(__file__).parent
_RED_SCAFFOLD_SLICES: frozenset[str] = frozenset()


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Mark every author-ahead RED-scaffold scenario xfail until GREEN."""
    from pytest_bdd.exceptions import StepDefinitionNotFoundError

    xfail = pytest.mark.xfail(
        reason=(
            "RED scaffold -- DISTILL-authored fix-mandate-9-v2-rollout slice-03, "
            "awaiting A_GREEN_ATS implementation"
        ),
        strict=False,
        raises=(
            AssertionError,
            ModuleNotFoundError,
            ImportError,
            TypeError,
            StepDefinitionNotFoundError,
        ),
    )
    for item in items:
        if not _belongs_to_this_suite(item):
            continue
        if set(item.keywords) & _RED_SCAFFOLD_SLICES:
            item.add_marker(xfail)


def _belongs_to_this_suite(item: pytest.Item) -> bool:
    """Whether a collected item lives under this conftest's suite directory."""
    item_path = getattr(item, "path", None)
    if item_path is None:
        return False
    return _SUITE_DIR in Path(item_path).parents or Path(item_path) == _SUITE_DIR
