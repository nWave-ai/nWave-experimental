"""PreToolUseService - application service for Agent tool invocation validation.

Orchestrates domain logic (DesMarkerParser, MarkerCompletenessPolicy) and driven ports
(ValidatorPort, AuditLogWriter, TimeProvider) to produce allow/block decisions.

This service implements the PreToolUsePort driver port interface.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from des.domain.des_marker_parser import (
    classify_atdd_pure_dispatch,
    classify_find_dispatch,
    classify_refactor_dispatch,
)
from des.domain.wave_active import NoWaveActive, WaveActiveRecord
from des.ports.driven_ports.audit_log_writer import AuditEvent, AuditLogWriter
from des.ports.driven_ports.committed_scope_port import Indeterminate
from des.ports.driver_ports.pre_tool_use_port import (
    HookDecision,
    PreToolUseInput,
    PreToolUsePort,
)


if TYPE_CHECKING:
    from collections.abc import Callable

    from des.domain.des_enforcement_policy import DesEnforcementPolicy
    from des.domain.des_marker_parser import DesMarkerParser
    from des.domain.marker_completeness_policy import MarkerCompletenessPolicy
    from des.ports.driven_ports.product_ssot_reader import ProductSsotReader
    from des.ports.driven_ports.time_provider_port import TimeProvider
    from des.ports.driven_ports.wave_active_store import WaveActiveReader
    from des.ports.driver_ports.validator_port import ValidatorPort


class PreToolUseService(PreToolUsePort):
    """Validates Agent tool invocations before execution.

    Flow:
      1. Parse DES markers via DesMarkerParser
      2. Block step-id tasks without DES markers via DesEnforcementPolicy
         - If enforced: log HOOK_PRE_TOOL_USE_BLOCKED, return block
      2.5. Whole-project exemption (ADR-PST-001): if deliverable_type is in
         DesEnforcementPolicy.EXEMPT_DELIVERABLE_TYPES (plugin/skill), log
         HOOK_PRE_TOOL_USE_ALLOWED and return allow immediately — a plugin/skill
         project is not policed at all (no completeness/structure validation).
         Unreachable for application/None (not in the exempt set).
      3. If not DES task: log HOOK_PRE_TOOL_USE_ALLOWED, return allow immediately
         (no prompt validation — non-DES tasks pass through)
      4. Validate marker completeness via MarkerCompletenessPolicy
         - If invalid: log HOOK_PRE_TOOL_USE_BLOCKED, return block
         - If orchestrator mode: log HOOK_PRE_TOOL_USE_ALLOWED, return allow
      5. Validate prompt structure via ValidatorPort
         - If invalid: log HOOK_PRE_TOOL_USE_BLOCKED, return block
         - If valid: log HOOK_PRE_TOOL_USE_ALLOWED, return allow
    """

    def __init__(
        self,
        marker_parser: DesMarkerParser,
        prompt_validator: ValidatorPort,
        audit_writer: AuditLogWriter,
        time_provider: TimeProvider,
        enforcement_policy: DesEnforcementPolicy | None = None,
        completeness_policy: MarkerCompletenessPolicy | None = None,
        atdd_pure_validator: ValidatorPort | None = None,
        wave_active_reader: WaveActiveReader | None = None,
        product_ssot_reader: ProductSsotReader | None = None,
        deliverable_type: str | None = None,
    ) -> None:
        self._marker_parser = marker_parser
        self._prompt_validator = prompt_validator
        self._audit_writer = audit_writer
        self._time_provider = time_provider
        self._enforcement_policy = enforcement_policy
        self._completeness_policy = completeness_policy
        self._atdd_pure_validator = atdd_pure_validator
        self._wave_active_reader = wave_active_reader
        self._product_ssot_reader = product_ssot_reader
        # ADR-PST-001 (feature plugin-skill-deliverable-type): resolved once per
        # dispatch by the DESConfig adapter, threaded pure into policy.check().
        # ``None`` keeps the app-code enforcement path byte-identical.
        self._deliverable_type = deliverable_type

    def validate(
        self,
        input_data: PreToolUseInput,
        hook_id: str | None = None,
    ) -> HookDecision:
        """Validate a Task tool invocation.

        Args:
            input_data: Parsed input from the hook protocol
            hook_id: Optional correlation ID from the adapter hook invocation.
                When provided, included in all emitted audit events for correlation.

        Returns:
            HookDecision indicating allow or block
        """
        # Step 1: Parse DES markers
        markers = self._marker_parser.parse(input_data.prompt)

        # Step 1b: Source the ACTIVE wave from the deterministic WaveActiveReader
        # (NEVER self-reported from the prompt). NoWaveActive -> wave None (S1);
        # a record -> the armed wave name; Indeterminate -> degrade-LOUD block.
        wave_state = self._read_active_wave()
        if isinstance(wave_state, Indeterminate):
            reason = f"WAVE_ACTIVE_INDETERMINATE: {wave_state.reason}"
            self._log_blocked(reason, hook_id=hook_id)
            return HookDecision.block(
                reason=reason,
                recovery_suggestions=[
                    "The wave-active floor .nwave/wave-active/active.json is "
                    "unreadable or corrupt -- restore a valid floor: ensure the "
                    "file holds a single well-formed JSON object describing the "
                    "active wave state (or remove it if no wave is active).",
                    "Re-derive the wave state by re-running the wave entry command "
                    "so the floor is written cleanly, then retry the dispatch.",
                ],
            )
        markers = replace(markers, wave=wave_state)

        # Step 1c: DISCUSS gate-IN precondition (slice-07). When the ACTIVE wave
        # is 'discuss', the wave-ENTERING dispatch must satisfy the DISCUSS entry
        # preconditions (product migration-gate + the four SSOT docs, §8). The
        # gate only VETOES (§22.0): a non-PASS DiscussGateIn token -> block; an
        # unreadable root -> INDETERMINATE degrade-LOUD block (§17). Additive DI:
        # no product_ssot_reader wired -> branch skipped (mirrors the slice-04
        # wave_active_reader degrade -- the gate never breaks existing wiring).
        #
        # The discriminant keys on TWO deterministic signals (never prompt
        # wording -- F3 NORMATIVO, slice-07c; the AD-66 keyword heuristic is
        # DELETED): (1) the ACTIVE wave is 'discuss' (sourced from the
        # WaveActiveReader floor, never self-reported) AND (2)
        # input_data.wave_entering -- computed by OUR hook adapter from OUR
        # floor's anchor-owned entry_pending flag
        # (WaveActivationService.peek_entry), the STRUCTURAL wave-entering
        # signal the COMMAND arm wrote. A later in-wave dispatch arrives with
        # the flag cleared (clear-on-allow), so the entry preconditions run
        # exactly once; an in-wave marked CHILD is honoured by the slice-04
        # wave-aware hinge below (PRESERVED, DESIGN REMOVE-scope). An ad-hoc
        # no-wave dispatch (markers.wave is None) never reaches here (K2).
        if (
            markers.wave == "discuss"
            and self._product_ssot_reader is not None
            and input_data.wave_entering
        ):
            gate_in_block = self._discuss_gate_in_declarative(
                "discuss", hook_id=hook_id
            )
            if gate_in_block is not None:
                return gate_in_block

        # Step 2: Enforce DES markers on step-id references (applies to all tasks)
        if self._enforcement_policy:
            enforcement = self._enforcement_policy.check(
                input_data.prompt, self._deliverable_type
            )
            if enforcement.is_enforced:
                self._log_blocked(
                    enforcement.reason or "DES_MARKERS_MISSING", hook_id=hook_id
                )
                return HookDecision.block(
                    reason=enforcement.reason or "DES_MARKERS_MISSING",
                    recovery_suggestions=enforcement.recovery_suggestions,
                )

            # Whole-project exemption (ADR-PST-001): declaring plugin/skill exempts
            # ALL step dispatches for that project -- the policy has already
            # certified is_enforced=False, so the service honors that verdict at
            # whole-project granularity and allows immediately, without re-imposing
            # discipline via marker-completeness/prompt-structure validation. The
            # service only THREADS this context; the enforcement decision stays in
            # the pure policy. App-code (None/application) is unaffected: it never
            # enters this branch, so its path is byte-identical.
            if (
                self._deliverable_type
                in self._enforcement_policy.EXEMPT_DELIVERABLE_TYPES
            ):
                self._log_allowed(context="deliverable_type_exempt", hook_id=hook_id)
                return HookDecision.allow()

        if not markers.is_des_task:
            # Mode-aware routing BEFORE the classic WAVE_MARKER_BYPASS (spine
            # friction, 2026-06-23): an atdd_pure dispatch carries the atdd_pure
            # marker discipline (DES-MODE:atdd_pure + DES-PHASE + DES-SLICE), NOT
            # the classic DES-VALIDATION the bypass below demands. Route it to
            # atdd_pure validation so a still-armed wave floor does NOT deny an
            # in-flight atdd_pure slice for lacking classic markers it never emits.
            # Purely ADDITIVE: a 'defective' atdd_pure dispatch is still blocked
            # loud by the atdd_pure validator (no silent bypass); a classic
            # ('absent') dispatch falls through to the unchanged bypass below.
            atdd_pure_classification = classify_atdd_pure_dispatch(markers)
            if atdd_pure_classification != "absent":
                return self._validate_atdd_pure_dispatch(
                    input_data.prompt, atdd_pure_classification, hook_id=hook_id
                )
            # Wave-aware hinge (slice-04, relaxed by fix-wave-dispatch-marker-contract
            # slice-01). Asymmetric authority (§22.0): the gate only VETOES; it
            # never writes the authorizing wave-state. The veto is now EXEMPT for a
            # wave-ENTERING dispatch (input_data.wave_entering=True) -- the exact
            # DES-WAVE-only shape every command template ships (§22.7.A). The
            # discriminant is the deterministic adapter-computed wave_entering
            # signal, NEVER prompt wording.
            if (
                markers.wave is not None
                and markers.carries_partial_wave_context
                and not input_data.wave_entering
            ):
                # S2a: the child's OWN <!-- DES-WAVE: <wave> --> declaration
                # MATCHES the active floor's wave -- a legitimate wave-membership
                # claim, not a bypass (fix-wave-marker-blocks-non-atdd-pure-child
                # slice-01). DES-WAVE only ARMS enforcement, it never authorizes
                # past it -- so a MATCHING declaration is honoured (allowed); a
                # MISSING declaration (no DES-WAVE at all, e.g. a bare DES-STEP-ID
                # subset) or a MISMATCHED one (declares a DIFFERENT wave than
                # active) falls through to the DENY below unchanged.
                if markers.declared_wave == markers.wave:
                    self._log_allowed(context="wave_marker_match", hook_id=hook_id)
                    return HookDecision.allow()
                # S2: a wave is active AND this dispatch carries PARTIAL wave context
                # (a DES marker subset OR a DES-WAVE declaration) but MISSES the
                # required DES-VALIDATION marker AND it is NOT entering the wave
                # -> a positively-identified wave-owned child that dropped its
                # required marker. The bypass is made LOUD (a DENY), never a silent
                # allow that would let it slip past the gate (K1). A FULLY-MARKERLESS
                # dispatch (carries_partial_wave_context=False) is an ad-hoc benign
                # prompt allowed below (K2 -- floor-in-the-tree is NOT in-the-wave);
                # a wave-ENTERING dispatch (wave_entering=True) is a legitimate entry
                # exempted above (ADR-001 positive-bypass-signal).
                reason = (
                    f"WAVE_MARKER_BYPASS: the '{markers.wave}' wave is active but "
                    "this in-wave sub-dispatch carries partial wave context and "
                    "is missing the required DES-VALIDATION marker -- a wave-owned "
                    "child that dropped its markers is a wave bypass, denied loud "
                    "(it must carry the wave's DES markers to proceed)"
                )
                recovery_suggestions = [
                    "Carry the wave's DES markers on this sub-dispatch: copy the "
                    "<!-- DES-VALIDATION --> (and the wave's DES-MODE / DES-PHASE / "
                    "DES-SLICE / DES-PROJECT-ID / DES-STEP-ID / DES-PROJECT-ROOT) "
                    "markers from the parent wave dispatch onto this child prompt.",
                    "Alternatively, carry a "
                    f"<!-- DES-WAVE: {markers.wave} --> marker matching the "
                    "active wave on this sub-dispatch -- a matching DES-WAVE "
                    "declaration is honoured as a legitimate wave-membership "
                    "claim and is allowed without DES-VALIDATION.",
                    f"If the '{markers.wave}' wave floor is STALE (a days-old wave "
                    "you are not actually in), clear it with the sanctioned command "
                    '`des wave-clear --reason "<why>"` so the floor no longer '
                    "blocks this dispatch.",
                ]
                self._log_blocked(reason, hook_id=hook_id)
                return HookDecision.block(
                    reason=reason, recovery_suggestions=recovery_suggestions
                )
            # S1: no wave active -> ad-hoc non-wave dispatch, allowed untouched (K2).
            self._log_allowed(context="non_des_task", hook_id=hook_id)
            return HookDecision.allow()

        # Step 3: refactor/find dispatch routing (D8, des-refactor-fixer-swarm
        # slice-03; reordered ahead of marker completeness by
        # bugfix-refactor-dispatch-mode-recognition-order). A DES-MODE:refactor
        # or DES-MODE:find dispatch is spine-recognized (allowed) rather than
        # forced through marker completeness or the classic Step 5
        # TemplateValidator -- mirrors how atdd_pure recognition (Step 2b
        # above) already runs before completeness for the same reason. MUST
        # run BEFORE the completeness check below: MarkerCompletenessPolicy
        # treats any non-atdd_pure mode as "classic" and demands DES-STEP-ID,
        # a marker a refactor/find dispatch never carries (D8: "no
        # per-dispatch DES-EXEMPT hand-typed justification required") -- if
        # completeness ran first it would refuse the exact dispatch this
        # recognition exists to allow. A markerless classic dispatch (no
        # DES-MODE) is unaffected -- both classifiers return 'absent' and
        # completeness/Step 5 still fire.
        if (
            classify_refactor_dispatch(markers) == "valid"
            or classify_find_dispatch(markers) == "valid"
        ):
            self._log_allowed(context="refactor_find_mode", hook_id=hook_id)
            return HookDecision.allow()

        # Step 4: Validate marker completeness
        if self._completeness_policy:
            completeness = self._completeness_policy.validate(markers)
            if not completeness.is_valid:
                self._log_blocked(
                    completeness.reason or "DES_MARKERS_INCOMPLETE", hook_id=hook_id
                )
                return HookDecision.block(
                    reason=completeness.reason or "DES_MARKERS_INCOMPLETE",
                    recovery_suggestions=completeness.recovery_suggestions,
                )

        if markers.is_orchestrator_mode:
            # Orchestrator mode: relaxed validation
            self._log_allowed(context="orchestrator_mode", hook_id=hook_id)
            return HookDecision.allow()

        # Step 4b: Mode-aware dispatch-prompt routing (T-B / F-08 G-2).
        # An atdd_pure dispatch carries the A→G phase block + AT-completion
        # ledger sections, NOT the classic execution-log schema. Route it to
        # the atdd_pure validator so the classic mandatory-section schema is
        # not wrongly imposed. A classic dispatch ("absent") is unchanged.
        classification = classify_atdd_pure_dispatch(markers)
        if classification != "absent":
            return self._validate_atdd_pure_dispatch(
                input_data.prompt, classification, hook_id=hook_id
            )

        # Step 5: Validate DES prompt structure (classic schema)
        validation_result = self._prompt_validator.validate_prompt(input_data.prompt)

        if validation_result.task_invocation_allowed:
            self._log_allowed(context="des_validated", hook_id=hook_id)
            return HookDecision.allow()
        else:
            reason = "; ".join(validation_result.errors)
            self._log_blocked(reason, hook_id=hook_id)
            return HookDecision.block(
                reason=reason,
                recovery_suggestions=[
                    "GENERATE the dispatch, do not hand-write it: `des dispatch "
                    "--project-id <feature-id> --slice <slice-NN> --phase <phase> "
                    '--intent "<task>"` emits a prompt carrying every mandatory '
                    "section BY CONSTRUCTION. Copy its output verbatim.",
                    "This prompt declares the DEPRECATED classic mode (9 sections, "
                    "roadmap-driven). New work runs atdd_pure, which `des dispatch` "
                    "defaults to -- prefer regenerating there over repairing this.",
                    f"What is missing right now: {reason}. Hand-adding the named "
                    "section does work -- but hand-assembly is exactly how a "
                    "mandatory section goes missing, so regenerating is the "
                    "cheaper fix and the one that cannot drift again.",
                ],
            )

    def _validate_atdd_pure_dispatch(
        self,
        prompt: str,
        classification: str,
        hook_id: str | None = None,
    ) -> HookDecision:
        """Validate an atdd_pure carpaccio-slice dispatch prompt (T-B).

        A 'defective' marker set is blocked outright. A 'valid' marker set is
        validated against the atdd_pure section schema via the atdd_pure
        validator; if no atdd_pure validator is wired, the dispatch is allowed
        (marker set already proven valid by classify_atdd_pure_dispatch).
        """
        if classification == "defective":
            reason = "ATDD_PURE_DISPATCH_DEFECTIVE: incomplete atdd_pure marker set"
            self._log_blocked(reason, hook_id=hook_id)
            return HookDecision.block(
                reason=reason,
                recovery_suggestions=[
                    "The atdd_pure DES markers are incoherent -- make the "
                    "DES-MODE / DES-PHASE / DES-SLICE markers coherent: a per-slice "
                    "phase (e.g. A_GREEN_ATS) must carry a per-slice DES-SLICE "
                    "(e.g. slice-01), and a feature-end phase (e.g. G_COMMIT) must "
                    "carry the feature-end scope -- do not pair a per-slice phase "
                    "with a feature-end DES-SLICE.",
                    "Re-emit the dispatch with a complete, coherent atdd_pure marker "
                    "set (DES-MODE: atdd_pure + matching DES-PHASE + DES-SLICE).",
                ],
            )

        if self._atdd_pure_validator is None:
            self._log_allowed(context="atdd_pure_validated", hook_id=hook_id)
            return HookDecision.allow()

        validation_result = self._atdd_pure_validator.validate_prompt(prompt)
        if validation_result.task_invocation_allowed:
            self._log_allowed(context="atdd_pure_validated", hook_id=hook_id)
            return HookDecision.allow()

        reason = "; ".join(validation_result.errors)
        self._log_blocked(reason, hook_id=hook_id)
        return HookDecision.block(
            reason=reason,
            recovery_suggestions=[
                "GENERATE the dispatch, do not hand-write it: `des dispatch "
                "--mode atdd_pure --project-id <feature-id> --slice <slice-NN> "
                '--phase <phase> --intent "<task>"` emits a prompt carrying every '
                "atdd_pure mandatory section BY CONSTRUCTION. Copy its output "
                "verbatim -- do not re-type it.",
                "For a single-slice BUGFIX (no feature-delta by design) add "
                "`--lane bugfix --defect <what-is-broken> --regression-test <path>`: "
                "the generator emits the lane markers and justification for you. "
                "Hand-writing those markers is not required and is how they end up "
                "malformed.",
                f"What is missing right now: {reason}. Hand-adding the named "
                "section does work -- but hand-assembly is exactly how a mandatory "
                "section goes missing, so regenerating is the cheaper fix and the "
                "one that cannot drift again.",
            ],
        )

    def _discuss_gate_in_declarative(
        self, wave: str, hook_id: str | None
    ) -> HookDecision | None:
        """Run the DISCUSS gate-IN stack DECLARATIVELY; return a block, or None.

        f-declarative-gate-composition (OB-1): the DISCUSS gate-IN stack is
        declared as DATA in ``wave_gate_stacks.discuss.gate-in``. This generic
        path SELECTS that stack (off the active wave), ITERATES it via the
        EXISTING ``dispatch_lifecycle_event`` (iterate-in-order,
        halt-at-first-veto), and CARRIES the blocking gate's specific reason +
        recovery through to the ``HookDecision`` (OB-2 parity). The gate stack is
        editable as data, not as a hand-coded handler branch.

        The per-gate behavior is the SAME pure core the imperative branch ran:
        the ``validate-feature-delta`` gate-id, on the gate-IN boundary, is
        routed to ``DiscussGateIn.evaluate`` over the product-SSOT presence read
        via the injected capability reader. A non-PASS token is a named-LOUD
        VETO (``DISCUSS_GATE_IN_<token>``); a clean iteration returns None so the
        normal wave-aware flow proceeds (PASS = "no objection found", NOT a GO).
        """
        from des.application import wave_gate_stack_dispatch as wgs

        assert self._product_ssot_reader is not None
        stack = wgs.resolve_stack(wave, "gate-in")
        if not stack:
            return None

        result = wgs.dispatch_wave_stack(
            stack, "discuss.gate-in", self._discuss_gate_in_invoker()
        )
        return self._block_from_composition(result, hook_id=hook_id)

    def _discuss_gate_in_invoker(
        self,
    ) -> Callable[[str, dict[str, str]], tuple[int, str]]:
        """Build the gate-IN invoker routing catalog gate-ids to the pure core.

        The invoker reads the product-SSOT presence ONCE and runs
        ``DiscussGateIn.evaluate`` for the declared ``validate-feature-delta``
        gate-id; an uncatalogued gate-id fails closed, named (reuse of the
        ``_gate_invoker_for`` fail-closed shape).

        The presence read resolves the root via ``resolve_nwave_root()``
        (DDD-14/15) rather than a bare ``Path.cwd()``, so a ``DES_PROJECT_DIR``
        override (the per-test isolation seam) redirects the read to an isolated
        root instead of the shared process cwd -- mirroring ``_read_active_wave``.
        """
        from des.application import wave_gate_stack_dispatch as wgs
        from des.domain.discuss_gate import DiscussGateIn, DiscussGateInToken
        from des.domain.nwave_root import resolve_nwave_root

        assert self._product_ssot_reader is not None
        reader = self._product_ssot_reader

        def invoke(gate_id: str, _context: dict[str, str]) -> tuple[int, str]:
            if gate_id != "validate-feature-delta":
                return wgs.unknown_gate_stdout(gate_id)
            presence = reader.ssot_present(resolve_nwave_root())
            gate_in = DiscussGateIn.evaluate(presence)
            if gate_in.token is DiscussGateInToken.PASS:
                return wgs.pass_stdout(gate_id)
            reason = f"DISCUSS_GATE_IN_{gate_in.token.value}: {gate_in.detail}"
            if gate_in.token is DiscussGateInToken.MIGRATION_UNMET:
                # ADR-FLOW-002 Q4 (retired into slice-05): a greenfield entry
                # (docs/product/ absent) is DECLASSED veto -> advisory. DIVERGE
                # owns the greenfield bootstrap; DISCUSS proceeds via the
                # soft-gate. Scope = MIGRATION_UNMET ONLY -- INDETERMINATE
                # (unreadable root) and MISSING_SSOT still hard-veto (Invariant
                # 2, §17 no-silent-pass; the degrade-LOUD veto is never coerced
                # to a silent pass).
                return wgs.advisory_stdout(
                    gate_id,
                    reason=reason,
                    advice=[
                        "This is a greenfield project (docs/product absent) -- "
                        "DIVERGE owns the greenfield bootstrap. DISCUSS may "
                        "proceed; the product-SSOT artifacts are populated "
                        "through the canonical DISCOVER -> DIVERGE -> DISCUSS "
                        "order, not as a DISCUSS precondition.",
                    ],
                )
            return wgs.veto_stdout(
                gate_id,
                reason=reason,
                recovery=[
                    "The DISCUSS gate-IN product-SSOT precondition is unmet -- "
                    "provide the docs/product SSOT artifacts the DISCUSS wave "
                    "requires (vision, roadmap, glossary, backlog) before "
                    "entering the wave.",
                    "If this is a migration of an existing project, run the "
                    "product migration so the docs/product SSOT exists, then "
                    "retry the discuss entry.",
                ],
            )

        return invoke

    def _block_from_composition(
        self, result: object, hook_id: str | None
    ) -> HookDecision | None:
        """Map a halted composition to a named-LOUD block, or None on clean pass.

        Carries the blocking gate's specific reason + recovery_suggestions
        through (OB-2 parity). A clean iteration (no halt) is "no objection
        found" -> None (NOT an authorizing GO, Invariant 4).
        """
        from des.application import wave_gate_stack_dispatch as wgs
        from des.application.flavor_dispatcher import CompositionResult

        assert isinstance(result, CompositionResult)
        if not result.halted or result.blocking_gate_id is None:
            return None
        blocking = next(
            (r for r in result.gate_results if r.gate_id == result.blocking_gate_id),
            None,
        )
        assert blocking is not None
        reason = wgs.reason_from_stdout(blocking.stdout, blocking.gate_id)
        self._log_blocked(reason, hook_id=hook_id)
        return HookDecision.block(
            reason=reason,
            recovery_suggestions=list(blocking.recovery_suggestions),
        )

    def _read_active_wave(self) -> str | None | Indeterminate:
        """Read the ACTIVE wave name via WaveActiveReader (None <=> NoWaveActive).

        No reader wired -> None (S1): the wave-aware hinge degrades to the legacy
        allow-ad-hoc behaviour. A record -> the armed wave name. Indeterminate ->
        propagated so the hinge degrades LOUD (never silent-pass).

        Resolves the root via `resolve_nwave_root()` (DDD-14/15) rather than a
        bare `Path.cwd()`, so a `DES_PROJECT_DIR` override (the per-test
        isolation seam) redirects the read to an isolated root instead of the
        shared process cwd.
        """
        if self._wave_active_reader is None:
            return None
        from des.domain.nwave_root import resolve_nwave_root

        state = self._wave_active_reader.read(resolve_nwave_root())
        if isinstance(state, WaveActiveRecord):
            return state.wave
        if isinstance(state, NoWaveActive):
            return None
        return state

    def _log_allowed(self, context: str, hook_id: str | None = None) -> None:
        """Log an allowed invocation to the audit trail."""
        self._audit_writer.log_event(
            AuditEvent(
                event_type="HOOK_PRE_TOOL_USE_ALLOWED",
                timestamp=self._time_provider.now_utc().isoformat(),
                hook_id=hook_id,
                data={"context": context},
            )
        )

    def _log_blocked(self, reason: str, hook_id: str | None = None) -> None:
        """Log a blocked invocation to the audit trail."""
        self._audit_writer.log_event(
            AuditEvent(
                event_type="HOOK_PRE_TOOL_USE_BLOCKED",
                timestamp=self._time_provider.now_utc().isoformat(),
                hook_id=hook_id,
                data={"reason": reason},
            )
        )
