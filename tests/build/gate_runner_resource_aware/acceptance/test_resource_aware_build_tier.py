"""Acceptance tests -- resource-aware build-tier gate (DISTILL, slice-01).

Feature-delta: docs/feature/gate-runner-resource-aware/feature-delta.md
  Wave: DESIGN / [REF] Architecture & Contract + [REF] Slice Plan (slice-01)

Defect (GDP-6 false-red): the commit-slice BuildTier's heavy pytest
subprocess, spawned by ``_run_arch_invariant_set`` inside
``src/des/cli/run_contract_gate.py``, is killed by the OS (OOM/earlyoom) under
resource contention. Today the worker's absent result line makes
``_run_arch_invariant_set`` raise ``_CollectionError``, which
``build_tier_exit_verdict`` maps to ``BuildTierRefused`` reason
``worker-failed`` -- a load-induced kill reported as a code defect. Wanted
(this slice, both halves witnessed by this ONE file per the Slice Plan
justification): (a) a pre-launch resource window (``/proc/meminfo``
MemAvailable + ``/proc/loadavg`` load1) that waits-and-polls with progress
before spawning, or gives up INDETERMINATE naming observed resources +
threshold + retry when it never opens; (b) a post-run classifier that
recognises a signal-killed / OOM-exit-coded (137/143) subprocess as
INDETERMINATE-resource-starvation (never red), while a genuinely completed
run with real failures still refuses, node ids named (unchanged).

Locus (Reuse Analysis EXTEND, not a new spawn site): the ONE place the heavy
pytest subprocess is spawned is ``_run_arch_invariant_set`` -> ``subprocess.
run`` inside ``src/des/cli/run_contract_gate.py``; the verdict-shaping
composition root is ``build_tier_exit_verdict(repo) -> int`` in the same
module (imported by ``des.cli.commit_slice`` at its build-tier exit check).

DESIGN PIN this AT establishes (necessary -- no prior slice fixed the
injectable seam): ``build_tier_exit_verdict`` gains THREE new keyword-only
parameters (ADD-not-mutate -- existing positional callers, e.g.
``commit_slice.py``'s ``build_tier_exit_verdict(repo)``, are untouched):

    def build_tier_exit_verdict(
        repo: Path,
        *,
        output: OutputPort | None = None,
        resource_readings: Iterable[tuple[int, float]] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> int:

  * ``output`` -- routes every ``_emit(...)`` call through the injected
    ``OutputPort`` (the SAME in-process capture contract
    ``des.testing.output_capture.CapturingOutput`` already realises for
    ``main()``; ``None`` keeps writing to ``sys.stdout``, zero behaviour
    change for the existing caller).
  * ``resource_readings`` -- an iterable of ``(mem_available_mib, load1)``
    pairs; the pre-launch window consumes ONE per poll attempt until a
    reading clears the threshold (MemAvailable > 700 MiB AND load1 below the
    configured ceiling) or the iterable is exhausted (the bounded-wait budget
    -- exhaustion IS the bound, no wall-clock needed in the injectable path).
    ``None`` reads real ``/proc/meminfo`` + ``/proc/loadavg`` (production
    default, degrade-open off-Linux per the design's GDP-7 note).
  * ``sleep_fn`` -- replaces ``time.sleep`` between polls (progress line
    emitted per poll, GDP-3). ``None`` uses real ``time.sleep``.

Active-RED scaffolding (hidden-signature-probe, ``nw-distill-red-scaffolding``
P1-P4 applied to a kwarg-extension rather than a new symbol): the module
imports ONLY the STABLE, ALREADY-PRESENT names
(``build_tier_exit_verdict``, ``_RUN_RESULT_PREFIX``, the ``run_contract_gate``
module itself, ``des.testing.output_capture.CapturingOutput``) at module top
-- nothing absent is imported, so collection is clean (never BROKEN). The
missing functionality is reached at RUNTIME inside ``_drive_gate`` -- calling
``build_tier_exit_verdict(repo, output=..., resource_readings=...,
sleep_fn=...)`` raises ``TypeError: ... got an unexpected keyword argument
'output'`` at HEAD (verified empirically before authoring). ``_drive_gate``
catches exactly that ``TypeError`` shape and re-raises a semantic
``AssertionError`` (MISSING_FUNCTIONALITY) -- so every current-slice test
RED-fails for the right reason, never a collection error.

Driving surface (Mandate-13 driving-port-only): every test drives the REAL
composition-root entry ``build_tier_exit_verdict(repo, ...)`` IN-PROCESS (a
direct call, no interpreter fork -- Layer 3 composition). The only faked
surfaces are the external/non-deterministic ports (Pillar 3): the heavy
pytest subprocess (``subprocess.run``, monkeypatched -- the AT never actually
spawns or starves a real process), the resource readings (injected instead of
reading the real, non-deterministic ``/proc``), the poll sleep, and the
terminal output sink (``CapturingOutput``). ``repo`` is a real ``tmp_path``
carrying a real ``tests/build`` directory (real-IO for the one read
``_arch_invariant_paths`` performs).

CONTRACT_SHAPE: bounded-change for every scenario -- ``build_tier_exit_verdict``
maps a bounded set of inputs (resource readings, subprocess outcome) to one of
a closed set of verdicts (BuildTierVerified / BuildTierRefused / the
INDETERMINATE-resource-starvation lane); it also performs the one bounded
side-effect of spawning (or not spawning) the heavy subprocess.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import Mock

import pytest

from des.cli import run_contract_gate
from des.cli.run_contract_gate import _RUN_RESULT_PREFIX, build_tier_exit_verdict
from des.testing.output_capture import CapturingOutput


# WHY -- a single fine reading (well above the 700 MiB / load1 design default)
# so tests NOT exercising the pre-launch window never trigger a wait as a side
# effect (the wait/never-wait behaviour is pinned by its own dedicated tests).
_FINE_READING = (900, 1.0)

_MISSING_FUNCTIONALITY_MESSAGE = (
    "MISSING_FUNCTIONALITY: build_tier_exit_verdict(repo, ...) does not yet "
    "accept the output=/resource_readings=/sleep_fn= keyword arguments "
    "(feature-delta slice-01, "
    "docs/feature/gate-runner-resource-aware/feature-delta.md "
    "[REF] Architecture & Contract). Extend its signature keyword-only "
    "(ADD-not-mutate -- existing positional callers stay untouched): "
    "output: OutputPort | None = None (route _emit() through it); "
    "resource_readings: Iterable[tuple[int, float]] | None = None "
    "((mem_available_mib, load1) pairs, one consumed per poll before "
    "spawning; None reads real /proc/meminfo + /proc/loadavg); "
    "sleep_fn: Callable[[float], None] | None = None (replaces time.sleep "
    "between polls, None uses real time.sleep). "
    "Re-check with: uv run pytest "
    "tests/build/gate_runner_resource_aware/acceptance/"
    "test_resource_aware_build_tier.py -q"
)


@dataclass(frozen=True)
class _GateRun:
    """The observable outcome of driving ``build_tier_exit_verdict`` once."""

    exit_code: int
    events: list[dict[str, object]] = field(default_factory=list)
    sleep_calls: list[float] = field(default_factory=list)
    spawn_calls: int = 0

    def event_names(self) -> list[object]:
        return [event.get("event") for event in self.events]

    def last_event(self) -> dict[str, object]:
        assert self.events, "the gate must emit at least one event -- got none"
        return self.events[-1]

    def event_named(self, name: str) -> dict[str, object]:
        for event in self.events:
            if event.get("event") == name:
                return event
        raise AssertionError(f"no {name!r} event among {self.events}")


def _drive_gate(
    repo: Path,
    *,
    resource_readings: Iterable[tuple[int, float]],
    spawn_result: subprocess.CompletedProcess[str] | None,
    monkeypatch: pytest.MonkeyPatch,
) -> _GateRun:
    """Drive the REAL ``build_tier_exit_verdict(repo, ...)`` composition root.

    Fakes exactly the external/non-deterministic ports (Pillar 3): the heavy
    subprocess spawn (``subprocess.run`` inside ``run_contract_gate``,
    monkeypatched to a ``Mock`` -- never a real process), the resource
    readings, and the poll sleep. Everything else is the real gate logic.
    """
    output = CapturingOutput()
    spawn = Mock(return_value=spawn_result)
    monkeypatch.setattr(run_contract_gate.subprocess, "run", spawn)
    sleep_calls: list[float] = []
    try:
        exit_code = build_tier_exit_verdict(
            repo,
            output=output,
            resource_readings=iter(resource_readings),
            sleep_fn=sleep_calls.append,
        )
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            raise
        raise AssertionError(_MISSING_FUNCTIONALITY_MESSAGE) from exc
    events = [json.loads(line) for line in output.lines]
    return _GateRun(
        exit_code=exit_code,
        events=events,
        sleep_calls=sleep_calls,
        spawn_calls=spawn.call_count,
    )


@pytest.fixture
def repo_with_build_tier(tmp_path: Path) -> Path:
    """A repo carrying a ``tests/build`` directory (the spawn itself is faked)."""
    (tmp_path / "tests" / "build").mkdir(parents=True)
    (tmp_path / "tests" / "build" / "__init__.py").touch()
    return tmp_path


def _killed_process(returncode: int) -> subprocess.CompletedProcess[str]:
    """A ``CompletedProcess`` mimicking a signal-killed / OOM-exit-coded worker.

    No ``NWAVE_RUN_SCOPE:`` result line -- exactly what a worker that never
    reached its own result-emitting code (because the OS killed it mid-run)
    produces.
    """
    return subprocess.CompletedProcess(
        args=["pytest"], returncode=returncode, stdout="", stderr="Killed"
    )


def _completed_process(
    *, pytest_exit_code: int, collected: int, failed_node_ids: list[str]
) -> subprocess.CompletedProcess[str]:
    """A ``CompletedProcess`` carrying a genuine ``NWAVE_RUN_SCOPE:`` payload."""
    payload = {
        "pytest_exit_code": pytest_exit_code,
        "collected_count": collected,
        "failed_node_ids": failed_node_ids,
    }
    return subprocess.CompletedProcess(
        args=["pytest"],
        returncode=pytest_exit_code,
        stdout=f"{_RUN_RESULT_PREFIX}{json.dumps(payload)}\n",
        stderr="",
    )


# ---------------------------------------------------------------------------
# T1 -- signal-killed subprocess (SIGKILL, returncode=-9): INDETERMINATE, not
# a refusal.
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


def test_build_tier_signal_killed_subprocess_reports_resource_starvation(
    monkeypatch: pytest.MonkeyPatch, repo_with_build_tier: Path
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: feature-delta Summary + [REF] Architecture & Contract
    ("Starvation classifier (post-run)... returncode is negative (killed by
    signal)... INDETERMINATE-resource-starvation... NEVER a red verdict").
    """
    run = _drive_gate(
        repo_with_build_tier,
        resource_readings=[_FINE_READING],
        spawn_result=_killed_process(-9),
        monkeypatch=monkeypatch,
    )

    assert run.exit_code == 0, (
        f"a signal-killed build-tier subprocess must NEVER refuse the slice "
        f"(GDP-6 false-red) -- expected exit 0 (proceed), got {run.exit_code}. "
        f"events={run.events}"
    )
    assert "BuildTierRefused" not in run.event_names(), (
        f"a signal-killed subprocess (returncode=-9, SIGKILL) must not be "
        f"reported through the red BuildTierRefused lane -- got "
        f"events={run.events}"
    )
    starvation = run.last_event()
    blob = json.dumps(starvation).lower()
    assert "9" in json.dumps(starvation), (
        f"the starvation report must name the observed signal (9) -- got {starvation}"
    )
    assert "retry" in blob or "commit-slice" in blob, (
        f"the starvation report must name a retry command (GDP-3/4) -- got {starvation}"
    )


# ---------------------------------------------------------------------------
# T2 -- OOM-exit-coded worker (137/143, no signal but the shell-convention
# kill codes): same INDETERMINATE lane, never a refusal.
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kill_exit_code", [137, 143])
def test_build_tier_oom_exit_code_reports_resource_starvation(
    monkeypatch: pytest.MonkeyPatch,
    repo_with_build_tier: Path,
    kill_exit_code: int,
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: feature-delta [REF] Architecture & Contract
    ("...or 137/143... INDETERMINATE-resource-starvation").
    """
    run = _drive_gate(
        repo_with_build_tier,
        resource_readings=[_FINE_READING],
        spawn_result=_killed_process(kill_exit_code),
        monkeypatch=monkeypatch,
    )

    assert run.exit_code == 0, (
        f"an OOM-exit-coded ({kill_exit_code}) subprocess must never refuse "
        f"the slice -- expected exit 0, got {run.exit_code}. "
        f"events={run.events}"
    )
    assert "BuildTierRefused" not in run.event_names(), (
        f"exit code {kill_exit_code} must not be reported through the red "
        f"BuildTierRefused lane -- got events={run.events}"
    )
    blob = json.dumps(run.last_event())
    assert str(kill_exit_code) in blob, (
        f"the starvation report must name the observed exit code "
        f"{kill_exit_code} -- got {run.last_event()}"
    )


# ---------------------------------------------------------------------------
# T3 -- a genuinely completed run with real failures: still refused, node
# ids named (the invariant guard -- unchanged behaviour).
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


def test_build_tier_genuine_failure_still_refused_with_node_ids(
    monkeypatch: pytest.MonkeyPatch, repo_with_build_tier: Path
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: feature-delta Summary ("A genuine assertion failure
    under low load stays a genuine FAIL").
    """
    failed_ids = ["tests/build/x.py::test_a", "tests/build/x.py::test_b"]
    run = _drive_gate(
        repo_with_build_tier,
        resource_readings=[_FINE_READING],
        spawn_result=_completed_process(
            pytest_exit_code=1, collected=2, failed_node_ids=failed_ids
        ),
        monkeypatch=monkeypatch,
    )

    assert run.exit_code == 1, (
        f"a genuinely failing build-tier run must still REFUSE the slice "
        f"(exit 1) -- got {run.exit_code}. events={run.events}"
    )
    refusal = run.event_named("BuildTierRefused")
    assert refusal.get("reason") == "arch-invariant-failed", (
        f"expected reason='arch-invariant-failed' -- got {refusal}"
    )
    reported_ids = refusal.get("failed_node_ids", [])
    for node_id in failed_ids:
        assert node_id in reported_ids, (
            f"the refusal must NAME the failing node id {node_id!r} -- got {refusal}"
        )


# ---------------------------------------------------------------------------
# T4 -- below-threshold resources that recover: bounded wait-with-progress,
# then the tier launches.
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


def test_build_tier_waits_for_resources_then_launches(
    monkeypatch: pytest.MonkeyPatch, repo_with_build_tier: Path
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: feature-delta [REF] Architecture & Contract
    ("Below threshold... wait-and-poll (bounded... progress line per poll)
    then proceed").
    """
    readings = [(500, 5.0), (500, 5.0), (900, 1.0)]  # two below, then healthy
    run = _drive_gate(
        repo_with_build_tier,
        resource_readings=readings,
        spawn_result=_completed_process(
            pytest_exit_code=0, collected=1, failed_node_ids=[]
        ),
        monkeypatch=monkeypatch,
    )

    assert len(run.sleep_calls) >= 2, (
        f"two below-threshold readings must trigger a bounded wait-and-poll "
        f"(a sleep between polls) before launching -- expected >= 2 sleep "
        f"calls, got {len(run.sleep_calls)}"
    )
    progress_events = [
        event for event in run.events if "wait" in str(event.get("event", "")).lower()
    ]
    assert progress_events, (
        f"the wait-and-poll loop must emit an observable progress line per "
        f"poll (GDP-3) -- got events={run.events}"
    )
    assert run.spawn_calls == 1, (
        f"once the window opens the build-tier subprocess must launch "
        f"exactly once -- got {run.spawn_calls} spawn call(s)"
    )
    assert run.exit_code == 0, (
        f"the tier launched after the window opened and passed -- expected "
        f"exit 0, got {run.exit_code}. events={run.events}"
    )
    assert "BuildTierVerified" in run.event_names(), (
        f"expected the tier to verify GREEN after the window opened -- got "
        f"events={run.events}"
    )


# ---------------------------------------------------------------------------
# T5 -- resources that never recover: INDETERMINATE naming observed
# resources + threshold + retry, and the subprocess is NEVER launched.
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


def test_build_tier_never_opening_window_reports_indeterminate_without_launching(
    monkeypatch: pytest.MonkeyPatch, repo_with_build_tier: Path
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: feature-delta [REF] Architecture & Contract ("window
    never opens -> exit INDETERMINATE naming the observed resources + the
    threshold + the retry command").
    """
    readings = [(500, 5.0), (500, 5.0), (500, 5.0)]  # exhausted, never healthy
    run = _drive_gate(
        repo_with_build_tier,
        resource_readings=readings,
        spawn_result=None,
        monkeypatch=monkeypatch,
    )

    assert run.spawn_calls == 0, (
        f"a resource window that never opens must NEVER spawn the heavy "
        f"build-tier subprocess -- got {run.spawn_calls} spawn call(s)"
    )
    assert run.exit_code == 0, (
        f"a never-opening window is INDETERMINATE, not a refusal -- expected "
        f"exit 0, got {run.exit_code}. events={run.events}"
    )
    assert "BuildTierRefused" not in run.event_names(), (
        f"a never-opening resource window must never be reported through "
        f"the red BuildTierRefused lane -- got events={run.events}"
    )
    indeterminate = run.last_event()
    blob = json.dumps(indeterminate).lower()
    assert "700" in blob or "mem" in blob, (
        f"the report must name the observed resources + the threshold -- "
        f"got {indeterminate}"
    )
    assert "retry" in blob or "commit-slice" in blob, (
        f"the report must name a retry command (GDP-3/4) -- got {indeterminate}"
    )


# ---------------------------------------------------------------------------
# T6 (negative_at) -- fine resources at the FIRST check: zero waiting, the
# guard does not tax the happy path.
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_build_tier_fine_resources_launches_directly_without_waiting(
    monkeypatch: pytest.MonkeyPatch, repo_with_build_tier: Path
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Negative AT (GS-8): asserts the wrong outcome (a wait) is NOT produced
    when resources are fine from the first check -- the pre-launch guard
    must not tax the happy path.
    """
    run = _drive_gate(
        repo_with_build_tier,
        resource_readings=[_FINE_READING],
        spawn_result=_completed_process(
            pytest_exit_code=0, collected=1, failed_node_ids=[]
        ),
        monkeypatch=monkeypatch,
    )

    assert run.sleep_calls == [], (
        f"fine resources at the FIRST check must never trigger a wait -- "
        f"got {len(run.sleep_calls)} sleep call(s)"
    )
    assert run.spawn_calls == 1, (
        f"fine resources must launch the build-tier subprocess directly -- "
        f"got {run.spawn_calls} spawn call(s)"
    )
    assert run.exit_code == 0, f"expected exit 0 -- got {run.exit_code}"
    assert "BuildTierVerified" in run.event_names(), (
        f"expected BuildTierVerified -- got events={run.events}"
    )
