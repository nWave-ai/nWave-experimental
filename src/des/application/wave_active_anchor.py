"""CommandLiteralWaveActiveAnchor -- the deterministic prompt-submission anchor.

Implements ``WaveActiveAnchorPort`` (slice-04, nwave-flow-v2-enforcement): detects
the literal ``^/nw-(<wave>)`` in the raw prompt (NON-LLM, deterministic) and arms
a COMMAND record via ``WaveActiveWriter``; no match -> ``NoWaveActive`` (S1, zero
interference). SHAPE per DESIGN feature-delta § slice-04 code-design.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from des.domain.wave_active import (
    WAVE_VOCABULARY,
    NoWaveActive,
    WaveActiveRecord,
    WaveProvenance,
)
from des.ports.driver_ports.wave_active_anchor_port import (
    PromptSubmission,
    WaveActiveAnchorPort,
)


if TYPE_CHECKING:
    from des.ports.driven_ports.wave_active_store import WaveActiveWriter


# The literal command anchored at the start of the prompt: ``/nw-<wave>`` where
# <wave> is a member of the closed vocabulary, terminated by a word boundary so
# ``/nw-discussion`` does not match ``discuss``. The same literal on every runtime
# (research crux Q3: ``/nw-<wave>`` arrives as plain text everywhere).
_COMMAND_LITERAL = re.compile(r"^/nw-([a-z-]+)\b")


class CommandLiteralWaveActiveAnchor(WaveActiveAnchorPort):
    """Arms a COMMAND wave-active record from the ``/nw-<wave>`` command literal."""

    def __init__(self, writer: WaveActiveWriter) -> None:
        self._writer = writer

    def on_prompt_submitted(
        self, submission: PromptSubmission
    ) -> WaveActiveRecord | NoWaveActive:
        wave = self._detect_wave(submission.prompt)
        if wave is None:
            return NoWaveActive()
        # INVARIANT I4 (slice-07c, floor v1.1): the COMMAND arm -- which
        # deterministically saw the /nw-<wave> literal -- marks the wave entry
        # as PENDING (F3 structural signal). The gate side only reads and
        # (post-allow) clears it.
        record = WaveActiveRecord(
            wave=wave, provenance=WaveProvenance.COMMAND, entry_pending=True
        )
        self._writer.arm(submission.project_root, record)
        return record

    @staticmethod
    def _detect_wave(prompt: str) -> str | None:
        match = _COMMAND_LITERAL.match(prompt.strip())
        if match is None:
            return None
        candidate = match.group(1)
        return candidate if candidate in WAVE_VOCABULARY else None
