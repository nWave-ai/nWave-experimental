"""Composition root for the f-coherence-and-attestation slice-03 ATs (gate-G).

Mandate-13 driving-port-only (Layer 3 composition): each behaviour is driven
through the REAL production seam slice-03 introduces -- the mechanical **gate-G**
(the design↔AT coherence gate, D1) over the slice-01/02 ``CodeFactPort`` substrate
-- built via lazy import inside the driving-port invocation. No production module
is imported-and-called at the step boundary for its business logic; the step
bodies (in ``test_slice_03_*``) delegate to these composition methods (Mandate-12
-- no logic in step bodies).

gate-G is the seam f-distill NAMED but DEFERRED (its OB-2 review-rubric
forward-references the ``CodeFactPort`` queries ``query.atoms-in-file`` over the AT
module + ``query.adr-section`` over the design prose). THIS slice wires that named
seam to the actual mechanical AST diff. gate-G CONSUMES the slice-01/02 substrate;
it does NOT fork it (C2 -- no second ``import ast``).

DRIVING SURFACE: the gate-G VERDICT (a §17 ``GateVerdict``) + the diagnostic the
mechanical diff names -- NEVER a line number. gate-G is driven over a REAL
``tmp_path`` carrying a real design ``[REF] Code-Design`` prose block + a real AT
module; the observable is the returned verdict envelope (verdict + diagnostic +
whether the North-Star cap was surfaced).

active-RED scaffold (atdd_pure -- NOT @skip): at HEAD the gate-G mechanism is
ABSENT -- ``src/des/cli/gate_g.py`` does not exist (verified: the `des` dispatcher
``_REGISTRY`` has no ``gate-g`` row, and no ``gate_g`` callable exists). Each
driving-port invocation captures the absent seam as a sentinel; the ``Then`` reads
the observable and fires a NAMED semantic ``AssertionError`` (the expected §17
verdict is missing because the gate-G seam is unbuilt) -- never a collection /
import / setup error. GREEN once DELIVER lands ``src/des/cli/gate_g.py`` (the
mechanical manifest/prose↔AT-AST diff via the ``CodeFactPort`` substrate).

DESIGN-CONTRACT ASSUMPTIONS flagged to DELIVER (state-here-so-DELIVER-matches --
the SEAM, never a line number):
  A1 (gate-G entry point): the slice-03 Reuse table pins gate-G at
     ``src/des/cli/gate_g.py`` (CREATE_NEW) importing
     ``from des.domain.gate_outcome import GateVerdict`` + the ``CodeFactPort``.
     Per Mandate-13 + the slice-01 ASSUMPTION (the `des` dispatcher has no gate-G
     row at HEAD -> a subprocess dispatch would be a collection-stage failure, not
     a semantic RED), gate-G is driven at the **composition root**: a real gate-G
     callable over the real ``CodeFactPort`` substrate. This composition tries, in
     order, ``des.cli.gate_g``'s ``evaluate_gate_g`` / ``run_gate_g`` / ``gate_g``
     / a ``GateG`` class -- whichever DELIVER ships, wire THIS single invocation
     (``_drive_gate_g``) to it. If DELIVER ships a subprocess ``des gate-g``
     dispatcher instead, update ``_drive_gate_g`` -- the SEAM, not a line number.
  A2 (gate-G input shape): OB-G RESOLVED -> DEFER D3. gate-G diffs the AT-AST
     against the **prose** ``## Wave: DESIGN / [REF] Code-Design`` block (read via
     ``query.adr-section``) + the AT module (read via ``query.atoms-in-file``).
     This composition writes a real ``feature-delta.md`` carrying a real
     ``[REF] Code-Design`` example-table + a real AT ``.feature`` / step module
     under ``tmp_path`` and asks gate-G to diff them. The input is passed as
     ``(design_contract_path, at_module_path)`` (or a single feature-root). If
     DELIVER's gate-G takes a different input shape, update ``_drive_gate_g``.
  A3 (verdict envelope): gate-G returns a §17 ``GateVerdict`` (PASS / FAIL /
     UNVERIFIED / INDETERMINATE -- never a sixth, C6) + a diagnostic naming the
     divergence + (on the suspected-but-unconfirmable case) a surfaced North-Star
     cap. This composition reads the verdict token + the diagnostic + a
     cap-surfaced flag from whichever envelope shape gate-G returns (a
     ``GateOutcome``-like object, a dict, or a ``(verdict, diagnostic)`` tuple).
     If DELIVER names the envelope fields differently, update ``_read_envelope``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .domain_types_slice_03_gate_g import (
    LOCKED_GATE_VERDICTS,
    CoherenceCase,
    ContractInput,
    GateGObservable,
    GateVerdict,
)


# Sentinel an absent gate-G invocation records, so the Then can name the missing
# verdict instead of letting an ImportError escape as a collection error.
_SEAM_ABSENT = "__SEAM_ABSENT__"

# The prose design block gate-G reads via `query.adr-section` (OB-G -- DEFER D3).
_DESIGN_SECTION_HEADING = "## Wave: DESIGN / [REF] Code-Design"


@dataclass
class GateGComposition:
    """Drives the slice-03 gate-G seam through its REAL driving surface."""

    _case: CoherenceCase | None = field(default=None)
    _contract_input: ContractInput = field(default=ContractInput.PROSE_REF_CODE_DESIGN)

    _observable: GateGObservable | None = field(default=None)
    _seam_error: str | None = field(default=None)

    # =====================================================================
    # Given -- arm the design↔AT coherence case + the contract-input shape
    # =====================================================================

    def given_coherence_case(self, case: CoherenceCase) -> None:
        """Arm whether design+ATs are bijective, or a confirmable divergence is present."""
        self._case = case

    def given_contract_input(self, contract_input: ContractInput) -> None:
        """Arm the shape of the design contract gate-G diffs against (OB-G)."""
        self._contract_input = contract_input

    # =====================================================================
    # When -- drive the REAL gate-G mechanical diff over a real tmp_path
    # =====================================================================

    def when_gate_g_diffs_design_against_ats(self, tmp_path: Path) -> None:
        """Drive the REAL gate-G mechanical diff (design `[REF] Code-Design` ↔ AT-AST).

        Writes a real feature-root under ``tmp_path`` (a ``[REF] Code-Design``
        prose example-table + an AT module) per the armed coherence case + the
        contract-input shape, then asks gate-G to diff them. The observable is the
        returned §17 verdict envelope.
        """
        assert (
            self._case is not None
            or self._contract_input is ContractInput.ADAPTER_ABSENT
        )
        feature_root = self._write_feature_root(tmp_path)
        self._observable = self._drive_gate_g(feature_root)

    def when_gate_g_runs_with_unsupported_adapter(self, tmp_path: Path) -> None:
        """Drive gate-G when the CodeFactPort AstAdapter cannot run (OB-G INDETERMINATE).

        Writes a feature-root in an UNSUPPORTED language (no AstAdapter can parse
        it) so the mechanical diff's inspection substrate cannot run -- gate-G must
        degrade LOUD to INDETERMINATE (the mechanism could not run), never a false
        green.
        """
        self._contract_input = ContractInput.ADAPTER_ABSENT
        feature_root = self._write_unsupported_language_root(tmp_path)
        self._observable = self._drive_gate_g(feature_root)

    # =====================================================================
    # Then -- observable readers (the §17 verdict + the diagnostic)
    # =====================================================================

    def then_verdict_is(self, expected: GateVerdict) -> None:
        """gate-G returned EXACTLY the expected §17 verdict (one of the LOCKED five)."""
        obs = self._require_observable()
        assert obs.verdict in LOCKED_GATE_VERDICTS, (
            f"gate-G must return one of the §17 LOCKED FIVE verdicts "
            f"{sorted(LOCKED_GATE_VERDICTS)!r} (ADR-GV-001, no sixth -- C6) -- got "
            f"verdict={obs.verdict!r}. {self._observed()}"
        )
        assert obs.verdict == expected.value, (
            f"gate-G must return {expected.value!r} for this design↔AT coherence "
            f"case -- got {obs.verdict!r}. {self._observed()}"
        )

    def then_diagnostic_names_the_divergence(self) -> None:
        """On FAIL, gate-G names the confirmable divergence (a non-empty diagnostic)."""
        obs = self._require_observable()
        assert obs.diagnostic, (
            f"a confirmable design↔AT divergence (a dropped example-table row or a "
            f"signature mismatch) must come back with a NON-EMPTY diagnostic naming "
            f"the divergence (the mechanical witness, not an LLM say-so) -- gate-G "
            f"returned no diagnostic. {self._observed()}"
        )

    def then_north_star_cap_is_surfaced_loud(self) -> None:
        """On suspected-but-unconfirmable drift, the North-Star cap is surfaced LOUD."""
        obs = self._require_observable()
        assert obs.cap_surfaced, (
            f"a suspected-but-unconfirmable design↔AT divergence (the prose contract "
            f"is not machine-diffable to a row-level bijection -- no D3 manifest, "
            f"OB-G) must surface the North-Star cap LOUD in the verdict envelope "
            f"(UNVERIFIED, never a false PASS, never a hard FAIL) -- the cap was NOT "
            f"surfaced. {self._observed()}"
        )

    def then_gate_g_did_not_run(self) -> None:
        """On adapter-absent, gate-G degraded LOUD (INDETERMINATE) -- the mechanism could not run."""
        obs = self._require_observable()
        assert not obs.ran, (
            f"when the CodeFactPort AstAdapter cannot run (unsupported language) "
            f"gate-G must NOT fabricate a mechanical-diff result -- it must degrade "
            f"LOUD to INDETERMINATE (the mechanism could not run) -- gate-G reported "
            f"it ran a real diff. {self._observed()}"
        )

    # =====================================================================
    # driving-port invocation (lazy seam import -> sentinel on absence)
    # =====================================================================

    def _drive_gate_g(self, feature_root: Path) -> GateGObservable:
        """Drive the REAL gate-G callable over the real feature-root (assumptions A1-A3).

        At HEAD ``src/des/cli/gate_g.py`` is ABSENT -> the lazy import fails -> the
        sentinel records the absent seam and the Then fires the named RED. GREEN
        once DELIVER ships the gate-G mechanical diff.
        """
        try:
            from des.cli import gate_g as gate_g_module
        except (ImportError, ModuleNotFoundError):
            self._seam_error = _SEAM_ABSENT
            return self._absent_observable()

        callable_ = self._resolve_gate_g_callable(gate_g_module)
        if callable_ is None:
            self._seam_error = _SEAM_ABSENT
            return self._absent_observable()

        design_path = feature_root / "feature-delta.md"
        at_module_path = feature_root / "tests" / "acceptance"
        try:
            result = callable_(
                design_contract_path=design_path,
                at_module_path=at_module_path,
            )
        except TypeError:
            # DELIVER may take a single feature-root instead of the (design, at)
            # pair -- try that shape before giving up.
            try:
                result = callable_(feature_root)
            except Exception:
                self._seam_error = _SEAM_ABSENT
                return self._absent_observable()

        return self._read_envelope(result)

    @staticmethod
    def _resolve_gate_g_callable(module: object) -> object | None:
        """Resolve whichever gate-G entry the DELIVER ships (A1 -- the SEAM)."""
        for name in ("evaluate_gate_g", "run_gate_g", "gate_g", "evaluate"):
            candidate = getattr(module, name, None)
            if callable(candidate):
                return candidate
        gate_cls = getattr(module, "GateG", None)
        if gate_cls is not None:
            try:
                instance = gate_cls()
            except Exception:
                return None
            method = getattr(instance, "evaluate", None)
            if callable(method):
                return method
        return None

    # =====================================================================
    # envelope reader + absent-seam observable
    # =====================================================================

    def _read_envelope(self, result: object) -> GateGObservable:
        """Read the port-exposed §17 verdict + diagnostic + cap-surfaced (A3)."""
        verdict = self._token(self._field(result, "verdict"))
        diagnostic = self._field(result, "diagnostic", "reason", "message")
        cap_surfaced = bool(
            self._field(result, "cap_surfaced", "north_star_cap", "capped") or False
        )
        # A tuple envelope (verdict, diagnostic).
        if verdict is None and isinstance(result, tuple) and result:
            verdict = self._token(result[0])
            diagnostic = result[1] if len(result) > 1 else diagnostic
        # gate-G ships a first-class `ran` flag (the mechanism-could-not-run signal
        # the INDETERMINATE degrade carries WITH a verdict token). Read it when the
        # envelope exposes it; fall back to verdict-presence only for an envelope
        # shape that has no `ran` field (e.g. the absent-seam observable).
        ran_field = self._field(result, "ran", "mechanism_ran")
        ran = bool(ran_field) if ran_field is not None else verdict is not None
        return GateGObservable(
            verdict=verdict,
            diagnostic=diagnostic if isinstance(diagnostic, str) else None,
            cap_surfaced=cap_surfaced,
            ran=ran,
        )

    def _absent_observable(self) -> GateGObservable:
        """The gate-G seam is absent -> no verdict; the Then names the missing mechanism."""
        return GateGObservable(
            verdict=None, diagnostic=None, cap_surfaced=False, ran=False
        )

    @staticmethod
    def _field(obj: object, *names: str) -> object:
        """Read the first present attribute (or dict key) from a result envelope."""
        for name in names:
            value = getattr(obj, name, None)
            if value is not None:
                return value
            if isinstance(obj, dict) and name in obj:
                return obj[name]
        return None

    @staticmethod
    def _token(value: object) -> str | None:
        """Coerce an enum-or-str verdict value to its wire token (or None)."""
        if value is None:
            return None
        return getattr(value, "value", value)

    # =====================================================================
    # substrate plumbing -- a real feature-root gate-G diffs (real I/O)
    # =====================================================================

    def _write_feature_root(self, tmp_path: Path) -> Path:
        """Write a real feature-root: a prose `[REF] Code-Design` + a real AT module.

        Per the armed coherence case the design example-table and the AT scenarios
        are bijective (PASS), a confirmable divergence is planted (a dropped row /
        a signature mismatch -> FAIL), OR a suspected-but-unconfirmable drift is
        planted (a loose/placeholder example-table the row-level diff cannot align
        to confirm either pole -> UNVERIFIED, North-Star cap). The mechanical diff
        reads the design prose via ``query.adr-section`` + the AT module via
        ``query.atoms-in-file``. Each case writes a CONTENT-DISTINCT on-disk
        fixture (different design rows AND/OR AT scenarios) so a deterministic
        ``gate_g(design, at)`` can return a different verdict per case.
        """
        root = (
            tmp_path
            / "feature_under_diff"
            / (self._case.value if self._case is not None else "bijective")
        )
        (root / "tests" / "acceptance").mkdir(parents=True, exist_ok=True)

        # No silent None->BIJECTIVE collapse: every gate-G diff path arms an
        # explicit coherence case (AT-9 BIJECTIVE / AT-10 DROPPED_ROW |
        # SIGNATURE_MISMATCH / AT-11a SUSPECTED_UNCONFIRMABLE). A None case here is
        # a scaffold-authoring error, not a default.
        assert self._case is not None, (
            "a gate-G design↔AT diff scenario must arm an explicit CoherenceCase "
            "(BIJECTIVE / DROPPED_ROW / SIGNATURE_MISMATCH / "
            "SUSPECTED_UNCONFIRMABLE) -- got None (would collapse AT-11a's "
            "UNVERIFIED fixture onto AT-9's BIJECTIVE fixture, an unsatisfiable "
            "spec)."
        )
        case = self._case
        design_rows = self._design_example_rows(case)
        at_scenarios = self._at_scenarios(case)

        (root / "feature-delta.md").write_text(
            self._render_design_contract(design_rows), encoding="utf-8"
        )
        (root / "tests" / "acceptance" / "export_csv.feature").write_text(
            self._render_at_feature(at_scenarios), encoding="utf-8"
        )
        return root

    def _write_unsupported_language_root(self, tmp_path: Path) -> Path:
        """Write a feature-root in a language the AstAdapter cannot parse (OB-G INDETERMINATE)."""
        root = tmp_path / "feature_unsupported_lang"
        (root / "tests" / "acceptance").mkdir(parents=True, exist_ok=True)
        (root / "feature-delta.md").write_text(
            self._render_design_contract(("full-dataset", "empty-dataset")),
            encoding="utf-8",
        )
        # A test file in an unsupported language (e.g. an Elixir AT) -> no
        # AstAdapter can parse it -> the inspection substrate cannot run.
        (root / "tests" / "acceptance" / "export_csv_test.exs").write_text(
            "defmodule ExportCsvTest do\n  use ExUnit.Case\nend\n", encoding="utf-8"
        )
        return root

    @staticmethod
    def _design_example_rows(case: CoherenceCase) -> tuple[str, ...]:
        """The design `[REF] Code-Design` example-table rows per the armed case.

        SUSPECTED_UNCONFIRMABLE uses VAGUE/PLACEHOLDER row identifiers that no D3
        manifest pins (OB-G) -- the row-level diff cannot align them to the AT
        scenarios to confirm a bijection, yet cannot pin a concrete dropped-row
        (the counts match). CONTENT-DISTINCT from the f-export-csv rows the other
        cases use.
        """
        if case is CoherenceCase.SUSPECTED_UNCONFIRMABLE:
            # Loose/placeholder rows -- present but not row-level-alignable.
            return ("row-tbd", "case-2", "misc")
        # f-export-csv declares 3 rows including the empty-dataset row.
        return ("full-dataset", "single-row", "empty-dataset")

    @staticmethod
    def _at_scenarios(case: CoherenceCase) -> tuple[str, ...]:
        """The AT scenarios covering the design rows -- per the armed coherence case."""
        if case is CoherenceCase.DROPPED_ROW:
            # The empty-dataset row was DROPPED -- the bijection is broken (FAIL).
            return ("full-dataset", "single-row")
        if case is CoherenceCase.SIGNATURE_MISMATCH:
            # The AT references a signature the design never declared (FAIL).
            return (
                "full-dataset",
                "single-row",
                "empty-dataset",
                "undeclared-bom-flag",
            )
        if case is CoherenceCase.SUSPECTED_UNCONFIRMABLE:
            # Generic scenario names that DO NOT lexically pin to the loose
            # placeholder design rows -- so the row-level diff can confirm neither
            # a clean bijection (no PASS) nor a concrete divergence (no FAIL): the
            # COUNTS match (3 rows, 3 scenarios) so nothing is provably dropped,
            # but the identifiers do not align so the bijection is unconfirmable
            # -> UNVERIFIED (North-Star cap). CONTENT-DISTINCT from BIJECTIVE.
            return ("scenario-one", "scenario-two", "scenario-three")
        # BIJECTIVE -- every row maps to a covering scenario and vice versa.
        return ("full-dataset", "single-row", "empty-dataset")

    @staticmethod
    def _render_design_contract(rows: tuple[str, ...]) -> str:
        """Render a feature-delta with a prose `[REF] Code-Design` example-table."""
        lines = [
            "# feature-delta f-export-csv",
            "",
            _DESIGN_SECTION_HEADING,
            "",
            "Operation: `export_csv(rows: list[Row], *, bom: bool = False) -> bytes`",
            "",
            "| ExampleTableRow | Input | Output |",
            "|-----------------|-------|--------|",
        ]
        for row in rows:
            lines.append(f"| {row} | <input-{row}> | <output-{row}> |")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _render_at_feature(scenarios: tuple[str, ...]) -> str:
        """Render an AT `.feature` whose scenarios cover (a subset of) the design rows."""
        lines = ["Feature: Operator exports a CSV", ""]
        for scenario in scenarios:
            lines.append(f"  Scenario: Operator exports the {scenario} case")
            lines.append(f"    Given the {scenario} dataset")
            lines.append("    When the operator exports a CSV")
            lines.append(f"    Then the {scenario} CSV is produced")
            lines.append("")
        return "\n".join(lines)

    # =====================================================================
    # diagnostics
    # =====================================================================

    def _require_observable(self) -> GateGObservable:
        if self._observable is None or self._seam_error == _SEAM_ABSENT:
            raise AssertionError(
                "the slice-03 gate-G mechanism (the mechanical design↔AT coherence "
                "diff -- the prose `[REF] Code-Design` example-table read via "
                "`query.adr-section` ↔ the AT-AST read via `query.atoms-in-file`, "
                "returning a §17 GateVerdict) must exist and return a verdict "
                "envelope -- the gate-G seam is ABSENT at HEAD (active-RED; DELIVER "
                "builds src/des/cli/gate_g.py over the slice-01/02 CodeFactPort "
                "substrate, consuming it -- NOT forking it, C2). "
                f"{self._observed()}"
            )
        return self._observable

    def _observed(self) -> str:
        return (
            f"case={self._case!r}; contract_input={self._contract_input!r}; "
            f"observable={self._observable!r}; seam_error={self._seam_error!r}"
        )
