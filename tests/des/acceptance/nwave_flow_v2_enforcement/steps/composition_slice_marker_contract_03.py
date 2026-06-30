"""Composition root for fix-wave-dispatch-marker-contract slice-03 ATs.

ONE driving port (Mandate-13, Layer 3 composition): the REAL
``PreToolUseService.validate`` via the production composition root. The service
is the SUT; the observable extended here is the ``HookDecision.recovery_suggestions``
list (alongside action + reason). Reuses the slice-01 real-service driving
pattern; the distinct value is the recovery-suggestions dimension.

Root Cause C: the :159 WAVE_MARKER_BYPASS block emits NO ``recovery_suggestions``,
unlike its twins at :140 (enforcement) and :173 (completeness). After slice-01
relaxes the false positive, the :159 block is reachable ONLY by a genuinely
markerless non-entering child -- THEN a fix-hint is correct (RCA R-A1
sequencing: a hint on a false-positive block would be politely wrong, so
slice-03 depends-on slice-01).

  * AT-3a -- recovery present on a genuine bypass. A genuinely markerless
    NON-entering in-wave child (wave_entering=False) is BLOCKED
    WAVE_MARKER_BYPASS and must carry a non-empty ``recovery_suggestions``
    naming the fix path (carry the wave's DES markers, OR -- if this is the entry
    -- ensure ``<!-- DES-WAVE: <wave> -->`` is present). RED-for-right-reason at
    HEAD: the :159 block passes no recovery_suggestions -> the list is EMPTY ->
    semantic AssertionError.
  * AT-3b -- no recovery leakage onto the allow path. The slice-01 ALLOW path
    (a recognized wave-entry) must carry NO recovery_suggestions and no block
    state. PRESERVATION-GREEN at HEAD on the recovery dimension; it pins that the
    recovery hint added in this slice does not bleed onto allows.

No collection / import error (test-local types + already-shipped production
composition only).

SUT STATE MACHINE (C2):
  states = {MARKERLESS_CHILD(non-entering), WAVE_ENTERING(DES_WAVE_ONLY)}.
    MARKERLESS_CHILD --(blocked)--> BLOCK + non-empty recovery_suggestions
                                    (self-documenting veto surface, Root Cause C)
    WAVE_ENTERING    --(allowed)--> ALLOW + empty recovery_suggestions (no leak)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types_slice_marker_contract import GateDecision, WaveUnderTest


# parents[5] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[5]

_FLOOR_FILE_REL = ".nwave/wave-active/active.json"
_PRODUCT_DIR_REL = "docs/product"
_SSOT_DOCS: tuple[str, ...] = ("vision.md", "backlog.md", "glossary.md", "jobs.yaml")

# Tokens an actionable recovery suggestion must name so the fix path is
# attributable, not a generic "fix it" (K1: the surface is self-documenting).
# Either route the operator to carry the wave's DES markers, OR to ensure the
# DES-WAVE entry marker is present.
_RECOVERY_FIX_TOKENS: tuple[str, ...] = (
    "des marker",
    "des-wave",
    "des markers",
    "wave's des",
)


@dataclass
class RecoveryHintComposition:
    """Drives the :159 bypass block recovery-suggestions surface (slice-03)."""

    _project_root: Path | None = field(default=None)
    _wave: WaveUnderTest | None = field(default=None)
    _decision_action: str | None = field(default=None)
    _decision_reason: str | None = field(default=None)
    _decision_recovery: list[str] | None = field(default=None)

    # ---- given --------------------------------------------------------------

    def given_markerless_child_in_wave(
        self, tmp_path: Path, wave: WaveUnderTest
    ) -> None:
        """Arm the wave (NOT entering) and arrange a PARTIAL-context child.

        CLASS-1 RE-EXPRESS (design-sanctioned, ADR-001 Amendment 2 -- fix-wave-
        marker-bypass-benign-passthrough). The recovery-message contract's INTENT
        (a denied bypass names its fix path) is preserved; only the TRIGGER is
        re-expressed from fully-markerless to PARTIAL-context. The K2 contract now
        ALLOWs a fully-markerless child (no BLOCK -> no recovery to assert), so the
        trigger must be a partial-context child (a DES-* subset, no DES-VALIDATION)
        that STILL BLOCKs -- the recovery-suggestions assertion still exercises the
        BLOCK path. See ADR-001 Amendment 2 retarget table (entry C3).
        """
        self._project_root = tmp_path
        self._wave = wave
        self._arm_floor(tmp_path, wave, entry_pending=False)

    def given_wave_entering(self, tmp_path: Path, wave: WaveUnderTest) -> None:
        """Arm the wave as ENTERING and satisfy its entry preconditions (allow path)."""
        self._project_root = tmp_path
        self._wave = wave
        self._arm_floor(tmp_path, wave, entry_pending=True)
        if wave is WaveUnderTest.DISCUSS:
            self._seed_product_ssot(tmp_path)

    # ---- when ---------------------------------------------------------------

    def when_markerless_child_dispatch_checked(self) -> None:
        """Drive the REAL service with a PARTIAL-context NON-entering child.

        CLASS-1 RE-EXPRESS (ADR-001 Amendment 2): a DES-* subset (PROJECT-ID +
        STEP-ID, ``has_des_markers=True``) carrying NO DES-VALIDATION -- a
        positively-identified bypass that STILL BLOCKs, so the recovery-suggestions
        contract is exercised on the BLOCK path (a fully-markerless child now ALLOWs).
        """
        self._run_pre_tool_use_gate(
            prompt=(
                "DES-PROJECT-ID: nwave-flow-v2-enforcement\n"
                "DES-STEP-ID: design-1\n"
                "please tidy the helper module for readability"
            ),
            wave_entering=False,
        )

    def when_des_wave_only_entering_dispatch_checked(self) -> None:
        """Drive the REAL service with a DES-WAVE-only ENTERING dispatch (allow path)."""
        assert self._wave is not None
        self._run_pre_tool_use_gate(
            prompt=f"<!-- DES-WAVE: {self._wave.value} -->\nbegin the {self._wave.value} wave",
            wave_entering=True,
        )

    # ---- then ---------------------------------------------------------------

    def then_bypass_block_names_recovery(self) -> None:
        """The genuine-bypass block carries a non-empty, actionable recovery hint.

        RED-for-right-reason at HEAD: the :159 block passes no
        recovery_suggestions, so the observable list is EMPTY -- this assertion
        fires now and goes GREEN once DELIVER mirrors the :140/:173 twins.
        """
        assert self._gate_decision() is GateDecision.BLOCK, (
            "AT-3a precondition: the genuinely markerless non-entering child must "
            f"be BLOCKED (the S2 veto); the gate returned {self._decision_action!r}. "
            f"{self._observed()}"
        )
        recovery = self._decision_recovery or []
        assert recovery, (
            "the WAVE_MARKER_BYPASS block must carry a non-empty "
            "recovery_suggestions naming the fix path (mirroring the :140 / :173 "
            "twins) so every veto surface is self-documenting (Root Cause C); the "
            f"recovery list is empty. got recovery={self._decision_recovery!r}. "
            f"{self._observed()}"
        )
        joined = " ".join(recovery).lower()
        assert any(token in joined for token in _RECOVERY_FIX_TOKENS), (
            "the recovery suggestion must NAME the fix path (carry the wave's DES "
            "markers, OR -- if this is the entry -- ensure '<!-- DES-WAVE: <wave> "
            f"-->' is present), one of {_RECOVERY_FIX_TOKENS!r}; got recovery="
            f"{self._decision_recovery!r}. {self._observed()}"
        )

    def then_allow_path_carries_no_recovery(self) -> None:
        """The recognized wave-entry ALLOW path carries no recovery / block leakage.

        PRESERVATION (no-leak): the recovery hint added to the :159 block in this
        slice must NOT bleed onto an allow. GREEN at HEAD on this dimension once
        slice-01 makes the entry an ALLOW; if slice-01 is not yet shipped the
        entry is a BLOCK and this fires RED -- correct, since AT-3b's invariant
        (no recovery on the allow path) presupposes the allow exists.
        """
        assert self._gate_decision() is GateDecision.ALLOW, (
            "AT-3b precondition: a recognized DES-WAVE-only wave-entry must be "
            f"ALLOWED (slice-01 relax); the gate returned {self._decision_action!r}. "
            f"{self._observed()}"
        )
        assert (self._decision_recovery or []) == [], (
            "an ALLOWED wave-entry must carry NO recovery_suggestions -- the "
            "Root-Cause-C recovery hint must not leak onto the allow path; got "
            f"recovery={self._decision_recovery!r}. {self._observed()}"
        )

    # ---- driving-port invocation --------------------------------------------

    def _run_pre_tool_use_gate(self, prompt: str, wave_entering: bool) -> None:
        assert self._project_root is not None
        from des.adapters.drivers.hooks import service_factory
        from des.ports.driver_ports.pre_tool_use_port import PreToolUseInput

        prev_cwd = Path.cwd()
        try:
            os.chdir(self._project_root)
            service = service_factory.create_pre_tool_use_service()
            decision = service.validate(
                PreToolUseInput(prompt=prompt, wave_entering=wave_entering)
            )
        finally:
            os.chdir(prev_cwd)
        self._decision_action = decision.action
        self._decision_reason = decision.reason
        self._decision_recovery = list(decision.recovery_suggestions)

    def _gate_decision(self) -> GateDecision:
        assert self._decision_action is not None, (
            "the dispatch must be checked (When) before asserting (Then)"
        )
        return (
            GateDecision.ALLOW
            if self._decision_action == GateDecision.ALLOW.value
            else GateDecision.BLOCK
        )

    # ---- substrate plumbing -------------------------------------------------

    def _arm_floor(
        self, root: Path, wave: WaveUnderTest, *, entry_pending: bool
    ) -> None:
        import json

        floor_path = root / _FLOOR_FILE_REL
        floor_path.parent.mkdir(parents=True, exist_ok=True)
        record: dict[str, object] = {"wave": wave.value, "provenance": "command"}
        if entry_pending:
            record["entry_pending"] = True
        floor_path.write_text(json.dumps(record), encoding="utf-8")

    def _seed_product_ssot(self, root: Path) -> None:
        product_dir = root / _PRODUCT_DIR_REL
        product_dir.mkdir(parents=True, exist_ok=True)
        for doc in _SSOT_DOCS:
            (product_dir / doc).write_text(f"# {doc}\n", encoding="utf-8")

    # ---- diagnostics --------------------------------------------------------

    def _observed(self) -> str:
        return (
            f"decision=({self._decision_action!r}, {self._decision_reason!r}, "
            f"recovery={self._decision_recovery!r}); wave={self._wave!r}; "
            f"project_root={self._project_root!r}"
        )
