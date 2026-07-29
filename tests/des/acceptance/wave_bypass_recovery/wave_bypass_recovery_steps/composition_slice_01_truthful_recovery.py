"""Composition root for fix-wave-bypass-recovery-truthful slice-01 ATs (JOB-019).

ONE driving surface, Mandate-13 driving-port-only (Layer 3 composition): the REAL
spine service built via the production composition root
(``service_factory.create_pre_tool_use_service``). The service is the SUT; the
observable extended here is ``HookDecision.recovery_suggestions`` (alongside
action + reason) on a WAVE_MARKER_BYPASS block. No production module is
imported-and-called at the step boundary for its business logic -- only the
production composition factory is used to BUILD the SUT, exactly as the shipped
fix-actionable-veto-recovery reference does.

INTENT (slice-01, OB-A=A2): the WAVE_MARKER_BYPASS veto's recovery list must be
TRUTHFUL and FOLLOWABLE-to-unblock. Today the second item is untruthful -- it
tells the LLM "ensure <!-- DES-WAVE: <wave> --> is present so it is recognized as
wave-entering", but DES-WAVE is excluded from ``_DES_MARKER_KEY`` (so
``has_des_markers`` stays False) AND ``wave_entering`` is floor-state never set by
the prompt -- so following it loops (add DES-WAVE -> still denied).

ARMED PRECONDITION (the empirically-hit case): a STALE, days-old
``{"wave":"distill","provenance":"inferred"}`` floor with no entry pending +
a markerless sub-dispatch + ``wave_entering=False`` -> the REAL service takes the
WAVE_MARKER_BYPASS branch (``markers.wave is not None and not
markers.has_des_markers and not input_data.wave_entering``).

ORACLE (tightened per the DESIGN SHAPE invariants, NOT a loose "names a fix"):
  * deny preserved (guardrail) -- the veto STILL returns action=block with its
    reason byte-identical (the fix is hint-text only; never weaken the veto).
  * item 1 followable -- the recovery contains a LITERAL marker from
    ``_DES_MARKER_KEY`` AND *simulating following it* (a prompt carrying that
    marker) re-run through the REAL marker parser yields ``has_des_markers=True``,
    which clears the veto condition.
  * item 2 followable -- the recovery contains the literal sanctioned clear
    command ``des wave-clear`` AND *simulating following it* (clearing the floor)
    yields ``markers.wave is None`` on the next REAL read, so WAVE_MARKER_BYPASS
    no longer fires.
  * NO phantom item -- no recovery item instructs the LLM to make the dispatch
    wave-entering via the prompt (the verified-impossible A3-class action).

Active-RED scaffold (atdd_pure -- NOT @skip): at HEAD the recovery list's second
item is the untruthful DES-WAVE-only item and there is NO ``des wave-clear`` hint,
so the followable-item-2 and no-phantom assertions fire a semantic
``AssertionError``, never a collection / import / setup error. GREEN once DELIVER
replaces the second item with the A2 stale-floor clear hint naming
``des wave-clear``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types_wave_bypass_recovery import (
    DES_MARKER_KEYS,
    PHANTOM_WAVE_ENTERING_PHRASE,
    SANCTIONED_CLEAR_COMMAND,
    GateDecision,
)


# DESIGN-PINNED floor path (slice-04 contract): a single JSON object at this FIXED
# relative path under project_root.
_FLOOR_FILE_REL = ".nwave/wave-active/active.json"

# The stale wave the empirically-hit floor carried (a days-old inferred distill
# floor the LLM is not even in).
_STALE_WAVE = "distill"

# A PARTIAL-context sub-dispatch (CLASS-1 RE-EXPRESS, design-sanctioned, ADR-001
# Amendment 2 -- fix-wave-marker-bypass-benign-passthrough). Carries a DES-* subset
# (PROJECT-ID + STEP-ID, so ``has_des_markers`` is True) but NEITHER DES-VALIDATION
# form -> ``carries_partial_wave_context`` is True -> with a wave armed +
# wave_entering False this is exactly the WAVE_MARKER_BYPASS branch.
#
# Why re-expressed: the K2 contract (slice-01 of fix-wave-marker-bypass-benign-
# passthrough) now ALLOWs a FULLY-markerless dispatch (floor-in-the-tree is NOT
# in-the-wave), so the original markerless trigger would no longer take the
# WAVE_MARKER_BYPASS branch and the truthful-recovery oracle would have no veto to
# inspect. A partial-context dispatch STILL fires the veto, so the JOB-019
# truthful/followable recovery oracle below is preserved VERBATIM (deny-preserved,
# item-1 followable, item-2 `des wave-clear`, no-phantom). See ADR-001 Amendment 2
# retarget table (entry C4).
_MARKERLESS_PROMPT = (
    "DES-PROJECT-ID: nwave-flow-v2-enforcement\n"
    "DES-STEP-ID: design-1\n"
    "please tidy the helper for readability"
)


@dataclass
class TruthfulRecoveryComposition:
    """Drives the WAVE_MARKER_BYPASS veto through the REAL PreToolUseService."""

    _project_root: Path | None = field(default=None)
    _decision_action: str | None = field(default=None)
    _decision_reason: str | None = field(default=None)
    _decision_recovery: list[str] | None = field(default=None)
    _decision_warning: str | None = field(default=None)

    # ---- given --------------------------------------------------------------

    def given_stale_inferred_floor(self, tmp_path: Path) -> None:
        """Arm a stale, days-old ``inferred`` wave floor the LLM is not in.

        ``entry_pending`` omitted (<=> False) so ``wave_entering`` is False and the
        markerless dispatch hits WAVE_MARKER_BYPASS rather than a wave-entry exempt.
        """
        self._project_root = tmp_path
        self._write_floor(
            tmp_path,
            json.dumps({"wave": _STALE_WAVE, "provenance": "inferred"}),
        )

    def given_stale_declared_floor(self, tmp_path: Path) -> None:
        """Arm a stale, days-old DECLARED (``command``) wave floor (slice-01's
        precondition since 2026-07-29): an INFERRED floor no longer vetoes
        (measured + Ale-authorized widening), so the truthful/followable
        recovery oracle now needs a floor that STILL blocks -- a DECLARED
        floor never expires (armed_at stays None, I5) and is never diverted
        by provenance, so it keeps vetoing exactly as slice-01 requires.
        """
        self._project_root = tmp_path
        self._write_floor(
            tmp_path,
            json.dumps({"wave": _STALE_WAVE, "provenance": "command"}),
        )

    # ---- when ---------------------------------------------------------------

    def when_markerless_dispatch_vetoed(self) -> None:
        """Drive the REAL PreToolUseService.validate; capture the block surface."""
        self._run_pre_tool_use_gate(_MARKERLESS_PROMPT, wave_entering=False)

    # ---- then ---------------------------------------------------------------

    def then_wave_marker_bypass_still_blocks(self) -> None:
        """(guardrail) deny preserved: the WAVE_MARKER_BYPASS veto STILL blocks."""
        assert self._gate_decision() is GateDecision.BLOCK, (
            "WAVE_MARKER_BYPASS must still BLOCK a markerless in-wave dispatch "
            "(deny preserved -- repairing the recovery hint must not weaken the "
            f"veto); the gate returned {self._decision_action!r}. {self._observed()}"
        )

    def then_block_reason_names_wave_marker_bypass(self) -> None:
        """(guardrail) the reason still names the WAVE_MARKER_BYPASS error-code.

        The DESIGN SHAPE holds the reason byte-identical; this asserts the
        observable reason still carries the discriminating WAVE_MARKER_BYPASS
        prefix (the fix is hint-text only, never a reason change).
        """
        reason = self._decision_reason or ""
        assert reason.startswith("WAVE_MARKER_BYPASS:"), (
            "the block reason must still name WAVE_MARKER_BYPASS (held "
            f"byte-identical by the additive fix); got reason={reason!r}. "
            f"{self._observed()}"
        )

    def then_first_recovery_item_carries_real_markers(self) -> None:
        """item 1 followable: names a real _DES_MARKER_KEY marker AND following it works.

        Conjunction (literal reference AND has_des_markers=True on a prompt that
        follows it) -- not mere substring presence.
        """
        recovery = self._decision_recovery or []
        joined = " ".join(recovery)
        named = [key for key in DES_MARKER_KEYS if key in joined]
        assert named, (
            "the recovery must name a real marker from _DES_MARKER_KEY "
            f"({DES_MARKER_KEYS!r}) so copying it sets has_des_markers=True; the "
            f"recovery names none. got recovery={recovery!r}. {self._observed()}"
        )
        # Simulate FOLLOWING item 1: a prompt carrying a named marker must, through
        # the REAL marker parser, yield has_des_markers=True (clears the veto cond).
        assert self._following_named_marker_sets_has_des_markers(named[0]), (
            f"following the recovery (a prompt carrying {named[0]!r}) must yield "
            "has_des_markers=True through the REAL marker parser so the veto "
            "condition (not markers.has_des_markers) no longer fires; it did not. "
            f"{self._observed()}"
        )

    def then_second_recovery_item_names_sanctioned_clear(self) -> None:
        """item 2 followable: names ``des wave-clear`` AND clearing yields no wave.

        RED-for-right-reason at HEAD: the second recovery item is the untruthful
        DES-WAVE-only item -- it does NOT name ``des wave-clear`` -- so this fires
        now and goes GREEN once DELIVER lands the A2 stale-floor clear hint.
        """
        recovery = self._decision_recovery or []
        joined = " ".join(recovery)
        assert SANCTIONED_CLEAR_COMMAND in joined, (
            "the recovery must name the sanctioned stale-floor clear command "
            f"{SANCTIONED_CLEAR_COMMAND!r} (the OB-A=A2 followable-to-unblock item "
            "for a stale floor the LLM is not in) instead of the untruthful "
            f"DES-WAVE-only loop item; the recovery names none. got "
            f"recovery={recovery!r}. {self._observed()}"
        )
        # Simulate FOLLOWING item 2: clearing the floor must yield markers.wave is
        # None on the next REAL read, so WAVE_MARKER_BYPASS no longer fires.
        assert self._following_clear_yields_no_active_wave(), (
            "following the recovery (clearing the floor) must yield "
            "markers.wave is None on the next read so WAVE_MARKER_BYPASS "
            f"(markers.wave is not None ...) no longer fires. {self._observed()}"
        )

    def then_reason_names_floor_absolute_path(self) -> None:
        """slice-03: the ALLOW+warning names the floor file's absolute PATH.

        Reads ``decision.warning``, not ``decision.reason``: since the
        2026-07-29 widening an INFERRED floor no longer blocks, it ALLOWS
        with an advisory warning that carries the same
        ``_describe_wave_floor`` text this scenario checks -- the
        self-locating property moved surfaces, it did not disappear.
        """
        assert self._project_root is not None
        warning = self._decision_warning or ""
        floor_path = str(self._project_root / _FLOOR_FILE_REL)
        assert floor_path in warning, (
            "the advisory warning must name the floor file's absolute path "
            f"{floor_path!r} (the gate already re-read it to decide); got "
            f"warning={warning!r}. {self._observed()}"
        )

    def then_reason_names_resolved_project_root(self) -> None:
        """slice-03: the ALLOW+warning names the RESOLVED project root.

        Reads ``decision.warning`` (see ``then_reason_names_floor_absolute_
        path`` for why): a reader must be able to tell which of several
        worktree/trunk roots the floor lives in without searching.
        """
        assert self._project_root is not None
        warning = self._decision_warning or ""
        assert str(self._project_root) in warning, (
            "the advisory warning must name the resolved project root "
            f"{str(self._project_root)!r} the floor was armed under; got "
            f"warning={warning!r}. {self._observed()}"
        )

    def then_reason_names_the_inferred_signal(self) -> None:
        """slice-03: the ALLOW+warning names WHAT the INFERRED floor was deduced from.

        Reads ``decision.warning``: the concrete deduction (a wave-declaring
        dispatch landing on an empty floor, the only writer of INFERRED --
        ``arm_inferred``) must be named, not the bare word 'inferred' alone.
        """
        warning = self._decision_warning or ""
        assert "INFERRED" in warning, (
            f"the advisory warning must mention the floor is INFERRED at all; "
            f"got warning={warning!r}. {self._observed()}"
        )
        assert "DES-WAVE" in warning and "empty floor" in warning, (
            "an INFERRED floor's description must name the CONCRETE signal it "
            "was deduced from (a <!-- DES-WAVE: <wave> --> declaration landing "
            "on an empty floor -- the only writer of INFERRED provenance), not "
            f"just the bare word 'INFERRED'; got warning={warning!r}. "
            f"{self._observed()}"
        )

    def then_no_recovery_item_proposes_phantom_wave_entry(self) -> None:
        """no phantom: no item instructs making the dispatch wave-entering via prompt.

        RED-for-right-reason at HEAD: the second item proposes exactly this
        verified-impossible action (add DES-WAVE so it is "recognized as a
        legitimate wave-entering dispatch") -- so this fires now. GREEN once the
        phantom item is removed/replaced.
        """
        recovery = self._decision_recovery or []
        offenders = [
            item for item in recovery if PHANTOM_WAVE_ENTERING_PHRASE in item.lower()
        ]
        assert not offenders, (
            "no recovery item may instruct the LLM to make this dispatch "
            f"{PHANTOM_WAVE_ENTERING_PHRASE!r} via the prompt -- wave_entering is "
            "floor-state (entry_pending), never prompt-settable, so such an item "
            f"is untruthful (the A3-class loop defect). offending items: "
            f"{offenders!r}. {self._observed()}"
        )

    # ---- driving-port invocation --------------------------------------------

    def _run_pre_tool_use_gate(self, prompt: str, *, wave_entering: bool) -> None:
        """Drive the REAL PreToolUseService.validate via the production composition root."""
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
                PreToolUseInput(prompt=prompt, wave_entering=wave_entering)
            )
        finally:
            os.chdir(prev_cwd)
            if prev_env is None:
                os.environ.pop("DES_PROJECT_DIR", None)
            else:
                os.environ["DES_PROJECT_DIR"] = prev_env
        self._record(decision)

    # ---- follow-the-recovery simulators (still through REAL surfaces) --------

    def _following_named_marker_sets_has_des_markers(self, marker_key: str) -> bool:
        """Re-run the REAL marker parser on a prompt carrying ``marker_key``.

        Drives the production marker-parse driving port indirectly through the
        REAL service: a prompt that follows item 1 (carries the marker) must take
        the gate OFF the WAVE_MARKER_BYPASS branch. We assert via the observable
        decision -- with a marker present the markerless-bypass veto no longer
        fires (its reason no longer starts WAVE_MARKER_BYPASS).
        """
        assert self._project_root is not None
        from des.adapters.drivers.hooks import service_factory
        from des.ports.driver_ports.pre_tool_use_port import PreToolUseInput

        followed_prompt = (
            f"<!-- {marker_key} : required -->\n"
            "do the in-wave work (now carrying the wave's marker)"
        )
        prev_cwd = Path.cwd()
        prev_env = os.environ.get("DES_PROJECT_DIR")
        try:
            os.chdir(self._project_root)
            # Mirror the armed root into DES_PROJECT_DIR (see
            # _run_pre_tool_use_gate above for the rationale).
            os.environ["DES_PROJECT_DIR"] = str(self._project_root)
            service = service_factory.create_pre_tool_use_service()
            decision = service.validate(
                PreToolUseInput(prompt=followed_prompt, wave_entering=False)
            )
        finally:
            os.chdir(prev_cwd)
            if prev_env is None:
                os.environ.pop("DES_PROJECT_DIR", None)
            else:
                os.environ["DES_PROJECT_DIR"] = prev_env
        # The observable proof that following item 1 worked: the markerless-bypass
        # veto is no longer the decision -- its reason no longer leads with the
        # WAVE_MARKER_BYPASS error-code (the dispatch now carries a real marker).
        reason = decision.reason or ""  # type: ignore[attr-defined]
        return not reason.startswith("WAVE_MARKER_BYPASS:")

    def _following_clear_yields_no_active_wave(self) -> bool:
        """Clear the floor, then re-drive the markerless dispatch through the REAL service.

        Proof that following item 2 (run ``des wave-clear``) unblocks: removing the
        floor record -> the next REAL read sees no active wave (markers.wave None)
        -> WAVE_MARKER_BYPASS no longer fires for the same markerless dispatch.
        We simulate the clear by removing the floor file (what the sanctioned
        command does via WaveActiveWriter.clear), then observe the REAL decision.
        """
        assert self._project_root is not None
        floor_path = self._project_root / _FLOOR_FILE_REL
        floor_path.unlink(missing_ok=True)

        from des.adapters.drivers.hooks import service_factory
        from des.ports.driver_ports.pre_tool_use_port import PreToolUseInput

        prev_cwd = Path.cwd()
        prev_env = os.environ.get("DES_PROJECT_DIR")
        try:
            os.chdir(self._project_root)
            # Mirror the armed root into DES_PROJECT_DIR (see
            # _run_pre_tool_use_gate above for the rationale).
            os.environ["DES_PROJECT_DIR"] = str(self._project_root)
            service = service_factory.create_pre_tool_use_service()
            decision = service.validate(
                PreToolUseInput(prompt=_MARKERLESS_PROMPT, wave_entering=False)
            )
        finally:
            os.chdir(prev_cwd)
            if prev_env is None:
                os.environ.pop("DES_PROJECT_DIR", None)
            else:
                os.environ["DES_PROJECT_DIR"] = prev_env
        reason = decision.reason or ""  # type: ignore[attr-defined]
        return not reason.startswith("WAVE_MARKER_BYPASS:")

    # ---- observable-surface reader ------------------------------------------

    def _record(self, decision: object) -> None:
        self._decision_action = decision.action  # type: ignore[attr-defined]
        self._decision_reason = decision.reason  # type: ignore[attr-defined]
        self._decision_recovery = list(decision.recovery_suggestions)  # type: ignore[attr-defined]
        self._decision_warning = decision.warning  # type: ignore[attr-defined]

    def _gate_decision(self) -> GateDecision:
        assert self._decision_action is not None, (
            "the dispatch must be vetoed (When) before asserting (Then)"
        )
        return (
            GateDecision.ALLOW
            if self._decision_action == GateDecision.ALLOW.value
            else GateDecision.BLOCK
        )

    # ---- substrate plumbing -------------------------------------------------

    def _write_floor(self, root: Path, content: str) -> None:
        floor_path = root / _FLOOR_FILE_REL
        floor_path.parent.mkdir(parents=True, exist_ok=True)
        floor_path.write_text(content, encoding="utf-8")

    # ---- diagnostics --------------------------------------------------------

    def _observed(self) -> str:
        return (
            f"decision=({self._decision_action!r}, {self._decision_reason!r}, "
            f"recovery={self._decision_recovery!r}); "
            f"project_root={self._project_root!r}"
        )
