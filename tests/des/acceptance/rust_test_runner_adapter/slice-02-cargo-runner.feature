@feature-f-rust-test-runner-adapter @slice-02
Feature: The cargo run-facet maps cargo exit-semantics and registers through the unified plugin
  As an operator running the nWave spine against a Rust target
  I want the cargo run-facet to shell the declared cargo command and map its exit
    code to PASS / FAIL / INDETERMINATE, registered THROUGH the nwave-lang-rust plugin
  So that a Rust spine runs through the FULL spine (no DES-EXEMPT) -- a green run
    PASSes, a real failure FAILs (never swallowed), a no-test-run is INDETERMINATE
    (never a vacuous pass), and the runner is the plugin's port-facet, not hardcoded

  # slice-02 of f-rust-test-runner-adapter (atdd_pure). Ships three net-new seams:
  #   C1  the cargo run-facet run_cargo_scope (cargo_runner.py) -- shells the
  #       target's cargo, maps the 4 §C1 exit-semantics to PASS/FAIL/INDETERMINATE.
  #   C2  the plugin-populated RunnerRegistry (runner_registry.py) -- GLOBAL_REGISTRY
  #       + seed_runner_registry(); replaces the hardcoded if name=="pytest" dispatch.
  #   C3  the nwave-lang-rust LanguageAdapterPlugin (nwave_lang_rust.py) -- whose
  #       register_adapters writes run_cargo_scope under the EXISTING "cargo-test"
  #       token (D8 -- no rename); THE unification.
  #
  # DRIVING SURFACE (Mandate-13, Layer 3 subprocess): the REAL production SUT
  # imported + invoked in a CHILD interpreter. ZERO des.adapters.* import in the test
  # process (slice-02-RC2 discipline) -- the SUT is only ever imported in the child.
  #
  # FAKE-cargo determinism (AT-4/5/6 -- explicit fixture approach): the exit-semantics
  # ATs drive run_cargo_scope over a planted REAL chmod+x fake `cargo` on a controlled
  # PATH that emits a controlled exit code/output (GREEN exit 0 / RED exit 1 / NO_MATCH
  # exit 4). The run-facet resolves the fake via the slice-01 resolve_tool PATH rung and
  # shells it exactly like a real cargo -- so the §C1 exit-semantics are exercised
  # end-to-end through the REAL run-facet, DETERMINISTICALLY in CI, with NO real Rust
  # toolchain. AT-7 is a PURE in-process/child WIRING check (no fake-cargo); its
  # cargo-unresolvable continuation drives run_cargo_scope over a cargo-absent fixture.
  #
  # DORMANT-SEAM RECONCILIATION (D11): the net-new DESIGN seam this slice declares is
  # the plugin->runner registration -- register_adapters writing run_cargo_scope into
  # the registry under "cargo-test" (Tsunami callers-of register_adapters: 0 at HEAD;
  # the seam is genuinely dormant). AT-7 names THAT exact seam as its driving port:
  # it runs plugin.register_adapters(registry) through the real plugin instance and
  # asserts the observable effect -- registry.lookup("cargo-test") resolving to the
  # cargo run-facet. Indirect wiring (registry registration) is the valid witness, not
  # a literal call-site. The run-facet seam (run_cargo_scope) is witnessed by AT-4..6
  # driving it over real subprocess + the cargo verdict observable.
  #
  # RED-for-right-reason (active-RED scaffold, atdd_pure -- NOT @skip): at HEAD the
  # cargo_runner / runner_registry / nwave_lang_rust modules are absent, so the child
  # import raises ModuleNotFoundError (rc != 0, no VERDICT:/REGISTERED: marker). Each
  # Then turns a captured observable into a semantic AssertionError. GREEN once DELIVER
  # ships the three modules. No @skip, no import / collection error in the test process.

  @slice-02 @driving_port @real-io @us-cargo-exit-semantics @contract-shape:bounded-change
  Scenario: A green cargo run yields a PASS verdict
    Given a Rust target whose cargo exits zero with all tests passing
    When the cargo run-facet runs the declared command
    Then the run verdict is pass

  @slice-02 @driving_port @real-io @us-cargo-exit-semantics @error @contract-shape:bounded-change
  Scenario: A failing cargo run yields a FAIL verdict, not indeterminate
    Given a Rust target whose cargo exits non-zero after executing tests
    When the cargo run-facet runs the declared command
    Then the run verdict is fail

  @slice-02 @driving_port @real-io @us-cargo-exit-semantics @error @contract-shape:bounded-change
  Scenario: A cargo run that matched no tests yields an indeterminate verdict, not a pass
    Given a Rust target whose cargo exits four having run no tests
    When the cargo run-facet runs the declared command
    Then the run verdict is indeterminate

  @slice-02 @driving_port @us-unification @contract-shape:bounded-change
  Scenario: The cargo run-facet registers through the nwave-lang-rust plugin under the cargo-test token
    Given the nwave-lang-rust plugin and an empty runner registry
    When the plugin registers its adapters into the registry
    Then the registry resolves the cargo-test token to the cargo run-facet

  @slice-02 @driving_port @real-io @us-unification @error @contract-shape:bounded-change
  Scenario: A Rust target whose cargo is unresolvable yields a loud indeterminate naming the remediation
    Given a Rust target whose cargo is absent from PATH and every known location
    When the cargo run-facet runs the declared command
    Then the run verdict is indeterminate
    And the indeterminate result names the remediation
