@feature-sustainable-test-suite
Feature: A maintainer's full suite runs fast and parallel again

  slice-05 of sustainable-test-suite — PER-TEST .nwave STATE ISOLATION (DESIGN
  Component Decomposition: "Per-test `.nwave` state isolation harness"). The full
  suite was forced SERIAL (`-n0`) because tests share `.nwave/` state via
  `Path.cwd()` when cwd=repo: a stale wave floor in `.nwave/wave-active/active.json`
  (and other per-test `.nwave` writes) read off `Path.cwd()` by production
  `WaveActiveReader`/`pre_tool_use_handler` contaminate cross-test under `-n auto`
  (xdist workers share the repo cwd). The CURE this slice proves: per-test `.nwave`
  ROOT isolation — each test resolves its OWN `.nwave` root under a per-test tmp dir
  (a `DES_PROJECT_DIR`-rooted resolver wired by an autouse fixture), so `-n auto`
  passes GREEN where serial `-n0` was MASKING the interference.

  Driving surfaces (Mandate-13):
    * WALKING SKELETON / NO-MASK — a hermetic `pytest -p xdist -n 2` run over a SMALL
      generated fixture test-set that deliberately writes `.nwave` state, observed as a
      real subprocess on a hermetic tmp_path (the subprocess IS the SUT; no production
      module imported at the step boundary). WITH the harness the run is GREEN; WITHOUT
      it the shared-cwd writes interfere across workers (the isolation is load-bearing).
    * ISOLATION-OBSERVABLE / STALE-FLOOR — the per-test `.nwave`-root RESOLVER entry
      point (`des.domain.nwave_root.resolve_nwave_root`), observed producing per-test
      isolated roots (distinct paths, none the shared repo cwd) and refusing to leak a
      stale real-repo floor.

  SCOPE: parallelism restoration via per-test `.nwave`-root isolation. Error/edge
  coverage is PRIMARY (3/5: the no-mask interference proof, the stale-floor
  non-leak vector, and the shared-cwd un-isolated status). The walking-skeleton
  carries the @property invariant (every fixture test that writes `.nwave` state
  passes under parallel workers) as its Then.

  Active-RED: at HEAD the per-test `.nwave`-root resolver is a RED scaffold
  (`resolve_nwave_root()` raises AssertionError) and the autouse isolation fixture in
  tests/conftest.py does not exist, so the resolver-driven scenarios fire a clean
  AssertionError when they invoke the resolver and the subprocess scenarios observe
  cross-test-interference where the WITH-isolation contract demands all-isolated-green
  (MISSING_FUNCTIONALITY — the isolation harness + resolver are not yet implemented),
  never an ImportError. DELIVER makes them GREEN by landing the DES_PROJECT_DIR-
  preferring resolver + the autouse per-test isolation fixture.

  @slice-05 @walking_skeleton @driving_port @real-io @property @contract-shape:bounded-change
  Scenario: A parallel fixture suite writing .nwave state runs green under isolated roots
    Given a parallel fixture suite that writes .nwave state under the isolation harness
    When the parallel fixture suite runs under two workers
    Then every fixture test that writes .nwave state passes under the parallel workers

  @slice-05 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: Without the isolation harness the shared cwd .nwave state interferes across workers
    Given a parallel fixture suite that writes .nwave state with the isolation harness disabled
    When the parallel fixture suite runs under two workers
    Then a fixture test reports cross-worker .nwave state interference

  @slice-05 @driving_port @real-io @contract-shape:bounded-change
  Scenario: Two tests under the harness resolve distinct per-test .nwave roots
    Given two tests run under the per-test .nwave isolation harness
    When the resolver is asked for each test's .nwave root
    Then the two tests resolve distinct per-test .nwave roots away from the shared repo cwd

  @slice-05 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: A stale shared-repo wave floor does not leak into an isolated test
    Given a stale wave-active floor is left in the shared repo at session start
    When the resolver runs inside an isolated per-test root
    Then the isolated test's resolved .nwave root is free of the stale wave floor

  @slice-05 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: Resolving with no per-test override falls back to the shared repo cwd root
    Given a test runs with no per-test .nwave override configured
    When the resolver is asked for the .nwave root with no override
    Then the resolved .nwave root is the shared repo cwd root
