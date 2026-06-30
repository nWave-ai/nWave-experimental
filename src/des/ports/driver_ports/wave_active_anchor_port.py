"""Wave-active submission anchor driving port (slice-04, nwave-flow-v2-enforcement).

The runtime-agnostic prompt-submission anchor (§15 ``HookEventPort``). Detects
the literal ``^/nw-(<wave>)`` in the raw prompt (deterministic, NON-LLM) and
arms a COMMAND record; no match -> ``NoWaveActive`` (S1, zero interference).
SHAPE per DESIGN feature-delta § slice-04 code-design. The concrete anchor lives
in the application layer (``des.application.wave_active_anchor``); the per-runtime
stdin-JSON translation lives in the hook adapters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path

    from des.domain.wave_active import NoWaveActive, WaveActiveRecord


@dataclass(frozen=True)
class PromptSubmission:
    """Cross-runtime submission payload (driver input VO).

    ``prompt`` is the RAW user prompt text -- the literal ``/nw-<wave>`` lives here.
    """

    prompt: str
    project_root: Path


class WaveActiveAnchorPort(ABC):
    """Driving port: the deterministic prompt-submission wave-active anchor."""

    @abstractmethod
    def on_prompt_submitted(
        self, submission: PromptSubmission
    ) -> WaveActiveRecord | NoWaveActive:
        """Detect ``^/nw-(<wave>)`` and arm a COMMAND record, or return ``NoWaveActive``.

        Match -> arm(COMMAND) via ``WaveActiveWriter``, return the armed record.
        No match -> ``NoWaveActive`` (S1: ad-hoc work, never armed).
        """
        ...
