"""Composition root for fix-wave-dispatch-marker-contract slice-01 ATs.

The *only* place the production system is wired for slice-01. ONE driving port,
composition-root (Mandate-13 driving-port-only, Layer 3 composition): the REAL
``PreToolUseService.validate`` built via the production composition root
(``service_factory.create_pre_tool_use_service``). The service is the SUT; the
arranged precondition state is (a) a wave-active floor under ``project_root``
(slice-04 anchor, already shipped) armed for the wave under test, and -- only
for the ``discuss`` fall-through path -- (b) a satisfied product SSOT shape under
``docs/product/`` so the DISCUSS gate-IN (``:122-129``) PASSES and falls through
to the ``:146`` veto under test. The assertion is on the service's
``HookDecision`` (allow vs block + the ``WAVE_MARKER_BYPASS`` reason).

State lives on the instance; every ``given_/when_/then_`` method mutates or reads
it. Step functions are thin delegations (Mandate-12: no business logic in step
bodies).

DRIVING PORT (Mandate-13): Layer 3 composition. ``wave_entering`` is the
structural discriminant the production hook adapter computes from the armed
pending floor; here it is fed directly to ``PreToolUseInput`` (the slice-07
precedent), so the SUT is the real service decision function over
``(PreToolUseInput, parsed markers, reader state)``.

RED-for-right-reason (pre-DELIVER fail-for-right-reason gate): the slice-01 fix
-- teaching the ``:146`` veto to EXEMPT ``input_data.wave_entering is True`` --
does NOT exist at HEAD. So the production service still keys the veto on
``markers.wave is not None and not markers.has_des_markers`` alone:
  * AT-1a / AT-1b: a DES-WAVE-only ENTERING dispatch (``wave_entering=True``)
    arms its wave, yields ``has_des_markers=False`` (``DES-WAVE`` is excluded
    from ``_DES_MARKER_KEY``), so the veto FIRES -> the service BLOCKS
    ``WAVE_MARKER_BYPASS`` where an ALLOW is expected -> semantic
    ``AssertionError``.
  * AT-1c: a genuinely markerless NON-entering child (``wave_entering=False``)
    is the bypass the veto must STILL DENY -- the service BLOCKS it today and
    must keep blocking it post-fix. PRESERVATION-GREEN at HEAD; it is the
    deletion-mutation guard (R-A2): a mutation gutting the ``wave_entering``
    exemption turns AT-1a/1b RED while AT-1c stays GREEN.
No collection / import error in the test process (only test-local types +
already-shipped production composition are imported). GREEN once DELIVER ships
the ``wave_entering`` exemption at the ``:146`` hinge.

DESIGN-PINNED CONTRACTS this AT-seed conforms to (feature-delta § slice-01):
  * wave-active floor: single JSON object at the FIXED path
    ``{project_root}/.nwave/wave-active/active.json`` (slice-04 floor contract).
  * product SSOT (discuss fall-through only): ``docs/product/{vision,backlog,
    glossary}.md`` + ``docs/product/jobs.yaml`` presence under ``project_root``.
  * the entering dispatch's marker shape: ``<!-- DES-WAVE: <wave> -->`` ALONE
    (no `_DES_MARKER_KEY` token) -- the exact shape the command templates ship.

SUT STATE MACHINE (C2 -- AT module docstring requirement):
  states = {WAVE_ENTERING(DES_WAVE_ONLY), MARKERLESS_CHILD(non-entering)}.
    WAVE_ENTERING(DES_WAVE_ONLY) --(wave_entering=True)--> allow (entry exempt
                                   from the markerless-in-wave veto; §22.7.A)
    MARKERLESS_CHILD             --(wave_entering=False)-> VETO (block,
                                   WAVE_MARKER_BYPASS -- S2 preserved)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types_slice_marker_contract import (
    GateDecision,
    WaveUnderTest,
)


# tests/des/acceptance/nwave_flow_v2_enforcement/steps/composition_slice_marker_contract_01.py
#   parents[5] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[5]

# DESIGN-PINNED floor path (slice-04 contract): a single JSON object at this
# FIXED relative path under project_root (one record per project).
_FLOOR_FILE_REL = ".nwave/wave-active/active.json"

# DESIGN-PINNED product-SSOT layout (§8 gate-IN precondition) -- only seeded for
# the discuss fall-through path so the gate-IN PASSES to the :146 veto.
# The four SSOT docs the production ProductSsotFilesystemReader._REQUIRED_DOCS
# demands (vision/backlog/glossary as .md AND the structured jobs.yaml registry).
# Seeding all four makes the DISCUSS gate-IN (:122-129) PASS so it falls through
# to the :146 veto under test -- the discuss fall-through path AT-1b exercises
# end-to-end.
_PRODUCT_DIR_REL = "docs/product"
_SSOT_DOCS: tuple[str, ...] = ("vision.md", "backlog.md", "glossary.md", "jobs.yaml")

# The veto reason the S2 bypass DENY must carry (K1: a veto is named-LOUD, never
# a silent or generic block). A genuine bypass block names WAVE_MARKER_BYPASS.
_BYPASS_TOKEN = "wave_marker_bypass"


@dataclass
class MarkerContractRelaxComposition:
    """Drives the production :146 veto hinge for the slice-01 relax ATs."""

    _project_root: Path | None = field(default=None)
    _wave: WaveUnderTest | None = field(default=None)
    _decision_action: str | None = field(default=None)
    _decision_reason: str | None = field(default=None)

    # ---- given --------------------------------------------------------------

    def given_wave_active_entering(self, tmp_path: Path, wave: WaveUnderTest) -> None:
        """Arm the given wave as ENTERING and satisfy its entry preconditions.

        The floor carries the v1.1 anchor-owned ``entry_pending: true`` mark (an
        entering dispatch). For ``discuss`` the product SSOT is also seeded so the
        DISCUSS gate-IN (``:122-129``) PASSES and falls through to the ``:146``
        veto -- the locus AT-1b exercises end-to-end (feature-delta §Code-Design
        "DISCUSS gate-IN fall-through").
        """
        self._project_root = tmp_path
        self._wave = wave
        self._arm_floor(tmp_path, wave, entry_pending=True)
        if wave is WaveUnderTest.DISCUSS:
            self._seed_product_ssot(tmp_path)

    def given_markerless_child_in_wave(
        self, tmp_path: Path, wave: WaveUnderTest
    ) -> None:
        """Arm the given wave and arrange a PARTIAL-context NON-entering child.

        CLASS-1 RE-EXPRESS (design-sanctioned, ADR-001 Amendment 2 -- fix-wave-
        marker-bypass-benign-passthrough). The R-A2 deletion-mutation guard's INTENT
        (a non-entering in-wave child that should still be DENIED loud) is preserved,
        but the TRIGGER is re-expressed from FULLY-MARKERLESS to PARTIAL-context: the
        K2 contract now ALLOWs a fully-markerless child (floor-in-the-tree is NOT
        in-the-wave), so a markerless trigger would no longer BLOCK. A partial-context
        child (a DES-* subset, NO DES-VALIDATION, ``wave_entering=False``) is a
        positively-identified bypass that STILL DENIES loud
        (``carries_partial_wave_context=True``) -- the mutation-guard role survives;
        only the trigger marker-shape changes. See ADR-001 Amendment 2 retarget
        table (entry C2).

        The floor is armed WITHOUT ``entry_pending`` (a later in-wave dispatch, not
        the entry); the dispatch checked later carries PARTIAL wave context
        (``has_des_markers=True``, no DES-VALIDATION) and is NOT entering
        (``wave_entering=False``) -- the exact bypass the S2 veto must DENY loud.
        """
        self._project_root = tmp_path
        self._wave = wave
        self._arm_floor(tmp_path, wave, entry_pending=False)

    # ---- when ---------------------------------------------------------------

    def when_des_wave_only_entering_dispatch_checked(self) -> None:
        """Drive PreToolUseService.validate with a DES-WAVE-only ENTERING dispatch.

        ``wave_entering=True`` is the structural discriminant the production hook
        adapter computes from the armed pending floor; the prompt carries
        ``<!-- DES-WAVE: <wave> -->`` ALONE (the shipped template shape).
        """
        assert self._wave is not None
        self._run_pre_tool_use_gate(
            prompt=self._des_wave_only_prompt(self._wave), wave_entering=True
        )

    def when_markerless_child_dispatch_checked(self) -> None:
        """Drive PreToolUseService.validate with a markerless NON-entering child."""
        self._run_pre_tool_use_gate(
            prompt=self._markerless_child_prompt(), wave_entering=False
        )

    # ---- then ---------------------------------------------------------------

    def then_entry_recognized_and_allowed(self) -> None:
        """The DES-WAVE-only entering dispatch is RECOGNIZED and ALLOWED (§22.7.A).

        The veto is RELAXED for a legitimate wave entry: PASS = no objection
        found (§22.0), not a GO. RED-for-right-reason at HEAD: the ``:146`` veto
        keys on ``has_des_markers`` alone (DES-WAVE excluded from
        ``_DES_MARKER_KEY``), so it FIRES and the service BLOCKS
        ``WAVE_MARKER_BYPASS`` -- this ALLOW assertion fires now and goes GREEN
        once the ``wave_entering`` exemption lands.
        """
        assert self._gate_decision() is GateDecision.ALLOW, (
            "a wave-ENTERING dispatch carrying only '<!-- DES-WAVE: <wave> -->' "
            "(the exact shape every command template ships) must be RECOGNIZED "
            "as a legitimate entry and ALLOWED (§22.7.A) -- not blocked as a "
            "markerless bypass; the gate returned "
            f"{self._decision_action!r}. exempting input_data.wave_entering at "
            f"the :146 veto would allow it. {self._observed()}"
        )

    def then_no_bypass_block(self) -> None:
        """The decision carries no WAVE_MARKER_BYPASS veto / recovery state (AT-3b).

        Asserts the relaxed entry path is clean: an ALLOW with no spurious block
        reason. (slice-03 AT-3b: no recovery leakage onto the allow path.)
        """
        reason = (self._decision_reason or "").lower()
        assert _BYPASS_TOKEN not in reason, (
            "the recognized wave-entry must NOT carry a WAVE_MARKER_BYPASS veto "
            f"reason; got reason={self._decision_reason!r}. {self._observed()}"
        )
        assert self._decision_reason in (None, ""), (
            "an ALLOWED wave-entry must be left untouched (no block / recovery "
            f"state leaking onto the allow path); got reason="
            f"{self._decision_reason!r}. {self._observed()}"
        )

    def then_bypass_denied_loud(self) -> None:
        """The S2 veto STILL bites: a PARTIAL-context child is BLOCKED, named-LOUD (R-A2).

        CLASS-1 RE-EXPRESS (ADR-001 Amendment 2): preservation of the R-A2
        deletion-mutation guard, with the trigger re-expressed from markerless to
        partial-context (a markerless child now ALLOWs under the K2 contract; a
        partial-context child still DENIES). The mutation-guard role survives: a
        deletion-mutation of the ``wave_entering`` exemption must turn AT-1a/1b RED
        while THIS stays GREEN.
        """
        assert self._gate_decision() is GateDecision.BLOCK, (
            "a PARTIAL-context NON-entering in-wave child "
            "(wave_entering=False, DES-* subset, no DES-VALIDATION) is a "
            "positively-identified wave bypass and MUST be DENIED loud (S2 "
            "preserved, §22.0); the gate returned "
            f"{self._decision_action!r}. {self._observed()}"
        )
        reason = (self._decision_reason or "").lower()
        assert _BYPASS_TOKEN in reason, (
            "the bypass DENY must NAME WAVE_MARKER_BYPASS so the veto is loud and "
            f"attributable (K1), not a generic block; got reason="
            f"{self._decision_reason!r}. {self._observed()}"
        )

    # ---- driving-port invocation --------------------------------------------

    def _run_pre_tool_use_gate(self, prompt: str, wave_entering: bool) -> None:
        """Drive the REAL PreToolUseService.validate via the production root."""
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

    # ---- observable-surface reader ------------------------------------------

    def _gate_decision(self) -> GateDecision:
        assert self._decision_action is not None, (
            "the dispatch must be checked (When) before asserting (Then)"
        )
        return (
            GateDecision.ALLOW
            if self._decision_action == GateDecision.ALLOW.value
            else GateDecision.BLOCK
        )

    # ---- substrate plumbing (precondition state, NOT the SUT) ---------------

    def _arm_floor(
        self, root: Path, wave: WaveUnderTest, *, entry_pending: bool
    ) -> None:
        """Seed the wave-active floor with a COMMAND record for the given wave."""
        import json

        floor_path = root / _FLOOR_FILE_REL
        floor_path.parent.mkdir(parents=True, exist_ok=True)
        record: dict[str, object] = {"wave": wave.value, "provenance": "command"}
        if entry_pending:
            record["entry_pending"] = True
        floor_path.write_text(json.dumps(record), encoding="utf-8")

    def _seed_product_ssot(self, root: Path) -> None:
        """Seed a satisfied product SSOT so the discuss gate-IN PASSES (fall-through).

        Writes the four docs the production ProductSsotFilesystemReader demands
        (``_REQUIRED_DOCS`` = vision/backlog/glossary as ``.md`` AND the
        structured ``jobs.yaml`` registry) so the gate-IN finds no missing SSOT
        and falls through to the :146 veto -- the path AT-1b exercises. (This
        satisfies the REAL reader's contract; the jobs-format question is owned
        by the flow-v2-enforcement feature, not this fix.)
        """
        product_dir = root / _PRODUCT_DIR_REL
        product_dir.mkdir(parents=True, exist_ok=True)
        for doc in _SSOT_DOCS:
            (product_dir / doc).write_text(f"# {doc}\n", encoding="utf-8")

    # ---- dispatch shapes ----------------------------------------------------

    @staticmethod
    def _des_wave_only_prompt(wave: WaveUnderTest) -> str:
        """The DES-WAVE-only ENTERING dispatch shape every command template ships.

        ``<!-- DES-WAVE: <wave> -->`` ALONE -- no `_DES_MARKER_KEY` token
        (DES-VALIDATION / PROJECT-ID / PROJECT-ROOT / STEP-ID), so
        ``has_des_markers=False`` and ``is_des_task=False``. This is the production
        shape the original slice-07d fixture never exercised (Root Cause B).
        """
        return f"<!-- DES-WAVE: {wave.value} -->\nbegin the {wave.value} wave"

    @staticmethod
    def _markerless_child_prompt() -> str:
        """A PARTIAL-context in-wave child (CLASS-1 RE-EXPRESS, ADR-001 Amendment 2).

        Re-expressed from fully-markerless to a DES-* subset (PROJECT-ID + STEP-ID,
        ``has_des_markers=True``) carrying NO DES-VALIDATION in either form -- a
        positively-identified wave bypass that STILL DENIES loud under the K2
        contract. (A fully-markerless prompt now ALLOWs; only the trigger marker
        shape changed, the BLOCK contract is preserved.)
        """
        return (
            "DES-PROJECT-ID: nwave-flow-v2-enforcement\n"
            "DES-STEP-ID: design-1\n"
            "please tidy the helper module for readability"
        )

    # ---- diagnostics --------------------------------------------------------

    def _observed(self) -> str:
        return (
            f"decision=({self._decision_action!r}, {self._decision_reason!r}); "
            f"wave={self._wave!r}; project_root={self._project_root!r}"
        )
