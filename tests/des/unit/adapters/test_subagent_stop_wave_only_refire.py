"""RC2/RC1 cure: the wave-only re-fire terminal breaks the unemittable-marker loop.

Root cause (docs/feedback/des-spine-ceremony-cost-attack-plan.md):

  * RC1 -- the wave-close keys on a DES-WAVE marker the agent CANNOT emit where the
    parser reads (it lives in the orchestrator's Task-prompt, not the agent's return).
  * RC2 -- the SubagentStop hook RE-FIRES on the ``{decision:block}`` body. Because the
    marker is unemittable, the re-fire makes no progress and the agent loops -- the
    ~100k-per-dispatch "wave-marker tax".

The cure (mirrors the atdd_pure bounded-block terminal + the classic path's
``stop_hook_active`` loop-break at subagent_stop_service.py:266): on a RE-FIRE (Claude
Code re-invokes the Stop hook with ``stop_hook_active: true`` after a prior block), the
wave-only path must NOT re-emit ``{decision:block}`` (which re-fires again). Instead it
emits a TERMINATING-LOUD INDETERMINATE -- a LOUD ``sys.__stderr__`` warning naming the
loop, NO block body, exit 0 -- so Claude Code reaches a terminal Stop. The FIRST fire
keeps its existing fail-closed block (the slice-01 gate-out veto + the slice-06
unresolvable-boundary refusal stay byte-stable). Enforcement is NOT bypassed: the
review verdict stays unrecorded and the wave floor stays armed, so the downstream
state-level gate still catches the missing review (fix-ask #2: wave-close derived from
STATE, not from an unemittable marker).

SUT (direct handler level): ``_handle_wave_only_return`` (the resolvable gate-out veto
path) and ``_handle_wave_only_unresolved`` (the slice-06 fail-closed boundary). The
subprocess driving surface used by the wave-gateout acceptance suite is short-circuited
by the unrelated activation gate on an inactive tmp project, so these unit tests drive
the two handler functions directly -- the precise locus of the RC2/RC1 cure.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

import pytest

from des.adapters.drivers.hooks.subagent_stop_handler import (
    _handle_wave_only_return,
    _handle_wave_only_unresolved,
    _WaveOnlyResolvedContext,
    _WaveOnlyUnresolved,
)


_FEATURE_ID = "synthetic-refire-feature"
_GOVERNED_WAVE = "design"

# The loud terminal token the cure prints to ``sys.__stderr__`` to NAME the broken
# re-fire loop -- the operator's signal that the agent was terminated (not silently
# allowed) because the demanded marker is unemittable.
_TERMINAL_STDERR_TOKEN = "wave-only re-fire terminal"


def _arm_design_floor(repo: Path) -> None:
    from des.adapters.driven.filesystem.wave_active_filesystem_store import (
        WaveActiveFilesystemStore,
    )
    from des.domain.wave_active import WaveActiveRecord, WaveProvenance

    WaveActiveFilesystemStore().arm(
        repo, WaveActiveRecord(wave=_GOVERNED_WAVE, provenance=WaveProvenance.INFERRED)
    )


def _provision_gate_out_veto_repo(repo: Path) -> None:
    """An armed DESIGN floor + a feature-delta the gate-out seals against, NO review.

    With no recorded review verdict the gate-out review veto blocks the wave-only
    return on the FIRST fire -- the loop driver this test breaks on re-fire.
    """
    delta = repo / "docs" / "feature" / _FEATURE_ID / "feature-delta.md"
    delta.parent.mkdir(parents=True, exist_ok=True)
    delta.write_text(
        "# Feature Delta: synthetic re-fire feature fixture\n\n## Wave: DESIGN\n",
        encoding="utf-8",
    )
    _arm_design_floor(repo)


def _run(fn) -> tuple[int, str, str]:
    """Run a handler closure capturing (exit_code, stdout, real-fd2 stderr).

    The cure's loud warning is printed to ``sys.__stderr__`` (the interpreter's
    original fd-2, which survives the handler's ``redirect_stderr``), so the test
    swaps ``sys.__stderr__`` for a buffer to observe it.
    """
    out = io.StringIO()
    err = io.StringIO()
    real_err = sys.__stderr__
    sys.__stderr__ = err  # type: ignore[misc]
    try:
        with contextlib.redirect_stdout(out):
            code = fn()
    finally:
        sys.__stderr__ = real_err  # type: ignore[misc]
    return code, out.getvalue(), err.getvalue()


def _decision(stdout: str) -> str | None:
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and "decision" in payload:
            value = payload.get("decision")
            return value if isinstance(value, str) else None
    return None


# ---------------------------------------------------------------------------
# resolvable wave-only return (gate-out review veto)
# ---------------------------------------------------------------------------


def test_resolved_first_fire_blocks_fail_closed(tmp_path: Path) -> None:
    """Regression-lock: the FIRST gate-out fire still blocks (review veto byte-stable)."""
    _provision_gate_out_veto_repo(tmp_path)
    ctx = _WaveOnlyResolvedContext(
        declared_wave=_GOVERNED_WAVE,
        project_id=_FEATURE_ID,
        effective_cwd=str(tmp_path),
        subagent_type="nw-solution-architect",
    )
    code, stdout, stderr = _run(
        lambda: _handle_wave_only_return(ctx, "hid", stop_hook_active=False)
    )
    assert code == 0
    assert _decision(stdout) == "block", (
        "the FIRST wave-only fire (no stop_hook_active) must keep the gate-out review "
        f"veto's fail-closed block. stdout={stdout[:300]!r} stderr={stderr[:300]!r}"
    )


def test_resolved_refire_breaks_loop_loud(tmp_path: Path) -> None:
    """RC2/RC1: a gate-out RE-FIRE emits a terminating-LOUD INDETERMINATE, not a block."""
    _provision_gate_out_veto_repo(tmp_path)
    ctx = _WaveOnlyResolvedContext(
        declared_wave=_GOVERNED_WAVE,
        project_id=_FEATURE_ID,
        effective_cwd=str(tmp_path),
        subagent_type="nw-solution-architect",
    )
    code, stdout, stderr = _run(
        lambda: _handle_wave_only_return(ctx, "hid", stop_hook_active=True)
    )
    assert code == 0
    assert _decision(stdout) != "block", (
        "a wave-only RE-FIRE (stop_hook_active=true) must NOT re-emit a {decision:block} "
        f"body -- that is the unbounded re-fire loop RC2 names. stdout={stdout[:300]!r}"
    )
    assert _TERMINAL_STDERR_TOKEN in stderr, (
        "the re-fire loop-break must be LOUD: a sys.__stderr__ warning naming the "
        f"{_TERMINAL_STDERR_TOKEN!r} terminal (degrade-LOUD, never a silent allow). "
        f"stderr={stderr[:400]!r}"
    )


# ---------------------------------------------------------------------------
# unresolvable wave-only return (slice-06 fail-closed boundary)
# ---------------------------------------------------------------------------


def _unresolved() -> _WaveOnlyUnresolved:
    return _WaveOnlyUnresolved(
        reason="out-of-vocabulary wave 'bogus-not-a-wave'",
        declared_wave="bogus-not-a-wave",
        project_id=_FEATURE_ID,
    )


def test_unresolved_first_fire_refuses(tmp_path: Path) -> None:
    """Regression-lock: the FIRST unresolvable fire still refuses (slice-06 boundary)."""
    code, stdout, _ = _run(
        lambda: _handle_wave_only_unresolved(
            _unresolved(), "hid", stop_hook_active=False
        )
    )
    assert code == 0
    assert _decision(stdout) == "block", (
        "the FIRST unresolvable wave-only fire must keep the slice-06 fail-closed "
        f"refusal (degrade-LOUD, never silent allow). stdout={stdout[:300]!r}"
    )


def test_unresolved_refire_breaks_loop_loud(tmp_path: Path) -> None:
    """RC2/RC1: an unresolvable RE-FIRE emits a terminating-LOUD INDETERMINATE."""
    code, stdout, stderr = _run(
        lambda: _handle_wave_only_unresolved(
            _unresolved(), "hid", stop_hook_active=True
        )
    )
    assert code == 0
    assert _decision(stdout) != "block", (
        "an unresolvable wave-only RE-FIRE must NOT re-emit a {decision:block} body -- "
        f"the marker is unemittable, re-firing is futile. stdout={stdout[:300]!r}"
    )
    assert _TERMINAL_STDERR_TOKEN in stderr, (
        "the unresolvable re-fire loop-break must be LOUD (sys.__stderr__ terminal). "
        f"stderr={stderr[:400]!r}"
    )


# Guard against accidentally weakening the first-fire fail-closed contract by a
# shared helper that ignores stop_hook_active.
@pytest.mark.parametrize("stop_hook_active", [False, True])
def test_unresolved_always_exits_zero(tmp_path: Path, stop_hook_active: bool) -> None:
    code, _, _ = _run(
        lambda: _handle_wave_only_unresolved(
            _unresolved(), "hid", stop_hook_active=stop_hook_active
        )
    )
    assert code == 0
