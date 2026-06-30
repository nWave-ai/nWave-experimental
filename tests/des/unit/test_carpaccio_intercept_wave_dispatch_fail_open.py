"""Unit tests for the slice-05 wave-dispatch guard fail-OPEN wiring.

f-nonbypassable-attestation slice-05 (DDD-8) -- closes the §22.0 DELIVER-review
BLOCKER: the intercept-side fail-OPEN wiring of the wave-dispatch guard had
ZERO tests. The guard gates EVERY Agent/Task dispatch the PreToolUse intercept
sees, so the fail-OPEN mapping is safety-critical: a future edit flipping
`== 1` to `!= 0`, or dropping a fail-OPEN branch, would brick ALL legitimate
dispatches while the suite stayed green. These regression-guards pin the
contract so such a regression goes RED instead of silently bricking dispatch.

The code under test EXISTS and is correct, so every case here is GREEN at HEAD.

Two distinct seams are pinned, because the fail-OPEN contract is split across
two collaborators:

  1. ``_real_wave_dispatch_runner`` -- the exit-code -> fail-OPEN mapping. The
     guard runner converts every non-BLOCK gate outcome (ALLOW 0, malformed 2,
     any module-absent / freshness-autoskip non-{0,1}, a subprocess timeout, a
     staging OSError) to exit 0 (allow); ONLY a definite off-spine BLOCK (gate
     exit 1) is surfaced as exit 1. This is the literal `== 1` line + the
     fail-OPEN branches. Driven by stubbing the runner's subprocess boundary.

  2. ``evaluate_atdd_pure_dispatch`` composition routing -- the dispatcher
     halts on ANY non-zero runner exit (`on_failure: block`), so the runner's
     fail-OPEN mapping (collapsing 2/timeout/OSError to 0) is what keeps a
     guard malfunction from halting the composition. At the composition layer
     a runner exit 1 routes to a `WaveDispatchGateRejected` block (the ONLY
     block path); a runner exit 0 lets the dispatch continue to the readiness
     + carpaccio gates. Driven by injecting a fake `wave_dispatch_runner`.

Port-to-port: the driving port is `evaluate_atdd_pure_dispatch` (intercept
seam); the runner builder `_real_wave_dispatch_runner` is the in-house guard
adapter whose subprocess boundary is the only injected I/O. No real subprocess
is spawned -- the fake runner / stubbed `subprocess.run` IS the input, the
returned exit code / `InterceptDecision` is the observable.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import des.adapters.drivers.hooks.carpaccio_intercept as ci
from des.adapters.drivers.hooks.carpaccio_intercept import (
    InterceptDecision,
    _real_wave_dispatch_runner,
    evaluate_atdd_pure_dispatch,
)


_FEATURE_ID = "demo-feature"
_SUBAGENT_TYPE = "nw-solution-architect"


def _atdd_pure_prompt(slice_id: str = "slice-01") -> str:
    """A valid atdd_pure A_GREEN_ATS dispatch prompt that reaches the gate stack."""
    return (
        "<!-- DES-VALIDATION : required -->\n"
        "<!-- DES-MODE : atdd_pure -->\n"
        "<!-- DES-PHASE : A_GREEN_ATS -->\n"
        f"<!-- DES-SLICE : {slice_id} -->\n"
        f"<!-- DES-PROJECT-ID : {_FEATURE_ID} -->\n"
    )


class _FakeCompleted:
    """A stand-in for `subprocess.CompletedProcess` carrying a chosen exit code."""

    def __init__(self, returncode: int) -> None:
        self.returncode = returncode
        self.stdout = '{"event": "WaveDispatchGuardStub"}'


# --- Seam 1: _real_wave_dispatch_runner exit-code -> fail-OPEN mapping --------
#
# The runner converts the gate's RAW exit code into the dispatcher-facing exit
# code. ONLY a definite off-spine BLOCK (gate exit 1) survives as exit 1; every
# other outcome is mapped to exit 0 (allow). The allow-cases are parametrized so
# a future edit dropping any single fail-OPEN branch reds exactly one case.


@pytest.mark.parametrize(
    "gate_exit",
    [
        pytest.param(0, id="allow-clean"),
        pytest.param(2, id="malformed-input"),
        pytest.param(78, id="module-absent-non-0-1"),
        pytest.param(124, id="autoskip-non-0-1"),
    ],
)
def test_real_runner_maps_non_block_gate_exit_to_allow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, gate_exit: int
) -> None:
    """(c) A non-BLOCK gate exit (ALLOW / malformed / module-absent) -> allow (0).

    Fail-OPEN: a guard that does not DEFINITELY block (exit 1) never halts the
    dispatch -- it returns exit 0 so the composition continues.
    """
    monkeypatch.setattr(ci.subprocess, "run", lambda *a, **k: _FakeCompleted(gate_exit))

    runner = _real_wave_dispatch_runner(tmp_path)
    returned_exit, _ = runner(_SUBAGENT_TYPE, _atdd_pure_prompt())

    assert returned_exit == 0


def test_real_runner_passes_through_definite_block_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(a) A definite off-spine BLOCK (gate exit 1) is surfaced unchanged as exit 1.

    This is the literal `== 1` line: the ONLY exit code that survives as a
    block. Flipping it to `!= 0` would red this test (exit 0/2 would block).
    """
    monkeypatch.setattr(ci.subprocess, "run", lambda *a, **k: _FakeCompleted(1))

    runner = _real_wave_dispatch_runner(tmp_path)
    returned_exit, _ = runner(_SUBAGENT_TYPE, _atdd_pure_prompt())

    assert returned_exit == 1


def test_real_runner_fails_open_on_subprocess_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(c) A guard subprocess timeout -> allow (0). A slow guard never bricks."""

    def _raise_timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="verify-wave-dispatch", timeout=20)

    monkeypatch.setattr(ci.subprocess, "run", _raise_timeout)

    runner = _real_wave_dispatch_runner(tmp_path)
    returned_exit, _ = runner(_SUBAGENT_TYPE, _atdd_pure_prompt())

    assert returned_exit == 0


def test_real_runner_fails_open_when_prompt_staging_raises_oserror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(c) A prompt-staging OSError -> allow (0). A guard staging failure never blocks.

    The runner writes the prompt to a hermetic temp FILE for the gate's
    `--prompt-path`; if that write raises OSError (e.g. disk full), the guard
    fails OPEN before ever spawning the subprocess.
    """

    def _raise_oserror(self, *_args, **_kwargs):
        raise OSError("simulated disk-full on prompt staging")

    monkeypatch.setattr(Path, "write_text", _raise_oserror)

    runner = _real_wave_dispatch_runner(tmp_path)
    returned_exit, _ = runner(_SUBAGENT_TYPE, _atdd_pure_prompt())

    assert returned_exit == 0


# --- Seam 2: evaluate_atdd_pure_dispatch composition routing ------------------
#
# A fake `wave_dispatch_runner` is injected so no real subprocess is spawned.
# The dispatcher halts on ANY non-zero runner exit (`on_failure: block`); the
# runner's own fail-OPEN mapping (Seam 1) is what guarantees only a definite
# block ever reaches the dispatcher as non-zero. Here we pin the routing of the
# runner's returned exit code to the `InterceptDecision`.


def test_composition_blocks_when_runner_returns_definite_block(tmp_path: Path) -> None:
    """(a) A wave_dispatch_runner exit 1 routes to a WaveDispatchGateRejected block.

    This is the ONLY block path through the wave-dispatch guard.
    """
    decision = evaluate_atdd_pure_dispatch(
        prompt=_atdd_pure_prompt("slice-01"),
        feature_id=_FEATURE_ID,
        project_root=tmp_path,
        subagent_type=_SUBAGENT_TYPE,
        wave_dispatch_runner=lambda _t, _p: (1, '{"event": "WaveOwnerOffSpine"}'),
        readiness_runner=lambda _f, _s: (0, ""),
        carpaccio_runner=lambda _f, _s: (0, "{}"),
    )

    assert decision.is_block
    assert decision.event == "WaveDispatchGateRejected"


def test_composition_allows_when_runner_returns_allow(tmp_path: Path) -> None:
    """(b) A wave_dispatch_runner exit 0 lets the dispatch continue (not blocked).

    The dispatch flows on to the readiness + carpaccio gates (both cleared
    here), so the final decision is allow -- the guard did not brick it.
    """
    decision = evaluate_atdd_pure_dispatch(
        prompt=_atdd_pure_prompt("slice-01"),
        feature_id=_FEATURE_ID,
        project_root=tmp_path,
        subagent_type=_SUBAGENT_TYPE,
        wave_dispatch_runner=lambda _t, _p: (0, "{}"),
        readiness_runner=lambda _f, _s: (0, ""),
        carpaccio_runner=lambda _f, _s: (0, "{}"),
    )

    assert decision == InterceptDecision.allow()
