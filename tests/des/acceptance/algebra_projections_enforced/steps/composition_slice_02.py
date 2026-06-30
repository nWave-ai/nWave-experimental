"""Composition roots for the algebra-projections-enforced slice-02 ATs (Mandate-13).

Two driving-port-only composition roots, BOTH driving the REAL DELIVER-entry
contract-freeze gate (ADR-002: direction (b) completeness lives at the
DELIVER-entry surface, not on the standalone ``validate-feature-delta`` flag):

  * ``MandatorySectionComposition`` drives the direction-(b) COMPLETENESS oracle
    through the REAL DELIVER-entry gate (Layer 3 subprocess: ``python -m
    des.cli.__main__ verify-deliver-entry-contract --feature-id <id> --repo-root
    <tmp> --format=json``), over a real temp repo carrying a real
    ``feature-delta.md``. The mandatory contract this gate freezes is the four
    LOCKED ``[REF]`` sections (``_DELIVER_LOCKED_CONTRACT``), read via
    ``missing_registry_sections`` at ``verify_deliver_entry_contract.py:193``.
  * ``DeliverEntryByteStableComposition`` drives the byte-stable migration
    regression-witness through the SAME REAL gate. This gate IS REGISTERED AND
    FUNCTIONAL at HEAD (it shipped in f-deliver-entry-contract-freeze).

Classification (atdd_pure — NOT @skip; honest per the pre-DELIVER
fail-for-right-reason gate):

  * ``MandatorySectionComposition`` scenarios are PRESERVATION-GUARDS, GREEN at
    HEAD. The DELIVER-entry gate ALREADY calls ``missing_registry_sections`` at
    ``:193`` against ``_DELIVER_LOCKED_CONTRACT`` and ALREADY names the missing
    section in its FAIL diagnostic; presence is ALREADY heading-based
    (``validate_feature_delta.py:574``), so an empty-body locked section ALREADY
    freezes. The direction-(b) completeness surface was always THIS gate (ADR-002:
    the call site at ``:193`` pre-exists; the slice-02 byte-stable migration IS
    direction-(b) realised). These scenarios pin the direction-(b) SEMANTICS (the
    specific missing section is named; an honest-empty section is not a failure) —
    distinct from the byte-stability witnesses, which pin that ALL FOUR sections
    are named after the swap.
  * ``DeliverEntryByteStableComposition`` scenarios are GREEN at HEAD (the gate
    works pre-migration) — they go RED only if a future DELIVER swap breaks the
    byte-stable contract (the whole point of the witness).

Hermetic: every subprocess ``cwd`` is the tmp repo and a ``.git/`` marker is
seeded so the runtime-freshness gate AUTOSKIPS (dev-checkout); the real developer
home / personal-hook path is never touched.

DELIVER-pinned assumptions (update HERE, not in the step bodies):

  A1 (direction-b surface): ``des verify-deliver-entry-contract --feature-id <id>
     --repo-root <path> --format=json``; JSON ``verdict`` in the §17 token set
     (slice-02 pins ``pass`` + ``fail``).
  A2 (direction-b FAIL diagnostic): on ``fail`` over a missing locked section the
     JSON ``diagnostic`` NAMES the omitted locked section id verbatim.
  A3 (empty-body presence): presence is heading-based — a locked section whose
     heading is present but whose body is empty SATISFIES the completeness check
     (the WD-5 structural analogue at this surface); the gate FREEZES (PASS).
  A4 (DELIVER-entry byte-stability oracle): on a missing-locked-section FAIL the
     ``diagnostic`` NAMES all four locked sections (DELIVER_ENTRY_LOCKED_SECTIONS).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process
from tests.env_parity import seed_dev_checkout_marker

from .domain_types_slice_02 import (
    DELIVER_ENTRY_LOCKED_SECTIONS,
    DeliverEntryShape,
    FreezeVerdict,
    MandatoryDeltaShape,
)


# ---------------------------------------------------------------------------
# Shared driving-port subcommand ids.
# ---------------------------------------------------------------------------

_DELIVER_ENTRY_SUBCOMMAND = "verify-deliver-entry-contract"

# A real, grep-findable feature-id the temp feature-delta self-identifies as.
_FEATURE_ID = "algebra-projections-enforced-slice02-fixture"

# The one locked section the OMITS_ONE_LOCKED shape drops (A2). The FAIL diagnostic
# must NAME it. A real `_DELIVER_LOCKED_CONTRACT` id (NOT fabricated).
_OMITTED_LOCKED_SECTION = "ADR Refs"

# The one locked section the ONE_SECTION_EMPTY shape renders heading-present /
# body-empty (A3). Presence is heading-based, so this still SATISFIES completeness.
_EMPTIED_LOCKED_SECTION = "Architecture & Contract Tests"


# =============================================================================
# Direction (b): mandatory locked-section completeness — DELIVER-entry port
# =============================================================================


@dataclass
class _FreezeCheckObservable:
    """What the DELIVER-entry freeze gate emitted for one completeness invocation."""

    verdict: str | None
    diagnostic: str | None
    raw: str


@dataclass
class MandatorySectionComposition:
    """Drives the direction-(b) completeness oracle through the REAL DELIVER-entry gate.

    ADR-002: completeness (every mandatory LOCKED section present) is enforced at
    ``des verify-deliver-entry-contract``, not on the standalone flag. PRESERVATION-
    GUARD (GREEN at HEAD): the gate already fails a missing-locked-section contract
    naming the section, and already freezes an empty-body (heading-present) section.
    """

    _shape: MandatoryDeltaShape | None = field(default=None)
    _feature_id: str = field(default=_FEATURE_ID)
    _delta_path: Path | None = field(default=None)
    _observable: _FreezeCheckObservable | None = field(default=None)
    _universe_before: dict[str, object] | None = field(default=None)

    # --- Given ---------------------------------------------------------------

    def given_delta_shape(self, shape: MandatoryDeltaShape) -> None:
        """Arm which locked-section completeness shape the contract carries."""
        self._shape = shape

    # --- When ----------------------------------------------------------------

    def when_the_freeze_gate_runs(self, tmp_path: Path) -> None:
        """Write a real temp repo for the armed shape, then run the REAL gate (A1)."""
        repo_root = self._write_repo(tmp_path)
        self._universe_before = self.capture_universe()
        self._observable = self._drive_gate(repo_root)

    # --- Then ----------------------------------------------------------------

    def then_verdict_is(self, expected: FreezeVerdict) -> None:
        """The gate returned EXACTLY the expected §17 verdict (A1)."""
        observed = self._observed_verdict()
        assert observed == expected, (
            f"the direction-(b) completeness oracle at the DELIVER-entry gate must "
            f"emit {expected.value!r} for this contract shape "
            f"({self._shape.value if self._shape else '?'}) — got "
            f"{observed.value if observed else observed!r}. {self._diag()}"
        )

    def then_rejection_names_the_omitted_section(self) -> None:
        """The missing-mandatory FAIL diagnostic NAMES the omitted locked section (A2)."""
        diagnostic = self._require_observable().diagnostic
        assert diagnostic is not None and _OMITTED_LOCKED_SECTION in diagnostic, (
            f"the missing-mandatory refusal must NAME the omitted locked section "
            f"{_OMITTED_LOCKED_SECTION!r} in its diagnostic so the maintainer knows "
            f"what to author — the emitted diagnostic was {diagnostic!r}. "
            f"{self._diag()}"
        )

    def then_no_diagnostic(self) -> None:
        """A frozen (PASS) contract emits an empty diagnostic (A3)."""
        diagnostic = self._require_observable().diagnostic
        assert diagnostic == "", (
            f"a frozen DELIVER-entry contract (empty-body section satisfies "
            f"presence, WD-5 analogue) must emit an EMPTY diagnostic — got "
            f"{diagnostic!r}. {self._diag()}"
        )

    def then_feature_delta_unchanged(self) -> None:
        """Pure-function contract: the gate mutates no file (Mandate 8 / DA-2)."""
        from tests.common.state_delta import assert_state_delta, unchanged

        assert self._universe_before is not None, (
            "the gate must have run (capturing the before-universe) before the "
            "read-only contract can be asserted."
        )
        assert_state_delta(
            before=self._universe_before,
            after=self.capture_universe(),
            universe={"feature_delta.exists", "feature_delta.bytes"},
            expected={
                "feature_delta.exists": unchanged(),
                "feature_delta.bytes": unchanged(),
            },
        )

    # --- driving-port invocation --------------------------------------------

    def _drive_gate(self, repo_root: Path) -> _FreezeCheckObservable:
        """Run the REAL ``des verify-deliver-entry-contract`` EDGE in-process (A1)."""
        _exit_code, stdout, stderr = run_cli_in_process(
            [
                _DELIVER_ENTRY_SUBCOMMAND,
                "--feature-id",
                self._feature_id,
                "--repo-root",
                str(repo_root),
                "--format=json",
            ],
            cwd=repo_root,
        )
        raw = f"{stdout}\n{stderr}"
        verdict, diagnostic = self._parse_envelope(stdout)
        return _FreezeCheckObservable(verdict=verdict, diagnostic=diagnostic, raw=raw)

    @staticmethod
    def _parse_envelope(stdout: str) -> tuple[str | None, str | None]:
        """Pull ``verdict`` + ``diagnostic`` out of the §17 JSON envelope (A1/A2)."""
        for line in reversed(stdout.splitlines()):
            stripped = line.strip()
            if not (stripped.startswith("{") and stripped.endswith("}")):
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and "verdict" in payload:
                verdict = payload.get("verdict")
                diagnostic = payload.get("diagnostic")
                return (
                    str(verdict) if verdict is not None else None,
                    str(diagnostic) if diagnostic is not None else None,
                )
        return None, None

    # --- real temp-repo fixtures --------------------------------------------

    def _write_repo(self, tmp_path: Path) -> Path:
        """Materialise a real temp repo carrying the armed completeness shape."""
        assert self._shape is not None, (
            "a direction-(b) scenario must arm a MandatoryDeltaShape before the "
            "gate runs."
        )
        feature_dir = tmp_path / "docs" / "feature" / self._feature_id
        feature_dir.mkdir(parents=True, exist_ok=True)
        self._delta_path = feature_dir / "feature-delta.md"
        self._delta_path.write_text(self._render_contract(), encoding="utf-8")
        # Both shapes carry a planned slice-01 row -> author a backing .feature so
        # the gate's slice<->AT binding check is satisfied (the OMITS_ONE_LOCKED
        # shape fails on the section check first, so the module is harmless there).
        at_dir = tmp_path / "tests" / "x"
        at_dir.mkdir(parents=True, exist_ok=True)
        (at_dir / "witness.feature").write_text(
            self._render_at_module(), encoding="utf-8"
        )
        seed_dev_checkout_marker(tmp_path)
        return tmp_path

    def _render_contract(self) -> str:
        """Render the DELIVER-entry contract for the armed completeness shape.

        A single typed lookup over the module-level dispatch (Mandate-12 criterion
        3: data, not branching logic in the service method).
        """
        return _COMPLETENESS_CONTRACT_BY_SHAPE[self._shape]  # type: ignore[index]

    def _render_at_module(self) -> str:
        """A .feature AT module backing slice-01 (the slice<->AT binding)."""
        return (
            f"@feature-{self._feature_id}\n"
            "Feature: witness\n"
            "  @slice-01\n"
            "  Scenario: y\n"
            "    Given a\n"
            "    When b\n"
            "    Then c\n"
        )

    # --- universe (Mandate 8) ------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for assert_state_delta (Mandate 8)."""
        path = self._delta_path
        return {
            "feature_delta.exists": path.exists() if path is not None else False,
            "feature_delta.bytes": (
                path.read_bytes() if path is not None and path.exists() else None
            ),
        }

    # --- internal observable accessors --------------------------------------

    def _observed_verdict(self) -> FreezeVerdict | None:
        """Map the gate output onto the §17 verdict. Off-contract token raises."""
        from .domain_types_slice_02 import FREEZE_VERDICT_TOKEN

        obs = self._require_observable()
        if obs.verdict is None:
            return None
        if obs.verdict not in FREEZE_VERDICT_TOKEN:
            raise ValueError(
                f"the DELIVER-entry gate emitted an off-§17 verdict token "
                f"{obs.verdict!r}; expected one of {sorted(FREEZE_VERDICT_TOKEN)}. "
                f"{self._diag()}"
            )
        return FREEZE_VERDICT_TOKEN[obs.verdict]

    def _require_observable(self) -> _FreezeCheckObservable:
        assert self._observable is not None, (
            "the direction-(b) completeness gate driving port was never invoked — a "
            "When step must run the gate before a Then reads its verdict."
        )
        return self._observable

    def _diag(self) -> str:
        obs = self._observable
        if obs is None:
            return "[no freeze observable captured]"
        return (
            f"[verdict={obs.verdict!r} diagnostic={obs.diagnostic!r}] "
            f"raw={obs.raw.strip()[:280]!r}"
        )


# Module-level dispatch (DELIVER-entry contract composition per completeness shape).
# Data, not branching logic in the service method (Mandate-12 criterion 3). Both
# carry a valid 5-column Slice Plan + (for ONE_SECTION_EMPTY) every locked-section
# heading; OMITS_ONE_LOCKED drops the `ADR Refs` heading entirely.
#
# OMITS_ONE_LOCKED: every locked section EXCEPT `ADR Refs` -> FAIL naming `ADR Refs`
# (the walking skeleton). ONE_SECTION_EMPTY: every locked-section heading PRESENT,
# `Architecture & Contract Tests` body left empty -> presence satisfied -> PASS.
_COMPLETENESS_CONTRACT_BY_SHAPE: dict[MandatoryDeltaShape, str] = {
    MandatoryDeltaShape.OMITS_ONE_LOCKED: (
        f"# Feature Delta: {_FEATURE_ID}\n\n"
        "## Wave: DESIGN / [REF] Architecture & Contract Tests\n\nbody.\n\n"
        "## Reuse Analysis\n\n"
        "| Existing Component | File | Overlap | Decision | Justification |\n"
        "|---|---|---|---|---|\n"
        "| x | y | z | EXTEND | j |\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
        "| slice-01 | x | pending | | j |\n"
    ),
    MandatoryDeltaShape.ONE_SECTION_EMPTY: (
        f"# Feature Delta: {_FEATURE_ID}\n\n"
        # `Architecture & Contract Tests` heading PRESENT, body empty (A3).
        "## Wave: DESIGN / [REF] Architecture & Contract Tests\n\n"
        "## Wave: DESIGN / [REF] ADR Refs\n\nbody.\n\n"
        "## Reuse Analysis\n\n"
        "| Existing Component | File | Overlap | Decision | Justification |\n"
        "|---|---|---|---|---|\n"
        "| x | y | z | EXTEND | j |\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
        "| slice-01 | x | pending | | j |\n"
    ),
}


# =============================================================================
# Byte-stable DELIVER-entry migration: regression-witness — verify-deliver-entry port
# =============================================================================


@dataclass
class _FreezeObservable:
    """What the DELIVER-entry freeze gate emitted for one invocation."""

    verdict: str | None
    diagnostic: str | None
    raw: str


@dataclass
class DeliverEntryByteStableComposition:
    """Drives the DELIVER-entry contract-freeze gate through its real port (A4)."""

    _shape: DeliverEntryShape | None = field(default=None)
    _feature_id: str = field(default=_FEATURE_ID)
    _observable: _FreezeObservable | None = field(default=None)

    # --- Given ---------------------------------------------------------------

    def given_contract_shape(self, shape: DeliverEntryShape) -> None:
        """Arm whether the presented DELIVER-entry contract is complete / deficient."""
        self._shape = shape

    # --- When ----------------------------------------------------------------

    def when_the_freeze_gate_runs_at_deliver_entry(self, tmp_path: Path) -> None:
        """Write a real temp repo for the armed shape, then run the REAL gate (A4)."""
        repo_root = self._write_repo(tmp_path)
        self._observable = self._drive_gate(repo_root)

    # --- Then ----------------------------------------------------------------

    def then_verdict_is(self, expected: FreezeVerdict) -> None:
        """The gate returned EXACTLY the expected §17 verdict (the byte-stable map)."""
        observed = self._observed_verdict()
        assert observed == expected, (
            f"the DELIVER-entry contract-freeze gate must emit {expected.value!r} "
            f"for a {self._shape.value if self._shape else '?'} contract — the "
            f"registry migration MUST keep this verdict byte-stable. Got "
            f"{observed.value if observed else observed!r}. {self._diag()}"
        )

    def then_refusal_names_the_four_locked_sections(self) -> None:
        """The FAIL diagnostic NAMES the four locked sections (the byte-stable oracle).

        This is the un-gameable byte-stability assertion (A4): a naive swap to the
        1-entry deliver.yaml output_contract would shrink the named set to
        ``Slice Plan`` only and this would red. The migration is byte-stable iff
        all four legacy locked sections are still named.
        """
        diagnostic = self._require_observable().diagnostic
        assert diagnostic is not None, (
            "a missing-locked-section refusal must carry a diagnostic naming the "
            f"locked sections. {self._diag()}"
        )
        missing = [s for s in DELIVER_ENTRY_LOCKED_SECTIONS if s not in diagnostic]
        assert not missing, (
            f"the DELIVER-entry missing-section refusal must NAME all four locked "
            f"sections {list(DELIVER_ENTRY_LOCKED_SECTIONS)!r} (byte-stable through "
            f"the registry migration) — these were absent from the diagnostic: "
            f"{missing!r}. A swap to the 1-entry deliver.yaml output_contract would "
            f"shrink the named set and trip this witness. {self._diag()}"
        )

    def then_contract_unfrozen(self) -> None:
        """A refused contract is NOT frozen (no PASS leaked through the FAIL)."""
        assert self._observed_verdict() == FreezeVerdict.FAIL, (
            f"a refused DELIVER-entry contract must carry the FAIL verdict (never a "
            f"leaked PASS that would freeze a deficient contract). {self._diag()}"
        )

    def then_no_diagnostic(self) -> None:
        """A frozen (PASS) contract emits an empty diagnostic (byte-stable PASS)."""
        diagnostic = self._require_observable().diagnostic
        assert diagnostic == "", (
            f"a frozen DELIVER-entry contract must emit an EMPTY diagnostic "
            f"(byte-stable PASS) — got {diagnostic!r}. {self._diag()}"
        )

    # --- driving-port invocation --------------------------------------------

    def _drive_gate(self, repo_root: Path) -> _FreezeObservable:
        """Run the REAL ``des verify-deliver-entry-contract`` EDGE in-process (A4)."""
        _exit_code, stdout, stderr = run_cli_in_process(
            [
                _DELIVER_ENTRY_SUBCOMMAND,
                "--feature-id",
                self._feature_id,
                "--repo-root",
                str(repo_root),
                "--format=json",
            ],
            cwd=repo_root,
        )
        raw = f"{stdout}\n{stderr}"
        verdict, diagnostic = self._parse_envelope(stdout)
        return _FreezeObservable(verdict=verdict, diagnostic=diagnostic, raw=raw)

    @staticmethod
    def _parse_envelope(stdout: str) -> tuple[str | None, str | None]:
        """Pull ``verdict`` + ``diagnostic`` out of the §17 JSON envelope (A4)."""
        for line in reversed(stdout.splitlines()):
            stripped = line.strip()
            if not (stripped.startswith("{") and stripped.endswith("}")):
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and "verdict" in payload:
                verdict = payload.get("verdict")
                diagnostic = payload.get("diagnostic")
                return (
                    str(verdict) if verdict is not None else None,
                    str(diagnostic) if diagnostic is not None else None,
                )
        return None, None

    # --- real temp-repo fixtures --------------------------------------------

    def _write_repo(self, tmp_path: Path) -> Path:
        """Materialise a real temp repo carrying the armed DELIVER-entry contract."""
        assert self._shape is not None, (
            "a DELIVER-entry witness scenario must arm a DeliverEntryShape before "
            "the gate runs."
        )
        feature_dir = tmp_path / "docs" / "feature" / self._feature_id
        feature_dir.mkdir(parents=True, exist_ok=True)
        (feature_dir / "feature-delta.md").write_text(
            self._render_contract(), encoding="utf-8"
        )
        # The COMPLETE shape needs a .feature AT module backing the planned slice
        # (the gate's slice<->AT binding check). Author one for both shapes; the
        # MISSING_LOCKED_SECTION shape fails on the section check BEFORE the
        # AT-module check is reached, so the AT module is harmless there.
        at_dir = tmp_path / "tests" / "x"
        at_dir.mkdir(parents=True, exist_ok=True)
        (at_dir / "witness.feature").write_text(
            self._render_at_module(), encoding="utf-8"
        )
        seed_dev_checkout_marker(tmp_path)
        return tmp_path

    def _render_contract(self) -> str:
        """Render the DELIVER-entry feature-delta for the armed shape.

        COMPLETE carries all four locked sections + a valid 5-column slice plan;
        MISSING_LOCKED_SECTION drops the first three locked sections (keeping a
        valid slice plan so the gate fails on the SECTION check, naming the four
        locked sections — the byte-stable behaviour under witness).
        """
        return _DELIVER_CONTRACT_BY_SHAPE[self._shape]  # type: ignore[index]

    def _render_at_module(self) -> str:
        """A .feature AT module backing slice-01 (the slice<->AT binding, A4)."""
        return (
            f"@feature-{self._feature_id}\n"
            "Feature: witness\n"
            "  @slice-01\n"
            "  Scenario: y\n"
            "    Given a\n"
            "    When b\n"
            "    Then c\n"
        )

    # --- internal observable accessors --------------------------------------

    def _observed_verdict(self) -> FreezeVerdict | None:
        from .domain_types_slice_02 import FREEZE_VERDICT_TOKEN

        obs = self._require_observable()
        if obs.verdict is None:
            return None
        if obs.verdict not in FREEZE_VERDICT_TOKEN:
            raise ValueError(
                f"the DELIVER-entry gate emitted an off-§17 verdict token "
                f"{obs.verdict!r}; expected one of {sorted(FREEZE_VERDICT_TOKEN)}. "
                f"{self._diag()}"
            )
        return FREEZE_VERDICT_TOKEN[obs.verdict]

    def _require_observable(self) -> _FreezeObservable:
        assert self._observable is not None, (
            "the DELIVER-entry freeze gate was never invoked — a When step must run "
            "the gate before a Then reads its verdict."
        )
        return self._observable

    def _diag(self) -> str:
        obs = self._observable
        if obs is None:
            return "[no freeze observable captured]"
        return (
            f"[verdict={obs.verdict!r} diagnostic={obs.diagnostic!r}] "
            f"raw={obs.raw.strip()[:280]!r}"
        )


# A complete DELIVER-entry feature-delta: all four locked sections + a valid
# 5-column slice plan (the byte-stable PASS happy path).
_DELIVER_COMPLETE_CONTRACT = (
    f"# Feature Delta: {_FEATURE_ID}\n\n"
    "## Wave: DESIGN / [REF] Architecture & Contract Tests\n\nbody.\n\n"
    "## Wave: DESIGN / [REF] ADR Refs\n\nbody.\n\n"
    "## Reuse Analysis\n\n"
    "| Existing Component | File | Overlap | Decision | Justification |\n"
    "|---|---|---|---|---|\n"
    "| x | y | z | EXTEND | j |\n\n"
    "## Wave: DISCUSS / [REF] Slice Plan\n\n"
    "| Slice | Value statement | Status | Annotation | Justification |\n"
    "|-------|-----------------|--------|------------|---------------|\n"
    "| slice-01 | x | pending | | j |\n"
)

# A DELIVER-entry feature-delta MISSING the first three locked sections (keeps a
# valid slice plan so the gate fails on the section check -> names the four locked
# sections — the byte-stable refusal under witness).
_DELIVER_MISSING_SECTION_CONTRACT = (
    f"# Feature Delta: {_FEATURE_ID}\n\n"
    "## Wave: DISCUSS / [REF] Slice Plan\n\n"
    "| Slice | Value statement | Status | Annotation | Justification |\n"
    "|-------|-----------------|--------|------------|---------------|\n"
    "| slice-01 | x | pending | | j |\n"
)

_DELIVER_CONTRACT_BY_SHAPE: dict[DeliverEntryShape, str] = {
    DeliverEntryShape.COMPLETE: _DELIVER_COMPLETE_CONTRACT,
    DeliverEntryShape.MISSING_LOCKED_SECTION: _DELIVER_MISSING_SECTION_CONTRACT,
}
