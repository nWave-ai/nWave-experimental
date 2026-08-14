"""Activation gate for hook_router.main() (ADR-AG-001).

The gate sits at the single hook dispatch point: buffer stdin, parse ``cwd``,
re-inject via ``io.StringIO`` (DDD-6), dispatch when active, else allow/exit-0
when inactive — NEVER exit-2 from the gate. Fail-open: empty / invalid-JSON /
missing-``cwd`` stdin resolves normally (defaults to inactive under opt-in)
and exits 0; the gate never raises.

Activation is never mutated by a hook. The only writer of the per-project
marker is the explicit ``nwave-ai project enable`` CLI verb.

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

from des.domain.nwave_root import resolve_nwave_root


class GateOutcome(Enum):
    """What the gate did with a hook invocation (production-side)."""

    ALLOWED_EXIT_0 = "allowed-exit-0"  # inactive -> sys.exit(0), handler skipped
    DISPATCHED = "dispatched"  # active -> handler runs


@dataclass(frozen=True)
class GateRun:
    """Observable result of one gated hook dispatch (port-exposed)."""

    gate_outcome: GateOutcome
    handler_stdin: str | None  # bytes the handler actually read (rewind proof)
    exit_code: int


def run_gate(*, envelope: Any, project_root: Path, global_config_path: Path) -> GateRun:
    """Run the activation gate over one hook envelope.

    Args:
        envelope: a hook envelope exposing ``raw`` (the literal stdin, or None).
        project_root: resolved project root sandbox.
        global_config_path: sandbox global-config path.

    Returns:
        ``GateRun`` with the observable gate outcome, the handler's stdin view
        (byte-identical to what the gate buffered), and the exit code (always 0;
        never 2 from the gate).
    """
    handler_stdin = envelope.raw  # buffered stdin, re-injected verbatim (DDD-6)

    if _is_active(project_root, global_config_path):
        return GateRun(GateOutcome.DISPATCHED, handler_stdin, 0)

    return GateRun(GateOutcome.ALLOWED_EXIT_0, handler_stdin, 0)


def apply_gate(command: str, stdin_text: str) -> str | None:
    """Production gate over real stdin for ``hook_router.main()``.

    Returns the re-injectable stdin text when the command should dispatch (the
    caller re-injects it as ``sys.stdin`` and runs the handler), or calls
    ``sys.exit(0)`` when the project is inactive (allow without blocking).
    Fail-open: any read/parse problem resolves to inactive under the default
    and exits 0.
    """
    # Missing/invalid cwd in the envelope falls back to the process cwd (Claude
    # Code always invokes hooks inside the project dir); resolution then runs
    # normally and only silences genuinely inactive projects.
    project_root = _parse_cwd(stdin_text) or resolve_nwave_root()
    if _is_active_or_inactive_on_error(project_root):
        return stdin_text

    sys.exit(0)


# ---------------------------------------------------------------------------
# helpers (no test-domain imports; duck-typed envelope access)
# ---------------------------------------------------------------------------


def _is_active(project_root: Path, global_config_path: Path) -> bool:
    from des.adapters.driven.config.des_config import DESConfig
    from des.domain.activation_policy import resolve_activation

    config = DESConfig(cwd=project_root, global_config_path=global_config_path)
    return resolve_activation(config.enabled_for_repo, config.activation_mode)


def _is_active_or_inactive_on_error(project_root: Path) -> bool:
    """Resolve activation without letting an I/O fault activate a project.

    The gate must never raise or block. If activation cannot be resolved, the
    non-invasive result is inactive: exit zero without running a mutating
    handler.
    """
    try:
        return _is_active(project_root, _global_config_path())
    except Exception:
        return False


def _parse_cwd(stdin_text: str) -> Path | None:
    try:
        data = json.loads(stdin_text)
    except (json.JSONDecodeError, TypeError):
        return None
    cwd = data.get("cwd") if isinstance(data, dict) else None
    return Path(cwd) if cwd else None


def _global_config_path() -> Path:
    return Path.home() / ".nwave" / "global-config.json"


def reinject_stdin(stdin_text: str) -> io.StringIO:
    """Wrap buffered stdin text so a handler can read it verbatim (DDD-6)."""
    return io.StringIO(stdin_text)
