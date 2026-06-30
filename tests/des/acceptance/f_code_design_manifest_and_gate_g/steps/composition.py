"""Composition root for the f-code-design-manifest-and-gate-g ATs.

Mandate-13 driving-port-only. Each behaviour is driven through a REAL production
seam this feature's DESIGN pins:

  * slices 01-03 -> Layer 3 composition: the REAL ``evaluate_gate_g`` callable (its
    manifest-source branch) + the REAL ``validate_component_manifest.validate_manifest``,
    over a real ``tmp_path`` carrying a real ``code-design.manifest.yaml`` + a real
    AT ``.feature`` module. The observable is the returned §17 ``GateVerdict``
    envelope / the validator exit code. No production module is imported-and-called
    at the step boundary for its business logic; the step bodies delegate to these
    composition methods (Mandate-12 -- no logic in step bodies).
  * slice-04 -> Layer 3 subprocess: the WIRED ``des gate-design-at-coherence``
    dispatch (``python -m des.cli.__main__ gate-design-at-coherence ...``), plus
    reads of the shipped wiring artifacts (``_REGISTRY`` / ``_catalog.yaml`` /
    ``atdd_pure.yaml``) -- the wiring membership is DATA the SUT ships.

active-RED scaffold (atdd_pure -- NOT @skip): at HEAD the net-new seams are ABSENT
(verified):
  * ``nWave/schemas/code-design-manifest.schema.json`` does not exist;
  * ``evaluate_gate_g`` reads PROSE only (no ``code-design.manifest.yaml`` branch,
    no ``@row:`` tag parser -- it has a hardcoded ``_SCENARIO_LINE`` regex);
  * ``validate_component_manifest._check_sut_grounding`` iterates ONLY
    ``unbounded-input-domains`` (no ``example-tables[].sut`` widening);
  * ``des gate-design-at-coherence`` has no ``_REGISTRY`` row, no ``_catalog.yaml``
    entry, no ``atdd_pure.yaml`` ``distill.gate-out`` membership.
Each driving-port invocation captures the absent/unbuilt behaviour as an observable
the ``Then`` reads, firing a NAMED semantic ``AssertionError`` (the expected
behaviour is missing because the seam is unbuilt) -- never a collection / import /
setup error. GREEN once DELIVER lands the four slices.

DESIGN-CONTRACT ASSUMPTIONS flagged to DELIVER (state-here-so-DELIVER-matches --
the SEAM, never a line number):
  A1 (manifest path + key): the manifest lives at
     ``docs/feature/{id}/design/code-design.manifest.yaml`` (DDD-1) with a
     load-bearing ``example-tables:`` list, each row ``{row-id, sut, description}``
     (DDD-2). This composition writes that shape under ``tmp_path``. If DELIVER
     names the key/path differently, update ``_render_manifest``.
  A2 (gate-G manifest-source signature): ``evaluate_gate_g`` keeps its
     ``(design_contract_path, at_module_path)`` signature; the manifest-source
     branch fires when a ``code-design.manifest.yaml`` sits beside the feature-delta
     (or is passed as ``design_contract_path``). This composition passes the
     manifest path as ``design_contract_path`` and the AT dir as
     ``at_module_path``; on a ``TypeError`` it retries a single feature-root arg.
     If DELIVER chooses a different manifest-discovery rule, update ``_drive_gate_g``.
  A3 (@row: tag convention): the AT scenario declares its join key via a
     ``@row:<row-id>`` Gherkin tag on the line ABOVE the ``Scenario:`` line (DDD-4 /
     CT-10). This composition renders that exact shape. If DELIVER reads the tag
     differently, update ``_render_at_feature``.
  A4 (subcommand id): the wired subcommand is ``des gate-design-at-coherence``
     (DDD-5). slice-04 drives it via subprocess; the wiring artifacts are read at
     their DESIGN-pinned paths.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from scripts.cli import validate_component_manifest
from tests.common.in_process_cli import run_cli_in_process

from .domain_types import (
    LOCKED_GATE_VERDICTS,
    CoherenceCase,
    ContractInput,
    GateGObservable,
    GateVerdict,
    ManifestHealth,
    ValidationObservable,
)


# Sentinel an absent seam invocation records, so the Then can name the missing
# behaviour instead of letting an ImportError escape as a collection error.
_SEAM_ABSENT = "__SEAM_ABSENT__"

# The prose design block gate-G falls back to (CT-7); also the manifest section
# heading is the absence of this block.
_DESIGN_SECTION_HEADING = "## Wave: DESIGN / [REF] Code-Design"

# Repo root (this file: tests/des/acceptance/<feature>/steps/composition.py).
_REPO_ROOT = Path(__file__).resolve().parents[5]

# A real, grep-findable symbol in a real repo file -- the manifest `sut:` points
# here so the schema-valid-grounded case grounds against a TRUE symbol (CT-1/CT-4).
_REAL_SUT = "src/des/cli/gate_g.py::evaluate_gate_g"
_STALE_SUT = "src/des/cli/gate_g.py::a_symbol_that_does_not_exist_anywhere"


@dataclass
class ManifestGateComposition:
    """Drives the f-code-design-manifest-and-gate-g seams through real driving ports."""

    _case: CoherenceCase | None = field(default=None)
    _contract_input: ContractInput = field(default=ContractInput.MANIFEST)
    _manifest_health: ManifestHealth | None = field(default=None)

    _gate_observable: GateGObservable | None = field(default=None)
    _validation: ValidationObservable | None = field(default=None)
    _seam_error: str | None = field(default=None)

    # =====================================================================
    # Given -- arm the coherence case / contract-input / manifest health
    # =====================================================================

    def given_coherence_case(self, case: CoherenceCase) -> None:
        """Arm the manifest ``row-id`` ↔ AT ``@row:`` tag bijection shape."""
        self._case = case
        self._contract_input = ContractInput.MANIFEST

    def given_contract_input(self, contract_input: ContractInput) -> None:
        """Arm which design source gate-G reads (manifest / prose / neither / unsupported)."""
        self._contract_input = contract_input

    def given_manifest_health(self, health: ManifestHealth) -> None:
        """Arm the DESIGN-OUT manifest-validation health (schema-valid / stale / invalid)."""
        self._manifest_health = health

    # =====================================================================
    # When -- drive the REAL gate-G manifest-source diff over a real tmp_path
    # =====================================================================

    def when_gate_g_reads_manifest(self, tmp_path: Path) -> None:
        """Drive the REAL gate-G mechanism reading the manifest ``example-tables:``.

        Writes a real feature-root under ``tmp_path`` (a ``code-design.manifest.yaml``
        carrying ``example-tables:`` ``row-id``s + an AT module whose scenarios carry
        ``@row:`` tags) per the armed coherence case, then asks gate-G to diff them.
        The observable is the returned §17 verdict envelope.
        """
        feature_root = self._write_feature_root(tmp_path)
        self._gate_observable = self._drive_gate_g(feature_root)

    def when_gate_g_reads_contract(self, tmp_path: Path) -> None:
        """Drive gate-G over the armed contract-input shape (prose / neither / unsupported).

        Used by slice-03 fallback + INDETERMINATE scenarios where the design source
        is NOT a manifest. Writes the matching feature-root and drives gate-G.
        """
        feature_root = self._write_contract_input_root(tmp_path)
        self._gate_observable = self._drive_gate_g(feature_root)

    def when_gate_g_reads_contract_or_manifest(self, tmp_path: Path) -> None:
        """Route the gate-G drive by the armed contract-input (the shared When seam).

        MANIFEST -> the manifest-source diff (slices 01/02 + the slice-03 bijective
        case). PROSE_FALLBACK / NEITHER / UNSUPPORTED_LANGUAGE -> the contract-input
        drive (slice-03 fallback + INDETERMINATE). One driving-port surface, the
        armed input shape selects the fixture.
        """
        if self._contract_input is ContractInput.MANIFEST:
            self.when_gate_g_reads_manifest(tmp_path)
        else:
            self.when_gate_g_reads_contract(tmp_path)

    def write_dispatch_root(self, tmp_path: Path) -> Path:
        """Write a real bijective manifest+AT feature-root for the slice-04 dispatch.

        slice-04's subprocess dispatch needs real ``--design`` / ``--at-module``
        paths; this writes the same bijective fixture the gate-G PASS case uses and
        returns the feature-root so the wiring composition can dispatch against it.
        """
        self.given_coherence_case(CoherenceCase.BIJECTIVE)
        return self._write_feature_root(tmp_path)

    def when_manifest_is_validated(self, tmp_path: Path) -> None:
        """Drive the REAL ``validate_component_manifest`` over the armed health (CT-4).

        Writes a real ``code-design.manifest.yaml`` whose ``example-tables[].sut`` is
        grounded / stale / schema-invalid per the armed health, then runs the
        WIDENED validator. The observable is the exit code + the stderr diagnostic.
        """
        manifest_path = self._write_manifest_for_validation(tmp_path)
        self._validation = self._drive_validator(manifest_path)

    # =====================================================================
    # Then -- observable readers (the §17 verdict + the validator exit)
    # =====================================================================

    def then_verdict_is(self, expected: GateVerdict) -> None:
        """gate-G returned EXACTLY the expected §17 verdict (one of the LOCKED five)."""
        obs = self._require_gate_observable()
        assert obs.verdict in LOCKED_GATE_VERDICTS, (
            f"gate-G must return one of the §17 LOCKED FIVE verdicts "
            f"{sorted(LOCKED_GATE_VERDICTS)!r} (ADR-GV-001, no sixth -- AT-A3/DDD-7) "
            f"-- got verdict={obs.verdict!r}. {self._observed()}"
        )
        assert obs.verdict == expected.value, (
            f"gate-G must return {expected.value!r} for this manifest-backed "
            f"design↔AT coherence case -- got {obs.verdict!r}. {self._observed()}"
        )

    def then_diagnostic_names(self, fragment: str) -> None:
        """On FAIL/UNVERIFIED, gate-G names the divergence/cap (a non-empty diagnostic
        mentioning ``fragment`` -- the dropped/undeclared ``row-id`` or the untagged
        scenario). The mechanical witness, not an LLM say-so."""
        obs = self._require_gate_observable()
        assert obs.diagnostic, (
            f"gate-G must return a NON-EMPTY diagnostic naming the divergence "
            f"(mentioning {fragment!r}) -- the mechanical witness -- but the "
            f"diagnostic was empty. {self._observed()}"
        )
        assert fragment in obs.diagnostic, (
            f"gate-G's diagnostic must NAME the specific divergence -- it must "
            f"mention {fragment!r} (a confirmed dropped/undeclared row-id, or the "
            f"untagged scenario, never a silent ignore) -- got diagnostic="
            f"{obs.diagnostic!r}. {self._observed()}"
        )

    def then_north_star_cap_is_surfaced_loud(self) -> None:
        """On the prose-fallback case, the North-Star cap is surfaced LOUD (CT-7)."""
        obs = self._require_gate_observable()
        assert obs.cap_surfaced, (
            f"the prose `[REF] Code-Design` fallback (no manifest) must surface the "
            f"North-Star UNVERIFIED cap LOUD in the verdict envelope (no regression "
            f"-- CT-7) -- the cap was NOT surfaced. {self._observed()}"
        )

    def then_cap_not_surfaced(self) -> None:
        """A manifest-backed verdict is deterministic -- the North-Star cap is NOT
        surfaced (CT-1: the manifest's stable row-id makes the bijection
        confirmable, so PASS/FAIL is reached without the prose-era UNVERIFIED cap)."""
        obs = self._require_gate_observable()
        assert not obs.cap_surfaced, (
            f"a manifest-backed coherence verdict must be DETERMINISTIC -- the "
            f"North-Star UNVERIFIED cap must NOT be surfaced (the stable example-table "
            f"row-id is the join key that closes the deferred D3 -- no cap on a "
            f"manifest-backed bijection) -- but the cap was surfaced. {self._observed()}"
        )

    def then_gate_g_did_not_run(self) -> None:
        """On unsupported AT language, gate-G degraded LOUD (INDETERMINATE -- CT-6)."""
        obs = self._require_gate_observable()
        assert not obs.ran, (
            f"when the CodeFactPort AstAdapter cannot run (unsupported AT language) "
            f"gate-G must NOT fabricate a mechanical-diff result -- it must degrade "
            f"LOUD to INDETERMINATE (the mechanism could not run) -- gate-G reported "
            f"it ran a real diff. {self._observed()}"
        )

    def then_validator_accepts(self) -> None:
        """The manifest is schema-valid + every sut: grounded -> validator exit 0 (CT-4)."""
        obs = self._require_validation()
        assert obs.exit_code == 0, (
            f"a schema-valid manifest whose every `example-tables[].sut` symbol is "
            f"grep-findable must be ACCEPTED (exit 0) by the WIDENED validator "
            f"(review MEDIUM-1: the sut-key iteration now scans example-tables, not "
            f"only unbounded-input-domains) -- got exit_code={obs.exit_code!r}, "
            f"message={obs.message!r}. {self._observed()}"
        )

    def then_validator_rejects(self) -> None:
        """The manifest is stale/schema-invalid -> validator exit ≠ 0 (CT-4)."""
        obs = self._require_validation()
        assert obs.exit_code is not None and obs.exit_code != 0, (
            f"a manifest naming a stale `example-tables[].sut` symbol OR violating "
            f"the schema must be REJECTED (exit ≠ 0) by the WIDENED validator "
            f"(CT-4 / DDD-6 -- a stale symbol never reads as PASS) -- got "
            f"exit_code={obs.exit_code!r}. {self._observed()}"
        )

    # =====================================================================
    # driving-port invocation (lazy seam import -> sentinel on absence)
    # =====================================================================

    def _drive_gate_g(self, feature_root: Path) -> GateGObservable:
        """Drive the REAL gate-G callable over the real feature-root (A2/A3).

        At HEAD ``evaluate_gate_g`` has NO manifest-source branch -> reading a
        manifest-backed feature-root cannot produce the deterministic PASS/FAIL the
        ATs expect (it would fall to the prose path / NOT_APPLICABLE), so the Then
        fires the named RED. GREEN once DELIVER lands the manifest-source read.
        """
        try:
            from des.cli import gate_g as gate_g_module
        except (ImportError, ModuleNotFoundError):
            self._seam_error = _SEAM_ABSENT
            return self._absent_gate_observable()

        callable_ = getattr(gate_g_module, "evaluate_gate_g", None)
        if not callable(callable_):
            self._seam_error = _SEAM_ABSENT
            return self._absent_gate_observable()

        manifest_path = feature_root / "design" / "code-design.manifest.yaml"
        design_path = (
            manifest_path
            if manifest_path.is_file()
            else (feature_root / "feature-delta.md")
        )
        at_module_path = feature_root / "tests" / "acceptance"
        try:
            result = callable_(
                design_contract_path=design_path,
                at_module_path=at_module_path,
            )
        except TypeError:
            try:
                result = callable_(feature_root)
            except Exception:
                self._seam_error = _SEAM_ABSENT
                return self._absent_gate_observable()
        return self._read_envelope(result)

    def _drive_validator(self, manifest_path: Path) -> ValidationObservable:
        """Drive the REAL ``validate_component_manifest`` over the manifest (CT-4).

        Runs as a subprocess so the WIDENED schema (``code-design-manifest.schema.json``)
        and sut-key iteration are exercised end-to-end. At HEAD the validator scans
        only ``unbounded-input-domains`` and the broad schema is absent, so a manifest
        with ONLY ``example-tables[].sut`` either schema-fails on the narrow schema or
        passes WITHOUT grounding the example-tables sut -> the Then fires the named RED.
        """
        exit_code, stdout, stderr = run_cli_in_process(
            [str(manifest_path)],
            cwd=str(_REPO_ROOT),
            main=validate_component_manifest.main,
        )
        return ValidationObservable(
            exit_code=exit_code,
            message=(stderr or stdout or None),
        )

    # =====================================================================
    # envelope reader + absent-seam observable
    # =====================================================================

    def _read_envelope(self, result: object) -> GateGObservable:
        """Read the port-exposed §17 verdict + diagnostic + cap-surfaced + ran."""
        verdict = self._token(self._field(result, "verdict"))
        diagnostic = self._field(result, "diagnostic", "reason", "message")
        cap_surfaced = bool(
            self._field(result, "cap_surfaced", "north_star_cap", "capped") or False
        )
        if verdict is None and isinstance(result, tuple) and result:
            verdict = self._token(result[0])
            diagnostic = result[1] if len(result) > 1 else diagnostic
        ran_field = self._field(result, "ran", "mechanism_ran")
        ran = bool(ran_field) if ran_field is not None else verdict is not None
        return GateGObservable(
            verdict=verdict,
            diagnostic=diagnostic if isinstance(diagnostic, str) else None,
            cap_surfaced=cap_surfaced,
            ran=ran,
        )

    def _absent_gate_observable(self) -> GateGObservable:
        return GateGObservable(
            verdict=None, diagnostic=None, cap_surfaced=False, ran=False
        )

    @staticmethod
    def _field(obj: object, *names: str) -> object:
        for name in names:
            value = getattr(obj, name, None)
            if value is not None:
                return value
            if isinstance(obj, dict) and name in obj:
                return obj[name]
        return None

    @staticmethod
    def _token(value: object) -> str | None:
        if value is None:
            return None
        return getattr(value, "value", value)

    # =====================================================================
    # substrate plumbing -- a real manifest-backed feature-root (real I/O)
    # =====================================================================

    def _write_feature_root(self, tmp_path: Path) -> Path:
        """Write a real feature-root: a ``code-design.manifest.yaml`` + an AT module.

        Per the armed coherence case the manifest ``row-id``s and the AT ``@row:``
        tags are bijective (PASS), a row is dropped (FAIL), a scenario references an
        undeclared row-id (FAIL), or a scenario is untagged (UNVERIFIED). Each case
        writes a CONTENT-DISTINCT on-disk fixture so a deterministic gate-G can return
        a different verdict per case.
        """
        assert self._case is not None, (
            "a manifest-backed gate-G scenario must arm an explicit CoherenceCase "
            "(BIJECTIVE / DROPPED_ROW / UNDECLARED_SCENARIO / UNTAGGED_SCENARIO) -- "
            "got None (would collapse distinct fixtures, an unsatisfiable spec)."
        )
        root = tmp_path / "feature_under_diff" / self._case.value
        (root / "design").mkdir(parents=True, exist_ok=True)
        (root / "tests" / "acceptance").mkdir(parents=True, exist_ok=True)

        manifest_rows = self._manifest_row_ids(self._case)
        at_rows = self._at_tagged_rows(self._case)
        untagged = self._case is CoherenceCase.UNTAGGED_SCENARIO

        (root / "design" / "code-design.manifest.yaml").write_text(
            self._render_manifest(manifest_rows), encoding="utf-8"
        )
        (root / "tests" / "acceptance" / "manifest_backed.feature").write_text(
            self._render_at_feature(at_rows, untagged=untagged), encoding="utf-8"
        )
        return root

    def _write_contract_input_root(self, tmp_path: Path) -> Path:
        """Write a feature-root for the prose / neither / unsupported-language cases."""
        root = tmp_path / "feature_contract_input" / self._contract_input.value
        (root / "tests" / "acceptance").mkdir(parents=True, exist_ok=True)

        if self._contract_input is ContractInput.PROSE_FALLBACK:
            # No manifest; a LOOSE prose [REF] Code-Design table whose row identifiers
            # the row-level diff cannot align to the AT @row: tags -> the EXISTING
            # North-Star UNVERIFIED cap (CT-7). Construction (CT-7-correct, review
            # CRITICAL-1 intent honoured): the prose table declares 3 loose rows
            # {row-tbd, case-2, misc} AND the AT declares 3 @row:-tagged scenarios
            # whose tags are DISJOINT from the prose rows, with EQUAL counts. The
            # generalized @row: reader (post-DELIVER) finds 3 disjoint tags vs 3 prose
            # rows -> counts match, no overlap -> _is_confirmable_divergence False ->
            # UNVERIFIED + cap. At HEAD the @row: parser does not exist (the seam this
            # feature builds): the hardcoded _SCENARIO_LINE matches none of the
            # general-wording scenarios -> 3 rows vs 0 subjects -> FAIL. RED for the
            # RIGHT reason (the @row: seam is absent), GREEN once DELIVER lands it.
            #
            # NOTE to review (CRITICAL-1): the literal "design_rows=[] (prose without a
            # markdown table)" suggestion would make HEAD return PASS (both sides
            # empty) and post-DELIVER return FAIL (0 rows vs 3 @row: tags -> undeclared
            # non-empty, counts differ -> confirmable) -- it contradicts CT-7's own
            # semantics (the existing UNVERIFIED cap fires only on PRESENT-but-loose
            # prose rows). The fixture below preserves the cap as DDD-3/CT-7 specify.
            (root / "feature-delta.md").write_text(
                self._render_prose_contract(("row-tbd", "case-2", "misc")),
                encoding="utf-8",
            )
            (root / "tests" / "acceptance" / "loose.feature").write_text(
                self._render_at_feature(
                    ("scenario-one", "scenario-two", "scenario-three"), untagged=False
                ),
                encoding="utf-8",
            )
        elif self._contract_input is ContractInput.PROSE_GENERAL_WORDING_BIJECTIVE:
            # CT-5 / slice-03 mechanical witness of the `_SCENARIO_LINE` REMOVAL on
            # the PROSE path. No manifest; a prose [REF] Code-Design table declaring
            # two rows {full-dataset, empty-dataset} that ARE covered, one-to-one, by
            # acceptance scenarios written in GENERAL wording (NOT "Operator exports
            # the X case") -- each carrying its row identifier as a `@row:` tag (the
            # join key the generalized reader reads on either side).
            #
            # At HEAD the prose path runs `_scenario_subjects`, whose hardcoded
            # `_SCENARIO_LINE` regex (gate_g.py:99) matches ONLY the
            # "Operator exports the X case" form -> it matches NONE of the
            # general-wording scenarios -> 2 prose rows vs 0 subjects -> the diff
            # treats both rows as uncovered -> FAIL (probed live). RED for the RIGHT
            # reason: the single-feature regex cannot see a general-wording scenario.
            # GREEN once DELIVER replaces `_SCENARIO_LINE` with the general `@row`
            # reader on the prose path too -> the two scenarios are recognized,
            # bijective with the prose rows -> PASS. This is the MECHANICAL witness
            # that the single-feature probe is gone (slice-03's thesis).
            (root / "feature-delta.md").write_text(
                self._render_prose_contract(("full-dataset", "empty-dataset")),
                encoding="utf-8",
            )
            (root / "tests" / "acceptance" / "general.feature").write_text(
                self._render_at_feature(
                    ("full-dataset", "empty-dataset"), untagged=False
                ),
                encoding="utf-8",
            )
        elif self._contract_input is ContractInput.NEITHER:
            # Neither manifest nor prose -> NOT_APPLICABLE (CT-7).
            (root / "feature-delta.md").write_text(
                "# feature-delta with no Code-Design contract\n", encoding="utf-8"
            )
            (root / "tests" / "acceptance" / "any.feature").write_text(
                "Feature: anything\n  Scenario: a\n    Given x\n", encoding="utf-8"
            )
        else:  # UNSUPPORTED_LANGUAGE
            # CT-6 SUT (feature-delta): `evaluate_gate_g` + `_indeterminate` over the
            # MANIFEST-source path -- the manifest branch this feature adds must
            # ALSO degrade LOUD to INDETERMINATE when the AT module is in a language
            # the AstAdapter cannot parse. So the design contract is a real
            # `code-design.manifest.yaml` (the new source) + an Elixir `.exs` AT
            # module (unparseable). At HEAD there is no manifest-source branch -> the
            # YAML is read as the design contract, finds no prose `[REF] Code-Design`
            # block -> NOT_APPLICABLE: RED for the RIGHT reason (the manifest-source
            # seam + its language probe are absent). Post-DELIVER the manifest branch
            # fires, probes the `.exs` AT -> the substrate cannot run -> INDETERMINATE
            # (GREEN). This witnesses CT-6 over THIS feature's net-new path, NOT the
            # pre-existing prose path (which already returns INDETERMINATE at HEAD =
            # a false-green; review CRITICAL-2 prose-path suggestion adjusted to keep
            # the scenario active-RED + cover the actual delta).
            (root / "design").mkdir(parents=True, exist_ok=True)
            (root / "design" / "code-design.manifest.yaml").write_text(
                self._render_manifest(("full-dataset", "empty-dataset")),
                encoding="utf-8",
            )
            # An AT module in a language the AstAdapter cannot parse (Elixir .exs).
            (root / "tests" / "acceptance" / "export_test.exs").write_text(
                "defmodule ExportTest do\n  use ExUnit.Case\nend\n", encoding="utf-8"
            )
        return root

    def _write_manifest_for_validation(self, tmp_path: Path) -> Path:
        """Write a ``code-design.manifest.yaml`` per the armed ManifestHealth (CT-4)."""
        assert self._manifest_health is not None, (
            "a manifest-validation scenario must arm an explicit ManifestHealth "
            "(SCHEMA_VALID_GROUNDED / STALE_SYMBOL / SCHEMA_INVALID) -- got None."
        )
        manifest_dir = tmp_path / "design"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        path = manifest_dir / "code-design.manifest.yaml"

        if self._manifest_health is ManifestHealth.SCHEMA_VALID_GROUNDED:
            path.write_text(
                self._render_grounded_manifest(sut=_REAL_SUT), encoding="utf-8"
            )
        elif self._manifest_health is ManifestHealth.STALE_SYMBOL:
            path.write_text(
                self._render_grounded_manifest(sut=_STALE_SUT), encoding="utf-8"
            )
        else:  # SCHEMA_INVALID -- an example-tables row missing its required row-id
            path.write_text(self._render_schema_invalid_manifest(), encoding="utf-8")
        return path

    # ---- manifest + AT fixture renderers (A1/A2/A3) ----------------------

    @staticmethod
    def _manifest_row_ids(case: CoherenceCase) -> tuple[str, ...]:
        """The manifest ``example-tables:`` ``row-id``s declared per the armed case."""
        if case is CoherenceCase.EMPTY_BIJECTIVE:
            # The C3 ZERO case: a manifest declaring no example-table rows.
            return ()
        # The contract: three declared rows. DROPPED_ROW omits one on the AT side.
        return ("full-dataset", "single-row", "empty-dataset")

    @staticmethod
    def _at_tagged_rows(case: CoherenceCase) -> tuple[str, ...]:
        """The ``@row:`` tags the AT scenarios carry, per the armed case."""
        if case is CoherenceCase.EMPTY_BIJECTIVE:
            # Zero covering scenarios -> a vacuous bijection against zero rows.
            return ()
        if case is CoherenceCase.DROPPED_ROW:
            # `empty-dataset` row has NO covering AT scenario -> FAIL (CT-2).
            return ("full-dataset", "single-row")
        if case is CoherenceCase.UNDECLARED_SCENARIO:
            # An AT scenario tags a row-id the manifest never declares -> FAIL (CT-3).
            return (
                "full-dataset",
                "single-row",
                "empty-dataset",
                "undeclared-bom-flag",
            )
        if case is CoherenceCase.UNTAGGED_SCENARIO:
            # Handled by the `untagged=True` flag in _render_at_feature -- the rows
            # listed here are tagged; the renderer appends ONE untagged scenario.
            return ("full-dataset", "single-row", "empty-dataset")
        # BIJECTIVE -- every row tagged, every tag a declared row.
        return ("full-dataset", "single-row", "empty-dataset")

    def _render_manifest(self, row_ids: tuple[str, ...]) -> str:
        """Render a ``code-design.manifest.yaml`` with an ``example-tables:`` block (A1)."""
        lines = [
            "schema-version: '1.0'",
            "feature-id: f-under-diff",
            "example-tables:",
        ]
        for row_id in row_ids:
            lines.append(f"  - row-id: {row_id}")
            lines.append(f"    sut: {_REAL_SUT}")
            lines.append(f"    description: the {row_id} example case")
        lines.append("")
        return "\n".join(lines)

    def _render_grounded_manifest(self, sut: str) -> str:
        """Render a manifest whose example-tables sut is the given (grounded/stale) ref."""
        return (
            "schema-version: '1.0'\n"
            "feature-id: f-validation\n"
            "example-tables:\n"
            "  - row-id: only-row\n"
            f"    sut: {sut}\n"
            "    description: the only example case\n"
        )

    def _render_schema_invalid_manifest(self) -> str:
        """Render a manifest with an example-tables row MISSING its required row-id."""
        return (
            "schema-version: '1.0'\n"
            "feature-id: f-validation\n"
            "example-tables:\n"
            f"  - sut: {_REAL_SUT}\n"
            "    description: a row missing its required row-id\n"
        )

    @staticmethod
    def _render_prose_contract(rows: tuple[str, ...]) -> str:
        """Render a feature-delta with a LOOSE prose `[REF] Code-Design` example-table."""
        lines = [
            "# feature-delta prose-only",
            "",
            _DESIGN_SECTION_HEADING,
            "",
            "| ExampleTableRow | Input | Output |",
            "|-----------------|-------|--------|",
        ]
        for row in rows:
            lines.append(f"| {row} | <in-{row}> | <out-{row}> |")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _render_at_feature(rows: tuple[str, ...], *, untagged: bool) -> str:
        """Render an AT `.feature` whose scenarios declare ``@row:`` tags (A3).

        Each scenario carries a ``@row:<row-id>`` tag on the line above the
        ``Scenario:`` line. When ``untagged`` is True, ONE extra scenario is
        appended with NO ``@row:`` tag (the CT-10b no-silent-pass case).
        """
        lines = ["Feature: A manifest-backed feature", ""]
        for row in rows:
            lines.append(f"  @row:{row}")
            lines.append(f"  Scenario: the {row} behaviour is delivered")
            lines.append(f"    Given the {row} precondition")
            lines.append("    When the operator runs the behaviour")
            lines.append(f"    Then the {row} outcome is observed")
            lines.append("")
        if untagged:
            lines.append("  Scenario: an outcome with no row tag declared")
            lines.append("    Given a precondition with no join key")
            lines.append("    When the operator runs the behaviour")
            lines.append("    Then an outcome is observed")
            lines.append("")
        return "\n".join(lines)

    # ---- the row-id a Then names (the confirmed divergence) --------------

    @staticmethod
    def dropped_row_id() -> str:
        return "empty-dataset"

    @staticmethod
    def undeclared_row_id() -> str:
        return "undeclared-bom-flag"

    @staticmethod
    def untagged_scenario_fragment() -> str:
        return "an outcome with no row tag declared"

    # =====================================================================
    # diagnostics
    # =====================================================================

    def _require_gate_observable(self) -> GateGObservable:
        if self._gate_observable is None or self._seam_error == _SEAM_ABSENT:
            raise AssertionError(
                "the manifest-backed gate-G mechanism (evaluate_gate_g reading the "
                "`code-design.manifest.yaml` `example-tables:` row-ids ↔ the AT "
                "`@row:` tags, returning a deterministic §17 GateVerdict) must exist "
                "and return a verdict envelope -- the manifest-source seam is ABSENT "
                "at HEAD (active-RED; DELIVER builds the manifest-source branch + the "
                "@row: parser in src/des/cli/gate_g.py). "
                f"{self._observed()}"
            )
        return self._gate_observable

    def _require_validation(self) -> ValidationObservable:
        if self._validation is None:
            raise AssertionError(
                "the WIDENED manifest validator (validate_component_manifest scanning "
                "example-tables[].sut, not only unbounded-input-domains) must run and "
                "return an exit code -- the validation seam was not driven. "
                f"{self._observed()}"
            )
        return self._validation

    def _observed(self) -> str:
        return (
            f"case={self._case!r}; contract_input={self._contract_input!r}; "
            f"manifest_health={self._manifest_health!r}; "
            f"gate_observable={self._gate_observable!r}; "
            f"validation={self._validation!r}; seam_error={self._seam_error!r}"
        )
