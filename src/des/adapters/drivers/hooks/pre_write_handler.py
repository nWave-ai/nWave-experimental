"""PreWrite/PreEdit handler — guards source file writes during deliver sessions.

The shell fast-path tests for deliver-session.json BEFORE invoking Python.
This handler only runs during active deliver sessions.

Extracted from claude_code_hook_adapter.py as part of P4 decomposition.
"""

import contextlib
import io
import json
import os
import subprocess
import time
import uuid
from pathlib import Path

from des.adapters.driven.time.system_time import SystemTimeProvider
from des.adapters.drivers.hooks import des_task_signal, hook_protocol
from des.adapters.drivers.hooks.hook_protocol import (
    EXIT_CODE_TO_DECISION,
    STDERR_CAPTURE_MAX_CHARS,
    log_hook_completed,
    log_hook_error,
    log_hook_invoked,
    read_and_parse_stdin,
)
from des.domain.session_guard_policy import SessionGuardPolicy
from des.ports.driven_ports.audit_log_writer import AuditEvent
from des.runtime.interpreter import des_spawn


def _log_pre_write_decision(
    hook_id: str,
    event_type: str,
    file_path: str,
    reason: str,
) -> None:
    """Log a HOOK_PRE_WRITE_ALLOWED or HOOK_PRE_WRITE_BLOCKED diagnostic event."""
    try:
        audit_writer = hook_protocol.get_audit_writer()
        audit_writer.log_event(
            AuditEvent(
                event_type=event_type,
                timestamp=SystemTimeProvider().now_utc().isoformat(),
                data={
                    "hook_id": hook_id,
                    "file_path": file_path,
                    "reason": reason,
                },
            )
        )
    except Exception:
        pass  # Diagnostic logging must never break the hook


# --- Skill-normative gate intercept (ADR-SNCG-002 §Placement rule, H-1) ----

_SKILLS_TREE_PARTS = ("nWave", "skills")
_SKILL_GATE_MODULE = "des.cli.skill_normative_gate"
_SKILL_GATE_TIMEOUT_S = 30
_SKILL_GATE_FAULT_ENV = "NWAVE_SKILL_GATE_INJECT_FAULT"


def _is_skill_tree_path(file_path: str) -> bool:
    """True iff the edited path lies under the `nWave/skills/**` tree."""
    parts = Path(file_path).parts
    return any(parts[i : i + 2] == _SKILLS_TREE_PARTS for i in range(len(parts) - 1))


def _run_skill_gate_subprocess() -> subprocess.CompletedProcess[str]:
    """Run `des skill-normative-gate` over the repo; return the completed process.

    Fail-stuck (timeout / signal-kill) maps to a non-zero exit (block) per the
    ADR-030 D5 discipline. Honours `NWAVE_SKILL_GATE_INJECT_FAULT` so the AC-07
    fault-injection AT can force the spawn to raise and prove the local
    fail-closed except-arm is reached.

    Returns the full ``CompletedProcess`` (not just the exit code): the gate's
    stdout NAMES the failing/indeterminate clause(s) (`skill_normative_gate.py`
    `_render`), and the caller must be able to propagate that fact into the
    block reason rather than discard it (GDP-3 — the fact is already in scope).
    """
    if os.environ.get(_SKILL_GATE_FAULT_ENV) == "1":
        raise RuntimeError("forced gate-subprocess spawn failure (fault injection)")
    return des_spawn(
        None,
        _SKILL_GATE_MODULE,
        capture_output=True,
        text=True,
        timeout=_SKILL_GATE_TIMEOUT_S,
    )


#: The gate's own exit codes (`des.domain.gate_outcome._EXIT_BY_VERDICT`) name
#: TWO distinct verdict classes that both count as "non-zero" here: FAIL (1,
#: a REAL violation) and INDETERMINATE (4, a could-not-verify claim the
#: gate's own ratchet -- gate-ratchet-skill-normative -- refused to allow).
#: Collapsing both into one "vetoed" reason lost the GDP-8 third state at
#: this aggregate: an operator reading the block could not tell a real defect
#: from a could-not-verify without re-running the gate by hand.
_GATE_EXIT_KIND: dict[int, str] = {
    1: "a REAL violation (FAIL)",
    4: (
        "a COULD-NOT-VERIFY finding this edit did not clear "
        "(INDETERMINATE, ratchet-refused)"
    ),
}


def _gate_exit_kind(returncode: int) -> str:
    """Name which verdict class a non-zero gate exit code belongs to."""
    return _GATE_EXIT_KIND.get(returncode, f"an unrecognised exit ({returncode})")


def _evaluate_skill_normative_intercept(file_path: str) -> dict[str, str] | None:
    """Guard a skill-tree edit, fail-closed (ADR-SNCG-002 §Placement rule, H-1).

    Returns the `{decision:block}` body when the edit must be blocked, or None
    when it is allowed / is not a `nWave/skills/**` edit. The body is wrapped in
    its OWN try/except so a gate-subprocess spawn failure degrades LOUD to a
    block — making the outer `handle_pre_write` fail-OPEN catch-all unreachable
    from this intercept (no-silent-pass).

    The block reason propagates the gate subprocess's own stdout (capped at
    `STDERR_CAPTURE_MAX_CHARS`, the file's established truncation convention):
    the subprocess already names the violated clause(s) before this function
    ever sees the exit code, so reporting only "gate exit N" would silently
    drop a fact already in hand -- an operator would have to re-run
    `des skill-normative-gate` by hand to learn what this call already knew.
    The reason also NAMES which verdict class the exit code belongs to
    (`_gate_exit_kind`) -- FAIL vs INDETERMINATE -- never just the bare code;
    this intercept still blocks on BOTH, unconditionally propagating whatever
    exit code the gate itself decided (the gate now owns the ratchet decision
    on the INDETERMINATE delta; this intercept never second-guesses it).
    """
    if not file_path or not _is_skill_tree_path(file_path):
        return None
    try:
        completed = _run_skill_gate_subprocess()
        if completed.returncode != 0:
            gate_output = (completed.stdout or "").strip()
            kind = _gate_exit_kind(completed.returncode)
            return {
                "decision": "block",
                "reason": (
                    f"skill-normative gate vetoed the skill edit — {kind} "
                    f"(gate exit {completed.returncode}): "
                    f"{gate_output[:STDERR_CAPTURE_MAX_CHARS]}"
                    if gate_output
                    else f"skill-normative gate vetoed the skill edit — {kind} "
                    f"(gate exit {completed.returncode}, no gate output captured)"
                ),
            }
        return None
    except Exception as exc:
        return {
            "decision": "block",
            "reason": f"skill-normative-gate intercept error: {exc!s}",
        }


def handle_pre_write() -> int:
    """Handle PreToolUse for Write/Edit: guard source writes during deliver.

    Shell fast-path: the hook command tests for deliver-session.json BEFORE
    invoking Python. This handler only runs during active deliver sessions.

    Returns:
        0 if write is allowed
        2 if write is blocked (source file during deliver without DES task)
    """
    hook_id = str(uuid.uuid4())
    start_ns = time.perf_counter_ns()
    exit_code = 0
    stderr_buffer = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr_buffer):
            stdin_result = read_and_parse_stdin(
                "pre_write",
                json_error_fallback="allow",
            )

            if stdin_result.is_empty:
                return 0

            if stdin_result.parse_error:
                # Write/Edit fails open on parse errors
                return 0

            hook_input = stdin_result.hook_input

            # Extract file path from tool_input
            tool_input = hook_input.get("tool_input", {})
            file_path = tool_input.get("file_path", "")

            # --- Skill-normative gate intercept (ADR-SNCG-002 §Placement) ---
            skill_block = _evaluate_skill_normative_intercept(file_path)
            if skill_block is not None:
                _log_pre_write_decision(
                    hook_id=hook_id,
                    event_type="HOOK_PRE_WRITE_BLOCKED",
                    file_path=file_path,
                    reason=skill_block["reason"],
                )
                print(json.dumps(skill_block))
                exit_code = 2
                return exit_code

            # --- Execution log guard: always block direct writes ---
            if file_path and file_path.endswith("execution-log.json"):
                block_reason = (
                    "execution-log.json belongs to a retired workflow and cannot be "
                    "created or modified.\n\n"
                    "Use the current atdd_pure delivery inputs: the selected feature "
                    "delta and its acceptance tests. Do not recreate retired phase records."
                )
                _log_pre_write_decision(
                    hook_id=hook_id,
                    event_type="HOOK_PRE_WRITE_BLOCKED",
                    file_path=file_path,
                    reason="execution_log_direct_write",
                )
                print(json.dumps({"decision": "block", "reason": block_reason}))
                return 2

            # Check session and signal state
            session_active = des_task_signal.DES_DELIVER_SESSION_FILE.exists()
            des_task_active = des_task_signal.DES_TASK_ACTIVE_FILE.exists()

            # Diagnostic: confirm hook was invoked with full context
            log_hook_invoked(
                "pre_write",
                {
                    "file_path": file_path,
                    "session_active": session_active,
                    "des_task_active": des_task_active,
                },
                hook_id=hook_id,
            )

            policy = SessionGuardPolicy()
            guard_result = policy.check(
                file_path=file_path,
                session_active=session_active,
                des_task_active=des_task_active,
            )

            if guard_result.blocked:
                _log_pre_write_decision(
                    hook_id=hook_id,
                    event_type="HOOK_PRE_WRITE_BLOCKED",
                    file_path=file_path,
                    reason=guard_result.reason or "Source write blocked during deliver",
                )
                response = {
                    "decision": "block",
                    "reason": guard_result.reason
                    or "Source write blocked during deliver",
                }
                print(json.dumps(response))
                exit_code = 2
                return exit_code
            else:
                # Determine allow reason for diagnostics
                allow_reason = "no_session" if not session_active else "policy_allowed"
                _log_pre_write_decision(
                    hook_id=hook_id,
                    event_type="HOOK_PRE_WRITE_ALLOWED",
                    file_path=file_path,
                    reason=allow_reason,
                )
                exit_code = 0
                return exit_code

    except Exception as e:
        # Fail-open for Write/Edit (unlike Task which is fail-closed)
        stderr_capture = stderr_buffer.getvalue()[:STDERR_CAPTURE_MAX_CHARS]
        log_hook_error(
            "pre_write",
            e,
            stderr_capture,
        )
        exit_code = 0
        return exit_code
    finally:
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        decision_str = EXIT_CODE_TO_DECISION.get(exit_code, "error")
        log_hook_completed(
            hook_id=hook_id,
            handler="pre_write",
            exit_code=exit_code,
            decision=decision_str,
            duration_ms=duration_ms,
        )
