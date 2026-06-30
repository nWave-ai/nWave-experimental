@feature-wire-multilang-run-facets
Feature: The runner registry wires the Go and JS/TS run-facets into the production dispatch
  As a spine operator on a Go or JS/TS target
  I want the production dispatch RunnerAdapter(token).run() to actually REACH
    run_go_scope / run_vitest_scope through the runner registry
  So that resolve(target).run() runs my tests through the port instead of failing
    with RunnerAdapterUnavailable because the run-facet was never registered

  # slice-01 of wire-multilang-run-facets (atdd_pure). Closes epic members C13 + C14,
  # demoted by the adversarial theater-audit swarm (2026-06-24) as catalogued != wired.
  #
  # THE WIRING GAP: run_go_scope (go_runner.py) + run_vitest_scope (vitest_runner.py)
  # EXIST and are correct, but seed_runner_registry (runner_registry.py:104-105)
  # registers ONLY pytest + cargo-test, and the nwave.lang.adapter entry-point discovery
  # is EMPTY in the installed sys.path-insert tree (BUG C). So the PRODUCTION dispatch
  #   resolve(target) -> RunnerAdapter("go-test"/"vitest")
  #   -> .run() -> GLOBAL_REGISTRY.lookup(token) -> None -> RunnerAdapterUnavailable
  # NEVER reaches the run-facet. resolve()/_REGISTRY already map go.mod->go-test and
  # package.json(vitest)->vitest (test_runner_port.py:149-150) -- ONLY the registration is
  # missing. This feature WIRES both run-facets into seed_runner_registry (mirroring the
  # cargo direct-registration at :105).
  #
  # DRIVING SURFACE (Mandate-13, Layer 3 subprocess): the REAL PRODUCTION REGISTRY DISPATCH
  # -- seed_runner_registry() + RunnerAdapter(token).run() over GLOBAL_REGISTRY.lookup --
  # driven in a CHILD interpreter over a hermetic target + a FAKE runner on a controlled
  # PATH. CRITICAL: this NEVER imports a run-facet directly. The C13/C14 ATs the swarm
  # flagged imported run_go_scope / run_vitest_scope DIRECTLY (the bypass = the theater);
  # these ATs reach the run-facet ONLY through the registry lookup -- the integrated path.
  # ZERO des.adapters.*/des.ports.* import in the test process (only in the child).
  #
  # RED-for-right-reason (active-RED scaffold, atdd_pure -- NOT @skip): at HEAD the go-test
  # and vitest tokens are NOT registered in seed_runner_registry, so the production dispatch
  # raises RunnerAdapterUnavailable (the run-facet is never reached) -> OUTCOME:UNWIRED.
  # Each AC-1/AC-2 Then turns that captured observable into a semantic AssertionError. GREEN
  # once DELIVER registers the run-facets under their resolve() tokens in seed_runner_registry.
  # AC-3 (preservation) is live-green: pytest + cargo-test are already registered.

  @slice-01 @driving_port @real-io @us-multilang-dispatch-wired @contract-shape:bounded-change
  Scenario: The Go production dispatch reaches the go run-facet through the registry
    Given a hermetic Go target with a fake go on PATH
    When the production dispatch runs through the runner registry
    Then the dispatch outcome is wired

  @slice-01 @driving_port @real-io @us-multilang-dispatch-wired @contract-shape:bounded-change
  Scenario: The JS/TS production dispatch reaches the vitest run-facet through the registry
    Given a hermetic JS/TS target with a fake vitest on PATH
    When the production dispatch runs through the runner registry
    Then the dispatch outcome is wired

  @slice-01 @driving_port @us-existing-runners-preserved @contract-shape:unbounded-preservation
  Scenario: Seeding the registry preserves the existing pytest and cargo-test registrations
    Given the runner registry is seeded
    When the existing runner tokens are looked up
    Then the existing runners still resolve
