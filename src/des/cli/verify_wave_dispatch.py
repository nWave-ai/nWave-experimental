"""Wave-dispatch guard gate -- ``des verify-wave-dispatch`` (slice-05, DDD-8/9).

PRODUCTION RUNTIME enforcement: a thin ``des.cli`` gate MIRRORING
``verify_readiness_pre_dispatch.py`` over the pure ``wave_dispatch_guard_policy``.
Composed onto ``dispatch.pre`` (atdd_pure.yaml) so it auto-fires on every
Agent/Task dispatch the PreToolUse intercept sees -- NOT a prose-invoked CLI an
orchestrator can silently skip.

Driving surface (Mandate-13, Layer-3 subprocess): ARGS -- ``--subagent-type``
(required), ``--prompt-path`` (a FILE holding the dispatch prompt, hermetic),
``--repo-root``, ``--session-id``. The decision is projected onto the process
EXIT CODE plus one JSON line on stdout.

Exit codes (mirrors the readiness gate, §22.0 H-2):
  0 -- ALLOW: on-spine (matching DES-WAVE marker) OR exempt agent OR a form-valid
       skip witness OR a valid session pre-grant.
  1 -- BLOCK: a wave-owner dispatched off-spine with no recognized signal.
  2 -- malformed input (argparse failure on the required --subagent-type).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from des.adapters.driven.filesystem.wave_active_filesystem_store import (
    WaveActiveFilesystemStore,
)
from des.domain.wave_active import WaveActiveRecord, is_inferred_floor_expired
from des.domain.wave_dispatch_guard_policy import (
    WAVE_OWNERS,
    GuardVerdict,
    decide_dispatch,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des verify-wave-dispatch",
        description=(
            "Verify an Agent/Task dispatch enters its wave on-spine before it "
            "fires (closes the wave-level silent-entry hole, DDD-8/9)."
        ),
    )
    parser.add_argument(
        "--subagent-type",
        required=True,
        help="The subagent_type the orchestrator is dispatching.",
    )
    parser.add_argument(
        "--prompt-path",
        required=False,
        default=None,
        help="Path to a FILE holding the dispatch prompt (carries the DES-WAVE marker).",
    )
    parser.add_argument(
        "--repo-root",
        required=False,
        default=None,
        help="Repo root path. Defaults to CWD.",
    )
    parser.add_argument(
        "--session-id",
        required=False,
        default="",
        help="Session id keying the session-scoped pre-grant lookup.",
    )
    return parser


def _read_prompt(prompt_path: str | None) -> str:
    """Read the dispatch prompt from the FILE, or '' when absent/unreadable.

    A missing prompt FILE reads as an empty prompt (no DES-WAVE marker) -- the
    gate then falls through to the witness / pre-grant / BLOCK cascade.
    """
    if prompt_path is None:
        return ""
    try:
        return Path(prompt_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def main(argv: list[str] | None = None) -> int:
    """Entry point invoked by ``des verify-wave-dispatch``.

    Returns 0 (ALLOW) / 1 (BLOCK); argparse returns 2 on the missing required
    --subagent-type (malformed input).
    """
    args = _build_parser().parse_args(argv)
    repo_root = Path(args.repo_root) if args.repo_root else Path.cwd()
    prompt = _read_prompt(args.prompt_path)

    decision = decide_dispatch(
        subagent_type=args.subagent_type,
        prompt=prompt,
        repo_root=repo_root,
        session_id=args.session_id,
        active_floor=_read_active_floor(repo_root),
    )

    payload = {
        "event": (
            "WaveDispatchAllowed"
            if decision.verdict is GuardVerdict.ALLOW
            else "WaveDispatchBlocked"
        ),
        "subagent_type": args.subagent_type,
        "wave": _wave_for(args.subagent_type),
        "verdict": "allow" if decision.verdict is GuardVerdict.ALLOW else "block",
        "recognized_signal": decision.recognized_signal,
        "reason": decision.reason,
    }
    print(json.dumps(payload))
    return decision.verdict.value


def _read_active_floor(repo_root: Path) -> WaveActiveRecord | None:
    """Read the wave-active floor via the SAME store the PreToolUse AT-3 check uses.

    Returns the armed ``WaveActiveRecord`` so ``decide_dispatch`` can detect the
    AT-3 collision case (DDD-1: one exemption model, the floor read shared with
    AT-3). A non-record state -- NoWaveActive (no floor) or Indeterminate (a
    degrade-LOUD read failure) -- yields None: the collision branch is then never
    detected and every existing ALLOW path is preserved (the change stays
    additive; this slice reconciles ONLY the collision case).
    """
    state = WaveActiveFilesystemStore().read(repo_root)
    if not isinstance(state, WaveActiveRecord):
        return None
    # RC3: a stale INFERRED guess (armed past the TTL) is treated as no floor ->
    # no AT-3 collision -> the non-owner dispatch is allowed. Read-side GC; the
    # floor self-heals on the next wave-declaring dispatch (arm_inferred re-arms).
    if is_inferred_floor_expired(state, time.time()):
        return None
    return state


def _wave_for(subagent_type: str) -> str | None:
    """The owner's wave token for the JSON line, or None for an exempt agent."""

    return WAVE_OWNERS.get(subagent_type)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
