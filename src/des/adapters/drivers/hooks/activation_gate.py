"""Activation gate for hook_router.main() (ADR-AG-001).

The gate sits at the single hook dispatch point: buffer stdin, parse ``cwd``,
re-inject via ``io.StringIO`` (DDD-6), exempt SessionStart (DDD-5),
adopt-and-proceed on pre-task ``nw-*`` dispatch (DDD-9), else allow/exit-0
when inactive — NEVER exit-2 from the gate. On an inactive project,
``user-prompt-submit`` additionally fires ONLY the hourly
orchestrator-affordance session-hygiene refresh directly before exiting
(mirrors SessionStart's own injection, ``orchestrator-affordance-hourly-refresh``)
without ever dispatching the full handler — so the wave-active anchor's
``arm()`` write stays gated on the project's own activation resolution
(deep-review finding, DDD-9). Fail-open: empty / invalid-JSON / missing-``cwd``
stdin resolves normally (defaults to inactive under opt-in) and exits 0; the
gate never raises.

``run_gate`` is the testable seam the acceptance composition drives. It returns
a ``GateRun`` recording the observable outcome, the bytes the handler saw (the
rewind contract), and the exit code. ``apply_gate`` is the production call path
used by ``hook_router.main()`` over the real ``sys.stdin`` / ``sys.exit``.
"""

from __future__ import annotations

import io
import json
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class GateOutcome(Enum):
    """What the gate did with a hook invocation (production-side)."""

    ALLOWED_EXIT_0 = "allowed-exit-0"  # inactive -> sys.exit(0), handler skipped
    DISPATCHED = "dispatched"  # active (or exempt) -> handler runs
    ADOPTED_AND_DISPATCHED = "adopted-and-dispatched"  # pre-task detect-and-adopt


_SESSION_START = "session-start"
_USER_PROMPT_SUBMIT = "user-prompt-submit"
# Commands exempt from activation gating entirely — dispatched unconditionally,
# regardless of the project's active/inactive resolution. SessionStart adopts
# existing projects silently (DDD-5). UserPromptSubmit is intentionally NOT
# exempt (deep-review finding, scope-creep DDD-9, reloop after the round-2
# EXAMINE fix): an unconditional exemption freed the ENTIRE
# handle_user_prompt_submit dispatch on an inactive project -- including
# CommandLiteralWaveActiveAnchor.on_prompt_submitted's arm() write, which has
# no activation check of its own -- bypassing the controlled adoption path.
# Instead, on an inactive project, apply_gate fires ONLY the hourly
# orchestrator-affordance session-hygiene refresh directly (see the
# ``_USER_PROMPT_SUBMIT`` branch below) and never reaches the full handler,
# so the wave-active anchor stays exactly as gated as it was before the
# refresh feature existed.
_ACTIVATION_EXEMPT_COMMANDS = (_SESSION_START,)
_PRE_TASK_COMMANDS = ("pre-task", "pre-tool-use")
_NW_AGENT_PREFIX = "nw-"


@dataclass(frozen=True)
class GateRun:
    """Observable result of one gated hook dispatch (port-exposed)."""

    gate_outcome: GateOutcome
    handler_stdin: str | None  # bytes the handler actually read (rewind proof)
    exit_code: int


def run_gate(*, envelope: Any, project_root: Path, global_config_path: Path) -> GateRun:
    """Run the activation gate over one hook envelope.

    Args:
        envelope: a hook envelope exposing ``command`` (with ``.value``),
            ``cwd``, ``subagent_type``, and ``raw`` (the literal stdin, or None).
        project_root: resolved project root sandbox.
        global_config_path: sandbox global-config path.

    Returns:
        ``GateRun`` with the observable gate outcome, the handler's stdin view
        (byte-identical to what the gate buffered), and the exit code (always 0;
        never 2 from the gate).
    """
    handler_stdin = envelope.raw  # buffered stdin, re-injected verbatim (DDD-6)
    command = _command_token(envelope)

    if command in _ACTIVATION_EXEMPT_COMMANDS:
        return GateRun(GateOutcome.DISPATCHED, handler_stdin, 0)

    if _is_active(project_root, global_config_path):
        return GateRun(GateOutcome.DISPATCHED, handler_stdin, 0)

    if _is_nw_agent_dispatch(envelope, command):
        _adopt(project_root)
        return GateRun(GateOutcome.ADOPTED_AND_DISPATCHED, handler_stdin, 0)

    return GateRun(GateOutcome.ALLOWED_EXIT_0, handler_stdin, 0)


def apply_gate(command: str, stdin_text: str) -> str | None:
    """Production gate over real stdin for ``hook_router.main()``.

    Returns the re-injectable stdin text when the command should dispatch (the
    caller re-injects it as ``sys.stdin`` and runs the handler), or calls
    ``sys.exit(0)`` when the project is inactive (allow without blocking).
    SessionStart and UserPromptSubmit are always dispatched (the latter for its
    session-hygiene hourly affordance refresh, gated internally on its own
    sentinel — not on activation). Fail-open: any read/parse problem resolves
    to inactive under the default and exits 0.
    """
    if command in _ACTIVATION_EXEMPT_COMMANDS:
        return stdin_text

    # Missing/invalid cwd in the envelope falls back to the process cwd (Claude
    # Code always invokes hooks inside the project dir); resolution then runs
    # normally and only silences genuinely inactive projects.
    project_root = _parse_cwd(stdin_text) or Path.cwd()
    if _is_active_failopen(project_root):
        return stdin_text

    if command in _PRE_TASK_COMMANDS and _stdin_is_nw_agent(stdin_text):
        _adopt(project_root)
        return stdin_text

    if command == _USER_PROMPT_SUBMIT:
        _refresh_orchestrator_affordance_only(project_root)

    sys.exit(0)


# ---------------------------------------------------------------------------
# helpers (no test-domain imports; duck-typed envelope access)
# ---------------------------------------------------------------------------


def _command_token(envelope: Any) -> str:
    command = envelope.command
    return command.value if hasattr(command, "value") else str(command)


def _is_active(project_root: Path, global_config_path: Path) -> bool:
    from des.adapters.driven.config.des_config import DESConfig
    from des.domain.activation_policy import resolve_activation

    config = DESConfig(cwd=project_root, global_config_path=global_config_path)
    return resolve_activation(config.enabled_for_repo, config.activation_mode)


def _is_active_failopen(project_root: Path) -> bool:
    """Resolve activation for the production gate, failing open to active.

    The gate must NEVER raise. If activation cannot be resolved (corrupt config,
    unexpected I/O error), default to active so the existing handler runs — the
    gate only silences a project it can positively resolve as inactive.
    """
    try:
        return _is_active(project_root, _global_config_path())
    except Exception:
        return True


def _is_nw_agent_dispatch(envelope: Any, command: str) -> bool:
    if command not in _PRE_TASK_COMMANDS:
        return False
    subagent = getattr(envelope, "subagent_type", None)
    return bool(subagent) and str(subagent).startswith(_NW_AGENT_PREFIX)


def _refresh_orchestrator_affordance_only(project_root: Path) -> None:
    """Fire ONLY the hourly orchestrator-affordance refresh for an inactive
    project's ``user-prompt-submit`` -- without dispatching the full handler,
    and therefore without ever reaching
    ``CommandLiteralWaveActiveAnchor.on_prompt_submitted`` / its ``arm()``
    write (deep-review finding, DDD-9: that write stays gated on the
    project's own activation resolution, unaffected by this refresh path).
    Mirrors SessionStart's own activation exemption for the refresh content
    only, never for the wave-active anchor.
    """
    from des.adapters.drivers.hooks.user_prompt_submit_handler import (
        _maybe_refresh_orchestrator_affordance,
    )

    _maybe_refresh_orchestrator_affordance(project_root)


def _adopt(project_root: Path) -> None:
    from des.application.auto_marking_service import (
        AdoptionTrigger,
        AutoMarkingService,
    )

    AutoMarkingService().adopt_if_warranted(
        project_root=project_root, trigger=AdoptionTrigger.REAL_FEATURE_USE
    )


def _parse_cwd(stdin_text: str) -> Path | None:
    try:
        data = json.loads(stdin_text)
    except (json.JSONDecodeError, TypeError):
        return None
    cwd = data.get("cwd") if isinstance(data, dict) else None
    return Path(cwd) if cwd else None


def _stdin_is_nw_agent(stdin_text: str) -> bool:
    try:
        data = json.loads(stdin_text)
    except (json.JSONDecodeError, TypeError):
        return False
    subagent = data.get("subagent_type") if isinstance(data, dict) else None
    return bool(subagent) and str(subagent).startswith(_NW_AGENT_PREFIX)


def _global_config_path() -> Path:
    return Path.home() / ".nwave" / "global-config.json"


def reinject_stdin(stdin_text: str) -> io.StringIO:
    """Wrap buffered stdin text so a handler can read it verbatim (DDD-6)."""
    return io.StringIO(stdin_text)
