"""Typed vocabulary for slice-05 ATs — PER-TEST .nwave STATE ISOLATION (Mandate-12).

slice-05 of sustainable-test-suite is the PARALLELISM-RESTORATION slice: the full
suite was forced SERIAL (`-n0`) because tests share `.nwave/` state via `Path.cwd()`
when cwd=repo (a stale wave floor in `.nwave/wave-active/active.json`, and other
per-test `.nwave` writes, read off `Path.cwd()` by production
`WaveActiveReader`/`pre_tool_use_handler`). Under `-n auto` the xdist workers share
the repo cwd, so one worker's `.nwave` write contaminates another worker's
wave-aware read — the cwd=repo flakiness that masked itself as "intermittent red,
not reproducible in a clean tree".

The CURE this slice proves: per-test `.nwave` ROOT isolation — each test resolves its
own `.nwave` root under a per-test tmp dir (via a `DES_PROJECT_DIR`-rooted resolver +
an autouse fixture), so NO shared `Path.cwd()/.nwave` is touched and `-n auto` passes
GREEN where serial `-n0` was MASKING the interference.

Driving surface (Mandate-13):
  * Layer 3 subprocess (walking skeleton / no-mask): a hermetic `pytest -p xdist -n 2`
    run over a SMALL fixture test-set that deliberately writes `.nwave` state, observed
    GREEN WITH the isolation harness and interfering WITHOUT it (a real subprocess is
    the SUT — no production module imported at the step boundary).
  * Layer 3 composition (isolation-observable / stale-floor): the per-test `.nwave`-root
    RESOLVER entry point, observed producing a per-test isolated `.nwave` root (distinct
    paths per test, no cross-test bleed; a stale real-repo floor does not leak in).

This module owns the TEST-SIDE typed vocabulary the step bodies coerce Gherkin literals
into (no raw `str` where an enum exists):

  * `ParallelOutcome` — the closed outcome-token set a hermetic parallel run reports
    (all-isolated-green / cross-test-interference) as observed from the subprocess.
  * `IsolationVerdict` — the closed per-test `.nwave`-root isolation verdict the resolver
    surface reports (per-test-isolated / shared-cwd-root).

The schema/decision constants from earlier slices are NOT reused — slice-05's SUT is
the test-infrastructure isolation mechanism, a DISTINCT domain from the sustainability
gate (slices 02-04). These tokens are test-arrangement vocabulary, legitimately
test-local (promotion-rule clause (c)).
"""

from __future__ import annotations

from enum import Enum


class ParallelOutcome(str, Enum):
    """The closed outcome a hermetic `pytest -n` run over the fixture test-set reports.

    SSOT (DELIVER lands the harness this observes): `tests/conftest.py` per-test
    `.nwave`-root isolation fixture + `src/des/.../nwave_root.py` resolver.

      * `all-isolated-green` — every fixture test that wrote `.nwave` state passed under
                               parallel workers because each test's `.nwave` root was
                               isolated (the core promise: parallelism without
                               correctness loss).
      * `cross-test-interference` — a fixture test FAILED because a sibling worker's
                                    shared-cwd `.nwave` write leaked across the worker
                                    boundary (the masked interference serial `-n0` hid).
    """

    ALL_ISOLATED_GREEN = "all-isolated-green"
    CROSS_TEST_INTERFERENCE = "cross-test-interference"


class IsolationVerdict(str, Enum):
    """The closed per-test `.nwave`-root isolation verdict the resolver surface reports.

    SSOT (DELIVER lands the resolver this observes): the per-test `.nwave`-root resolver
    (`DES_PROJECT_DIR`-rooted) wired by the autouse isolation fixture in `tests/conftest.py`.

      * `per-test-isolated` — two tests resolve DISTINCT `.nwave` roots, neither rooted at
                              the shared repo `Path.cwd()`; no cross-test state bleed.
      * `shared-cwd-root`   — the resolver returned the shared repo-cwd `.nwave` root (the
                              UN-isolated status that contaminates under `-n auto`).
    """

    PER_TEST_ISOLATED = "per-test-isolated"
    SHARED_CWD_ROOT = "shared-cwd-root"


__all__ = [
    "IsolationVerdict",
    "ParallelOutcome",
]
