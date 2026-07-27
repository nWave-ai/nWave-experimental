"""Regression: nw-spike/SKILL.md must not frame SPIKE as a live wave.

OBSERVED (2026-07-26): CLAUDE.md (this repo's own SSOT, section 'Wave
Methodology') states plainly that SPIKE was a canonical wave phase prior to
v3.16.0 and is now deprecated -- spike/analysis work is embedded in the
DESIGN wave, and the /nw-spike command remains only for backward
compatibility. But nWave/skills/nw-spike/SKILL.md -- the skill an agent or
user actually loads when running /nw-spike -- opened with a bare wave/agent/
command banner presenting SPIKE as a normal, currently-canonical wave slotted
between DISCUSS and DESIGN, with no mention anywhere in the file of
deprecated, backward-compat, or v3.16 (grepped, zero hits). Its sibling
nw-spike-methodology/SKILL.md likewise never stated the deprecation. Since
/nw-spike remains callable and these are the only docs most callers read, an
agent following them had no way to learn SPIKE's proper current home is
inside DESIGN, not a standalone slot before it.
"""

from __future__ import annotations

from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3]
_SPIKE_SKILL = _REPO_ROOT / "nWave" / "skills" / "nw-spike" / "SKILL.md"
_SPIKE_METHODOLOGY_SKILL = (
    _REPO_ROOT / "nWave" / "skills" / "nw-spike-methodology" / "SKILL.md"
)

_DEPRECATION_MARKERS = ("deprecated", "backward compat")


def test_nw_spike_skill_states_the_deprecation() -> None:
    text = _SPIKE_SKILL.read_text(encoding="utf-8").lower()
    for marker in _DEPRECATION_MARKERS:
        assert marker in text, (
            f"nw-spike/SKILL.md must name its own deprecation ({marker!r} "
            "missing) -- CLAUDE.md's Wave Methodology section already "
            "declares SPIKE deprecated since v3.16.0."
        )


def test_nw_spike_methodology_skill_states_the_deprecation() -> None:
    text = _SPIKE_METHODOLOGY_SKILL.read_text(encoding="utf-8").lower()
    for marker in _DEPRECATION_MARKERS:
        assert marker in text, (
            f"nw-spike-methodology/SKILL.md must name its own deprecation "
            f"({marker!r} missing), mirroring the nw-spike sibling."
        )
