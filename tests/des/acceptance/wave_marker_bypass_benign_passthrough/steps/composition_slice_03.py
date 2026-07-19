"""Composition root for the fix-wave-marker-bypass-benign-passthrough slice-03 ATs.

ADR-001 Amendment 1: the corrected guard's exclusion clause is refined from
``and not is_des_task`` (HTML-comment-only) to ``and not carries_des_validation``
(HTML-comment OR plain-line ``DES-VALIDATION: required``). slice-01 false-positive
BLOCKs a legitimate plain-line-validated dispatch; this slice locks the fix.

The *only* place the production system is wired for slice-03. ONE driving port
(Mandate-13 driving-port-only, Layer 3 composition): THE REFINED GUARD -- the REAL
``PreToolUseService.validate(PreToolUseInput)`` built via the production
composition root (``service_factory.create_pre_tool_use_service``, Pillar 3). The
service is the SUT; only the wave-active floor (precondition state, a
driven-internal filesystem port) is arranged. The OBSERVABLE is whether the S2
``WAVE_MARKER_BYPASS`` veto fires -- read off the service's ``HookDecision.reason``,
the exact surface a Claude Code hook translates to exit 2.

WHY observe the BYPASS REASON, not a bare ALLOW (AT-8). A plain-line-validated
dispatch carries ``has_des_markers`` (so it is is_des_task=False but
marker-bearing); under the refined guard it is NOT a partial-context bypass, so
the S2 branch must NOT claim it. Like the slice-01 AT-6 ``is_des_task`` witness, a
complete dispatch may still be blocked DOWNSTREAM by a different, legitimate gate
(template / completeness) -- so the ALLOW for the guard's purposes is witnessed on
the ABSENCE of the WAVE_MARKER_BYPASS reason, never on a bare allow that a
downstream block would falsify.

FLOOR ISOLATION (Fix-2): every scenario injects its floor state EXPLICITLY into a
clean ``tmp_path`` root and drives the service under ``os.chdir(tmp_path)``, so the
production ``WaveActiveReader`` resolves the INJECTED floor -- never the
developer's live ``.nwave/wave-active/active.json``. Reuses the slice-01
seed-floor + chdir-service drive (``composition_slice_01.py``).

RED-for-right-reason (pre-DELIVER fail-for-right-reason gate). At HEAD the slice-01
guard keys ``carries_partial_wave_context`` on ``and not is_des_task``:
  * AT-8 (PLAIN_LINE_DES_VALIDATION) -- is_des_task=False (HTML-comment pattern
    does not match the plain-line form) AND has_des_markers=True (the plain-line
    ``DES-VALIDATION:`` matches ``_DES_MARKER_KEY``), so
    ``carries_partial_wave_context`` is True at HEAD -> the guard BLOCKs
    WAVE_MARKER_BYPASS where the refined guard must NOT -> the not-blocked-as-bypass
    assertion fails with a semantic ``AssertionError``.
  * AT-9 (NEITHER_VALIDATION_FORM) -- ``carries_partial_wave_context`` is True under
    BOTH the slice-01 and the refined predicate (no DES-VALIDATION in either form)
    -> BLOCK at HEAD and post-fix: preservation-GREEN (K1 survives the refinement).
Only test-local types + already-shipped production composition are imported, so the
suite COLLECTS cleanly and each RED is a semantic ``AssertionError``, never a
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

# The discriminating error-code a genuine bypass DENY must carry (K1: a real
# bypass is named-LOUD). A plain-line-validated dispatch must NOT carry it.
_BYPASS_TOKEN = "wave_marker_bypass"

# Tokens a loud BLOCK reason must carry so a generic block cannot satisfy the
# bypass-named assertion (mirrors slice-01 _BYPASS_TOKENS).
_BYPASS_TOKENS: tuple[str, ...] = ("wave", "bypass", "marker")

# --- DES-marker prompt fixtures keyed by DispatchShape (precondition content) --
# PLAIN-LINE DES-VALIDATION: the required marker in the plain ``DES-KEY: value``
# line form (NOT the HTML-comment form). has_des_markers=True (matches
# _DES_MARKER_KEY ``DES-VALIDATION\s*:``) but is_des_task=False (the HTML-comment
# _VALIDATION_PATTERN does not match) -- the exact shape the slice-01 guard
# false-positive-BLOCKs and the refined ``carries_des_validation`` must recognize.
_PROMPT_PLAIN_LINE_DES_VALIDATION = (
    "DES-VALIDATION: required\n"
    "DES-PROJECT-ID: fix-wave-marker-bypass-benign-passthrough\n"
    "DES-STEP-ID: design-1\n"
    "proceed with the complete in-wave dispatch (plain-line validated)"
)

# NEITHER DES-VALIDATION form: partial markers (a DES-* subset) with NO
# HTML-comment AND no plain-line DES-VALIDATION -- a genuine wave-bypass that must
# STILL be blocked under the refined predicate (K1 preserved).
_PROMPT_NEITHER_VALIDATION_FORM = (
    "DES-PROJECT-ID: fix-wave-marker-bypass-benign-passthrough\n"
    "DES-STEP-ID: design-1\n"
    "proceed with the in-wave work (no DES-VALIDATION in either form)"
)


def _prompt_for(shape: DispatchShape) -> str:
    """The pinned prompt content for a dispatch shape (precondition, not logic)."""
    return {
        DispatchShape.PLAIN_LINE_DES_VALIDATION: _PROMPT_PLAIN_LINE_DES_VALIDATION,
        DispatchShape.NEITHER_VALIDATION_FORM: _PROMPT_NEITHER_VALIDATION_FORM,
    }[shape]


@dataclass
class MarkerFormComposition:
    """Drives the refined S2 guard (ADR-001 Amendment 1) via the production root."""

    _project_root: Path | None = field(default=None)
    _floor_state: FloorState | None = field(default=None)
    _decision_action: str | None = field(default=None)
    _decision_reason: str | None = field(default=None)

    # ---- given (floor isolation -- Fix-2) -----------------------------------

    def given_floor(self, tmp_path: Path, floor_state: FloorState) -> None:
        """Inject the floor state into a CLEAN isolated root (Fix-2)."""
        self._project_root = tmp_path
        self._floor_state = floor_state
        if floor_state is FloorState.DESIGN_ARMED:
            self._seed_floor(tmp_path, wave="design", provenance="command")

    # ---- when (the driving port) --------------------------------------------

    def when_dispatch_checked(self, shape: DispatchShape) -> None:
        """Drive the REAL PreToolUseService.validate with the shaped dispatch."""
        self._run_guard(_prompt_for(shape))

    # ---- then (observable: the WAVE_MARKER_BYPASS veto surface) -------------

    def then_not_blocked_as_bypass(self) -> None:
        """The refined guard does NOT claim this dispatch as a WAVE_MARKER_BYPASS.

        AT-8: a plain-line DES-VALIDATION dispatch carries the required marker, so
        ``carries_des_validation`` is True and ``carries_partial_wave_context`` is
        False -> the S2 bypass branch must NOT fire. Witnessed on the ABSENCE of the
        bypass reason (not a bare allow): a complete dispatch may be blocked
        downstream for a DIFFERENT legitimate reason, but the bypass branch must
        never tag it.
        """
        reason = (self._decision_reason or "").lower()
        assert _BYPASS_TOKEN not in reason, (
            "a plain-line `DES-VALIDATION: required` dispatch carries the required "
            "marker (carries_des_validation True) and must NOT be tagged a "
            "WAVE_MARKER_BYPASS (the refined exclusion uses carries_des_validation, "
            "not the HTML-comment-only is_des_task); the guard blocked it as a "
            f"bypass. got reason={self._decision_reason!r}. {self._observed()}"
        )

    def then_blocked_as_bypass(self) -> None:
        """The refined guard BLOCKS a neither-form partial dispatch (K1 preserved).

        AT-9: partial markers with NEITHER DES-VALIDATION form ->
        ``carries_des_validation`` False -> ``carries_partial_wave_context`` True ->
        BLOCK loud. Preservation-GREEN at HEAD (the slice-01 predicate already
        BLOCKs it) and post-fix.
        """
        assert self._gate_decision() is GateDecision.BLOCK, (
            "a partial-context dispatch carrying NEITHER DES-VALIDATION form is a "
            "genuine wave-bypass and must be BLOCKED loud (K1 survives the "
            f"refinement); the guard returned {self._decision_action!r}. "
            f"{self._observed()}"
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

    # ---- AT-10 either-form-equivalence property (driving-port invariance) ----

    def bypass_fires_under_floor(
        self, tmp_path: Path, floor_wave: str, prompt: str
    ) -> bool:
        """Drive the guard once under an armed floor; return whether the S2 bypass fired.

        AT-10 witness helper: re-arming a SEPARATE isolated root with a chosen floor
        wave and re-driving a prompt lets the property assert that the refined
        discriminant treats both DES-VALIDATION spellings as equivalent and reads
        ONLY the prompt (decision invariant across floor identity). Pure
        precondition-arrange + one driving-port call; no business logic.
        """
        self._project_root = tmp_path
        self._floor_state = FloorState.DESIGN_ARMED
        self._seed_floor(tmp_path, wave=floor_wave, provenance="command")
        self._run_guard(prompt)
        return _BYPASS_TOKEN in (self._decision_reason or "").lower()

    # ---- driving-port invocation (Layer 3 composition) ----------------------

    def _run_guard(self, prompt: str) -> None:
        """Drive the REAL PreToolUseService.validate via the production root.

        Driven under ``os.chdir(project_root)`` so the production WaveActiveReader
        resolves the INJECTED floor (Fix-2 isolation). ``wave_entering=False``: these
        dispatches are in-wave children, not the entering dispatch.
        """
        assert self._project_root is not None
        from des.adapters.drivers.hooks import service_factory
        from des.ports.driver_ports.pre_tool_use_port import PreToolUseInput

        prev_cwd = Path.cwd()
        prev_env = os.environ.get("DES_PROJECT_DIR")
        try:
            os.chdir(self._project_root)
            # Mirror the armed root into DES_PROJECT_DIR so `resolve_nwave_root()`
            # resolves the SAME root the floor was seeded at, not the per-test
            # isolation root the autouse `_isolate_nwave_root` fixture set.
            os.environ["DES_PROJECT_DIR"] = str(self._project_root)
            service = service_factory.create_pre_tool_use_service()
            decision = service.validate(
                PreToolUseInput(prompt=prompt, wave_entering=False)
            )
        finally:
            os.chdir(prev_cwd)
            if prev_env is None:
                os.environ.pop("DES_PROJECT_DIR", None)
            else:
                os.environ["DES_PROJECT_DIR"] = prev_env
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
            f"project_root={self._project_root!r}"
        )

    # ---- state-machine doc (C2 -- AT module docstring requirement) ----------
    # SUT state machine (the refined S2 guard, ADR-001 Amendment 1), under an
    # active floor, not entering:
    #   ARMED + PLAIN_LINE_DES_VALIDATION  -> NOT bypass (carries_des_validation)
    #   ARMED + NEITHER_VALIDATION_FORM    -> BLOCK (K1 bypass loud preserved)
