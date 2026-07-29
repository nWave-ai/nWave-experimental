"""Regression: the freshness degrade-loud advisory (STALE / CONFIG_DRIFT) must
be throttled to one emission per verdict state per window, not re-announced
on every hook subprocess.

Measured 2026-07-28: `HEALTH_GATE_INSTALL_FRESHNESS_STALE` fired 14,378 times
over 8 days in this project's own audit log (`grep -c` over
`.nwave/des/logs/audit-*.log`) -- 75/hour on average, zero production
readers (`mcp__tsunami__reads_of` confirms only the emitter module + 4 test
files touch the symbol). Each individual emission was mechanically CORRECT
(the installed tree really did differ from the live repo tree at that
instant), so muting the signal outright would hide a real condition
(GDP-6). What is wrong is the CADENCE: an import-time gate that fires on
every hook subprocess (PreToolUse, PostToolUse, SubagentStop, ...)
re-announces an UNCHANGED verdict every single call.

Fix (`src/des/runtime/freshness.py` `_should_emit_degrade` /
`_record_degrade_emitted` / `_degrade_loud`): throttle to one emission per
`(state)` per `_DEGRADE_THROTTLE_SECONDS` (1800s) window, persisted in a
sentinel file next to the audit sink. A STATE TRANSITION always breaks
through immediately and unthrottled -- this is the GDP-8 arity corollary
applied to volume: suppress an unchanged repeat, never a change.

This regression test did not exist when the throttle landed (commit
`ccf1b9d41`, `fix(des): throttle freshness degrade-loud emissions per state
per 30min`) -- the fix shipped without a companion test
(`mcp__tsunami__reads_of` / grep confirmed `_should_emit_degrade` had zero
test readers). Closing that gap here, after the fact: this test FAILS if the
throttle machinery is reverted (proven by the `_no_throttle` control below
using a zero-second window) and PASSES against the shipped code.

Driving surface: `des.runtime.freshness.assert_fresh_or_explain` via its
documented `probe` injection seam + `NWAVE_FRESHNESS_FORCE_GATE=1` (bypasses
the `.git`-adjacency autoskip so the four-state classifier runs
deterministically regardless of this repo checkout's own `.git/`) +
`suppress_git_autoskip=True` (the hook-path caller shape that reaches the
degrade-loud branch at all -- the CLI path REFUSEs instead, see
`test_freshness_refusal_has_human_line_and_apt_remediation.py`).
`DES_AUDIT_LOG_DIR` is redirected to `tmp_path` so the throttle sentinel
(which lives next to the audit sink, `_degrade_sentinel_path()`) and the
persisted audit record are both isolated per test -- no shared state with
this repo's real `.nwave/des/logs/`.
"""

from __future__ import annotations

import json

import pytest

from des.ports.driven_ports.freshness_port import FreshnessVerdict
from des.runtime.freshness import assert_fresh_or_explain


class _FakeProbe:
    """Test-only `FreshnessProbe` -- returns a pre-built verdict, then a
    second one on re-invocation if `verdicts` has more than one entry.

    Mirrors the seam already established by
    `test_freshness_refusal_has_human_line_and_apt_remediation.py`.
    """

    def __init__(self, *verdicts: FreshnessVerdict) -> None:
        self._verdicts = list(verdicts)
        self._calls = 0

    def probe(self) -> FreshnessVerdict:
        verdict = self._verdicts[min(self._calls, len(self._verdicts) - 1)]
        self._calls += 1
        return verdict


_STALE_VERDICT = FreshnessVerdict(
    state="STALE",
    reason="installed src/des diverges from the live repo tree",
)
_CONFIG_DRIFT_VERDICT = FreshnessVerdict(
    state="CONFIG_DRIFT",
    reason="shipped config asset diverges from the live repo tree",
)


def _run_hook_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object, probe: _FakeProbe
) -> str:
    """Invoke `assert_fresh_or_explain` the way the hook adapter does
    (`suppress_git_autoskip=True`, degrade-loud never sys.exit) and return
    everything printed to stderr for this one call.

    Redirects the audit sink (and therefore the throttle sentinel that lives
    next to it) to `tmp_path` so each test starts with a clean, isolated
    throttle state -- no cross-test or cross-run contamination.
    """
    import sys
    from io import StringIO

    monkeypatch.setenv("NWAVE_FRESHNESS_FORCE_GATE", "1")
    monkeypatch.setenv("DES_AUDIT_LOG_DIR", str(tmp_path))
    monkeypatch.delenv("NWAVE_FRESHNESS", raising=False)

    captured = StringIO()
    monkeypatch.setattr(sys, "stderr", captured)
    assert_fresh_or_explain(probe=probe, suppress_git_autoskip=True)
    return captured.getvalue()


def _events_named(stderr_text: str, event_name: str) -> list[dict[str, object]]:
    events = []
    for raw_line in stderr_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("event") == event_name:
            events.append(payload)
    return events


def _stale_events(stderr_text: str) -> list[dict[str, object]]:
    return _events_named(stderr_text, "des.runtime.freshness.stale")


# ---------------------------------------------------------------------------
# Oracle A -- an unchanged repeat within the window is throttled to silence.
# ---------------------------------------------------------------------------


def test_second_stale_call_within_the_window_emits_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    """Two back-to-back hook-path calls with the SAME STALE verdict must
    emit the advisory exactly once -- the second call is a silent no-op
    (still PROCEED, no stderr, no second audit record).

    This is the exact shape of the measured defect: consecutive hook
    subprocesses (PreToolUse, PostToolUse, ...) probing an unchanged,
    still-stale install must not each re-announce it.
    """
    probe = _FakeProbe(_STALE_VERDICT, _STALE_VERDICT)

    first_stderr = _run_hook_path(monkeypatch, tmp_path, probe)
    second_stderr = _run_hook_path(monkeypatch, tmp_path, probe)

    assert len(_stale_events(first_stderr)) == 1, (
        "WHAT: the first STALE call did not emit exactly one advisory event. "
        "WHY: the FIRST occurrence of a real condition must never be "
        "suppressed (GDP-6, degrade-loud). "
        f"HOW: check `_should_emit_degrade` fail-open path. got "
        f"stderr={first_stderr!r}"
    )
    assert second_stderr == "", (
        "WHAT: a second call with the SAME STALE verdict, inside the "
        "30-minute throttle window, printed to stderr. "
        "WHY: `_should_emit_degrade` (src/des/runtime/freshness.py) must "
        "suppress an unchanged repeat within `_DEGRADE_THROTTLE_SECONDS` -- "
        "re-announcing an unchanged verdict on every hook subprocess is "
        "exactly the measured defect (14,378 emissions / 8 days). "
        "HOW: verify `_record_degrade_emitted` persisted the sentinel after "
        f"the first call. got stderr={second_stderr!r}"
    )


# ---------------------------------------------------------------------------
# Oracle B -- a state TRANSITION always breaks through, never throttled.
# ---------------------------------------------------------------------------


def test_state_transition_breaks_through_the_throttle_immediately(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    """STALE -> CONFIG_DRIFT is a real change in the system, not a repeat --
    it must emit immediately, unthrottled, even though the sentinel was just
    written by the STALE call a moment earlier.

    GDP-8 arity corollary applied to volume: suppress an unchanged repeat,
    never a change.
    """
    stale_probe = _FakeProbe(_STALE_VERDICT)
    drift_probe = _FakeProbe(_CONFIG_DRIFT_VERDICT)

    stale_stderr = _run_hook_path(monkeypatch, tmp_path, stale_probe)
    drift_stderr = _run_hook_path(monkeypatch, tmp_path, drift_probe)

    assert _stale_events(stale_stderr), "setup: the STALE call must emit first"

    drift_events = _events_named(drift_stderr, "des.runtime.freshness.config-drift")
    assert drift_events, (
        "WHAT: the CONFIG_DRIFT call, immediately after a throttled STALE "
        "call, printed no advisory. "
        "WHY: a state TRANSITION must NEVER be throttled -- it is a change, "
        "not a repeat (GDP-8 arity corollary). Throttling it here would "
        "hide a real, different condition behind the previous state's "
        "sentinel. "
        "HOW: `_should_emit_degrade` must compare `record.get('state') == "
        "state` before applying the elapsed-time check. "
        f"got stderr={drift_stderr!r}"
    )


# ---------------------------------------------------------------------------
# Negative AT -- a corrupt/missing sentinel must fail OPEN (still emits),
# never silently swallow a first-seen condition.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_missing_sentinel_fails_open_to_emitting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    """The wrong outcome under test: a throttle-machinery bug (no sentinel
    written yet, or a corrupt one) silently swallowing the very first
    occurrence of a real STALE condition. It must instead fail OPEN --
    emit, exactly like the always-first-call path.
    """
    probe = _FakeProbe(_STALE_VERDICT)

    stderr_text = _run_hook_path(monkeypatch, tmp_path, probe)

    assert _stale_events(stderr_text), (
        "the wrong outcome under test: a fresh throttle sentinel (nothing "
        "written yet in this isolated tmp_path) must fail OPEN to emitting, "
        "not silently swallow the first-seen STALE condition -- got no "
        f"advisory event. stderr={stderr_text!r}"
    )
