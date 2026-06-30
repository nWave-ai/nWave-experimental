"""UserPromptSubmit hook handler (slice-04, nwave-flow-v2-enforcement).

The prompt-submission adapter behind ``WaveActiveAnchorPort`` (§15 HookEventPort).
Reads the runtime's stdin JSON ``{prompt, cwd}``, builds a ``PromptSubmission``,
calls ``on_prompt_submitted`` (which arms the wave-active floor on a
``/nw-<wave>`` match via ``WaveActiveWriter``), exits 0.

Router command: ``user-prompt-submit``. The arm happens deterministically from
the literal command -- whether or not a model turn or skill load ever occurs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from des.adapters.driven.filesystem.wave_active_filesystem_store import (
    WaveActiveFilesystemStore,
)
from des.application.wave_active_anchor import CommandLiteralWaveActiveAnchor
from des.ports.driver_ports.wave_active_anchor_port import PromptSubmission


def handle_user_prompt_submit() -> int:
    """Read the submission from stdin, arm the wave-active floor, exit 0."""
    raw = sys.stdin.read()
    payload = json.loads(raw) if raw.strip() else {}
    prompt = payload.get("prompt", "")
    project_root = Path(payload.get("cwd") or Path.cwd())

    anchor = CommandLiteralWaveActiveAnchor(writer=WaveActiveFilesystemStore())
    anchor.on_prompt_submitted(
        PromptSubmission(prompt=prompt, project_root=project_root)
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - subprocess entry for the e2e AT
    raise SystemExit(handle_user_prompt_submit())
