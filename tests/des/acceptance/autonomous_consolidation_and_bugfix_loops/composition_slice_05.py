"""Composition root + shared fixtures for autonomous-consolidation-and-bugfix-loops
slice-05 (a session starting fires every pending autonomous-loop tick,
fail-open -- resolves feature-delta Open Question OQ-3 / DA-13).

Pillar 3 (App as in production): the SUT is the REAL SessionStart hook --
`handle_session_start`, invoked over its JSON stdin protocol via the SAME
faithful in-process driving-port pattern slice-01 uses for the SubagentStop
hook (`run_hook_in_process`). This module NEVER imports a `des.domain.*` /
`des.cli.*` symbol to invoke the SUT -- only the real hook entry point is
driven. `AtCompletionLedger` is imported ONLY to OBSERVE the resulting
records (the S2 tolerable-variant, same as every sibling slice in this
feature) -- it is observation substrate, NOT the SUT.

── DELIVER-PINNED DIAGNOSTIC-MESSAGE CONTRACT (D-8 class 2) ──
When a request's `feature_id` cannot be derived (missing, or unparseable
JSON), the wrapper's fail-open stderr diagnostic MUST include the request's
OWN filename (`LOOP_TICK_REQUEST_FILENAME[domain]`, e.g.
`loop-tick-consolidation-signal.json`) so the diagnostic is attributable to
the domain that failed without requiring an exact-sentence match -- mirrors
the existing `[nwave] ... error (fail-open): {e}` idiom already used by
`_adopt_prior_use_if_warranted` / `_apply_pending_update_if_any`.

Each of the three default well-formed payloads in `steps.domain_types_slice_05`
is deliberately shaped to produce EXACTLY ONE new ledger record per domain per
tick (a fresh work-exhausted window opens; a fresh cloud-lane RCA stage is
always admitted) -- so "ticked exactly once" is provable by record-kind
presence alone, no count-fragile assertions.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Observation substrate (NOT the SUT) -- reads back the appended records.
from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

# The REAL `handle_session_start` SessionStart hook, driven IN-PROCESS over
# its stdin protocol (the same faithful driving-port pattern slice-01 uses
# for SubagentStop).
from des.adapters.drivers.hooks.session_start_handler import handle_session_start
from tests.common.in_process_cli import run_hook_in_process

from .steps.domain_types_slice_05 import (
    FEATURE_ID_BY_DOMAIN,
    LOOP_TICK_REQUEST_FILENAME,
    TICK_ATTEMPT_FAILED_EVENT,
    TICK_SUCCESS_EVENT,
    LoopTickDomain,
    LoopTickWiringOutcome,
    PendingLoopTick,
)


class LoopTickWiringFixture:
    """Composition-root service for autonomous-consolidation-and-bugfix-loops
    slice-05 ATs.

    Pillar 3: writes zero-or-more `.nwave/loop-tick-{domain}.json` request
    files under a real project directory, fires the SAME `handle_session_start`
    hook the live spine fires, and observes the resulting per-domain ledger
    diff + stderr text.

    Mandate-12 criterion 3: every public method is the SSOT for one piece of
    business logic. Step bodies do a typed lookup + one method call; nothing
    more.
    """

    def __init__(self, tmp_path: Path) -> None:
        self._session_cwd = tmp_path / "session-project"
        (self._session_cwd / ".nwave").mkdir(parents=True, exist_ok=True)

    # --- request seeding ---------------------------------------------------

    def seed(self, tick: PendingLoopTick) -> None:
        """Write ONE pending loop-tick request file (a Given precondition)."""
        filename = LOOP_TICK_REQUEST_FILENAME[tick.domain]
        request_path = self._session_cwd / ".nwave" / filename
        request_path.write_text(json.dumps(tick.request_json()), encoding="utf-8")

    # --- driving-port invocation (the REAL hook) ----------------------------

    def fire_session_start(self) -> LoopTickWiringOutcome:
        """Fire the REAL SessionStart hook once and observe the outcome."""
        before = {domain: self._read_all(domain) for domain in LoopTickDomain}

        hook_input = json.dumps(
            {
                "session_id": "loops-slice05-session",
                "hook_event_name": "SessionStart",
                "source": "startup",
                "cwd": str(self._session_cwd),
            }
        )
        exit_code, _stdout, stderr = run_hook_in_process(
            handle_session_start,
            stdin_text=hook_input,
            cwd=str(self._session_cwd),
        )

        after = {domain: self._read_all(domain) for domain in LoopTickDomain}

        ticked: dict[LoopTickDomain, bool] = {}
        attempt_failed: dict[LoopTickDomain, bool] = {}
        stderr_mentions_domain: dict[LoopTickDomain, bool] = {}
        for domain in LoopTickDomain:
            new_records = after[domain][len(before[domain]) :]
            ticked[domain] = any(
                r.get("event") == TICK_SUCCESS_EVENT[domain] for r in new_records
            )
            attempt_failed[domain] = any(
                r.get("event") == TICK_ATTEMPT_FAILED_EVENT[domain] for r in new_records
            )
            stderr_mentions_domain[domain] = (
                "[nwave]" in stderr
                and "fail-open" in stderr
                and LOOP_TICK_REQUEST_FILENAME[domain] in stderr
            )

        return LoopTickWiringOutcome(
            exit_code=exit_code,
            ticked=ticked,
            attempt_failed=attempt_failed,
            stderr_mentions_domain=stderr_mentions_domain,
        )

    # --- ledger observation --------------------------------------------------

    def _read_all(self, domain: LoopTickDomain) -> list[dict]:
        """Read every record for `domain`'s fixed ledger namespace (port read)."""
        ledger = AtCompletionLedger(FEATURE_ID_BY_DOMAIN[domain], self._session_cwd)
        try:
            return ledger.read_records()
        except Exception:
            return []


@pytest.fixture
def loop_tick_wiring_fixture(tmp_path) -> LoopTickWiringFixture:
    """The single composition-root service all slice-05 step methods delegate to."""
    return LoopTickWiringFixture(tmp_path)


@pytest.fixture
def state_05() -> dict:
    """Per-scenario scratchpad: `outcome`, `broken_domain`, `only_domain`."""
    return {}


__all__ = [
    "LoopTickWiringFixture",
]
