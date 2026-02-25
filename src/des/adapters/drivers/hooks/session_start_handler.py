"""SessionStart hook handler for nWave update checks.

Reads hook input JSON from stdin, invokes UpdateCheckService, and writes
additionalContext JSON to stdout when UPDATE_AVAILABLE.

Fail-open: any exception exits 0 so session is never blocked.

Output format when UPDATE_AVAILABLE:
    {"additionalContext": "nWave update available: {local} → {latest}. Changes: {changelog_or_empty}"}
"""

from __future__ import annotations

import json
import sys


def _get_local_version() -> str:
    """Return installed nwave-ai version, or '0.0.0' if unavailable."""
    from des.application.update_check_service import _detect_local_version

    return _detect_local_version()


def _build_update_check_service():
    """Build UpdateCheckService with DESConfig for frequency gating."""
    from des.adapters.driven.config.des_config import DESConfig
    from des.application.update_check_service import UpdateCheckService

    des_config = DESConfig()
    return UpdateCheckService(des_config=des_config)


def _build_update_message(local: str, latest: str, changelog: str | None) -> str:
    """Format the additionalContext message for an available update."""
    changes = changelog or ""
    return f"nWave update available: {local} \u2192 {latest}. Changes: {changes}"


def handle_session_start() -> int:
    """Handle session-start hook: check for nWave updates.

    Reads JSON from stdin (Claude Code hook protocol), calls UpdateCheckService,
    and writes additionalContext to stdout when an update is available.

    Returns:
        0 always (fail-open: session must never be blocked).
    """
    try:
        # Read stdin (ignore content — session-start sends session metadata)
        sys.stdin.read()

        service = _build_update_check_service()
        result = service.check_for_updates()

        from des.application.update_check_service import UpdateStatus

        if result.status == UpdateStatus.UPDATE_AVAILABLE:
            message = _build_update_message(
                local=_get_local_version(),
                latest=result.latest or "",
                changelog=result.changelog,
            )
            print(json.dumps({"additionalContext": message}))

        return 0

    except Exception:
        return 0
