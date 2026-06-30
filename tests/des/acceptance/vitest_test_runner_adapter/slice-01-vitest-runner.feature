@feature-vitest-test-runner-adapter
Feature: The vitest run-facet shells the declared vitest command and maps vitest exit-semantics
  As an operator running the nWave spine against a JS/TS target
  I want the vitest run-facet to resolve the target's vitest binary, shell the
    declared vitest run command at the target root, and map its exit code to
    PASS / FAIL / INDETERMINATE
  So that a JS/TS spine runs through the port like Python, Rust, and Go -- a green
    run PASSes, a real failure FAILs (never swallowed), and an unresolvable vitest
    is a LOUD INDETERMINATE (never a silent pass, never a pytest fallback), with
    the feature's declared subcommand shelled as-is at cwd=target_root

  # slice-01 of vitest-test-runner-adapter (atdd_pure). Ships ONE net-new seam:
  #   the JS/TS run-facet run_vitest_scope (vitest_runner.py) -- mirrors
  #   run_go_scope / run_cargo_scope: resolves the target's vitest via the shared
  #   resolve_tool scale, shells the declared `vitest run` command at
  #   cwd=target_root, maps exit 0 -> PASS / non-zero -> FAIL / unresolvable ->
  #   INDETERMINATE (RunnerAdapterUnavailable).
  #
  # DRIVING SURFACE (Mandate-13, Layer 3 subprocess): the REAL production SUT
  # (run_vitest_scope) imported + invoked in a CHILD interpreter. ZERO
  # des.adapters.* import in the test process -- the SUT is only ever imported in
  # the child.
  #
  # FAKE-vitest determinism (AC-1/2/4 -- explicit fixture approach): the
  # exit-semantics ATs drive run_vitest_scope over a planted REAL chmod+x fake
  # `vitest` on a controlled PATH that emits a controlled exit code/output (GREEN
  # exit 0 / RED exit non-zero) AND records its argv + cwd. The run-facet resolves
  # the fake via resolve_tool's PATH rung and shells it exactly like a real vitest
  # -- so the exit-semantics + the declared-command-shelled contract are exercised
  # end-to-end through the REAL run-facet, DETERMINISTICALLY in CI, with NO real
  # Node / vitest toolchain. AC-3 drives run_vitest_scope over a vitest-absent
  # fixture (PATH empty, known-locations empty).
  #
  # VITEST-vs-cargo (like go): there is NO cargo-style exit-4 NO_MATCH empty-scope.
  # So VitestExitScenario has only GREEN (0) and RED (non-zero); there is NO
  # "vitest ran no tests -> INDETERMINATE" scenario (OUT-OF-SCOPE per the
  # feature-delta). INDETERMINATE is reached ONLY via an unresolvable vitest (AC-3).
  #
  # RED-for-right-reason (active-RED scaffold, atdd_pure -- NOT @skip): at HEAD the
  # vitest_runner module is absent, so the child import raises ModuleNotFoundError
  # (rc != 0, no VERDICT:/ARGV: marker). Each Then turns a captured observable into
  # a semantic AssertionError. GREEN once DELIVER ships vitest_runner.run_vitest_scope.
  # No @skip, no import / collection error in the test process.

  @slice-01 @driving_port @real-io @us-vitest-exit-semantics @contract-shape:bounded-change
  Scenario: A green vitest run yields a PASS verdict
    Given a JS/TS target whose vitest run exits zero with all tests passing
    When the vitest run-facet runs the declared command
    Then the run verdict is pass

  @slice-01 @driving_port @real-io @us-vitest-exit-semantics @error @contract-shape:bounded-change
  Scenario: A failing vitest run yields a FAIL verdict, not indeterminate
    Given a JS/TS target whose vitest run exits non-zero after executing tests
    When the vitest run-facet runs the declared command
    Then the run verdict is fail

  @slice-01 @driving_port @real-io @us-vitest-exit-semantics @error @contract-shape:bounded-change
  Scenario: A JS/TS target whose vitest is unresolvable yields a loud indeterminate naming the remediation
    Given a JS/TS target whose vitest is absent from PATH and every known location
    When the vitest run-facet runs the declared command
    Then the run verdict is indeterminate
    And the indeterminate result names the remediation

  @slice-01 @driving_port @real-io @us-declared-command-shelled @contract-shape:bounded-change
  Scenario: The vitest run-facet shells the feature's declared subcommand as-is at the target root
    Given a JS/TS target whose vitest records the argv and working directory it is shelled with
    When the vitest run-facet runs the declared command
    Then the vitest binary was invoked with the declared subcommand as-is
    And the vitest binary was invoked with the working directory set to the target root
