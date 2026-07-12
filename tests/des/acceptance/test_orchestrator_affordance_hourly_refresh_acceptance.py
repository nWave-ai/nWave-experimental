"""Acceptance tests: 30-MINUTE re-injection of the orchestrator spine-discipline
affordance via the UserPromptSubmit hook.

Ale-ratified problem: `handle_session_start` (session_start_handler.py) injects
the spine-discipline / throughput affordance ONLY at SessionStart/clear/compact.
With a 1M context window, a session can run for hours without ever hitting one
of those anchors, so the discipline silently goes stale. Ale-directed retune
(2026-07-12 verbatim: "aumenta la frequenza del reminder a 30 minuti"): a full
night of hourly re-injection held authorship discipline at 100% but did NOT
prevent driver-level drift -- a long session decays faster than the hourly
cadence refreshes it. Ale now requires >=1 refresh per 30 minutes.

Driving port: `handle_user_prompt_submit()` -- the REAL, already-wired entry
point (`des.adapters.drivers.hooks.user_prompt_submit_handler`, routed by
`hook_router.py` under the `user-prompt-submit` command). Driven in-process
per the project's existing AT convention for hook handlers (see sibling
`test_session_start_handler_acceptance.py`): patched stdin + `capsys`, no
subprocess fork.

GROUNDED DESIGN DECISIONS (tsunami/Read grounding done before authoring --
see dispatch report):

  - Sentinel location: `{project_root}/.nwave/orchestrator-affordance-last-injected`
    -- a marker file whose MTIME (not its JSON body) IS the "last injected at"
    timestamp. This mirrors the ALREADY-SHIPPED idiomatic pattern in
    `HousekeepingService._clean_signal_files` (`.nwave/des/des-task-active*`,
    `threshold_seconds = signal_staleness_hours * 3600`,
    `time_provider.now_utc().timestamp() - mtime`) -- no new timestamp
    encoding is invented for this feature.
  - Hook event: `user-prompt-submit` (`handle_user_prompt_submit`) -- fires on
    every submitted prompt, the natural "next handled hook event" cadence for
    an hourly refresh (`pre-tool-use` fires far more often, once per tool
    call, and is not the per-turn cadence Ale described).
  - Time source: real wall-clock via `os.utime()` to backdate/freshen the
    sentinel's mtime -- `handle_user_prompt_submit` has NO TimeProvider port
    wired today (it is a bare stdin -> stdout function with no DI seam for
    time), so "never wall-clock-*sleep*-in-tests" is honored by never
    sleeping; the elapsed-time precondition is set directly via file mtime,
    exactly as `HousekeepingService` tests do for signal-file staleness.
  - Content: SAME spine-discipline/throughput content as the SessionStart
    injection -- the shipped `nWave/data/orchestrator-affordance/*.md`
    assets, loaded via the EXISTING `load_orchestrator_affordance()` +
    `_ORCHESTRATOR_AFFORDANCE_ASSETS_DIR` (session_start_handler.py). The
    expected text is computed from that real function/asset at test time
    (never a hardcoded prose duplicate), so the AT stays coupled to the real
    shipped content instead of a guess.
  - Degrade-safe: sentinel absent OR corrupt (e.g. a directory sits where a
    file is expected) -> treated as elapsed -> inject, never raise (exit 0
    always, mirroring the handler's existing fail-open discipline elsewhere
    in this hook family).

ACTIVE-RED: `handle_user_prompt_submit` today NEVER prints anything -- it only
arms the wave-active floor via `CommandLiteralWaveActiveAnchor` and returns 0
(see `user_prompt_submit_handler.py`). No hourly-refresh path exists yet.
Every positive scenario below fails with a semantic `AssertionError` (empty
stdout / unwritten sentinel), never an ImportError or collection error --
this file imports ONLY symbols that already exist in production code.

TEST ONLY -- no production code authored in this pass.
"""

from __future__ import annotations

import io
import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest


_SENTINEL_RELATIVE = Path(".nwave") / "orchestrator-affordance-last-injected"
_REFRESH_THRESHOLD_SECONDS = 1800


def _sentinel_path(project_root: Path) -> Path:
    return project_root / _SENTINEL_RELATIVE


def _write_sentinel_with_age(project_root: Path, seconds_ago: float) -> Path:
    """Create the sentinel marker file, backdating its mtime by ``seconds_ago``.

    Real wall-clock arithmetic via ``os.utime`` -- no sleeping, no injected
    fake-time port (none exists on this handler yet).
    """
    sentinel = _sentinel_path(project_root)
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.touch()
    backdated_ts = time.time() - seconds_ago
    os.utime(sentinel, (backdated_ts, backdated_ts))
    return sentinel


def _expected_affordance_text() -> str:
    """The real, currently-shipped SessionStart affordance content.

    Computed via the EXISTING production loader/asset-dir (never a hardcoded
    duplicate) so this AT proves the hourly refresh emits the SAME content the
    SessionStart path already injects.
    """
    from des.adapters.drivers.hooks.session_start_handler import (
        _ORCHESTRATOR_AFFORDANCE_ASSETS_DIR,
        load_orchestrator_affordance,
    )

    text = load_orchestrator_affordance(_ORCHESTRATOR_AFFORDANCE_ASSETS_DIR)
    assert text, (
        "shipped nWave/data/orchestrator-affordance/*.md assets must be "
        "present for this AT to ground its content-parity expectation"
    )
    return text


def _submit_prompt(project_root: Path, prompt: str = "what should I do next?"):
    """Drive the real `handle_user_prompt_submit()` entry point in-process.

    Uses a non-`/nw-<wave>` prompt so `CommandLiteralWaveActiveAnchor` never
    arms the wave-active floor -- keeps `project_root` free of incidental
    writes unrelated to the sentinel under test.
    """
    from des.adapters.drivers.hooks.user_prompt_submit_handler import (
        handle_user_prompt_submit,
    )

    stdin_payload = json.dumps({"prompt": prompt, "cwd": str(project_root)})
    with patch("sys.stdin", io.StringIO(stdin_payload)):
        exit_code = handle_user_prompt_submit()
    return exit_code


class TestOrchestratorAffordanceHourlyRefreshAcceptance:
    """AC: the orchestrator spine-discipline affordance re-injects every 30
    minutes via the UserPromptSubmit hook, not just at SessionStart/clear/compact."""

    def test_elapsed_sentinel_reinjects_affordance_on_next_prompt(
        self, tmp_path, capsys
    ):
        """AC: sentinel older than 30 minutes -> the next submitted prompt
        re-injects the SAME spine-discipline content as additionalContext."""
        project_root = tmp_path
        _write_sentinel_with_age(
            project_root, seconds_ago=_REFRESH_THRESHOLD_SECONDS + 1
        )
        expected_text = _expected_affordance_text()

        exit_code = _submit_prompt(project_root)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert captured.out.strip(), (
            "expected 30-minute re-injection additionalContext on a stale "
            "sentinel, got no stdout output"
        )
        output = json.loads(captured.out.strip())
        ctx = output["hookSpecificOutput"]["additionalContext"]
        assert output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
        assert expected_text in ctx, (
            "re-injected content must be the SAME spine-discipline/throughput "
            "text as the SessionStart affordance, not a different payload"
        )

    def test_elapsed_reinjection_refreshes_sentinel_mtime(self, tmp_path, capsys):
        """AC (chained from the prior scenario): after a triggered
        re-injection, the sentinel's mtime is updated to "now" so the next
        immediate prompt does not re-fire."""
        project_root = tmp_path
        sentinel = _write_sentinel_with_age(
            project_root, seconds_ago=_REFRESH_THRESHOLD_SECONDS + 1
        )
        before_call_ts = time.time()

        _submit_prompt(project_root)

        assert sentinel.exists(), "sentinel must still exist after re-injection"
        refreshed_mtime = sentinel.stat().st_mtime
        assert refreshed_mtime >= before_call_ts, (
            "re-injection must rewrite the sentinel's mtime to (approximately) "
            "now, not leave the stale backdated timestamp in place"
        )

    def test_fresh_sentinel_not_reinjected_within_the_threshold(self, tmp_path, capsys):
        """Negative AT: sentinel written 60s ago (<< 30min elapsed) -> the
        next prompt must NOT re-inject the affordance."""
        project_root = tmp_path
        _write_sentinel_with_age(project_root, seconds_ago=60)

        exit_code = _submit_prompt(project_root)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert captured.out.strip() == "", (
            "no re-injection expected within the 30-minute threshold -- "
            "refresh must not fire on every UserPromptSubmit event"
        )

    def test_sentinel_just_under_the_threshold_boundary_not_reinjected(
        self, tmp_path, capsys
    ):
        """Negative AT (boundary): sentinel backdated to 1799s (just under the
        1800s/30-minute threshold) -> still no re-injection."""
        project_root = tmp_path
        _write_sentinel_with_age(
            project_root, seconds_ago=_REFRESH_THRESHOLD_SECONDS - 1
        )

        exit_code = _submit_prompt(project_root)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert captured.out.strip() == "", (
            "1799s elapsed is still under the 1800s threshold -- must not re-inject yet"
        )

    def test_missing_sentinel_degrades_to_elapsed_and_injects(self, tmp_path, capsys):
        """Degrade-safe AT: no sentinel file at all (first-ever prompt, or a
        pre-feature project) -> treated as elapsed -> injects AND creates the
        sentinel, never crashes."""
        project_root = tmp_path
        assert not _sentinel_path(project_root).exists()
        expected_text = _expected_affordance_text()

        exit_code = _submit_prompt(project_root)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert captured.out.strip(), (
            "a missing sentinel must degrade to 'elapsed' and inject the "
            "affordance, not silently stay quiet forever"
        )
        output = json.loads(captured.out.strip())
        ctx = output["hookSpecificOutput"]["additionalContext"]
        assert expected_text in ctx
        assert _sentinel_path(project_root).exists(), (
            "the sentinel must be written after injecting on a missing-sentinel "
            "first run, so the NEXT prompt can correctly measure elapsed time"
        )

    def test_corrupt_sentinel_degrades_to_elapsed_without_crashing(
        self, tmp_path, capsys
    ):
        """Degrade-safe AT: sentinel path occupied by a directory (corrupt
        state) -> treated as elapsed, hook still exits 0 (fail-open) and still
        injects -- never raises."""
        project_root = tmp_path
        corrupt_sentinel = _sentinel_path(project_root)
        corrupt_sentinel.parent.mkdir(parents=True, exist_ok=True)
        corrupt_sentinel.mkdir()  # a directory where a file is expected
        expected_text = _expected_affordance_text()

        exit_code = _submit_prompt(project_root)

        assert exit_code == 0, (
            "a corrupt sentinel must never crash the hook -- fail-open, exit 0"
        )
        captured = capsys.readouterr()
        assert captured.out.strip(), (
            "a corrupt sentinel must degrade to 'elapsed' and still inject "
            "the affordance rather than silently going dormant forever"
        )
        output = json.loads(captured.out.strip())
        ctx = output["hookSpecificOutput"]["additionalContext"]
        assert expected_text in ctx


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
