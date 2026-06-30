"""Generic per-wave gate-stack dispatch support (f-declarative-gate-composition).

The SINGLE home for the select->iterate->carry mechanics the generic PreToolUse
(gate-IN) and SubagentStop (gate-OUT) handlers share when running a wave's
DECLARATIVE gate stack (``wave_gate_stacks.<wave>.{gate-in,gate-out}``).

The lift REUSES the existing flavor dispatcher: ``iterate_composition`` (the core
extracted from ``dispatch_lifecycle_event``) iterates a composition in declared
order, halts at the first ``on_failure: block`` veto, and parses each gate's
JSON-stdout ``recovery_suggestions`` into ``GateInvocationResult`` (OB-2 parity).
This module only provides:

  * the shipped-flavors-dir resolution (env override + package-anchored default,
    the same convention ``subagent_stop_handler`` uses);
  * the JSON-stdout shapes a per-wave gate emits (pass / veto / unknown-gate)
    so the generic iteration can carry the per-gate reason + recovery;
  * the select-then-iterate helper over an already-resolved stack.

The per-gate DECISION logic stays in the existing pure cores (``DiscussGateIn``
/ ``DiscussGateOut`` / ``DiscussReviewGate``) — this module never re-implements a
gate's correctness, only the wiring that makes the stack editable as data.

C9 / target-machine-agnosticism: Python + filesystem only, stdlib ``json`` +
``os``; the flavor read is the SSOT stdlib-only subset parser.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path

from des.application.flavor_dispatcher import (
    CompositionResult,
    iterate_composition,
    resolve_wave_gate_stack_from_registry,
)


# The active OSS flavor whose declarative wave gate stacks the spine reads. The
# wave gate stacks are an atdd_pure-flavor concern (classic declares none); the
# resolver returns the empty stack for any flavor without a declared block, so a
# fixed flavor here is the additive-coexistence reading (C8).
_ACTIVE_FLAVOR_ID = "atdd_pure"

# The shipped flavors dir the installed des package resolves as a sibling of
# lib/python (``Path(__file__).parents[3] / "nWave" / "flavors"``): in dev this
# is ``<repo>/nWave/flavors``; installed it is ``lib/nWave/flavors``. The
# ``NWAVE_FLAVORS_DIR`` env override mirrors ``subagent_stop_handler`` so tests
# and alternate layouts can redirect the lookup.
_SHIPPED_FLAVORS_DIR = Path(__file__).resolve().parents[3] / "nWave" / "flavors"

# The shipped wave-contract registry dir (ADR-FLOW-006 D6): the gate stack is
# authored ONCE per wave in ``nWave/waves/<wave>.yaml`` and the spine resolves it
# FROM that registry as the SOLE source (slice-06 MOVE-completion — the flavor-
# private ``wave_gate_stacks`` block is deleted). Same package-anchored default +
# ``NWAVE_WAVES_DIR`` env override convention as the flavors dir.
_SHIPPED_WAVES_DIR = Path(__file__).resolve().parents[3] / "nWave" / "waves"

# A per-wave gate invoker: (gate_id, context) -> (exit_code, json_stdout).
StackInvoker = Callable[[str, dict[str, str]], "tuple[int, str]"]


def shipped_flavors_dir() -> Path:
    """The shipped flavors dir: ``NWAVE_FLAVORS_DIR`` env, else package default."""
    return Path(os.environ.get("NWAVE_FLAVORS_DIR") or str(_SHIPPED_FLAVORS_DIR))


def shipped_waves_dir() -> Path:
    """The shipped wave-contract registry dir: ``NWAVE_WAVES_DIR`` env, else default."""
    return Path(os.environ.get("NWAVE_WAVES_DIR") or str(_SHIPPED_WAVES_DIR))


def resolve_stack(wave: str, boundary: str) -> list[dict[str, object]]:
    """Resolve the wave's declared gate stack for ``boundary`` FROM the registry.

    The canonical wave-contract registry (``nWave/waves/<wave>.yaml``) is the SOLE
    gate-stack source (ADR-FLOW-006 D6, slice-06 MOVE-completion). Behaviour is
    byte-identical to the retired flavor-private read: the rows were migrated
    verbatim; an absent registry / boundary returns the empty list (additive
    coexistence, C8).
    """
    return resolve_wave_gate_stack_from_registry(
        wave, boundary, waves_dir=shipped_waves_dir()
    )


def dispatch_wave_stack(
    stack: list[dict[str, object]],
    event_label: str,
    invoker: StackInvoker,
) -> CompositionResult:
    """Iterate an already-resolved wave gate stack via the EXISTING dispatcher.

    The resolved stack (the select step already happened) IS the composition the
    REUSED ``iterate_composition`` core drives — iterate-in-declared-order +
    halt-at-first-block + per-gate recovery parse, one iterator, no second
    implementation, no temp flavor file.
    """
    return iterate_composition(
        stack,
        event_id=event_label,
        flavor_id=_ACTIVE_FLAVOR_ID,
        context={},
        gate_invoker=invoker,
    )


def pass_stdout(gate_id: str) -> tuple[int, str]:
    """A gate's clean-pass JSON stdout: exit 0, no veto (Invariant 4)."""
    return 0, json.dumps({"verdict": "pass", "gate_id": gate_id})


def advisory_stdout(gate_id: str, *, reason: str, advice: list[str]) -> tuple[int, str]:
    """A gate's ADVISORY JSON stdout: exit 0 (non-blocking), verdict "advisory".

    A soft-gate signal -- the gate found a condition worth surfacing but does
    NOT hard-block (exit 0 -> the composition does not halt, Invariant 4: not an
    authorizing GO, just "no objection that blocks"). Distinct from
    ``pass_stdout`` (silent clean pass) so the advisory reason is carried.
    """
    return 0, json.dumps(
        {
            "verdict": "advisory",
            "gate_id": gate_id,
            "reason": reason,
            "recovery_suggestions": list(advice),
        }
    )


def veto_stdout(gate_id: str, *, reason: str, recovery: list[str]) -> tuple[int, str]:
    """A gate's veto JSON stdout: exit 1, carrying the specific reason + recovery."""
    return 1, json.dumps(
        {
            "verdict": "fail",
            "gate_id": gate_id,
            "reason": reason,
            "recovery_suggestions": list(recovery),
        }
    )


def unknown_gate_stdout(gate_id: str) -> tuple[int, str]:
    """An uncatalogued gate's fail-closed JSON stdout, named (C6).

    Reuses the ``_gate_invoker_for`` fail-closed shape
    (``carpaccio_intercept.py``): a declared-but-uncatalogued gate_id is a
    declaration defect refused LOUD, named — never a silent skip.
    """
    return 1, json.dumps(
        {
            "event": "UnknownGateOnDispatchPre",
            "gate_id": gate_id,
            "reason": (
                f"UNKNOWN_GATE: the declared gate_id {gate_id!r} is not in the "
                "gate catalog -- a typo'd gate-id is refused fail-closed, never "
                "a silent enforcement skip"
            ),
            "recovery_suggestions": [
                f"The declared gate_id {gate_id!r} is not a catalog gate -- fix "
                "the typo in the wave_gate_stacks composition so it names a gate "
                "from nWave/gates/_catalog.yaml.",
            ],
        }
    )


def reason_from_stdout(stdout: str, gate_id: str) -> str:
    """Extract the gate's specific veto ``reason`` from its JSON stdout.

    Fail-closed to a generic-but-named reason when the stdout is non-JSON or
    carries no ``reason`` field (the gate still vetoed; we never invent a clean
    pass).
    """
    if stdout.strip():
        try:
            payload = json.loads(stdout)
        except (json.JSONDecodeError, ValueError):
            payload = None
        if isinstance(payload, dict):
            reason = payload.get("reason")
            if isinstance(reason, str) and reason:
                return reason
    return f"GATE_BLOCKED: the gate {gate_id!r} vetoed the dispatch"
