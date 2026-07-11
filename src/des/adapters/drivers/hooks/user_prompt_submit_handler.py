"""UserPromptSubmit hook handler (slice-04, nwave-flow-v2-enforcement).

The prompt-submission adapter behind ``WaveActiveAnchorPort`` (§15 HookEventPort).
Reads the runtime's stdin JSON ``{prompt, cwd}``, builds a ``PromptSubmission``,
calls ``on_prompt_submitted`` (which arms the wave-active floor on a
``/nw-<wave>`` match via ``WaveActiveWriter``), exits 0.

Router command: ``user-prompt-submit``. The arm happens deterministically from
the literal command -- whether or not a model turn or skill load ever occurs.

Also carries the HOURLY re-injection of the orchestrator spine-discipline
affordance (feature: orchestrator-affordance-hourly-refresh). SessionStart /
clear / compact inject the affordance once via
``session_start_handler.load_orchestrator_affordance``; on a long-running
session (1M context) that single injection can go stale for hours. This
handler mirrors the SAME content on every submitted prompt, gated by a
``.nwave/orchestrator-affordance-last-injected`` sentinel file whose mtime is
the "last injected at" timestamp -- the same idiomatic pattern
``HousekeepingService._clean_signal_files`` uses for signal-file staleness --
so the refresh fires at most once per hour. Missing or corrupt sentinel state
degrades to "elapsed" (inject) rather than silently going dormant. Fail-open:
any internal error is swallowed and the hook always exits 0.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

from des.adapters.driven.filesystem.wave_active_filesystem_store import (
    WaveActiveFilesystemStore,
)
from des.adapters.drivers.hooks.session_start_handler import (
    _ORCHESTRATOR_AFFORDANCE_ASSETS_DIR,
    load_orchestrator_affordance,
)
from des.application.wave_active_anchor import CommandLiteralWaveActiveAnchor
from des.ports.driver_ports.wave_active_anchor_port import PromptSubmission


_ORCHESTRATOR_AFFORDANCE_SENTINEL_RELATIVE = (
    Path(".nwave") / "orchestrator-affordance-last-injected"
)
_ORCHESTRATOR_AFFORDANCE_REFRESH_SECONDS = 3600


def _is_orchestrator_affordance_sentinel_elapsed(
    sentinel: Path, threshold_seconds: float = _ORCHESTRATOR_AFFORDANCE_REFRESH_SECONDS
) -> bool:
    """True when the sentinel is missing, corrupt, or older than the threshold.

    A missing sentinel, a directory occupying the sentinel path (corrupt
    state -- a directory's own mtime would otherwise pass the age check), and
    any other stat failure all degrade to "elapsed" so the caller re-injects
    rather than staying silently dormant forever.
    """
    try:
        if sentinel.is_dir():
            return True
        mtime = sentinel.stat().st_mtime
    except OSError:
        return True
    return (time.time() - mtime) >= threshold_seconds


def _touch_orchestrator_affordance_sentinel(sentinel: Path) -> None:
    """Create/refresh the sentinel file's mtime to now.

    Degrade-safe: if a directory occupies the sentinel path (corrupt state),
    it is removed and replaced with a fresh empty file so subsequent elapsed
    checks stat a plain file again.
    """
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    if sentinel.is_dir():
        shutil.rmtree(sentinel)
    sentinel.touch(exist_ok=True)
    now = time.time()
    os.utime(sentinel, (now, now))


def _build_user_prompt_submit_affordance_output(affordance: str) -> dict[str, object]:
    """Build the UserPromptSubmit hookSpecificOutput payload for the affordance text.

    Mirrors ``session_start_handler._build_orchestrator_affordance_output`` --
    same wrapped ``hookSpecificOutput.additionalContext`` shape, only the
    ``hookEventName`` differs (``UserPromptSubmit`` vs ``SessionStart``).
    """
    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": affordance,
        }
    }


def _maybe_refresh_orchestrator_affordance(project_root: Path) -> None:
    """Re-inject the orchestrator affordance when the hourly sentinel has elapsed.

    Fail-open: any error (unreadable assets, unwritable sentinel, etc.) is
    swallowed -- a refresh failure must never block prompt submission.
    """
    try:
        sentinel = project_root / _ORCHESTRATOR_AFFORDANCE_SENTINEL_RELATIVE
        if not _is_orchestrator_affordance_sentinel_elapsed(sentinel):
            return
        affordance = load_orchestrator_affordance(_ORCHESTRATOR_AFFORDANCE_ASSETS_DIR)
        if affordance:
            print(json.dumps(_build_user_prompt_submit_affordance_output(affordance)))
        _touch_orchestrator_affordance_sentinel(sentinel)
    except Exception:
        pass


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

    _maybe_refresh_orchestrator_affordance(project_root)

    return 0


if __name__ == "__main__":  # pragma: no cover - subprocess entry for the e2e AT
    raise SystemExit(handle_user_prompt_submit())
