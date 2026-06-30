"""Composition root for f-declarative-gate-composition slice-01 (walking skeleton).

DRIVING SURFACES (Mandate-13 driving-port-only -- TWO real surfaces, no
direct-domain testing):

  * Layer 3 composition -- the REAL spine services built via the production
    composition root (``service_factory.create_pre_tool_use_service`` /
    ``create_subagent_stop_service``). The services are the SUT; the observable is
    the ``HookDecision`` surface (action / reason / ``recovery_suggestions``).
    Used by AT-1 (gate-IN), AT-2 (gate-OUT), AT-4 (parity), and the run-ORDER AT.
  * Layer 3 composition (pure seam through its real read path) -- the REAL
    ``flavor_dispatcher.resolve_wave_gate_stack`` reading the SHIPPED
    ``nWave/flavors/atdd_pure.yaml`` from the repo. This is the DESIGN-declared
    net-new seam (Public Surface table) that proves the veto's wiring is DATA
    (``wave_gate_stacks.discuss``), not the imperative ``if markers.wave`` branch.
  * Layer 3 subprocess -- the REAL ``des verify-discuss-review`` catalog gate
    (the OB-2-promoted PO-review consumer veto) invoked through
    ``python -m des.cli``. Drives AT-2's gate-OUT veto through its declared
    catalog ``gate_id`` (the seam that makes the gate-out stack a 2-row list).

No production module is imported-and-called at the step boundary for its business
logic -- only the production composition factories BUILD the SUT, and the REAL
pure seam ``resolve_wave_gate_stack`` is read over the SHIPPED flavor file.

DORMANT-SEAM RECONCILIATION (Mandate-15 / S3): the DESIGN driving-surface (Public
Surface table, lines 754-763) declares these net-new load-bearing seams reached
from the REAL PreToolUse/SubagentStop entry points:
  (1) ``flavor_dispatcher.resolve_wave_gate_stack`` -- NEW pure function selecting
      the active-wave stack off the wave-active anchor.
  (2) ``GateInvocationResult.recovery_suggestions`` -- NEW optional field carrying
      each gate's specific recovery (OB-2 parity).
  (3) the ``wave_gate_stacks.discuss`` flavor block -- the DATA home of the lift.
  (4) the ``verify-discuss-review`` catalog gate -- the PO-review consumer veto
      promoted to a declared gate_id (DESIGN line 763 / OB-2).
Each slice-01 AT NAMES one of these seams, drives it through a REAL entry point,
and asserts an observable effect.

ASSUMED CONCRETE gate_id for the PO-review consumer veto: ``verify-discuss-review``
(DESIGN leaves it as ``<discuss-review-veto consumer gate>`` placeholder, suggests
``verify-discuss-review`` / ``discuss-review-veto``; the ``verify-*`` catalog
convention -- verify-slice-commit / verify-integrity / verify-commit-trailers --
makes ``verify-discuss-review`` the matching name).

DELIVER-HANDOFF NOTE (F-4): ``verify-discuss-review`` is a FAITHFUL INDUCTION from
the ``verify-*`` convention + the DESIGN declared placeholder -- it is NOT a
crafter-matches-design contract the test gets to invent. The crafter MUST reconcile
this gate_id against the DESIGN Public Surface table (line 763,
``<discuss-review-veto consumer gate>``) at registration and CONFIRM the concrete
name -- the crafter does NOT inherit the test's guess. If the crafter picks a
different sanctioned name, update ``_PO_REVIEW_VETO_GATE_ID`` here to match; the
ASSERTION (the consumer veto is a registered catalog gate) is the contract, the
literal string is the late-bound detail.

Active-RED scaffold (atdd_pure -- NOT @skip): at HEAD none of the four seams
exist -- ``resolve_wave_gate_stack`` is absent (AttributeError caught -> semantic
AssertionError), ``GateInvocationResult`` has no ``recovery_suggestions`` field,
``atdd_pure.yaml`` has no ``wave_gate_stacks`` key, and ``des verify-discuss-review``
is an ``invalid choice`` (exit 2). Every Then fires a semantic ``AssertionError``
naming the missing seam -- never a collection / import / setup error. The REAL
service still vetoes via the imperative branch at HEAD (deny preserved), so the
deny-preserved assertions are GREEN-by-construction and the seam-named assertions
are the RED -- the lift makes the SAME veto flow from the DATA stack.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process

from .domain_types_declarative_gate_composition import (
    DiscussVetoSite,
    GateDecision,
    WaveBoundary,
)


# tests/des/acceptance/declarative_gate_composition/<pkg>/<this file>
#   parents[5] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[5]

# The SHIPPED flavor dir the production code reads (carpaccio_intercept._FLAVORS_DIR).
_SHIPPED_FLAVORS_DIR = REPO_ROOT / "nWave" / "flavors"

# DESIGN-PINNED floor path + product-SSOT layout (slice-04 contract / §8 gate-IN).
_FLOOR_FILE_REL = ".nwave/wave-active/active.json"

# DESIGN-PINNED feature-delta path the gate-OUT FeatureDeltaReader reads.
_GATE_OUT_FEATURE_ID = "f-declarative-gate-composition-gate-out-probe"
_FEATURE_DELTA_REL = f"docs/feature/{_GATE_OUT_FEATURE_ID}/feature-delta.md"

# An infra-only slice plan (every row @infrastructure) -> the discuss gate-OUT
# structural cohesion veto BLOCKS with a DISCUSS_GATE_OUT_* reason.
_INFRA_ONLY_FEATURE_DELTA = f"""\
# Feature Delta: {_GATE_OUT_FEATURE_ID}

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|---|---|---|---|---|
| slice-01 | wire the logging adapter | pending | @infrastructure | plumbing only |
| slice-02 | configure the CI matrix | pending | @infrastructure | plumbing only |
"""

# The DISCUSS-wave flavor the slice migrates (atdd_pure ships the discuss stack).
_ATDD_PURE = "atdd_pure"
_DISCUSS_WAVE = "discuss"

# The concrete catalog gate_id the OB-2 PO-review consumer veto is promoted to.
_PO_REVIEW_VETO_GATE_ID = "verify-discuss-review"

# Per-site discriminating reason-token the veto must carry (the SEAM, not a line).
_REASON_PREFIX_BY_SITE: dict[DiscussVetoSite, str] = {
    DiscussVetoSite.DISCUSS_GATE_IN: "DISCUSS_GATE_IN",
    DiscussVetoSite.DISCUSS_GATE_OUT: "DISCUSS_GATE_OUT",
}

# Per-site discriminating recovery fix-token (parity: the carried recovery must
# name the fix specific to that veto, not a generic "a gate blocked").
_RECOVERY_TOKENS_BY_SITE: dict[DiscussVetoSite, tuple[str, ...]] = {
    DiscussVetoSite.DISCUSS_GATE_IN: (
        "ssot",
        "docs/product",
        "migration",
        "vision",
        "precondition",
    ),
    DiscussVetoSite.DISCUSS_GATE_OUT: (
        "slice plan",
        "slice-plan",
        "feature-delta",
        "value-bearing",
        "review",
    ),
}


@dataclass
class DeclarativeGateStackComposition:
    """Drives the DISCUSS gate-in/gate-out lift through the REAL spine + seams."""

    _project_root: Path | None = field(default=None)
    _site: DiscussVetoSite | None = field(default=None)
    _decision_action: str | None = field(default=None)
    _decision_reason: str | None = field(default=None)
    _decision_recovery: list[str] | None = field(default=None)
    # run-ORDER observable: the ordered sequence the generic PreToolUse handler
    # composes (wave_gate_stacks.<wave>.gate-in FIRST, then dispatch.pre).
    _composed_order: list[str] | None = field(default=None)

    # ---- given --------------------------------------------------------------

    def given_discuss_gate_stack_declared(
        self, tmp_path: Path, site: DiscussVetoSite
    ) -> None:
        """Arm the precondition steering the REAL service down ``site``'s veto.

        The DISCUSS gate stack is declared as DATA in the SHIPPED
        ``wave_gate_stacks.discuss`` block; this Given arms the runtime state that
        makes that declared stack's gate VETO.
        """
        self._project_root = tmp_path
        self._site = site
        self._arm_precondition(tmp_path, site)

    # ---- when ---------------------------------------------------------------

    def when_active_wave_dispatch_iterates_declared_stack(self) -> None:
        """Drive the REAL spine for the armed boundary; capture the decision."""
        assert self._site is not None
        if self._site is DiscussVetoSite.DISCUSS_GATE_OUT:
            self._run_subagent_stop_gate()
        else:
            self._run_pre_tool_use_gate()

    # ---- then: AT-1 / AT-2 (declared stack iterated, halt at first veto) -----

    def then_declared_stack_is_the_veto_source(self, boundary: WaveBoundary) -> None:
        """The veto is sourced from the DECLARED ``wave_gate_stacks.discuss`` stack.

        Seam-named oracle (Mandate-15 seam #1 + #3): drives the REAL
        ``flavor_dispatcher.resolve_wave_gate_stack`` over the SHIPPED
        ``atdd_pure.yaml`` and asserts it returns a NON-EMPTY ordered gate list for
        ``discuss``/``boundary`` -- proving the gate stack is DATA, not the
        imperative ``if markers.wave`` branch.

        RED at HEAD: ``resolve_wave_gate_stack`` does not exist (the helper is the
        DESIGN net-new pure function) -> the absence is caught and re-raised as a
        semantic AssertionError naming the missing seam; GREEN once DELIVER adds the
        helper + the ``wave_gate_stacks.discuss`` block.
        """
        stack = self._resolve_declared_stack(_DISCUSS_WAVE, boundary)
        assert stack, (
            f"the DISCUSS {boundary.value} stack must be declared as DATA in "
            f"wave_gate_stacks.discuss.{boundary.value} (resolved via the REAL "
            "flavor_dispatcher.resolve_wave_gate_stack over the shipped "
            "atdd_pure.yaml) -- the generic handler iterates THIS declared list, "
            f"not the imperative `if markers.wave` branch; resolved stack={stack!r}. "
            f"{self._observed()}"
        )

    def then_the_boundary_veto_still_blocks(self) -> None:
        """Deny preserved: the migrated veto STILL blocks (behavior-preserved)."""
        assert self._gate_decision() is GateDecision.BLOCK, (
            f"{self._site}: the lifted veto must still BLOCK (behavior-preserved -- "
            "moving the wiring from the imperative branch to the declared stack must "
            f"not weaken the veto); the gate returned {self._decision_action!r}. "
            f"{self._observed()}"
        )

    def then_block_names_the_boundary_reason(self) -> None:
        """The block carries this boundary's discriminating reason-code prefix."""
        assert self._site is not None
        prefix = _REASON_PREFIX_BY_SITE[self._site]
        reason = self._decision_reason or ""
        assert prefix in reason, (
            f"{self._site}: the lifted veto must carry the boundary's specific "
            f"reason-code prefix {prefix!r}; got reason={reason!r}. {self._observed()}"
        )

    # ---- then: AT-4 (per-gate veto-reason + recovery parity) -----------------

    def then_recovery_is_carried_with_parity(self) -> None:
        """The block carries the gate's SPECIFIC recovery through the DECLARATIVE path.

        Seam-named oracle (Mandate-15 seam #2 + #3): parity is satisfied ONLY when
        the recovery flows through the declarative composition (OB-2: each gate's
        recovery parsed from its JSON stdout into the net-new
        ``GateInvocationResult.recovery_suggestions`` field, carried by the generic
        iteration over ``wave_gate_stacks.discuss``) -- not merely "the imperative
        branch happened to carry a non-empty list".

        RED at HEAD: the net-new ``GateInvocationResult.recovery_suggestions`` field
        does NOT exist, so the declarative carry path cannot exist; this asserts the
        field is present (the seam) AND the carried recovery names the site-specific
        fix with parity. The field-absence is the RED -- at HEAD the parity cannot be
        sourced from the declarative path because the field that carries it is absent.
        GREEN once DELIVER adds the field + the per-gate parse + the wave-stack carry.
        """
        assert self._site is not None
        # Seam-presence gate: the declarative carry requires the net-new field.
        from des.application.flavor_dispatcher import GateInvocationResult

        field_names = set(GateInvocationResult.__dataclass_fields__)
        assert "recovery_suggestions" in field_names, (
            f"{self._site}: OB-2 parity requires the per-gate recovery to be carried "
            "by the DECLARATIVE composition -- the net-new "
            "GateInvocationResult.recovery_suggestions field is the carrier; it does "
            f"not exist yet (fields={sorted(field_names)!r}). A non-empty recovery on "
            "the imperative branch is NOT parity through the declarative path. "
            f"{self._observed()}"
        )
        recovery = self._decision_recovery or []
        assert recovery, (
            f"{self._site}: the lifted block must carry a NON-EMPTY recovery list "
            "through the generic iteration (OB-2 parity), not a generic "
            f"'a gate blocked'; recovery is empty. {self._observed()}"
        )
        joined = " ".join(recovery).lower()
        tokens = _RECOVERY_TOKENS_BY_SITE[self._site]
        assert any(token in joined for token in tokens), (
            f"{self._site}: the carried recovery must NAME the fix specific to this "
            f"veto (one of {tokens!r}) with parity to the imperative branch; got "
            f"recovery={self._decision_recovery!r}. {self._observed()}"
        )

    # ---- then: AT-2 companion (the PO-review consumer veto catalog gate) ------

    def then_po_review_veto_gate_is_catalogued(self) -> None:
        """The PO-review consumer veto is a DECLARED catalog ``gate_id`` (OB-2).

        Seam-named oracle (Mandate-15 seam #4): drives the REAL
        ``des verify-discuss-review`` subcommand (Layer 3 subprocess). The 2-row
        gate-out list ``[validate-feature-delta, verify-discuss-review]`` is only
        expressible once the consumer veto is a catalog gate.

        RED at HEAD: ``verify-discuss-review`` is UNREGISTERED -> the dispatcher
        rejects it with ``invalid choice`` (exit 2); the discriminating stderr
        (``invalid choice`` present) is the RED signal. GREEN once DELIVER ships the
        thin catalog gate wrapping ``DiscussReviewGate.evaluate``.
        """
        exit_code, _stdout, stderr = self._run_des([_PO_REVIEW_VETO_GATE_ID, "--help"])
        combined = stderr.lower()
        assert "invalid choice" not in combined, (
            f"the PO-review consumer veto must be a registered catalog gate "
            f"({_PO_REVIEW_VETO_GATE_ID!r}) so the DISCUSS gate-out stack is the "
            "2-row declared list [validate-feature-delta, verify-discuss-review] "
            f"(OB-2 promotion); `des {_PO_REVIEW_VETO_GATE_ID}` is still an "
            f"'invalid choice' (exit {exit_code}). stderr={stderr!r}"
        )

    # ---- then: run-ORDER AT (§22.0 MEDIUM advisory) --------------------------

    def then_gate_in_composes_before_wave_agnostic_dispatch(self) -> None:
        """The wave gate-IN composition runs BEFORE the wave-agnostic dispatch.pre.

        §22.0 DESIGN-review MEDIUM advisory: assert the TWO-composition ORDER (the
        DISCUSS precondition fires before carpaccio), not each in isolation. The
        observable is the ordered gate-id sequence the generic PreToolUse handler
        composes: the ``wave_gate_stacks.discuss.gate-in`` gate(s) FIRST, then the
        ``dispatch.pre`` gate(s) (verify-readiness-pre-dispatch / carpaccio-slice-gate).

        RED at HEAD: the handler does NOT yet compose the wave stack ahead of the
        event composition (the wave gate-IN is an imperative branch, not part of the
        composed order) -> the observed order does not begin with the declared
        gate-in stack -> semantic AssertionError. GREEN once DELIVER's generic
        handler runs the select->iterate(gate-in) THEN dispatch.pre path
        (DESIGN OB-1 coexistence, lines 618-626).
        """
        order = self._composed_order or []
        gate_in_stack = self._resolve_declared_stack(
            _DISCUSS_WAVE, WaveBoundary.GATE_IN
        )
        gate_in_ids = [row["gate_id"] for row in gate_in_stack]
        assert gate_in_ids, (
            "the DISCUSS gate-in stack must be declared (wave_gate_stacks.discuss."
            "gate-in) so the run-order can be asserted; it resolved empty. "
            f"{self._observed()}"
        )
        # The composed order must START with the wave gate-in stack, THEN the
        # wave-agnostic dispatch.pre gates -- the two-composition order.
        assert order[: len(gate_in_ids)] == gate_in_ids, (
            "the generic PreToolUse handler must compose the wave "
            f"gate-in stack {gate_in_ids!r} FIRST, then the wave-agnostic "
            "dispatch.pre gates (a DISCUSS precondition must fire before "
            f"carpaccio); observed composed order={order!r}. {self._observed()}"
        )
        # And the dispatch.pre carpaccio gate must appear AFTER the gate-in stack.
        assert any("carpaccio" in gid for gid in order[len(gate_in_ids) :]), (
            "the wave-agnostic dispatch.pre composition (carpaccio-slice-gate) must "
            f"run AFTER the wave gate-in stack; observed order={order!r}. "
            f"{self._observed()}"
        )

    # ---- driving-port invocations -------------------------------------------

    def _run_pre_tool_use_gate(self) -> None:
        """Drive the REAL PreToolUseService.validate via the production composition root."""
        assert self._project_root is not None
        from des.adapters.drivers.hooks import service_factory
        from des.ports.driver_ports.pre_tool_use_port import PreToolUseInput

        prompt = (
            "<!-- DES-VALIDATION : required -->\n"
            "<!-- DES-PROJECT-ID : probe-discuss -->\n"
            "<!-- DES-STEP-ID : discuss-1 -->\n"
            "begin the discuss wave"
        )
        prev_cwd = Path.cwd()
        try:
            os.chdir(self._project_root)
            service = service_factory.create_pre_tool_use_service()
            decision = service.validate(
                PreToolUseInput(prompt=prompt, wave_entering=True)
            )
        finally:
            os.chdir(prev_cwd)
        self._record(decision)
        self._capture_composed_order()

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

    def _resolve_declared_stack(
        self, wave: str, boundary: WaveBoundary
    ) -> list[dict[str, str]]:
        """Drive the REAL registry-sourced stack resolver over the wave registry.

        slice-06 MOVE-completion (ADR-FLOW-006 D6): the DISCUSS gate-stack SOURCE
        moved from the flavor-private ``wave_gate_stacks.discuss`` block (deleted)
        to the canonical wave-contract registry ``nWave/waves/discuss.yaml``. The
        resolution is retargeted to the spine
        ``wave_gate_stack_dispatch.resolve_stack`` -- the registry-sourced entry the
        REAL PreToolUse/SubagentStop callers now read (pre_tool_use_service.py:327 /
        subagent_stop_service.py:311). The behavioral guarantee is UNCHANGED: the
        DISCUSS stack is declared DATA (a NON-EMPTY ordered gate list), proving the
        veto is DATA-sourced, not the imperative ``if markers.wave`` branch -- only
        the SOURCE moved (flavor -> registry). The stack is now WAVE-keyed
        (flavor-independent), so ``flavor_id`` no longer selects it.
        """
        from des.application import wave_gate_stack_dispatch

        resolver = getattr(wave_gate_stack_dispatch, "resolve_stack", None)
        if resolver is None:
            return []
        try:
            stack = resolver(wave, boundary.value)
        except (KeyError, ValueError, FileNotFoundError):
            return []
        return list(stack)

    def _capture_composed_order(self) -> None:
        """Build the run-ORDER from DESIGN-sanctioned seams only.

        The handler composes, in order: the wave ``wave_gate_stacks.discuss.gate-in``
        stack (via the net-new ``resolve_wave_gate_stack``) FIRST, then the
        wave-agnostic ``dispatch.pre`` event composition (iterated via the EXISTING
        ``dispatch_lifecycle_event``). This concatenation IS the handler order the
        DESIGN OB-1 coexistence declares (lines 618-626) -- reconstructed from the two
        sanctioned seams, NOT from any invented ``compose_pre_tool_use_order`` symbol.

        At HEAD ``resolve_wave_gate_stack`` is absent -> the gate-in segment is empty
        -> the composed order does not begin with the declared gate-in stack -> the
        run-ORDER Then fires RED. GREEN once the resolver returns the declared
        gate-in stack so the handler composes it ahead of dispatch.pre.
        """
        gate_in_ids = [
            row["gate_id"]
            for row in self._resolve_declared_stack(_DISCUSS_WAVE, WaveBoundary.GATE_IN)
        ]
        dispatch_pre_ids = self._dispatch_pre_order()
        # Handler order: wave gate-in FIRST, then the wave-agnostic dispatch.pre.
        self._composed_order = gate_in_ids + dispatch_pre_ids

    def _dispatch_pre_order(self) -> list[str]:
        """Iterate the shipped ``dispatch.pre`` composition via the EXISTING dispatcher.

        DESIGN-sanctioned: drives ``dispatch_lifecycle_event`` over the shipped
        atdd_pure ``dispatch.pre`` event with a pass-through in-process invoker; the
        ordered ``gate_results`` are the wave-agnostic segment of the composed order.
        """
        from des.application.flavor_dispatcher import dispatch_lifecycle_event

        def invoker(gate_id: str, _ctx: dict[str, str]) -> tuple[int, str]:
            return 0, json.dumps({"verdict": "pass", "gate_id": gate_id})

        try:
            result = dispatch_lifecycle_event(
                "dispatch.pre",
                _ATDD_PURE,
                {"feature_id": "probe", "slice_id": "slice-01"},
                flavors_dir=_SHIPPED_FLAVORS_DIR,
                gate_invoker=invoker,
            )
        except (KeyError, ValueError, FileNotFoundError):
            return []
        return [r.gate_id for r in result.gate_results]

    def _run_des(self, argv: list[str]) -> tuple[int, str, str]:
        """Invoke the REAL des dispatcher IN-PROCESS via the ``des.cli`` EDGE main(argv).

        The faithful in-process analogue of the former ``python -m des.cli
        <argv...>`` fork: ``run_cli_in_process`` drives ``des.cli.__main__.main``
        (the same dispatcher ``python -m des.cli`` runs) under ``cwd=REPO_ROOT``,
        capturing the (exit_code, stdout, stderr) triple. The fork's
        ``PYTHONPATH=src`` is already satisfied in-process (``des`` is importable
        in the test interpreter), so no env shim is needed.
        """
        return run_cli_in_process(list(argv), cwd=REPO_ROOT)

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

    def _arm_precondition(self, root: Path, site: DiscussVetoSite) -> None:
        if site is DiscussVetoSite.DISCUSS_GATE_IN:
            # A discuss wave-entering dispatch with product-SSOT absent -> the
            # gate-IN precondition is unmet -> DISCUSS_GATE_IN_* block.
            self._write_floor(
                root,
                json.dumps(
                    {"wave": "discuss", "provenance": "command", "entry_pending": True}
                ),
            )
            # docs/product/ PRESENT but its required SSOT docs absent -> MISSING_SSOT,
            # still a hard DISCUSS_GATE_IN veto. (MIGRATION_UNMET = docs/product/
            # absent was declassed veto->advisory in slice-05 / ADR-FLOW-002 Q4, so
            # the entry-veto site is now armed via the missing-ssot precondition.)
            (root / "docs" / "product").mkdir(parents=True, exist_ok=True)
        elif site is DiscussVetoSite.DISCUSS_GATE_OUT:
            # A discuss wave with an infra-only feature-delta slice plan -> the
            # gate-OUT structural cohesion veto -> DISCUSS_GATE_OUT_* block.
            self._write_floor(
                root, json.dumps({"wave": "discuss", "provenance": "command"})
            )
            self._write_feature_delta(root, _INFRA_ONLY_FEATURE_DELTA)

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
            f"recovery={self._decision_recovery!r}); composed_order="
            f"{self._composed_order!r}; site={self._site!r}; "
            f"project_root={self._project_root!r}"
        )
