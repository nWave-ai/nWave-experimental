"""Composition root for fix-actionable-veto-recovery slice-01 ATs.

ONE driving surface, Mandate-13 driving-port-only (Layer 3 composition): the REAL
spine services built via the production composition root
(``service_factory.create_pre_tool_use_service`` /
``service_factory.create_subagent_stop_service``). The services are the SUT; the
observable extended here is ``HookDecision.recovery_suggestions`` (alongside
action + reason). No production module is imported-and-called at the step
boundary for its business logic -- only the production composition factories are
used to BUILD the SUT, exactly as the shipped slice-marker-contract-03 reference
does.

INTENT (JOB-019): every spine veto that today calls
``HookDecision.block(reason=...)`` WITHOUT ``recovery_suggestions`` must emit a
NON-EMPTY, actionable ``recovery_suggestions`` list naming the concrete fix.
slice-01 is the walking skeleton: ONE parametrized scenario shape over the 6
enumerated bare-veto SITES asserting each block now (a) still BLOCKS (deny
preserved), (b) carries a non-empty recovery list, (c) names a fix specific to
that veto's failure (not a generic placeholder).

The 6 SITES (driven through the REAL entry point, observing the block surface):
  1. WAVE_ACTIVE_INDETERMINATE    -- pre_tool_use_service.validate, corrupt floor
  2. CLASSIC_PROMPT_INVALID       -- pre_tool_use_service.validate, classic dispatch
                                      passing completeness but failing template schema
  3. ATDD_PURE_DISPATCH_DEFECTIVE -- pre_tool_use_service.validate, atdd_pure markers
                                      complete but (phase, scope) incoherent
  4. ATDD_PURE_PROMPT_INVALID     -- pre_tool_use_service.validate, valid atdd_pure
                                      markers but missing the atdd_pure sections
  5. DISCUSS_GATE_IN              -- pre_tool_use_service.validate, discuss-entering
                                      dispatch with product SSOT present but
                                      INCOMPLETE (MISSING_SSOT -- the still-vetoing
                                      gate-IN case after the slice-05 declass of
                                      MIGRATION_UNMET to a soft advisory)
  6. DISCUSS_GATE_OUT            -- subagent_stop_service.validate, discuss return
                                      whose feature-delta slice plan is rejected

Active-RED scaffold (atdd_pure -- NOT @skip): at HEAD every one of the 6 sites
calls ``HookDecision.block(reason=...)`` with NO ``recovery_suggestions``, so the
observable list is EMPTY where a non-empty actionable hint is expected. The
``Then`` fires a semantic ``AssertionError`` (recovery list empty for site X),
never a collection / import / setup error. GREEN once DELIVER adds a
``recovery_suggestions=`` arg to each of the 6 blocks (mirroring the shipped
:140 / :178 / :192 twins).

SUT STATE MACHINE (C2): each VetoSite arms a distinct precondition that steers
the REAL service down exactly that veto's BLOCK branch; every branch must reach
BLOCK + non-empty actionable recovery_suggestions (the self-documenting veto
surface). No site may reach ALLOW (each precondition is a genuine veto).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types_actionable_veto_recovery import GateDecision, VetoSite


# tests/des/acceptance/nwave_flow_v2_enforcement/steps/<this file>
#   parents[5] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[5]

# DESIGN-PINNED floor path (slice-04 contract): a single JSON object at this FIXED
# relative path under project_root.
_FLOOR_FILE_REL = ".nwave/wave-active/active.json"

# DESIGN-PINNED product-SSOT layout (§8 gate-IN precondition).
_PRODUCT_DIR_REL = "docs/product"

# DESIGN-PINNED feature-delta path the gate-OUT FeatureDeltaReader reads. The
# project_id below is what the SubagentStopContext carries; the gate-OUT reader
# joins it to docs/feature/{project_id}/feature-delta.md.
_GATE_OUT_FEATURE_ID = "fix-actionable-veto-recovery-gate-out-probe"
_FEATURE_DELTA_REL = f"docs/feature/{_GATE_OUT_FEATURE_ID}/feature-delta.md"

# An infra-only slice plan (every row @infrastructure) -- the discuss gate-OUT
# cohesion veto (not value-bearing), so the gate-OUT BLOCKS with a
# DISCUSS_GATE_OUT_* reason.
_INFRA_ONLY_FEATURE_DELTA = f"""\
# Feature Delta: {_GATE_OUT_FEATURE_ID}

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|---|---|---|---|---|
| slice-01 | wire the logging adapter | pending | @infrastructure | plumbing only |
| slice-02 | configure the CI matrix | pending | @infrastructure | plumbing only |
"""

# Per-site discriminating fix-tokens an actionable recovery suggestion must name
# so the hint is SPECIFIC to that veto's failure, not a generic "fix it"
# placeholder. Lower-cased substring match against the joined recovery list.
_FIX_TOKENS_BY_SITE: dict[VetoSite, tuple[str, ...]] = {
    VetoSite.WAVE_ACTIVE_INDETERMINATE: (
        "wave-active",
        "active.json",
        "floor",
        "wave state",
    ),
    # Discriminating-only token per the §22.0 oracle-specificity finding: the
    # shared "section"/"add" tokens are dropped so a generic "add a section"
    # recovery cannot falsely satisfy BOTH prompt-invalid sites -- the classic
    # site must name "mandatory" (the 9-section classic schema), the atdd_pure
    # site must name "atdd_pure".
    VetoSite.CLASSIC_PROMPT_INVALID: ("mandatory",),
    VetoSite.ATDD_PURE_DISPATCH_DEFECTIVE: (
        "des-phase",
        "des-slice",
        "des-mode",
        "marker",
    ),
    VetoSite.ATDD_PURE_PROMPT_INVALID: ("atdd_pure",),
    VetoSite.DISCUSS_GATE_IN: (
        "ssot",
        "docs/product",
        "migration",
        "vision",
        "precondition",
    ),
    VetoSite.DISCUSS_GATE_OUT: (
        "slice plan",
        "slice-plan",
        "feature-delta",
        "review",
        "value",
    ),
}


@dataclass
class ActionableRecoveryComposition:
    """Drives each of the 6 bare-veto sites through the REAL spine services."""

    _project_root: Path | None = field(default=None)
    _site: VetoSite | None = field(default=None)
    _decision_action: str | None = field(default=None)
    _decision_reason: str | None = field(default=None)
    _decision_recovery: list[str] | None = field(default=None)

    # ---- given --------------------------------------------------------------

    def given_bare_veto_site(self, tmp_path: Path, site: VetoSite) -> None:
        """Arm the precondition state that steers the REAL service down ``site``."""
        self._project_root = tmp_path
        self._site = site
        self._arm_precondition(tmp_path, site)

    # ---- when ---------------------------------------------------------------

    def when_dispatch_checked_for_recovery(self) -> None:
        """Drive the REAL spine service for the armed site and capture the decision."""
        assert self._site is not None
        if self._site is VetoSite.DISCUSS_GATE_OUT:
            self._run_subagent_stop_gate()
        else:
            self._run_pre_tool_use_gate(*self._pre_tool_use_dispatch(self._site))

    # ---- then ---------------------------------------------------------------

    def then_veto_still_blocks(self) -> None:
        """(a) deny preserved: the veto STILL blocks (it is a genuine veto)."""
        assert self._gate_decision() is GateDecision.BLOCK, (
            f"{self._site}: the veto must still BLOCK (deny preserved -- adding a "
            "recovery hint must not weaken the veto); the gate returned "
            f"{self._decision_action!r}. {self._observed()}"
        )

    def then_block_carries_non_empty_recovery(self) -> None:
        """(b) the block carries a non-empty recovery_suggestions list.

        RED-for-right-reason at HEAD: the site calls ``HookDecision.block(reason=)``
        with NO recovery_suggestions, so the observed list is EMPTY -- this
        assertion fires now and goes GREEN once DELIVER adds the recovery arg.
        """
        recovery = self._decision_recovery or []
        assert recovery, (
            f"{self._site}: the bare veto must now carry a NON-EMPTY "
            "recovery_suggestions list naming the concrete fix (mirroring the "
            "shipped enforcement / completeness / WAVE_MARKER_BYPASS twins) so the "
            "veto surface is self-documenting (JOB-019); the recovery list is "
            f"empty. got recovery={self._decision_recovery!r}. {self._observed()}"
        )

    def then_recovery_names_specific_fix(self) -> None:
        """(c) the suggestion text is SPECIFIC to this veto, not a placeholder."""
        recovery = self._decision_recovery or []
        joined = " ".join(recovery).lower()
        assert self._site is not None
        tokens = _FIX_TOKENS_BY_SITE[self._site]
        assert any(token in joined for token in tokens), (
            f"{self._site}: the recovery suggestion must NAME the fix specific to "
            f"this veto (one of {tokens!r}) -- a generic placeholder is not "
            f"actionable; got recovery={self._decision_recovery!r}. {self._observed()}"
        )

    # ---- driving-port invocations -------------------------------------------

    def _run_pre_tool_use_gate(self, prompt: str, wave_entering: bool) -> None:
        """Drive the REAL PreToolUseService.validate via the production composition root."""
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
        self._record(decision)

    def _run_subagent_stop_gate(self) -> None:
        """Drive the REAL SubagentStopService.validate via the production composition root."""
        assert self._project_root is not None
        from des.adapters.drivers.hooks import service_factory
        from des.ports.driver_ports.subagent_stop_port import SubagentStopContext

        prev_cwd = Path.cwd()
        try:
            os.chdir(self._project_root)
            service = service_factory.create_subagent_stop_service()
            decision = service.validate(
                SubagentStopContext(
                    execution_log_path="",
                    project_id=_GATE_OUT_FEATURE_ID,
                    step_id="",
                    cwd=str(self._project_root),
                    mode="atdd_pure",
                    slice_id="slice-01",
                    atdd_pure_phase="D_REFACTOR_COMMIT",
                )
            )
        finally:
            os.chdir(prev_cwd)
        self._record(decision)

    # ---- observable-surface reader ------------------------------------------

    def _record(self, decision: object) -> None:
        self._decision_action = decision.action  # type: ignore[attr-defined]
        self._decision_reason = decision.reason  # type: ignore[attr-defined]
        self._decision_recovery = list(decision.recovery_suggestions)  # type: ignore[attr-defined]

    def _gate_decision(self) -> GateDecision:
        assert self._decision_action is not None, (
            "the dispatch must be checked (When) before asserting (Then)"
        )
        return (
            GateDecision.ALLOW
            if self._decision_action == GateDecision.ALLOW.value
            else GateDecision.BLOCK
        )

    # ---- precondition arming (per-site steering) ----------------------------

    def _arm_precondition(self, root: Path, site: VetoSite) -> None:
        if site is VetoSite.WAVE_ACTIVE_INDETERMINATE:
            # A CORRUPT floor file -> WaveActiveFilesystemStore.read returns
            # Indeterminate -> :99 WAVE_ACTIVE_INDETERMINATE block.
            self._write_floor(root, "{not valid json")
        elif site is VetoSite.DISCUSS_GATE_IN:
            # A discuss wave-entering dispatch whose product SSOT is present but
            # INCOMPLETE -> the gate-IN precondition is unmet (MISSING_SSOT) ->
            # DISCUSS_GATE_IN_missing-ssot block with the named recovery.
            #
            # slice-05 declass (ADR-FLOW-002 Q4): the MIGRATION_UNMET case
            # (docs/product/ entirely absent) is NO LONGER a veto -- it is a soft
            # advisory (allow). So the still-vetoing DISCUSS gate-IN site is now
            # the MISSING_SSOT case: docs/product/ EXISTS (migration met) but a
            # required SSOT doc (jobs.yaml) is absent -> the gate hard-vetoes with
            # the named recovery. This keeps DISCUSS_GATE_IN a genuine veto site
            # so its recovery-hint contract is exercised; only the arming
            # condition moves off the declassed case.
            self._write_floor(
                root,
                json.dumps(
                    {"wave": "discuss", "provenance": "command", "entry_pending": True}
                ),
            )
            product_dir = root / _PRODUCT_DIR_REL
            product_dir.mkdir(parents=True, exist_ok=True)
            for doc in ("vision.md", "backlog.md", "glossary.md"):
                (product_dir / doc).write_text(f"# {doc}\n", encoding="utf-8")
            # jobs.yaml deliberately absent -> MISSING_SSOT (still a hard veto).
        elif site is VetoSite.DISCUSS_GATE_OUT:
            # A discuss wave with an infra-only feature-delta slice plan -> the
            # gate-OUT cohesion veto -> :334 DISCUSS_GATE_OUT_* block.
            self._write_floor(
                root, json.dumps({"wave": "discuss", "provenance": "command"})
            )
            self._write_feature_delta(root, _INFRA_ONLY_FEATURE_DELTA)
        # CLASSIC_PROMPT_INVALID / ATDD_PURE_* sites need no floor (no wave
        # active -> the wave-aware hinge does not interfere); the dispatch shape
        # alone steers the service down the validation/classification veto.

    def _pre_tool_use_dispatch(self, site: VetoSite) -> tuple[str, bool]:
        """The (prompt, wave_entering) that steers the REAL service down ``site``."""
        if site is VetoSite.WAVE_ACTIVE_INDETERMINATE:
            # Any dispatch reaches the :96 Indeterminate guard before any branch.
            return ("please tidy the helper for readability", False)
        if site is VetoSite.CLASSIC_PROMPT_INVALID:
            # A classic DES dispatch: passes completeness (project-id + step-id),
            # NOT atdd_pure (classification absent), but missing the 9 mandatory
            # template sections -> :222 classic prompt-validator block.
            return (
                "<!-- DES-VALIDATION : required -->\n"
                "<!-- DES-PROJECT-ID : probe-classic -->\n"
                "<!-- DES-STEP-ID : step-1 -->\n"
                "do the work (no mandatory sections present)",
                False,
            )
        if site is VetoSite.ATDD_PURE_DISPATCH_DEFECTIVE:
            # atdd_pure markers complete for completeness (project-id + phase +
            # slice) but an INCOHERENT (phase, scope) pair -- G_COMMIT is
            # per-slice yet the scope is feature-end -> classify=defective ->
            # :240 ATDD_PURE_DISPATCH_DEFECTIVE block.
            return (
                "<!-- DES-VALIDATION : required -->\n"
                "<!-- DES-MODE : atdd_pure -->\n"
                "<!-- DES-PROJECT-ID : probe-atdd -->\n"
                "<!-- DES-PHASE : G_COMMIT -->\n"
                "<!-- DES-SLICE : feature-end -->\n"
                "do the work",
                False,
            )
        if site is VetoSite.ATDD_PURE_PROMPT_INVALID:
            # VALID coherent atdd_pure markers (A_GREEN_ATS is per-slice, slice-01
            # is a per-slice scope -> classify=valid) but the prompt is missing
            # the atdd_pure mandatory sections -> :253 atdd_pure prompt block.
            return (
                "<!-- DES-VALIDATION : required -->\n"
                "<!-- DES-MODE : atdd_pure -->\n"
                "<!-- DES-PROJECT-ID : probe-atdd -->\n"
                "<!-- DES-PHASE : A_GREEN_ATS -->\n"
                "<!-- DES-SLICE : slice-01 -->\n"
                "do the work (no atdd_pure sections present)",
                False,
            )
        if site is VetoSite.DISCUSS_GATE_IN:
            # A discuss wave-entering dispatch; the floor armed entry_pending so
            # the gate-IN precondition runs and vetoes on absent product SSOT.
            return (
                "<!-- DES-VALIDATION : required -->\n"
                "<!-- DES-PROJECT-ID : probe-discuss -->\n"
                "<!-- DES-STEP-ID : discuss-1 -->\n"
                "begin the discuss wave",
                True,
            )
        raise AssertionError(f"no pre-tool-use dispatch for {site!r}")

    # ---- substrate plumbing -------------------------------------------------

    def _write_floor(self, root: Path, content: str) -> None:
        floor_path = root / _FLOOR_FILE_REL
        floor_path.parent.mkdir(parents=True, exist_ok=True)
        floor_path.write_text(content, encoding="utf-8")

    def _write_feature_delta(self, root: Path, content: str) -> None:
        delta_path = root / _FEATURE_DELTA_REL
        delta_path.parent.mkdir(parents=True, exist_ok=True)
        delta_path.write_text(content, encoding="utf-8")

    # ---- diagnostics --------------------------------------------------------

    def _observed(self) -> str:
        return (
            f"decision=({self._decision_action!r}, {self._decision_reason!r}, "
            f"recovery={self._decision_recovery!r}); site={self._site!r}; "
            f"project_root={self._project_root!r}"
        )
