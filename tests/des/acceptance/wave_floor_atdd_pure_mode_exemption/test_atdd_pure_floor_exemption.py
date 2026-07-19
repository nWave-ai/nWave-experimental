"""Regression (sister-reported spine friction, 2026-06-23): an atdd_pure dispatch
under an armed wave floor must NOT be denied as a classic WAVE_MARKER_BYPASS.

An atdd_pure carpaccio sub-dispatch carries the atdd_pure marker discipline
(DES-MODE:atdd_pure + DES-PHASE + DES-SLICE) but NOT the classic DES-VALIDATION
marker. Under a still-armed wave floor (the floor does not auto-close at
slice-end), the classic WAVE_MARKER_BYPASS branch fired and DENIED it -- demanding
classic markers (DES-STEP-ID / DES-VALIDATION) that atdd_pure never produces. The
only escape was a human-authorized `des wave-clear`, so every new atdd_pure slice
stalled on the previous slice's stale floor.

The mode-aware fix routes an atdd_pure dispatch to atdd_pure validation BEFORE the
classic bypass -- the bypass's DES-VALIDATION demand is classic-only. It is purely
ADDITIVE (a new exemption branch); the classic bypass invariant is preserved (a
CLASSIC partial-marker child under an armed floor is STILL blocked loud).

Floor isolation mirrors the shipped wave_marker_bypass_benign_passthrough suite:
seed the DESIGN-pinned floor into a clean tmp_path and drive the REAL service under
os.chdir so the production WaveActiveReader resolves the INJECTED floor.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


_FLOOR_FILE_REL = ".nwave/wave-active/active.json"

# atdd_pure carpaccio dispatch: mode + a per-slice phase + a coherent slice scope,
# no classic DES-VALIDATION (atdd_pure never emits it).
_ATDD_PURE_PROMPT = (
    "<!-- DES-MODE : atdd_pure -->\n"
    "<!-- DES-PHASE : A_GREEN_ATS -->\n"
    "<!-- DES-SLICE : slice-01 -->\n"
    "proceed with the carpaccio slice work"
)

# Classic partial-marker child (no DES-MODE:atdd_pure): the invariant case that
# must STAY blocked loud under an armed floor.
_CLASSIC_PARTIAL_PROMPT = (
    "DES-PROJECT-ID: some-feature\n"
    "DES-STEP-ID: deliver-1\n"
    "proceed with the in-wave work"
)


def _seed_floor(root: Path, wave: str) -> None:
    floor_path = root / _FLOOR_FILE_REL
    floor_path.parent.mkdir(parents=True, exist_ok=True)
    floor_path.write_text(
        json.dumps({"wave": wave, "provenance": "command"}), encoding="utf-8"
    )


def _decide(root: Path, prompt: str):
    from des.adapters.drivers.hooks import service_factory
    from des.ports.driver_ports.pre_tool_use_port import PreToolUseInput

    prev_cwd = Path.cwd()
    prev_env = os.environ.get("DES_PROJECT_DIR")
    try:
        os.chdir(root)
        # Mirror the armed root into DES_PROJECT_DIR so `resolve_nwave_root()`
        # resolves the SAME root the floor was seeded at, not the per-test
        # isolation root the autouse `_isolate_nwave_root` fixture set.
        os.environ["DES_PROJECT_DIR"] = str(root)
        service = service_factory.create_pre_tool_use_service()
        return service.validate(PreToolUseInput(prompt=prompt, wave_entering=False))
    finally:
        os.chdir(prev_cwd)
        if prev_env is None:
            os.environ.pop("DES_PROJECT_DIR", None)
        else:
            os.environ["DES_PROJECT_DIR"] = prev_env


def test_atdd_pure_dispatch_under_armed_floor_not_wave_bypass(tmp_path):
    """An atdd_pure dispatch under an armed floor is NOT denied as a wave-bypass."""
    _seed_floor(tmp_path, wave="deliver")
    decision = _decide(tmp_path, _ATDD_PURE_PROMPT)
    reason = (decision.reason or "").lower()
    assert "wave_marker_bypass" not in reason, (
        "an atdd_pure dispatch (mode+phase+scope, no classic DES-VALIDATION) under "
        "an armed wave floor must be routed to atdd_pure validation, NEVER denied "
        f"as a classic WAVE_MARKER_BYPASS; got action={decision.action!r} "
        f"reason={decision.reason!r}"
    )


def test_classic_partial_marker_child_still_bypass_blocked(tmp_path):
    """Invariant preserved: a CLASSIC partial-marker child is STILL blocked loud."""
    _seed_floor(tmp_path, wave="design")
    decision = _decide(tmp_path, _CLASSIC_PARTIAL_PROMPT)
    assert decision.action == "block", (
        "a classic partial-marker child (no DES-MODE:atdd_pure) under an armed "
        f"floor must STAY blocked loud (bypass invariant); got {decision.action!r}"
    )
    assert "wave" in (decision.reason or "").lower()
