"""SessionStart/SessionEnd registration in the global activity registry.

Every host session that reaches the installed lifecycle hooks is recorded under
the selected agents home, whether or not its project is activated and whether
or not any update permission is granted: an update replaces the installation
shared by every repository, so an unrecorded session would be invisible to it.

Registration waits for the exclusive update lock, but native SessionStart hooks
cannot prove that their host withheld work. A timeout still records the session
and returns an explicit failed admission plus a warning. Controlled launchers,
not this advisory hook, gate host startup. Both functions are total.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Literal

from des.domain.update_timing import UPDATE_TIMING


REGISTRATION_WAIT_SECONDS = UPDATE_TIMING.admission_seconds
DEREGISTRATION_WAIT_SECONDS = UPDATE_TIMING.session_end_seconds


@dataclass(frozen=True)
class Registration:
    """Outcome of one SessionStart registration attempt."""

    key: str | None
    waited_for_update: bool = False
    notice: str = ""
    admission_state: Literal["admitted", "busy", "unknown", "update-incomplete"] = (
        "unknown"
    )

    @property
    def admitted(self) -> bool:
        """Positive coordination result, not evidence of native host blocking."""
        return self.admission_state == "admitted"


def _event(stdin_text: str) -> dict:
    try:
        event = json.loads(stdin_text)
    except (TypeError, json.JSONDecodeError):
        return {}
    return event if isinstance(event, dict) else {}


def register_session_start(stdin_text: str, host: str) -> Registration:
    """Record this host session; never raises."""
    try:
        from des.adapters.driven.activity.session_registry import (
            MANAGED_SESSION_ENV,
            SessionActivityRegistry,
        )

        registry = SessionActivityRegistry.selected()
        if registry is None:
            return Registration(
                key=None,
                notice=(
                    "nWave session admission is unknown: the activity registry could "
                    "not be resolved. Installation safety is not established; repair "
                    "the selected installation before starting wave work."
                ),
            )
        managed_key = os.environ.get(MANAGED_SESSION_ENV)
        if managed_key and any(
            record.key == managed_key
            and record.host == f"managed:{host}"
            and not record.problem
            for record in registry.sessions()
        ):
            # The wrapper, not a native inner session-end event, owns this lifetime.
            return Registration(key=managed_key, admission_state="admitted")
        event = _event(stdin_text)
        raw_id = event.get("session_id")
        session_id = raw_id if isinstance(raw_id, str) and raw_id else None
        cwd = event.get("cwd") if isinstance(event.get("cwd"), str) else ""
        source = event.get("source") if isinstance(event.get("source"), str) else ""
        started = time.monotonic()
        with registry.exclusive(REGISTRATION_WAIT_SECONDS) as acquired:
            key = registry.register(
                host=host, session_id=session_id, cwd=cwd, source=source
            )
            marker = registry.update_in_progress() if acquired else None
        waited = time.monotonic() - started > 2.0
        if not acquired:
            return Registration(
                key=key,
                waited_for_update=True,
                admission_state="busy",
                notice=(
                    "nWave session admission timed out: another session still holds "
                    "the installation update lock. The host may not block work on "
                    "this warning. Close this session; restart after the update finishes."
                ),
            )
        if marker is not None:
            return Registration(
                key=key,
                waited_for_update=waited,
                admission_state="update-incomplete",
                notice=(
                    "nWave session admission refused: an unfinished update is recorded; "
                    "package or host state is unknown. The host may not block work on "
                    "this warning. Close this session and inspect the update recovery "
                    "state before restarting."
                ),
            )
        return Registration(
            key=key, waited_for_update=waited, admission_state="admitted"
        )
    except Exception:
        return Registration(
            key=None,
            notice=(
                "nWave session admission is unknown: the activity registry could not "
                "record or verify this session. Installation safety is not established; "
                "repair the registry before starting wave work."
            ),
        )


def handle_session_end(stdin_text: str, host: str) -> int:
    """Remove this host session's record; always exits 0."""
    try:
        from des.adapters.driven.activity.session_registry import (
            SessionActivityRegistry,
            session_key,
        )

        registry = SessionActivityRegistry.selected()
        raw_id = _event(stdin_text).get("session_id")
        if registry is None or not isinstance(raw_id, str) or not raw_id:
            return 0
        key = session_key(host, raw_id)
        with registry.exclusive(DEREGISTRATION_WAIT_SECONDS):
            # A session that ended cannot be running a wave, so removal is
            # safe even when an update still holds the lock.
            registry.deregister(key)
    except Exception:
        pass
    return 0
