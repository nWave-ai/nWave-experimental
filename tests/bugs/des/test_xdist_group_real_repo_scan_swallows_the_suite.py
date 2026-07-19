"""Regression AT -- the `real_repo_scan` xdist_group swallows the majority of
the full-suite wall-clock budget, AND the isolation it substitutes for is not
actually wired where it matters.

RCA (measured, not re-derived here -- see the feature ticket for the full
timing pass):

    `tests/conftest.py:1495-1501` pins every test whose module (or sibling
    `*composition*.py` / `*steps*/` module) drives a `cwd=<real repo>`
    subprocess onto `pytest.mark.xdist_group("real_repo_scan")`. Under
    `--dist loadgroup` every member of a group runs on ONE worker, serialized.
    Measured: that group holds 1264s of a 1491s pass = 84.7% of total test
    weight -- so `-n auto` buys ~1x at full-suite scale (8084 items, 25m15s
    wall, 4-core box, target 5min / ceiling 10min) while paying full xdist
    overhead, even though unit-only runs get the expected ~2x (89.4s serial
    -> 44.2s at -n4).

    The detector (`tests/conftest.py:1301-1414`) is a regex over SOURCE TEXT
    matching `cwd=REPO_ROOT|PROJECT_ROOT|_repo_root()|Path.cwd()`, scanned
    against the test's own module PLUS its directory's `*composition*.py` and
    `*steps*/` siblings -- BDD suites keep the actual subprocess call in a
    shared composition/step module, so ONE matching module pins the WHOLE
    directory. Reproduced here (deterministic, static, no timing needed):
    249 of 1220 `test_*.py` files (20.4%) match the sibling-expanded detector,
    versus only 30 of 1220 (2.5%) matching a DIRECT `cwd=<real repo>` call in
    their own module -- an ~8.3x over-approximation from the directory-wide
    expansion.

    The marker exists for a REAL reason (commit 25bc00d35, 2026-06-21): these
    tests drive actual `des` CLI subprocesses against the repo root, sharing
    mutable `.nwave` state (`.nwave/wave-active/active.json`, the wave floor
    `PreToolUseService._read_active_wave()` reads via `Path.cwd()` --
    `src/des/application/pre_tool_use_service.py:508`). Two such tests landing
    on the same xdist worker collide on that shared on-disk state; the fix
    at the time was correct (serialize them) and its commit message recorded
    "No slowdown (466s -> 458s)" -- true at 5630 items, false at 8084. The
    safety measure was never re-measured as the suite grew.

WHAT THIS FILE GUARDS -- both halves, deliberately in ONE module so neither
gets "fixed" without the other:

  (a) `test_real_repo_scan_group_does_not_dominate_collected_items` --
      the serialized lane must not silently swallow the majority of the
      suite AGAIN. Deterministic observable: the FRACTION OF COLLECTED ITEMS
      pinned to the `real_repo_scan` xdist_group (never wall-clock seconds --
      machine-dependent and would itself become a source of flakiness). This
      mirrors exactly what `--dist loadgroup` schedules on: item membership,
      not file count or timing.

      THRESHOLD: 10% of collected items (`unit or integration or acceptance`
      selection). CURRENT measured value: 1339 of 7809 items = 17.15% --
      reproduced live by this test on every run, not a hardcoded snapshot.
      JUSTIFICATION: the RCA's own timing pass gives an empirical per-item
      cost ratio between group and non-group items:
        group:      1264s / 1339 items = 0.944s/item
        non-group:   227s / 6470 items = 0.0351s/item
        ratio:      0.944 / 0.0351 ~= 26.9x
      i.e. group items are ~27x more expensive on average (subprocess spawns
      vs in-memory calls) -- which is EXACTLY why 17.15% of items already
      costs 84.7% of wall time (0.1715*26.9 / (0.1715*26.9 + 0.8285) = 84.7%,
      matching the measurement). At the chosen 10% ceiling, the SAME cost
      ratio still implies ~75% of wall time is serialized -- so 10% is
      explicitly a NECESSARY-not-sufficient floor: it catches "the group grew
      back to (or past) today's size," it does NOT certify the suite hits its
      5-10min target. It is set comfortably below today's 17.15% (a ~42%
      required reduction) so the test is RED now, for the measured reason,
      and gives the fix a concrete, non-hand-wavy number to beat. Achieving
      the actual wall-clock target requires shrinking the GROUP (tighter
      detection than "one matching sibling pins the whole directory" -- see
      the 249-vs-30-file gap above) and/or removing the need for serialization
      (isolating the shared `.nwave` state the group protects) -- that is the
      fix's job, not this test's.

  (b) `test_pre_tool_use_service_does_not_honor_des_project_dir_override` --
      whatever REPLACES the serialization must PRESERVE isolation. A fix that
      dissolves/shrinks the group without isolating `.nwave` state per-test
      re-opens the EXACT order-dependent corruption 25bc00d35 fixed -- and the
      symptom is flakiness: false reds indistinguishable from real
      regressions, false greens that ship defects. A suite that is fast and
      untrustworthy is worse than one that is slow and honest, so a
      regression test that only asserts speed would invite exactly that.

      This test proves, behaviourally (through the real driving port
      `PreToolUseService.validate()`, real `WaveActiveFilesystemStore`, no
      fakes on the seam under test), that the per-test isolation mechanism
      ALREADY BUILT for this (`DES_PROJECT_DIR` / `resolve_nwave_root()` --
      DDD-14/DDD-15, `src/des/domain/nwave_root.py`) is NOT wired into the one
      production call site the group-pin's own comment names:
      `PreToolUseService._read_active_wave()` calls
      `self._wave_active_reader.read(Path.cwd())` directly
      (`pre_tool_use_service.py:508`), never consulting `DES_PROJECT_DIR`.
      Confirmed via the code-fact port (`callers_of resolve_nwave_root`):
      the resolver has exactly TWO callers, both inside its OWN acceptance
      test (`tests/des/acceptance/sustainable-test-suite/.../slice_05_composition.py`)
      -- it is a dormant seam, never consumed by the hinge it was built to fix.

      So TODAY, isolation for this floor is achieved SOLELY by the
      `real_repo_scan` serialization -- there is no fallback. Any fix that
      relaxes the group before wiring this call site through a per-test
      overridable root regresses correctness, not just speed. This test
      documents that dependency as an executable assertion so it cannot be
      silently dropped: it is RED now (the call site ignores the isolation
      override), and it must go GREEN (the call site honours it) BEFORE
      (a)'s ceiling can be safely lowered further or the group removed.

Neither test drives a `cwd=<real repo>` subprocess itself (test (a) collects
in-process via a nested `pytest.main()`; test (b) drives the real filesystem
adapter directly and only `chdir`s) -- this file legitimately does not match
the detector it exercises, and is not itself pinned to `real_repo_scan`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.adapters.driven.filesystem.wave_active_filesystem_store import (
    WaveActiveFilesystemStore,
)
from des.adapters.driven.logging.null_audit_log_writer import NullAuditLogWriter
from des.adapters.driven.time.system_time import SystemTimeProvider
from des.application.pre_tool_use_service import PreToolUseService
from des.domain.des_marker_parser import DesMarkerParser
from des.domain.wave_active import WaveActiveRecord, WaveProvenance
from des.ports.driven_ports.wave_active_store import WaveActiveReader
from des.ports.driver_ports.pre_tool_use_port import PreToolUseInput
from des.ports.driver_ports.validator_port import ValidationResult, ValidatorPort


# ---------------------------------------------------------------------------
# (a) speed regression -- the group must not dominate collected items.
# ---------------------------------------------------------------------------

# See module docstring "(a)" for the full derivation of this number from the
# RCA's measured ~26.9x per-item cost ratio between group and non-group items.
_REAL_REPO_SCAN_ITEM_FRACTION_CEILING = 0.10

_FULL_SUITE_MARKER_EXPR = "unit or integration or acceptance"


class _GroupFractionCollector:
    """In-process pytest plugin: counts items pinned to `real_repo_scan`.

    Runs via `pytest.main()` NESTED inside this test's own already-running
    pytest process -- no subprocess, no `cwd=` keyword argument anywhere in
    this call, so this collection pass is NOT itself a `cwd=<real repo>`
    subprocess the detector under test would match.
    """

    def __init__(self) -> None:
        self.total_items: int | None = None
        self.pinned_items: int | None = None

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        self.total_items = len(session.items)
        self.pinned_items = sum(
            1
            for item in session.items
            if any(
                marker.name == "xdist_group" and marker.args == ("real_repo_scan",)
                for marker in item.iter_markers()
            )
        )


def test_real_repo_scan_group_does_not_dominate_collected_items() -> None:
    """The `real_repo_scan` xdist_group must not exceed 10% of collected items.

    See the module docstring "(a)" for the threshold derivation. This
    re-collects the LIVE suite on every run (never a hardcoded snapshot), so
    it catches both "the group grew back" and "the total suite shrank enough
    that the same absolute group size is now proportionally worse."
    """
    collector = _GroupFractionCollector()
    exit_code = pytest.main(
        ["--collect-only", "-q", "-m", _FULL_SUITE_MARKER_EXPR],
        plugins=[collector],
    )
    assert collector.total_items is not None and collector.total_items > 0, (
        "nested collection produced no items (pytest.main exit_code="
        f"{exit_code!r}) -- cannot evaluate the real_repo_scan weight without "
        "a real collection pass; this is a harness failure, not the defect "
        "under test."
    )

    fraction = collector.pinned_items / collector.total_items

    assert fraction <= _REAL_REPO_SCAN_ITEM_FRACTION_CEILING, (
        f"'real_repo_scan' xdist_group holds {collector.pinned_items} of "
        f"{collector.total_items} collected items ({fraction:.1%}), above the "
        f"{_REAL_REPO_SCAN_ITEM_FRACTION_CEILING:.0%} ceiling. Under `--dist "
        "loadgroup` every member of this group runs on ONE worker, serialized "
        "-- `-n auto` cannot parallelize past this group's own wall time, "
        "which the RCA measured at 84.7% of total suite weight at the "
        "group's CURRENT (larger) size. See the module docstring '(a)' for "
        "the full threshold derivation (the RCA's measured ~26.9x per-item "
        "cost ratio between group and non-group items)."
    )


# ---------------------------------------------------------------------------
# (b) isolation-preservation guard -- whatever replaces the serialization
# must not silently drop the isolation it protects.
# ---------------------------------------------------------------------------


class _UnreachedValidator(ValidatorPort):
    """Classic prompt validator that must never be reached by this path.

    Both the S1 (no-wave, allow) and S2 (wave-active partial-context, block)
    branches under test resolve BEFORE Step 5's `validate_prompt` call
    (`pre_tool_use_service.py` lines ~184-260) -- reaching this is itself a
    sign the test built the wrong scenario, not a legitimate outcome.
    """

    def validate_prompt(self, prompt: str) -> ValidationResult:
        raise AssertionError(
            "classic prompt validation must not be reached by a markerless "
            "partial-context dispatch -- it resolves at S1/S2, before Step 5"
        )


@pytest.mark.negative_at
def test_pre_tool_use_service_does_not_honor_des_project_dir_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`PreToolUseService` must read the wave-active floor from an isolated
    per-test root when `DES_PROJECT_DIR` overrides it -- exactly the
    isolation `resolve_nwave_root()` (DDD-14/15) was built to provide.

    Setup: two real, empty tmp roots. `shared_cwd_root` stands in for the
    REAL repo checkout a `cwd=<real repo>` subprocess test runs against --
    ARMED with an active 'devops' wave floor (mirrors a live/stale floor a
    concurrent dispatch could leave behind). `isolated_root` stands in for
    the per-test tmp dir `DES_PROJECT_DIR` is meant to redirect state into --
    left UNARMED (no floor -> NoWaveActive -> no active wave).
    `DES_PROJECT_DIR` is set to `isolated_root`; the process `chdir`s to
    `shared_cwd_root` (mirrors `subprocess.run(..., cwd=<real repo>)`).

    A markerless-but-partial-context dispatch (`DES-STEP-ID` only, no
    `DES-WAVE`, no `DES-VALIDATION`) is BLOCKED (`WAVE_MARKER_BYPASS`) when
    the active wave is 'devops' (S2 branch), and ALLOWED when no wave is
    active (S1 branch) -- both confirmed by the sibling regression AT
    `test_wave_marker_allows_matching_wave_child_non_atdd_pure.py`
    (scenarios 1-2), which drives the identical composition.

    If `DES_PROJECT_DIR` were honoured, the service would read the UNARMED
    `isolated_root` floor and ALLOW. TODAY it reads the ARMED `shared_cwd_root`
    floor (via bare `Path.cwd()`, `pre_tool_use_service.py:508`) and BLOCKS --
    proving isolation is not wired into this call site. See the module
    docstring '(b)' for why this matters: it is the seam the `real_repo_scan`
    group's serialization currently substitutes for.
    """
    shared_cwd_root = tmp_path / "shared_repo_cwd"
    isolated_root = tmp_path / "isolated_des_project_dir"
    shared_cwd_root.mkdir()
    isolated_root.mkdir()

    store: WaveActiveReader = WaveActiveFilesystemStore()
    assert isinstance(store, WaveActiveFilesystemStore)
    store.arm(
        shared_cwd_root,
        WaveActiveRecord(
            wave="devops", provenance=WaveProvenance.COMMAND, entry_pending=False
        ),
    )
    # isolated_root deliberately left unarmed -- no floor -> NoWaveActive.

    monkeypatch.setenv("DES_PROJECT_DIR", str(isolated_root))
    monkeypatch.chdir(shared_cwd_root)

    service = PreToolUseService(
        marker_parser=DesMarkerParser(),
        prompt_validator=_UnreachedValidator(),
        audit_writer=NullAuditLogWriter(),
        time_provider=SystemTimeProvider(),
        wave_active_reader=WaveActiveFilesystemStore(),
    )
    decision = service.validate(
        PreToolUseInput(
            prompt="<!-- DES-STEP-ID: 01-01 -->\nwork on something",
            subagent_type="child",
            wave_entering=False,
        )
    )

    assert decision.action == "allow", (
        "PreToolUseService._read_active_wave() must honour DES_PROJECT_DIR "
        "(the per-test isolation override) and read the UNARMED isolated "
        "root -- expected action='allow' (S1: no wave active). Observed "
        f"action={decision.action!r} reason={decision.reason!r}: the service "
        "read the ARMED shared cwd floor instead of the isolated root, "
        "proving `_read_active_wave()` still calls bare `Path.cwd()` "
        "(pre_tool_use_service.py:508) rather than an isolation-aware "
        "resolver. Until this is fixed, the `real_repo_scan` xdist_group's "
        "SERIALIZATION is the ONLY thing preventing this exact "
        "order-dependent collision across xdist workers -- do not relax or "
        "remove that group without wiring this call site through a "
        "per-test-overridable root first (see module docstring '(b)')."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
