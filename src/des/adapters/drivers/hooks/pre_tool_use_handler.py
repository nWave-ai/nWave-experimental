"""PreToolUse handler — validates Task/Agent tool invocations.

Translates Claude Code's PreToolUse hook event (JSON stdin) into
PreToolUseService decisions (allow/block), manages DES task signal creation,
and emits audit events through hook_protocol.

Extracted from claude_code_hook_adapter.py as part of P4 decomposition.

U1 (slice-01 of F-DES-ATDD-PURE-HOOK-GATES -- ADR-030 D1): before the classic
service path, the handler runs the carpaccio entry-gate intercept for atdd_pure
dispatches. The carpaccio gate runs whether or not the orchestrating LLM chose
to run it. The entire U1 branch is fail-closed (M1) -- any exception inside it
surfaces as an `AtddPureHookInternalError` block, never the bare exit-1 path.
"""

import contextlib
import io
import json
import time
import uuid
from pathlib import Path

from des.adapters.driven.time.system_time import SystemTimeProvider
from des.adapters.drivers.hooks import des_task_signal, hook_protocol, service_factory
from des.adapters.drivers.hooks.carpaccio_intercept import (
    InterceptDecision,
    intercept_atdd_pure_dispatch,
)
from des.adapters.drivers.hooks.earned_verdict_commit_gate_hook import (
    evaluate_commit_gate,
    is_git_commit,
)
from des.adapters.drivers.hooks.hook_protocol import (
    EXIT_CODE_TO_DECISION,
    STDERR_CAPTURE_MAX_CHARS,
    log_hook_completed,
    log_hook_error,
    log_hook_invoked,
    read_and_parse_stdin,
)
from des.adapters.drivers.hooks.project_root_validator import validate_project_root
from des.application.commit_attribution_service import CommitAttributionService
from des.application.wave_activation_service import WaveActivationService
from des.domain.atdd_pure_phases import ATDDPurePhase
from des.domain.des_marker_parser import DesMarkerParser
from des.ports.driven_ports.audit_log_writer import AuditEvent
from des.ports.driven_ports.committed_scope_port import Indeterminate
from des.ports.driver_ports.pre_tool_use_port import PreToolUseInput


# Non-zero exit code paired with a `{decision:block}` body for an atdd_pure
# U1 intercept block (matches the existing block path's exit_code convention).
_ATDD_PURE_BLOCK_EXIT_CODE = 2

# Tool names that constitute a DISPATCH (slice-07c): the wave-entering
# peek -> validate(wave_entering=) -> clear-on-allow lifecycle applies to
# agent dispatches only -- a Bash/Read tool-use is not the wave-entering
# dispatch and must never consume the pending entry flag.
_DISPATCH_TOOL_NAMES = ("Agent", "Task")

# slice-02 (oss-hook-side-phase-injection -- G-DISTILL-PRE): the DISTILL-specific
# block event the DISTILL dispatch marker-enforcement branch emits. It mirrors
# the generic U1 `AtddPureMarkerSetIncomplete` block but names the DISTILL gate
# so "a DISTILL dispatch was well-formed" is a mechanical, DISTILL-scoped fact.
_DISTILL_DISPATCH_INCOMPLETE_EVENT = "DistillDispatchMarkerSetIncomplete"

# The feature-end-cycle phase the G-DISTILL-PRE gate keys on. A D_DISTILL
# dispatch is per-feature: its only coherent scope is the `feature-end` literal.
_D_DISTILL_PHASE = ATDDPurePhase.D_DISTILL.value


def _atdd_pure_intercept_block(decision: InterceptDecision) -> dict[str, str]:
    """Render the `{decision:block}` body for a U1 intercept block."""
    return {
        "decision": "block",
        "event": decision.event or "AtddPureHookInternalError",
        "reason": decision.reason or "atdd_pure dispatch blocked by the U1 gate",
    }


def _distill_dispatch_block(reason: str) -> dict[str, str]:
    """Render the `{decision:block}` body for a G-DISTILL-PRE marker block."""
    return {
        "decision": "block",
        "event": _DISTILL_DISPATCH_INCOMPLETE_EVENT,
        "reason": reason,
    }


def _evaluate_distill_dispatch_gate(prompt: str) -> tuple[str, dict[str, str] | None]:
    """The G-DISTILL-PRE marker-enforcement gate (slice-02 AT-1 / AT-2).

    A `D_DISTILL` acceptance-designer dispatch is validated for its marker set
    BEFORE it runs. The gate produces a terminal verdict for D_DISTILL dispatches
    (short-circuiting the classic template-validation service path, which would
    otherwise block the dispatch for missing the DELIVER template sections a
    DISTILL dispatch does not carry):

      * ("allow", None)       -- a complete, coherent D_DISTILL marker set
                                 (mode atdd_pure + phase D_DISTILL + DES-PROJECT-ID
                                 + feature-end scope) -- the dispatch may run.
      * ("block", payload)    -- missing DES-PROJECT-ID, or a slice-N scope on the
                                 feature-end D_DISTILL phase (incoherent XOR) --
                                 blocked `DistillDispatchMarkerSetIncomplete`.
      * ("not_distill", None) -- not a D_DISTILL dispatch -- the classic path and
                                 the U1 carpaccio intercept run unchanged.

    Mirrors the U1 marker-block pattern: the decision table is the closed-world
    (project-id present + feature-end scope) coherence check the marker parser
    already encodes.
    """
    markers = DesMarkerParser().parse(prompt)
    if markers.mode != "atdd_pure" or markers.atdd_pure_phase != _D_DISTILL_PHASE:
        return ("not_distill", None)

    if not markers.project_id:
        return (
            "block",
            _distill_dispatch_block(
                "DISTILL acceptance-designer dispatch is missing its "
                "DES-PROJECT-ID marker -- a whole-feature DISTILL dispatch needs "
                "the feature id"
            ),
        )

    if not markers.is_feature_end:
        return (
            "block",
            _distill_dispatch_block(
                "DISTILL acceptance-designer dispatch is scoped to "
                f"'{markers.slice_id}' instead of the whole feature -- a "
                "D_DISTILL dispatch's only coherent scope is the feature-end "
                "literal"
            ),
        )

    return ("allow", None)


def _evaluate_u1_intercept(
    prompt: str, subagent_type: str = ""
) -> dict[str, str] | None:
    """Run the U1 carpaccio intercept, fail-closed (M1).

    Returns the `{decision:block}` body when the dispatch must be blocked, or
    None when the dispatch is allowed / is not an atdd_pure dispatch (the
    classic path then runs unchanged).

    The U1 decision itself is M1-wrapped inside `intercept_atdd_pure_dispatch`.
    This function adds a second, defence-in-depth try/except so an exception in
    marker parsing or project-root resolution is also surfaced as an
    `AtddPureHookInternalError` block -- NEVER the bare `exit 1` /
    `{status:error}` path. An atdd_pure-branch exception is fail-closed.

    slice-05 (DDD-8): `subagent_type` (from the Task tool_input) is threaded into
    the intercept so the wave-dispatch guard composed on `dispatch.pre` can look
    up the dispatched agent's wave->owner entry. It is best-effort + fail-OPEN: an
    absent subagent_type makes the guard treat the dispatch as a non-owner ->
    ALLOW, never a block.
    """
    try:
        markers = DesMarkerParser().parse(prompt)
        if markers.mode != "atdd_pure":
            return None

        feature_id = markers.feature_id or markers.project_id
        if not feature_id:
            return {
                "decision": "block",
                "event": "AtddPureMarkerSetIncomplete",
                "reason": (
                    "atdd_pure dispatch prompt is missing a DES-PROJECT-ID "
                    "marker -- the carpaccio gate needs the feature id"
                ),
            }

        project_root = Path.cwd()
        if markers.project_root:
            validated = validate_project_root(markers.project_root, str(Path.cwd()))
            if validated is not None:
                project_root = validated

        decision = intercept_atdd_pure_dispatch(
            prompt=prompt,
            feature_id=feature_id,
            project_root=project_root,
            subagent_type=subagent_type,
        )
        if decision.is_block:
            return _atdd_pure_intercept_block(decision)
        return None
    except Exception as exc:
        return {
            "decision": "block",
            "event": "AtddPureHookInternalError",
            "reason": f"U1 carpaccio intercept raised: {exc!s}",
        }


def _peek_wave_entering(
    hook_input: dict[str, object], activation: WaveActivationService
) -> tuple[bool, dict[str, str] | None]:
    """Peek the STRUCTURAL wave-entering discriminant (slice-07c, F3 NORMATIVO).

    Reads the anchor-owned ``entry_pending`` flag from the wave-active floor --
    never prompt wording (AD-66 closed). Returns ``(wave_entering, block)``:

      * ``(False, None)`` -- not a dispatch tool-use, or no entry pending.
      * ``(True, None)``  -- this dispatch IS the wave-entering one.
      * ``(False, {decision:block,...})`` -- corrupt floor = mechanism-absent
        -> block degrade-LOUD (§17 N=0), never coerced to a bool.
    """
    if hook_input.get("tool_name") not in _DISPATCH_TOOL_NAMES:
        return (False, None)
    peeked = activation.peek_entry(Path.cwd())
    if isinstance(peeked, Indeterminate):
        return (
            False,
            {
                "decision": "block",
                "reason": f"WAVE_ENTRY_INDETERMINATE: {peeked.reason}",
            },
        )
    return (peeked, None)


def _arm_inferred_fallback(
    hook_input: dict[str, object],
    prompt: str,
    activation: WaveActivationService,
) -> tuple[bool, dict[str, str] | None]:
    """The INFERRED fallback strand (slice-07d, F4 -- closes S2 cross-runtime).

    A wave-DECLARING dispatch (`<!-- DES-WAVE: <wave> -->`) on an EMPTY floor
    arms enforcement by itself -- the submission anchor never fired (observe-
    only / missed-write runtime). The armed record is INFERRED (lower trust
    class, I3-bounded) with ``entry_pending=False``: arm and gate-IN coincide
    in this SAME pass (self-entry NORMATIVE), so the caller proceeds as
    wave-entering immediately. Returns ``(wave_entering, block)``:

      * ``(False, None)`` -- not a dispatch tool-use, no declaration, an
        out-of-vocabulary declaration (treated absent -- no arm, no garbage
        record, K2/S1), or a floor already armed (I3: INFERRED never clobbers
        COMMAND -- the declaration can only ADD gating, never remove it).
      * ``(True, None)``  -- the fallback armed; this dispatch IS wave-entering.
      * ``(False, {decision:block,...})`` -- corrupt floor -> degrade-LOUD
        block (S17), never armed over.
    """
    if hook_input.get("tool_name") not in _DISPATCH_TOOL_NAMES:
        return (False, None)
    declared_wave = DesMarkerParser().parse(prompt).declared_wave
    if declared_wave is None:
        return (False, None)
    armed = activation.arm_inferred(Path.cwd(), declared_wave)
    if isinstance(armed, Indeterminate):
        return (
            False,
            {
                "decision": "block",
                "reason": f"WAVE_ARM_INDETERMINATE: {armed.reason}",
            },
        )
    return (armed, None)


def _log_wave_entry_clear_failed(exc: Exception, hook_id: str) -> None:
    """LOUD audit event for a failed clear-on-allow (slice-07c).

    The dispatch outcome stays UNCHANGED: a flag that could not clear fails
    toward MORE enforcement (the next dispatch re-runs the idempotent entry
    preconditions) -- never a silent pass.
    """
    try:
        hook_protocol._audit_writer_factory().log_event(
            AuditEvent(
                event_type="WAVE_ENTRY_CLEAR_FAILED",
                timestamp=SystemTimeProvider().now_utc().isoformat(),
                hook_id=hook_id,
                data={"reason": f"clear_entry raised: {exc!s}"},
            )
        )
    except Exception:
        pass  # the LOUD event must never change the dispatch outcome


def emit_commit_attribution_mutation(tool_input: dict[str, object]) -> int | None:
    """Net-new mutation branch: rewrite a Bash `git commit` to carry the trailer.

    ADR-CA-006 D4 (Reuse row R4). On a Bash `git commit` command, asks
    :class:`CommitAttributionService` for a :class:`CommitRewritePlan`. On a
    mutate Plan, emits the protocol JSON
    ``{"hookSpecificOutput":{"hookEventName":"PreToolUse",
    "permissionDecision":"allow","updatedInput":{<full tool_input, command
    rewritten>}}}`` on stdout and returns exit 0. On a passthrough Plan, returns
    ``None`` so the caller falls through to the existing validation path
    unchanged.

    This is the ONLY net-new branch in the handler; the existing block/allow
    validation path is not modified.

    Args:
        tool_input: the ``tool_input`` object from the PreToolUse payload. Its
            ``command`` field is the Bash command to consider.

    Returns:
        ``0`` after emitting a mutation; ``None`` to fall through to the existing
        validation path (passthrough / non-Bash / non-commit).
    """
    command = tool_input.get("command")
    if not isinstance(command, str) or not command:
        return None

    # Fail-safe (ADR-CA-006): attribution is best-effort. ANY error here — a
    # raising rewrite core, a JSON-serialization failure — must NOT propagate to
    # the outer `handle_pre_tool_use` `except Exception`, which fail-closes to
    # exit 1 and BLOCKS the commit. A missed trailer is recoverable; a blocked
    # commit is not. On any failure, return None so the caller falls through to
    # the existing validation path and the original command runs unchanged.
    try:
        plan = _commit_attribution_service.plan_rewrite(command)
        if plan.action != "mutate" or plan.rewritten_command is None:
            return None

        updated_input = {**tool_input, "command": plan.rewritten_command}
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "allow",
                        "updatedInput": updated_input,
                    }
                }
            )
        )
        return 0
    except Exception:
        return None


# Bound so step-composition / future wiring reference a single seam, not a free
# constructor call. DELIVER injects the real service here.
_commit_attribution_service = CommitAttributionService()


def _resolve_deliverable_type() -> str | None:
    """Resolve the project deliverable type for this dispatch (ADR-PST-001).

    Reads ``DESConfig(cwd=Path.cwd()).deliverable_type`` over the dispatch's
    working directory: a plugin/skill declaration on disk threads through
    ``service_factory`` into ``PreToolUseService.validate`` and exempts the
    step dispatch. An unresolved/absent/``application`` project returns ``None``
    so enforcement stays ON (fail-safe by construction).
    """
    from des.adapters.driven.config.des_config import DESConfig

    return DESConfig(cwd=Path.cwd()).deliverable_type


def handle_pre_tool_use() -> int:
    """Handle PreToolUse command: validate Task tool invocation.

    Protocol translation only -- all decisions delegated to PreToolUseService.

    Returns:
        0 if validation passes (allow)
        1 if error occurs (fail-closed)
        2 if validation fails (block)
    """
    hook_id = str(uuid.uuid4())
    start_ns = time.perf_counter_ns()
    exit_code = 0
    task_correlation_id: str | None = None
    stderr_buffer = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr_buffer):
            stdin_result = read_and_parse_stdin("pre_tool_use")

            if stdin_result.is_empty:
                return 0

            if stdin_result.parse_error:
                response = {"status": "error", "reason": stdin_result.parse_error}
                print(json.dumps(response))
                exit_code = 1
                return exit_code

            # The is_empty / parse_error guards above guarantee a parsed dict.
            hook_input = stdin_result.hook_input
            assert hook_input is not None  # narrowed by the guards above

            # Diagnostic: confirm hook was invoked
            tool_input = hook_input.get("tool_input", {})

            # NET-NEW Bash-commit ordering (slice-04 fix + ADR-CA-006 D4). On a
            # Bash event the earned-verdict commit gate is the FIRST authority on
            # the git-commit path: a theater commit must be DENIED before the
            # cosmetic attribution rewrite can run (deny-wins). Only on gate
            # allow / abstain / non-commit Bash does the path fall through to the
            # commit-attribution mutation unchanged.
            if hook_input.get("tool_name") == "Bash":
                command = tool_input.get("command", "")
                if is_git_commit(command):
                    commit_decision = evaluate_commit_gate(command)
                    if (
                        commit_decision is not None
                        and commit_decision.get("decision") == "block"
                    ):
                        print(json.dumps(commit_decision))
                        exit_code = _ATDD_PURE_BLOCK_EXIT_CODE
                        return exit_code
                # gate allowed / abstained / non-commit Bash -> attribution may proceed
                mutation_exit = emit_commit_attribution_mutation(tool_input)
                if mutation_exit is not None:
                    exit_code = mutation_exit
                    return exit_code

            log_hook_invoked(
                "pre_tool_use",
                {
                    "subagent_type": tool_input.get("subagent_type"),
                },
                hook_id=hook_id,
            )

            # Extract protocol fields
            # Claude Code sends: {"tool_name": "Agent", "tool_input": {...}, ...}
            prompt = tool_input.get("prompt", "")

            # G-DISTILL-PRE (slice-02) -- DISTILL dispatch marker enforcement.
            # A D_DISTILL acceptance-designer dispatch is validated for its
            # marker set BEFORE it runs and resolves to a terminal verdict here
            # (a complete set is ALLOWED -- short-circuiting the classic
            # template-validation path that would otherwise block a DISTILL
            # dispatch for the DELIVER template sections it does not carry; an
            # incomplete set BLOCKS `DistillDispatchMarkerSetIncomplete`).
            distill_verdict, distill_block = _evaluate_distill_dispatch_gate(prompt)
            if distill_verdict == "block":
                assert distill_block is not None  # narrowed by the verdict
                print(json.dumps(distill_block))
                exit_code = _ATDD_PURE_BLOCK_EXIT_CODE
                return exit_code
            if distill_verdict == "allow":
                exit_code = 0
                return exit_code

            # U1 -- carpaccio entry gate as a PreToolUse intercept.
            # Runs before the classic service path. An atdd_pure dispatch is
            # recognised positively (M3); a defective marker set, a rejected
            # slice, or an out-of-order slice blocks; the entire branch is
            # fail-closed (M1) -- any exception inside it is surfaced as an
            # AtddPureHookInternalError block, never the bare exit-1 path.
            atdd_pure_block = _evaluate_u1_intercept(
                prompt, tool_input.get("subagent_type", "") or ""
            )
            if atdd_pure_block is not None:
                print(json.dumps(atdd_pure_block))
                exit_code = _ATDD_PURE_BLOCK_EXIT_CODE
                return exit_code

            # slice-07c (F3 NORMATIVO): this adapter is the composition seat of
            # the wave-entry lifecycle:
            #   peek_entry -> validate(wave_entering=...) -> clear-on-allow.
            # The service itself stays writer-free (§22.0: the veto path never
            # writes); a BLOCKED entry stays pending so the retry re-runs the
            # entry preconditions.
            activation = service_factory.create_wave_activation_service()
            wave_entering, entry_block = _peek_wave_entering(hook_input, activation)
            if entry_block is not None:
                print(json.dumps(entry_block))
                exit_code = _ATDD_PURE_BLOCK_EXIT_CODE
                return exit_code

            # slice-07d (F4 NORMATIVO): INFERRED fallback strand. No pending
            # entry (empty floor on a runtime whose submission anchor never
            # fired) + the dispatch DECLARES its wave -> arm INFERRED and
            # proceed as wave-entering in this SAME pass (self-entry). The
            # armed record is written BEFORE service.validate runs, so the
            # service's WaveActiveReader sees it in this same invocation
            # (read-after-write ordering). I3 + vocabulary validation live in
            # arm_inferred -- an armed floor or a garbage declaration leaves
            # everything untouched.
            if not wave_entering:
                wave_entering, fallback_block = _arm_inferred_fallback(
                    hook_input, prompt, activation
                )
                if fallback_block is not None:
                    print(json.dumps(fallback_block))
                    exit_code = _ATDD_PURE_BLOCK_EXIT_CODE
                    return exit_code
            # Resolve the project deliverable type (ADR-PST-001, feature
            # plugin-skill-deliverable-type) and thread it into the service so
            # the enforcement policy can exempt plugin/skill projects. This is
            # the handler SEAM the driving-adapter acceptance scenario drives.
            deliverable_type = _resolve_deliverable_type()

            # Delegate to application service
            service = service_factory.create_pre_tool_use_service(
                deliverable_type=deliverable_type
            )
            decision = service.validate(
                PreToolUseInput(
                    prompt=prompt,
                    subagent_type=tool_input.get("subagent_type"),
                    wave_entering=wave_entering,
                ),
                hook_id=hook_id,
            )

            # Translate HookDecision to protocol response
            if decision.action == "allow":
                if wave_entering:
                    # Clear-on-allow (NORMATIVE): the entry check ran and the
                    # gate allowed -- the flag clears, the wave stays armed.
                    try:
                        activation.clear_entry(Path.cwd())
                    except Exception as clear_exc:
                        _log_wave_entry_clear_failed(clear_exc, hook_id)
                # Create DES task signal if this is a DES-validated task
                if "DES-VALIDATION" in prompt:
                    # Extract step-id and project-id from DES markers
                    step_id_marker = ""
                    project_id_marker = ""
                    parser = DesMarkerParser()
                    markers = parser.parse(prompt)
                    if markers.step_id:
                        step_id_marker = markers.step_id
                    if markers.project_id:
                        project_id_marker = markers.project_id
                    task_correlation_id = des_task_signal.create_signal(
                        step_id=step_id_marker, project_id=project_id_marker
                    )
                exit_code = 0
                return exit_code
            else:
                recovery = decision.recovery_suggestions or []
                reason_with_recovery = decision.reason or "Validation failed"
                if recovery:
                    reason_with_recovery += "\n\nRecovery:\n" + "\n".join(
                        f"  {i + 1}. {s}" for i, s in enumerate(recovery)
                    )
                response = {
                    "decision": "block",
                    "reason": reason_with_recovery,
                }
                print(json.dumps(response))
                exit_code = decision.exit_code
                return exit_code

    except Exception as e:
        # Fail-closed: any error blocks execution
        stderr_capture = stderr_buffer.getvalue()[:STDERR_CAPTURE_MAX_CHARS]
        log_hook_error("pre_tool_use", e, stderr_capture)
        response = {"status": "error", "reason": f"Unexpected error: {e!s}"}
        print(json.dumps(response))
        exit_code = 1
        return exit_code
    finally:
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        decision_str = EXIT_CODE_TO_DECISION.get(exit_code, "error")
        log_hook_completed(
            hook_id=hook_id,
            handler="pre_tool_use",
            exit_code=exit_code,
            decision=decision_str,
            duration_ms=duration_ms,
            task_correlation_id=task_correlation_id,
        )
