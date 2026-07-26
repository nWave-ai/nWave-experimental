#!/usr/bin/env python3
"""Standalone, spine-independent orchestrator-affordance refresh hook.

# des-hook:orchestrator-affordance-refresh-standalone

Fixes the discoverability defect where the "how to use nWave" affordance
(`nWave/data/orchestrator-affordance/{spine-discipline.md,
des-command-catalog.md}`) was injected ONLY by the DES runtime hooks
(`src/des/adapters/drivers/hooks/{session_start_handler,
user_prompt_submit_handler}.py`), which meant:

  (A) a 30-minute refresh cadence, not the mandated ~15 minutes;
  (B) zero affordance in a session where the `des` package cannot be
      imported (non-DES repo, broken install);
  (C) SessionStart registered with `matcher="startup"` only, so it never
      fired on Claude Code's `resume`/`clear`/`compact` sub-events.

This script is stdlib-only -- it NEVER imports the `des` package -- and
mirrors the existing `~/.claude/hooks/load_persona.py` pattern: resolve its
own assets relative to `Path(__file__)`, read them fresh on every call,
print the Claude Code `hookSpecificOutput` JSON envelope.

Usage: orchestrator_affordance_refresh.py <SessionStart|UserPromptSubmit>

SessionStart: unconditional injection (no matcher registration -- fires on
startup|resume|clear|compact).
UserPromptSubmit: self-gated on a 900-second (~15-minute) sentinel file
(`.nwave/orchestrator-affordance-last-injected`, relative to the process
cwd) -- the SAME sentinel path the DES-side
`user_prompt_submit_handler._maybe_refresh_orchestrator_affordance` uses,
so the two paths never double-inject.

Degrade-loud: a missing assets directory prints a one-line stderr
diagnostic and exits 0 (fail-open for the hook protocol) -- never a silent
no-op.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


_REFRESH_SECONDS = 900
_SENTINEL_RELATIVE = Path(".nwave") / "orchestrator-affordance-last-injected"
_ASSET_SEPARATOR = "\n\n"


def _candidate_assets_dirs() -> list[Path]:
    """Every plausible location of the shipped `orchestrator-affordance/` assets.

    Three install shapes, tried in order:
      1. Installed Claude-scoped layout -- this script ships flat to
         `<claude_dir>/scripts/orchestrator_affordance_refresh.py`, and the
         nWave runtime assets ship to `<claude_dir>/lib/nWave/data/...`
         (`DESPlugin._ship_nwave_runtime_assets`). Two `.parent` hops off
         the script's own file reach `<claude_dir>`.
      2. Installed host-neutral layout (Codex, Copilot, OpenCode) --
         `DESPlugin._runtime_python_dir` ships the SAME runtime assets to
         `~/.nwave/nWave/data/...` instead, whenever "codex" is in
         the install's target platforms (fix-codex-only-orchestrator-
         affordance-runtime-aware-resolver). A host-neutral install never
         populates candidate 1, so this script found nothing there and
         diagnosed a false "missing assets" -- even though the data had
         already landed on disk, just under a different root. Computed
         inline (not imported from scripts/shared/install_paths) to keep
         this script's zero-coupling, stdlib-only contract intact.
      3. Dev-checkout layout -- this script lives at
         `<repo_root>/scripts/hooks/orchestrator_affordance_refresh.py`,
         and the assets live at `<repo_root>/nWave/data/...`. Three
         `.parent` hops off the script's own file reach `<repo_root>`.

    Never cwd-dependent -- always resolved relative to `Path(__file__)` (and,
    for candidate 2, `Path.home()`, which is what the shipping side also
    resolves against).
    """
    script_path = Path(__file__).resolve()
    installed_candidate = (
        script_path.parent.parent / "lib" / "nWave" / "data" / "orchestrator-affordance"
    )
    host_neutral_candidate = (
        Path.home() / ".nwave" / "nWave" / "data" / "orchestrator-affordance"
    )
    dev_checkout_candidate = (
        script_path.parent.parent.parent / "nWave" / "data" / "orchestrator-affordance"
    )
    return [installed_candidate, host_neutral_candidate, dev_checkout_candidate]


def _resolve_assets_dir() -> Path | None:
    """First existing candidate assets directory, or `None` if none exist."""
    for candidate in _candidate_assets_dirs():
        if candidate.is_dir():
            return candidate
    return None


def _load_affordance(assets_dir: Path) -> str | None:
    """Concatenate every `*.md` file directly under `assets_dir`, sorted by name.

    Content is read fresh on every call -- never cached -- mirroring
    `session_start_handler.load_orchestrator_affordance`. Returns `None`
    when the directory carries no readable `.md` file.
    """
    md_paths = sorted(assets_dir.glob("*.md"))
    contents = []
    for path in md_paths:
        try:
            contents.append(path.read_text(encoding="utf-8"))
        except OSError:
            continue
    if not contents:
        return None
    return _ASSET_SEPARATOR.join(contents)


def _build_envelope(event: str, additional_context: str) -> dict[str, object]:
    return {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": additional_context,
        }
    }


def _sentinel_path() -> Path:
    """The refresh sentinel, relative to the process's own cwd.

    Claude Code invokes hooks with `cwd` set to the project root, so this
    resolves to the SAME path the DES-side handler computes from the hook
    payload's `cwd` field -- the shared sentinel that prevents double
    injection between the two paths.
    """
    return Path.cwd() / _SENTINEL_RELATIVE


def _is_sentinel_elapsed(sentinel: Path) -> bool:
    """True when the sentinel is missing, corrupt, or `>= _REFRESH_SECONDS` old.

    Degrade-safe: a missing sentinel, a directory occupying the sentinel
    path, or any other stat failure all count as elapsed so the caller
    re-injects rather than staying silently dormant forever.
    """
    try:
        if sentinel.is_dir():
            return True
        mtime = sentinel.stat().st_mtime
    except OSError:
        return True
    return (time.time() - mtime) >= _REFRESH_SECONDS


def _touch_sentinel(sentinel: Path) -> None:
    """Create/refresh the sentinel file's mtime to now."""
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.touch(exist_ok=True)
    now = time.time()
    os.utime(sentinel, (now, now))


def _diagnose_missing_assets(assets_dir_candidates: list[Path]) -> None:
    """Non-silent stderr diagnostic naming the problem (degrade-loud)."""
    tried = ", ".join(str(candidate) for candidate in assets_dir_candidates)
    sys.stderr.write(
        "[orchestrator-affordance-refresh] assets directory not found -- "
        f"tried: {tried}\n"
    )


def main() -> int:
    event = sys.argv[1] if len(sys.argv) > 1 else "SessionStart"

    candidates = _candidate_assets_dirs()
    assets_dir = _resolve_assets_dir()
    if assets_dir is None:
        _diagnose_missing_assets(candidates)
        return 0

    if event == "UserPromptSubmit":
        sentinel = _sentinel_path()
        if not _is_sentinel_elapsed(sentinel):
            return 0
        affordance = _load_affordance(assets_dir)
        if affordance:
            print(json.dumps(_build_envelope(event, affordance)))
        _touch_sentinel(sentinel)
        return 0

    # SessionStart (and any other event Claude Code may route here):
    # unconditional injection -- no self-gating, no matcher restriction.
    affordance = _load_affordance(assets_dir)
    if affordance is None:
        sys.stderr.write(
            "[orchestrator-affordance-refresh] no *.md affordance assets "
            f"found under {assets_dir} -- nothing injected\n"
        )
        return 0
    print(json.dumps(_build_envelope(event, affordance)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
