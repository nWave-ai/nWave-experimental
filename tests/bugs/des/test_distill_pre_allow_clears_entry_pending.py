"""Regression AT -- G-DISTILL-PRE's `allow` return skipped the wave-entering
clear-on-allow write, leaking `entry_pending=True` into the next dispatch.

`_evaluate_distill_dispatch_gate` (G-DISTILL-PRE, `src/des/adapters/drivers/
hooks/pre_tool_use_handler.py`) runs BEFORE `_peek_wave_entering` /
`activation.clear_entry` (slice-07c F3 NORMATIVO). On a complete D_DISTILL
marker set it returned `("allow", None)` and `handle_pre_tool_use` exited
immediately -- skipping the wave-entry peek AND the clear-on-allow write that
every other ALLOW path performs. `clear_entry` is called from exactly one
place in the whole codebase (the clear-on-allow branch), so nothing else
cleared the flag: `entry_pending` stayed True and was silently consumed by
whichever Agent/Task dispatch ran next, exempting it from the DES-VALIDATION
DENY cascade in `pre_tool_use_service.py` even when it was not the dispatch
genuinely entering the wave.

REPRODUCED LIVE (per the pile row): arm a `WaveActiveRecord(wave="distill",
provenance=COMMAND, entry_pending=True)` floor, drive a well-formed D_DISTILL
prompt through the real `handle_pre_tool_use()` hook entrypoint over its JSON
stdin protocol, and read the floor back afterward.

covers: techdebt row
`g-distill-pre-short-circuit-skips-clear-on-allow-leaks-wave-entering-flag`
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from des.adapters.driven.filesystem.wave_active_filesystem_store import (
    WaveActiveFilesystemStore,
)
from des.adapters.drivers.hooks.pre_tool_use_handler import handle_pre_tool_use
from des.domain.wave_active import WaveActiveRecord, WaveProvenance


def _armed_store(root: Path, *, wave: str, entry_pending: bool) -> None:
    WaveActiveFilesystemStore().arm(
        root,
        WaveActiveRecord(
            wave=wave, provenance=WaveProvenance.COMMAND, entry_pending=entry_pending
        ),
    )


def _well_formed_distill_prompt() -> str:
    return (
        "<!-- DES-MODE : atdd_pure -->\n"
        "<!-- DES-PHASE : D_DISTILL -->\n"
        "<!-- DES-PROJECT-ID : demo-feature -->\n"
        "<!-- DES-SLICE : feature-end -->\n"
        "Author the acceptance tests for the feature.\n"
    )


def _distill_dispatch_payload() -> dict[str, object]:
    return {
        "tool_name": "Agent",
        "tool_input": {
            "prompt": _well_formed_distill_prompt(),
            "subagent_type": "acceptance-designer",
        },
    }


def _run_handler_with_stdin(
    monkeypatch: pytest.MonkeyPatch, payload: dict[str, object]
) -> int:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    return handle_pre_tool_use()


def test_distill_pre_allow_clears_the_pending_entry_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    _armed_store(root, wave="distill", entry_pending=True)

    monkeypatch.delenv("DES_PROJECT_DIR", raising=False)
    monkeypatch.chdir(root)

    exit_code = _run_handler_with_stdin(monkeypatch, _distill_dispatch_payload())

    assert exit_code == 0, (
        f"a well-formed D_DISTILL dispatch must be allowed, got exit {exit_code}"
    )

    store = WaveActiveFilesystemStore()
    state = store.read(root)
    assert isinstance(state, WaveActiveRecord), (
        f"floor unexpectedly missing/corrupt after the dispatch: {state!r}"
    )
    assert state.entry_pending is False, (
        "G-DISTILL-PRE's 'allow' branch (pre_tool_use_handler.py, "
        "_evaluate_distill_dispatch_gate) must not short-circuit the "
        "wave-entering peek/clear-on-allow lifecycle -- observed "
        f"entry_pending={state.entry_pending!r} (still True): the flag leaked "
        "past this dispatch and would be silently consumed by the next one."
    )


def test_distill_pre_allow_still_short_circuits_when_no_entry_is_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No pending entry -> the distill-allow branch must not spuriously arm
    or block; it stays a plain allow with the floor left untouched."""
    root = tmp_path / "project"
    root.mkdir()
    _armed_store(root, wave="distill", entry_pending=False)

    monkeypatch.delenv("DES_PROJECT_DIR", raising=False)
    monkeypatch.chdir(root)

    exit_code = _run_handler_with_stdin(monkeypatch, _distill_dispatch_payload())

    assert exit_code == 0, f"expected allow, got exit {exit_code}"

    store = WaveActiveFilesystemStore()
    state = store.read(root)
    assert isinstance(state, WaveActiveRecord)
    assert state.entry_pending is False


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
