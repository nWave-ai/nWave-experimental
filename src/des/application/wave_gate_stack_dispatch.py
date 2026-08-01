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
from dataclasses import dataclass
from pathlib import Path

from des.application.flavor_dispatcher import (
    CompositionResult,
    iterate_composition,
    resolve_wave_gate_stack_from_registry,
)
from des.runtime.packaged_asset import (
    AssetOrigin,
    AssetResolution,
    resolve_packaged_asset,
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


@dataclass(frozen=True)
class StackResolution:
    """The resolved gate-stack rows for one wave/boundary (RCA §6.3
    illustrative shape, GDP-8 arity corollary).

    Deliberately NOT ``list``-compatible: an earlier ``list`` subclass made an
    INDETERMINATE resolution falsy AND equal to ``[]`` (``bool(r) is False``,
    ``r == []``), so a caller that merely tested truthiness or emptiness --
    exactly the ``if not stack: return None`` shape that caused this bug --
    would silently re-collapse the third state into "nothing to enforce". A
    frozen dataclass with an explicit ``rows`` field makes that collapse
    IMPOSSIBLE: there is no bare-list value to be falsy or equal to ``[]``
    against, so every caller MUST name ``.rows`` / ``.indeterminate``
    explicitly, and an unmigrated caller fails at authoring time (a
    ``TypeError``/``AttributeError`` on first use, GDP-1 -- not a silent pass).

    ``.rows`` may be LEGITIMATELY empty (RCA §3: an absent registry file, an
    absent ``gate_stack`` block, an absent boundary sub-key, or an explicit
    ``[]`` declaration -- ``.indeterminate`` stays ``None`` in every one of
    those cases). ``.indeterminate``, when set, carries a WHAT/WHY/HOW message
    naming the registry directory that could not be read at all -- the
    discriminant is directory-level usability, never row count.
    """

    rows: list[dict[str, object]]
    indeterminate: str | None = None


def _override_resolution(raw: str) -> AssetResolution:
    """Classify an explicit ``NWAVE_WAVES_DIR`` override -- highest precedence.

    An explicit override always names an intended location: unlike the default
    package-anchored path, a non-existent override is NEVER "declared N/A" --
    it is always a defect (RCA §6.2, GDP-4: the HOW must invoke a REAL lever,
    so the lever must actually be honoured, including its failure mode).
    """
    p = Path(raw)
    usable = p.is_dir()
    return AssetResolution(
        AssetOrigin.INSTALLED if usable else AssetOrigin.ABSENT,
        p if usable else None,
        p,
        None,
        f"NWAVE_WAVES_DIR={p}"
        + ("" if usable else " names a directory that does not exist"),
    )


def _declared_no_nwave_tier(shipped_waves_dir_default: Path) -> bool:
    """True iff this host carries NO nWave tier at all (RCA point 8 / R6).

    Mirrors ``des_plugin.py``'s own install-time tier-presence check
    (``_install_nwave_runtime_assets`` :801-810, ``nwave_source.exists()``):
    the runtime-lib anchor (the directory that WOULD contain ``nWave/`` as a
    sibling, e.g. ``<claude_dir>/lib``) exists, but the ``nWave/`` tier itself
    was never shipped there -- a genuinely minimal / non-Claude host, legitimate
    and NOT a defect. Distinct from a tier that IS present (the ``nWave/``
    directory exists, so SOME assets shipped) but specifically missing
    ``waves/`` -- that is the actual defect and must NOT be waved through here.
    """
    nwave_dir = shipped_waves_dir_default.parent
    anchor_dir = nwave_dir.parent
    return anchor_dir.is_dir() and not nwave_dir.is_dir()


def _registry_indeterminate_message(
    wave: str, boundary: str, resolution: AssetResolution
) -> str:
    """WHAT/WHY/HOW for a wave-contract registry directory that could not be
    read at all -- distinct from a directory that legitimately declares zero
    rows (RCA §6.3)."""
    return (
        f"WHAT  the wave-contract registry directory could not be verified for "
        f"{wave} {boundary} -- looked at {resolution.installed}; the resolved "
        f"gate stack is UNVERIFIABLE, not empty.\n"
        f"WHY   this boundary could not be verified, and returning 'no gates' "
        f"here would be indistinguishable from 'every gate passed' -- an "
        f"unverifiable boundary must degrade LOUD, never silently allow.\n"
        f"HOW   reinstall so nWave/waves/ ships: "
        f"python scripts/install/install_nwave.py\n"
        f"      or name the registry explicitly: "
        f"NWAVE_WAVES_DIR=<repo-or-install>/nWave/waves"
    )


def resolve_stack(
    wave: str, boundary: str, *, start: Path | None = None
) -> StackResolution:
    """Resolve the wave's declared gate stack for ``boundary`` FROM the registry.

    The canonical wave-contract registry (``nWave/waves/<wave>.yaml``) is the SOLE
    gate-stack source (ADR-FLOW-006 D6, slice-06 MOVE-completion). Behaviour is
    byte-identical to the retired flavor-private read: the rows were migrated
    verbatim; an absent registry file / ``gate_stack`` block / boundary sub-key
    over a USABLE registry directory returns the empty list -- additive
    coexistence (C8), unaffected by this fix (RCA §3).

    RCA fix-installed-waves-registry-silent-empty: the REGISTRY DIRECTORY
    itself may be unusable (never shipped -- Root Cause A) rather than merely
    declaring no rows. ``NWAVE_WAVES_DIR`` keeps highest precedence (Root Cause
    C fix, GDP-4); absent that, the existing ``resolve_packaged_asset`` producer
    is reused (Root Cause B fix, §6.2) to classify the default location against
    a developer checkout (``start`` anchors the checkout search -- callers pass
    the PROJECT root they are validating, never the process cwd, so isolated
    tests never accidentally rescue an absent default via this very checkout).
    AMBIGUOUS prefers the checkout copy and never hard-blocks (§6.2, R3: it is
    the NORMAL developer state). A registry directory that is genuinely absent
    is INDETERMINATE unless this host DECLARES NO nWave TIER AT ALL, which is
    legitimate and stays a clean empty stack (RCA point 8 / R6).
    """
    override = os.environ.get("NWAVE_WAVES_DIR")
    if override:
        resolution = _override_resolution(override)
    else:
        resolution = resolve_packaged_asset(
            "nWave/waves", start=start, installed=_SHIPPED_WAVES_DIR
        )
        if resolution.origin is AssetOrigin.ABSENT and _declared_no_nwave_tier(
            _SHIPPED_WAVES_DIR
        ):
            return StackResolution([])

    if resolution.origin is AssetOrigin.AMBIGUOUS:
        waves_dir = resolution.repo
    elif resolution.is_usable:
        waves_dir = resolution.path
    else:
        return StackResolution(
            [],
            indeterminate=_registry_indeterminate_message(wave, boundary, resolution),
        )

    assert waves_dir is not None
    rows = resolve_wave_gate_stack_from_registry(wave, boundary, waves_dir=waves_dir)
    return StackResolution(rows)


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
