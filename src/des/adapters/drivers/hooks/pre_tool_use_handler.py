"""PreToolUse handler — validates Task/Agent tool invocations.

Translates Claude Code's PreToolUse hook event (JSON stdin) into
PreToolUseService decisions (allow/block), manages DES task signal creation,
and emits audit events through hook_protocol.

Extracted from claude_code_hook_adapter.py as part of P4 decomposition.

The U1 carpaccio entry-gate intercept that used to run here is gone: a dispatch
is no longer refused by a hook for slice order, readiness, or marker
completeness. Reuse, architecture conformance and AT-first are practices carried
in the dispatch itself, not preconditions a hook re-litigates.
"""

import contextlib
import io
import json
import time
import uuid
from pathlib import Path

from des.adapters.driven.time.system_time import SystemTimeProvider
from des.adapters.drivers.hooks import des_task_signal, hook_protocol, service_factory
from des.adapters.drivers.hooks.bash_command_guards import (
    evaluate_git_stash_command,
    evaluate_worktree_remove_command,
    git_stash_guard_target_root,
    worktree_guard_target_root,
    write_bash_guard_audit_event,
)
from des.adapters.drivers.hooks.hook_protocol import (
    EXIT_CODE_TO_DECISION,
    STDERR_CAPTURE_MAX_CHARS,
    extract_transcript_path,
    log_hook_completed,
    log_hook_error,
    log_hook_invoked,
    read_and_parse_stdin,
)
from des.adapters.drivers.hooks.root_activation_context import (
    build_root_mode_select_context,
)
from des.application.commit_attribution_service import CommitAttributionService
from des.application.skill_tracking_service import mode_select_observed_before_mutation
from des.application.wave_activation_service import WaveActivationService
from des.domain.atdd_pure_phases import ATDDPurePhase
from des.domain.des_marker_parser import DesMarkerParser
from des.domain.nwave_root import resolve_nwave_root
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


def _classic_mode_removed_payload() -> dict[str, object]:
    """Closed public refusal for a retired workflow carrier."""
    return {
        "outcome": "CLASSIC_MODE_REMOVED",
        "reason_code": "MIGRATION_REQUIRED",
        "effective_mode": None,
        "diagnostic": (
            "WHAT: the dispatch requested the retired classic spine. "
            "WHY: classic is no longer executable. "
            "HOW: migrate or repair the dispatch to explicit atdd_pure."
        ),
    }


def _classic_prompt_refusal(prompt: str) -> dict[str, object] | None:
    """Refuse a direct legacy carrier before any service or hook mutation."""
    if DesMarkerParser().parse(prompt).mode == "classic":
        return _classic_mode_removed_payload()
    return None


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
      * ("not_distill", None) -- not a D_DISTILL dispatch -- the retired path and
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
    peeked = activation.peek_entry(resolve_nwave_root())
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
    armed = activation.arm_inferred(resolve_nwave_root(), declared_wave)
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


def emit_commit_attribution_mutation(
    tool_input: dict[str, object], *, cwd: Path | None = None
) -> int | None:
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
        cwd: Optional working directory for attribution config resolution.

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
        from des.adapters.driven.config.des_config import DESConfig

        config = DESConfig(
            cwd=cwd or Path.cwd(),
            global_config_path=Path.home() / ".nwave" / "global-config.json",
        )
        if not config.attribution_enabled:
            return None

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


def evaluate_bash_safety_guards(
    hook_input: dict[str, object], tool_input: dict[str, object]
) -> dict[str, str] | None:
    """The git-stash + worktree-remove Bash guard decisions (consolidated).

    Formerly two standalone PreToolUse/Bash hook registrations
    (`scripts/hooks/git_stash_guard.py`, `scripts/hooks/worktree_removal_guard.py`).
    The single decision authority is `des.adapters.drivers.hooks.bash_command_guards`
    (`evaluate_git_stash_command` / `evaluate_worktree_remove_command`); this
    function is one envelope-parsing wrapper around it. The standalone scripts
    call the shared predicate authority directly (their own CLI envelope
    shape), NOT necessarily this helper. `hook_router.main()` calls THIS
    helper by name, once, BEFORE `activation_gate.apply_gate` (ADR-AG-001
    ordering repair), so an inactive project cannot exit 0 past a live
    stash/worktree mutation -- see the router's pre-activation call site for
    the ordering contract. Returns a `{decision: block, reason: ...}` payload,
    or `None` to allow (paying no triage/filesystem work when neither guard's
    command shape matched).
    """
    command = tool_input.get("command")
    if not isinstance(command, str) or not command:
        return None

    stash_decision = evaluate_git_stash_command(command)
    if stash_decision is not None:
        if stash_decision.audit_event is not None:
            write_bash_guard_audit_event(
                git_stash_guard_target_root(),
                stash_decision.audit_event,
                {
                    **(stash_decision.audit_data or {}),
                    "session_id": str(hook_input.get("session_id", "")),
                },
            )
        if not stash_decision.allow:
            return {"decision": "block", "reason": stash_decision.reason or ""}
        return None

    repo = Path(str(hook_input.get("cwd") or Path.cwd()))
    worktree_decision = evaluate_worktree_remove_command(command, repo)
    if worktree_decision is not None:
        if worktree_decision.audit_event is not None:
            write_bash_guard_audit_event(
                worktree_guard_target_root(),
                worktree_decision.audit_event,
                {
                    **(worktree_decision.audit_data or {}),
                    "session_id": str(hook_input.get("session_id", "")),
                },
            )
        if not worktree_decision.allow:
            return {"decision": "block", "reason": worktree_decision.reason or ""}
        return None

    return None


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

            if hook_input.get("tool_name") == "Bash":
                # The git-stash / worktree-remove safety decision already ran
                # once, pre-activation, in `hook_router.main()` (before
                # `apply_gate`) -- see `evaluate_bash_safety_guards`. Do not
                # re-run it here; that would be a duplicate second evaluation
                # of the same command on the active path.
                if (
                    not hook_input.get("agent_id")
                    and not hook_input.get("agent_type")
                    and not des_task_signal.DES_DELIVER_SESSION_FILE.exists()
                ):
                    transcript_path = extract_transcript_path(hook_input)
                    observed = False
                    try:
                        observed = bool(
                            transcript_path
                            and mode_select_observed_before_mutation(transcript_path)
                        )
                    except Exception:
                        observed = False
                    if not observed:
                        print(
                            json.dumps(
                                {
                                    "decision": "block",
                                    "reason": (
                                        "Invoke nw-mode-select before the "
                                        "first Bash/Write/Edit."
                                    ),
                                }
                            )
                        )
                        exit_code = 2
                        return exit_code

                mutation_cwd = None
                if isinstance(hook_input.get("cwd"), str):
                    cwd_str = hook_input.get("cwd")
                    if cwd_str:
                        mutation_cwd = Path(cwd_str)
                mutation_exit = emit_commit_attribution_mutation(
                    tool_input, cwd=mutation_cwd
                )
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

            classic_refusal = _classic_prompt_refusal(prompt)
            if classic_refusal is not None:
                print(json.dumps(classic_refusal))
                exit_code = _ATDD_PURE_BLOCK_EXIT_CODE
                return exit_code

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
                # G-DISTILL-PRE short-circuits ONLY the classic template-
                # validation service call below (its declared intent, see the
                # comment above) -- it must NOT also short-circuit the
                # wave-entering peek/clear-on-allow lifecycle that every other
                # ALLOW path honours (slice-07c F3 NORMATIVO). Skipping it here
                # left `entry_pending` stuck True, leaking into whatever
                # dispatch ran next.
                distill_activation = service_factory.create_wave_activation_service()
                distill_wave_entering, distill_entry_block = _peek_wave_entering(
                    hook_input, distill_activation
                )
                if distill_entry_block is not None:
                    print(json.dumps(distill_entry_block))
                    exit_code = _ATDD_PURE_BLOCK_EXIT_CODE
                    return exit_code
                if distill_wave_entering:
                    try:
                        distill_activation.clear_entry(resolve_nwave_root())
                    except Exception as clear_exc:
                        _log_wave_entry_clear_failed(clear_exc, hook_id)
                exit_code = 0
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
                        activation.clear_entry(resolve_nwave_root())
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
                # GDP-6 (degrade-LOUD, never silent-wrong): an allow decision
                # normally prints nothing (silence IS the signal, exit 0). A
                # decision carrying a ``warning`` chose NOT to veto something it
                # noticed (e.g. an expired-INFERRED wave floor) -- print it via
                # the SAME allow-with-message protocol shape
                # ``emit_commit_attribution_mutation`` already uses above, so
                # the operator sees WHY the dispatch went through instead of
                # mistaking silence for "nothing happened".
                if decision.warning:
                    print(
                        json.dumps(
                            {
                                "hookSpecificOutput": {
                                    "hookEventName": "PreToolUse",
                                    "permissionDecision": "allow",
                                    "permissionDecisionReason": decision.warning,
                                }
                            }
                        )
                    )
                else:
                    # K3-A root activation: the root/orchestrator never gets a
                    # SubagentStart event (only spawned sub-agents do), so this
                    # is the one already-registered, already-executed hook that
                    # fires in root's own process at dispatch time. Best-effort,
                    # never changes the allow decision above.
                    root_context = build_root_mode_select_context(
                        prompt=prompt,
                        subagent_type=tool_input.get("subagent_type"),
                    )
                    if root_context:
                        print(
                            json.dumps(
                                {
                                    "hookSpecificOutput": {
                                        "hookEventName": "PreToolUse",
                                        "permissionDecision": "allow",
                                        # D2: permissionDecisionReason explains
                                        # a permission decision; the installed
                                        # runtime's own hook doc (Claude Code
                                        # 2.1.224) documents only
                                        # additionalContext as "Text injected
                                        # into model context" -- that is the
                                        # channel the reminder must use to be
                                        # seen at all.
                                        "additionalContext": root_context,
                                    }
                                }
                            )
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
