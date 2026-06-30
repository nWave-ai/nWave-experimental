"""Composition root for the fix-wave-marker-bypass-benign-passthrough slice-01 ATs.

The *only* place the production system is wired for slice-01. ONE driving port
(Mandate-13 driving-port-only, Layer 3 composition):

  * THE CORRECTED GUARD -- the REAL ``PreToolUseService.validate(PreToolUseInput)``
    built via the production composition root
    (``service_factory.create_pre_tool_use_service``, Pillar 3). The service is
    the SUT; only the wave-active floor (precondition state, a driven-internal
    filesystem port) is arranged. The assertion is on the service's
    ``HookDecision`` (allow vs block) -- the exact observable a Claude Code hook
    translates to exit 0 / exit 2.

FLOOR ISOLATION (Fix-2, the defect this whole feature exists to fix). Every
scenario injects its floor state EXPLICITLY into a clean ``tmp_path`` root and
drives the service under ``os.chdir(tmp_path)``, so the production
``WaveActiveReader`` (which resolves the floor off ``Path.cwd()``) reads the
INJECTED floor -- never the developer's live ``.nwave/wave-active/active.json``.
A markerless prompt under an ARMED ``design`` floor therefore asserts the hook's
INTRINSIC decision for a CONTROLLED floor, independent of the working tree. The
slice-04 ``WaveActiveAnchorComposition`` is the precedent for this exact
seed-floor + chdir-service drive; this composition reuses it.

DESIGN-PINNED FLOOR CONTRACT (slice-04 SSOT, reused): a single JSON object at the
FIXED path ``{project_root}/.nwave/wave-active/active.json`` with required
``wave`` (closed vocab) + ``provenance`` (``command``|``inferred``). Absent file
<=> NoWaveActive (the S1 floor). The AT-seed SEEDS the floor as precondition
state; the production reader CONSUMES it. The path/shape are not the crafter's
choice -- they are DESIGN-PINNED.

State lives on the instance; every ``given_/when_/then_`` method mutates or reads
it. Step functions are thin delegations (Mandate-12: no business logic, no
control flow in step bodies).

RED-for-right-reason (pre-DELIVER fail-for-right-reason gate). At HEAD the S2
guard keys on the OLD floor-presence predicate
(``markers.wave is not None and not markers.has_des_markers and not
wave_entering``), so:
  * AT-1 (benign FULLY-MARKERLESS under an armed floor) -- the old guard BLOCKS
    (markerless under a floor) where the corrected guard must ALLOW -> the Then
    asserts ALLOW, the service returns block -> semantic ``AssertionError``.
  * AT-2 (PARTIAL-MARKERS bypass) -- ``has_des_markers`` is True, so
    ``not has_des_markers`` is False -> the old guard does NOT block where the
    corrected guard must BLOCK -> the Then asserts BLOCK, the service returns
    allow -> semantic ``AssertionError``.
  * AT-3 (DES-WAVE-only) -- preservation-GREEN at HEAD via the OLD path
    (``has_des_markers`` is False because ``_DES_MARKER_KEY`` excludes DES-WAVE,
    so the old guard blocks) AND must STAY BLOCK under the corrected guard (via
    ``declared_wave`` counting as partial context) -- the regression guard that
    the DES-WAVE collision stays closed end-to-end.
  * AT-4 (no floor, markerless) + AT-5 (wave_entering) -- preservation-GREEN at
    HEAD; pin S1 + the entering exemption are not regressed by the re-point.
Only test-local types + already-shipped production composition are imported, so
the suite COLLECTS cleanly and each RED is a semantic ``AssertionError``, never a
collection / import / setup error.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types import DispatchShape, FloorState, GateDecision


# DESIGN-PINNED floor path (slice-04 contract, reused as the one SSOT).
_FLOOR_FILE_REL = ".nwave/wave-active/active.json"

# Tokens a loud BLOCK reason must carry so a generic block cannot satisfy the
# bypass-named assertion (K1: a real bypass is LOUD, not a silent green).
_BYPASS_TOKENS: tuple[str, ...] = ("wave", "bypass", "marker")

# --- DES-marker prompt fixtures keyed by DispatchShape (precondition content) --
# The benign 9-reds prompt: a real markerless prompt that carries ZERO DES
# markers and no DES-WAVE -- the exact K2 contract ("builds 10-12 failed in CI").
_PROMPT_FULLY_MARKERLESS = "builds 10-12 failed in CI -- look into it"

# PARTIAL wave context: carries a DES marker subset (PROJECT-ID + STEP-ID, so
# has_des_markers is True) but MISSES DES-VALIDATION -- a positively-identified
# wave-owned child that dropped the required marker.
_PROMPT_PARTIAL_MARKERS = (
    "DES-PROJECT-ID: fix-wave-marker-bypass-benign-passthrough\n"
    "DES-STEP-ID: design-1\n"
    "proceed with the in-wave work"
)

# DES-WAVE-only: carries ONLY the wave declaration (has_des_markers is False
# because _DES_MARKER_KEY excludes DES-WAVE) but no DES-VALIDATION -- the
# collision case the corrected predicate must still count as partial context.
_PROMPT_DES_WAVE_ONLY = "<!-- DES-WAVE: design -->\nproceed with the in-wave work"


def _prompt_for(shape: DispatchShape) -> str:
    """The pinned prompt content for a dispatch shape (precondition, not logic)."""
    return {
        DispatchShape.FULLY_MARKERLESS: _PROMPT_FULLY_MARKERLESS,
        DispatchShape.PARTIAL_MARKERS: _PROMPT_PARTIAL_MARKERS,
        DispatchShape.DES_WAVE_ONLY: _PROMPT_DES_WAVE_ONLY,
    }[shape]


@dataclass
class GuardComposition:
    """Drives the corrected S2 guard via the production composition root."""

    _project_root: Path | None = field(default=None)
    _floor_state: FloorState | None = field(default=None)
    _wave_entering: bool = field(default=False)
    _decision_action: str | None = field(default=None)
    _decision_reason: str | None = field(default=None)

    # ---- given (floor isolation -- Fix-2) -----------------------------------

    def given_floor(self, tmp_path: Path, floor_state: FloorState) -> None:
        """Inject the floor state into a CLEAN isolated root (Fix-2).

        ``tmp_path`` is the isolated wave-active root: the floor is seeded here
        (or left absent), and the service is later driven under
        ``os.chdir(tmp_path)`` so the production reader resolves THIS floor, not
        the developer's live working-tree floor.
        """
        self._project_root = tmp_path
        self._floor_state = floor_state
        if floor_state is FloorState.DESIGN_ARMED:
            self._seed_floor(tmp_path, wave="design", provenance="command")
        # NO_FLOOR: write nothing -> NoWaveActive (the S1 floor).

    def given_wave_entering(self) -> None:
        """Mark this dispatch as the wave-ENTERING dispatch (AT-5 exemption)."""
        self._wave_entering = True

    # ---- when (the driving port) --------------------------------------------

    def when_dispatch_checked(self, shape: DispatchShape) -> None:
        """Drive the REAL PreToolUseService.validate with the shaped dispatch."""
        self._run_guard(_prompt_for(shape))

    # ---- then (observable: the HookDecision) --------------------------------

    def then_allowed(self) -> None:
        """The corrected guard ALLOWS the dispatch (exit 0 -- K2 passthrough)."""
        assert self._gate_decision() is GateDecision.ALLOW, (
            "the dispatch must be ALLOWED (benign passthrough / S1 / entering "
            "exemption -- floor-in-the-tree is NOT in-the-wave); the guard "
            f"returned {self._decision_action!r}. {self._observed()}"
        )

    def then_left_untouched(self) -> None:
        """K2 non-interference: an allowed benign dispatch carries no block reason."""
        assert self._decision_reason in (None, ""), (
            "a benign markerless dispatch must be left completely untouched (no "
            f"block reason); got reason={self._decision_reason!r}. "
            f"{self._observed()}"
        )

    def then_blocked(self) -> None:
        """The corrected guard BLOCKS the dispatch (exit 2 -- K1 bypass loud)."""
        assert self._gate_decision() is GateDecision.BLOCK, (
            "a positively-identified bypass (partial wave context missing "
            "DES-VALIDATION, under an active floor, not entering) must be BLOCKED "
            f"loud (K1 / no-silent-pass); the guard returned "
            f"{self._decision_action!r}. {self._observed()}"
        )

    def then_block_names_bypass(self) -> None:
        """The BLOCK reason names the wave-bypass so it cannot pass as success."""
        reason = (self._decision_reason or "").lower()
        assert any(token in reason for token in _BYPASS_TOKENS), (
            "the block must NAME the wave-bypass (one of "
            f"{_BYPASS_TOKENS!r}) so it surfaces as a loud, attributable failure, "
            f"not a silent success; got reason={self._decision_reason!r}. "
            f"{self._observed()}"
        )

    # ---- AT-6 purity property (driving-port invariance) ---------------------

    def decide_under_floor(self, tmp_path: Path, floor_wave: str, prompt: str) -> str:
        """Drive the guard once under an armed floor of the given wave; return action.

        AT-6 witness helper: re-arming a SEPARATE isolated root with a DIFFERENT
        floor wave and re-driving the same prompt lets the property assert that
        the corrected guard's decision is INVARIANT across floor identity --
        i.e. the discriminant (carries_partial_wave_context) reads ONLY the
        prompt, never the floor's wave value. Pure precondition-arrange + one
        driving-port call; no business logic.
        """
        self._project_root = tmp_path
        self._floor_state = FloorState.DESIGN_ARMED
        self._wave_entering = False
        self._seed_floor(tmp_path, wave=floor_wave, provenance="command")
        self._run_guard(prompt)
        assert self._decision_action is not None
        return self._decision_action

    def reason_under_floor(self, tmp_path: Path, floor_wave: str, prompt: str) -> str:
        """Drive once under an armed floor; return the decision reason (or "").

        AT-6 is_des_task witness: a complete DES-VALIDATION dispatch may still be
        blocked downstream (template/completeness), but it must NEVER be blocked
        by the S2 WAVE_MARKER_BYPASS branch -- so the property asserts on the
        ABSENCE of the bypass reason, not on a bare allow.
        """
        self.decide_under_floor(tmp_path, floor_wave=floor_wave, prompt=prompt)
        return self._decision_reason or ""

    # ---- driving-port invocation (Layer 3 composition) ----------------------

    def _run_guard(self, prompt: str) -> None:
        """Drive the REAL PreToolUseService.validate via the production root.

        The service is built by the production factory (Pillar 3). The service
        is driven under ``os.chdir(project_root)`` so the production
        WaveActiveReader resolves the INJECTED floor (Fix-2 isolation). The
        wave_entering flag is threaded as the adapter would compute it.
        """
        assert self._project_root is not None
        from des.adapters.drivers.hooks import service_factory
        from des.ports.driver_ports.pre_tool_use_port import PreToolUseInput

        prev_cwd = Path.cwd()
        try:
            os.chdir(self._project_root)
            service = service_factory.create_pre_tool_use_service()
            decision = service.validate(
                PreToolUseInput(prompt=prompt, wave_entering=self._wave_entering)
            )
        finally:
            os.chdir(prev_cwd)
        self._decision_action = decision.action
        self._decision_reason = decision.reason

    # ---- observable-surface readers -----------------------------------------

    def _gate_decision(self) -> GateDecision:
        assert self._decision_action is not None, (
            "the dispatch must be checked (When) before asserting (Then)"
        )
        return (
            GateDecision.ALLOW
            if self._decision_action == "allow"
            else GateDecision.BLOCK
        )

    # ---- substrate plumbing (precondition state, NOT the SUT) ---------------

    def _seed_floor(self, root: Path, wave: str, provenance: str) -> None:
        """Seed the pinned floor record (precondition state, NOT the SUT)."""
        floor_path = root / _FLOOR_FILE_REL
        floor_path.parent.mkdir(parents=True, exist_ok=True)
        floor_path.write_text(
            json.dumps({"wave": wave, "provenance": provenance}),
            encoding="utf-8",
        )

    # ---- diagnostics --------------------------------------------------------

    def _observed(self) -> str:
        return (
            f"decision.action={self._decision_action!r}; "
            f"decision.reason={self._decision_reason!r}; "
            f"floor_state={self._floor_state!r}; "
            f"wave_entering={self._wave_entering!r}; "
            f"project_root={self._project_root!r}"
        )

    # ---- state-machine doc (C2 -- AT module docstring requirement) ----------
    # SUT state machine (the corrected S2 guard), under an active floor:
    #   ARMED + FULLY_MARKERLESS          -> ALLOW (K2 benign passthrough)
    #   ARMED + PARTIAL_MARKERS (no -VAL) -> BLOCK (K1 bypass loud)
    #   ARMED + DES_WAVE_ONLY (no -VAL)   -> BLOCK (collision closed)
    #   ARMED + wave_entering             -> ALLOW (entering exemption)
    #   NO_FLOOR + any                    -> ALLOW (S1 ad-hoc path)
